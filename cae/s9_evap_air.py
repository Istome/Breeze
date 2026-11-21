"""CAE-9  Evaporation and airflow as additional sinks.

(a) Sink-temperature map: for every month and site, the temperatures each sink can
    deliver water/air at: sky (effective radiative sink of the plate), wet-bulb
    (+3 K tower approach), night air (+2 K), deep soil (10 m).
(b) Design-day capacity per m2 of the alternatives at T_w = 20 C:
    - wetted open plate (water film on a white broadband emitter, no screen)
    - closed-circuit evaporative cooler (indirect, no humidity added indoors)
    - night-flush ventilation of building mass (buoyancy stack)
    - passive downdraft evaporative cooling (PDEC) tower
    with water consumption.
"""
import numpy as np
from common import plt, save, dump, C
from breeze.physics import Climate, Surface, flat_solar, SIGMA, flat_net_ir
from breeze.psychro import wet_bulb, w_sat, CP_AIR, H_FG, sky_emissivity_berdahl, tau0_for_emissivity
from breeze.climate_year import SITES, MONTHS, month_hours, soil_temperature, MONTH_DOY
from breeze.climate_day import ambient_profile
from scipy.optimize import brentq

hours = np.arange(0, 24, 0.5) + 0.25
LE23 = 0.85 ** (2 / 3)


def wet_plate_flux(Ts, Ta, Tdp, clim, G, wind=2.5, surf=Surface(0.96, 0.96, 0.10)):
    """Open wetted plate: radiation + convection + evaporation (Lewis analogy)."""
    hc = 2.8 + 3.0 * wind
    q_rad = flat_net_ir([0, 0, 1], Ts, clim, surf)
    q_evap = hc / (CP_AIR * LE23) * max(w_sat(Ts) - w_sat(Tdp), 0.0) * H_FG
    return q_rad + q_evap - hc * (Ta - Ts) - surf.alpha_sol * G, q_evap


def sky_sink_temp(Ta, tau0):
    """Stagnation temperature of the round-2 plate (selective, 100 mm still-air gap, night)."""
    clim = Climate(T_amb=Ta, tau0=tau0)
    s = Surface(0.95, 0.15, 0.05)
    U = 1 / (0.1 / 0.026 + 1 / 10.3) + 0.2
    f = lambda Ts: 0.85 * flat_net_ir([0, 0, 1], Ts, clim, s) - U * (Ta - Ts)
    return brentq(f, Ta - 60, Ta + 5)


# (a) monthly sink temperatures
sinks = {}
for site, s in SITES.items():
    rec = {k: [] for k in ("air_min", "air_mean", "wb_min", "wb_mean", "sky_stag_night", "soil10", "soil3")}
    for m in range(12):
        Ta = month_hours(site, m, hours)
        wb = np.array([wet_bulb(t, s["Tdp"][m]) for t in Ta])
        eps = sky_emissivity_berdahl(s["Tdp"][m], cloud=s["cloud"][m])
        tau0 = tau0_for_emissivity(eps, float(Ta.mean()))
        rec["air_min"].append(Ta.min() - 273.15)
        rec["air_mean"].append(Ta.mean() - 273.15)
        rec["wb_min"].append(wb.min() - 273.15)
        rec["wb_mean"].append(wb.mean() - 273.15)
        rec["sky_stag_night"].append(sky_sink_temp(Ta.min(), tau0) - 273.15)
        rec["soil10"].append(float(soil_temperature(site, 10, MONTH_DOY[m])) - 273.15)
        rec["soil3"].append(float(soil_temperature(site, 3, MONTH_DOY[m])) - 273.15)
    sinks[site] = rec
    print(site, {k: np.round(v, 1).tolist() for k, v in rec.items()})

# (b) design-day capacities at T_w = 20 C
DD = {"hot-dry": dict(tau0=0.75, Tmin=297.15, Tmax=311.15, Tdp=276.15),
      "hot-humid": dict(tau0=0.55, Tmin=299.15, Tmax=306.15, Tdp=296.15)}
