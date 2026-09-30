# CLAUDE.md — Fulgurite Antenna Prototype

## Project Overview

Experimental RF/antenna design project exploring **fulgurite-inspired fractal geometries** as functional antennas for radio frequency reception and energy harvesting. The project translates natural lightning-discharge fractal patterns into antenna prototypes and tests them against RTL-SDR satellite signals.

## Repository Structure

```
/README.md              — Project overview, approach, roadmap, key findings
/LICENSE                — MIT License
/CLAUDE.md              — This file (AI assistant guidance)
/requirements.txt       — Python dependencies (numpy, matplotlib, scipy)
/sim/                   — Python simulation and analysis scripts
  fractal_generator.py  — Lichtenberg / fractal tree geometry generator
  space_filling.py      — Koch and Hilbert curve generators
  antenna_physics.py    — RF physics core (loss, efficiency, Chu bound, noise)
  resonance_calc.py     — Bracketed resonance prediction
  link_budget.py        — Satellite link budget (NOAA APT and friends)
  layout_exporter.py    — Printable SVG template exporter
  sdr_analysis.py       — SDR/VNA data analysis and plotting
/docs/                  — Physics and measurement documentation
  physics_model.md      — Every equation, assumption and failure mode
  measurement_protocol.md — Bench procedure for valid A/B comparison
/degradation_harvesting/ — Separate sub-project: energy from material failure
  notes/                — Framework, architecture, refinements, build
  sim/                  — microfracture_harvest_sim.py
  hardware/             — SCAD, Arduino sketch, rectifier notes
/megacasting/           — Separate sub-project: dendrite growth simulation
  dendrite_sim.py
/legacy/                — Falsification log and frozen superseded models
  README.md             — The ledger: claims tested, refuted, and still unknown
  resonance_model_v1.py — v1 resonance model, FROZEN at the commit it failed
```

## The /legacy/ Convention

Superseded work is **preserved, not deleted**. A refuted model is the reason its
replacement exists; deleting it means the next builder rebuilds it from the same
intuition and hits the same wall.

When you refute something in this repo:

1. Freeze the artifact into `/legacy/` **exactly as it stood when it failed**.
2. Add a ledger entry to `legacy/README.md` using the template in its §5.
   Always fill in *Still unknown* — that field is where the next hypothesis
   comes from.
3. Record **how** it was refuted: analytic or experimental. These are not
   equivalent.
4. Edit the live claim in README.md and docs/ so old and new are both legible.

**Do not fix, refactor, or optimise anything in `/legacy/`** — known defects are
left in on purpose. A record that has been quietly corrected is no longer a
record. New defects found in frozen code get *documented* in the ledger, not
patched in place. The one permitted change is an import path when a file moves.

Frozen models must still run: each carries a mode reproducing its own
falsification (`python legacy/resonance_model_v1.py --falsification`).

**Epistemic status:** every result so far is analytic — no hardware has been
built. The current models are *unrefuted, not confirmed*. `legacy/README.md` §4
states in advance what would falsify them; do not weaken those criteria after
data arrives.

### Planned directories (not yet created)

```
/prototypes/       — Build photos and test logs
/data/             — SDR captures, VNA sweeps
```

A `SCOPE.md` file is referenced in the README but does not exist yet.

## Physics Ground Rules (read before changing any model)

These corrections are load-bearing. Do not regress them.

1. **Branches are electrically parallel, not in series.** Resonance is set by the
   **longest root-to-leaf path**, never by total wire length. The old
   `f0 = c/(2*L_eff)` with `L_eff` = total wire was wrong by ~2.5×.
2. **Loss scales with total wire; tuning scales with the longest path.** This
   asymmetry is why branching factor is a direct efficiency cost.
3. **Report brackets, not false precision.** `f_low` and `f_high` are hard
   physical bounds; `f_model` depends on empirical `ρ∞`/`n_sat` that are *not*
   derived from first principles and need calibration against measurement.
4. **The Chu–Harrington/McLean bound is inviolable.** `Q ≥ η(1/(ka)³ + 1/(ka))`
   depends on size and efficiency only. Folding wire inside a sphere never
   enlarges the sphere. Check any "small and broadband" claim against it.
5. **A better S11 is not a better antenna.** A resistive load matches perfectly
   and radiates nothing. Efficiency needs a Wheeler cap measurement.
6. **At 137 MHz there is no external-noise headroom.** Sky temp ≈ 269 K ≈ the
   conductor's own temperature, so inefficiency costs the full `10·log₁₀(η)`.
   The HF intuition that "loss is free because the sky is hot" does not transfer.
7. **A fulgurite is a dielectric** (fused silica), not a conductor. Phase 3
   casting is dielectric loading, and it shrinks the enclosing sphere — which
   tightens rule 4.

If a result seems to violate rules 4 or 6, suspect the measurement first; see
`docs/measurement_protocol.md` §1 (unchoked feedline is the usual culprit).

