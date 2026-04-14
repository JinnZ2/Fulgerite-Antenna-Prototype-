#!/usr/bin/env python3
"""
Megacasting Dendrite Growth Simulation (Simplified Phase-Field + Fluid)

2D cellular automaton that approximates dendrite growth under electromagnetic
stirring (EMS) and ultrasonic vibration during alloy solidification. The model
is intentionally crude — it is NOT a replacement for full phase-field solvers
like PRISMS-PF or CALPHAD-coupled simulations. It exists to give a visual,
intuitive sense of how active melt conditioning breaks dendrite arms and
accelerates solidification.

Physical model:
- Phase field phi:     0 = liquid, 1 = solid, 0 < phi < 1 = interface
- Temperature field T: degrees Celsius
- Composition C:       wt% Si (default Al-7%Si binary)
- Liquidus line:       T_liq ~= 660 - 5 * C (Al-Si, simplified)
- EMS stirring:        vortex velocity field + hacky roll-based solute advection
- Ultrasonic:          cavitation-like fragmentation of interface cells
- Growth:              simplified Allen-Cahn-style update driven by undercooling

Usage:
    python dendrite_sim.py                                 # Default: stir + ultra
    python dendrite_sim.py --stir 0 --ultra 0              # Baseline (no conditioning)
    python dendrite_sim.py --compare                       # Side-by-side
    python dendrite_sim.py --compare --save compare.png    # Headless save
    python dendrite_sim.py --steps 300 --seed 42           # Reproducible run
"""

import argparse

import numpy as np
from scipy.ndimage import convolve


