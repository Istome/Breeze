"""Synthetic hourly year (8760 h) built from the monthly normals in
breeze.climate_year, with day-to-day weather noise, cloudy/clear days and an
explicit design heat wave.  Precomputes everything the hourly simulator needs:
air and wet-bulb temperature, wind, horizontal sun, and the infrared sky
irradiance seen by an upward- or downward-facing surface (two-band model).

Design extremes (approximate, for sizing only):
  hot-dry 46 C, hot-humid 39 C, arid 47 C peak dry-bulb.
"""
from __future__ import annotations

import numpy as np

from ..climate_year import SITES, MONTH_DOY, DAYS
from ..physics import SIGMA, _planck_band_fraction, WINDOW
from ..psychro import wet_bulb, sky_emissivity_berdahl
from ..physics import Climate

EXTREME = {"hot-dry": (46.0, 32.0, 14.0), "hot-humid": (39.0, 28.0, 24.0), "arid": (47.0, 33.0, 4.0)}  # Tmax, Tmin, Tdp

# ---- tables -------------------------------------------------------------
_TG = np.linspace(230, 400, 171)
_FW = np.array([_planck_band_fraction(t, *WINDOW, n=1500) for t in _TG])


def frac_window(T):
    return np.interp(T, _TG, _FW)


def band_E(T):
    E = SIGMA * np.asarray(T, float) ** 4
    f = frac_window(T)
    return f * E, (1 - f) * E


_TAU = np.linspace(1e-3, 0.999, 120)
_MU = np.linspace(1e-4, 1, 2000)
_TAUBAR = np.array([2 * np.trapezoid(t ** (1 / _MU) * _MU, _MU) for t in _TAU])  # cos-weighted hemispherical
_EPS = np.array([Climate(T_amb=300.0, tau0=t).sky_emissivity() for t in _TAU[::6]])
_EPS = np.interp(_TAU, _TAU[::6], _EPS)


def tau0_from_eps(eps):
    """Invert eps_sky(tau0) (monotonic decreasing)."""
    return np.interp(-np.asarray(eps), -_EPS, _TAU)


def taubar(tau0):
    return np.interp(tau0, _TAU, _TAUBAR)


# ---- year ---------------------------------------------------------------
def _periodic_interp(day, xs, ys):
    xs = np.concatenate([xs - 365, xs, xs + 365])
    ys = np.concatenate([ys, ys, ys])
    return np.interp(day, xs, ys)


def make_year(site, seed=7, heatwave=True, warming=0.0):
    rng = np.random.default_rng(seed)
    S = SITES[site]
    days = np.arange(365) + 0.5
    Tmax = _periodic_interp(days, MONTH_DOY, S["Tmax"] - 273.15)
    Tmin = _periodic_interp(days, MONTH_DOY, S["Tmin"] - 273.15)
    Tdp = _periodic_interp(days, MONTH_DOY, S["Tdp"] - 273.15)
    cloudf = _periodic_interp(days, MONTH_DOY, S["cloud"])
    a = np.zeros(365)
    for d in range(1, 365):
        a[d] = 0.7 * a[d - 1] + rng.normal(0, 1.8)
    Tmax, Tmin = Tmax + a + warming, Tmin + 0.8 * a + warming
    Tdp = Tdp + rng.normal(0, 1.5, 365)
    cloudy = rng.random(365) < cloudf
    cover = np.where(cloudy, rng.uniform(0.5, 0.9, 365), rng.uniform(0.0, 0.15, 365))
    if heatwave:
        hx, hn, hd = EXTREME[site]
        mid = 196  # mid July
        for k, d in enumerate(range(mid - 2, mid + 2)):
            Tmax[d] = hx + warming - (0.6 if k in (0, 3) else 0.0)
            Tmin[d] = hn + warming
            Tdp[d] = hd
            cover[d] = 0.05
    # hourly
    hour = np.arange(8760) % 24 + 0.5
    day = np.arange(8760) // 24
    tmin_h, tmax_h = Tmin[day], Tmax[day]
    rise = (hour >= 5) & (hour <= 15)
    xr = (hour - 5) / 10
    xf = ((hour - 15) % 24) / 14
    T = np.where(rise, tmin_h + (tmax_h - tmin_h) * (1 - np.cos(np.pi * xr)) / 2,
                 tmax_h - (tmax_h - tmin_h) * (1 - np.cos(np.pi * xf)) / 2)
    Td = np.minimum(Tdp[day], T - 0.5)
    c = cover[day]
    wind = np.clip(2.2 + 1.3 * np.sin(2 * np.pi * (hour - 9) / 24) + rng.normal(0, 0.6, 8760), 0.4, None)
    # sun
    lat = np.radians(S["lat"])
    doy = day + 1
    decl = np.radians(23.45) * np.sin(2 * np.pi * (284 + doy) / 365)
    hra = np.radians(15 * (hour - 12))
    sin_el = np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.cos(hra)
    el = np.arcsin(np.clip(sin_el, -1, 1))
    am = 1 / np.clip(np.sin(el), 1e-3, 1)
    dni = np.where(el > 0, 1361 * 0.7 ** (am ** 0.678), 0.0)
    dhi = np.where(el > 0, 0.11 * dni * np.sin(el) + 15 * np.sin(el), 0.0)
    G = (dni * np.clip(sin_el, 0, None) * (1 - 0.75 * c) + dhi * (1 + 0.6 * c))
    # sky
    eps = sky_emissivity_berdahl(Td + 273.15, hour=hour, cloud=c)
    tb = taubar(tau0_from_eps(eps))
    TK = T + 273.15
    EW, ENW = band_E(TK)
    G_ir_W = EW * (1 - tb)          # window-band irradiance on an upward face
    G_ir_NW = ENW
    # wet bulb (vectorised via psychrometric approximation, Stull 2011)
    RH = np.clip(100 * np.exp(17.625 * Td / (243.04 + Td)) / np.exp(17.625 * T / (243.04 + T)), 1, 100)
    Twb = (T * np.arctan(0.151977 * np.sqrt(RH + 8.313659)) + np.arctan(T + RH) - np.arctan(RH - 1.676331)
           + 0.00391838 * RH ** 1.5 * np.arctan(0.023101 * RH) - 4.686035)
    return dict(site=site, T=T, Td=Td, Twb=Twb, RH=RH, wind=wind, G=G, cover=c, eps_sky=eps,
                G_ir_W=G_ir_W, G_ir_NW=G_ir_NW, hour=hour, day=day, T_soil10=None)
