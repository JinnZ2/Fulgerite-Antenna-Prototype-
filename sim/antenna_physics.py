#!/usr/bin/env python3
"""
Antenna Physics Core

Quantitative RF physics for the fulgurite antenna prototypes: conductor loss,
radiation resistance, radiation efficiency, the Chu-Harrington bandwidth bound,
dielectric loading by glass/sand, impedance mismatch, and external-noise-limited
sensitivity.

This module exists because `f0 = c / (2 * L_eff)` tells you where an antenna
resonates but nothing about whether it will actually *receive*. A geometry can
resonate perfectly and still be useless if its radiation resistance sits below
its loss resistance, or if its enclosing sphere is too small to support the
bandwidth you need.

Pure standard library (no numpy/scipy) so it stays importable anywhere. The
sine/cosine integrals are implemented directly and checked in --self-test.

Usage:
    python antenna_physics.py --self-test                  # Validate vs textbook
    python antenna_physics.py --freq 137.1e6 --length 1000 # Analyze a conductor
    python antenna_physics.py --freq 137.1e6 --length 1000 --material aluminum
    python antenna_physics.py --materials                  # List material data
    python antenna_physics.py --noise-sweep                # External noise study
"""

import argparse
import math

# ---------------------------------------------------------------------------
# Physical constants (SI unless noted)
# ---------------------------------------------------------------------------

C = 299_792_458.0            # speed of light, m/s
MU0 = 4.0e-7 * math.pi       # vacuum permeability, H/m
EPS0 = 1.0 / (MU0 * C * C)   # vacuum permittivity, F/m
ETA0 = MU0 * C               # free-space wave impedance, ~376.73 ohm
K_B = 1.380649e-23           # Boltzmann constant, J/K
T0 = 290.0                   # IEEE reference noise temperature, K
GAMMA = 0.5772156649015329   # Euler-Mascheroni constant

# ---------------------------------------------------------------------------
# Material data
#
# sigma  : bulk DC conductivity in S/m at ~20 C
# mu_r   : relative permeability (matters -- it multiplies skin loss)
# Values are nominal handbook figures. Real stock varies by temper, alloy and
# surface finish; plated and painted conductors vary by an order of magnitude.
# ---------------------------------------------------------------------------

CONDUCTORS = {
    "silver":        {"sigma": 6.30e7, "mu_r": 1.0,   "note": "best conductor, tarnish is not a big RF problem"},
    "copper":        {"sigma": 5.80e7, "mu_r": 1.0,   "note": "annealed; the Phase 1 baseline"},
    "copper_hard":   {"sigma": 5.65e7, "mu_r": 1.0,   "note": "hard-drawn, holds a bent fractal shape better"},
    "gold":          {"sigma": 4.10e7, "mu_r": 1.0,   "note": "plating only, does not oxidise"},
    "aluminum":      {"sigma": 3.77e7, "mu_r": 1.0,   "note": "light, but oxide makes soldered joints hard"},
    "brass":         {"sigma": 1.50e7, "mu_r": 1.0,   "note": "stiff, easy to machine, ~2x copper loss"},
    "steel_galv":    {"sigma": 6.00e6, "mu_r": 200.0, "note": "mu_r wrecks it at RF -- see skin depth"},
    "silver_epoxy":  {"sigma": 1.00e6, "mu_r": 1.0,   "note": "conductive adhesive, ~60x worse than bulk silver"},
    "graphite":      {"sigma": 1.00e5, "mu_r": 1.0,   "note": "pyrolytic, in-plane; ~600x worse than copper"},
    "carbon_paint":  {"sigma": 1.00e3, "mu_r": 1.0,   "note": "conductive paint/ink -- expect terrible efficiency"},
}

# Relative permittivity and loss tangent for the Phase 3 fulgurite/mould
# materials. A fulgurite is fused silica glass with inclusions, so it behaves
# as a low-loss dielectric, NOT as a conductor.
DIELECTRICS = {
    "vacuum":        {"eps_r": 1.0,  "tan_d": 0.0,     "note": "reference"},
    "fused_silica":  {"eps_r": 3.8,  "tan_d": 0.0001,  "note": "closest analogue to true fulgurite glass"},
    "soda_lime":     {"eps_r": 7.0,  "tan_d": 0.01,    "note": "common window/bottle glass, much lossier"},
    "quartz":        {"eps_r": 4.4,  "tan_d": 0.0001,  "note": "crystalline SiO2"},
    "dry_sand":      {"eps_r": 2.5,  "tan_d": 0.005,   "note": "loose, unfused feedstock"},
    "wet_sand":      {"eps_r": 20.0, "tan_d": 0.1,     "note": "water dominates; avoid, very lossy"},
    "pla":           {"eps_r": 2.7,  "tan_d": 0.005,   "note": "3D-printed jig/former"},
}


# ---------------------------------------------------------------------------
# Sine and cosine integrals
#
# Si(x) = int_0^x sin(t)/t dt
# Ci(x) = gamma + ln(x) + int_0^x (cos(t)-1)/t dt
#
# Power series below the crossover; above it the series loses too much to
# cancellation, so we evaluate the continued fraction for the complex
# exponential integral E1(ix) by the modified Lentz algorithm. Both branches
# reach near machine precision -- the rational approximations in A&S 5.2.38/9
# are only good to ~1e-4 here, which is enough to shift a computed radiation
# resistance by 0.1 ohm.
# ---------------------------------------------------------------------------

