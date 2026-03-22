#!/usr/bin/env python3
"""
SDR Data Analysis and Plotting

Analyze RF measurement data from RTL-SDR captures and NanoVNA sweeps.
Supports loading raw IQ data, CSV power spectral data, and NanoVNA S-parameter
exports. Generates comparative plots between antenna configurations.

Usage:
    python sdr_analysis.py spectrum capture.csv                 # Plot spectrum
    python sdr_analysis.py compare baseline.csv fractal.csv     # Compare two
    python sdr_analysis.py iq recording.bin --freq 137.1e6      # Analyze IQ data
    python sdr_analysis.py vnasweep nanovna_export.csv           # Plot VNA data
"""

import argparse
import csv
import struct
import sys

import numpy as np


def load_csv_spectrum(filepath):
    """
    Load spectrum data from CSV (frequency, power columns).
    Supports SDR++ CSV export and generic freq,dB formats.
    """
    freqs = []
    powers = []
    with open(filepath, "r") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            try:
                freqs.append(float(row[0]))
                powers.append(float(row[1]))
            except ValueError:
                continue
    return np.array(freqs), np.array(powers)


def load_iq_data(filepath, sample_rate=2.4e6, dtype="uint8"):
    """
    Load raw IQ data from RTL-SDR binary capture.

    RTL-SDR outputs interleaved uint8 I/Q samples (0-255, centered at 127.5).
    """
    with open(filepath, "rb") as f:
        raw = np.frombuffer(f.read(), dtype=np.uint8)

    # Convert to complex float, centered at zero
    iq = (raw.astype(np.float32) - 127.5) / 127.5
    samples = iq[0::2] + 1j * iq[1::2]
    return samples, sample_rate


def compute_psd(iq_samples, sample_rate, fft_size=1024, center_freq=0):
    """Compute power spectral density from IQ samples."""
    num_ffts = len(iq_samples) // fft_size
    if num_ffts == 0:
        raise ValueError(f"Not enough samples for FFT (have {len(iq_samples)}, need {fft_size})")

    # Average multiple FFTs for cleaner spectrum
    psd = np.zeros(fft_size)
    window = np.hanning(fft_size)
    for i in range(num_ffts):
        segment = iq_samples[i * fft_size:(i + 1) * fft_size] * window
        spectrum = np.fft.fftshift(np.fft.fft(segment))
        psd += np.abs(spectrum) ** 2

    psd /= num_ffts
    psd_db = 10 * np.log10(psd + 1e-12)

    freqs = np.fft.fftshift(np.fft.fftfreq(fft_size, 1.0 / sample_rate))
    freqs += center_freq

    return freqs, psd_db


def load_nanovna_csv(filepath):
    """
    Load NanoVNA S-parameter export (typically freq, S11_real, S11_imag or
    freq, S11_dB, S11_phase).
    """
    freqs = []
    s11_db = []
    with open(filepath, "r") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            try:
                freq = float(row[0])
                # Try to detect format: if 3+ columns with small values, assume real/imag
                if len(row) >= 3:
                    try:
                        real = float(row[1])
                        imag = float(row[2])
                        if abs(real) <= 2 and abs(imag) <= 2:
                            mag = np.sqrt(real ** 2 + imag ** 2)
                            db = 20 * np.log10(mag + 1e-12)
                        else:
                            db = float(row[1])
                    except ValueError:
                        db = float(row[1])
                else:
                    db = float(row[1])
                freqs.append(freq)
                s11_db.append(db)
            except ValueError:
                continue
    return np.array(freqs), np.array(s11_db)


def find_peaks(freqs, power_db, threshold_db=-30, min_distance_hz=1e6):
    """Find spectral peaks above a threshold."""
    peaks = []
    for i in range(1, len(power_db) - 1):
        if (power_db[i] > power_db[i - 1] and
                power_db[i] > power_db[i + 1] and
                power_db[i] > threshold_db):
            # Check minimum distance from existing peaks
            too_close = False
            for pf, _ in peaks:
                if abs(freqs[i] - pf) < min_distance_hz:
                    too_close = True
                    break
            if not too_close:
                peaks.append((freqs[i], power_db[i]))
    return sorted(peaks, key=lambda p: p[1], reverse=True)


def plot_spectrum(freqs, power_db, title="Spectrum", peaks=None, save_path=None):
    """Plot a single spectrum."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed. Install with: pip install matplotlib")
        return

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(freqs / 1e6, power_db, linewidth=0.8, color="#8B4513")
    if peaks:
        for freq, pwr in peaks:
            ax.axvline(freq / 1e6, color="red", alpha=0.3, linestyle="--")
            ax.annotate(f"{freq / 1e6:.2f} MHz\n{pwr:.1f} dB",
                        (freq / 1e6, pwr), fontsize=7,
                        textcoords="offset points", xytext=(5, 5))
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Power (dB)")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved plot to {save_path}")
    else:
        plt.show()


def plot_comparison(datasets, labels, title="Antenna Comparison", save_path=None):
    """Plot multiple spectra for comparison."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed. Install with: pip install matplotlib")
        return

    colors = ["#8B4513", "#1f77b4", "#2ca02c", "#d62728"]
    fig, ax = plt.subplots(figsize=(12, 5))

    for i, ((freqs, power_db), label) in enumerate(zip(datasets, labels)):
        color = colors[i % len(colors)]
        ax.plot(freqs / 1e6, power_db, linewidth=0.8, label=label, color=color)

    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Power (dB)")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved comparison plot to {save_path}")
    else:
        plt.show()


