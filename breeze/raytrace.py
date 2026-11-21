"""Vectorised Monte-Carlo ray tracer for periodic skin cells (troughs / funnels).

Materials: 0 = specular mirror (R_ir, R_sol), 1 = ideal mirror (symmetry plane),
           2 = diffuse emitter.  The aperture is the plane z = z_ap; any ray that
reaches it travelling upward escapes to the sky.  Triangle normals point into the
cavity.  Net exchange uses reciprocity: a bundle emitted by a surface with
weight w and escaping after mirror bounces in direction d exchanges
w*R^n*[E_b(Ts) - pi*L_env,b(d)] with the environment.
"""
from __future__ import annotations

import numpy as np

from .physics import band_emissive_power

MIRROR, SYMM, EMITTER = 0, 1, 2


class CellMesh:
    def __init__(self, tris, mats, z_ap, ap_area, kind):
        self.tris = np.asarray(tris, float)  # (M,3,3)
        self.mats = np.asarray(mats, int)
        self.z_ap = z_ap
        self.ap_area = ap_area
        self.kind = kind
        v0, v1, v2 = self.tris[:, 0], self.tris[:, 1], self.tris[:, 2]
        n = np.cross(v1 - v0, v2 - v0)
        self.area = 0.5 * np.linalg.norm(n, axis=1)
        self.n = n / (2 * self.area[:, None])

    def area_of(self, mat):
        return self.area[self.mats == mat].sum()


def _orient(tris, ref_fn):
    out = []
    for t in tris:
        t = np.asarray(t, float)
        n = np.cross(t[1] - t[0], t[2] - t[0])
        c = t.mean(0)
        if n @ (ref_fn(c) - c) < 0:
            t = t[[0, 2, 1]]
        out.append(t)
    return out


def _quad(a, b, c, d):
    return [[a, b, c], [a, c, d]]


# ------------------------------------------------------------------ profiles
def cpc_profile(a_exit, theta_a, trunc=1.0, n=14):
    """Right-hand wall of a 2-D CPC (Welford & Winston). Returns (y,z) points from
    exit-edge to (truncated) aperture.  trunc in (0,1] scales the full height."""
    f = a_exit * (1 + np.sin(theta_a))
    phi = np.linspace(np.pi / 2 + theta_a, 2 * theta_a, 400)
    r = 2 * f / (1 - np.cos(phi))
    y = r * np.sin(phi - theta_a) - a_exit
    z = r * np.cos(phi - theta_a)
    zmax = z[-1] * trunc
    keep = z <= zmax + 1e-12
    y, z = y[keep], z[keep]
    idx = np.linspace(0, len(y) - 1, n).astype(int)
    return np.stack([y[idx], z[idx]], 1)


def v_profile(a_exit, half_angle, height, n=2):
    """Straight wall leaning outward by half_angle from vertical."""
    return np.array([[a_exit, 0.0], [a_exit + height * np.tan(half_angle), height]])