_SICI_CROSSOVER = 2.0
_SICI_MAXIT = 200
_SICI_EPS = 1e-16
_TINY = 1e-300


def _sici(x):
    """Return (Si(x), Ci(x)) for x > 0."""
    if x < _SICI_CROSSOVER:
        # Power series.
        s = 0.0
        term = x
        n = 0
        while True:
            contrib = term / (2 * n + 1)
            s += contrib
            if abs(contrib) < _SICI_EPS * max(abs(s), _TINY) or n > _SICI_MAXIT:
                break
            n += 1
            term *= -x * x / ((2 * n) * (2 * n + 1))

        c_sum = 0.0
        term = 1.0
        n = 0
        while True:
            n += 1
            term *= -x * x / ((2 * n - 1) * (2 * n))
            contrib = term / (2 * n)
            c_sum += contrib
            if abs(contrib) < _SICI_EPS * max(abs(c_sum), _TINY) or n > _SICI_MAXIT:
                break
        return s, GAMMA + math.log(x) + c_sum

    # Continued fraction for E1(ix), modified Lentz.
    b = complex(1.0, x)
    c = complex(1.0 / _TINY, 0.0)
    d = h = 1.0 / b
    for i in range(2, _SICI_MAXIT + 1):
        a = -((i - 1) ** 2)
        b += 2.0
        d = 1.0 / (a * d + b)
        c = b + a / c
        delta = c * d
        h *= delta
        if abs(delta.real - 1.0) + abs(delta.imag) < _SICI_EPS:
            break
    h = complex(math.cos(x), -math.sin(x)) * h
    return math.pi / 2.0 + h.imag, -h.real


def si(x):
    """Sine integral Si(x). Odd function."""
    if x < 0:
        return -si(-x)
    if x == 0.0:
        return 0.0
    return _sici(x)[0]


def ci(x):
    """Cosine integral Ci(x). Defined for x > 0."""
    if x <= 0:
        raise ValueError("ci(x) requires x > 0")
    return _sici(x)[1]


# ---------------------------------------------------------------------------
# Conductor loss
# ---------------------------------------------------------------------------

def skin_depth(freq_hz, material="copper"):
    """
    Skin depth in metres: delta = sqrt(rho / (pi * f * mu)).

    At 137 MHz copper is ~5.6 um, so anything thicker than ~30 um of copper is
    electrically solid and plating a cheap substrate works fine.
    """
    m = _conductor(material)
    mu = MU0 * m["mu_r"]
    return math.sqrt(1.0 / (math.pi * freq_hz * mu * m["sigma"]))


def surface_resistance(freq_hz, material="copper"):
    """Surface resistivity R_s = 1/(sigma*delta), in ohm per square."""
    m = _conductor(material)
    return 1.0 / (m["sigma"] * skin_depth(freq_hz, material))


def wire_ac_resistance(length_mm, diameter_mm, freq_hz, material="copper"):
    """
    AC resistance of a round wire carrying uniform current, in ohm.

    Uses the conducting-annulus area so the result degrades gracefully to the DC
    resistance when the skin depth exceeds the wire radius (thin wire / low
    frequency), instead of diverging like the bare R_s*L/(pi*d) form.
    """
    m = _conductor(material)
    radius = diameter_mm / 2000.0        # mm -> m
    length = length_mm / 1000.0
    if radius <= 0 or length <= 0:
        return 0.0
    delta = skin_depth(freq_hz, material)
    if delta >= radius:
        area = math.pi * radius * radius          # full cross-section
    else:
        inner = radius - delta
        area = math.pi * (radius * radius - inner * inner)
    return length / (m["sigma"] * area)


# Current-distribution weighting for referring distributed loss to the
# feedpoint. A half-wave dipole carries a sinusoidal current (mean square = 1/2
# of peak); an electrically short dipole carries a near-triangular one (1/3).
CURRENT_FACTOR = {"sinusoidal": 0.5, "triangular": 1.0 / 3.0, "uniform": 1.0}


def loss_resistance_dipole(length_mm, diameter_mm, freq_hz,
                           material="copper", distribution="sinusoidal"):
    """
    Ohmic loss resistance referred to the current maximum, in ohm.

    R_loss = f_dist * R_ac(total conductor length)
    """
    if distribution not in CURRENT_FACTOR:
        raise ValueError(f"unknown distribution {distribution!r}")
    r_ac = wire_ac_resistance(length_mm, diameter_mm, freq_hz, material)
    return CURRENT_FACTOR[distribution] * r_ac


# ---------------------------------------------------------------------------
# Radiation resistance (induced-EMF method, thin-wire dipole)
# ---------------------------------------------------------------------------

def radiation_resistance(length_mm, freq_hz):
    """
    Radiation resistance of a centre-fed thin-wire dipole of total length l,
    referred to the CURRENT MAXIMUM, in ohm. Balanis eq. 4-70.

    Reproduces 73.08 ohm at l = lambda/2 and 198.95 ohm at l = lambda.
    """
    lam = C / freq_hz
    l = length_mm / 1000.0
    if l <= 0:
        return 0.0
    kl = 2.0 * math.pi * l / lam
    if kl < 1e-9:
        return 0.0
    term = (GAMMA + math.log(kl) - ci(kl)
            + 0.5 * math.sin(kl) * (si(2 * kl) - 2 * si(kl))
            + 0.5 * math.cos(kl) * (GAMMA + math.log(kl / 2.0)
                                    + ci(2 * kl) - 2 * ci(kl)))
    return ETA0 / (2.0 * math.pi) * term


