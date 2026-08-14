# Legacy — The Falsification Log

**Nothing in this folder is deprecated in the sense of "worthless." It is
superseded, which is different. Precedence carries.**

A model that was refuted is the reason the current model exists. Delete it and
the next person rebuilds it from the same intuition, hits the same wall, and
loses the same weeks. Keep it and they inherit the wall for free.

This folder holds work that has been tested and found wrong, preserved exactly
as it stood at the moment it was refuted, together with the reasoning that
refuted it.

---

## The method this repo follows

```
hypothesize  →  run  →  result  →  falsified?  →  edit the claim
                 ↑                                      ↓
                 └────  rerun  ←  search for unknowns  ←─┘
```

The step people skip is **"edit the claim."** A hypothesis that survives by
being quietly reworded was never tested. When something here is refuted, the
old claim stays legible in this folder and the new claim goes in the live docs,
so the difference between them is visible.

The step people skip *second* is **"search for unknowns."** A refutation tells
you the old answer was wrong, not that the new one is right. Every entry below
therefore ends with what is still unknown, and §4 lists what would falsify the
*current* model.

---

## Rules for this folder

1. **Frozen files are not maintained.** Do not fix bugs, refactor, or optimise
   anything in here. A record that has been quietly corrected is no longer a
   record. `resonance_model_v1.py` keeps its O(n²) scan and its half-wave
   assumption on purpose.
2. **Frozen files must still run.** A refutation you cannot reproduce is a
   rumour. Each preserved model carries a mode that reproduces its own
   falsification.
3. **Only the import path may change**, and only when a file is moved. Never
   the arithmetic.
4. **New defects found in frozen code get documented here, not patched there.**
5. **Every entry records how it was refuted** — analytically or experimentally.
   These are not equivalent (see §3).

---

## 1. The ledger

### H1 — Resonance tracks total unfolded wire length

> *"Fractal resonance approximated by: `f0 = c / (2 * L_eff)` where `L_eff` is
> total unfolded branch length."*
> — README.md at commit `9e126ea`, and `sim/resonance_calc.py` v1

| | |
|---|---|
| **Status** | **FALSIFIED** — analytically, 10/10 test cases |
| **Refuted** | 2026-08, commit `c3e8ebf` |
| **Frozen at** | [`resonance_model_v1.py`](./resonance_model_v1.py) |
| **Reproduce** | `python legacy/resonance_model_v1.py --falsification` |
| **Replaced by** | `sim/resonance_calc.py` — bracketed model |

**The test.** No bench required. The hypothesis was checked against two lengths
it had conflated: the wire you *spend*, and the path a current can actually
*travel*. The longest root-to-leaf path sets a hard lower bound on resonant
frequency — nothing resonates below the frequency set by the longest conductor
path it contains.

| depth | v1 predicts | hard bound `f_low` | outside by |
|---|---|---|---|
| 3 | 242.3 MHz | 332.7 MHz | 1.37× |
| 4 | 165.8 MHz | 309.0 MHz | 1.86× |
| 5 | 117.5 MHz | 295.4 MHz | 2.51× |
| 6 | 85.3 MHz | 287.1 MHz | 3.37× |
| 7 | 62.8 MHz | 282.0 MHz | 4.49× |

**Mechanism.** Branches hang in **parallel** off their parent, not in series. A
depth-5 tree has 63 branches; a current crosses **6** of them. Summing all 63
counts conductor the current never traverses.

**The error scaling is the evidence.** It grows 1.37× → 4.49× with depth. That
is not generic wrongness — it is the specific signature of the parallel/series
confusion, because branch count grows exponentially with depth while path length
grows linearly. A different defect would have left a different fingerprint. This
is what upgraded the result from "the number looks off" to a diagnosed cause.

**Still unknown:** the replacement predicts a *bracket* 295–310 MHz, not a
number. Where inside that bracket a real antenna lands has never been measured.

---

### H2 — Fractal branching miniaturises the antenna

> *"Their branching, self-similar channels offer unique fractal discharge
> geometries that may provide broadband resonance and nonlinear coupling
> advantages."*
> — README.md, retained; the miniaturisation reading of it is what failed

| | |
|---|---|
| **Status** | **FALSIFIED for the branching tree. Survives, narrowed, for space-filling curves.** |
| **Reproduce** | `python sim/space_filling.py compare` |
| **Replaced by** | `sim/space_filling.py` — Koch and Hilbert generators |

**The test.** 27 configurations (depth 3–7 × scale 0.5–0.8 × angle 20–60°),
measuring what you gain against what you pay:

| geometry | path/extent (gain) | wire/extent (cost) |
|---|---|---|
| Lichtenberg tree | **1.01 – 1.16** | **2.2 – 19.5** |
| Koch order *n* | (4/3)ⁿ | identical to gain |
| Hilbert order *n* | ≈2ⁿ | identical to gain |

Up to **19× the ohmic loss for 16% of the size reduction**. A tree branches
*outward*, so its longest path barely exceeds a straight line to the same tip.

**This is a narrowing, not a discard.** "Fractals miniaturise" is true of
space-filling curves and false of branching trees. The original hypothesis was
too broad rather than simply wrong, and the useful output was finding *which*
fractals it applies to. The tree is still in the repo and still correct as
fulgurite morphology — it is just not a miniaturisation strategy.

**Still unknown:** whether the tree's spread of path lengths delivers usable
**multiband** behaviour. That was always the more interesting half of the
original claim and **it has never been tested.** See §2.

---

### H3 — Fractal geometry gives broadband resonance

| | |
|---|---|
| **Status** | **CONSTRAINED, not falsified** |
| **Bound** | Chu–Harrington/McLean: `Q ≥ η(1/(ka)³ + 1/(ka))` |

