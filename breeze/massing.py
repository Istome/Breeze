"""Convex massing library + whole-envelope radiative balance.

For any face of a convex body the only things it can see are sky and ground, so the
net exchange is exact face-by-face:  P = sum_f A_f q(n_f).  Equivalently (and this
is the governing idea of the study)

    P = Int_{4pi} A_proj(w) * pi*dL(w) dw / pi,

i.e. a convex envelope is a *projected-area filter* applied to the coldness pattern
dL(w) = L_surface - L_environment(w) of the sky.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import ConvexHull

from .physics import band_emissive_power, hemisphere_quadrature


def hull_faces(points):
    h = ConvexHull(points)
    tri = points[h.simplices]
    n = h.equations[:, :3]
    # orient triangles consistently with outward normal
    c = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    flip = np.sum(c * n, 1) < 0
    tri[flip] = tri[flip][:, [0, 2, 1]]
    area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    ground = (n[:, 2] < -0.999) & (np.abs(tri[:, :, 2]).max(1) < 1e-6)
    return tri[~ground], n[~ground], area[~ground], h.volume, area[ground].sum()


# ---------------------------------------------------------------- shapes
def box(L, W, H):
    return np.array([[x, y, z] for x in (-L / 2, L / 2) for y in (-W / 2, W / 2) for z in (0, H)])


def cylinder(R, H, n=72):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = np.stack([R * np.cos(a), R * np.sin(a)], 1)
    return np.vstack([np.c_[ring, np.zeros(n)], np.c_[ring, np.full(n, H)]])


def spherical_cap(Rb, h, n=48):
    """Cap of base radius Rb and rise h (h=Rb is a hemisphere)."""
    Rs = (Rb**2 + h**2) / (2 * h)
    pts = []
    for t in np.linspace(0, 1, n):
        z = t * h
        r = np.sqrt(max(Rs**2 - (z + Rs - h) ** 2, 0))
        k = max(int(4 * n * r / Rb), 6) if r > 1e-6 else 1
        a = np.linspace(0, 2 * np.pi, k, endpoint=False)
        pts += [[r * np.cos(b), r * np.sin(b), z] for b in a]
    return np.array(pts)


def frustum(Lb, Lt, H):
    """Square frustum: base side Lb, top side Lt (Lt>Lb = cantilevered/inverted)."""
    return np.array([[s * L / 2, t * L / 2, z] for (L, z) in ((Lb, 0), (Lt, H)) for s in (-1, 1) for t in (-1, 1)])


def volume_scaled(make, V, *args):
    """Uniformly scale a shape to volume V."""
    p = make(*args)
    v = ConvexHull(p).volume
    return p * (V / v) ** (1 / 3)


# ---------------------------------------------------------------- balance
class FaceBalance:
    """Vectorised net IR for many face normals at once (sky + ground only)."""

    def __init__(self, climate, n_theta=45, n_phi=90):
        self.c = climate
        self.d, self.dO = hemisphere_quadrature(n_theta, n_phi)

    def irradiance(self, normals, T_amb=None):
        """Incident band irradiance (W/m^2) on faces: returns (G_W, G_NW) arrays."""
        c = self.c
        if T_amb is not None:
            c.T_amb = c.T_ground = T_amb
        LW, LNW = c.env_radiance(self.d)
        GW, GNW = [], []
        for chunk in np.array_split(normals, max(1, len(normals) // 500)):
            cs = np.clip(chunk @ self.d.T, 0, None) * self.dO
            GW.append(cs @ LW)
            GNW.append(cs @ LNW)
        return np.concatenate(GW), np.concatenate(GNW)

    def net(self, normals, Ts, surf, T_amb=None):
        GW, GNW = self.irradiance(normals, T_amb)
        EW, ENW = band_emissive_power(Ts)
        return surf.eps_W * (EW - GW) + surf.eps_NW * (ENW - GNW)

    def solar(self, normals, hour, doy=172):
        s, dni, dhi = self.c.sun(hour, doy)
        ghi = dni * max(s[2], 0) + dhi
        cb = normals[:, 2]
        return dni * np.clip(normals @ s, 0, None) + dhi * (1 + cb) / 2 + self.c.albedo * ghi * (1 - cb) / 2