## Quick Start

```bash
pip install -r requirements.txt
cd sim/

# Validate the physics implementation against published values (35 assertions)
python antenna_physics.py --self-test

# Generate a fractal antenna and view it
python fractal_generator.py --depth 5 --seed 42

# Space-filling curves — the geometries that actually miniaturize
python space_filling.py compare              # geometry trade table
python space_filling.py koch --order 3
python space_filling.py hilbert --order 3 --size 200

# Export a printable wire-bending template
python layout_exporter.py --depth 5 --seed 42 --output template.svg

# Bracketed resonance prediction, with loss/bandwidth/noise analysis
python resonance_calc.py --depth 5 --report
python resonance_calc.py --depth 5 --seed 42 --compare-models --physics

# Design an antenna for a target frequency (e.g. NOAA at 137.1 MHz)
python resonance_calc.py --target-freq 137.1e6

# Conductor physics and the external-noise study
python antenna_physics.py --freq 137.1e6 --length 1000 --material copper
python antenna_physics.py --materials
python antenna_physics.py --noise-sweep

# Will a NOAA APT pass actually decode?
python link_budget.py --elevation 30 --efficiency 0.5
python link_budget.py --sweep-elevation

# Analyze SDR spectrum data
python sdr_analysis.py spectrum capture.csv --show-peaks

# Compare fractal vs dipole antenna performance
python sdr_analysis.py compare baseline.csv fractal.csv --labels "Dipole,Fractal"
```


<!-- clone-refspec-note v1 -->
## Cloning and pushing
Shallow clones are single-branch by default.
Before pushing any branch other than main, run:

    git config remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'
    git fetch --depth 1

Or clone with: git clone --depth 1 --no-single-branch <url>
Without this, the first push of a new branch
fails the tracking-ref check even when the
commit landed.
<!-- /clone-refspec-note v1 -->

## Technology Stack

| Area | Tools / Languages |
|------|------------------|
| Simulation | Python 3 (numpy, matplotlib) |
| SDR Software | GNU Radio, SDR++ |
| Hardware | RTL-SDR dongle, NanoVNA |
| Materials | Copper wire, aluminum, conductive carbon, silver, glass/metal hybrids |

## Key Technical Parameters

- **Fractal geometry:** Lichtenberg/fractal tree patterns with 30-40 degree angle variance, branch scaling ratio r = 0.6-0.7
- **Resonance model:** bracketed quarter-wave monopole over the longest current
  path, with an end-effect factor `k` from the induced-EMF solution and a
  saturating fold-compression `ρ`. See `docs/physics_model.md` §1.
- **Test frequencies:** 137 MHz (NOAA APT), 162 MHz (weather), 400-1600 MHz (broadband)
- **Baseline comparison:** standard dipole antenna
- **Validity:** thin-wire assumption throughout (length/diameter ≳ 50); 2-D
  geometry; no mutual coupling between branches; no ground-plane model. For
  anything beyond design intuition, export to NEC-2 / PyNEC.

## Development Workflow

### Setup

```bash
pip install -r requirements.txt
```

Dependencies: `numpy>=1.21`, `matplotlib>=3.5`. No build system or CI/CD.

### Simulation scripts

All scripts live in `/sim/` and import from `fractal_generator.py` as the core module:

- **fractal_generator.py** — Core module. Generates `FractalAntenna` objects with configurable depth, scale ratio, angle variance, and branching factor. Can export to CSV and plot with matplotlib.
- **layout_exporter.py** — Converts fractal geometries to SVG templates for printing at 1:1 scale. Supports A4/Letter page sizes, grid overlay, and scale bars.
- **sdr_analysis.py** — Loads RTL-SDR IQ binary captures, CSV spectrum exports, and NanoVNA S-parameter data. Supports spectrum plotting, multi-antenna comparison, and peak detection.
- **resonance_calc.py** — Predicts resonance frequencies from fractal geometry using `f0 = c / (2 * L_eff)`. Can reverse-calculate trunk length needed for a target frequency.

### Conventions

- Documentation uses Markdown with structured headings
- Symbolic notation: lightning (fractal shape), spiral (resonance), gear (material tests), satellite dish (signal)
- MIT licensed — open for forking and remixing
- Scripts use argparse with `--help` for all options
- Physical units: mm for lengths, Hz for frequencies, dB for power

## For AI Assistants

- When generating Python simulation code, target the `/sim/` directory
- Import `fractal_generator.generate_fractal()` to create antenna geometries
- When adding documentation or notes, use `/docs/`
- Experimental data belongs in `/data/`
- Prototype build logs and photos go in `/prototypes/`
- Follow the existing README style: structured Markdown with clear section headings
- The project mixes physics/RF engineering with software — understand the domain context before making changes
- All scripts should support `--help`, `--save` (for plots), and headless operation (no GUI required)
