#!/usr/bin/env python3
"""
Resonance Frequency Calculator

Predicts where a fractal antenna geometry resonates, and how confident you can
be about it.

A NOTE ON THE MODEL
-------------------
The original model here (and in the README) was `f0 = c / (2 * L_eff)` with
L_eff taken as the TOTAL UNFOLDED BRANCH LENGTH. That over-predicts the size
reduction badly, for two separate reasons:

1. Topology. Branches of a tree hang in PARALLEL off their parent, not in
   series. Current leaving the feed divides at every node; it does not traverse
   every branch in turn. A depth-5 binary tree has 63 branches but a current
   path only ever crosses 6 of them. Summing all 63 overstates the electrical
   length by roughly an order of magnitude.

2. Cancellation. Even along one path, folding a wire into a small volume does
   not convert all of its length into electrical length. Closely spaced
   antiparallel segments radiate out of phase and largely cancel in the far
   field; that energy is stored reactively instead. This is why measured
   miniaturisation from fractal iteration SATURATES after a few iterations
   rather than tracking perimeter, a result reported consistently for Koch and
   Minkowski geometries.

So this module now reports a BRACKET rather than a single number:

    f_high  = straight-wire resonance over the physical extent (no folding gain)
    f_low   = resonance over the longest root-to-leaf current path (perfect
              folding, no cancellation)
    f_model = a saturating interpolation between them

f_low and f_high are hard physical bounds. f_model uses two empirical
parameters that MUST be calibrated against a NanoVNA sweep or an NEC solve
before you trust it -- defaults are ballpark figures from the Koch literature.
The legacy total-wire-length number is still printed, labelled, so you can see
how far off it was.

Usage:
    python resonance_calc.py                              # Default fractal
    python resonance_calc.py --depth 6 --length 150
    python resonance_calc.py --seed 42 --report           # Full report
    python resonance_calc.py --target-freq 137.1e6        # Design for NOAA
    python resonance_calc.py --depth 5 --physics          # Add loss/Q/noise
    python resonance_calc.py --depth 5 --compare-models   # Model bracket only
"""

import argparse
import math
from collections import defaultdict

from fractal_generator import generate_fractal

try:
    import antenna_physics as phys
except ImportError:  # pragma: no cover - physics module is optional
    phys = None

# Speed of light in mm/s
C_MM_S = 299_792_458_000.0  # mm/s

# --- Empirical fractal compression parameters -------------------------------
# rho_inf : the largest frequency-compression ratio folding can ever deliver
#           for this family of shapes (f_straight / f_fractal).
# n_sat   : iteration depth constant over which compression approaches rho_inf.
#
# Defaults are order-of-magnitude figures consistent with published Koch
# monopole/dipole results, where useful miniaturisation stalls after roughly
# four iterations. They are NOT derived from first principles and are the
# single largest source of error in this module. Fit them to your own measured
# resonances with --calibrate as soon as you have two data points.
DEFAULT_RHO_INF = 1.40
DEFAULT_N_SAT = 2.0


def calc_resonance_freq(length_mm):
    """
    Calculate half-wave resonance frequency for a given conductor length.
    f0 = c / (2 * L_eff)
    """
    if length_mm <= 0:
        return float("inf")
    return C_MM_S / (2.0 * length_mm)


def calc_quarter_wave_freq(length_mm):
    """Calculate quarter-wave resonance frequency."""
    if length_mm <= 0:
        return float("inf")
    return C_MM_S / (4.0 * length_mm)


def calc_length_for_freq(freq_hz, mode="half"):
    """
    Calculate required conductor length for a target frequency.

    Args:
        freq_hz: Target frequency in Hz.
        mode: 'half' for half-wave, 'quarter' for quarter-wave.
    """
    if freq_hz <= 0:
        return float("inf")
    divisor = 2.0 if mode == "half" else 4.0
    return C_MM_S / (divisor * freq_hz)


