# Sovereign Rectifier — Wiring Reference

Minimal analog front-end for a single microfracture harvesting unit cell.
Rectifies PVDF output, stores energy in a local capacitor, detects acoustic
emission (AE) spikes with a comparator, and triggers an interrupt on the
ESP32 for each crack event.

## Function

1. **Rectification** — full-wave bridge across the PVDF film smooths the bipolar
   piezo signal into DC across `C1`.
2. **Continuous channel** — `C1` voltage is divided down (100k / 10k) and fed
   to an ESP32 ADC input. This is the slow hysteresis / continuous-strain
   signal.
3. **AE channel** — a high-pass filter (`C2`, `R2`) above the continuous
   channel strips the DC and passes spikes in the ~1.6 kHz band and above.
   These are the high-frequency transients from crack-tip events.
4. **Comparator wake-up** — `TLV3201` compares the AE signal against a
   reference taken from a divider (`R3`, `R4`) off the ESP32 3.3 V rail. When
   a spike crosses the threshold the open-drain output pulls low, driving the
   ESP32 interrupt pin and optionally lighting an LED.

## Bill of materials (one cell)

| Ref     | Part                  | Value / P/N         | Notes |
|---------|-----------------------|---------------------|-------|
| J1      | 2-pin terminal block  | 5 mm pitch          | PVDF leads in |
| D1..D4  | Schottky diode        | 1N5819 or BAT54S    | Low-Vf, fast |
| C1      | Ceramic capacitor     | 10 uF / 16 V / X7R  | Local reservoir |
| C2      | Ceramic capacitor     | 1 nF / 50 V         | High-pass input |
| R1      | Resistor              | 10 k                | Reservoir bleed (optional) |
| R2      | Resistor              | 100 k               | High-pass load |
| R3      | Resistor              | 100 k               | Top of threshold divider |
| R4      | Resistor              | 10 k                | Bottom of threshold divider |
| U1      | Comparator            | TLV3201 (SOT-23-5)  | Open-drain, 40 ns delay |
| R5      | Resistor              | 10 k                | Pull-up on comparator output |
| LED1    | Indicator LED         | any 3 mm            | Optional |
| R6      | Resistor              | 220                 | LED current limit |

Total unit cost: roughly **USD 15** in prototype quantities (see
`notes/04_build.md` for sourcing notes).

## Connections

```
PVDF+ ----+--|>|--+--|>|-- GND          full-wave bridge
          |  D1   |  D3
          |       +---- C1+ (10 uF) ----+
          |                             |
PVDF- ----+--|<|--+--|<|-- GND          |
             D2      D4                 |
                                        |
                                        +---- R1 (100 k) ----+---- ESP32 ADC (GPIO34)
                                        |                    |
                                        |                    +---- R_div_bot (10 k) --- GND
                                        |
                                        +---- C2 (1 nF) -----+---- R2 (100 k) --- GND
                                                             |
                                                             +---- U1 IN+

ESP32 3V3 --- R3 (100 k) --+--- U1 IN-
                           |
                           +--- R4 (10 k) --- GND     (~0.3 V reference)

U1 OUT (open drain) --- R5 (10 k pull-up to 3V3)
                     |
                     +--- ESP32 GPIO18   (falling-edge interrupt)
                     |
                     +--- LED1 + R6 (220 ohm) --- GND
```

## Layout notes

- Keep the PVDF-to-bridge traces short (under ~10 mm) — piezo sources are
  high-impedance and pick up hum on long runs.
- Place `C1` and `U1` as close to each other as possible; the AE signal is
  small and fast.
- Ground plane on the bottom layer of the board.
- If adding a buck-boost converter (e.g. TPS61097), bring `C1+` and GND to
  its VIN/GND pins, and wire `U1 OUT` to its enable pin so the converter
  only fires when the comparator says there's energy worth moving.

## Thresholding

Start with `R3 / R4 = 100 k / 10 k`, giving roughly 0.3 V reference. Lower
that (smaller R3 or larger R4) if spikes aren't registering; raise it if
background noise is tripping the comparator. A pot in place of R3 is worth
installing for the first prototype — you'll tune it empirically while
bending the tile.