class DendriteSim:
    """2D cellular automaton for dendrite growth under active melt conditioning."""

    def __init__(self, nx=200, ny=200, dx=1e-6, T0=680.0, T_boundary=700.0,
                 seed=None):
        self.nx, self.ny = nx, ny
        self.dx = dx
        self.T_boundary = T_boundary  # pour / edge temperature (C)
        self._rng = np.random.default_rng(seed)
        # Phase field: 0 = liquid, 1 = solid, 0.5 = interface
        self.phi = np.zeros((nx, ny))
        # Temperature field (C) — start slightly above liquidus so modest
        # global cooling drives the bulk below liquidus over the run.
        self.T = np.full((nx, ny), T0)
        # Alloy composition (Al-7%Si by default)
        self.C = np.full((nx, ny), 7.0)  # wt% Si
        # Nucleation seed centers (kept for optional visualization / debugging)
        self.seed_centers = []

    def seed_equiaxed(self, n_seeds=50):
        """Plant random nucleation sites as small solid blocks near the solidus."""
        for _ in range(n_seeds):
            x = int(self._rng.integers(20, self.nx - 20))
            y = int(self._rng.integers(20, self.ny - 20))
            self.seed_centers.append((x, y))
            self.phi[x:x + 3, y:y + 3] = 1.0
            self.T[x:x + 3, y:y + 3] = 550.0  # approx solidus for Al-Si

    def apply_stirring(self, intensity=1.0):
        """
        EMS: creates a rotational flow field that advects solute.
        Simplified: the vortex field is computed for the metric, but actual
        advection is approximated by rolling the composition array.
        """
        if intensity == 0:
            return 0.0
        X, Y = np.meshgrid(np.arange(self.nx), np.arange(self.ny), indexing="ij")
        cx, cy = self.nx // 2, self.ny // 2
        r = np.hypot(X - cx, Y - cy) + 1e-6
        u = intensity * (Y - cy) / r
        # v component exists physically but only |u| is reported as a mixing metric
        # Advect composition (intentionally crude: a rigid roll stands in for advection)
        self.C = np.roll(self.C, int(intensity), axis=0)
        return float(np.mean(np.abs(u)))

    def apply_ultrasonic(self, amplitude=1.0, frequency=20e3):
        """
        High-frequency pressure waves cause cavitation near dendrite tips.
        Interface cells (0.3 < phi < 0.8) have a small probability of
        fragmenting back to liquid each step. Vectorized for speed.
        """
        if amplitude == 0:
            return 0.0
        frag_prob = amplitude * 0.01  # per-step, per-eligible-cell probability
        interface = (self.phi > 0.3) & (self.phi < 0.8)
        roll = self._rng.random((self.nx, self.ny))
        fragment = interface & (roll < frag_prob)
        self.phi[fragment] = 0.0
        return float(frag_prob)

    def diffuse_temperature(self, dt=0.001, alpha=1e-5, cooling_rate=0.5):
        """
        Simple heat diffusion with a uniform global cooling term.

        - alpha*dt/dx**2 is clamped to a CFL-stable value (2D explicit-scheme
          stability limit is 0.25), so callers can pass physically meaningful
          alpha/dt/dx without blowing up the field.
        - cooling_rate models bulk heat extraction (mold chilling, radiation)
          as a uniform per-step temperature drop. Without this the boundary
          at T_boundary pumps heat into the domain and nothing cools below
          liquidus. Latent heat of solidification is ignored for speed.
        """
        coef = min(alpha * dt / self.dx ** 2, 0.2)
        kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=float)
        laplacian = convolve(self.T, kernel, mode="wrap")
        self.T += coef * laplacian
        self.T -= cooling_rate
        # Dirichlet boundary: edges held at the pour temperature
        self.T[0, :] = self.T[-1, :] = self.T_boundary
        self.T[:, 0] = self.T[:, -1] = self.T_boundary

    def grow(self, beta=1e-3):
        """
        Phase field evolution: solid grows where T < liquidus.
        Simplified Allen-Cahn-style update, vectorized.
        """
        # Liquidus temperature for Al-Si (approx): 660 - 5 * wt% Si
        T_liq = 660.0 - 5.0 * self.C
        undercool = np.clip(T_liq - self.T, 0.0, None)
        growing = (self.phi < 1.0) & (undercool > 0)
        self.phi[growing] += beta * (1 - self.phi[growing]) * undercool[growing]
        np.clip(self.phi, 0.0, 1.0, out=self.phi)

    def run(self, steps=200, stir_intensity=1.0, ultra_amp=1.0, n_seeds=30,
            log_every=10):
        """Run the simulation and return (solid_fraction_history, final_phi)."""
        self.seed_equiaxed(n_seeds)
        history = []
        for step in range(steps):
            self.diffuse_temperature()
            self.apply_stirring(stir_intensity)
            self.apply_ultrasonic(ultra_amp)
            self.grow()
            if step % log_every == 0:
                history.append(float(np.mean(self.phi)))
        return history, self.phi


def _get_matplotlib(save_path):
    """Import matplotlib, forcing the Agg backend if running headless."""
    try:
        import matplotlib
        if save_path:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        print("matplotlib not installed. Install with: pip install matplotlib")
        return None


def plot_single(history, phi, title_hist, title_phi, save_path=None):
    """Plot solid-fraction history and final microstructure for a single run."""
    plt = _get_matplotlib(save_path)
    if plt is None:
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))
    ax1.plot(history, color="#8B4513")
    ax1.set_xlabel("Time step (x10)")
    ax1.set_ylabel("Solid fraction")
    ax1.set_title(title_hist)
    ax1.grid(True, alpha=0.3)

    ax2.imshow(phi, cmap="gray", vmin=0, vmax=1)
    ax2.set_title(title_phi)
    ax2.axis("off")

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved plot to {save_path}")
    else:
        plt.show()