def build_child_index(antenna):
    """
    Map each branch index to its child branch indices.

    Children are branches one level deeper whose start point coincides with
    this branch's end point. Indexed by rounded endpoint so this is O(n)
    rather than the O(n^2) pairwise scan it replaces -- at depth 10 that is
    ~2000 branches instead of ~4 million comparisons.
    """
    def key(x, y):
        return (round(x, 3), round(y, 3))

    starts = defaultdict(list)
    for j, b in enumerate(antenna.branches):
        starts[key(b.x_start, b.y_start)].append(j)

    children = defaultdict(list)
    for i, b in enumerate(antenna.branches):
        for j in starts.get(key(b.x_end, b.y_end), ()):
            if j != i and antenna.branches[j].depth == b.depth + 1:
                children[i].append(j)
    return children


def enumerate_paths(antenna, children=None):
    """Yield every root-to-leaf path as a list of branch indices."""
    if children is None:
        children = build_child_index(antenna)
    roots = [i for i, b in enumerate(antenna.branches) if b.depth == 0]

    paths = []
    for root in roots:
        stack = [(root, [root])]
        while stack:
            node, acc = stack.pop()
            kids = children.get(node, [])
            if not kids:
                paths.append(acc)
            else:
                for kid in kids:
                    stack.append((kid, acc + [kid]))
    return paths


def geometry_metrics(antenna):
    """
    Extract the length scales that actually govern resonance.

    Returns:
        total_wire_mm     sum of every branch (the legacy, misleading number)
        longest_path_mm   longest root-to-leaf current path -- the electrical
                          length bound
        extent_mm         straight-line feed-to-farthest-tip distance -- the
                          physical size bound
        enclosing_radius_mm  radius of the smallest circle centred on the feed
                          that contains the structure; feeds the Chu bound
        path_lengths_mm   every root-to-leaf path length, for multiband analysis
    """
    children = build_child_index(antenna)
    paths = enumerate_paths(antenna, children)

    path_lengths = [sum(antenna.branches[i].length for i in path) for path in paths]

    # Feed is at the trunk's start point.
    if antenna.branches:
        fx, fy = antenna.branches[0].x_start, antenna.branches[0].y_start
    else:
        fx = fy = 0.0

    tips = []
    for path in paths:
        b = antenna.branches[path[-1]]
        tips.append(math.hypot(b.x_end - fx, b.y_end - fy))

    all_pts = [(b.x_end, b.y_end) for b in antenna.branches]
    all_pts += [(b.x_start, b.y_start) for b in antenna.branches]
    enclosing = max((math.hypot(x - fx, y - fy) for x, y in all_pts), default=0.0)

    return {
        "total_wire_mm": antenna.total_wire_length,
        "longest_path_mm": max(path_lengths, default=0.0),
        "mean_path_mm": (sum(path_lengths) / len(path_lengths)) if path_lengths else 0.0,
        "extent_mm": max(tips, default=0.0),
        "enclosing_radius_mm": enclosing,
        "path_lengths_mm": path_lengths,
        "path_count": len(paths),
    }


def compression_ratio(depth, rho_inf=DEFAULT_RHO_INF, n_sat=DEFAULT_N_SAT):
    """
    Frequency compression from fractal folding, saturating with iteration depth:

        rho(n) = 1 + (rho_inf - 1) * (1 - exp(-n / n_sat))

    rho = 1 means the fold bought nothing (resonance stays at the straight-wire
    value); rho = 2 would mean the antenna resonates an octave lower than its
    physical size suggests. The saturating form encodes the experimental finding
    that added iterations stop helping: each new generation of detail is
    electrically smaller and contributes progressively less phase delay while
    contributing progressively more reactive storage.
    """
    if depth <= 0:
        return 1.0
    return 1.0 + (rho_inf - 1.0) * (1.0 - math.exp(-depth / n_sat))


