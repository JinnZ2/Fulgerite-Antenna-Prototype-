# Measurement Protocol — Making the Fractal-vs-Dipole Comparison Mean Something

The project's central experiment is "compare the fractal against a baseline
dipole on an RTL-SDR." That comparison is easy to run and easy to get wrong. The
error sources below are all larger than the effect being measured, so a result
obtained without controlling them carries no information.

This is written to be followed at the bench. Where a step exists to kill a
specific artefact, the artefact is named.

---

## 0. Before touching hardware

Run the prediction so you know what you are looking for:

```bash
cd sim/
python resonance_calc.py --depth 5 --seed 42 --compare-models --physics
```

Write down `f_low`, `f_model`, `f_high`. **Sweep the whole bracket**, not just
`f_model` — the bracket is wide because the model is genuinely uncertain, and a
resonance found outside it means the geometry assumptions are wrong, which is a
more interesting result than a hit.

---

## 1. The artefact that will bite you first: common-mode current on the coax

A coax braid connected to an unbalanced antenna radiates and receives. Without a
choke **the feedline is part of your antenna**, often the larger part.

This is not a small correction. It routinely dominates, and it changes when you
move the cable, which is why "the fractal did better" can reverse when you
reposition the desk. Two antennas with different feedpoint impedances excite
different amounts of common-mode current, so the comparison is corrupted
*differently* for each one — this bias does not cancel.

**Fix:** a common-mode choke at the feedpoint on *both* antennas. Either 5–8
turns of the coax through a mix-31 ferrite toroid, or 8–10 turns of RG-316 in a
50 mm coil. Fit it before any other work.

**Verify:** grab the coax 300 mm below the feedpoint while watching the noise
floor. A choked system barely moves; an unchoked one shifts by several dB.

---

## 2. Calibrate the NanoVNA properly

1. Let it warm up ~10 minutes — the reference oscillator drifts.
2. Set the sweep to the range you actually care about. Calibration is only valid
   over the calibrated span; do not calibrate 1–900 MHz and then zoom in.
3. Run **SOLT** (short / open / load / thru) at the **far end of the cable that
   will connect to the antenna**, not at the connector. Calibrating at the
   instrument moves the reference plane to the wrong place and adds the cable's
   phase to every reading.
4. Re-run the calibration after changing cables, and after any large temperature
   change.

**Record S11 as touchstone (`.s1p`)**, not screenshots. `sdr_analysis.py vnasweep`
reads the exported CSV.

### What S11 tells you and what it does not

A deep S11 null means power is *entering* the antenna, **not** that it is being
radiated. A resistive load has a perfect match and radiates nothing. A lossy,
badly-radiating fractal can show a *better* S11 than an efficient one, because
its loss resistance conveniently approaches 50 Ω.

> **A better match is not a better antenna.** Never rank geometries by S11 depth
> alone.

Efficiency needs a separate measurement — a Wheeler cap, or a calibrated
reference comparison as below.

---

## 3. Controls that must be identical between antennas

Change one variable. In practice this means:

| control | why |
|---|---|
| Same feedpoint height above ground | ground reflection sets pattern and impedance; a half-metre shift is worth several dB |
| Same location and orientation | near-field objects detune and shadow |
| Same coax, choke and connectors | see §1 |
| Same RTL-SDR, gain setting, **AGC off** | AGC silently rescales; two captures are then not comparable |
| Same bandwidth and FFT settings | noise power scales with bandwidth |
| Same polarisation | see §5 |
| Interleave A/B/A/B in one session | see §4 |

Set gain manually and record the number in the log.

---

## 4. Interleave, don't sequence

Ionospheric conditions, man-made noise and the galactic background all vary on
minute-to-hour timescales. Testing the dipole in the morning and the fractal in
the afternoon measures the *time of day*.

**Do:** A/B/A/B/A/B with a few minutes per leg, then compare medians and report
the spread of the repeats. If the A-to-A spread is comparable to the A-to-B
difference, you have no result — say so.

---

## 5. Use a reference signal, not "the noise floor"