def radiation_resistance_at_feed(length_mm, freq_hz):
    """
    Radiation resistance referred to the FEEDPOINT of a centre-fed dipole.

    R_in = R_max / sin^2(kl/2). This is the number that matters for matching.
    Diverges as l -> lambda (full-wave), where the feedpoint sits on a current
    null and the input impedance becomes very high; capped and flagged there.
    """
    lam = C / freq_hz
    kl = 2.0 * math.pi * (length_mm / 1000.0) / lam
    s = math.sin(kl / 2.0)
    if abs(s) < 1e-6:
        return float("inf")
    return radiation_resistance(length_mm, freq_hz) / (s * s)


def radiation_efficiency(r_rad, r_loss):
    """eta = R_rad / (R_rad + R_loss), dimensionless 0..1."""
    denom = r_rad + r_loss
    if denom <= 0:
        return 0.0
    return r_rad / denom


# ---------------------------------------------------------------------------
# Resonant length including wire-thickness end effect
# ---------------------------------------------------------------------------

def dipole_reactance(length_mm, diameter_mm, freq_hz):
    """
    Dipole reactance referred to the current maximum, in ohm (Balanis 4-70b).
    Unlike the resistance, this depends on wire radius -- which is exactly what
    produces the end effect.
    """
    lam = C / freq_hz
    l = length_mm / 1000.0
    a = diameter_mm / 2000.0
    if l <= 0 or a <= 0:
        return 0.0
    k = 2.0 * math.pi / lam
    kl = k * l
    arg = 2.0 * k * a * a / l
    return ETA0 / (4.0 * math.pi) * (
        2.0 * si(kl)
        + math.cos(kl) * (2.0 * si(kl) - si(2 * kl))
        - math.sin(kl) * (2.0 * ci(kl) - ci(2 * kl) - ci(arg))
    )


def resonant_length(freq_hz, diameter_mm, tol=1e-9):
    """
    Physical length (mm) of a straight dipole that is actually resonant (X = 0)
    at freq_hz, found by bisecting the induced-EMF reactance.

    This replaces the folklore "multiply by 0.95": the shortening factor falls
    out of the physics and tracks wire thickness. Valid for thin wires
    (length/diameter >~ 50); thicker wires drift from measurement.
    """
    lam_mm = C / freq_hz * 1000.0
    lo, hi = 0.30 * lam_mm, 0.55 * lam_mm
    f_lo = dipole_reactance(lo, diameter_mm, freq_hz)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        f_mid = dipole_reactance(mid, diameter_mm, freq_hz)
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
        if hi - lo < tol * lam_mm:
            break
    return 0.5 * (lo + hi)


def shortening_factor(freq_hz, diameter_mm):
    """Resonant length as a fraction of a free-space half wavelength."""
    lam_mm = C / freq_hz * 1000.0
    return resonant_length(freq_hz, diameter_mm) / (0.5 * lam_mm)


# ---------------------------------------------------------------------------
# Chu-Harrington / McLean fundamental bandwidth bound
# ---------------------------------------------------------------------------

def ka_value(radius_mm, freq_hz):
    """
    Electrical size ka, where a is the radius of the smallest sphere enclosing
    the whole antenna. ka < 0.5 is "electrically small" and the Chu bound bites.
    """
    lam_mm = C / freq_hz * 1000.0
    return 2.0 * math.pi * radius_mm / lam_mm


def chu_q_min(ka, efficiency=1.0):
    """
    McLean's exact lower bound on radiation Q for a linearly polarised antenna
    enclosed in a sphere of radius a:

        Q_min = eta * (1/(ka)^3 + 1/(ka))

    No geometry -- fractal, spiral or otherwise -- beats this. It is a
    consequence of the spherical-mode expansion outside the enclosing sphere,
    not of any particular antenna topology.

    The bound is only TIGHT for electrically small antennas (ka < 1). Above
    that it stays true but goes slack: it will happily report Q < 1 and a
    bandwidth near 100%, which says the size is not what limits you, not that
    the antenna is genuinely that broadband. Use chu_bound_is_tight() before
    quoting the number as a real ceiling.

    Reference: McLean, "A re-examination of the fundamental limits on the
    radiation Q of electrically small antennas", IEEE TAP 44(5), 1996.
    """
    if ka <= 0:
        return float("inf")
    return efficiency * (1.0 / (ka ** 3) + 1.0 / ka)


def chu_bound_is_tight(ka):
    """True when the antenna is electrically small enough for Chu to bind."""
    return ka < 1.0


def fractional_bandwidth(q, vswr=2.0):
    """
    Matched fractional bandwidth for a single-resonance antenna of quality
    factor Q, at a given VSWR limit:  FBW = (S-1)/(Q*sqrt(S)).
    """
    if q <= 0:
        return float("inf")
    return (vswr - 1.0) / (q * math.sqrt(vswr))