def predict_resonance(antenna, wire_diameter_mm=1.0,
                      rho_inf=DEFAULT_RHO_INF, n_sat=DEFAULT_N_SAT):
    """
    Predict the fundamental resonance of a fractal antenna as a bracket.

    Returns a dict with f_high (no folding gain), f_low (perfect folding),
    f_model (saturating interpolation) and f_legacy (the old total-wire-length
    number, kept for comparison).
    """
    g = geometry_metrics(antenna)
    extent = g["extent_mm"]
    path = g["longest_path_mm"]

    # The structure is fed against ground/a counterpoise at the trunk base, so
    # it behaves as a monopole: quarter-wave, not half-wave, over its extent.
    # Apply the thin-wire end-effect correction if the physics module is around.
    if phys is not None and extent > 0:
        f_straight_guess = C_MM_S / (4.0 * extent)
        k = phys.shortening_factor(f_straight_guess, wire_diameter_mm)
    else:
        k = 0.95
    f_high = C_MM_S / (4.0 * extent) / k if extent > 0 else float("inf")
    f_low = C_MM_S / (4.0 * path) / k if path > 0 else float("inf")

    # Folding can never buy more compression than the wire physically provides.
    # Use the true fractal iteration order: for a chain geometry (Koch/Hilbert)
    # Branch.depth is a position index along the curve, not an iteration count,
    # so max_depth would be wildly wrong there.
    order = antenna.params.get("order", antenna.max_depth)
    rho_cap = (path / extent) if extent > 0 else 1.0
    rho = min(compression_ratio(order, rho_inf, n_sat), rho_cap)
    f_model = f_high / rho if rho > 0 else float("inf")

    f_legacy = calc_resonance_freq(g["total_wire_mm"])

    return {
        "geometry": g,
        "shortening_factor": k,
        "rho": rho,
        "rho_cap": rho_cap,
        "rho_saturated": rho >= rho_cap - 1e-9,
        "f_high_hz": f_high,
        "f_low_hz": f_low,
        "f_model_hz": f_model,
        "f_legacy_hz": f_legacy,
        "legacy_error_factor": (f_model / f_legacy) if f_legacy > 0 else float("inf"),
    }


def calibrate(measurements, depth, extent_mm, path_mm, k=0.95):
    """
    Fit rho_inf from one or more measured resonances.

    measurements: list of (depth, measured_f_hz) pairs. With a single point we
    can only solve for rho_inf at the fixed default n_sat; with several, this
    reports the implied rho at each depth so you can see whether the saturating
    form actually describes your builds.
    """
    out = []
    f_high = C_MM_S / (4.0 * extent_mm) / k if extent_mm > 0 else float("inf")
    for d, f_meas in measurements:
        if f_meas <= 0:
            continue
        rho_implied = f_high / f_meas
        out.append({"depth": d, "f_meas_hz": f_meas, "rho_implied": rho_implied})
    return {"f_high_hz": f_high, "points": out}


def analyze_antenna_resonances(antenna):
    """
    Analyze all resonance modes of a fractal antenna.

    Each unique path from root to leaf tip creates an effective conductor
    length. Additionally, individual branch segments and partial paths
    contribute to multi-band behavior.

    Returns dict with resonance analysis results.
    """
    results = {
        "total_wire_length": antenna.total_wire_length,
        "branch_resonances": [],
        "path_resonances": [],
        "unique_frequencies": set(),
    }

    # Individual branch segment resonances
    for b in antenna.branches:
        freq = calc_resonance_freq(b.length)
        results["branch_resonances"].append({
            "depth": b.depth,
            "length_mm": b.length,
            "half_wave_hz": freq,
            "quarter_wave_hz": calc_quarter_wave_freq(b.length),
        })

    # Enumerate root-to-leaf paths (iterative, O(n) child indexing)
    all_paths = enumerate_paths(antenna)

    # Calculate effective length for each path
    for path in all_paths:
        path_length = sum(antenna.branches[i].length for i in path)
        freq_half = calc_resonance_freq(path_length)
        freq_quarter = calc_quarter_wave_freq(path_length)
        results["path_resonances"].append({
            "path_depth": len(path),
            "length_mm": path_length,
            "half_wave_hz": freq_half,
            "quarter_wave_hz": freq_quarter,
        })

    # Collect unique frequency bands (rounded to MHz)
    for br in results["branch_resonances"]:
        results["unique_frequencies"].add(round(br["half_wave_hz"] / 1e6))
    for pr in results["path_resonances"]:
        results["unique_frequencies"].add(round(pr["half_wave_hz"] / 1e6))

    return results


