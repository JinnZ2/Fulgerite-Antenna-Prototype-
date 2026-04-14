# Prototype Build — $300 Proof of Concept

*Hand-buildable on a kitchen table. No hydraulic press, no cleanroom, no
custom fabrication. See `hardware/` for the companion files:
OpenSCAD tile, schematic reference, and the ESP32 sketch.*

## 1. Bill of materials

| Component        | Specifics                                        | ~Cost |
|------------------|--------------------------------------------------|-------|
| PVDF film        | PiezoTech 28 µm, metalized (1 ft²)               | $25   |
| Brittle layer    | Glass-fiber epoxy sheet, 1 mm, 10x10 cm          | $10   |
| TPU filament     | NinjaFlex or any flexible 95A                    | $30   |
| Conductive epoxy | MG Chemicals 8331                                | $20   |
| Schottky diodes  | BAT54S or 1N5819 (pack of 10)                    | $5    |
| Capacitors       | 10 uF, 1 nF (assorted pack)                      | $5    |
| Resistors        | 10 k, 100 k (assorted pack)                      | $5    |
| Comparator       | TLV3201 (SOT-23-5)                               | $3    |
| Microcontroller  | ESP32-C3 or DevKit V1 (either works)             | $8    |
| Tools            | Soldering iron, multimeter, wire (assumed owned) | —     |

**Total per 10x10 cm cell: ~$111**. For a 1 m² array (100 cells) roughly
**$8300** — cheap enough for a pilot, expensive enough to think twice.

## 2. Manufacturing the notched brittle tile

### Option A — hand-filed (cheapest)

Take the glass-epoxy sheet. Mark a 5x5 grid of 8x8 mm squares with a
fine-tip marker. Use a triangle file or a diamond burr on a Dremel to cut a
shallow V-notch (0.3–0.5 mm deep) in the center of each square. Allow
roughly 30 minutes. Consistency matters more than exact depth.

Notch patterns by type (matches the sim's threshold classes):

- **Type L** (low threshold): four notches in a 2x2 grid
- **Type M** (medium): two perpendicular notches
- **Type H** (high): one central notch

This gives the tile a **programmed distribution of weaknesses** — the same
thing the sim expresses in `thresholds = rng.uniform(0.5, 2.0, N)`.

### Option B — dual-material 3D print

Use a dual-extrusion printer (or print in two passes and glue):

- **Brittle phase** — ceramic-filled SLA resin (e.g. Formlabs Ceramic) or
  high-fill ceramic photopolymer. Cracks cleanly.
- **Ductile phase** — TPU walls (0.2 mm thick) as crack arrestors.

The `hardware/checkerboard_notch.scad` file emits the geometry for Option
B: a 100 mm tile with 8x8 mm brittle islands separated by 2 mm TPU walls,
each island notched per its type (H / M / L). Render in OpenSCAD → export
STL → slice for dual extrusion (or print the island pattern in brittle
resin and the wall grid separately in TPU, then press-fit).

### Why walls matter

The TPU walls are the **crack-arrest rule** from `01_framework.md` made
physical. A crack initiated in one island propagates to the wall, where the
soft phase absorbs it — the crack cannot cross to the next island. That's
how "many small failures" stays stable at the fleet level instead of
cascading into one large failure.

## 3. PVDF lamination and poling

### The trap

PVDF needs 80–100 V / µm to align its dipoles. If you bond the film to the
brittle layer *first* and try to pole it afterward, the notches act as
field concentrators and short out the poling voltage.

### Order of operations that actually works

1. **Pole the PVDF film first**, before lamination. A corona discharge rig
   is the cheap DIY route — under $200 in parts.
2. **Then bond** with a conductive epoxy that does not require a
   high-temperature cure (MG Chemicals 8331 works at room temperature).
3. Clamp lightly for 24 hours.

Pre-poled PVDF from a supplier is the other option, and for a single-cell
prototype it is probably worth the extra cost over building a corona rig.

## 4. The Sovereign rectifier (analog front-end)

See `hardware/sovereign_rectifier.md` for the full schematic, BOM, and
connection diagram.

Function in one sentence: **rectify PVDF → store in C1 → split into a slow
continuous channel (to the ADC) and a high-pass AE channel (to a
comparator) → trigger an interrupt on the ESP32 for each crack event.**

Build it on perfboard first. Solder the bridge, the reservoir cap, the
high-pass filter, and the comparator. Total assembly time: under an hour
once parts arrive.

## 5. Monitor firmware

`hardware/esp32_ae_monitor.ino` reads the two channels and prints once per
second over Serial:

```
C1=1.234 V   spikes=42
```

`C1` is the rectified hysteresis voltage (slow strain channel). `spikes`
is the cumulative AE event count. The ISR increments the count on every
falling edge from the comparator.

Pin choice is `GPIO34` for the ADC and `GPIO18` for the interrupt on a
classic ESP32 DevKit. On ESP32-C3, `GPIO34` does not exist — use one of
`GPIO0..GPIO4` for ADC1 instead, and pick any spare GPIO for the interrupt.

## 6. Manual test procedure — first weekend

1. Connect the PVDF leads to the bridge input.
2. Lay the tile on a table, notches facing up.
3. **Press your thumb** into the center of a Type L square until you feel a
   tiny click (crack initiation).
4. Watch the LED flash on the comparator output.
5. On the ESP32 serial monitor, confirm the spike count incremented.
6. **Bend the whole tile** gently — you should see low-level continuous
   voltage rise on the 10 uF cap (read `C1=` on Serial or measure with a
   multimeter).

### Crude calibration

Count how many thumb-presses (or bending cycles) it takes for a Type L
square to stop producing spikes — that's the end-of-life for that cell.
Compare to Type H. You should see exactly what the sim predicts: denser
notches → more frequent events → shorter life.

## 7. Success criteria after one weekend

- Measurable microjoules harvested from intentional cracking.
- AE events logged on a microcontroller.
- Notch density shown to control event rate (L fires most, H fires least).
- A working prototype of a system that **uses entropy instead of fighting
  it**.

## 8. Second weekend — put it in water

Drop the tile (sealed with silicone around the edges of the electronics)
into a bucket with a wave simulator — a paddle, even a child's toy that
sloshes water. Record output under random sloshing. Compare to the sim's
predictions with `--burst-prob 0.05` and a matching step count.

## 9. Heterogeneity as modularity — the institutional hack

Manufacturers and certifiers hate "flawed" materials. They love "modular
components with different part numbers."

So do not ask for a heterogeneous sheet. Ask for an **array of three part
types**:

- **Type H** — high threshold (few notches, thick islands)
- **Type M** — medium
- **Type L** — low (dense notches, thin islands)

Assemble them in a repeating pattern (H M L M H …). Same physics, but now
it is a standard bill of materials instead of a custom graded material.
No institutional friction.

## 10. Next milestones (in order)

1. **Single-cell bench test** — confirms notches control crack statistics.
2. **Three-cell array** — confirms cell-to-cell variation is under 20% and
   no cascade when one cell dies.
3. **Bucket / wave-tank test** — confirms the sim's burst statistics match
   reality.
4. **1 m² field prototype** — requires adaptive thresholding and
   hot-swappable cells from `03_refinements.md`.

Stop and evaluate after each milestone. The failure modes are cheap to
discover at step 1 and expensive at step 4.
