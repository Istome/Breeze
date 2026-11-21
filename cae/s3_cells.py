"""CAE-3  Skin-cell optics: Monte-Carlo ray tracing of angular-selective cavities.

Cell families (per unit APERTURE = per unit roof area):
  flat   : bare emitter
  trough : 2-D CPC, axis East-West, specular walls (blocks N/S horizon only)
  funnel : square inverted pyramid frustum, specular walls (blocks all azimuths)
Emitters: broadband PDRC (0.96 / 0.90) and window-selective (0.95 / 0.15).
Walls: Al mirror under nanoporous-PE solar scatterer, R_IR = 0.98, R_sol = 0.97.
"""
import numpy as np
from common import plt, save, dump, C
from breeze.physics import Climate, Surface
from breeze.raytrace import flat_cell, trough_cell, funnel_cell, cpc_profile, net_ir, angular_emittance, solar_absorbed

R_IR, R_SOL, NR = 0.98, 0.97, 16000
emit = {"broadband": Surface(0.96, 0.90, 0.04), "selective": Surface(0.95, 0.15, 0.05)}
thetas = [30, 40, 50, 60, 70, 80]
dTs = np.array([-25, -20, -15, -10, -5, 0, 5])


def funnel(th):
    th = np.radians(th)
    t = 0.5
    e = t * np.sin(th)
    return funnel_cell(e, t, (t + e) / np.tan(th))


def trough(th):
    return trough_cell(cpc_profile(0.5 * np.sin(np.radians(th)), np.radians(th), 1.0))


res = {"dT": dTs.tolist(), "thetas": thetas, "cells": {}}
for tau in (0.75, 0.55):
    clim = Climate(tau0=tau)
    for ename, s in emit.items():
        key = f"tau{tau}/{ename}"
        res["cells"][key] = {"flat": [net_ir(flat_cell(), clim.T_amb + dT, clim, s, R_IR, NR) for dT in dTs]}
        for fam, mk in (("funnel", funnel), ("trough", trough)):
            for th in thetas:
                m = mk(th)
                res["cells"][key][f"{fam}{th}"] = [net_ir(m, clim.T_amb + dT, clim, s, R_IR, NR) for dT in dTs]
        print(key, "done", flush=True)


def stagnation(curve):
    q = np.array(curve)
    i = np.flatnonzero(q > 0)[0]
    return float(np.interp(0, q[i - 1:i + 1], dTs[i - 1:i + 1])) if i > 0 else float(dTs[0])


summary = {}
for key, cells in res["cells"].items():
    summary[key] = {}
    for j, dT in enumerate(dTs):
        best = max(cells, key=lambda c: cells[c][j])
        summary[key][int(dT)] = (best, round(cells[best][j], 1), round(cells["flat"][j], 1))
    summary[key]["stagnation"] = {c: round(stagnation(v), 1) for c, v in cells.items()}
res["summary"] = summary
for k, v in summary.items():
    print(k, {d: v[d] for d in v if d != "stagnation"})
    print("   stagnation:", {c: v["stagnation"][c] for c in ("flat", "funnel50", "funnel60", "trough60")})

# angular emittance + solar absorption on design day
ang = {}
for name, m in (("funnel 50°", funnel(50)), ("trough 50° (all azimuths)", trough(50))):
    th, e = angular_emittance(m, R_IR, 60000)
    ang[name] = (th.tolist(), e.tolist())
clim = Climate(tau0=0.75)
hours = np.arange(5, 20, 0.5)
sol = {}
for name, m in (("flat", flat_cell()), ("funnel50", funnel(50)), ("funnel60", funnel(60)), ("trough50 E-W", trough(50))):
    G, Aabs = [], []
    for h in hours:
        s, dni, dhi = clim.sun(h)
        if s[2] <= 0:
            G.append(0); Aabs.append(0); continue
        frac = solar_absorbed(m, s, 0.04, R_SOL, 6000)
        G.append(dni * s[2] + dhi)
        Aabs.append(frac * dni * s[2] + 0.04 * dhi * (1.6 if name != "flat" else 1.0))
    sol[name] = {"G": G, "abs": Aabs, "daily_abs_Wh": float(np.sum(Aabs) * 0.5)}
    print("solar", name, round(sol[name]["daily_abs_Wh"], 0), "Wh/m2/day")
res["angular"] = ang
res["solar"] = {"hours": hours.tolist(), **sol}
dump("s3_cells.json", res)

# ---------------- figures
fig, axs = plt.subplots(1, 3, figsize=(12.5, 3.8))
cells = res["cells"]["tau0.75/broadband"]
for j, (lab, ck) in enumerate((("flat", "flat"), ("funnel 40°", "funnel40"), ("funnel 50°", "funnel50"),
                               ("funnel 60°", "funnel60"), ("trough CPC 60°", "trough60"), ("funnel 80°", "funnel80"))):
    axs[0].plot(dTs, cells[ck], marker="o", ms=3, label=lab, color=C[j % len(C)])
axs[0].axhline(0, color="k", lw=0.8)
axs[0].set(xlabel="surface − ambient ΔT (K)", ylabel="net IR per roof area (W m⁻²)", title="Cell net emission (dry, broadband)")
axs[0].legend(fontsize=7)
for j, key in enumerate(res["cells"]):
    cl = res["cells"][key]
    best_th = []
    for i in range(len(dTs)):
        best_th.append(max([90] + thetas, key=lambda t: cl["flat"][i] if t == 90 else cl[f"funnel{t}"][i]))
    axs[1].plot(dTs, best_th, marker="s", ms=3, label=key.replace("tau", "τ₀="), color=C[j])
axs[1].set(xlabel="ΔT (K)", ylabel="optimal acceptance half-angle θₐ* (deg)", title="Matched filter: θₐ*(ΔT)", ylim=(20, 95))
axs[1].legend(fontsize=7)
for j, (k, (th, e)) in enumerate(ang.items()):
    axs[2].plot(th, e, label=k, color=C[j])
axs[2].set(xlabel="emission zenith angle (deg)", ylabel="directional effective emittance", title="Aperture angular emittance", ylim=(0, 1.15))
axs[2].legend(fontsize=7)
save(fig, "fig3_cells.png")
