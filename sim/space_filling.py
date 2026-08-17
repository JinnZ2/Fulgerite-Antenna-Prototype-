#!/usr/bin/env python3
"""
Space-Filling Curve Antenna Generator

Generates Koch and Hilbert curve geometries as antenna candidates, returning
the same FractalAntenna objects as fractal_generator so every downstream tool
(resonance_calc, layout_exporter, antenna_physics) works unchanged.

WHY THIS EXISTS
---------------
The Lichtenberg tree in fractal_generator.py is a faithful model of a fulgurite
discharge, but it is the wrong fractal for miniaturisation, and the geometry
says so plainly. Measured across the whole parameter space (depth 3-7, scale
0.5-0.8, angle 20-60 degrees), a branching tree gives:

    longest current path / physical extent   =  1.01 - 1.16
    total wire length    / physical extent   =  2.2  - 19.5

The first ratio is what buys you a lower resonant frequency. The second is what
you pay in ohmic loss. A tree branches OUTWARD, so its longest path is barely
longer than a straight line to the same tip -- the extra wire goes sideways into
parallel branches that dissipate power without extending the resonant path.
Up to 19x the loss for 16% of the size reduction is a bad trade.

Space-filling curves fold the wire BACK on itself inside a bounded footprint,
so the path grows while the extent does not:

    Koch order n     path/extent  =  (4/3)^n   -> 1.33, 1.78, 2.37, 3.16
    Hilbert order n  path/extent  ~  2^n       -> 2, 4, 8, 16

That is the geometry family the miniaturisation claim actually needs. Nothing
here is free -- shrinking the enclosing sphere tightens the Chu-Harrington
bandwidth bound and the added wire still adds loss -- but now the size
reduction is real and the trade can be measured instead of assumed.

Keep the tree for the fulgurite-morphology and multiband questions. Use these
when the question is "how small can this get and still work".

Usage:
    python space_filling.py koch --order 3
    python space_filling.py hilbert --order 3 --size 200
    python space_filling.py koch --order 4 --export koch4.csv
    python space_filling.py compare --max-order 5     # geometry trade table
"""

import argparse
import math

from fractal_generator import Branch, FractalAntenna, export_csv, plot_antenna


def _polyline_to_antenna(points, params):
    """
    Convert an ordered point list into a FractalAntenna.

    Segment `depth` is set to the segment's index along the curve. That is not
    a fractal iteration number -- it is what lets the tree-oriented path finder
    in resonance_calc walk a chain, since each segment starts where the previous
    one ended and sits one "depth" further along. The true iteration order is
    carried in params["order"].
    """
    antenna = FractalAntenna(params=params)
    for i in range(len(points) - 1):
        (x0, y0), (x1, y1) = points[i], points[i + 1]
        dx, dy = x1 - x0, y1 - y0
        antenna.branches.append(Branch(
            x_start=x0, y_start=y0,
            x_end=x1, y_end=y1,
            depth=i,
            length=math.hypot(dx, dy),
            angle=math.degrees(math.atan2(dy, dx)),
        ))
    return antenna


# ---------------------------------------------------------------------------
# Koch curve
# ---------------------------------------------------------------------------

def koch_points(order, initial_length=100.0, indentation_deg=60.0):
    """
    Koch curve control points.

    Each segment is replaced by four segments of one third the length, with the
    middle two forming a tent of the given indentation angle. The classic Koch
    curve uses 60 degrees; smaller angles give less compression but a less
    convoluted (easier to bend, lower loss) wire.
    """
    points = [(0.0, 0.0), (float(initial_length), 0.0)]
    theta = math.radians(indentation_deg)

    for _ in range(order):
        new_points = [points[0]]
        for i in range(len(points) - 1):
            (x0, y0), (x1, y1) = points[i], points[i + 1]
            dx, dy = (x1 - x0) / 3.0, (y1 - y0) / 3.0

            pa = (x0 + dx, y0 + dy)
            pb = (x0 + 2 * dx, y0 + 2 * dy)
            # Apex: rotate the middle third by the indentation angle.
            px = pa[0] + dx * math.cos(theta) - dy * math.sin(theta)
            py = pa[1] + dx * math.sin(theta) + dy * math.cos(theta)

            new_points.extend([pa, (px, py), pb, (x1, y1)])
        points = new_points
    return points