def trough_cell(profile, Lx=1.0):
    """Extruded trough (axis along x = East-West). Symmetry caps make it infinite."""
    prof = np.asarray(profile)
    a_e, z_ap, a_t = prof[0, 0], prof[-1, 1], prof[-1, 0]
    x0, x1 = -Lx / 2, Lx / 2
    tris, mats = [], []
    for side in (+1, -1):
        for (y0, z0), (y1, z1) in zip(prof[:-1], prof[1:]):
            q = _quad([x0, side * y0, z0], [x1, side * y0, z0], [x1, side * y1, z1], [x0, side * y1, z1])
            tris += q
            mats += [MIRROR, MIRROR]
    tris += _quad([x0, -a_e, 0], [x1, -a_e, 0], [x1, a_e, 0], [x0, a_e, 0])
    mats += [EMITTER, EMITTER]
    # end caps: polygon (fan) of the cross-section at x0 and x1
    poly = [(-y, z) for y, z in prof[::-1]] + [(y, z) for y, z in prof]
    for xc in (x0, x1):
        cy, cz = 0.0, z_ap / 2
        for (y0, z0), (y1, z1) in zip(poly[:-1], poly[1:]):
            tris.append([[xc, cy, cz], [xc, y0, z0], [xc, y1, z1]])
            mats.append(SYMM)
        # top edge of the cap (aperture line) and bottom edge (emitter)
        tris.append([[xc, cy, cz], [xc, a_t, z_ap], [xc, -a_t, z_ap]])
        mats.append(SYMM)
        tris.append([[xc, cy, cz], [xc, -a_e, 0], [xc, a_e, 0]])
        mats.append(SYMM)

    def ref(c):
        if abs(abs(c[0]) - Lx / 2) < 1e-9:
            return np.array([0.0, c[1], c[2]])
        if abs(c[2]) < 1e-12:
            return np.array([c[0], c[1], 1.0])
        return np.array([c[0], 0.0, c[2]])

    tris = _orient(tris, ref)
    keep = [i for i, m in enumerate(mats) if not (m == SYMM and abs(np.cross(tris[i][1] - tris[i][0], tris[i][2] - tris[i][0])).sum() < 1e-14)]
    tris = [tris[i] for i in keep]
    mats = [mats[i] for i in keep]
    return CellMesh(tris, mats, z_ap, 2 * a_t * Lx, "trough")


def funnel_cell(a_exit, a_top, height):
    """Square inverted-pyramid frustum cell (3-D angular selectivity)."""
    e, t, h = a_exit, a_top, height
    B = [[-e, -e, 0], [e, -e, 0], [e, e, 0], [-e, e, 0]]
    T = [[-t, -t, h], [t, -t, h], [t, t, h], [-t, t, h]]
    tris, mats = [], []
    for i in range(4):
        j = (i + 1) % 4
        tris += _quad(B[i], B[j], T[j], T[i])
        mats += [MIRROR, MIRROR]
    tris += _quad(*B)
    mats += [EMITTER, EMITTER]

    def ref(c):
        return np.array([0.0, 0.0, max(c[2], 1e-3) if c[2] > 1e-12 else 1.0])

    tris = _orient(tris, ref)
    return CellMesh(tris, mats, h, (2 * t) ** 2, "funnel")


def flat_cell():
    tris = _quad([-0.5, -0.5, 0], [0.5, -0.5, 0], [0.5, 0.5, 0], [-0.5, 0.5, 0])
    tris = _orient(tris, lambda c: np.array([c[0], c[1], 1.0]))
    return CellMesh(tris, [EMITTER, EMITTER], 1e-6, 1.0, "flat")


# ------------------------------------------------------------------ tracing
def _lambert(normals, rng):
    n = normals.shape[0]
    u1, u2 = rng.random(n), rng.random(n)
    r, ph = np.sqrt(u1), 2 * np.pi * u2
    local = np.stack([r * np.cos(ph), r * np.sin(ph), np.sqrt(1 - u1)], 1)
    a = np.where(np.abs(normals[:, 2:3]) < 0.9, np.array([[0, 0, 1.0]]), np.array([[1.0, 0, 0]]))
    t1 = np.cross(a, normals)
    t1 /= np.linalg.norm(t1, axis=1, keepdims=True)
    t2 = np.cross(normals, t1)
    return local[:, :1] * t1 + local[:, 1:2] * t2 + local[:, 2:3] * normals


