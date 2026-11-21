"""CAE-11  Year-round performance with every added variable, as a cumulative stack:

S0  round-1 design: 26 mm film cells (U 2.5 as assumed in round 1), one exposed storey,
    diurnal tank only
S1  + 100 mm still-air cells (CAE-8)
S2  + programme sunk 4.5 m under a thick earth vault, earth-tube fresh air (CAE-10)
S3  + stack-driven night flush of the massive interior (airflow)
S4  + seasonal pit under the plate (deep subterranean store, CAE-10)
S5  + evaporative trim and evaporative pit charging (water, CAE-9)
Then: how many storeys can each configuration carry with zero backup cooling?
"""
import numpy as np
from common import plt, save, dump, C
from breeze.physics import Climate, Surface, flat_solar
from breeze.psychro import wet_bulb, w_sat, sky_emissivity_berdahl, tau0_for_emissivity, H_FG
from breeze.climate_year import SITES, MONTHS, MONTH_DOY, DAYS, month_hours, soil_temperature
from breeze.annual import simulate
from breeze.cover import Cover
import importlib.util, os, json

spec = importlib.util.spec_from_file_location("s8", os.path.join(os.path.dirname(__file__), "s8_cover.py"))
# reuse RibGapPlate without re-running s8: copy minimal class
from breeze.raytrace import funnel_cell, net_ir
from breeze.physics import band_emissive_power


class FilmSky:
    def __init__(self, clim, tau, Tf):
        self.c, self.tau, self.Tf = clim, tau, Tf
    def env_radiance(self, d):
        LW, LNW = self.c.env_radiance(d)
        BW, BNW = band_emissive_power(self.Tf)
        return self.tau * LW + (1 - self.tau) * BW / np.pi, self.tau * LNW + (1 - self.tau) * BNW / np.pi


class RibGapPlate:
    def __init__(self, surf, g, U=None, pitch=0.30):
        t = pitch / 2
        self.cell = funnel_cell(t - 1e-4, t, g)
        self.s, self.cov = surf, Cover("film", g)
        self.U = U if U is not None else 1.0 / (g / 0.026 + 1.0 / self.cov.h_out) + 0.2
    def flux(self, Ts, Ta, clim, G):
        clim.T_amb = clim.T_ground = Ta
        q_ir = net_ir(self.cell, Ts, FilmSky(clim, 0.85, Ta - 1.0), self.s, 0.98, 12000)
        return q_ir - self.s.alpha_sol * 0.92 * G * 1.02 - self.U * (Ta - Ts)


sel = Surface(0.95, 0.15, 0.05)
SKINS = {"26 mm film cells (round 1)": RibGapPlate(sel, 0.026, U=2.5), "100 mm still-air cells": RibGapPlate(sel, 0.10)}
SKINS.update({f"gap{g}": RibGapPlate(sel, g / 1000) for g in (26, 50, 75, 150)})
hours = np.arange(0, 24, 1.0) + 0.5
T_IN, A_FOOT, PERIM, H_ST, PLATE = 25.0, 2160.0, 192.0, 4.2, 3456.0
T_DIRECT, T_CHARGE = 19.5, 15.0