Absolute dBFS from an RTL-SDR is meaningless — uncalibrated gain, unknown
frontend response. Two workable references:

- **Best:** a signal generator / noise source at fixed distance and level. Gives
  a genuine relative gain figure.
- **Practical:** a stable, always-on local transmitter (NOAA weather radio at
  162.400–162.550 MHz, or a local FM/pager carrier) as the reference, and report
  **SNR**, never raw level. SNR is insensitive to receiver gain; raw level is not.

For satellite passes, compare **SNR vs elevation angle** rather than a single
number — range varies by ~12 dB across a pass. `link_budget.py --sweep-elevation`
gives the expected shape to compare against.

---

## 6. Polarisation and the Faraday trap

NOAA APT is **right-hand circularly polarised**. A flat fractal and a flat dipole
are both linear, so both lose the nominal 3 dB — that part cancels in the
comparison.

What does not cancel cleanly is **Faraday rotation**. At 137 MHz the ionosphere
rotates the incoming polarisation through many complete turns, varying through
the pass. Both linear antennas fade, but they fade at different times if their
orientations differ. **Mount both with the same orientation**, or the fading
pattern alone will produce a spurious "winner."

If you compare against a QFH or turnstile, expect the circular antenna to win by
much more than 3 dB on that basis alone. That is not a fractal failure.

---

## 7. Measuring efficiency: the Wheeler cap

The one measurement that separates "resonates" from "radiates", and the number
the physics model most wants calibrated.

1. Measure feedpoint resistance `R_free` at resonance in the open.
2. Enclose the antenna in a conducting sphere/cylinder of radius ≈ λ/2π
   (a metal bucket or foil-lined box works at these frequencies). This
   suppresses radiation while leaving loss unchanged.
3. Measure `R_cap` at the same frequency. This is loss alone.
4. `η = (R_free − R_cap) / R_free`

Compare to `resonance_calc.py --physics`. A large disagreement means the loss
model is missing something real — joints, plating, or dielectric in the former.
Joints are the usual culprit: every unsoldered mechanical joint in a bent-wire
fractal adds contact resistance in series with the current path, and a depth-5
tree has a lot of joints.

---

## 8. Calibrating the compression model

`ρ∞` and `n_sat` in `resonance_calc.py` are the largest error source in the
resonance prediction and are currently ballpark literature figures.

Build the **same geometry at several iteration depths** (3, 4, 5), measure each
resonance, and back out the implied compression:

```
ρ_implied = f_high / f_measured
```

`calibrate()` in `resonance_calc.py` does this arithmetic. Then check the shape:
if `ρ_implied` keeps climbing with depth rather than levelling off, the
saturating model is wrong for this geometry family and should be replaced, not
refitted. Report either outcome — a refuted model is a result.

---

## 9. Log format

One file per session in `/prototypes/`, one row per capture in `/data/`:

```
date, time_utc, antenna_id, geometry, depth, material, wire_dia_mm,
height_m, orientation, choke (y/n), rtlsdr_gain_db, agc (off), bandwidth_hz,
center_freq_hz, reference_source, snr_db, notes
```

Record the failures and the reconfigurations too. A log that only contains
successful captures cannot distinguish a real effect from selection.

---

## 10. Sanity checks before believing a result

- [ ] Choke fitted to both antennas, cable-grab test passes
- [ ] VNA calibrated at the antenna end of the cable, over the swept span
- [ ] RTL-SDR AGC **off**, gain recorded
- [ ] A/B interleaved, repeats show A-to-A spread smaller than A-to-B difference
- [ ] Result reported as SNR against a reference, not raw dBFS
- [ ] Both antennas at the same height and orientation
- [ ] Measured resonance falls inside the predicted `[f_low, f_high]` bracket —
      if not, the geometry model is wrong and that is worth writing up
- [ ] Efficiency measured, not inferred from S11

If a fractal appears to beat a dipole by more than a couple of dB at 137 MHz,
the physics says to suspect the measurement first: §8 of `physics_model.md`
shows there is no external-noise headroom at this frequency to hide a gain from.
Re-check §1 before anything else — an unchoked feedline is the usual explanation.
