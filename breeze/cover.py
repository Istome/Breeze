"""Covers over the emitter: thin film over a still-air gap, or a thick
IR-transparent insulating layer (polyethylene aerogel, after Leroy et al.,
Sci. Adv. 2019: 6 mm -> R_sol 0.92, tau_IR 0.80, k 28 mW/mK).

Directional model: in direction theta the emitter sees
    tau(theta) * L_env + (1 - tau(theta)) * B(T_c)/pi,
with tau(theta) = tau_s * exp(-t / (l cos theta)) for a thick slab (path length
grows with obliquity, so a thick cover is itself an angular filter that dims the
warm horizon) and T_c the mean temperature of the absorbing medium.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .physics import band_emissive_power, hemisphere_quadrature

K_AIR = 0.026


@dataclass
class Cover:
    kind: str = "film"       # "film" (film over still-air gap), "aerogel", "none"
    t: float = 0.026         # gap or slab thickness (m)
    wind: float = 2.5        # m/s
    # film
    tau_film: float = 0.85
    tau_film_sol: float = 0.92
    # aerogel (PE) optical/thermal constants
    l_ir: float = 0.0348     # m, IR extinction length (fit: 0.80 at 6 mm incl. 5 % surface loss)
    S_sol: float = 1970.0    # 1/m, solar back-scatter: R = S t / (1 + S t)  (0.922 at 6 mm)
    a_sol: float = 1.7       # 1/m, solar absorption in the slab (1 % at 6 mm)
    k: float = 0.028
    top_film_tau: float = 0.93  # 6 um HDPE weather skin over the aerogel
    leak: float = 0.2        # W/m2K edge/frame thermal bridging

    @property
    def h_out(self):
        return 2.8 + 3.0 * self.wind

    def U(self):
        if self.kind == "none":
            return self.h_out
        cond = self.t / (K_AIR if self.kind == "film" else self.k)
        return 1.0 / (cond + 1.0 / self.h_out) + self.leak

    def tau_ir(self, cos_t):
        if self.kind == "none":
            return np.ones_like(cos_t)
        if self.kind == "film":
            return np.full_like(cos_t, self.tau_film)
        return self.top_film_tau * 0.95 * np.exp(-self.t / (self.l_ir * np.clip(cos_t, 0.02, 1)))

    def solar(self):
        """(transmitted to emitter, absorbed in cover) fractions of incident sun."""
        if self.kind == "none":
            return 1.0, 0.0
        if self.kind == "film":
            return self.tau_film_sol, 0.01
        St = self.S_sol * self.t
        R = St / (1 + St)
        A = min(self.a_sol * self.t, 1 - R)
        return max(0.0, 1 - R - A) * 0.97, A


class CoveredPlate:
    """Net cooling flux (W/m2, +ve = heat leaving the water) of a horizontal emitter
    under a cover, including sun and conduction/convection."""

    def __init__(self, surf, cover: Cover, n_theta=45, n_phi=72):
        self.s, self.c = surf, cover
        d, dO = hemisphere_quadrature(n_theta, n_phi)
        up = d[:, 2] > 0
        self.d, self.w = d[up], (d[up, 2] * dO[up])
        self.tau = cover.tau_ir(self.d[:, 2])

    def flux(self, Ts, Ta, clim, G_sun=0.0):
        clim.T_amb = clim.T_ground = Ta
        LW, LNW = clim.env_radiance(self.d)
        Tc = 0.5 * (Ts + Ta) if self.c.kind == "aerogel" else Ta - 1.0
        BW, BNW = band_emissive_power(Tc)
        EW, ENW = band_emissive_power(Ts)
        inW = np.sum((self.tau * LW + (1 - self.tau) * BW / np.pi) * self.w)
        inNW = np.sum((self.tau * LNW + (1 - self.tau) * BNW / np.pi) * self.w)
        q_ir = self.s.eps_W * (EW - inW) + self.s.eps_NW * (ENW - inNW)
        tr, ab = self.c.solar()
        q_sun = self.s.alpha_sol * tr * G_sun + 0.5 * ab * G_sun
        return q_ir - q_sun - self.c.U() * (Ta - Ts)
