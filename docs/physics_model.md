# Physics Model — Equations, Assumptions, and Where They Break

This document states exactly what the simulation code computes, what it assumes,
and how far each result can be trusted. Every equation here is implemented in
`sim/antenna_physics.py` and checked against published values by
`python antenna_physics.py --self-test` (35 assertions).

The short version: the original project model was `f0 = c / (2 · L_eff)` with
`L_eff` taken as total unfolded branch length. That model is wrong for a
branching structure, by roughly a factor of 2.5 for the default geometry, and it
says nothing about whether the antenna can receive. What follows replaces it.

That model is preserved, runnable, at
[`legacy/resonance_model_v1.py`](../legacy/resonance_model_v1.py), frozen at the
commit where it failed. The full ledger of tested-and-abandoned claims is
[`legacy/README.md`](../legacy/README.md).

> **Epistemic status.** Everything below is analytic. No antenna has been built
> and no sweep taken, so these models are **unrefuted, not confirmed**. The
> refutation of the old model was by internal inconsistency with physical
> bounds — decisive against it, but no evidence for the replacement.
> `legacy/README.md` §4 states what would falsify what is written here.

---

## 1. The correction that matters most

### 1.1 Branches are parallel, not in series

A fractal tree of depth 5 has 63 branches, but current leaving the feed only
ever traverses **6** of them before reaching a tip. At every node the current
*divides*; it does not flow through each branch in turn. Summing all 63 branch
lengths and calling the result an effective conductor length overstates the
electrical length by about an order of magnitude.

The electrical length is bounded by the **longest root-to-leaf path**, not the
total wire.

### 1.2 Folding does not convert length into electrical length for free

Even along a single path, bending a wire into a compact volume does not turn all
of its length into phase delay. Closely spaced antiparallel segments radiate out
of phase and cancel in the far field; that energy is stored reactively instead of
radiated. This is why measured miniaturisation from fractal iteration
**saturates** after a few iterations rather than tracking perimeter — a result
reported consistently across Koch and Minkowski geometries.

### 1.3 So the code reports a bracket, not a number

```
f_high  = c / (4 · L_extent · k)      no folding gain      (hard upper bound)
f_low   = c / (4 · L_path   · k)      perfect folding      (hard lower bound)
f_model = f_high / ρ(n)                saturating estimate
```

`ρ(n) = 1 + (ρ∞ − 1)(1 − e^{−n/n_sat})`, capped at `L_path / L_extent`, because
folding can never buy more compression than the wire physically provides.

`f_low` and `f_high` are physical bounds and are trustworthy. **`f_model` rests
on two empirical parameters (`ρ∞`, `n_sat`) that are not derived from first
principles.** Defaults (1.40, 2.0) are ballpark figures consistent with published
Koch results. Calibrate them against your own NanoVNA sweeps before trusting
`f_model` to within better than the bracket width.

Quarter-wave, not half-wave: the structure is fed at the trunk base against a
counterpoise, which makes it a monopole.

---

## 2. Measured consequence: the tree is the wrong fractal for miniaturisation

Two ratios decide whether a geometry is a good trade:

| ratio | meaning |
|---|---|
| `longest path / extent` | the miniaturisation you **gain** |
| `total wire / extent` | the ohmic loss you **pay** |

Surveyed across depth 3–7, scale 0.5–0.8, angle 20–60° (`space_filling.py compare`):

| geometry | path/extent | wire/extent |
|---|---|---|
| Lichtenberg tree | **1.01 – 1.16** | **2.2 – 19.5** |
| Koch order *n* | (4/3)ⁿ → 1.33, 1.78, 2.37, 3.16 | same as path |
| Hilbert order *n* | ≈2ⁿ → 3, 5, 9, 17, 33 | same as path |

A tree branches *outward*, so its longest path is barely longer than a straight
line to the same tip. It spends up to 19× its extent in wire to gain 5–16% in
electrical length. For a space-filling curve the two columns are identical —
every millimetre of wire sits on the current path.

