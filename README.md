# Fulgurite Antenna Prototype

## Overview
This project explores **fulgurite-inspired antenna geometries** for radio frequency (RF) reception and energy harvesting.  
Fulgurites are naturally occurring glass-like fractals formed when lightning strikes sand or soil. Their branching, self-similar channels offer unique **fractal discharge geometries** that may provide **broadband resonance** and **nonlinear coupling advantages** for antenna design.

Our goal is to:
- Translate fulgurite discharge fractals into **functional antenna prototypes**.
- Test reception and spectral response against **RTL-SDR satellite signals** and other RF sources.
- Compare performance across different materials (copper wire, conductive composites, possible sintered glass/metal hybrids).

---

## Prototype Approach

1. **Geometry Extraction**
   - Base structure: Lichtenberg / fractal tree patterns.
   - Iterative branching defined by:
     - Angle distribution: ~30–40° random variance.
     - Branch length scaling: `L(n+1) = L(n) * r` where `r ≈ 0.6–0.7`.
     - Self-similar recursion until branch < cutoff length.

2. **Materials**
   - Phase 1: Copper wire bent into fractal geometry.
   - Phase 2: Alternative conductors (aluminum, conductive carbon, silver plating).
   - Phase 3: Hybrid fulgurite molds (sand/glass fused with metal inserts).

3. **Testing Setup**
   - SDR: RTL-SDR dongle with GNU Radio / SDR++.
   - Frequency range: 137 MHz (NOAA APT), 162 MHz (weather), 400–1600 MHz (broadband test).
   - Compare against baseline dipole antenna.

4. **Simulation & Equations**
   - Resonance is reported as a **bracket**, not a single number:
     - `f_high = c / (4 * L_extent * k)` — no folding gain (hard upper bound)
     - `f_low  = c / (4 * L_path * k)` — perfect folding (hard lower bound)
     - `f_model` — a saturating interpolation between them
   - `L_path` is the **longest root-to-leaf current path**, not the total wire.
   - Multi-band behavior emerges from the branch-length distribution.

> **Model correction.** Earlier versions of this README used
> `f0 = c / (2 * L_eff)` with `L_eff` as *total unfolded branch length*. That is
> wrong for a branching structure: branches hang in **parallel** off their
> parent, so current traverses only ~6 of a depth-5 tree's 63 branches. The old
> model was off by ~2.5× and predicted a resonance outside the physical bounds.
> Full derivation in [docs/physics_model.md](./docs/physics_model.md).

---

## Key Finding: the tree is the wrong fractal for miniaturization

Two ratios decide whether a geometry is a good trade — what you **gain**
(`longest path / extent`) versus what you **pay** (`total wire / extent`):

| geometry | path/extent (gain) | wire/extent (cost) |
|---|---|---|
| Lichtenberg tree | **1.01 – 1.16** | **2.2 – 19.5** |
| Koch order *n* | (4/3)ⁿ → 1.33, 1.78, 2.37, 3.16 | identical to gain |
| Hilbert order *n* | ≈2ⁿ → 3, 5, 9, 17, 33 | identical to gain |

A tree branches *outward*, so its longest path is barely longer than a straight
line to the same tip — the extra wire goes sideways into parallel branches that
dissipate power without extending the resonant path. It spends up to **19× its
extent in wire to gain 5–16%** in electrical length. Space-filling curves fold
the wire *back* on itself, so every millimetre spent is electrical length gained.

This does **not** retire the tree. It remains the honest model of a fulgurite
discharge and a plausible route to multiband behavior. It is simply not a
miniaturization strategy, and this repo no longer claims otherwise. Reproduce
the table with `python sim/space_filling.py compare`.

---

## Key Finding: at 137 MHz, inefficiency costs full price

Reception depends on SNR against total system noise, not efficiency alone. Ohmic
loss attenuates the signal *and* injects thermal noise — but it also attenuates
sky noise. Where the sky is hot, loss is nearly free:

