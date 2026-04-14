#!/usr/bin/env python3
"""
Microfracture Energy Harvesting Simulation

Cellular-automaton model of a distributed array of brittle/piezo unit cells
under heavy-tailed wave forcing (Nazare Canyon regime). Each cell can:

  - Harvest continuous hysteresis energy from elastic strain
  - Fire discrete "fold / unfold" events releasing pulse energy
  - Accumulate fatigue damage from each event
  - Optionally be replaced when damage exceeds a threshold
  - Optionally couple weakly to neighbors through shared mechanical state
  - Optionally drift its threshold as damage accumulates (material learning)

The model is deliberately coarse - it is NOT a replacement for a finite-element
fatigue solver. Its job is to explore the SYSTEM-LEVEL behavior of a
degradation-coupled harvester: how do total energy output, event statistics,
and cell lifetime scale with flaw distribution, burst statistics, and
replacement policy?

Two physics modes:

  Base model (default): binary state flip with linear damage accumulation.
    - p_transition = min(E / threshold, 1)
    - pulse energy  = threshold * 0.5
    - damage step   = E * 0.01

  Refined model (--refined): power-law fatigue damage and phase-3 terminal
  gain, per the voice-note follow-up:
    - damage step   = (E / threshold)^m * 0.01   (m > 1)
    - pulse gain    = 1 + damage / D_fail         (rises toward failure)
    - continuous contribution attenuated by (1 - damage/D_fail) stiffness

Usage:
    python microfracture_harvest_sim.py
    python microfracture_harvest_sim.py --refined
    python microfracture_harvest_sim.py --refined --neighbors --replace
    python microfracture_harvest_sim.py --seed 42 --steps 5000 --save out.png
    python microfracture_harvest_sim.py --no-plot       # headless stats only
"""

import argparse

import numpy as np


def wave_energy(rng, burst_prob=0.05, burst_shape=3.0,
                base_mean=0.5, base_std=0.2):
    """Heavy-tailed environmental forcing: Gaussian base + rare Pareto bursts."""
    base = rng.normal(base_mean, base_std)
    burst = rng.pareto(burst_shape) if rng.random() < burst_prob else 0.0
    return max(base + burst, 0.0)


class HarvesterArray:
    """A 1D ring of unit cells with optional neighbor coupling and replacement."""

    def __init__(self, n_units=100, seed=None, refined=False,
                 neighbors=False, replace=False, learn=False,
                 fatigue_exp=2.5, failure_damage=10.0,
                 threshold_lo=0.5, threshold_hi=2.0):
        self.n = n_units
        self.rng = np.random.default_rng(seed)
        self.refined = refined
        self.neighbors = neighbors
        self.replace = replace
        self.learn = learn
        self.m = fatigue_exp
        self.D_fail = failure_damage
        self.threshold_lo = threshold_lo
        self.threshold_hi = threshold_hi

        # Thresholds drawn from a uniform distribution (flaw-size population).
        # Swap this for a Weibull or log-normal later to model real flaw stats.
        self.thresholds = self.rng.uniform(threshold_lo, threshold_hi, n_units)
        self.states = np.zeros(n_units, dtype=int)
        self.damage = np.zeros(n_units)
        self.events = np.zeros(n_units, dtype=int)
        self.replacements = 0

    def step(self, E):
        """Advance one time step under environmental input E. Returns (energy, n_events)."""
        # Optional neighbor coupling (cyclic neighbors pull each other)
        if self.neighbors:
            nbr = (np.roll(self.states, 1) + np.roll(self.states, -1)) * 0.1
        else:
            nbr = 0.0

        # Transition probability, clipped at 1
        p_trans = np.minimum((E + nbr) / self.thresholds, 1.0)
        fires = self.rng.random(self.n) < p_trans

        total_energy = 0.0
        if self.refined:
            # Power-law fatigue damage on firing cells
            delta_d = np.zeros(self.n)
            delta_d[fires] = (E / self.thresholds[fires]) ** self.m * 0.01
            self.damage += delta_d

            # Phase-3 terminal: pulse energy grows as damage approaches D_fail
            pulse_gain = 1.0 + self.damage / self.D_fail
            total_energy += (self.thresholds[fires] * 0.5 * pulse_gain[fires]).sum()

            # Continuous hysteresis on non-firing cells, attenuated by stiffness loss
            stiffness = np.maximum(1.0 - self.damage / self.D_fail, 0.0)
            total_energy += E * 0.01 * stiffness[~fires].sum()
        else:
            # Base model from the voice-note sim
            self.damage[fires] += E * 0.01
            total_energy += (self.thresholds[fires] * 0.5).sum()
            total_energy += E * 0.01 * (~fires).sum()

        # Flip state (fold / unfold) on firing cells
        self.states[fires] = 1 - self.states[fires]
        self.events[fires] += 1

        # Material learning: thresholds drift upward with accumulated damage
        if self.learn:
            self.thresholds *= 1.0 + 0.001 * self.damage

        # Replacement policy: fully damaged cells get swapped for fresh stock
        if self.replace:
            dead = self.damage > self.D_fail
            n_dead = int(dead.sum())
            if n_dead:
                self.damage[dead] = 0.0
                self.thresholds[dead] = self.rng.uniform(
                    self.threshold_lo, self.threshold_hi, n_dead)
                self.states[dead] = 0
                self.replacements += n_dead

        return total_energy, int(fires.sum())

    def run(self, steps, env_kwargs=None):
        env_kwargs = env_kwargs or {}
        energy_out = np.zeros(steps)
        damage_mean = np.zeros(steps)
        events_per_step = np.zeros(steps, dtype=int)

        for t in range(steps):
            E = wave_energy(self.rng, **env_kwargs)
            energy, n_events = self.step(E)
            energy_out[t] = energy
            damage_mean[t] = self.damage.mean()
            events_per_step[t] = n_events

        return {
            "energy": energy_out,
            "damage": damage_mean,
            "events": events_per_step,
            "replacements": self.replacements,
            "final_damage": self.damage.copy(),
            "final_thresholds": self.thresholds.copy(),
        }