data = {"months": MONTHS, "days": DAYS.tolist(), "sites": {}}
for site, S in SITES.items():
    sd = {"plate": {}, "loads": {}}
    # ---- sinks: plate capacity per m2 per day by month
    for sk, plate in SKINS.items():
        cdir, cch = [], []
        for m in range(12):
            Ta = month_hours(site, m, hours)
            eps = sky_emissivity_berdahl(S["Tdp"][m], cloud=S["cloud"][m])
            clim = Climate(tau0=tau0_for_emissivity(eps, float(Ta.mean())), lat_deg=S["lat"])
            vals = {}
            for Tw in (T_DIRECT, T_CHARGE):
                q = [plate.flux(Tw + 273.15 + 0.5, ta, clim, flat_solar([0, 0, 1], clim, h, MONTH_DOY[m]) * (1 - 0.6 * S["cloud"][m]))
                     for h, ta in zip(hours, Ta)]
                vals[Tw] = float(np.clip(q, 0, None).sum() / 1000)
            cdir.append(vals[T_DIRECT]); cch.append(vals[T_CHARGE])
        sd["plate"][sk] = {"direct": cdir, "charge": cch}
        print(site, sk, "direct", np.round(cdir, 2), "charge", np.round(cch, 2), flush=True)
    # ---- evaporative availability (fraction of hours wb + 3 K below target)
    ev, evc, wbm = [], [], []
    for m in range(12):
        Ta = month_hours(site, m, hours)
        wb = np.array([wet_bulb(t, S["Tdp"][m]) for t in Ta]) - 273.15
        ev.append(float(np.mean(wb + 3 <= T_DIRECT))); evc.append(float(np.mean(wb + 3 <= T_CHARGE))); wbm.append(float(wb.mean()))
    sd["evap_avail"], sd["evap_charge_avail"], sd["wb_mean"] = ev, evc, wbm
    # ---- loads per configuration: sunk (0/1), flush (0/1), storeys 1..4  -> daily sensible kWh
    def loads(sunk, flush, N):
        out, lat = [], []
        for m in range(12):
            Ta = month_hours(site, m, hours) - 273.15
            Tm = Ta.mean(); Tocc = Ta[8:20].mean()
            soil = lambda z: float(soil_temperature(site, z, MONTH_DOY[m])) - 273.15
            A = A_FOOT * N
            q_int = 0.20 * A
            UA_T = 0.0  # W, envelope
            if not sunk:
                UA_T += 0.25 * PERIM * H_ST * (Tm - T_IN) + 0.20 * A_FOOT * (Tm - T_IN)
                for i in range(1, N):  # basements
                    UA_T += 0.30 * PERIM * H_ST * (soil(i * H_ST + H_ST / 2) - T_IN)
                UA_T += 0.30 * A_FOOT * (soil(max(1.0, (N - 1) * H_ST + 0.5)) - T_IN)
                mass_cap = 0.12
            else:
                UA_T += 0.13 * A_FOOT * 1.15 * (Tm - T_IN)  # earth vault + PIR, 15 % extra curved area
                for i in range(N):
                    UA_T += 0.30 * PERIM * H_ST * (soil(0.6 + i * H_ST + H_ST / 2) - T_IN)
                UA_T += 0.30 * A_FOOT * (soil(0.6 + N * H_ST) - T_IN)
                mass_cap = 0.25
            q_env = UA_T * 24 / 1000
            Vdot = 0.8e-3 * A  # m3/s fresh air
            Tpre = Tocc - (0.7 * (Tocc - soil(3.0)) if sunk else 0.0)
            q_vent = 1.2 * 1006 * Vdot * (1 - 0.75) * (Tpre - T_IN) * 12 / 1000
            w_in = w_sat(T_IN + 273.15) * 0.5
            q_lat = max(0.0, 1.2 * Vdot * (w_sat(SITES[site]["Tdp"][m]) - w_in) * H_FG * (1 - 0.6) * 12 / 1000)
            net = q_int + q_env + q_vent
            if flush and net > 0:
                pot = 1.2 * 1006 * 6 * (H_ST * A) / 3600 * np.clip(T_IN - Ta, 0, None) * (Ta <= T_IN - 2)
                net -= min(pot.sum() / 1000, mass_cap * A, net)
            out.append(float(net)); lat.append(q_lat)
        return out, lat
    for sunk in (0, 1):
        for flush in (0, 1):
            for N in (1, 2, 3, 4):
                l, lat = loads(sunk, flush, N)
                sd["loads"][f"{sunk}{flush}{N}"] = l
                sd.setdefault("latent", {})[str(N)] = lat
    import json as _j
    g = _j.load(open(os.path.join(os.path.dirname(__file__), "..", "results", "s10_ground.json")))
    sd["pit_UA_coef"], sd["T_far"] = g["pit"][site]["UA_coef"], g["pit"][site]["T_far_C"]
    data["sites"][site] = sd

# ---- scenario stack
SC = [("S0 round-1 design", dict(skin="26 mm film cells (round 1)", sunk=0, flush=0, pit=0, evap=False)),
      ("S1 + 100 mm still-air cells", dict(skin="100 mm still-air cells", sunk=0, flush=0, pit=0, evap=False)),
      ("S2 + sunk under thick earth vault", dict(skin="100 mm still-air cells", sunk=1, flush=0, pit=0, evap=False)),
      ("S3 + night-flush stack", dict(skin="100 mm still-air cells", sunk=1, flush=1, pit=0, evap=False)),
      ("S4 + 20,000 m³ seasonal pit", dict(skin="100 mm still-air cells", sunk=1, flush=1, pit=20000, evap=False)),
      ("S5 + evaporative trim", dict(skin="100 mm still-air cells", sunk=1, flush=1, pit=20000, evap=True))]


