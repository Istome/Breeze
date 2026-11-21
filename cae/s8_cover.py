"""CAE-8  Insulating covers over the plate: thick aerogel vs. a deeper still-air gap.

(a) Polyethylene-aerogel covers 3-40 mm on a flat selective emitter (analytic
    directional model, breeze.cover).
(b) 12 um LDPE film over a still-air gap of depth g held by vertical Al ribs at
    300 mm pitch.  Under a cold emitter the gap is stably stratified, so it
    conducts (k/g) instead of convecting; deeper ribs cost sky view, which the
    Monte-Carlo tracer measures (film transmittance enters the environment
    radiance seen through the cell aperture).
Design days of CAE-6.
"""
import numpy as np
from common import plt, save, dump, C
from breeze.physics import Climate, Surface, flat_solar
from breeze.cover import Cover, CoveredPlate
from breeze.climate_day import ambient_profile
from breeze.raytrace import funnel_cell, net_ir
from breeze.physics import band_emissive_power, SIGMA


class FilmSky:
    """Environment as seen through a film of IR transmittance tau at T_f."""
    def __init__(self, clim, tau, Tf):
        self.c, self.tau, self.Tf = clim, tau, Tf
    def env_radiance(self, d):
        LW, LNW = self.c.env_radiance(d)
        BW, BNW = band_emissive_power(self.Tf)
        return self.tau * LW + (1 - self.tau) * BW / np.pi, self.tau * LNW + (1 - self.tau) * BNW / np.pi


class RibGapPlate:
    """Film over a still-air gap of depth g; ribs = vertical specular walls (MC)."""
    def __init__(self, surf, g, pitch=0.30, U_factor=1.0, leak=0.2):
        t = pitch / 2
        self.cell = funnel_cell(t - 1e-4, t, g)
        self.s, self.g = surf, g
        self.cov = Cover("film", g)
        self.U = (1.0 / (g / 0.026 + 1.0 / self.cov.h_out)) * U_factor + leak
    def flux(self, Ts, Ta, clim, G_sun=0.0):
        clim.T_amb = clim.T_ground = Ta
        q_ir = net_ir(self.cell, Ts, FilmSky(clim, self.cov.tau_film, Ta - 1.0), self.s, 0.98, 12000)
        return q_ir - self.s.alpha_sol * self.cov.tau_film_sol * G_sun * 1.02 - self.U * (Ta - Ts)

SITES = {"hot-dry": dict(tau0=0.75, Tmin=297.15, Tmax=311.15), "hot-humid": dict(tau0=0.55, Tmin=299.15, Tmax=306.15)}
sel, bb = Surface(0.95, 0.15, 0.05), Surface(0.96, 0.90, 0.04)
hours = np.arange(0, 24, 0.5) + 0.25
Tws = np.array([14, 16, 18, 20, 22, 24]) + 273.15
thick = [0.003, 0.006, 0.010, 0.020]
gaps = [0.010, 0.026, 0.050, 0.075, 0.100, 0.150]


def day_energy(plate, sp, Tw, record=False):
    clim = Climate(tau0=sp["tau0"])
    Ta = ambient_profile(hours, sp["Tmin"], sp["Tmax"])
    q = np.array([plate.flux(Tw + 0.5, ta, clim, flat_solar([0, 0, 1], clim, h)) for h, ta in zip(hours, Ta)])
    return (q if record else None), float(np.clip(q, 0, None).sum() * 0.5)


out = {"Tw": (Tws - 273.15).tolist(), "thick_mm": [t * 1e3 for t in thick], "sites": {}}
for sn, sp in SITES.items():
    rec = {}
    for label, plate in [(f"film + {g*1e3:.0f} mm still-air gap", RibGapPlate(sel, g)) for g in gaps] + \
                        [("film + 50 mm gap, U×2 (flutter)", RibGapPlate(sel, 0.050, U_factor=2.0))] + \
                        [(f"aerogel {t*1e3:.0f} mm", CoveredPlate(sel, Cover("aerogel", t))) for t in thick]:
        daily = [day_energy(plate, sp, Tw)[1] / 1000 for Tw in Tws]
        qh, _ = day_energy(plate, sp, 293.15, True)
        U = plate.U if hasattr(plate, "g") else plate.c.U()
        rec[label] = {"daily": daily, "hourly_Tw20": qh.tolist(), "U": U}
        print(f"{sn:9s} {label:34s} U={U:5.2f}", np.round(daily, 3), flush=True)
    out["sites"][sn] = rec

# optimum thickness vs dT at night (no sun) and at noon (G = 950 W/m2), dry sky
clim = Climate(tau0=0.75)
tgrid = np.linspace(0.001, 0.05, 50)
dTs = [-5, -10, -15, -20]
opt = {}
for cond, G in (("night", 0.0), ("noon", 950.0)):
    opt[cond] = {}
    for dT in dTs:
        q = [CoveredPlate(sel, Cover("aerogel", t), 30, 48).flux(303.15 + dT, 303.15, clim, G) for t in tgrid]
        opt[cond][dT] = {"q": q, "t_opt_mm": float(tgrid[int(np.argmax(q))] * 1e3), "q_max": float(max(q))}
        print(cond, dT, "t_opt", round(opt[cond][dT]["t_opt_mm"], 1), "mm  q", round(max(q), 1))
out["opt"] = {"t_mm": (tgrid * 1e3).tolist(), **opt}
dump("s8_cover.json", out)

fig, axs = plt.subplots(1, 3, figsize=(12.5, 3.8))
for k, sn in enumerate(SITES):
    for j, Tw in enumerate((18, 20, 22)):
        i = out["Tw"].index(Tw)
        axs[0].plot([g * 1e3 for g in gaps], [out["sites"][sn][f"film + {g*1e3:.0f} mm still-air gap"]["daily"][i] for g in gaps],
                    marker="o", ms=3, color=C[j], ls="-" if k == 0 else "--", label=f"{sn} T_w={Tw} °C")
        axs[0].axhline(out["sites"][sn]["aerogel 6 mm"]["daily"][i], color=C[j], lw=0.6, ls=":")
axs[0].set(xlabel="still-air gap / rib height (mm)", ylabel="kWh m⁻² day⁻¹", title="Gap depth optimum (dotted: 6 mm aerogel)")
axs[0].legend(fontsize=6.3)
for k, sn in enumerate(SITES):
    for i, (lab, r) in enumerate(out["sites"][sn].items()):
        if lab.startswith("aerogel") and lab not in ("aerogel 3 mm", "aerogel 40 mm"):
            pass
        axs[1 + k].plot(out["Tw"], r["daily"], marker="o", ms=2.5, color=C[i % len(C)], label=lab,
                        lw=2.6 if lab == "film + 26 mm gap (round 1)" else 1.4)
    axs[1 + k].set(xlabel="loop water T_w (°C)", ylabel="kWh m⁻² day⁻¹", title=sn)
axs[2].legend(fontsize=6.3)
save(fig, "fig8_cover.png")
