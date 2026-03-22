# CLAUDE.md — Fulgurite Antenna Prototype

## Project Overview

Experimental RF/antenna design project exploring **fulgurite-inspired fractal geometries** as functional antennas for radio frequency reception and energy harvesting. The project translates natural lightning-discharge fractal patterns into antenna prototypes and tests them against RTL-SDR satellite signals.

**Stage:** Early planning/pre-implementation. No source code exists yet — only documentation.

## Repository Structure

```
/README.md        — Project overview, approach, roadmap, symbolic mapping
/LICENSE           — MIT License
/CLAUDE.md         — This file (AI assistant guidance)
```

### Planned directories (not yet created)

```
/docs/             — Notes and symbolic mappings
/sim/              — Python scripts for fractal generation
/prototypes/       — Build photos and test logs
/data/             — SDR captures, VNA sweeps
```

A `SCOPE.md` file is referenced in the README but does not exist yet.

## Technology Stack

| Area | Tools / Languages |
|------|------------------|
| Simulation | Python (matplotlib, turtle, fractal libs) |
| SDR Software | GNU Radio, SDR++ |
| Hardware | RTL-SDR dongle, NanoVNA |
| Materials | Copper wire, aluminum, conductive carbon, silver, glass/metal hybrids |

## Key Technical Parameters

- **Fractal geometry:** Lichtenberg/fractal tree patterns with 30–40° angle variance, branch scaling ratio r ≈ 0.6–0.7
- **Resonance model:** `f0 = c / (2 * L_eff)` where `L_eff` = total unfolded branch length
- **Test frequencies:** 137 MHz (NOAA APT), 162 MHz (weather), 400–1600 MHz (broadband)
- **Baseline comparison:** standard dipole antenna

## Development Workflow

### Current state

No build system, CI/CD, tests, or dependency files exist. The project is documentation-only at this stage.

### When code is added

The planned workflow involves:
1. Python fractal generation scripts in `/sim/`
2. Physical prototype construction from generated templates
3. RF measurement and data collection into `/data/`
4. Documentation of results in `/docs/` and `/prototypes/`

### Conventions

- Documentation uses Markdown with structured headings
- Symbolic notation: ⚡ (fractal shape), ↻ (resonance), ⚙ (material tests), 📡 (signal)
- MIT licensed — open for forking and remixing

## For AI Assistants

- **No code to build or test** — this is currently a documentation/planning repository
- When generating Python simulation code, target the `/sim/` directory
- When adding documentation or notes, use `/docs/`
- Experimental data belongs in `/data/`
- Prototype build logs and photos go in `/prototypes/`
- Follow the existing README style: structured Markdown with clear section headings
- Preserve the symbolic mapping convention (⚡, ↻, ⚙, 📡) in documentation
- The project mixes physics/RF engineering with software — understand the domain context before making changes