def run(site, cfg, N):
    sd = data["sites"][site]
    p = sd["plate"][cfg["skin"]]
    return simulate(np.array(p["direct"]), np.array(p["charge"]), np.array(sd["loads"][f"{cfg['sunk']}{cfg['flush']}{N}"]),
                    PLATE, cfg["pit"], sd["pit_UA_coef"], sd["T_far"], sd["evap_avail"], sd["evap_charge_avail"], cfg["evap"],
                    latent=np.array(sd["latent"][str(N)]) if cfg.get("latent") else None)


results = {}
CFG = {
    "A  round-1 design": dict(skin="26 mm film cells (round 1)", sunk=0, flush=0, pit=0, evap=False),
    "B  + 100 mm still-air cells": dict(skin="100 mm still-air cells", sunk=0, flush=0, pit=0, evap=False),
    "C  + sunk, thick vault, night flush": dict(skin="100 mm still-air cells", sunk=1, flush=1, pit=0, evap=False),
    "D  C + evaporative trim (water)": dict(skin="100 mm still-air cells", sunk=1, flush=1, pit=0, evap=True),
    "E  C + 20,000 m³ seasonal pit": dict(skin="100 mm still-air cells", sunk=1, flush=1, pit=20000, evap=False),
    "F  E, pit also dehumidifies fresh air": dict(skin="100 mm still-air cells", sunk=1, flush=1, pit=20000, evap=False, latent=True),
}
for site in SITES:
    results[site] = {}
    for name, cfg in CFG.items():
        results[site][name] = []
        for N in (1, 2, 3, 4):
            tot, mon = run(site, cfg, N)
            water = (tot["evap"] + tot["charge_evap"]) * 3.6e6 / H_FG * 1.2 / 1000
            r = {"N": N, "load_MWh": tot["load"] / 1e3, "coverage": 1 - tot["unmet"] / tot["load"], "unmet_MWh": tot["unmet"] / 1e3,
                 "latent_MWh": tot["latent"] / 1e3, "latent_unmet_MWh": tot["latent_unmet"] / 1e3,
                 "direct_MWh": tot["direct"] / 1e3, "pit_MWh": tot["pit"] / 1e3, "evap_MWh": tot["evap"] / 1e3,
                 "water_m3": water, "monthly": mon}
            results[site][name].append(r)
        print(f"{site:9s} {name:38s} unmet MWh N=1..4:", [round(r["unmet_MWh"], 1) for r in results[site][name]],
              "lat unmet:", [round(r["latent_unmet_MWh"], 1) for r in results[site][name]],
              " water m3:", [round(r["water_m3"]) for r in results[site][name]], " load MWh:", [round(r["load_MWh"]) for r in results[site][name]])
    for key, cname in (("_pit_needed", "E  C + 20,000 m³ seasonal pit"), ("_pit_needed_with_latent", "F  E, pit also dehumidifies fresh air")):
        need = {}
        for N in (1, 2, 3, 4):
            need[N] = None
            for V in (0, 1000, 2000, 3000, 4000, 6000, 8000, 10000, 12500, 15000, 20000, 25000, 30000, 40000, 60000):
                cfg = dict(CFG[cname]); cfg["pit"] = V
                t2, _ = run(site, cfg, N)
                if t2["unmet"] <= 0.005 * t2["load"] and t2["latent_unmet"] <= 0.005 * max(t2["latent"], 1):
                    need[N] = V
                    break
        results[site + key] = need
        print(site, key, need)
    lat = np.array(data["sites"][site]["latent"]["1"]) * DAYS
    results[site + "_latent_MWh_1storey"] = float(lat.sum() / 1e3)
    print(site, "latent (1 storey, ERV 0.6):", round(lat.sum() / 1e3, 1), "MWh")

data["scenarios"] = list(CFG)
dump("s11_annual.json", {"inputs": data, "results": results})

# figure: cae/fig11_annual.py