def format_freq(hz):
    """Format frequency for display."""
    if hz >= 1e9:
        return f"{hz / 1e9:.2f} GHz"
    elif hz >= 1e6:
        return f"{hz / 1e6:.2f} MHz"
    elif hz >= 1e3:
        return f"{hz / 1e3:.2f} kHz"
    else:
        return f"{hz:.2f} Hz"


def print_report(antenna, results):
    """Print a full resonance analysis report."""
    print("=" * 60)
    print("FULGURITE ANTENNA RESONANCE ANALYSIS")
    print("=" * 60)
    print(f"\nTotal wire length: {results['total_wire_length']:.1f} mm")
    print(f"Number of branches: {antenna.branch_count}")
    print(f"Max depth: {antenna.max_depth}")

    # Full antenna resonance (legacy model, retained for comparison only)
    full_half = calc_resonance_freq(results["total_wire_length"])
    print(f"\n[legacy model] total-wire half-wave resonance: {format_freq(full_half)}")
    print("  Superseded -- branches are electrically parallel, not in series.")
    print("  See the resonance prediction section for the corrected bracket.")

    # Path-based resonances
    print(f"\n--- Root-to-Leaf Path Resonances ({len(results['path_resonances'])} paths) ---")
    seen = set()
    for pr in sorted(results["path_resonances"], key=lambda x: x["half_wave_hz"]):
        freq_mhz = round(pr["half_wave_hz"] / 1e6, 1)
        if freq_mhz not in seen:
            seen.add(freq_mhz)
            print(f"  Path length {pr['length_mm']:7.1f} mm → "
                  f"λ/2 = {format_freq(pr['half_wave_hz']):>12s}  |  "
                  f"λ/4 = {format_freq(pr['quarter_wave_hz']):>12s}")

    # Branch-level resonances by depth
    print(f"\n--- Branch Segment Resonances by Depth ---")
    by_depth = defaultdict(list)
    for br in results["branch_resonances"]:
        by_depth[br["depth"]].append(br)

    for depth in sorted(by_depth.keys()):
        branches = by_depth[depth]
        lengths = [b["length_mm"] for b in branches]
        freqs = [b["half_wave_hz"] for b in branches]
        print(f"  Depth {depth}: {len(branches)} branches, "
              f"length {min(lengths):.1f}-{max(lengths):.1f} mm, "
              f"λ/2 range {format_freq(min(freqs))} - {format_freq(max(freqs))}")

    # Notable RF bands
    print("\n--- Coverage of Notable RF Bands ---")
    notable_bands = [
        (137.1e6, "NOAA APT Weather Satellite"),
        (144e6, "2m Amateur Radio"),
        (162.55e6, "NOAA Weather Radio"),
        (433e6, "70cm Amateur / ISM"),
        (915e6, "ISM 900 MHz"),
        (1090e6, "ADS-B Aircraft"),
        (1575.42e6, "GPS L1"),
    ]

    all_freqs_hz = ([pr["half_wave_hz"] for pr in results["path_resonances"]] +
                    [br["half_wave_hz"] for br in results["branch_resonances"]])

    for target, name in notable_bands:
        closest = min(all_freqs_hz, key=lambda f: abs(f - target))
        offset_pct = abs(closest - target) / target * 100
        match = "GOOD" if offset_pct < 10 else "FAIR" if offset_pct < 25 else "POOR"
        print(f"  {name:30s} ({format_freq(target):>12s}): "
              f"nearest = {format_freq(closest):>12s}  [{match}, {offset_pct:.0f}% off]")