def generate_koch(order=3, initial_length=100.0, indentation_deg=60.0):
    """Generate a Koch curve antenna geometry."""
    if order < 0:
        raise ValueError("order must be >= 0")
    points = koch_points(order, initial_length, indentation_deg)
    return _polyline_to_antenna(points, {
        "curve": "koch",
        "order": order,
        "topology": "chain",
        "initial_length": initial_length,
        "indentation_deg": indentation_deg,
    })


# ---------------------------------------------------------------------------
# Hilbert curve
# ---------------------------------------------------------------------------

def hilbert_points(order, size=100.0):
    """
    Hilbert curve control points, visiting the centres of a 2^order grid.

    Uses the standard vector recursion: each call subdivides the current cell
    into four, traversing them in an order that keeps the curve continuous.
    """
    points = []

    def recurse(x0, y0, xi, xj, yi, yj, n):
        if n <= 0:
            points.append((x0 + (xi + yi) / 2.0, y0 + (xj + yj) / 2.0))
            return
        recurse(x0, y0, yi / 2, yj / 2, xi / 2, xj / 2, n - 1)
        recurse(x0 + xi / 2, y0 + xj / 2, xi / 2, xj / 2, yi / 2, yj / 2, n - 1)
        recurse(x0 + xi / 2 + yi / 2, y0 + xj / 2 + yj / 2,
                xi / 2, xj / 2, yi / 2, yj / 2, n - 1)
        recurse(x0 + xi / 2 + yi, y0 + xj / 2 + yj,
                -yi / 2, -yj / 2, -xi / 2, -xj / 2, n - 1)

    recurse(0.0, 0.0, float(size), 0.0, 0.0, float(size), order)
    return points


def generate_hilbert(order=3, size=100.0):
    """Generate a Hilbert curve antenna geometry inside a square of `size` mm."""
    if order < 1:
        raise ValueError("order must be >= 1")
    points = hilbert_points(order, size)
    return _polyline_to_antenna(points, {
        "curve": "hilbert",
        "order": order,
        "topology": "chain",
        "size": size,
    })


# ---------------------------------------------------------------------------
# Geometry comparison
# ---------------------------------------------------------------------------

def curve_metrics(antenna):
    """
    Path length, extent and their ratio for a chain geometry.

    For a chain every segment is in series, so the current path IS the total
    wire -- unlike a tree, where they differ by an order of magnitude.
    """
    total = antenna.total_wire_length
    if not antenna.branches:
        return {"path_mm": 0.0, "extent_mm": 0.0, "ratio": 1.0, "bbox_mm": 0.0}
    first, last = antenna.branches[0], antenna.branches[-1]
    extent = math.hypot(last.x_end - first.x_start, last.y_end - first.y_start)
    x0, y0, x1, y1 = antenna.bounding_box
    bbox = max(x1 - x0, y1 - y0)
    return {
        "path_mm": total,
        "extent_mm": extent,
        "ratio": (total / extent) if extent > 0 else float("inf"),
        "bbox_mm": bbox,
        "segments": antenna.branch_count,
    }