Tw = 293.15
dd = {}
for site, sp in DD.items():
    clim = Climate(tau0=sp["tau0"])
    Ta = ambient_profile(hours, sp["Tmin"], sp["Tmax"])
    q_wet, q_ev, wb = [], [], []
    for h, ta in zip(hours, Ta):
        clim.T_amb = clim.T_ground = ta
        q, qe = wet_plate_flux(Tw + 0.5, ta, sp["Tdp"], clim, flat_solar([0, 0, 1], clim, h))
        q_wet.append(q); q_ev.append(qe if q > 0 else 0.0)
        wb.append(wet_bulb(ta, sp["Tdp"]))
    q_wet, wb = np.array(q_wet), np.array(wb)
    E_wet = np.clip(q_wet, 0, None).sum() * 0.5 / 1000
    water_wet = np.sum(q_ev) * 0.5 * 3600 / H_FG  # kg/m2/day
    tower_hours = float(np.sum(wb + 3.0 <= Tw) * 0.5)
    # night flush: stack-driven, 6 ACH equivalent when T_a <= 23 C into a 25 C space, per m2 floor (4.2 m storey)
    vent = np.clip(298.15 - Ta, 0, None) * (Ta <= 296.15)
    E_flush = 1.2 * CP_AIR * 6 * 4.2 / 3600 * vent.sum() * 0.5 / 1000  # kWh/m2 floor/day (before mass cap)
    # PDEC: 10 m tower, supply at Ta - 0.8 (Ta - Twb); buoyant velocity; capacity per m2 tower section into 25 C room
    Tsup = Ta - 0.8 * (Ta - wb)
    v = np.sqrt(np.clip(2 * 9.81 * 10 * (Ta - Tsup) / Ta, 0, None)) * 0.6
    P_pdec = 1.2 * CP_AIR * v * np.clip(298.15 - Tsup, 0, None)  # W per m2 of tower section
    dd[site] = {"wet_plate_kWh": E_wet, "wet_plate_water_kg": water_wet, "wet_q_hourly": q_wet.tolist(),
                "wb_hourly": (wb - 273.15).tolist(), "Ta_hourly": (Ta - 273.15).tolist(), "tower_hours": tower_hours,
                "flush_kWh_per_m2floor": E_flush, "pdec_kWh_per_m2tower": float(P_pdec.sum() * 0.5 / 1000),
                "pdec_peak_W_per_m2tower": float(P_pdec.max()), "pdec_supply_min_C": float(Tsup.min() - 273.15)}
    print(site, {k: (round(v, 2) if isinstance(v, float) else "...") for k, v in dd[site].items()})

dump("s9_evap_air.json", {"sinks": sinks, "design_day": dd, "months": MONTHS})

fig, axs = plt.subplots(1, 4, figsize=(16, 3.8))
for k, site in enumerate(SITES):
    r = sinks[site]
    x = np.arange(12)
    for j, (key, lab) in enumerate((("sky_stag_night", "sky (plate stagnation, night)"), ("wb_min", "wet-bulb, night"),
                                    ("wb_mean", "wet-bulb, 24 h mean"), ("air_min", "air, night min"), ("soil10", "soil, 10 m"))):
        axs[k].plot(x, r[key], marker="o", ms=3, color=C[j], label=lab)
    axs[k].axhspan(16, 21, color="#1a9e75", alpha=0.10)
    axs[k].text(0.2, 16.4, "radiant loop 16–21 °C", fontsize=7, color="#1a9e75")
    axs[k].set(xticks=x, xticklabels=[m[0] for m in MONTHS], ylabel="°C", title=f"Sink temperatures, {site}")
axs[0].legend(fontsize=6.5)
for j, site in enumerate(DD):
    axs[3].plot(hours, dd[site]["wet_q_hourly"], color=C[j], label=f"wet plate, {site}")
axs[3].axhline(0, color="k", lw=0.8)
axs[3].set(xlabel="hour", ylabel="W m⁻²", title="Wetted open plate at T_w = 20 °C")
axs[3].legend(fontsize=7)
save(fig, "fig9_sinks.png")