def max_bandwidth_hz(radius_mm, freq_hz, efficiency=1.0, vswr=2.0):
    """Best-case absolute bandwidth (Hz) permitted by the Chu bound."""
    ka = ka_value(radius_mm, freq_hz)
    q = chu_q_min(ka, efficiency)
    return fractional_bandwidth(q, vswr) * freq_hz


# ---------------------------------------------------------------------------
# Dielectric loading (Phase 3: fulgurite moulds, glass/metal hybrids)
# ---------------------------------------------------------------------------

def effective_permittivity(eps_r, fill_factor=0.5):
    """
    Effective relative permittivity seen by a conductor partially embedded in a
    dielectric. fill_factor is the fraction of the near field inside the
    dielectric: 1.0 fully embedded, ~0.5 for a conductor on a surface, 0 in air.

    A first-order mixing rule. Adequate for predicting the direction and rough
    size of the shift; not a substitute for a full-wave solve.
    """
    fill_factor = min(max(fill_factor, 0.0), 1.0)
    return 1.0 + fill_factor * (eps_r - 1.0)


def dielectric_shortening(eps_r, fill_factor=0.5):
    """
    Length scale factor from dielectric loading: 1/sqrt(eps_eff).

    Casting the fractal into fulgurite glass shrinks it, but the size win is
    paid for in bandwidth: the enclosing sphere shrinks too, so the Chu bound
    tightens. Loading is not free miniaturisation.
    """
    return 1.0 / math.sqrt(effective_permittivity(eps_r, fill_factor))


def dielectric_loss_q(tan_d):
    """Q ceiling imposed by dielectric loss alone: Q_d = 1/tan(delta)."""
    if tan_d <= 0:
        return float("inf")
    return 1.0 / tan_d


# ---------------------------------------------------------------------------
# Impedance match
# ---------------------------------------------------------------------------

def reflection_coefficient(z_load_real, z_load_imag=0.0, z0=50.0):
    """Complex reflection coefficient magnitude |Gamma| into a real z0."""
    num_r = z_load_real - z0
    den_r = z_load_real + z0
    num = math.hypot(num_r, z_load_imag)
    den = math.hypot(den_r, z_load_imag)
    if den == 0:
        return 1.0
    return num / den


def vswr(gamma_mag):
    """Voltage standing wave ratio from |Gamma|."""
    if gamma_mag >= 1.0:
        return float("inf")
    return (1.0 + gamma_mag) / (1.0 - gamma_mag)


def return_loss_db(gamma_mag):
    """Return loss in dB (positive number). S11 = -return_loss."""
    if gamma_mag <= 0:
        return float("inf")
    return -20.0 * math.log10(gamma_mag)


def mismatch_loss_db(gamma_mag):
    """Power lost to reflection, in dB."""
    transmitted = 1.0 - gamma_mag * gamma_mag
    if transmitted <= 0:
        return float("inf")
    return -10.0 * math.log10(transmitted)


def polarization_loss_db(mode="linear_to_circular"):
    """
    Polarisation mismatch loss.

    NOAA APT downlinks are right-hand circularly polarised, so any linear
    antenna -- fractal or dipole -- gives up 3 dB before anything else happens.
    Both antennas under test lose it equally, so it cancels in a comparison but
    must be in an absolute link budget.
    """
    table = {
        "matched": 0.0,
        "linear_to_circular": 3.0,
        "circular_opposite_sense": float("inf"),
        "linear_45deg": 3.0,
        "linear_orthogonal": float("inf"),
    }
    if mode not in table:
        raise ValueError(f"unknown polarisation mode {mode!r}")
    return table[mode]


# ---------------------------------------------------------------------------
# External noise and real sensitivity
# ---------------------------------------------------------------------------

# The ITU galactic expression is a straight line in log-frequency, and it hits
# Fam = 0 dB (zero excess sky temperature) at 10^(52/23) = 182 MHz, going
# negative above that. That is not a physical prediction, just the edge of the
# range where galactic noise dominates. Past the limit we fall back to a floor
# representing the cosmic microwave background plus atmospheric emission.
#
# Real installations sit well above this floor thanks to ground pickup and
# man-made noise, neither of which this model attempts to predict. Treat the
# floor as "the sky contributes nothing you can rely on here", not as a
# measurement.
GALACTIC_MODEL_MIN_MHZ = 20.0
GALACTIC_MODEL_MAX_MHZ = 182.0   # where 52 - 23*log10(f) reaches 0 dB
T_SKY_FLOOR_K = 5.0


def galactic_model_valid(freq_hz):
    """True when freq_hz is inside the ITU-R P.372 galactic model's range."""
    f_mhz = freq_hz / 1e6
    return GALACTIC_MODEL_MIN_MHZ <= f_mhz <= GALACTIC_MODEL_MAX_MHZ


def galactic_noise_figure_db(freq_hz):
    """
    Median galactic noise figure above the thermal floor:

        Fam = 52 - 23*log10(f_MHz)      [dB]

    Recommendation ITU-R P.372, for a short vertical monopole neglecting
    ionospheric shielding. Decile deviation about 2 dB. Meant for the range
    where galactic noise dominates (taken here as 20-400 MHz); outside it the
    expression is extrapolation and callers should check galactic_model_valid().
    """
    f_mhz = freq_hz / 1e6
    if f_mhz <= 0:
        return 0.0
    return 52.0 - 23.0 * math.log10(f_mhz)


