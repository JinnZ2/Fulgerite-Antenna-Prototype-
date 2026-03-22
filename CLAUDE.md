# CLAUDE.md — Fulgurite Antenna Prototype

## Project Overview

Experimental RF/antenna design project exploring **fulgurite-inspired fractal geometries** as functional antennas for radio frequency reception and energy harvesting. The project translates natural lightning-discharge fractal patterns into antenna prototypes and tests them against RTL-SDR satellite signals.

## Repository Structure

```
/README.md              — Project overview, approach, roadmap, symbolic mapping
/LICENSE                — MIT License
/CLAUDE.md              — This file (AI assistant guidance)
/requirements.txt       — Python dependencies (numpy, matplotlib)
/sim/                   — Python simulation and analysis scripts
  fractal_generator.py  — Fractal antenna geometry generator
  layout_exporter.py    — Printable SVG template exporter
  sdr_analysis.py       — SDR/VNA data analysis and plotting
  resonance_calc.py     — Resonance frequency calculator
```

### Planned directories (not yet created)

```
/docs/             — Notes and symbolic mappings
/prototypes/       — Build photos and test logs
/data/             — SDR captures, VNA sweeps
```

A `SCOPE.md` file is referenced in the README but does not exist yet.

## Quick Start

```bash
pip install -r requirements.txt
cd sim/

# Generate a fractal antenna and view it
python fractal_generator.py --depth 5 --seed 42

# Export a printable wire-bending template
python layout_exporter.py --depth 5 --seed 42 --output template.svg

# Calculate resonance frequencies
python resonance_calc.py --depth 5 --report

# Design an antenna for a target frequency (e.g. NOAA at 137.1 MHz)
python resonance_calc.py --target-freq 137.1e6

# Analyze SDR spectrum data
python sdr_analysis.py spectrum capture.csv --show-peaks

# Compare fractal vs dipole antenna performance
python sdr_analysis.py compare baseline.csv fractal.csv --labels "Dipole,Fractal"
```

## Technology Stack

| Area | Tools / Languages |
|------|------------------|
| Simulation | Python 3 (numpy, matplotlib) |
| SDR Software | GNU Radio, SDR++ |
| Hardware | RTL-SDR dongle, NanoVNA |
| Materials | Copper wire, aluminum, conductive carbon, silver, glass/metal hybrids |

## Key Technical Parameters

- **Fractal geometry:** Lichtenberg/fractal tree patterns with 30-40 degree angle variance, branch scaling ratio r = 0.6-0.7
- **Resonance model:** `f0 = c / (2 * L_eff)` where `L_eff` = total unfolded branch length
- **Test frequencies:** 137 MHz (NOAA APT), 162 MHz (weather), 400-1600 MHz (broadband)
- **Baseline comparison:** standard dipole antenna

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
