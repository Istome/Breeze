"""CAE-1  Sky coldness pattern and tilt response.

Outputs the directional net radiance dL(theta) that any envelope element sees, the
crossover zenith angle beyond which the sky *heats* a sub-ambient surface, and the
net flux of a flat face vs. tilt.
"""
import numpy as np
from common import plt, save, dump, C
from breeze.physics import Climate, Surface, band_emissive_power, flat_net_ir

surf = Surface(0.96, 0.90, 0.04)
th = np.radians(np.linspace(0, 90, 181))
dTs = [-15, -10, -5, 0, 10, 25]
out = {"theta_deg": np.degrees(th).tolist(), "climates": {}}
fig, axs = plt.subplots(1, 3, figsize=(12, 3.6))
for k, tau in enumerate((0.75, 0.55)):
    clim = Climate(tau0=tau)
    d = np.stack([np.sin(th), 0 * th, np.cos(th)], 1)
    LW, LNW = clim.env_radiance(d)
    rec = {"eps_sky": clim.sky_emissivity(), "dL": {}, "crossover_deg": {}}
    for j, dT in enumerate(dTs):
        EW, ENW = band_emissive_power(clim.T_amb + dT)
        dL = surf.eps_W * (EW - np.pi * LW) + surf.eps_NW * (ENW - np.pi * LNW)  # W/m^2 per pi sr
        rec["dL"][dT] = dL.tolist()
        neg = np.flatnonzero(dL < 0)
        rec["crossover_deg"][dT] = float(np.degrees(th[neg[0]])) if neg.size else 90.0
        if k == 0:
            axs[0].plot(np.degrees(th), dL, label=f"ΔT = {dT:+d} K", color=C[j % len(C)])
    out["climates"][f"tau{tau}"] = rec
axs[0].axhline(0, color="k", lw=0.8)
axs[0].set(xlabel="zenith angle θ (deg)", ylabel="π·ΔL(θ)  (W m⁻²)", title="Sky coldness pattern (dry, τ₀=0.75)")
axs[0].legend(fontsize=7.5, ncol=2)

dT_grid = np.linspace(-25, 5, 61)
for k, tau in enumerate((0.75, 0.55)):
    clim = Climate(tau0=tau)
    d = np.stack([np.sin(th), 0 * th, np.cos(th)], 1)
    LW, LNW = clim.env_radiance(d)
    xo = []
    for dT in dT_grid:
        EW, ENW = band_emissive_power(clim.T_amb + dT)
        dL = surf.eps_W * (EW - np.pi * LW) + surf.eps_NW * (ENW - np.pi * LNW)
        neg = np.flatnonzero(dL < 0)
        xo.append(np.degrees(th[neg[0]]) if neg.size else 90.0)
    axs[1].plot(dT_grid, xo, label=f"τ₀ = {tau} ({'dry' if tau > 0.6 else 'humid'})")
    out["climates"][f"tau{tau}"]["crossover_curve"] = {"dT": dT_grid.tolist(), "theta0": xo}
axs[1].set(xlabel="surface − ambient ΔT (K)", ylabel="θ₀: sky turns from sink to source (deg)",
           title="Useful-sky cone half-angle", ylim=(0, 92))
axs[1].legend()

betas = np.linspace(0, 180, 37)
clim = Climate(tau0=0.75)
qb = {}
for j, dT in enumerate(dTs):
    q = [flat_net_ir([0, np.sin(np.radians(b)), np.cos(np.radians(b))], clim.T_amb + dT, clim, surf) for b in betas]
    qb[dT] = q
    axs[2].plot(betas, q, label=f"ΔT = {dT:+d} K", color=C[j % len(C)])
axs[2].axhline(0, color="k", lw=0.8)
for b, lab in ((0, "roof"), (90, "wall"), (180, "soffit")):
    axs[2].axvline(b, color="#999", lw=0.6, ls=":")
    axs[2].text(b + 2, axs[2].get_ylim()[1] * 0.92, lab, fontsize=7.5, color="#666")
axs[2].set(xlabel="face tilt β from upward (deg)", ylabel="net IR flux q (W m⁻²)", title="Flat-face net emission vs. tilt")
out["tilt"] = {"beta": betas.tolist(), "q": qb}
save(fig, "fig1_sky_tilt.png")
dump("s1_sky.json", out)
print({k: (round(v["eps_sky"], 3), v["crossover_deg"]) for k, v in out["climates"].items()})
print("q(beta) at dT=-10:", np.round(qb[-10][::6], 1), " dT=+10:", np.round(qb[10][::6], 1))
