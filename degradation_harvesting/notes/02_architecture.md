# Unit Cell Architecture and Closed-Loop Model

*Focus on one mode and close the loop end-to-end. Use microfracture +
acoustic/electrical capture as the base case.*

## 1. Unit cell definition (one element)

**Geometry**: thin, compliant strip or tile anchored to a flexible spine.

**Layer stack** (outer → inner):

1. **Compliant skin** — polymer / elastomer tuned to wave-induced strain;
   sets the broadband strain field.
2. **Fracture-enabled layer** — brittle composite with engineered flaw
   density (micro-notches, inclusions). Cracks nucleate at predictable
   strain thresholds.
3. **Transduction layer** — piezoelectric film (or fiber weave) bonded
   across the fracture layer; converts strain spikes and acoustic emission
   into charge.
4. **Backbone + bus** — carries minimal mechanical load; routes charge and
   data.

## 2. Event physics (single cycle)

```
wave packet → distributed strain ε(t)
local hotspot → crack initiation
ε(t) ↔ σ(t) with phase lag → piezo output (continuous)
crack growth Δa → acoustic emission (kHz–MHz) + rapid local strain release
                → high-frequency piezo spike
```

You end up with **low-frequency continuous power plus sparse high-energy
pulses**.

## 3. Minimal quantitative model

Let:

- `E_env(t)` = local strain energy density input
- `η_h` = hysteresis capture efficiency
- `η_ae` = acoustic-emission capture efficiency
- `D(t)` = damage state, 0 → 1

Then per element:

```
P_out(t)  ≈  η_h · P_strain(t)  +  η_ae · Σ δ(t - t_i) · E_crack,i

dD/dt  =  f(ε_max, cycle count, spectrum)

failure when D → 1
```

Design objective:

```
maximize ∫ P_out dt
subject to D(t) < D_crit over the service window
```

## 4. Tuning the "weakness"

You don't eliminate cracks — you set their **statistics**:

- **flaw size distribution** → sets crack thresholds
- **layer thickness** → sets energy per event
- **interface toughness** → localizes cracks, prevents runaways

Practical knobs:

- inclusion spacing (controls event frequency)
- brittle / ductile ratio (controls pulse vs continuous output balance)
- pre-strain (biases activation under smaller waves)

## 5. Bounding failure — no cascades

Rules:

- **Segmentation** — microcells electrically in parallel, mechanically
  semi-decoupled.
- **Crack arrest features** — soft interlayers or patterned stop-lines.
- **Load shedding** — when a cell softens (damage ↑), neighboring cells
  take more load.

Net effect:

> many small failures → stable global behavior

## 6. Sensing is intrinsic

Each crack event is also a **measurement**:

- count rate → local energy flux
- amplitude spectrum → strain intensity distribution
- temporal clustering → storm / packet structure

So from the same signals you get:

> power output + structural health + environmental state

## 7. Power conditioning (field level)

Because output is spiky:

- local rectification + small capacitors per cell
- medium buffer per cluster (supercap / pressure accumulator)
- slow export (electrical or other form)

This implements:

> impulsive input → smoothed export

## 8. Deployment pattern

- Place elements in energy pathways (where the canyon focuses waves).
- Keep porous coverage (no flow blockage).
- Vary material tuning across the field to cover a wider spectrum.

## 9. What to prototype first

Single tile test:

- cyclic random strain (broadband, heavy-tailed peaks)
- measure:
  - continuous piezo power vs spectrum
  - AE pulse energy distribution
  - damage rate vs peak strain

**Target curves**:

```
P_out    vs   spectrum overlap
D(t)     vs   peak statistics (NOT averages)
```

**Success criteria**:

- high integrated energy over time
- bounded, predictable degradation
- stable output after smoothing

## 10. State-machine abstraction (for the sim)

```
environment → random + burst energy input
unit state  → {0, 1}            (unfolded / folded)
transition  → probability based on energy threshold
energy out  → when state changes + hysteresis
damage      → increases with large energy events
```

This is the model implemented in
`sim/microfracture_harvest_sim.py`. See `notes/03_refinements.md` for the
refined physics (power-law fatigue, phase-3 terminal pulse gain) that sits
behind the `--refined` flag.
