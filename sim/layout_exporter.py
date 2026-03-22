#!/usr/bin/env python3
"""
Antenna Layout Template Exporter

Generates printable SVG templates from fractal antenna geometries for use
as wire-bending guides. Print at 1:1 scale and use as a physical template
to shape copper wire into the fractal antenna pattern.

Usage:
    python layout_exporter.py                          # Default fractal to SVG
    python layout_exporter.py --depth 4 --output template.svg
    python layout_exporter.py --scale-to-fit 200       # Fit within 200mm square
"""

import argparse
import math

from fractal_generator import generate_fractal


def antenna_to_svg(antenna, page_width_mm=210, page_height_mm=297, margin_mm=15,
                   scale_to_fit=None, show_labels=True, show_grid=True):
    """
    Convert a FractalAntenna to an SVG string suitable for printing.

    Args:
        antenna: FractalAntenna object from fractal_generator.
        page_width_mm: Page width in mm (default A4: 210).
        page_height_mm: Page height in mm (default A4: 297).
        margin_mm: Page margin in mm.
        scale_to_fit: If set, scale antenna to fit within this size (mm).
        show_labels: Add depth labels and measurements.
        show_grid: Add background grid for alignment.

    Returns:
        SVG content as a string.
    """
    bbox = antenna.bounding_box
    ant_w = bbox[2] - bbox[0]
    ant_h = bbox[3] - bbox[1]

    if ant_w == 0 or ant_h == 0:
        raise ValueError("Antenna has zero extent")

    usable_w = page_width_mm - 2 * margin_mm
    usable_h = page_height_mm - 2 * margin_mm

    if scale_to_fit:
        target = scale_to_fit
        scale = min(target / ant_w, target / ant_h)
    else:
        scale = min(usable_w / ant_w, usable_h / ant_h)

    # Center the antenna on the page
    scaled_w = ant_w * scale
    scaled_h = ant_h * scale
    offset_x = margin_mm + (usable_w - scaled_w) / 2 - bbox[0] * scale
    offset_y = margin_mm + (usable_h - scaled_h) / 2 + bbox[3] * scale  # flip Y

    def tx(x):
        return offset_x + x * scale

    def ty(y):
        return offset_y - y * scale  # SVG Y is inverted

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                 f'width="{page_width_mm}mm" height="{page_height_mm}mm" '
                 f'viewBox="0 0 {page_width_mm} {page_height_mm}">')

    # White background
    lines.append(f'  <rect width="{page_width_mm}" height="{page_height_mm}" fill="white"/>')

    # Grid
    if show_grid:
        lines.append('  <g stroke="#e0e0e0" stroke-width="0.1">')
        for x in range(0, page_width_mm + 1, 10):
            weight = "0.2" if x % 50 == 0 else "0.1"
            lines.append(f'    <line x1="{x}" y1="0" x2="{x}" y2="{page_height_mm}" stroke-width="{weight}"/>')
        for y in range(0, page_height_mm + 1, 10):
            weight = "0.2" if y % 50 == 0 else "0.1"
            lines.append(f'    <line x1="0" y1="{y}" x2="{page_width_mm}" y2="{y}" stroke-width="{weight}"/>')
        lines.append('  </g>')

    # Antenna branches
    max_d = antenna.max_depth or 1
    depth_colors = [
        "#8B4513",  # saddle brown (trunk)
        "#A0522D",  # sienna
        "#CD853F",  # peru
        "#D2691E",  # chocolate
        "#DEB887",  # burlywood
        "#F4A460",  # sandy brown
        "#FFDEAD",  # navajo white
        "#FFE4C4",  # bisque
    ]

    lines.append('  <g stroke-linecap="round">')
    for b in antenna.branches:
        color = depth_colors[min(b.depth, len(depth_colors) - 1)]
        width = max(0.3, 2.0 - b.depth * 0.25)
        lines.append(
            f'    <line x1="{tx(b.x_start):.2f}" y1="{ty(b.y_start):.2f}" '
            f'x2="{tx(b.x_end):.2f}" y2="{ty(b.y_end):.2f}" '
            f'stroke="{color}" stroke-width="{width}"/>'
        )
    lines.append('  </g>')

    # Junction dots at branch points for wire-bending reference
    lines.append('  <g fill="#333">')
    for b in antenna.branches:
        if b.depth > 0:
            r = max(0.3, 1.0 - b.depth * 0.1)
            lines.append(f'    <circle cx="{tx(b.x_start):.2f}" cy="{ty(b.y_start):.2f}" r="{r}"/>')
    lines.append('  </g>')

    # Labels
    if show_labels:
        lines.append('  <g font-family="monospace" font-size="3" fill="#666">')
        lines.append(f'    <text x="{margin_mm}" y="{margin_mm - 3}">'
                     f'Fulgurite Antenna Template — '
                     f'Depth: {antenna.max_depth}, '
                     f'Branches: {antenna.branch_count}, '
                     f'Wire: {antenna.total_wire_length:.0f}mm'
                     f'</text>')
        lines.append(f'    <text x="{margin_mm}" y="{page_height_mm - margin_mm + 5}">'
                     f'Scale: {scale:.2f}x | '
                     f'Print at 100% (no scaling) for accurate dimensions'
                     f'</text>')
        lines.append('  </g>')

        # Scale bar (50mm reference)
        bar_y = page_height_mm - margin_mm + 10
        bar_x = margin_mm
        bar_len = 50 * scale
        if bar_len > 5:
            lines.append(f'  <line x1="{bar_x}" y1="{bar_y}" x2="{bar_x + bar_len}" y2="{bar_y}" '
                         f'stroke="black" stroke-width="0.5"/>')
            lines.append(f'  <text x="{bar_x}" y="{bar_y + 3}" font-family="monospace" font-size="2.5">'
                         f'50mm (at {scale:.2f}x scale)</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Export fractal antenna as printable SVG template")
    parser.add_argument("--depth", type=int, default=5, help="Fractal recursion depth (default: 5)")
    parser.add_argument("--length", type=float, default=100.0, help="Initial trunk length in mm (default: 100)")
    parser.add_argument("--scale", type=float, default=0.65, help="Branch scale ratio (default: 0.65)")
    parser.add_argument("--angle", type=float, default=35.0, help="Angle variance in degrees (default: 35)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--output", type=str, default="antenna_template.svg", help="Output SVG file")
    parser.add_argument("--page", type=str, default="a4", choices=["a4", "letter"],
                        help="Page size (default: a4)")
    parser.add_argument("--scale-to-fit", type=float, default=None,
                        help="Scale antenna to fit within this size in mm")
    parser.add_argument("--no-labels", action="store_true", help="Omit labels and measurements")
    parser.add_argument("--no-grid", action="store_true", help="Omit background grid")
    args = parser.parse_args()

    page_sizes = {
        "a4": (210, 297),
        "letter": (216, 279),
    }
    pw, ph = page_sizes[args.page]

    antenna = generate_fractal(
        depth=args.depth,
        initial_length=args.length,
        scale_ratio=args.scale,
        angle_variance=args.angle,
        seed=args.seed,
    )

    svg = antenna_to_svg(
        antenna,
        page_width_mm=pw,
        page_height_mm=ph,
        scale_to_fit=args.scale_to_fit,
        show_labels=not args.no_labels,
        show_grid=not args.no_grid,
    )

    with open(args.output, "w") as f:
        f.write(svg)

    print(f"Saved SVG template to {args.output}")
    print(f"  Page: {args.page.upper()} ({pw}x{ph}mm)")
    print(f"  Branches: {antenna.branch_count}")
    print(f"  Total wire length: {antenna.total_wire_length:.1f}mm")
    print(f"  Print at 100% scale for accurate dimensions.")


if __name__ == "__main__":
    main()