def galactic_noise_temperature(freq_hz):
    """
    External sky brightness temperature (K) from the ITU-R P.372 median,
    floored at the CMB-plus-atmosphere background so it never goes negative
    when the straight-line fit is extrapolated upward in frequency.
    """
    fam_db = galactic_noise_figure_db(freq_hz)
    t = T0 * (10.0 ** (fam_db / 10.0) - 1.0)
    return max(t, T_SKY_FLOOR_K)


def antenna_noise_temperature(t_external, efficiency, t_physical=290.0):
    """
    Noise temperature at the antenna terminals:

        T_A = eta*T_ext + (1-eta)*T_phys

    Ohmic loss does two things at once: it attenuates the wanted signal AND
    injects thermal noise at the conductor's physical temperature. That second
    half is why "efficiency" alone does not predict sensitivity.
    """
    return efficiency * t_external + (1.0 - efficiency) * t_physical


def noise_figure_to_temperature(nf_db):
    """Receiver noise figure (dB) -> equivalent noise temperature (K)."""
    return T0 * (10.0 ** (nf_db / 10.0) - 1.0)


def sensitivity_penalty_db(efficiency, freq_hz, rx_nf_db=6.0, t_physical=290.0):
    """
    Actual SNR penalty (dB, negative = worse) of a lossy antenna relative to a
    lossless one at the same frequency, accounting for external noise.

    SNR ~ eta / (eta*T_ext + (1-eta)*T_phys + T_rx)

    This is the honest figure of merit. When the sky is much hotter than the
    hardware -- true at HF and low VHF -- a badly inefficient antenna costs far
    less than its efficiency suggests, because the sky noise is attenuated
    alongside the signal. When the sky is cool relative to the receiver, as at
    137 MHz with a bare RTL-SDR, the penalty tracks efficiency almost 1:1.
    """
    if efficiency <= 0:
        return float("-inf")
    t_ext = galactic_noise_temperature(freq_hz)
    t_rx = noise_figure_to_temperature(rx_nf_db)
    t_sys_lossy = antenna_noise_temperature(t_ext, efficiency, t_physical) + t_rx
    t_sys_ideal = t_ext + t_rx
    return 10.0 * math.log10((efficiency / t_sys_lossy) / (1.0 / t_sys_ideal))


def external_noise_limited(freq_hz, rx_nf_db=6.0, margin_db=6.0):
    """
    True when external (galactic) noise exceeds receiver noise by margin_db, so
    the receiver's own noise no longer sets the floor. Determines whether
    antenna losses are cheap or expensive.
    """
    t_ext = galactic_noise_temperature(freq_hz)
    t_rx = noise_figure_to_temperature(rx_nf_db)
    if t_rx <= 0:
        return True
    if t_ext <= 0:
        return False
    return 10.0 * math.log10(t_ext / t_rx) >= margin_db


# ---------------------------------------------------------------------------
# Link budget
# ---------------------------------------------------------------------------

def free_space_path_loss_db(distance_m, freq_hz):
    """FSPL = 20log10(4*pi*d/lambda), in dB."""
    if distance_m <= 0:
        return 0.0
    lam = C / freq_hz
    return 20.0 * math.log10(4.0 * math.pi * distance_m / lam)


def effective_aperture(gain_dbi, freq_hz):
    """Effective aperture in m^2: A_e = G*lambda^2/(4*pi)."""
    lam = C / freq_hz
    return (10.0 ** (gain_dbi / 10.0)) * lam * lam / (4.0 * math.pi)


def noise_power_dbm(t_sys, bandwidth_hz):
    """Thermal noise power in dBm for a system temperature and bandwidth."""
    watts = K_B * t_sys * bandwidth_hz
    return 10.0 * math.log10(watts * 1000.0)


def _conductor(name):
    if name not in CONDUCTORS:
        raise ValueError(
            f"unknown conductor {name!r}; choose from {', '.join(sorted(CONDUCTORS))}")
    return CONDUCTORS[name]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def analyze_conductor(freq_hz, length_mm, diameter_mm, material="copper",
                      enclosing_radius_mm=None, z0=50.0, rx_nf_db=6.0):
    """Full physical analysis of one conductor at one frequency."""
    lam_mm = C / freq_hz * 1000.0
    r_rad = radiation_resistance(length_mm, freq_hz)
    r_loss = loss_resistance_dipole(length_mm, diameter_mm, freq_hz, material)
    eta = radiation_efficiency(r_rad, r_loss)
    if enclosing_radius_mm is None:
        enclosing_radius_mm = length_mm / 2.0
    ka = ka_value(enclosing_radius_mm, freq_hz)
    q_min = chu_q_min(ka, eta)
    r_in = radiation_resistance_at_feed(length_mm, freq_hz)
    gamma = reflection_coefficient(r_in if math.isfinite(r_in) else 1e9, 0.0, z0)
    t_ext = galactic_noise_temperature(freq_hz)
    return {
        "freq_hz": freq_hz,
        "wavelength_mm": lam_mm,
        "length_mm": length_mm,
        "length_over_lambda": length_mm / lam_mm,
        "material": material,
        "skin_depth_um": skin_depth(freq_hz, material) * 1e6,
        "surface_resistance_ohm": surface_resistance(freq_hz, material),
        "r_rad_ohm": r_rad,
        "r_loss_ohm": r_loss,
        "efficiency": eta,
        "efficiency_db": 10.0 * math.log10(eta) if eta > 0 else float("-inf"),
        "r_in_ohm": r_in,
        "vswr": vswr(gamma),
        "mismatch_loss_db": mismatch_loss_db(gamma),
        "ka": ka,
        "q_min": q_min,
        "max_fbw_pct": fractional_bandwidth(q_min) * 100.0,
        "max_bw_hz": fractional_bandwidth(q_min) * freq_hz,
        "t_sky_k": t_ext,
        "t_antenna_k": antenna_noise_temperature(t_ext, eta),
        "ext_noise_limited": external_noise_limited(freq_hz, rx_nf_db),
        "sensitivity_penalty_db": sensitivity_penalty_db(eta, freq_hz, rx_nf_db),
        "resonant_length_mm": resonant_length(freq_hz, diameter_mm),
        "shortening_factor": shortening_factor(freq_hz, diameter_mm),
    }


