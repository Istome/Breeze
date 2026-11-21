"""Psychrometrics + humidity-dependent clear/cloudy sky (for the evaporation and
annual studies).  SI units, temperatures in K unless stated."""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

P_ATM = 101325.0
CP_AIR = 1006.0
H_FG = 2.45e6


def p_sat(T):
    """Saturation vapour pressure over water (Pa), Buck (1981)."""
    t = np.asarray(T, float) - 273.15
    return 611.21 * np.exp((18.678 - t / 234.5) * (t / (257.14 + t)))


def w_from_pv(pv):
    return 0.622 * pv / (P_ATM - pv)


def w_sat(T):
    return w_from_pv(p_sat(T))


def wet_bulb(T, T_dp):
    """Thermodynamic wet-bulb temperature from dry-bulb and dew point (K)."""
    w = w_sat(T_dp)

    def f(Tw):
        ws = w_sat(Tw)
        return ((2501 - 2.326 * (Tw - 273.15)) * ws - 1.006 * (T - Tw)) / (2501 + 1.86 * (T - 273.15) - 4.186 * (Tw - 273.15)) - w

    return brentq(f, T_dp - 1, T + 0.01)


def sky_emissivity_berdahl(T_dp, hour=None, cloud=0.0, C=0.6):
    """Berdahl & Martin (1984) clear-sky emissivity from dew point, with a
    simple cloud correction eps = eps_c + C*(1-eps_c)*n (C~0.6 mixed cloud heights)."""
    td = np.asarray(T_dp, float) - 273.15
    eps = 0.711 + 0.56 * (td / 100) + 0.73 * (td / 100) ** 2
    if hour is not None:
        eps += 0.013 * np.cos(2 * np.pi * hour / 24)
    return eps + C * (1 - eps) * cloud


_tau_cache = {}


def tau0_for_emissivity(eps_target, T_amb=298.15):
    """Invert the two-band model: window zenith transmittance giving eps_target."""
    from .physics import Climate
    key = (round(float(eps_target), 4), round(T_amb))
    if key not in _tau_cache:
        f = lambda t: Climate(T_amb=T_amb, tau0=t).sky_emissivity() - eps_target
        lo, hi = f(1e-4), f(0.999)
        if lo < 0:
            _tau_cache[key] = 1e-4  # sky darker than the model can reach: window closed
        elif hi > 0:
            _tau_cache[key] = 0.999
        else:
            _tau_cache[key] = brentq(f, 1e-4, 0.999, xtol=1e-4)
    return _tau_cache[key]
