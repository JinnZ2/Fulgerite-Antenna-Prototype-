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
   - Fractal resonance approximated by:
     - `f0 = c / (2 * L_eff)` where `L_eff` is total unfolded branch length.
   - Multi-band behavior emerges from branch-length distribution.

---

## Roadmap

- [ ] Generate fractal wireframe models in Python (matplotlib / turtle / fractal lib).
- [ ] Print layout templates for bending copper wire.
- [ ] Build first **desktop prototype** for SDR testing.
- [ ] Measure resonance spectrum using NanoVNA + SDR comparison.
- [ ] Explore fulgurite molds and composite casting.
- [ ] Document findings with images and spectral plots.

---

## Symbolic Mapping

- **Fractal Shape (⚡)** → natural discharge pattern.  
- **Resonance Spiral (↻)** → energy capture & feedback.  
- **Material Test Nodes (⚙)** → each conductor trial.  
- **Signal Glyph (📡)** → received spectrum signatures.  

---

## Repo Structure
