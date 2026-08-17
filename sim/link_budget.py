#!/usr/bin/env python3
"""
Satellite Link Budget

Answers the question the geometry tools cannot: given this antenna, at this
efficiency, on this receiver -- will a NOAA APT pass actually decode?

Defaults describe a NOAA POES APT downlink received by an RTL-SDR. Every term
is overridable, and every term is printed, so a failed prediction points at the
line that killed it rather than at a single opaque number.

THE FARADAY PROBLEM
-------------------
APT is right-hand circularly polarised, and this matters more than the nominal
3 dB polarisation penalty suggests. At 137 MHz a signal crossing the ionosphere
undergoes Faraday rotation of many complete turns, and the amount varies through
the pass with total electron content and geometry. A CIRCULAR antenna is immune:
rotating a circular polarisation just changes its phase. A LINEAR antenna --
which is what any flat fractal or plain dipole is -- sees its alignment with the
incoming field sweep in and out, producing deep fades that no amount of antenna
efficiency fixes.

So a flat fractal tested against a flat dipole is a fair comparison, and both
will fade. Neither is a fair comparison against a proper QFH or turnstile. Keep
that in mind before concluding a geometry "failed".

Usage:
    python link_budget.py                                  # NOAA APT defaults
    python link_budget.py --elevation 30 --efficiency 0.5
    python link_budget.py --sweep-elevation                # Margin vs elevation
    python link_budget.py --efficiency 0.05 --rx-nf 6      # A lossy fractal
    python link_budget.py --preset noaa-apt --lna-nf 1.0   # With a preamp
"""

import argparse
import math

import antenna_physics as phys

EARTH_RADIUS_KM = 6371.0

# Preset downlinks. Figures are nominal published values; EIRP in particular
# varies with satellite attitude and where you sit in the antenna pattern.
PRESETS = {
    "noaa-apt": {
        "freq_hz": 137.1e6,
        "eirp_dbm": 37.0,          # ~5 W transmitter into a modest antenna
        "altitude_km": 854.0,      # NOAA-18/19 sun-synchronous orbit
        "bandwidth_hz": 34e3,      # APT occupied bandwidth
        "required_snr_db": 10.0,   # usable image; below ~8 dB it degrades fast
        "polarization": "linear_to_circular",
        "label": "NOAA POES APT (137.1 MHz)",
    },
    "noaa-wx": {
        "freq_hz": 162.55e6,
        "eirp_dbm": 60.0,          # terrestrial NWR transmitter, 1 kW class
        "altitude_km": 0.0,        # ground station -- use --distance instead
        "bandwidth_hz": 16e3,
        "required_snr_db": 12.0,
        "polarization": "matched",
        "label": "NOAA Weather Radio (162.55 MHz)",
    },
    "meteor-lrpt": {
        "freq_hz": 137.9e6,
        "eirp_dbm": 40.0,
        "altitude_km": 820.0,
        "bandwidth_hz": 150e3,
        "required_snr_db": 8.0,
        "polarization": "linear_to_circular",
        "label": "Meteor-M LRPT (137.9 MHz)",
    },
}


def slant_range_km(elevation_deg, altitude_km, earth_radius_km=EARTH_RADIUS_KM):
    """
    Distance to a satellite at a given elevation angle above the horizon.

        d = -Re*sin(el) + sqrt((Re*sin(el))^2 + h^2 + 2*Re*h)

    At 90 degrees this reduces to the orbital altitude; at 0 degrees it gives
    the horizon distance, which for an 854 km orbit is over 3000 km -- a 12 dB
    path-loss swing across a single pass.
    """
    if altitude_km <= 0:
        return 0.0
    el = math.radians(elevation_deg)
    re_sin = earth_radius_km * math.sin(el)
    return -re_sin + math.sqrt(re_sin ** 2 + altitude_km ** 2
                               + 2 * earth_radius_km * altitude_km)


def cascade_noise_temperature(stages):
    """
    Friis cascade: stages is a list of (gain_db, noise_figure_db) tuples in
    signal order. Returns the total equivalent input noise temperature in K.

    This is what shows whether a preamp is worth fitting: a low-noise first
    stage with real gain makes everything after it nearly irrelevant.
    """
    t_total = 0.0
    gain_product = 1.0
    for gain_db, nf_db in stages:
        t_stage = phys.noise_figure_to_temperature(nf_db)
        t_total += t_stage / gain_product
        gain_product *= 10.0 ** (gain_db / 10.0)
    return t_total