| frequency | sky temp | η = 0.1 penalty | η = 0.01 penalty |
|---|---|---|---|
| 10 MHz | 230 065 K | −0.19 dB | −1.75 dB |
| 30 MHz | 18 119 K | −1.90 dB | −8.46 dB |
| **137.1 MHz** | **269 K** | **−10.07 dB** | **−20.08 dB** |

*(naive `10·log₁₀(η)` guess: −10, −20 dB)*

At HF a 1%-efficient antenna costs under 2 dB. At the NOAA band the sky has
cooled to roughly the conductor's own physical temperature and the penalty
converges on the naive value. **There is no external-noise headroom at 137 MHz**,
so a fractal trading efficiency for size pays in full. Reproduce with
`python sim/antenna_physics.py --noise-sweep`.

---

## The bound nothing beats

For any antenna in a sphere of radius *a* (McLean 1996):

```
Q_min = η · ( 1/(ka)³ + 1/(ka) )      FBW = (S−1)/(Q√S)
```

| ka | Q_min | max bandwidth @ VSWR 2 |
|---|---|---|
| 0.1 | 1010 | 0.07 % |
| 0.5 | 10.0 | 7.07 % |
| 1.0 | 2.0 | 35.4 % |

This depends on **size and efficiency only** — not topology. Fractal folding
buys a longer conductor inside the same sphere; it does not enlarge the sphere.
Any "small *and* broadband" claim must clear this bound first.

---

## Roadmap

- [x] Generate fractal wireframe models in Python.
- [x] Print layout templates for bending copper wire.
- [x] Quantitative physics: loss, efficiency, Chu bound, external noise.
- [x] Space-filling curve generators (Koch, Hilbert) for real miniaturization.
- [ ] Build first **desktop prototype** for SDR testing.
- [ ] Measure resonance spectrum using NanoVNA + SDR comparison.
- [ ] **Calibrate `ρ∞` / `n_sat`** against measured resonances at depths 3/4/5.
- [ ] **Measure efficiency with a Wheeler cap** — the number the model most needs.
- [ ] Cross-check geometries against a real solver (NEC-2 / PyNEC).
- [ ] Explore fulgurite molds and composite casting.
- [ ] Document findings with images and spectral plots.

---

## Documentation

| Document | Contents |
|---|---|
| [docs/physics_model.md](./docs/physics_model.md) | Every equation, its assumptions, and where it breaks. References. |
| [docs/measurement_protocol.md](./docs/measurement_protocol.md) | How to make the fractal-vs-dipole comparison actually mean something. |

---

## Symbolic Mapping

- **Fractal Shape (⚡)** → natural discharge pattern.  
- **Resonance Spiral (↻)** → energy capture & feedback.  
- **Material Test Nodes (⚙)** → each conductor trial.  
- **Signal Glyph (📡)** → received spectrum signatures.  

---

## Repo Structure

/README.md        → This document
/docs/            → Physics model, measurement protocol, notes
/sim/             → Python scripts for geometry, physics and analysis
/prototypes/      → Build photos & test logs
/data/            → SDR captures, VNA sweeps

### /sim/

| Script | Role |
|---|---|
| `fractal_generator.py` | Lichtenberg / fractal tree geometry (fulgurite morphology) |
| `space_filling.py` | Koch and Hilbert curves — the geometries that actually miniaturize |
| `antenna_physics.py` | Loss, efficiency, Chu bound, dielectric loading, noise. `--self-test` validates 35 assertions against published values |
| `resonance_calc.py` | Bracketed resonance prediction, `--physics` for the full picture |
| `link_budget.py` | Will a NOAA APT pass actually decode? |
| `layout_exporter.py` | 1:1 printable wire-bending templates |
| `sdr_analysis.py` | RTL-SDR captures, NanoVNA sweeps, A/B comparison |

```bash
cd sim/
python antenna_physics.py --self-test        # validate the physics
python space_filling.py compare              # geometry trade table
python resonance_calc.py --depth 5 --seed 42 --compare-models --physics
python link_budget.py --sweep-elevation
```

---

## License
Open-source under MIT License.  
Feel free to fork, remix, and expand the exploration of **lightning-born geometries for RF intelligence**.


[📖 See Scope & Scaling Philosophy](./SCOPE.md)