def print_analysis(a):
    """Print a conductor analysis report."""
    print("=" * 66)
    print("CONDUCTOR PHYSICS ANALYSIS")
    print("=" * 66)
    print(f"  Frequency:            {a['freq_hz'] / 1e6:.3f} MHz")
    print(f"  Wavelength:           {a['wavelength_mm']:.1f} mm")
    print(f"  Conductor length:     {a['length_mm']:.1f} mm "
          f"({a['length_over_lambda']:.3f} lambda)")
    print(f"  Material:             {a['material']} "
          f"({CONDUCTORS[a['material']]['note']})")

    print("\n--- Conductor loss ---")
    print(f"  Skin depth:           {a['skin_depth_um']:.2f} um")
    print(f"  Surface resistance:   {a['surface_resistance_ohm'] * 1000:.3f} milliohm/square")
    print(f"  Radiation resistance: {a['r_rad_ohm']:.3f} ohm")
    print(f"  Loss resistance:      {a['r_loss_ohm']:.3f} ohm")
    print(f"  Radiation efficiency: {a['efficiency'] * 100:.2f} %  "
          f"({a['efficiency_db']:.2f} dB)")

    print("\n--- Match (into 50 ohm, reactance not tuned out) ---")
    r_in = a["r_in_ohm"]
    print(f"  Feedpoint resistance: "
          f"{'very high (current null)' if not math.isfinite(r_in) else f'{r_in:.1f} ohm'}")
    print(f"  VSWR:                 {a['vswr']:.2f}")
    print(f"  Mismatch loss:        {a['mismatch_loss_db']:.2f} dB")

    print("\n--- Fundamental size/bandwidth bound (Chu-Harrington/McLean) ---")
    print(f"  ka:                   {a['ka']:.3f}"
          f"{'  [electrically small]' if a['ka'] < 0.5 else ''}")
    print(f"  Minimum Q:            {a['q_min']:.1f}")
    print(f"  Max bandwidth:        {a['max_fbw_pct']:.2f} % "
          f"({a['max_bw_hz'] / 1e6:.3f} MHz at VSWR 2)")
    if chu_bound_is_tight(a["ka"]):
        print("  No geometry beats this bound. Fractal branching buys you a longer")
        print("  conductor inside the same sphere -- it does not enlarge the sphere.")
    else:
        print("  ka > 1, so this bound is slack: size is not what limits this")
        print("  antenna. The number is still a valid ceiling, but do not quote")
        print("  it as a predicted bandwidth.")

    print("\n--- Straight-dipole reference at this frequency ---")
    print(f"  Resonant length:      {a['resonant_length_mm']:.1f} mm "
          f"(k = {a['shortening_factor']:.4f} of lambda/2)")

    print("\n--- Noise and real sensitivity ---")
    print(f"  Sky temperature:      {a['t_sky_k']:.0f} K (ITU-R P.372 median)")
    print(f"  Antenna temperature:  {a['t_antenna_k']:.0f} K")
    print(f"  External-noise limited: {'YES' if a['ext_noise_limited'] else 'NO'}")
    print(f"  SNR penalty vs lossless: {a['sensitivity_penalty_db']:.2f} dB")
    if a["ext_noise_limited"]:
        print("  Sky noise dominates, so ohmic loss is partly free: the loss")
        print("  attenuates signal and sky noise together.")
    else:
        print("  Receiver noise dominates, so ohmic loss costs nearly 1:1.")
        print("  A low-noise preamp at the feedpoint buys more than any")
        print("  geometry change here.")
    print()


def print_materials():
    """Print the material tables with RF-relevant derived values."""
    ref_f = 137.1e6
    print("=" * 78)
    print(f"CONDUCTORS (derived values at {ref_f / 1e6:.1f} MHz)")
    print("=" * 78)
    print(f"{'name':<15}{'sigma S/m':>12}{'mu_r':>7}{'skin um':>10}{'Rs mohm/sq':>13}")
    print("-" * 78)
    for name in sorted(CONDUCTORS, key=lambda n: -CONDUCTORS[n]["sigma"]):
        d = skin_depth(ref_f, name) * 1e6
        rs = surface_resistance(ref_f, name) * 1000
        m = CONDUCTORS[name]
        print(f"{name:<15}{m['sigma']:>12.2e}{m['mu_r']:>7.0f}{d:>10.2f}{rs:>13.3f}")
        print(f"{'':<15}{m['note']}")
    print()
    print("=" * 78)
    print("DIELECTRICS (Phase 3 moulds and formers)")
    print("=" * 78)
    print(f"{'name':<16}{'eps_r':>8}{'tan_d':>10}{'shrink@50%':>12}{'Q_diel':>10}")
    print("-" * 78)
    for name, d in DIELECTRICS.items():
        shrink = dielectric_shortening(d["eps_r"], 0.5)
        qd = dielectric_loss_q(d["tan_d"])
        qs = "inf" if math.isinf(qd) else f"{qd:.0f}"
        print(f"{name:<16}{d['eps_r']:>8.1f}{d['tan_d']:>10.4f}"
              f"{shrink:>12.3f}{qs:>10}")
        print(f"{'':<16}{d['note']}")
    print()