def compute_link(freq_hz, eirp_dbm, distance_m, gain_dbi, efficiency,
                 bandwidth_hz, rx_temp_k, polarization="linear_to_circular",
                 mismatch_loss_db=0.0, feedline_loss_db=0.0,
                 t_physical=290.0, extra_loss_db=0.0):
    """
    Evaluate one link. Returns every intermediate term, not just the answer.

    Antenna gain is handled as (directivity) + (efficiency), kept separate
    because they fail differently: directivity is geometry and is what a fractal
    might plausibly change, efficiency is material loss and is what it usually
    costs you.
    """
    fspl_db = phys.free_space_path_loss_db(distance_m, freq_hz)
    pol_db = phys.polarization_loss_db(polarization)
    eff_db = 10.0 * math.log10(efficiency) if efficiency > 0 else float("-inf")

    received_dbm = (eirp_dbm - fspl_db + gain_dbi + eff_db
                    - pol_db - mismatch_loss_db - feedline_loss_db
                    - extra_loss_db)

    t_sky = phys.galactic_noise_temperature(freq_hz)
    t_ant = phys.antenna_noise_temperature(t_sky, efficiency, t_physical)
    # Feedline loss both attenuates and adds its own thermal noise.
    feed_lin = 10.0 ** (feedline_loss_db / 10.0)
    t_sys = t_ant / feed_lin + t_physical * (1.0 - 1.0 / feed_lin) + rx_temp_k

    noise_dbm = phys.noise_power_dbm(t_sys, bandwidth_hz)
    snr_db = received_dbm - noise_dbm

    return {
        "freq_hz": freq_hz,
        "eirp_dbm": eirp_dbm,
        "distance_m": distance_m,
        "fspl_db": fspl_db,
        "gain_dbi": gain_dbi,
        "efficiency": efficiency,
        "efficiency_db": eff_db,
        "polarization_db": pol_db,
        "mismatch_db": mismatch_loss_db,
        "feedline_db": feedline_loss_db,
        "extra_db": extra_loss_db,
        "received_dbm": received_dbm,
        "t_sky_k": t_sky,
        "t_antenna_k": t_ant,
        "t_system_k": t_sys,
        "bandwidth_hz": bandwidth_hz,
        "noise_dbm": noise_dbm,
        "snr_db": snr_db,
    }


def print_link(link, required_snr_db, label=""):
    """Print a full link budget with a per-line accounting."""
    print("=" * 66)
    print(f"LINK BUDGET{' -- ' + label if label else ''}")
    print("=" * 66)
    print(f"  Frequency:              {link['freq_hz'] / 1e6:>10.3f} MHz")
    print(f"  Slant range:            {link['distance_m'] / 1000:>10.1f} km")

    print("\n--- Signal path (dB unless noted) ---")
    print(f"  Satellite EIRP:         {link['eirp_dbm']:>10.2f} dBm")
    print(f"  Free-space path loss:   {-link['fspl_db']:>10.2f}")
    print(f"  Antenna directivity:    {link['gain_dbi']:>10.2f} dBi")
    print(f"  Radiation efficiency:   {link['efficiency_db']:>10.2f}"
          f"   ({link['efficiency'] * 100:.1f} %)")
    print(f"  Polarisation mismatch:  {-link['polarization_db']:>10.2f}")
    print(f"  Impedance mismatch:     {-link['mismatch_db']:>10.2f}")
    print(f"  Feedline loss:          {-link['feedline_db']:>10.2f}")
    if link["extra_db"]:
        print(f"  Other losses:           {-link['extra_db']:>10.2f}")
    print(f"  {'-' * 40}")
    print(f"  Received power:         {link['received_dbm']:>10.2f} dBm")

    print("\n--- Noise ---")
    print(f"  Sky temperature:        {link['t_sky_k']:>10.1f} K")
    print(f"  Antenna temperature:    {link['t_antenna_k']:>10.1f} K")
    print(f"  System temperature:     {link['t_system_k']:>10.1f} K")
    print(f"  Bandwidth:              {link['bandwidth_hz'] / 1e3:>10.1f} kHz")
    print(f"  Noise power:            {link['noise_dbm']:>10.2f} dBm")

    margin = link["snr_db"] - required_snr_db
    print("\n--- Result ---")
    print(f"  SNR:                    {link['snr_db']:>10.2f} dB")
    print(f"  Required SNR:           {required_snr_db:>10.2f} dB")
    print(f"  Margin:                 {margin:>10.2f} dB   "
          f"{'PASS' if margin >= 0 else 'FAIL'}")
    if margin < 0:
        print(f"\n  Short by {-margin:.1f} dB. Compare the loss lines above:")
        print("  efficiency and feedline are the ones you can usually buy back.")
    print()