def print_prediction(pred):
    """Print the bracketed resonance prediction."""
    g = pred["geometry"]
    print("=" * 66)
    print("RESONANCE PREDICTION (bracketed)")
    print("=" * 66)
    print("\n--- Length scales that matter ---")
    print(f"  Physical extent (feed to farthest tip): {g['extent_mm']:9.1f} mm")
    print(f"  Longest current path (root to leaf):    {g['longest_path_mm']:9.1f} mm")
    print(f"  Total wire in the structure:            {g['total_wire_mm']:9.1f} mm")
    print(f"  Enclosing radius (for the Chu bound):   {g['enclosing_radius_mm']:9.1f} mm")
    print(f"  Root-to-leaf paths:                     {g['path_count']:9d}")
    print(f"\n  Path/extent ratio: {pred['rho_cap']:.2f}x  "
          "<- the most compression the wire could ever provide")
    print(f"  Modelled compression rho: {pred['rho']:.2f}x"
          + ("  [capped by geometry]" if pred["rho_saturated"] else ""))
    print(f"  End-effect shortening factor k: {pred['shortening_factor']:.4f}")

    print("\n--- Predicted fundamental (quarter-wave, monopole against ground) ---")
    print(f"  f_high (no folding gain):    {format_freq(pred['f_high_hz']):>12s}"
          "   hard upper bound")
    print(f"  f_model (saturating fit):    {format_freq(pred['f_model_hz']):>12s}"
          "   <- best estimate")
    print(f"  f_low  (perfect folding):    {format_freq(pred['f_low_hz']):>12s}"
          "   hard lower bound")
    print("\n  The true resonance lies inside [f_low, f_high]. f_model relies on")
    print("  empirical parameters -- treat it as a starting point for a sweep,")
    print("  not a prediction to build to.")

    print(f"\n  [legacy total-wire model would have said "
          f"{format_freq(pred['f_legacy_hz'])}]")
    if pred["f_legacy_hz"] > 0 and math.isfinite(pred["legacy_error_factor"]):
        print(f"  That is off by a factor of {pred['legacy_error_factor']:.1f}x "
              "and lies outside the physical bounds.")
    print()