def noise_sweep():
    """
    Show where ohmic loss is cheap and where it is expensive across the bands
    this project cares about.
    """
    print("=" * 78)
    print("SNR PENALTY OF A LOSSY ANTENNA vs FREQUENCY AND EFFICIENCY")
    print("=" * 78)
    print("Penalty in dB relative to a lossless antenna, bare RTL-SDR (NF 6 dB).")
    print("Naive expectation would be 10*log10(eta): -3, -10, -20 dB.\n")
    effs = [0.5, 0.1, 0.01]
    print(f"{'freq':>10}{'T_sky K':>10}{'ext-lim':>9}"
          + "".join(f"{'eta=' + str(e):>11}" for e in effs))
    print("-" * 78)
    for f_mhz in [10, 30, 50, 100, 137.1, 162.55, 300, 433, 915, 1090, 1575.42]:
        f = f_mhz * 1e6
        t = galactic_noise_temperature(f)
        lim = "yes" if external_noise_limited(f) else "no"
        flag = "" if galactic_model_valid(f) else " *"
        row = f"{f_mhz:>9.1f}M{t:>10.0f}{lim:>9}"
        for e in effs:
            row += f"{sensitivity_penalty_db(e, f):>11.2f}"
        print(row + flag)
    print("\n  * outside the ITU-R P.372 galactic range "
          f"({GALACTIC_MODEL_MIN_MHZ:.0f}-{GALACTIC_MODEL_MAX_MHZ:.0f} MHz); "
          f"sky floored at {T_SKY_FLOOR_K:.0f} K")
    print("\nAt 10-30 MHz the sky is thousands of kelvin, so a 1%-efficient")
    print("antenna is only a few dB worse than a perfect one -- the loss")
    print("attenuates the sky noise right along with the signal. By 137 MHz the")
    print("sky has cooled to a few hundred kelvin and the penalty converges on")
    print("the naive 10*log10(eta). This is the single most important number")
    print("for this project: at the NOAA band there is no free lunch, so a")
    print("fractal that trades efficiency for size pays full price.")
    print()


# ---------------------------------------------------------------------------
# Self-test against published values
# ---------------------------------------------------------------------------

