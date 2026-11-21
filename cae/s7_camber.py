"""CAE-7  Camber optimisation of the radiant plate.

Fixed plan (circle of radius R, i.e. fixed land), spherical-cap plate of rise s.
Only the sky-facing upper surface is an emitter (soffit + edges are IR mirrors).
Net per unit LAND area vs. rise/span, night-time IR only and 24 h incl. sun.
"""
import numpy as np
from common import plt, save, dump, C
from breeze.physics import Climate, Surface
from breeze.massing import FaceBalance, hull_faces, spherical_cap
from breeze.climate_day import ambient_profile

R = 30.0
surf = Surface(0.95, 0.15, 0.05)        # selective emitter (CAE-6 winner)
surf_bb = Surface(0.96, 0.90, 0.04)
ratios = np.array([0.005, 0.03, 0.06, 0.09, 0.12, 0.16, 0.20, 0.25, 0.32, 0.40, 0.50])
out = {"rise_over_span": ratios.tolist(), "cases": {}}
fig, ax = plt.subplots(1, 1, figsize=(6.2, 3.8))
k = 0
for tau in (0.75, 0.55):
    clim = Climate(tau0=tau)
    fb = FaceBalance(clim)
    for sname, s in (("selective", surf), ("broadband", surf_bb)):
        for dT in (-5, -12):
            vals = []
            for r in ratios:
                tri, n, A, vol, foot = hull_faces(spherical_cap(R, r * 2 * R, 40))
                q = fb.net(n, clim.T_amb + dT, s, T_amb=clim.T_amb)
                vals.append(float(np.sum(q * A) / (np.pi * R**2)))
            vals = np.array(vals)
            key = f"τ₀={tau} {sname} ΔT={dT}"
            out["cases"][key] = vals.tolist()
            rel = vals / abs(vals[0])
            print(f"{key:32s} flat={vals[0]:6.1f} W/m2land  best rise/span={ratios[np.argmax(vals)]:.2f} gain={rel.max():.3f}", np.round(rel, 3))
            ax.plot(ratios, vals, marker="o", ms=2.5, color=C[k % len(C)], ls="-" if sname == "selective" else "--", label=key)
            k += 1
ax.axhline(0, color="k", lw=0.7)
ax.axvspan(0, 0.06, color="#1a9e75", alpha=0.08)
ax.text(0.008, ax.get_ylim()[1] * 0.92, "chosen camber band", fontsize=7, color="#1a9e75")
ax.set(xlabel="rise / span of cambered plate", ylabel="net IR per land area (W m⁻²)", title="Camber of the radiant plate (night)")
ax.legend(fontsize=6.3, ncol=2)
save(fig, "fig7_camber.png")
dump("s7_camber.json", out)
