"""CAE-6  Design-day performance of complete roof systems.

Each system: radiation (MC cell optics) + absorbed sun (MC) + convection, with an
optional 12 um LDPE wind-screen carried on the cell rims.  The plate is fed by a
water loop at T_w; the emitter runs 0.5 K above T_w (see CAE-4).  A controller
only circulates when the plate is a net sink, charging the buried tank.
"""
import numpy as np
from common import plt, save, dump, C
from breeze.physics import Climate, Surface, SIGMA
from breeze.raytrace import flat_cell, funnel_cell, net_ir, solar_absorbed
from breeze.climate_day import ambient_profile

R_IR, R_SOL, NR = 0.98, 0.97, 16000
TAU_F, TAU_F_SOL = 0.85, 0.92
SITES = {
    "hot-dry (τ₀=0.75, 24–38 °C)": dict(tau0=0.75, Tmin=297.15, Tmax=311.15),
    "hot-humid (τ₀=0.55, 26–33 °C)": dict(tau0=0.55, Tmin=299.15, Tmax=306.15),
}


def funnel(th):
    th = np.radians(th)
    t = 0.5
    e = t * np.sin(th)
    return funnel_cell(e, t, (t + e) / np.tan(th))


SYSTEMS = {
    "Dark membrane roof": dict(cell=flat_cell(), surf=Surface(0.9, 0.9, 0.80), film=False),
    "White roof (open)": dict(cell=flat_cell(), surf=Surface(0.90, 0.90, 0.20), film=False),
    "PDRC flat (open)": dict(cell=flat_cell(), surf=Surface(0.96, 0.90, 0.04), film=False),
    "PDRC flat + film": dict(cell=flat_cell(), surf=Surface(0.96, 0.90, 0.04), film=True),
    "Selective flat + film": dict(cell=flat_cell(), surf=Surface(0.95, 0.15, 0.05), film=True),
    "Zenith cell 60° PDRC + film": dict(cell=funnel(60), surf=Surface(0.96, 0.90, 0.04), film=True),
    "Zenith cell 60° selective + film": dict(cell=funnel(60), surf=Surface(0.95, 0.15, 0.05), film=True),
    "Zenith cell 75° selective + film": dict(cell=funnel(75), surf=Surface(0.95, 0.15, 0.05), film=True),
    "Rib grid 85° selective + film (final)": dict(cell=funnel(85), surf=Surface(0.95, 0.15, 0.05), film=True),
}
hours = np.arange(0, 24, 0.5) + 0.25
wind = 2.5  # m/s


def system_flux(sysd, clim, Tw, h, Ta):
    Ts = Tw + 0.5
    cell, s = sysd["cell"], sysd["surf"]
    clim.T_amb = clim.T_ground = Ta
    q_rad = net_ir(cell, Ts, clim, s, R_IR, NR)
    sun, dni, dhi = clim.sun(h)
    key = ("sol", round(h, 3))
    cache = cell.__dict__.setdefault("_sol", {})
    if (key, s.alpha_sol) not in cache:
        frac = solar_absorbed(cell, sun, s.alpha_sol, R_SOL, 5000) if sun[2] > 0 else 0.0
        cache[(key, s.alpha_sol)] = frac
    frac = cache[(key, s.alpha_sol)]
    diff_fac = 1.0 if cell.kind == "flat" else 1.6
    q_sun = frac * dni * max(sun[2], 0) + s.alpha_sol * diff_fac * dhi
    if sysd["film"]:
        Tf = Ta - 2.0
        eps_eff = 0.5 * (s.eps_W + s.eps_NW)
        q = TAU_F * q_rad + (1 - TAU_F) * eps_eff * SIGMA * (Ts**4 - Tf**4) - TAU_F_SOL * q_sun - 2.5 * (Ta - Ts)
    else:
        hc = 2.8 + 3.0 * wind
        q = q_rad - q_sun - hc * (Ta - Ts)
    return q


out = {"hours": hours.tolist(), "sites": {}}
fig, axs = plt.subplots(1, 3, figsize=(12.5, 3.8))
Tws = np.array([16, 18, 20, 22, 24, 26]) + 273.15
for si, (sname, sp) in enumerate(SITES.items()):
    clim = Climate(tau0=sp["tau0"])
    Ta = ambient_profile(hours, sp["Tmin"], sp["Tmax"])
    rec = {"T_amb": Ta.tolist(), "systems": {}}
    for k, (name, sysd) in enumerate(SYSTEMS.items()):
        daily = []
        for Tw in Tws:
            q = np.array([system_flux(sysd, clim, Tw, h, ta) for h, ta in zip(hours, Ta)])
            daily.append(float(np.clip(q, 0, None).sum() * 0.5))  # Wh/m2/day, controller on only when sink
            if abs(Tw - 293.15) < 0.1:
                rec["systems"].setdefault(name, {})["q_hourly_Tw20"] = q.tolist()
        rec["systems"][name]["daily_Wh_vs_Tw"] = daily
        print(f"{sname[:9]} {name:34s}", np.round(np.array(daily) / 1000, 3), "kWh/m2/d @Tw", (Tws - 273.15).astype(int), flush=True)
        if si == 0:
            axs[0].plot(hours, rec["systems"][name]["q_hourly_Tw20"], label=name, color=C[k % len(C)],
                        ls="-" if k < 6 else ("--" if k < 8 else "-"), lw=1.4)
        axs[1 + si].plot(Tws - 273.15, np.array(daily) / 1000, marker="o", ms=3, color=C[k % len(C)],
                         ls="-" if k < 6 else ("--" if k < 8 else "-"), label=name)
    out["sites"][sname] = rec
    axs[1 + si].set(xlabel="loop water temperature T_w (°C)", ylabel="heat rejected (kWh m⁻² day⁻¹)", title=sname)
axs[0].axhline(0, color="k", lw=0.8)
axs[0].set(xlabel="hour", ylabel="net cooling (W m⁻²)", title="Hot-dry day, T_w = 20 °C", ylim=(-150, 80))
axs[2].legend(fontsize=6.5, loc="upper left")
out["Tw_C"] = (Tws - 273.15).tolist()
save(fig, "fig6_designday.png")
dump("s6_designday.json", out)
