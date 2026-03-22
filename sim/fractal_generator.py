#!/usr/bin/env python3
"""
Fulgurite Antenna Fractal Geometry Generator

Generates Lichtenberg / fractal tree patterns that model fulgurite discharge
geometries. Outputs branch coordinates for antenna prototyping.

Usage:
    python fractal_generator.py                     # Interactive with plot
    python fractal_generator.py --depth 6 --seed 42 # Reproducible generation
    python fractal_generator.py --export branches.csv  # Export coordinates
"""

import argparse
import csv
import math
import random
import sys
from dataclasses import dataclass, field


@dataclass
class Branch:
    """A single branch segment of the fractal antenna."""
    x_start: float
    y_start: float
    x_end: float
    y_end: float
    depth: int
    length: float
    angle: float


@dataclass
class FractalAntenna:
    """Collection of branches forming a fractal antenna geometry."""
    branches: list = field(default_factory=list)
    params: dict = field(default_factory=dict)

    @property
    def total_wire_length(self):
        return sum(b.length for b in self.branches)

    @property
    def max_depth(self):
        return max(b.depth for b in self.branches) if self.branches else 0

    @property
    def branch_count(self):
        return len(self.branches)

    @property
    def bounding_box(self):
        if not self.branches:
            return (0, 0, 0, 0)
        xs = [b.x_start for b in self.branches] + [b.x_end for b in self.branches]
        ys = [b.y_start for b in self.branches] + [b.y_end for b in self.branches]
        return (min(xs), min(ys), max(xs), max(ys))


def generate_fractal(
    depth=5,
    initial_length=100.0,
    scale_ratio=0.65,
    angle_variance=35.0,
    min_branch_length=2.0,
    seed=None,
    branching_factor=2,
):
    """
    Generate a fulgurite-inspired fractal antenna geometry.

    Args:
        depth: Maximum recursion depth.
        initial_length: Length of the trunk segment (mm).
        scale_ratio: Branch length scaling factor (0.6-0.7 per README spec).
        angle_variance: Random angle spread in degrees (30-40 per README spec).
        min_branch_length: Stop recursion below this length (mm).
        seed: Random seed for reproducibility.
        branching_factor: Number of child branches per node (2 = binary tree).

    Returns:
        FractalAntenna with all branch segments.
    """
    if seed is not None:
        random.seed(seed)

    antenna = FractalAntenna(params={
        "depth": depth,
        "initial_length": initial_length,
        "scale_ratio": scale_ratio,
        "angle_variance": angle_variance,
        "min_branch_length": min_branch_length,
        "seed": seed,
        "branching_factor": branching_factor,
    })

    def _recurse(x, y, angle, length, current_depth):
        if current_depth > depth or length < min_branch_length:
            return

        x_end = x + length * math.cos(math.radians(angle))
        y_end = y + length * math.sin(math.radians(angle))

        antenna.branches.append(Branch(
            x_start=x, y_start=y,
            x_end=x_end, y_end=y_end,
            depth=current_depth,
            length=length,
            angle=angle,
        ))

        next_length = length * scale_ratio
        if branching_factor == 2:
            spread = angle_variance + random.uniform(-5, 5)
            _recurse(x_end, y_end, angle + spread, next_length, current_depth + 1)
            _recurse(x_end, y_end, angle - spread, next_length, current_depth + 1)
        else:
            for i in range(branching_factor):
                offset = (i - (branching_factor - 1) / 2) * angle_variance
                jitter = random.uniform(-5, 5)
                _recurse(x_end, y_end, angle + offset + jitter, next_length, current_depth + 1)

    # Start from origin growing upward
    _recurse(0, 0, 90, initial_length, 0)

    return antenna


def export_csv(antenna, filepath):
    """Export branch coordinates to CSV for use in CAD or other tools."""
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["branch_id", "depth", "x_start", "y_start", "x_end", "y_end", "length_mm", "angle_deg"])
        for i, b in enumerate(antenna.branches):
            writer.writerow([
                i, b.depth,
                f"{b.x_start:.3f}", f"{b.y_start:.3f}",
                f"{b.x_end:.3f}", f"{b.y_end:.3f}",
                f"{b.length:.3f}", f"{b.angle:.2f}",
            ])
    print(f"Exported {len(antenna.branches)} branches to {filepath}")


def print_summary(antenna):
    """Print a summary of the generated fractal antenna."""
    bbox = antenna.bounding_box
    print("=" * 50)
    print("Fulgurite Fractal Antenna Summary")
    print("=" * 50)
    print(f"  Branches:         {antenna.branch_count}")
    print(f"  Max depth:        {antenna.max_depth}")
    print(f"  Total wire length: {antenna.total_wire_length:.1f} mm")
    print(f"  Bounding box:     {bbox[2] - bbox[0]:.1f} x {bbox[3] - bbox[1]:.1f} mm")
    print(f"  Parameters:       {antenna.params}")
    print()


def plot_antenna(antenna, title="Fulgurite Fractal Antenna", save_path=None):
    """Plot the fractal antenna geometry using matplotlib."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.cm as cm
    except ImportError:
        print("matplotlib not installed. Install with: pip install matplotlib")
        print("Skipping plot.")
        return

    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    max_d = antenna.max_depth or 1
    cmap = cm.get_cmap("copper")

    for b in antenna.branches:
        color = cmap(b.depth / max_d)
        linewidth = max(0.5, 3.0 - b.depth * 0.4)
        ax.plot(
            [b.x_start, b.x_end], [b.y_start, b.y_end],
            color=color, linewidth=linewidth, solid_capstyle="round",
        )

    ax.set_aspect("equal")
    ax.set_title(title)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.grid(True, alpha=0.3)

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved plot to {save_path}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description="Fulgurite fractal antenna generator")
    parser.add_argument("--depth", type=int, default=5, help="Recursion depth (default: 5)")
    parser.add_argument("--length", type=float, default=100.0, help="Initial trunk length in mm (default: 100)")
    parser.add_argument("--scale", type=float, default=0.65, help="Branch scale ratio (default: 0.65)")
    parser.add_argument("--angle", type=float, default=35.0, help="Angle variance in degrees (default: 35)")
    parser.add_argument("--min-length", type=float, default=2.0, help="Min branch length in mm (default: 2)")
    parser.add_argument("--branches", type=int, default=2, help="Branching factor (default: 2)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--export", type=str, default=None, help="Export branches to CSV file")
    parser.add_argument("--save-plot", type=str, default=None, help="Save plot to image file instead of displaying")
    parser.add_argument("--no-plot", action="store_true", help="Skip plotting")
    args = parser.parse_args()

    antenna = generate_fractal(
        depth=args.depth,
        initial_length=args.length,
        scale_ratio=args.scale,
        angle_variance=args.angle,
        min_branch_length=args.min_length,
        seed=args.seed,
        branching_factor=args.branches,
    )

    print_summary(antenna)

    if args.export:
        export_csv(antenna, args.export)

    if not args.no_plot:
        plot_antenna(antenna, save_path=args.save_plot)


if __name__ == "__main__":
    main()
