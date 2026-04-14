# Refinements, Critiques, and Follow-Up Ideas

*Notes collected after the first draft. These are the higher-order fixes
that make the sim and the prototype correspond to real microfracture physics
instead of just the binary state-machine abstraction.*

## 1. The gap in the first sim

The base model uses `p_transition = min(E / threshold, 1)` and emits
`threshold * 0.5` of energy on each flip. That is a useful abstraction but
it skips the actual crack physics — specifically the difference between:

- **Subcritical crack growth** — slow, continuous AE, little energy release.
- **Catastrophic propagation** — fast, large AE spike, large energy release.

Real microfracture harvesting lives in the **subcritical** regime, because
catastrophic fracture would destroy the cell in a few cycles.

### What that means for the model

Replace the binary state flip with:

- **Damage accumulation per event**
  `Δd = k · (E / threshold)^m`   with `m > 1` for fatigue
- **AE energy per event**
  `E_ae = η_ae · E · damage_rate`
- **Harvested pulse energy** — not constant; **increases as the crack
  approaches critical length**. That gives the system a built-in early
  warning: energy output per event rises just before failure.

All three of these are wired into the `--refined` mode in
`sim/microfracture_harvest_sim.py`.

### Three-phase curve under constant-amplitude strain

A single cell under a repeated strain pulse should exhibit:

1. **Initiation** — few events, low energy
2. **Steady cracking** — constant event rate, moderate energy
3. **Terminal** — rate ↑, energy per event ↑↑ → replace cell

That three-phase curve **is the control law**. The system should replace
the cell partway through phase 3 — not earlier (wastes life), not later
(cascade risk).

### Flaw-size distribution

Replace uniform thresholds with a distribution of **initial flaw sizes**.
Larger flaws trigger earlier, smaller flaws later. That spreads degradation
across the array — exactly the "modular failure" rule from `01_framework.md`.

In the sim today this is a uniform draw between `0.5` and `2.0`. A Weibull
or log-normal distribution would be more physically realistic; swap it in
the `HarvesterArray.__init__` when there's bench data to calibrate against.

## 2. The real unknown, and where to advance the field

**Coupling efficiency `η_ae`** — from acoustic emission to electrical energy
**in a piezoelectric film bonded across a cracking layer**. Literature has
almost nothing on this specific geometry.

A single benchtop experiment (tensile test of a brittle coating on PVDF,
with an AE sensor and an electrical load) would give the first empirical
curve:

```
E_out_electrical  =  f(crack_length, crack_velocity, piezo_thickness)
```

That curve becomes the design equation for the whole architecture.

## 3. Adaptive thresholding via crack-precursor detection

A conventional buck-boost wakes up at a voltage threshold. But in a
heavy-tailed environment like Nazaré, waiting for voltage means you are
always **reacting** to past energy. Instead, use the high-frequency AE
signal itself as a trigger:

- Low-level AE (crack initiation) → keep the capacitor in high-impedance
  sense mode (nW power).
- AE event rate > 1 kHz → pre-charge the buck-boost input capacitor.
- AE amplitude exceeds `3x` moving average → fire the converter.

This gives **predictive wake-up**: the converter is already hot when the
mechanical energy arrives. Estimated capture improvement in bursty seas:
2–5x.

Implementation is trivial — a comparator bank on the piezo's high-pass
branch (100 kHz – 1 MHz). No DSP needed. The `hardware/esp32_ae_monitor.ino`
sketch already does the single-comparator version of this.

## 4. Neighbor handshake — wave-speed limited

Synchronizing neighbors is correct in principle but has a hard constraint:
the wave packet travels at ~10–20 m/s in the canyon. Over a 10 m array that
is 0.5–1 s of lag.

Consequences:

- **Spatial lag is fixed by geometry.** You cannot synchronize perfectly
  across the whole field.
- But you **can** synchronize clusters (cells within 1–2 m) using a shared
  timing reference — a common clock line, or a low-frequency pilot wave.

### The real trick — deliberate detuning

Upstream cells (first to hit the wave) are tuned to **higher** fracture
thresholds. Downstream cells are tuned **lower**. The wave decays as it
passes through the array, so downstream cells see lower strain — you
compensate by lowering their threshold.

Result: **uniform event rate across the field**, not a hotspot at the
leading edge.

In the sim, this shows up as a **gradient in `thresholds[i]` vs position**,
not just local state coupling. Currently the sim uses cyclic neighbors as a
placeholder; a positional threshold gradient is a ~5-line change in
`HarvesterArray.__init__`.

## 5. The "molt" analogy — and its engineering limit

This system molts. But biological molting has a **quiescent phase** where
the old structure is shed before the new one hardens. In a wave field you
cannot pause the forcing, so replacement must be **hot-swappable**:

- Each cell is mechanically decoupled (compliant edges).
- When `damage[i] > D_max`, the cell disconnects electrically and goes limp
  (zero stiffness).
- Neighbors expand their effective load area (mechanical reconfiguration)
  to cover the gap until replacement.

That requires a redundant bus and a mechanical clutch per cell — doable
with shape-memory alloy or electroadhesive layers. Prototype cost roughly
$500 per cell, not millions.

## 6. The single validating experiment

Build three identical unit cells (skin / brittle layer / piezo / backbone).
Instrument each with:

- continuous piezo output (low-pass < 10 kHz)
- high-pass AE channel (100 kHz – 1 MHz)
- local capacitor + comparator (the Sovereign rectifier)

Run them in a hydraulic press with random strain (program a heavy-tailed
distribution). Measure:

| Metric                                     | Success criterion                                      |
|--------------------------------------------|--------------------------------------------------------|
| Total harvested energy (J) over 1e5 cycles | > 50% of theoretical hysteresis + AE energy            |
| Event detection latency                    | < 1 ms from crack to converter firing                  |
| Cell-to-cell variation in damage rate      | < 20% (confirms tuning works)                          |
| Neighbor effect (mechanical coupling)      | No cascade failure when one cell dies                  |

If those numbers hold, there is a patentable topology and a path to a 1 m²
field prototype.

## 7. The institutional bias to name explicitly

Experts start hedging immediately because "a system that intentionally
cracks" does not fit legacy design bias. The bias is not technical — it is
**liability-driven**. Nobody wants to certify a system that fails on
purpose.

The way around it is not to argue — it is to change the use case:

- **Short-life deployments** — months, not years: oceanographic sensors,
  disposable energy harvesters for gliders, sacrificial anchors.
- **Non-critical infrastructure** where replacement is cheaper than
  prevention.

Start there. Certified-infrastructure adoption can come later if it ever
does.