def sweep_elevation(preset, gain_dbi, efficiency, rx_temp_k, mismatch_db,
                    feedline_db):
    """Show how margin varies across a pass -- range changes by ~12 dB."""
    print("=" * 66)
    print(f"MARGIN vs ELEVATION -- {preset['label']}")
    print("=" * 66)
    print(f"  efficiency {efficiency * 100:.1f} %, directivity {gain_dbi:.1f} dBi, "
          f"T_rx {rx_temp_k:.0f} K\n")
    print(f"{'elev deg':>10}{'range km':>11}{'FSPL dB':>10}"
          f"{'SNR dB':>10}{'margin dB':>11}{'':>7}")
    print("-" * 66)
    for el in [5, 10, 20, 30, 45, 60, 90]:
        d_km = slant_range_km(el, preset["altitude_km"])
        link = compute_link(
            preset["freq_hz"], preset["eirp_dbm"], d_km * 1000.0,
            gain_dbi, efficiency, preset["bandwidth_hz"], rx_temp_k,
            preset["polarization"], mismatch_db, feedline_db)
        margin = link["snr_db"] - preset["required_snr_db"]
        print(f"{el:>10}{d_km:>11.1f}{link['fspl_db']:>10.2f}"
              f"{link['snr_db']:>10.2f}{margin:>11.2f}"
              f"{'  PASS' if margin >= 0 else '  FAIL':>7}")
    print("\n  A pass is only usable while the margin stays positive, so the")
    print("  low-elevation rows decide how much of an image you actually get.")
    print()


def main():
    parser = argparse.ArgumentParser(description="Satellite link budget calculator")
    parser.add_argument("--preset", choices=sorted(PRESETS), default="noaa-apt",
                        help="Downlink preset (default: noaa-apt)")
    parser.add_argument("--freq", type=float, default=None, help="Override frequency Hz")
    parser.add_argument("--eirp", type=float, default=None, help="Override EIRP dBm")
    parser.add_argument("--elevation", type=float, default=30.0,
                        help="Elevation angle in degrees (default: 30)")
    parser.add_argument("--distance", type=float, default=None,
                        help="Override slant range in km")
    parser.add_argument("--gain", type=float, default=2.15,
                        help="Antenna directivity dBi (default: 2.15, a dipole)")
    parser.add_argument("--efficiency", type=float, default=1.0,
                        help="Radiation efficiency 0-1 (default: 1.0)")
    parser.add_argument("--rx-nf", type=float, default=6.0,
                        help="Receiver noise figure dB (default: 6, bare RTL-SDR)")
    parser.add_argument("--lna-nf", type=float, default=None,
                        help="Add an LNA of this NF dB ahead of the receiver")
    parser.add_argument("--lna-gain", type=float, default=20.0,
                        help="LNA gain dB (default: 20)")
    parser.add_argument("--mismatch-loss", type=float, default=0.0,
                        help="Impedance mismatch loss dB (default: 0)")
    parser.add_argument("--feedline-loss", type=float, default=0.5,
                        help="Feedline loss dB (default: 0.5)")
    parser.add_argument("--bandwidth", type=float, default=None,
                        help="Override receiver bandwidth Hz")
    parser.add_argument("--required-snr", type=float, default=None,
                        help="Override required SNR dB")
    parser.add_argument("--sweep-elevation", action="store_true",
                        help="Print margin across a pass and exit")
    args = parser.parse_args()

    preset = dict(PRESETS[args.preset])
    if args.freq is not None:
        preset["freq_hz"] = args.freq
    if args.eirp is not None:
        preset["eirp_dbm"] = args.eirp
    if args.bandwidth is not None:
        preset["bandwidth_hz"] = args.bandwidth
    if args.required_snr is not None:
        preset["required_snr_db"] = args.required_snr

    if args.lna_nf is not None:
        rx_temp = cascade_noise_temperature(
            [(args.lna_gain, args.lna_nf), (0.0, args.rx_nf)])
    else:
        rx_temp = phys.noise_figure_to_temperature(args.rx_nf)

    if args.sweep_elevation:
        sweep_elevation(preset, args.gain, args.efficiency, rx_temp,
                        args.mismatch_loss, args.feedline_loss)
        return

    if args.distance is not None:
        d_km = args.distance
    else:
        d_km = slant_range_km(args.elevation, preset["altitude_km"])
        if d_km <= 0:
            raise SystemExit(
                "This preset is a ground station; pass --distance in km.")

    link = compute_link(
        preset["freq_hz"], preset["eirp_dbm"], d_km * 1000.0,
        args.gain, args.efficiency, preset["bandwidth_hz"], rx_temp,
        preset["polarization"], args.mismatch_loss, args.feedline_loss)

    print_link(link, preset["required_snr_db"], preset["label"])

    if args.lna_nf is not None:
        print(f"  Receiver chain: LNA {args.lna_nf:.1f} dB NF / "
              f"{args.lna_gain:.0f} dB gain -> RX {args.rx_nf:.1f} dB NF")
        print(f"  Cascaded T_rx = {rx_temp:.1f} K "
              f"(bare receiver would be "
              f"{phys.noise_figure_to_temperature(args.rx_nf):.1f} K)\n")


if __name__ == "__main__":
    main()