def _intersect(mesh: CellMesh, o, d):
    v0 = mesh.tris[:, 0]
    e1 = mesh.tris[:, 1] - v0
    e2 = mesh.tris[:, 2] - v0
    p = np.cross(d[:, None, :], e2[None])
    det = np.einsum("nmk,mk->nm", p, e1)
    inv = 1.0 / np.where(np.abs(det) < 1e-14, np.inf, det)
    s = o[:, None, :] - v0[None]
    u = np.einsum("nmk,nmk->nm", s, p) * inv
    q = np.cross(s, e1[None])
    v = np.einsum("nk,nmk->nm", d, q) * inv
    t = np.einsum("nmk,mk->nm", q, e2) * inv
    ok = (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > 1e-9)
    t = np.where(ok, t, np.inf)
    idx = np.argmin(t, 1)
    tmin = t[np.arange(len(o)), idx]
    # aperture plane
    t_ap = np.where(d[:, 2] > 1e-12, (mesh.z_ap - o[:, 2]) / np.where(d[:, 2] > 1e-12, d[:, 2], 1), np.inf)
    t_ap = np.where(t_ap > 1e-9, t_ap, np.inf)
    escape = t_ap < tmin
    return idx, tmin, escape


def _sample_on(mesh, mat_mask, n, rng):
    ids = np.flatnonzero(mat_mask)
    w = mesh.area[ids] / mesh.area[ids].sum()
    pick = rng.choice(ids, n, p=w)
    r1, r2 = rng.random(n), rng.random(n)
    s = np.sqrt(r1)
    v = mesh.tris[pick]
    pts = (1 - s)[:, None] * v[:, 0] + (s * (1 - r2))[:, None] * v[:, 1] + (s * r2)[:, None] * v[:, 2]
    return pts, pick


def trace_emission(mesh: CellMesh, R_ir=0.97, n_rays=60000, max_bounce=60, seed=1, source="emitter"):
    """Trace emission bundles from the emitter (or mirrors). Returns escape dirs and
    weights (product of mirror reflectances), normalised per emitted bundle."""
    rng = np.random.default_rng(seed)
    mask = mesh.mats == (EMITTER if source == "emitter" else MIRROR)
    o, tri = _sample_on(mesh, mask, n_rays, rng)
    d = _lambert(mesh.n[tri], rng)
    o = o + 1e-9 * mesh.n[tri]
    w = np.ones(n_rays)
    esc_d, esc_w = [], []
    alive = np.arange(n_rays)
    for _ in range(max_bounce):
        if alive.size == 0:
            break
        idx, t, escape = _intersect(mesh, o[alive], d[alive])
        e = alive[escape]
        esc_d.append(d[e])
        esc_w.append(w[e])
        hit = ~escape & np.isfinite(t)
        a = alive[hit]
        idx, t = idx[hit], t[hit]
        m = mesh.mats[idx]
        refl = m != EMITTER  # rays returning to the emitter are internal exchange
        a, idx, t, m = a[refl], idx[refl], t[refl], m[refl]
        nrm = mesh.n[idx]
        o[a] = o[a] + t[:, None] * d[a]
        dd = d[a]
        d[a] = dd - 2 * np.sum(dd * nrm, 1, keepdims=True) * nrm
        o[a] += 1e-9 * nrm
        w[a] *= np.where(m == MIRROR, R_ir, 1.0)
        alive = a
    return np.concatenate(esc_d), np.concatenate(esc_w)


def net_ir(mesh: CellMesh, Ts, climate, surf, R_ir=0.97, n_rays=60000, tilt=0.0, seed=1):
    """Net IR power per unit APERTURE area (W/m^2). tilt rotates the cell toward north."""
    _cache = mesh.__dict__.setdefault("_trace_cache", {})
    key = (R_ir, n_rays, seed)
    if key not in _cache:
        _cache[key] = (trace_emission(mesh, R_ir, n_rays, seed=seed),
                       trace_emission(mesh, R_ir, n_rays, seed=seed + 7, source="mirror")
                       if (mesh.mats == MIRROR).any() else None)
    (dE, wE), mir = _cache[key]
    EW, ENW = band_emissive_power(Ts)

    def ex(dirs, w):
        c, s = np.cos(tilt), np.sin(tilt)
        rot = np.array([[1, 0, 0], [0, c, s], [0, -s, c]])  # tilts cell normal toward +y (north)
        LW, LNW = climate.env_radiance(dirs @ rot.T)
        return (np.sum(w * (EW - np.pi * LW)), np.sum(w * (ENW - np.pi * LNW)))

    xW, xNW = ex(dE, wE)
    A_e = mesh.area_of(EMITTER)
    q = A_e * (surf.eps_W * xW + surf.eps_NW * xNW) / n_rays
    if mir is not None:
        dM, wM = mir
        mW, mNW = ex(dM, wM)
        q += mesh.area_of(MIRROR) * (1 - R_ir) * (mW + mNW) / n_rays
    return q / mesh.ap_area