def cmd_spectrum(args):
    """Handle the 'spectrum' subcommand."""
    freqs, powers = load_csv_spectrum(args.file)
    print(f"Loaded {len(freqs)} points from {args.file}")
    print(f"  Frequency range: {freqs[0] / 1e6:.2f} - {freqs[-1] / 1e6:.2f} MHz")
    print(f"  Power range: {powers.min():.1f} to {powers.max():.1f} dB")

    peaks = find_peaks(freqs, powers, threshold_db=args.threshold)
    if peaks:
        print(f"\n  Top peaks:")
        for f, p in peaks[:5]:
            print(f"    {f / 1e6:.3f} MHz : {p:.1f} dB")

    plot_spectrum(freqs, powers, title=f"Spectrum: {args.file}",
                  peaks=peaks if args.show_peaks else None,
                  save_path=args.save)


def cmd_compare(args):
    """Handle the 'compare' subcommand."""
    datasets = []
    labels = args.labels.split(",") if args.labels else []

    for i, filepath in enumerate(args.files):
        freqs, powers = load_csv_spectrum(filepath)
        datasets.append((freqs, powers))
        if i >= len(labels):
            labels.append(filepath)
        print(f"Loaded {filepath}: {len(freqs)} points, "
              f"{freqs[0] / 1e6:.2f}-{freqs[-1] / 1e6:.2f} MHz")

    plot_comparison(datasets, labels, title="Antenna Comparison", save_path=args.save)


def cmd_iq(args):
    """Handle the 'iq' subcommand."""
    samples, sr = load_iq_data(args.file, sample_rate=args.sample_rate)
    print(f"Loaded {len(samples)} IQ samples from {args.file}")
    print(f"  Sample rate: {sr / 1e6:.1f} MHz")
    print(f"  Duration: {len(samples) / sr:.2f} seconds")

    freqs, psd = compute_psd(samples, sr, fft_size=args.fft_size,
                             center_freq=args.freq)
    peaks = find_peaks(freqs, psd)
    plot_spectrum(freqs, psd, title=f"IQ Spectrum: {args.file}",
                  peaks=peaks, save_path=args.save)


def cmd_vnasweep(args):
    """Handle the 'vnasweep' subcommand."""
    freqs, s11 = load_nanovna_csv(args.file)
    print(f"Loaded {len(freqs)} points from {args.file}")
    print(f"  Frequency range: {freqs[0] / 1e6:.2f} - {freqs[-1] / 1e6:.2f} MHz")

    # Find resonance points (S11 minima = best impedance match)
    minima = []
    for i in range(1, len(s11) - 1):
        if s11[i] < s11[i - 1] and s11[i] < s11[i + 1] and s11[i] < -10:
            minima.append((freqs[i], s11[i]))

    if minima:
        print(f"\n  Resonance points (S11 < -10dB):")
        for f, s in sorted(minima, key=lambda x: x[1]):
            print(f"    {f / 1e6:.3f} MHz : S11 = {s:.1f} dB")

    plot_spectrum(freqs, s11, title=f"S11 Return Loss: {args.file}",
                  peaks=None, save_path=args.save)


def main():
    parser = argparse.ArgumentParser(description="SDR data analysis for antenna testing")
    subparsers = parser.add_subparsers(dest="command", help="Analysis mode")

    # Spectrum plot
    sp = subparsers.add_parser("spectrum", help="Plot spectrum from CSV")
    sp.add_argument("file", help="CSV file with frequency,power columns")
    sp.add_argument("--threshold", type=float, default=-30, help="Peak detection threshold (dB)")
    sp.add_argument("--show-peaks", action="store_true", help="Annotate peaks on plot")
    sp.add_argument("--save", type=str, default=None, help="Save plot to file")

    # Compare
    cp = subparsers.add_parser("compare", help="Compare multiple spectra")
    cp.add_argument("files", nargs="+", help="CSV files to compare")
    cp.add_argument("--labels", type=str, default=None, help="Comma-separated labels")
    cp.add_argument("--save", type=str, default=None, help="Save plot to file")

    # IQ analysis
    iq = subparsers.add_parser("iq", help="Analyze raw IQ capture")
    iq.add_argument("file", help="Binary IQ file from RTL-SDR")
    iq.add_argument("--freq", type=float, default=0, help="Center frequency (Hz)")
    iq.add_argument("--sample-rate", type=float, default=2.4e6, help="Sample rate (Hz)")
    iq.add_argument("--fft-size", type=int, default=1024, help="FFT size")
    iq.add_argument("--save", type=str, default=None, help="Save plot to file")

    # VNA sweep
    vn = subparsers.add_parser("vnasweep", help="Plot NanoVNA S-parameter sweep")
    vn.add_argument("file", help="NanoVNA CSV export")
    vn.add_argument("--save", type=str, default=None, help="Save plot to file")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    commands = {
        "spectrum": cmd_spectrum,
        "compare": cmd_compare,
        "iq": cmd_iq,
        "vnasweep": cmd_vnasweep,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
