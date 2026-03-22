#!/usr/bin/env python3
"""
Resonance Frequency Calculator

Calculates expected resonance frequencies for fractal antenna geometries
based on branch lengths and electromagnetic theory. Helps predict which
frequency bands a given fractal design will resonate at before building.

Usage:
    python resonance_calc.py                              # Default fractal
    python resonance_calc.py --depth 6 --length 150
    python resonance_calc.py --seed 42 --report           # Full report
    python resonance_calc.py --target-freq 137.1e6        # Design for NOAA
"""

import argparse
import math
from collections import defaultdict

from fractal_generator import generate_fractal

# Speed of light in mm/s
C_MM_S = 299_792_458_000.0  # mm/s


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

    # Build adjacency for path enumeration
    # Find root-to-leaf paths by tracing the tree structure
    children = defaultdict(list)
    roots = []
    for i, b in enumerate(antenna.branches):
        if b.depth == 0:
            roots.append(i)
        # Find children: branches that start where this one ends
        for j, b2 in enumerate(antenna.branches):
            if (j != i and b2.depth == b.depth + 1 and
                    abs(b2.x_start - b.x_end) < 0.01 and
                    abs(b2.y_start - b.y_end) < 0.01):
                children[i].append(j)

    # Enumerate root-to-leaf paths
    def find_paths(node, current_path):
        current_path = current_path + [node]
        if not children[node]:
            yield current_path
        else:
            for child in children[node]:
                yield from find_paths(child, current_path)

    all_paths = []
    for root in roots:
        for path in find_paths(root, []):
            all_paths.append(path)

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

    # Full antenna resonance
    full_half = calc_resonance_freq(results["total_wire_length"])
    print(f"\nFull-length half-wave resonance: {format_freq(full_half)}")

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


def design_for_frequency(target_freq_hz, depth=5, scale=0.65, angle=35.0):
    """Calculate required initial trunk length to hit a target frequency."""
    # The longest path determines the lowest resonance.
    # For a binary tree with scale r, the longest path length is:
    # L_total = L0 * (1 + r + r^2 + ... + r^depth) = L0 * (1 - r^(depth+1)) / (1 - r)
    geometric_sum = (1 - scale ** (depth + 1)) / (1 - scale)
    target_path_length = calc_length_for_freq(target_freq_hz, mode="half")
    initial_length = target_path_length / geometric_sum

    return {
        "target_freq_hz": target_freq_hz,
        "required_trunk_mm": initial_length,
        "total_path_mm": target_path_length,
        "geometric_sum": geometric_sum,
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
    args = parser.parse_args()

    if args.target_freq:
        design = design_for_frequency(args.target_freq, args.depth, args.scale, args.angle)
        print(f"Design for {format_freq(design['target_freq_hz'])}:")
        print(f"  Required trunk length: {design['required_trunk_mm']:.1f} mm")
        print(f"  Total path length:     {design['total_path_mm']:.1f} mm")
        print(f"  (depth={args.depth}, scale={args.scale})")
        print(f"\nGenerating antenna with computed trunk length...")
        args.length = design["required_trunk_mm"]

    antenna = generate_fractal(
        depth=args.depth,
        initial_length=args.length,
        scale_ratio=args.scale,
        angle_variance=args.angle,
        seed=args.seed,
    )

    results = analyze_antenna_resonances(antenna)

    if args.report or args.target_freq:
        print_report(antenna, results)
    else:
        print(f"Antenna: {antenna.branch_count} branches, "
              f"{results['total_wire_length']:.1f} mm total wire")
        full_res = calc_resonance_freq(results["total_wire_length"])
        print(f"Full-length λ/2 resonance: {format_freq(full_res)}")
        print(f"Unique frequency bands: {len(results['unique_frequencies'])}")
        print(f"\nRun with --report for full analysis.")


if __name__ == "__main__":
    main()