**This does not mean the tree is useless.** It is the correct model for
fulgurite morphology, and its spread of path lengths is a plausible route to
multiband behaviour. It is simply not a miniaturisation strategy, and the repo
should stop implying that it is.

---

## 3. Conductor loss

### 3.1 Skin depth

```
δ = sqrt( ρ / (π · f · μ) ),      μ = μ₀ · μ_r
```

Copper at 137.1 MHz: **5.64 µm**. Anything thicker than ~30 µm of copper is
electrically solid, so plating a cheap substrate works. Note `μ_r` sits inside
the square root — galvanised steel (`μ_r ≈ 200`) has a skin depth ~14× smaller
than its conductivity alone would suggest, and correspondingly worse loss.

### 3.2 AC resistance

Computed over the conducting annulus rather than the naive `R_s·L/(π·d)`, so it
degrades gracefully to the DC resistance when `δ` exceeds the wire radius
instead of diverging.

### 3.3 Referring distributed loss to the feedpoint

Current is not uniform along the conductor, so the loss resistance is weighted by
the mean-square current: **0.5** for a half-wave sinusoidal distribution,
**1/3** for a short dipole's near-triangular one.

### 3.4 The asymmetry that penalises branching

> Loss is driven by **total wire**. Tuning is driven by the **longest path**.

Every branch dissipates; only one path sets resonance. Branching factor is
therefore a direct efficiency cost, paid for whatever multiband behaviour it
buys. `resonance_calc.py --physics` computes loss from total wire and radiation
resistance from the longest path for exactly this reason.

---

## 4. Radiation resistance

Induced-EMF method for a centre-fed thin-wire dipole (Balanis eq. 4-70),
referred to the current maximum:

```
R_r = (η/2π)[ γ + ln(kl) − Ci(kl)
              + ½sin(kl)(Si(2kl) − 2Si(kl))
              + ½cos(kl)(γ + ln(kl/2) + Ci(2kl) − 2Ci(kl)) ]
```

Referred to the feedpoint: `R_in = R_r / sin²(kl/2)`.

Verified: **73.08 Ω** at *l* = λ/2 and **198.95 Ω** at *l* = λ. Textbooks quote
73.13 Ω by rounding η/4π to exactly 30; carrying the exact η gives 73.08. The
feedpoint transformation reproduces the short-dipole `20π²(l/λ)²` result to four
significant figures, which is a genuine cross-check between two independent
derivations.

`Si` and `Ci` are implemented in pure standard library — power series below
x = 2, continued fraction for E₁(ix) by modified Lentz above it. Agreement with
`scipy.special.sici` is **1.5 × 10⁻¹⁵** across x ∈ [0.01, 200]. The Abramowitz
& Stegun rational approximations were tried first and rejected: their real error
here is ~10⁻⁴, enough to shift computed radiation resistance by 0.1 Ω.

---

## 5. End effect from first principles

A resonant dipole is shorter than λ/2. Rather than hardcoding the folklore 0.95,
the code bisects the induced-EMF reactance (Balanis 4-70b, which *does* depend on
wire radius) for `X = 0`:

| length/diameter | computed k | published |
|---|---|---|
| 10 000 | 0.974 | ~0.98 |
| 1 000 | 0.965 | ~0.965 |
| 100 | 0.945 | ~0.94 |
| 25 | 0.918 | ~0.89–0.90 |

Reproduces the classic ARRL k-factor curve in the thin-wire regime. **Valid for
length/diameter ≳ 50**; below that the induced-EMF approximation drifts from
measurement, as the last row shows.

---

## 6. The Chu–Harrington bound — the ceiling nothing beats

For an antenna enclosed in a sphere of radius *a*, with `k = 2π/λ`, McLean's
exact result for linear polarisation:

