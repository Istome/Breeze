"""Radiation physics: two-band IR model, angular sky model, clear-sky solar.

Band model
----------
The thermal IR is split into the atmospheric window W = 8-13 um, where a clear
atmosphere is partly transparent to the 3 K universe, and everything else (NW),
where the lower atmosphere is optically thick and radiates like a blackbody at
roughly ambient temperature.

Directional window transmittance follows Beer-Lambert through a plane-parallel
atmosphere:  tau(theta) = tau0 ** (1 / cos(theta)).  This is what makes the
zenith cold and the horizon warm, and it is the central fact behind the geometry.
"""
from __future__ import annotations

import numpy as np

SIGMA = 5.670374419e-8
H = 6.62607015e-34
C = 2.99792458e8
KB = 1.380649e-23
WINDOW = (8e-6, 13e-6)


def _planck_band_fraction(T: float, l1: float, l2: float, n: int = 4000) -> float:
    lam = np.linspace(l1, l2, n)
    B = 2 * H * C**2 / lam**5 / np.expm1(H * C / (lam * KB * T))
    return float(np.pi * np.trapezoid(B, lam) / (SIGMA * T**4))


def band_emissive_power(T):
    """Return (E_W, E_NW) hemispherical blackbody emissive power in W/m^2."""
    T = np.atleast_1d(np.asarray(T, float))
    fW = np.array([_planck_band_fraction(t, *WINDOW) for t in T])
    E = SIGMA * T**4
    out = (fW * E, (1 - fW) * E)
    return (out[0][0], out[1][0]) if out[0].size == 1 else out


# ---------------------------------------------------------------- directions
def hemisphere_quadrature(n_theta: int = 90, n_phi: int = 180):
    """Midpoint quadrature over the full sphere. Returns unit dirs (N,3) and dOmega (N,)."""
    th = (np.arange(n_theta * 2) + 0.5) * np.pi / (2 * n_theta)
    ph = (np.arange(n_phi) + 0.5) * 2 * np.pi / n_phi
    TH, PH = np.meshgrid(th, ph, indexing="ij")
    d = np.stack([np.sin(TH) * np.cos(PH), np.sin(TH) * np.sin(PH), np.cos(TH)], -1).reshape(-1, 3)
    dO = (np.sin(TH) * (np.pi / (2 * n_theta)) * (2 * np.pi / n_phi)).ravel()
    return d, dO


class Climate:
    """Ambient conditions. z-axis is up, +y is north, +x is east."""

    def __init__(self, T_amb=303.15, tau0=0.75, T_ground=None, albedo=0.25,
                 lat_deg=33.45, name="hot-dry"):
        self.T_amb = T_amb
        self.tau0 = tau0
        self.T_ground = T_amb if T_ground is None else T_ground
        self.albedo = albedo
        self.lat = np.radians(lat_deg)
        self.name = name

    # band radiances arriving FROM direction d (d points away from surface, toward source)
    def env_radiance(self, d):
        d = np.atleast_2d(d)
        EW_a, ENW_a = band_emissive_power(self.T_amb)
        EW_g, ENW_g = band_emissive_power(self.T_ground)
        up = d[:, 2] > 1e-9
        cz = np.clip(d[:, 2], 1e-9, 1)
        tau = np.where(up, self.tau0 ** (1 / cz), 0.0)
        LW = np.where(up, (1 - tau) * EW_a, EW_g) / np.pi
        LNW = np.where(up, ENW_a, ENW_g) / np.pi
        return LW, LNW

    def sky_emissivity(self):
        d, dO = hemisphere_quadrature()
        up = d[:, 2] > 0
        LW, LNW = self.env_radiance(d[up])
        E = np.sum((LW + LNW) * d[up, 2] * dO[up])
        return E / (SIGMA * self.T_amb**4)

    # ---------------------------------------------------------- solar
    def sun(self, hour, doy=172):
        """Unit vector toward the sun and DNI, DHI (clear-sky, Meinel/ASHRAE-style)."""
        decl = np.radians(23.45) * np.sin(2 * np.pi * (284 + doy) / 365)
        hra = np.radians(15 * (hour - 12))
        sin_el = np.sin(self.lat) * np.sin(decl) + np.cos(self.lat) * np.cos(decl) * np.cos(hra)
        el = np.arcsin(np.clip(sin_el, -1, 1))
        # azimuth measured from north, clockwise (east positive)
        cos_az = (np.sin(decl) - np.sin(el) * np.sin(self.lat)) / (np.cos(el) * np.cos(self.lat) + 1e-12)
        az = np.arccos(np.clip(cos_az, -1, 1))
        az = np.where(hra > 0, 2 * np.pi - az, az)
        s = np.stack([np.cos(el) * np.sin(az), np.cos(el) * np.cos(az), np.sin(el)], -1)
        am = 1 / np.clip(np.sin(el), 1e-3, 1)
        dni = np.where(el > 0, 1361 * 0.7 ** (am**0.678), 0.0)
        dhi = np.where(el > 0, 0.11 * dni * np.sin(el) + 15 * np.sin(el), 0.0)
        return s, dni, dhi


class Surface:
    """Two-band grey-per-band diffuse surface + solar absorptance."""

    def __init__(self, eps_W=0.96, eps_NW=0.90, alpha_sol=0.04, name="PDRC"):
        self.eps_W, self.eps_NW, self.alpha_sol, self.name = eps_W, eps_NW, alpha_sol, name


def flat_net_ir(normal, Ts, climate: Climate, surf: Surface, quad=None):
    """Net IR emission (W/m^2, positive = leaving) of a flat diffuse face that sees
    only sky + ground (no self view: valid for any face of a convex body)."""
    d, dO = quad if quad is not None else hemisphere_quadrature()
    n = np.asarray(normal, float)
    n = n / np.linalg.norm(n)
    c = d @ n
    m = c > 0
    LW, LNW = climate.env_radiance(d[m])
    inW = np.sum(LW * c[m] * dO[m])
    inNW = np.sum(LNW * c[m] * dO[m])
    EW, ENW = band_emissive_power(Ts)
    return surf.eps_W * (EW - inW) + surf.eps_NW * (ENW - inNW)


def flat_solar(normal, climate: Climate, hour, doy=172):
    """Incident solar irradiance on a tilted face (W/m^2): beam + isotropic diffuse + ground."""
    n = np.asarray(normal, float)
    n = n / np.linalg.norm(n)
    s, dni, dhi = climate.sun(hour, doy)
    ghi = dni * max(s[2], 0) + dhi
    cb = n[2]
    return dni * max(float(s @ n), 0) + dhi * (1 + cb) / 2 + climate.albedo * ghi * (1 - cb) / 2