def self_test():
    """Validate the implementation against textbook and handbook numbers."""
    checks = []

    def check(name, got, want, tol, unit=""):
        ok = abs(got - want) <= tol
        checks.append(ok)
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name:<46} got {got:>12.5f}{unit}  "
              f"want {want:g}{unit} +/-{tol:g}")

    print("=" * 78)
    print("SELF-TEST: validating against published values")
    print("=" * 78)

    print("\nSine/cosine integrals (vs known values):")
    check("Si(1)", si(1.0), 0.946083070367, 1e-6)
    check("Si(pi)", si(math.pi), 1.851937051982, 1e-6)
    check("Si(10)", si(10.0), 1.658347594218, 1e-5)
    check("Si(-2)", si(-2.0), -1.605412976802, 1e-6)
    check("Ci(1)", ci(1.0), 0.337403922901, 1e-6)
    check("Ci(10)", ci(10.0), -0.045456433004, 1e-5)
    check("Si(inf) limit ~ pi/2", si(1e6), math.pi / 2, 1e-5)

    print("\nRadiation resistance (Balanis, Kraus):")
    # Pick f so that lambda is exactly 1000 mm; at a round 300 MHz lambda is
    # 999.31 mm and a 500 mm wire is 0.5003 lambda, which shifts R_rad by 0.15 ohm.
    f = C                          # lambda = 1.000 m exactly
    # At kl = pi the general expression collapses to (eta/4pi)*Cin(2pi).
    # Textbooks quote 73.13 ohm by rounding eta/4pi to exactly 30; carrying the
    # exact eta gives 73.08, so that is what we assert against.
    check("half-wave dipole R_rad", radiation_resistance(500.0, f), 73.08, 0.02, " ohm")
    check("  == (eta/4pi)*Cin(2pi) identity", radiation_resistance(500.0, f),
          (ETA0 / (4 * math.pi)) * (GAMMA + math.log(2 * math.pi) - ci(2 * math.pi)),
          1e-9, " ohm")
    check("full-wave dipole R_rad", radiation_resistance(1000.0, f), 198.95, 0.05, " ohm")
    for frac in (0.1, 0.05, 0.02):
        got = radiation_resistance_at_feed(frac * 1000.0, f)
        want = 20 * math.pi ** 2 * frac ** 2
        check(f"short dipole l={frac}lambda vs 20pi^2(l/lam)^2",
              got, want, 0.02 * want, " ohm")

    print("\nSkin depth (handbook):")
    check("copper @ 137.1 MHz", skin_depth(137.1e6, "copper") * 1e6, 5.60, 0.10, " um")
    check("copper @ 1 GHz", skin_depth(1e9, "copper") * 1e6, 2.07, 0.05, " um")
    check("aluminum @ 137.1 MHz", skin_depth(137.1e6, "aluminum") * 1e6, 6.95, 0.15, " um")

    print("\nChu-Harrington / McLean bound:")
    check("Q_min at ka=0.5", chu_q_min(0.5), 10.0, 1e-9)
    check("Q_min at ka=1.0", chu_q_min(1.0), 2.0, 1e-9)
    check("Q_min at ka=0.1", chu_q_min(0.1), 1010.0, 1e-6)
    check("FBW at Q=10, VSWR 2", fractional_bandwidth(10.0, 2.0) * 100, 7.071, 1e-3, " %")

    print("\nEnd effect / shortening factor (ARRL dipole k-factor curve):")
    check("L/d = 1000", shortening_factor(f, 500.0 / 1000.0), 0.965, 0.010)
    check("L/d = 100", shortening_factor(f, 500.0 / 100.0), 0.945, 0.012)
    check("L/d = 10000", shortening_factor(f, 500.0 / 10000.0), 0.976, 0.010)

    print("\nMatch arithmetic:")
    check("VSWR of 50 ohm into 50 ohm", vswr(reflection_coefficient(50.0)), 1.0, 1e-9)
    check("VSWR of 100 ohm into 50 ohm", vswr(reflection_coefficient(100.0)), 2.0, 1e-9)
    check("VSWR of 73 ohm into 50 ohm", vswr(reflection_coefficient(73.0)), 1.46, 0.01)
    check("mismatch loss at VSWR 2", mismatch_loss_db(1.0 / 3.0), 0.5115, 1e-3, " dB")

    print("\nNoise (ITU-R P.372):")
    check("Fam at 100 MHz", galactic_noise_figure_db(100e6), 6.0, 0.01, " dB")
    check("Fam at 137.1 MHz", galactic_noise_figure_db(137.1e6), 2.85, 0.05, " dB")
    check("NF 3 dB -> T", noise_figure_to_temperature(3.0), 288.6, 1.0, " K")
    check("NF 0 dB -> T", noise_figure_to_temperature(0.0), 0.0, 1e-9, " K")

    print("\nLink budget:")
    check("FSPL 1 km @ 137.1 MHz", free_space_path_loss_db(1000.0, 137.1e6),
          75.18, 0.05, " dB")
    check("aperture of 0 dBi @ 137.1 MHz",
          effective_aperture(0.0, 137.1e6), 0.3805, 0.001, " m^2")
    check("kTB, 290 K, 1 Hz", noise_power_dbm(290.0, 1.0), -173.98, 0.05, " dBm")

    print("\nSanity: lossless antenna has zero penalty")
    check("penalty at eta=1", sensitivity_penalty_db(1.0, 137.1e6), 0.0, 1e-9, " dB")

    passed = sum(1 for c in checks if c)
    total = len(checks)
    print("\n" + "=" * 78)
    print(f"RESULT: {passed}/{total} checks passed")
    print("=" * 78)
    return passed == total


def main():
    parser = argparse.ArgumentParser(
        description="Antenna physics: loss, efficiency, bandwidth bounds, noise")
    parser.add_argument("--freq", type=float, default=137.1e6,
                        help="Frequency in Hz (default: 137.1e6, NOAA APT)")
    parser.add_argument("--length", type=float, default=1000.0,
                        help="Conductor length in mm (default: 1000)")
    parser.add_argument("--diameter", type=float, default=1.0,
                        help="Wire diameter in mm (default: 1.0)")
    parser.add_argument("--material", type=str, default="copper",
                        choices=sorted(CONDUCTORS), help="Conductor material")
    parser.add_argument("--enclosing-radius", type=float, default=None,
                        help="Radius of smallest enclosing sphere in mm "
                             "(default: length/2). Use the fractal's bounding "
                             "radius to get a meaningful Chu bound.")
    parser.add_argument("--z0", type=float, default=50.0,
                        help="System impedance in ohm (default: 50)")
    parser.add_argument("--rx-nf", type=float, default=6.0,
                        help="Receiver noise figure in dB (default: 6, bare RTL-SDR)")
    parser.add_argument("--self-test", action="store_true",
                        help="Validate against published values and exit")
    parser.add_argument("--materials", action="store_true",
                        help="Print material tables and exit")
    parser.add_argument("--noise-sweep", action="store_true",
                        help="Print the loss-vs-frequency noise study and exit")
    args = parser.parse_args()

    if args.self_test:
        raise SystemExit(0 if self_test() else 1)
    if args.materials:
        print_materials()
        return
    if args.noise_sweep:
        noise_sweep()
        return

    analysis = analyze_conductor(
        freq_hz=args.freq,
        length_mm=args.length,
        diameter_mm=args.diameter,
        material=args.material,
        enclosing_radius_mm=args.enclosing_radius,
        z0=args.z0,
        rx_nf_db=args.rx_nf,
    )
    print_analysis(analysis)


if __name__ == "__main__":
    main()