```
Q_min = η · ( 1/(ka)³ + 1/(ka) )
FBW   = (S−1) / (Q·√S)          at VSWR limit S
```

| ka | Q_min | max FBW @ VSWR 2 |
|---|---|---|
| 0.1 | 1010 | 0.07 % |
| 0.3 | 40.4 | 1.75 % |
| 0.5 | 10.0 | 7.07 % |
| 1.0 | 2.0 | 35.4 % |

This follows from the spherical-mode expansion outside the enclosing sphere. It
depends on **size and efficiency only** — not topology. No fractal, spiral or
meander beats it.

**The bound is only tight for ka < 1.** Above that it stays true but goes slack —
it will report Q < 1 and near-100% bandwidth, which means "size is not what
limits you", not "this antenna is genuinely that broadband". A quarter-wave
monopole sits at ka ≈ π/2 ≈ 1.57 at its own resonance, so the bound says nothing
useful there. `chu_bound_is_tight()` gates the claim, and both report paths print
the caveat rather than the bare number.

The practical consequence for this project: **fractal folding buys a longer
conductor inside the same sphere; it does not enlarge the sphere.** Any claim
that a fractal is simultaneously small *and* broadband must be checked against
this bound first. The one legitimate escape is that lower efficiency *relaxes*
Q — you can trade radiated power for bandwidth, which is a real engineering
option but not a free lunch, and it is worth stating plainly rather than
discovering by accident.

---

## 7. Dielectric loading (Phase 3 fulgurite moulds)

**A fulgurite is fused silica glass — a dielectric, not a conductor.** Casting a
conductor into one loads it:

```
ε_eff  = 1 + F(ε_r − 1)          F = fraction of near field in the dielectric
shrink = 1/√ε_eff
Q_d    = 1/tan δ                  ceiling from dielectric loss alone
```

Fused silica (ε_r ≈ 3.8, tan δ ≈ 10⁻⁴) at F = 0.5 gives ~0.68× shrink with
negligible added loss. Soda-lime glass (tan δ ≈ 10⁻²) caps Q at 100. Wet sand
(tan δ ≈ 0.1) caps it at 10 and should be avoided.

First-order mixing rule: good for direction and rough magnitude, not a
substitute for a full-wave solve. And note the shrink is not free — a smaller
structure means a smaller enclosing sphere, which tightens §6.

---

## 8. External noise — the most under-appreciated term

Reception is not set by antenna efficiency alone but by SNR against the *total*
system noise. Ohmic loss does two things at once: it attenuates the signal **and**
injects thermal noise at the conductor's physical temperature.

```
T_A   = η·T_ext + (1−η)·T_phys
SNR   ∝ η / (η·T_ext + (1−η)·T_phys + T_rx)
```

Sky brightness from Recommendation ITU-R P.372:

```
Fam = 52 − 23·log₁₀(f_MHz)      [dB above kT₀]
```

Median for a short vertical monopole neglecting ionospheric shielding; decile
deviation ~2 dB. This is a straight line in log-frequency and reaches 0 dB at
`10^(52/23) = 182 MHz`, going negative above that — not a physical prediction,
just the edge of the range where galactic noise dominates. The code therefore
applies it over **20–182 MHz**, floors sky temperature at 5 K (CMB plus
atmosphere) outside that, and flags extrapolated values.

The floor means "the sky contributes nothing you can rely on here", not a
measurement. Real backyards sit well above it thanks to ground pickup and
man-made noise, which this model does not attempt to predict.

### SNR penalty vs the naive `10·log₁₀(η)` guess

Bare RTL-SDR, NF 6 dB (`antenna_physics.py --noise-sweep`):

| frequency | T_sky | η = 0.5 | η = 0.1 | η = 0.01 |
|---|---|---|---|---|
| 10 MHz | 230 065 K | −0.02 | −0.19 | −1.75 |
| 30 MHz | 18 119 K | −0.26 | −1.90 | −8.46 |
| 137.1 MHz | 269 K | −3.05 | −10.07 | −20.08 |
| 162.6 MHz | 88 K | −3.45 | −10.76 | −20.83 |

