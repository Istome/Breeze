"""Re-record hourly traces of both finals on the same (base) weather year."""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import ROOT
from breeze.dc.climate_hourly import make_year
from breeze.dc.sim import Sim, Design
OUT = os.path.join(ROOT, "results", "dc")
R = json.load(open(os.path.join(OUT, "generations.json")))
s10 = json.load(open(os.path.join(ROOT, "results", "s10_ground.json")))
sim = Sim(make_year("hot-dry"), ground_T0=24.0, pit_T_far=s10["pit"]["hot-dry"]["T_far_C"], pit_ua_coef=s10["pit"]["hot-dry"]["UA_coef"])
y = sim.y
hw0 = int(np.flatnonzero(y["day"] == 194)[0])
for name in ("cost-optimal", "water-neutral"):
    rr = sim.run(Design(**R["g6_finals"][name]["design"]), record=True)
    rec = rr["rec"]
    H = {k: (np.add.reduceat(v, np.arange(0, 8760, 24)) / 24 / 1000).round(2).tolist() for k, v in rec.items() if not k.startswith(("E", "T"))}
    H["heatwave"] = {k: (rec[k][hw0:hw0 + 6 * 24] / 1000).round(1).tolist() for k in ("w_pass", "w_dry", "w_tank", "w_wet", "w_chil", "c_plate", "c_econ", "c_tank", "c_evap", "c_chil")}
    H["heatwave_T"] = y["T"][hw0:hw0 + 6 * 24].round(1).tolist()
    R["g6_hourly"][name] = H
json.dump(R, open(os.path.join(OUT, "generations.json"), "w"), default=lambda o: o.item() if hasattr(o, "item") else str(o), indent=0)
print("re-recorded")
