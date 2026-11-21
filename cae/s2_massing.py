"""CAE-2  Massing study: which convex envelope rejects the most heat to the sky?

All shapes enclose the same programme volume V and wear the same PDRC skin
(eps 0.96/0.90, alpha_sol 0.04). Hourly design-day balance (radiation + absorbed
sun), two operating modes: sub-ambient sink (dT = -8 K) and above-ambient
rejection (dT = +15 K).
"""
import numpy as np
from common import plt, save, dump, C
from breeze.physics import Climate, Surface
from breeze.massing import (FaceBalance, hull_faces, box, cylinder, spherical_cap, frustum, volume_scaled)
from breeze.climate_day import ambient_profile

V = 24000.0
surf = Surface(0.96, 0.90, 0.04)


def cap_V(Rb):
    from scipy.optimize import brentq
    return brentq(lambda h: np.pi * h * (3 * Rb**2 + h**2) / 6 - V, 0.1, Rb)


shapes = {
    "Cube": box(28.84, 28.84, 28.84),
    "Tower 20x20x60": box(20, 20, 60),
    "Cylinder R20": cylinder(20, V / (np.pi * 400)),
    "Hemisphere": volume_scaled(spherical_cap, V, 1.0, 1.0),
    "Pyramid 60m": frustum(60, 1e-3, 3 * V / 3600),
    "Low dome R45": spherical_cap(45, cap_V(45)),
    "Cantilever (inverted frustum)": None,
    "Slab 77x77x4": box(77.46, 77.46, 4.0),
}
# inverted frustum: base 30, top 50, solve H
Hc = V / ((900 + 2500 + np.sqrt(900 * 2500)) / 3)
shapes["Cantilever (inverted frustum)"] = frustum(30, 50, Hc)

clim = Climate(tau0=0.75)
fb = FaceBalance(clim)
hours = np.arange(24) + 0.5
Tamb = ambient_profile(hours)
modes = {"sub-ambient (ΔT=−8 K)": -8.0, "above-ambient (ΔT=+15 K)": 15.0}
rows = []
for name, pts in shapes.items():
    tri, n, A, vol, A_foot = hull_faces(pts)
    rec = {"shape": name, "V": vol, "A_env": A.sum(), "A_foot": A_foot,
           "H": pts[:, 2].max(), "A_roofproj": float(np.sum(A * np.clip(n[:, 2], 0, None)))}
    for mlabel, dT in modes.items():
        P = []
        for h, Ta in zip(hours, Tamb):
            q = fb.net(n, Ta + dT, surf, T_amb=Ta) - surf.alpha_sol * fb.solar(n, h)
            P.append(np.sum(q * A))
        P = np.array(P)
        rec[mlabel] = {"P_mean_kW": P.mean() / 1e3, "per_env": P.mean() / A.sum(),
                       "per_foot": P.mean() / A_foot, "per_vol": P.mean() / vol, "hourly_kW": (P / 1e3).tolist()}
    rows.append(rec)
    print(f"{name:32s} A_env={A.sum():7.0f} foot={A_foot:6.0f} H={rec['H']:5.1f} | " +
          " | ".join(f"{k[:5]} P={rec[k]['P_mean_kW']:6.1f}kW q_env={rec[k]['per_env']:6.1f} q_ft={rec[k]['per_foot']:6.1f}" for k in modes))

fig, axs = plt.subplots(1, 3, figsize=(12.5, 3.9))
names = [r["shape"] for r in rows]
y = np.arange(len(rows))
for ax, (mlabel, _) in zip(axs[:2], modes.items()):
    vals = [r[mlabel]["P_mean_kW"] for r in rows]
    ax.barh(y, vals, color=[C[2] if v == max(vals) else C[0] for v in vals])
    ax.set_yticks(y, names if ax is axs[0] else [""] * len(y))
    ax.axvline(0, color="k", lw=0.8)
    ax.set(xlabel="24-h mean net rejection (kW)", title=mlabel)
    ax.invert_yaxis()
for j, (mlabel, _) in enumerate(modes.items()):
    axs[2].scatter([r[mlabel]["per_env"] for r in rows], [r[mlabel]["per_foot"] for r in rows],
                   color=C[j], label=mlabel, s=22)
    for r in rows:
        axs[2].annotate(r["shape"].split(" ")[0], (r[mlabel]["per_env"], r[mlabel]["per_foot"]), fontsize=6.5,
                        xytext=(3, 2), textcoords="offset points", color="#555")
axs[2].axhline(0, color="k", lw=0.6); axs[2].axvline(0, color="k", lw=0.6)
axs[2].set(xlabel="W per m² of envelope", ylabel="W per m² of land", title="Skin efficiency vs land efficiency")
axs[2].legend(fontsize=7)
save(fig, "fig2_massing.png")
dump("s2_massing.json", {"V": V, "rows": rows})
