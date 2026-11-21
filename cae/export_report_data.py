"""Collect compact series from the CAE result files for the interactive report."""
import json, os
import numpy as np
from common import RES

L = lambda n: json.load(open(os.path.join(RES, n)))
r = lambda a, k=1: [round(float(x), k) for x in a]
s1, s2, s3, s4, s5, s6, s7 = (L(f) for f in ("s1_sky.json", "s2_massing.json", "s3_cells.json", "s4_panel_fea.json",
                                              "s5_structure.json", "s6_designday.json", "s7_camber.json"))
th = s1["theta_deg"][::4]
out = {
    "sky": {"theta": r(th, 0), "dL": {k: r(v[::4]) for k, v in s1["climates"]["tau0.75"]["dL"].items()},
            "eps_sky": {k: round(v["eps_sky"], 3) for k, v in s1["climates"].items()},
            "crossover": {k: {"dT": r(v["crossover_curve"]["dT"][::2], 1), "th": r(v["crossover_curve"]["theta0"][::2], 1)}
                          for k, v in s1["climates"].items()}},
    "tilt": {"beta": r(s1["tilt"]["beta"], 0), "q": {k: r(v) for k, v in s1["tilt"]["q"].items()}},
    "massing": [{"shape": x["shape"], "A_env": round(x["A_env"]), "A_foot": round(x["A_foot"]), "H": round(x["H"], 1),
                 "sub": round(x["sub-ambient (ΔT=−8 K)"]["P_mean_kW"], 1), "above": round(x["above-ambient (ΔT=+15 K)"]["P_mean_kW"], 1),
                 "sub_env": round(x["sub-ambient (ΔT=−8 K)"]["per_env"], 1), "sub_foot": round(x["sub-ambient (ΔT=−8 K)"]["per_foot"], 1),
                 "above_env": round(x["above-ambient (ΔT=+15 K)"]["per_env"], 1), "above_foot": round(x["above-ambient (ΔT=+15 K)"]["per_foot"], 1)}
                for x in s2["rows"]],
    "cells": {"dT": s3["dT"], "thetas": s3["thetas"],
              "q": {key: {c: r(v) for c, v in cells.items()} for key, cells in s3["cells"].items()},
              "angular": {k: {"th": r(v[0], 1), "eps": r(v[1], 3)} for k, v in s3["angular"].items()},
              "solar_daily_Wh": {k: round(v["daily_abs_Wh"]) for k, v in s3["solar"].items() if isinstance(v, dict)}},
    "fea": {k: {"pitch": v["pitch"], "eta": r(v["eta"], 3), "dT": r(v["dT_max"], 2)} for k, v in s4.items()},
    "structure": {k: v for k, v in s5.items() if k != "tiles"},
    "day": {"Tw": s6["Tw_C"], "hours": r(s6["hours"], 2),
            "sites": {sn: {"T_amb": r(np.array(sv["T_amb"]) - 273.15),
                           "systems": {k: {"daily": r(np.array(v["daily_Wh_vs_Tw"]) / 1000, 3), "hourly": r(v["q_hourly_Tw20"])}
                                       for k, v in sv["systems"].items()}} for sn, sv in s6["sites"].items()}},
    "camber": {"ratio": s7["rise_over_span"], "cases": {k: r(v) for k, v in s7["cases"].items()}},
}
json.dump(out, open(os.path.join(RES, "report_data.json"), "w"), separators=(",", ":"), ensure_ascii=False)
print(os.path.getsize(os.path.join(RES, "report_data.json")), "bytes")
print(json.dumps(out["structure"], indent=0)[:900])

# ------------------------------------------------------------------ round 2
import os.path as _p
if all(_p.exists(_p.join(RES, f)) for f in ("s8_cover.json", "s9_evap_air.json", "s10_ground.json", "s11_annual.json")):
    s8, s9, s10, s11 = (L(f) for f in ("s8_cover.json", "s9_evap_air.json", "s10_ground.json", "s11_annual.json"))
    inp = s11["inputs"]
    skin_keys = {"r1": "26 mm film cells (round 1)", 26: "gap26", 50: "gap50", 75: "gap75", 100: "100 mm still-air cells", 150: "gap150"}
    r2 = {
        "cover": {sn: {k: {"daily": r(v["daily"], 3), "U": round(v["U"], 2)} for k, v in sv.items()} for sn, sv in s8["sites"].items()},
        "cover_Tw": s8["Tw"],
        "cover_hourly": {sn: {k: r(sv[k]["hourly_Tw20"]) for k in ("film + 26 mm still-air gap", "film + 100 mm still-air gap", "aerogel 6 mm")}
                         for sn, sv in s8["sites"].items()},
        "sinks": {site: {k: r(v) for k, v in rec.items()} for site, rec in s9["sinks"].items()},
        "dd_evap": {site: {k: (round(v, 2) if isinstance(v, float) else None) for k, v in rec.items() if not isinstance(v, list)}
                    for site, rec in s9["design_day"].items()},
        "pit": {site: {"T_far": round(v["T_far_C"], 1), "rows": [{k: round(x[k], 1) for k in ("V", "R", "UA_W_K", "E_cap_MWh", "loss_MWh_yr")} for x in v["rows"]]}
                for site, v in s10["pit"].items()},
        "dome": s10["dome"],
        "annual": {"days": inp["days"], "sites": {}},
        "results": {},
    }
    for site, sd in inp["sites"].items():
        r2["annual"]["sites"][site] = {
            "plate": {str(g): {"direct": r(sd["plate"][k]["direct"], 3), "charge": r(sd["plate"][k]["charge"], 3)} for g, k in skin_keys.items()},
            "loads": {k: r(v, 1) for k, v in sd["loads"].items()},
            "latent": {k: r(v, 1) for k, v in sd["latent"].items()},
            "evap_avail": r(sd["evap_avail"], 3), "evap_charge_avail": r(sd["evap_charge_avail"], 3),
            "ua_coef": round(sd["pit_UA_coef"], 3), "T_far": round(sd["T_far"], 2),
        }
        res = s11["results"]
        r2["results"][site] = {
            "cfg": {name: [{k: round(x[k], 3) for k in ("N", "load_MWh", "unmet_MWh", "direct_MWh", "pit_MWh", "evap_MWh", "water_m3", "latent_MWh", "latent_unmet_MWh")}
                           for x in rows] for name, rows in res[site].items()},
            "pit_needed": res[site + "_pit_needed"], "pit_needed_latent": res[site + "_pit_needed_with_latent"],
            "latent_1": round(res[site + "_latent_MWh_1storey"], 1),
        }
    out["r2"] = r2
    json.dump(out, open(os.path.join(RES, "report_data.json"), "w"), separators=(",", ":"), ensure_ascii=False)
    print("with round 2:", os.path.getsize(os.path.join(RES, "report_data.json")), "bytes")