def plot_comparison(hist_no, phi_no, hist_yes, phi_yes, save_path=None):
    """Plot baseline vs conditioned side-by-side."""
    plt = _get_matplotlib(save_path)
    if plt is None:
        return

    fig = plt.figure(figsize=(12, 8))
    gs = fig.add_gridspec(2, 2)

    ax_hist = fig.add_subplot(gs[0, :])
    ax_hist.plot(hist_no, label="No EMS/ultrasound", color="#8B4513")
    ax_hist.plot(hist_yes, label="With EMS + ultrasound", color="#1f77b4")
    ax_hist.set_xlabel("Time step (x10)")
    ax_hist.set_ylabel("Solid fraction")
    ax_hist.set_title("Dendrite growth under active melt conditioning")
    ax_hist.legend()
    ax_hist.grid(True, alpha=0.3)

    ax1 = fig.add_subplot(gs[1, 0])
    ax1.imshow(phi_no, cmap="gray", vmin=0, vmax=1)
    ax1.set_title("No conditioning\n(coarse dendrites)")
    ax1.axis("off")

    ax2 = fig.add_subplot(gs[1, 1])
    ax2.imshow(phi_yes, cmap="gray", vmin=0, vmax=1)
    ax2.set_title("EMS + ultrasound\n(fine equiaxed)")
    ax2.axis("off")

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved comparison plot to {save_path}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Megacasting dendrite growth simulation (simplified phase-field + fluid)")
    parser.add_argument("--nx", type=int, default=200, help="Grid size x (default: 200)")
    parser.add_argument("--ny", type=int, default=200, help="Grid size y (default: 200)")
    parser.add_argument("--steps", type=int, default=200, help="Number of time steps (default: 200)")
    parser.add_argument("--seeds", type=int, default=30, help="Number of nucleation seeds (default: 30)")
    parser.add_argument("--stir", type=float, default=2.0,
                        help="EMS stirring intensity (default: 2.0, 0 = off)")
    parser.add_argument("--ultra", type=float, default=0.5,
                        help="Ultrasonic amplitude (default: 0.5, 0 = off)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--compare", action="store_true",
                        help="Run baseline and conditioned side-by-side")
    parser.add_argument("--save", type=str, default=None, help="Save plot to file instead of displaying")
    parser.add_argument("--no-plot", action="store_true", help="Skip plotting")
    args = parser.parse_args()

    if args.compare:
        sim_no = DendriteSim(nx=args.nx, ny=args.ny, seed=args.seed)
        hist_no, phi_no = sim_no.run(steps=args.steps, stir_intensity=0,
                                     ultra_amp=0, n_seeds=args.seeds)
        sim_yes = DendriteSim(nx=args.nx, ny=args.ny, seed=args.seed)
        hist_yes, phi_yes = sim_yes.run(steps=args.steps,
                                        stir_intensity=args.stir,
                                        ultra_amp=args.ultra,
                                        n_seeds=args.seeds)
        print("=" * 50)
        print("Megacasting Dendrite Simulation — Comparison")
        print("=" * 50)
        print(f"  Grid:             {args.nx} x {args.ny}")
        print(f"  Steps:            {args.steps}")
        print(f"  Seeds:            {args.seeds}")
        print(f"  Baseline  final solid fraction: {hist_no[-1]:.3f}")
        print(f"  Conditioned final solid fraction: {hist_yes[-1]:.3f}")
        if not args.no_plot:
            plot_comparison(hist_no, phi_no, hist_yes, phi_yes, save_path=args.save)
    else:
        sim = DendriteSim(nx=args.nx, ny=args.ny, seed=args.seed)
        history, phi = sim.run(steps=args.steps,
                               stir_intensity=args.stir,
                               ultra_amp=args.ultra,
                               n_seeds=args.seeds)
        conditions = []
        if args.stir > 0:
            conditions.append(f"stir={args.stir}")
        if args.ultra > 0:
            conditions.append(f"ultra={args.ultra}")
        cond_str = ", ".join(conditions) if conditions else "no conditioning"

        print("=" * 50)
        print("Megacasting Dendrite Simulation")
        print("=" * 50)
        print(f"  Grid:             {args.nx} x {args.ny}")
        print(f"  Steps:            {args.steps}")
        print(f"  Conditions:       {cond_str}")
        print(f"  Final solid fraction: {history[-1]:.3f}")
        print(f"  Solid cells (phi>0.5): {int(np.sum(phi > 0.5))} / {args.nx * args.ny}")

        if not args.no_plot:
            plot_single(history, phi,
                        f"Solid fraction vs time ({cond_str})",
                        f"Final microstructure ({cond_str})",
                        save_path=args.save)


if __name__ == "__main__":
    main()