def print_physics(antenna, pred, freq_hz, wire_diameter_mm=1.0,
                  material="copper", rx_nf_db=6.0):
    """Print loss, bandwidth-bound and noise analysis at a chosen frequency."""
    if phys is None:
        print("antenna_physics.py not importable -- skipping physics section.\n")
        return

    g = pred["geometry"]
    print("=" * 66)
    print(f"PHYSICS AT {freq_hz / 1e6:.3f} MHz")
    print("=" * 66)

    # Loss uses the TOTAL wire, since every branch dissipates even though only
    # the longest path sets resonance. This is the asymmetry that makes highly
    # branched fractals lossy: wire count drives loss, path length drives tuning.
    r_loss = phys.loss_resistance_dipole(
        g["total_wire_mm"], wire_diameter_mm, freq_hz, material)
    r_rad = phys.radiation_resistance(g["longest_path_mm"], freq_hz)
    eta = phys.radiation_efficiency(r_rad, r_loss)

    print(f"\n  Material: {material}")
    print(f"  Skin depth:              {phys.skin_depth(freq_hz, material) * 1e6:.2f} um")
    print(f"  Radiation resistance:    {r_rad:.3f} ohm   (from longest path)")
    print(f"  Loss resistance:         {r_loss:.3f} ohm   (from total wire)")
    print(f"  Radiation efficiency:    {eta * 100:.2f} %")
    print("  Note the asymmetry: every branch adds loss, but only the longest")
    print("  path sets the tuning. Branching factor is therefore a direct")
    print("  efficiency cost, paid for whatever multiband behaviour it buys.")

    ka = phys.ka_value(g["enclosing_radius_mm"], freq_hz)
    q_min = phys.chu_q_min(ka, eta)
    fbw = phys.fractional_bandwidth(q_min) * 100.0
    print(f"\n  ka:                      {ka:.3f}"
          f"{'  [electrically small]' if ka < 0.5 else ''}")
    print(f"  Chu/McLean minimum Q:    {q_min:.1f}")
    print(f"  Max bandwidth (VSWR 2):  {fbw:.2f} % "
          f"({fbw / 100 * freq_hz / 1e6:.3f} MHz)")
    if phys.chu_bound_is_tight(ka):
        print("  This ceiling depends only on the enclosing sphere and efficiency.")
        print("  Folding more wire inside the same sphere cannot raise it.")
    else:
        print("  ka > 1, so the bound is slack here -- the structure is not")
        print("  electrically small at its own resonance and size is not the")
        print("  limiting factor. Valid ceiling, but not a bandwidth prediction.")

    t_sky = phys.galactic_noise_temperature(freq_hz)
    penalty = phys.sensitivity_penalty_db(eta, freq_hz, rx_nf_db)
    print(f"\n  Sky temperature:         {t_sky:.0f} K"
          f"{'' if phys.galactic_model_valid(freq_hz) else '  [extrapolated]'}")
    print(f"  External-noise limited:  {'YES' if phys.external_noise_limited(freq_hz, rx_nf_db) else 'NO'}")
    print(f"  SNR penalty vs lossless: {penalty:.2f} dB "
          f"(naive guess would be {10 * math.log10(eta) if eta > 0 else float('-inf'):.2f} dB)")
    print()


def design_for_frequency(target_freq_hz, depth=5, scale=0.65, angle=35.0,
                         wire_diameter_mm=1.0, rho_inf=DEFAULT_RHO_INF,
                         n_sat=DEFAULT_N_SAT):
    """
    Calculate the trunk length needed to hit a target frequency.

    Corrected against the original version, which sized the antenna for a
    HALF-wave resonance over the longest path and ignored both the end effect
    and fractal compression. Three changes:

      * quarter-wave, not half-wave -- the structure is fed at the trunk base
        against a counterpoise, so it is a monopole;
      * end-effect factor k from the induced-EMF solution rather than nothing;
      * compression rho from the saturating fold model, so the design does not
        assume the fold is free.

    The geometric sum for the longest root-to-leaf path is unchanged and
    correct: L_path = L0 * (1 - r^(depth+1)) / (1 - r).
    """
    geometric_sum = (1 - scale ** (depth + 1)) / (1 - scale)

    if phys is not None:
        k = phys.shortening_factor(target_freq_hz, wire_diameter_mm)
    else:
        k = 0.95
    rho = compression_ratio(depth, rho_inf, n_sat)

    # A quarter-wave monopole resonant at the target, shortened by the end
    # effect. The fold buys rho, so the straight-line extent may be rho times
    # shorter than the electrical length demands.
    electrical_len = C_MM_S / (4.0 * target_freq_hz) * k
    target_path_length = electrical_len * rho
    initial_length = target_path_length / geometric_sum

    return {
        "target_freq_hz": target_freq_hz,
        "required_trunk_mm": initial_length,
        "total_path_mm": target_path_length,
        "geometric_sum": geometric_sum,
        "shortening_factor": k,
        "rho": rho,
        "electrical_length_mm": electrical_len,
        # What the superseded model would have produced, for comparison.
        "legacy_trunk_mm": calc_length_for_freq(target_freq_hz, "half") / geometric_sum,
    }