*(naive guess: −3.0, −10.0, −20.0 dB)*

**This is the single most important number for this project.** At HF the sky is
thousands of kelvin, so a 1%-efficient antenna costs only 1.75 dB — the loss
attenuates sky noise right along with the signal. By 137 MHz the sky has cooled
to ~269 K, comparable to the conductor's own 290 K, and the penalty converges on
the naive value.

**At the NOAA band there is no free lunch.** A fractal that trades efficiency for
size pays full price. Any "fractal beats dipole" result at 137 MHz that appears
to violate this should be treated as a measurement artefact until proven
otherwise — see `docs/measurement_protocol.md`.

---

## 9. Link budget

```
slant range   d = −R⊕sin(el) + √((R⊕sin el)² + h² + 2R⊕h)
FSPL          = 20·log₁₀(4πd/λ)
A_e           = G·λ²/4π
N             = k·T_sys·B
cascade       T = T₁ + T₂/G₁ + …
```

NOAA APT, lossless dipole, 30° elevation: **+9.8 dB margin**. At 10% efficiency
the margin goes negative below ~40° elevation, so you lose most of the pass.
Range varies by ~12 dB from horizon to zenith, which is why low-elevation rows
decide how much image you actually get.

### Faraday rotation

APT is RHCP. The nominal 3 dB linear-to-circular penalty understates the problem:
at 137 MHz a signal crossing the ionosphere undergoes **many complete rotations**,
varying through the pass with total electron content. A circular antenna is
immune — rotating a circular polarisation only changes its phase. Any flat
fractal or plain dipole is linear and will fade deeply, and no amount of
efficiency fixes it.

Fractal-vs-dipole is therefore a fair comparison (both fade). Either against a
proper QFH or turnstile is **not**.

---

## 10. Known limitations

1. **`ρ∞` and `n_sat` are empirical.** Largest error source in resonance
   prediction. Calibrate against measurement.
2. **Geometry is 2-D.** Real prototypes are 3-D; out-of-plane segments change
   both the enclosing sphere and the cancellation behaviour.
3. **No mutual coupling between branches.** Radiation resistance is computed for
   an isolated conductor of the given path length. Closely spaced branches
   couple strongly, which is precisely the effect §1.2 hand-waves into `ρ`. This
   is the single biggest reason to run a real solver.
4. **No ground plane / counterpoise model.** Height above ground shifts feedpoint
   impedance and pattern substantially at these frequencies.
5. **Thin-wire assumption throughout** — valid for length/diameter ≳ 50.
6. **Sky model is a median.** Ignores galactic-plane pointing, man-made noise,
   and ground pickup, all of which dominate in a real backyard.

For anything beyond a first-order estimate, export the geometry and run it
through **NEC-2** (`nec2c`, `xnec2c`, or `PyNEC`). These closed-form models are
for design intuition and sanity-checking, not for final numbers.

---

## References

- Balanis, *Antenna Theory: Analysis and Design* — dipole radiation resistance
  and reactance (eq. 4-70, 4-70b), loss resistance (eq. 2-90b).
- McLean, "A re-examination of the fundamental limits on the radiation Q of
  electrically small antennas", *IEEE Trans. Antennas Propag.* 44(5), 1996.
- Chu, "Physical limitations of omni-directional antennas", *J. Appl. Phys.* 19,
  1948; Harrington (1960).
- Recommendation ITU-R P.372, *Radio noise*.
- Abramowitz & Stegun, *Handbook of Mathematical Functions*, §5.2.
- Press et al., *Numerical Recipes* — `cisi` continued-fraction algorithm.
- ARRL *Antenna Book* — dipole length correction (k-factor) curve.