def compare_geometries(max_order=5, initial_length=100.0):
    """Print the miniaturisation-vs-cost trade for each curve family."""
    try:
        from fractal_generator import generate_fractal
        from resonance_calc import geometry_metrics
        have_tree = True
    except ImportError:
        have_tree = False

    print("=" * 78)
    print("GEOMETRY TRADE: electrical length gained vs wire spent")
    print("=" * 78)
    print("path/extent is the miniaturisation you gain.")
    print("wire/extent is the ohmic loss you pay.")
    print("For a chain the two are identical -- every millimetre of wire is on")
    print("the current path. For a tree they diverge badly, which is the whole")
    print("point of this comparison.\n")
    print(f"{'geometry':<18}{'order':>6}{'segments':>10}{'extent mm':>11}"
          f"{'path mm':>10}{'path/ext':>10}{'wire/ext':>10}")
    print("-" * 78)

    for order in range(1, max_order + 1):
        a = generate_koch(order, initial_length)
        m = curve_metrics(a)
        print(f"{'koch':<18}{order:>6}{m['segments']:>10}{m['extent_mm']:>11.1f}"
              f"{m['path_mm']:>10.1f}{m['ratio']:>10.3f}{m['ratio']:>10.3f}")

    print()
    for order in range(1, min(max_order, 5) + 1):
        a = generate_hilbert(order, initial_length)
        m = curve_metrics(a)
        print(f"{'hilbert':<18}{order:>6}{m['segments']:>10}{m['extent_mm']:>11.1f}"
              f"{m['path_mm']:>10.1f}{m['ratio']:>10.3f}{m['ratio']:>10.3f}")

    if have_tree:
        print()
        for depth in range(1, max_order + 1):
            a = generate_fractal(depth=depth, initial_length=initial_length,
                                 scale_ratio=0.65, angle_variance=35.0, seed=42,
                                 min_branch_length=0.5)
            g = geometry_metrics(a)
            ext = g["extent_mm"]
            print(f"{'lichtenberg tree':<18}{depth:>6}{a.branch_count:>10}"
                  f"{ext:>11.1f}{g['longest_path_mm']:>10.1f}"
                  f"{g['longest_path_mm'] / ext:>10.3f}"
                  f"{g['total_wire_mm'] / ext:>10.3f}")

    print("\nRead the last two columns together. Koch and Hilbert keep them")
    print("equal -- wire spent is electrical length gained. The tree lets them")
    print("diverge: by depth 5 it spends 5x its extent in wire to gain 5%.")
    print("If the goal is a smaller antenna, use a curve. If the goal is to")
    print("study fulgurite morphology or many weak resonances, use the tree.")
    print()


def print_summary(antenna):
    """Print a summary of a generated curve."""
    m = curve_metrics(antenna)
    p = antenna.params
    print("=" * 56)
    print(f"{p.get('curve', 'curve').upper()} CURVE ANTENNA  (order {p.get('order')})")
    print("=" * 56)
    print(f"  Segments:          {m['segments']}")
    print(f"  Wire / path length:{m['path_mm']:>10.1f} mm")
    print(f"  End-to-end extent: {m['extent_mm']:>10.1f} mm")
    print(f"  Bounding box:      {m['bbox_mm']:>10.1f} mm")
    print(f"  Path/extent ratio: {m['ratio']:>10.3f}x")
    print(f"  Parameters:        {p}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Space-filling curve antenna generator")
    sub = parser.add_subparsers(dest="curve", required=True)

    def common(sp):
        sp.add_argument("--export", type=str, default=None, help="Export branches to CSV")
        sp.add_argument("--save-plot", type=str, default=None, help="Save plot to image file")
        sp.add_argument("--no-plot", action="store_true", help="Skip plotting")

    k = sub.add_parser("koch", help="Koch curve")
    k.add_argument("--order", type=int, default=3, help="Iteration order (default: 3)")
    k.add_argument("--length", type=float, default=100.0,
                   help="End-to-end extent in mm (default: 100)")
    k.add_argument("--indentation", type=float, default=60.0,
                   help="Indentation angle in degrees (default: 60, classic Koch)")
    common(k)

    h = sub.add_parser("hilbert", help="Hilbert curve")
    h.add_argument("--order", type=int, default=3, help="Iteration order (default: 3)")
    h.add_argument("--size", type=float, default=100.0,
                   help="Square footprint side in mm (default: 100)")
    common(h)

    c = sub.add_parser("compare", help="Print the geometry trade table")
    c.add_argument("--max-order", type=int, default=5, help="Highest order (default: 5)")
    c.add_argument("--length", type=float, default=100.0, help="Reference extent mm")

    args = parser.parse_args()

    if args.curve == "compare":
        compare_geometries(args.max_order, args.length)
        return

    if args.curve == "koch":
        antenna = generate_koch(args.order, args.length, args.indentation)
        title = f"Koch curve order {args.order}"
    else:
        antenna = generate_hilbert(args.order, args.size)
        title = f"Hilbert curve order {args.order}"

    print_summary(antenna)

    if args.export:
        export_csv(antenna, args.export)
    if not args.no_plot:
        plot_antenna(antenna, title=title, save_path=args.save_plot)


if __name__ == "__main__":
    main()
