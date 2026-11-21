"""CAE-4  Thermal FEA (finite-volume, 2-D) of the emitter base sheet.

Section: N-S cut through one hydronic channel and the emitter strips it feeds.
 - channel (roll-bond pillow or printed duct) on the underside at x=0, h_w = 800 W/m2K
 - top surface: emitter strips |x - k*p| <= e radiate with q(T) = q_w + h_r (T - T_w)
   (linearised about water temperature; h_r = d q/dT from the MC optics, ~6 W/m2K
   incl. film coupling); under the mirror walls the top is adiabatic
 - underside insulated (PIR + low-e foil).
Output: fin efficiency eta = Q / (A_emitter q_w) and peak water->emitter dT for
four candidate construction materials and channel pitches.
"""
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from common import plt, save, dump, C

p_cell = 0.30
e = 0.5 * p_cell * np.sin(np.radians(60))
q_w = 60.0       # W/m2 of emitter at water temperature (design night)
h_r = 6.0        # W/m2K linearised
h_w = 800.0      # W/m2K water side
w_ch = 0.030     # wetted perimeter of a 15 mm roll-bond pillow (both faces), m
MATS = {
    "Al 1050 roll-bond, 1.5 mm": (220.0, 1.5e-3),
    "Stainless 304, 1.0 mm": (16.0, 1.0e-3),
    "3D-printed UHPC, 20 mm": (2.2, 20e-3),
    "Recycled PP sheet, 3 mm": (0.22, 3e-3),
}


def solve(k, t, pitch, nx=600, nz=6):
    L = pitch / 2
    dx, dz = L / nx, t / nz
    N = nx * nz
    idx = lambda i, j: j * nx + i
    A = sp.lil_matrix((N, N))
    b = np.zeros(N)
    x = (np.arange(nx) + 0.5) * dx
    xc = np.abs(((x + p_cell / 2) % p_cell) - p_cell / 2)
    emit = xc <= e
    for j in range(nz):
        for i in range(nx):
            r = idx(i, j)
            for di, dj, area, d in ((1, 0, dz, dx), (-1, 0, dz, dx), (0, 1, dx, dz), (0, -1, dx, dz)):
                ii, jj = i + di, j + dj
                if 0 <= ii < nx and 0 <= jj < nz:
                    g = k * area / d
                    A[r, r] += g
                    A[r, idx(ii, jj)] -= g
            # unknown is theta = T - T_w
            if j == 0 and x[i] <= w_ch / 2:  # channel
                g = 1 / (1 / (h_w * dx) + dz / 2 / (k * dx))
                A[r, r] += g
            if j == nz - 1 and emit[i]:  # emitter: q = q_w + h_r*theta leaves
                g = 1 / (1 / (h_r * dx) + dz / 2 / (k * dx))
                A[r, r] += g
                b[r] -= q_w * dx
    th = spla.spsolve(A.tocsr(), b).reshape(nz, nx)
    top = th[-1]
    q = q_w + h_r * top[emit]
    eta = q.sum() / (q_w * emit.sum())
    return eta, -top.min(), x, top


res = {}
pitches = np.array([0.15, 0.30, 0.60, 0.90, 1.20, 1.80])
fig, axs = plt.subplots(1, 2, figsize=(10.5, 3.6))
for j, (name, (k, t)) in enumerate(MATS.items()):
    etas, dts = [], []
    for P in pitches:
        eta, dT, x, top = solve(k, t, P)
        etas.append(eta); dts.append(dT)
        if abs(P - 0.6) < 1e-9:
            axs[1].plot(x * 1000, top, label=name, color=C[j])
    res[name] = {"k": k, "t": t, "pitch": pitches.tolist(), "eta": etas, "dT_max": dts}
    print(f"{name:28s} eta:", np.round(etas, 3), " dTmax:", np.round(dts, 2))
    axs[0].plot(pitches, etas, marker="o", ms=3, label=name, color=C[j])
axs[0].axhline(0.95, color="#999", ls=":", lw=0.8)
axs[0].set(xlabel="channel pitch (m)", ylabel="emitter efficiency η", title="Hydronic channel pitch vs. material", ylim=(0, 1.02))
axs[0].legend(fontsize=7)
axs[1].set(xlabel="distance from channel (mm)", ylabel="T_surface − T_water (K)", title="Top-surface temperature, 0.6 m pitch")
save(fig, "fig4_panel_fea.png")
dump("s4_panel_fea.json", res)