def _get_matplotlib(save_path):
    try:
        import matplotlib
        if save_path:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        print("matplotlib not installed. Install with: pip install matplotlib")
        return None


def plot_results(results, title_suffix="", save_path=None):
    plt = _get_matplotlib(save_path)
    if plt is None:
        return

    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)

    energy = results["energy"]
    axes[0].plot(energy, color="#8B4513", linewidth=0.6, alpha=0.7,
                 label="per-step output")
    window = max(1, len(energy) // 50)
    smoothed = np.convolve(energy, np.ones(window) / window, mode="same")
    axes[0].plot(smoothed, color="#1f77b4", linewidth=1.6,
                 label=f"{window}-step moving avg")
    axes[0].set_ylabel("Harvested energy (au)")
    axes[0].set_title(f"Energy output over time{title_suffix}")
    axes[0].legend(loc="upper left")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(results["damage"], color="#d62728", linewidth=1.0)
    axes[1].set_ylabel("Mean damage")
    axes[1].set_title("Fleet-average damage accumulation")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(results["events"], color="#2ca02c", linewidth=0.5)
    axes[2].set_ylabel("Events per step")
    axes[2].set_xlabel("Time step")
    axes[2].set_title(f"AE event rate  (cell replacements: {results['replacements']})")
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved plot to {save_path}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Microfracture energy harvesting simulation (degradation-coupled)")
    parser.add_argument("--units", type=int, default=100,
                        help="Number of unit cells (default: 100)")
    parser.add_argument("--steps", type=int, default=2000,
                        help="Number of time steps (default: 2000)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility")
    parser.add_argument("--refined", action="store_true",
                        help="Use power-law fatigue + phase-3 terminal pulse gain")
    parser.add_argument("--neighbors", action="store_true",
                        help="Enable cyclic neighbor coupling")
    parser.add_argument("--replace", action="store_true",
                        help="Replace fully-damaged cells in place")
    parser.add_argument("--learn", action="store_true",
                        help="Drift thresholds upward as damage accumulates")
    parser.add_argument("--fatigue-exp", type=float, default=2.5,
                        help="Fatigue exponent m for --refined (default: 2.5)")
    parser.add_argument("--burst-prob", type=float, default=0.05,
                        help="Pareto burst probability per step (default: 0.05)")
    parser.add_argument("--save", type=str, default=None,
                        help="Save plot to file instead of displaying")
    parser.add_argument("--no-plot", action="store_true", help="Skip plotting")
    args = parser.parse_args()

    array = HarvesterArray(
        n_units=args.units,
        seed=args.seed,
        refined=args.refined,
        neighbors=args.neighbors,
        replace=args.replace,
        learn=args.learn,
        fatigue_exp=args.fatigue_exp,
    )
    results = array.run(args.steps, env_kwargs={"burst_prob": args.burst_prob})

    modes = []
    if args.refined:   modes.append("refined")
    if args.neighbors: modes.append("neighbors")
    if args.replace:   modes.append("replace")
    if args.learn:     modes.append("learn")
    mode_str = ", ".join(modes) if modes else "base"

    print("=" * 60)
    print("Microfracture Harvesting Simulation")
    print("=" * 60)
    print(f"  Units:             {args.units}")
    print(f"  Steps:             {args.steps}")
    print(f"  Mode:              {mode_str}")
    print(f"  Total energy:      {results['energy'].sum():.2f}")
    print(f"  Mean per step:     {results['energy'].mean():.3f}")
    print(f"  Peak per step:     {results['energy'].max():.3f}")
    print(f"  Final mean damage: {results['damage'][-1]:.3f}")
    print(f"  Cell replacements: {results['replacements']}")
    print(f"  Total AE events:   {int(results['events'].sum())}")

    if not args.no_plot:
        plot_results(results, title_suffix=f"  ({mode_str})", save_path=args.save)


if __name__ == "__main__":
    main()