Not refuted, but now boxed in by a limit that depends on **size and efficiency
only, not topology**. Folding wire inside a sphere never enlarges the sphere.

Two distinctions the original claim blurred, worth keeping separate:

- **Multiband ≠ broadband.** Several narrow resonances is not one wide one. The
  Chu bound constrains the second; the first is still open.
- **The bound is only tight for ka < 1.** Above that it stays true but goes
  slack. A quarter-wave monopole sits at ka ≈ 1.57 at its own resonance, where
  the bound says nothing useful. Quoting it there is a misuse.

---

### H4 — Antenna loss is cheap because external noise dominates

Never written in this repo, but it is standard HF intuition and it silently
underwrote the idea that an inefficient fractal would be fine.

| | |
|---|---|
| **Status** | **FALSIFIED at 137 MHz. True at HF.** |
| **Reproduce** | `python sim/antenna_physics.py --noise-sweep` |

| frequency | sky temp | η = 0.01 penalty |
|---|---|---|
| 10 MHz | 230 065 K | −1.75 dB |
| 30 MHz | 18 119 K | −8.46 dB |
| **137.1 MHz** | **269 K** | **−20.08 dB** *(naive: −20)* |

At HF the sky is thousands of kelvin and loss attenuates sky noise alongside the
signal, so a 1%-efficient antenna costs under 2 dB. At 137 MHz the sky has
cooled to ≈269 K — about the conductor's own physical temperature — and the
penalty converges on the full `10·log₁₀(η)`.

**The transfer of intuition across frequency was the error**, not the physics at
either end. Worth flagging generally: most RF folklore carries an unstated band.

---

## 2. Search for unknowns

Ranked by how much they block. These are the reruns waiting to happen.

| # | Unknown | Blocks | Cost to resolve |
|---|---|---|---|
| 1 | **No hardware exists.** Every result is model-vs-model. | Everything | Build one |
| 2 | **Mutual coupling between branches is unmodelled.** This is exactly the physics that `ρ` hand-waves into an empirical constant. | The whole compression model | NEC-2 / PyNEC |
| 3 | **`ρ∞`, `n_sat` uncalibrated** — literature ballpark, not derived | `f_model` precision | Build depths 3/4/5, sweep each |
| 4 | **Efficiency never measured** | Every SNR claim | Wheeler cap |
| 5 | **H2's multiband half untested** | The tree's actual value | VNA sweep, wide span |
| 6 | **Geometry is 2-D**; real builds are not | Enclosing sphere, cancellation | 3-D solver |
| 7 | **No ground plane / counterpoise model** | Feedpoint impedance, pattern | NEC with ground |
| 8 | **Real fulgurite ε_r / tan δ unmeasured** — silica figures assume no inclusions or bubbles | Phase 3 casting | Measure a specimen |

Items 1 and 2 are the ones that matter. Everything else is refinement.

---

## 3. Epistemic status — read this before citing anything

**H1 and H2 were refuted analytically, not experimentally.** No antenna has been
built, no sweep taken, no photon received.

This distinction is not pedantry:

- An **analytic** refutation is cheap, fast, and decisive *within its
  assumptions*. H1 was contradicted by the geometry it was itself computed
  from — internal inconsistency, which is the strongest kind of cheap
  refutation. It cannot be explained away by a bad measurement.
- It also **cannot confirm the replacement.** Showing v1 violates a bound proves
  v1 wrong. It does not prove the bracketed model right.

> **The current model is unrefuted, not confirmed.** It has never met a
> measurement.

The first real sweep can falsify the replacement just as thoroughly. That would
be a good outcome, and §4 says in advance what it would look like — written down
now, before the data exists, so it cannot be quietly adjusted afterwards.

---

## 4. What would falsify the *current* model

Stated in advance. If any of these is observed, the live claim is wrong and this
folder gets a new entry.

| Current claim | Falsified by |
|---|---|
| Resonance lies in `[f_low, f_high]` | Any measured fundamental outside the bracket. **Below `f_low` is the serious one** — that breaks the longest-path bound and means the topology model is still wrong |
| Compression saturates with iteration depth | `ρ_implied` climbing steadily across depths 3/4/5 instead of levelling off. Then the saturating form is wrong and needs replacing, not refitting |
| Loss scales with total wire, tuning with longest path | Measured efficiency roughly independent of branching factor at fixed path length |
| Tree gives ≤1.16× miniaturisation | A tree measuring below `f_low` — same observation as row 1, and it would refute H2's narrowing too |
| No external-noise headroom at 137 MHz | A lossy antenna matching an efficient one on SNR, with feedline choked and efficiency independently confirmed |
| Chu bound holds | Measured bandwidth above the bound at ka < 1, with efficiency measured not assumed. Would be a genuinely extraordinary result — check the choke first |

Before accepting any of these, work `docs/measurement_protocol.md` §10. Every
error source on that checklist is larger than the effects listed here.

---

## 5. Template for the next entry

```markdown
### H<n> — <the claim, in the words it was originally made>

> *"<verbatim quote>"* — <file> at commit <sha>

| | |
|---|---|
| **Status** | FALSIFIED / CONSTRAINED / NARROWED / OPEN |
| **Refuted** | <date>, commit <sha> |
| **How** | analytic / experimental  ← say which |
| **Frozen at** | legacy/<file> |
| **Reproduce** | <exact command> |
| **Replaced by** | <file> |

**The test.** <what was run, what was measured, n = ?>

**Mechanism.** <why it failed -- a diagnosed cause, not just a discrepancy>

**Still unknown.** <what the refutation did NOT settle>
```

Fill in **Still unknown** even when it feels empty. That field is where the next
hypothesis comes from.