def solar_absorbed(mesh: CellMesh, sun_dir, alpha_e, R_sol=0.95, n_rays=20000, seed=3, tilt=0.0):
    """Fraction of collimated irradiance (per unit aperture area, normal to aperture
    projected) absorbed by the cell. sun_dir is in world frame (toward the sun)."""
    rng = np.random.default_rng(seed)
    c, s = np.cos(tilt), np.sin(tilt)
    rot = np.array([[1, 0, 0], [0, c, s], [0, -s, c]])
    sd = np.asarray(sun_dir) @ rot  # world -> cell frame (inverse rotation)
    if sd[2] <= 0:
        return 0.0
    # start points on aperture
    if mesh.kind == "flat":
        return alpha_e
    bb = mesh.tris.reshape(-1, 3)
    top = bb[np.abs(bb[:, 2] - mesh.z_ap) < 1e-9]
    xlo, xhi = top[:, 0].min(), top[:, 0].max()
    ylo, yhi = top[:, 1].min(), top[:, 1].max()
    o = np.stack([rng.uniform(xlo, xhi, n_rays), rng.uniform(ylo, yhi, n_rays),
                  np.full(n_rays, mesh.z_ap - 1e-9)], 1)
    d = np.tile(-sd, (n_rays, 1))
    w = np.ones(n_rays)
    absorbed = np.zeros(n_rays)
    alive = np.arange(n_rays)
    for _ in range(60):
        if alive.size == 0:
            break
        idx, t, escape = _intersect(mesh, o[alive], d[alive])
        hit = ~escape & np.isfinite(t)
        a, idx, t = alive[hit], idx[hit], t[hit]
        m = mesh.mats[idx]
        o[a] = o[a] + t[:, None] * d[a]
        nrm = mesh.n[idx]
        em = m == EMITTER
        absorbed[a[em]] += w[a[em]] * alpha_e
        w[a[em]] *= 1 - alpha_e
        d[a[em]] = _lambert(nrm[em], rng)
        mi = m == MIRROR
        absorbed[a[mi]] += w[a[mi]] * (1 - R_sol)
        w[a[mi]] *= R_sol
        sp = ~em
        dd = d[a[sp]]
        d[a[sp]] = dd - 2 * np.sum(dd * nrm[sp], 1, keepdims=True) * nrm[sp]
        o[a] += 1e-9 * nrm
        alive = a[w[a] > 1e-4]
    return absorbed.mean()


def angular_emittance(mesh: CellMesh, R_ir=0.97, n_rays=100000, nbins=18, seed=5):
    """Directional effective emittance of the aperture vs. polar angle, in the
    N-S (profile) plane and E-W plane, for a black emitter."""
    d, w = trace_emission(mesh, R_ir, n_rays, seed=seed)
    A_e = mesh.area_of(EMITTER)
    th = np.degrees(np.arccos(np.clip(d[:, 2], -1, 1)))
    edges = np.linspace(0, 90, nbins + 1)
    # radiance-normalised: power per solid angle / (cos * aperture) relative to black
    dO = 2 * np.pi * (np.cos(np.radians(edges[:-1])) - np.cos(np.radians(edges[1:])))
    mid = np.radians(0.5 * (edges[1:] + edges[:-1]))
    P, _ = np.histogram(th, edges, weights=w)
    eps = P * A_e / n_rays / (dO * np.cos(mid) * mesh.ap_area / np.pi)
    return 0.5 * (edges[1:] + edges[:-1]), eps