def main():
    parser = argparse.ArgumentParser(description="Fractal antenna resonance calculator")
    parser.add_argument("--depth", type=int, default=5, help="Fractal depth (default: 5)")
    parser.add_argument("--length", type=float, default=100.0, help="Trunk length mm (default: 100)")
    parser.add_argument("--scale", type=float, default=0.65, help="Branch scale ratio (default: 0.65)")
    parser.add_argument("--angle", type=float, default=35.0, help="Angle variance degrees (default: 35)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--report", action="store_true", help="Print full analysis report")
    parser.add_argument("--target-freq", type=float, default=None,
                        help="Design for target frequency (Hz), e.g. 137.1e6 for NOAA")
    parser.add_argument("--diameter", type=float, default=1.0,
                        help="Wire diameter mm, drives the end effect (default: 1.0)")
    parser.add_argument("--material", type=str, default="copper",
                        help="Conductor material for the physics section (default: copper)")
    parser.add_argument("--physics", action="store_true",
                        help="Add loss, bandwidth-bound and noise analysis")
    parser.add_argument("--physics-freq", type=float, default=None,
                        help="Frequency for the physics section (default: predicted f_model)")
    parser.add_argument("--rx-nf", type=float, default=6.0,
                        help="Receiver noise figure in dB (default: 6, bare RTL-SDR)")
    parser.add_argument("--compare-models", action="store_true",
                        help="Print the resonance bracket only and exit")
    parser.add_argument("--rho-inf", type=float, default=DEFAULT_RHO_INF,
                        help=f"Max fold compression (default: {DEFAULT_RHO_INF}); calibrate this")
    parser.add_argument("--n-sat", type=float, default=DEFAULT_N_SAT,
                        help=f"Compression saturation depth (default: {DEFAULT_N_SAT})")
    args = parser.parse_args()

    if args.target_freq:
        design = design_for_frequency(args.target_freq, args.depth, args.scale,
                                      args.angle, args.diameter,
                                      args.rho_inf, args.n_sat)
        print(f"Design for {format_freq(design['target_freq_hz'])}:")
        print(f"  Required trunk length: {design['required_trunk_mm']:.1f} mm")
        print(f"  Total path length:     {design['total_path_mm']:.1f} mm")
        print(f"  Electrical length:     {design['electrical_length_mm']:.1f} mm "
              f"(quarter-wave, k={design['shortening_factor']:.4f})")
        print(f"  Fold compression rho:  {design['rho']:.2f}x")
        print(f"  (depth={args.depth}, scale={args.scale})")
        print(f"  [legacy model would have said {design['legacy_trunk_mm']:.1f} mm trunk]")
        print(f"\nGenerating antenna with computed trunk length...")
        args.length = design["required_trunk_mm"]

    antenna = generate_fractal(
        depth=args.depth,
        initial_length=args.length,
        scale_ratio=args.scale,
        angle_variance=args.angle,
        seed=args.seed,
    )

    pred = predict_resonance(antenna, args.diameter, args.rho_inf, args.n_sat)

    if args.compare_models:
        print_prediction(pred)
        return

    results = analyze_antenna_resonances(antenna)

    if args.report or args.target_freq:
        print_report(antenna, results)
        print_prediction(pred)
    else:
        print(f"Antenna: {antenna.branch_count} branches, "
              f"{results['total_wire_length']:.1f} mm total wire")
        print(f"Predicted fundamental: {format_freq(pred['f_model_hz'])} "
              f"(bracket {format_freq(pred['f_low_hz'])} - "
              f"{format_freq(pred['f_high_hz'])})")
        full_res = calc_resonance_freq(results["total_wire_length"])
        print(f"[legacy total-wire λ/2 model: {format_freq(full_res)}]")

    if args.physics:
        f = args.physics_freq or pred["f_model_hz"]
        print_physics(antenna, pred, f, args.diameter, args.material, args.rx_nf)
        print(f"Unique frequency bands: {len(results['unique_frequencies'])}")
        print(f"\nRun with --report for full analysis.")


if __name__ == "__main__":
    main()
