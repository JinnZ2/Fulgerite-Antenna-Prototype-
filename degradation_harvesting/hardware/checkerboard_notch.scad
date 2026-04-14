// ============================================================================
// Checkerboard notch tile for microfracture harvesting prototype
//
// A 100 x 100 mm brittle tile with a grid of 8x8 mm islands separated by 2 mm
// TPU walls (print the walls separately, or dual-extrude). Each island has one
// or more V-notches on its top face to set a programmed crack threshold:
//
//   Type H (high threshold): 1 central notch
//   Type M (medium):         2 perpendicular notches
//   Type L (low):            2x2 grid of 4 half-length notches
//
// The checkerboard pattern (H M / M L) repeats across the tile so the array
// contains a spread of thresholds - that's the "flaw-size distribution"
// that spreads damage across the fleet instead of concentrating it.
//
// NOTE: the v_notch module here differs from the voice-note draft, which used
// linear_extrude along Z and would have punched a vertical slit *through* the
// cube rather than carving a groove across its top face. This version uses
// rotate + linear_extrude to lay the prism on its side so the groove runs
// along the local Y axis, with the apex pointing down into the material.
// ============================================================================

// ---- Parameters ------------------------------------------------------------
tile_w       = 100;   // mm, tile width
tile_h       = 100;   // mm, tile height (unused except for comment / symmetry)
island_size  = 8;     // mm, edge length of each brittle island
gap          = 2;     // mm, TPU wall thickness between islands
thickness    = 2;     // mm, tile thickness
notch_depth  = 0.4;   // mm, ~20% of thickness
notch_width  = 0.2;   // mm, V-groove opening width at the top surface

N = floor(tile_w / (island_size + gap));   // islands per row (= 10)

// ---- V-groove module -------------------------------------------------------
// Carves a V-groove along the Y axis. Place at [cx, cy, thickness] and the
// groove will run from (cx, cy - length/2) to (cx, cy + length/2) on the top
// surface, biting downward to (thickness - depth).
module v_notch(length, depth, width) {
    rotate([-90, 0, 0])
        linear_extrude(height = length, center = true)
            polygon(points = [
                [-width/2, 0],
                [ width/2, 0],
                [ 0,       depth]
            ]);
}

// ---- Single island with typed notch pattern --------------------------------
module island(type, x, y) {
    translate([x, y, 0]) {
        difference() {
            cube([island_size, island_size, thickness]);

            if (type == "H") {
                // 1 central notch running along Y
                translate([island_size/2, island_size/2, thickness])
                    v_notch(island_size, notch_depth, notch_width);
            }
            else if (type == "M") {
                // 2 perpendicular notches (Y-running + X-running)
                translate([island_size/2, island_size/2, thickness])
                    v_notch(island_size, notch_depth, notch_width);
                translate([island_size/2, island_size/2, thickness])
                    rotate([0, 0, 90])
                        v_notch(island_size, notch_depth, notch_width);
            }
            else if (type == "L") {
                // 2x2 grid of shorter notches - densest crack seeding
                for (dx = [island_size/4, 3*island_size/4])
                    for (dy = [island_size/4, 3*island_size/4])
                        translate([dx, dy, thickness])
                            v_notch(island_size/2, notch_depth, notch_width);
            }
        }
    }
}

// ---- Assemble tile ---------------------------------------------------------
// Checkerboard pattern of types across the grid.
for (i = [0 : N - 1]) {
    for (j = [0 : N - 1]) {
        x = i * (island_size + gap);
        y = j * (island_size + gap);
        type =
            (i % 2 == 0 && j % 2 == 0) ? "H" :
            (i % 2 == 1 && j % 2 == 1) ? "L" : "M";
        island(type, x, y);
    }
}
