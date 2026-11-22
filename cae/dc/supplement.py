"""Supplementary checks: (a) buffer vs chiller at several dry-cooler sizes (fair
version of the G2 sweep), (b) where the sky radiator deck would win."""
import json, os, sys
from dataclasses import replace
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import ROOT
from breeze.dc.climate_hourly import make_year
from breeze.dc.sim import Sim, Design, PRICE
from breeze.dc.evolve import Evolver, reoptimise

OUT = os.path.join(ROOT, "results", "dc")
R = json.load(open(os.path.join(OUT, "generations.json")))
s10 = json.load(open(os.path.join(ROOT, "results", "s10_ground.json")))
mk = lambda **kw: Sim(make_year("hot-dry", **kw), ground_T0=24.0, pit_T_far=s10["pit"]["hot-dry"]["T_far_C"], pit_ua_coef=s10["pit"]["hot-dry"]["UA_coef"])
sim = mk()
g1 = Design(**R["generations"][0]["best"])
tank = {}
for dc in (0.9, 1.2, 1.5, 2.0):
    rows = []
    for V in (0, 250, 500, 1000, 2000, 4000):
        r = sim.run(replace(g1, adiabatic=False, dc_size=dc, tank_m3=float(V)))
        rows.append(dict(V=V, chiller_kW=r["peaks_kW"]["w_chil"], cost=r["annual_cost"]))
    tank[str(dc)] = rows
    print("dc", dc, [(x["V"], round(x["chiller_kW"]), round(x["cost"] / 1e3, 1)) for x in rows])
# where would the integrated radiator deck win?  (water-neutral final, re-optimising dry coolers + buffer)
wn = Design(**R["g6_finals"]["water-neutral"]["design"])
window = []
for warm_K in (0.0, 2.0, 4.0):
    s = sim if warm_K == 0 else mk(warming=warm_K)
    for elec in (0.08, 0.15, 0.25):
        PRICE["elec"] = elec
        ev = Evolver(s, seed=1)
        ev.open_genes({"dc_size": ([0.6, 0.9, 1.2, 1.5, 2.0], 1.2), "tank_m3": ([0.0, 250.0, 500.0, 1000.0], 0.0), "econ_size": ([0.5, 1.0, 2.0], 1.0)})
        off = reoptimise(ev, replace(wn, roof="none"), None)
        on = reoptimise(ev, replace(wn, roof="hall roof, integrated deck", roof_loop="warm", coating="white paint"), None)
        ron = ev.evaluate(on)
        deck_annual = PRICE["crf"] * ron["capex_parts"]["roof"] + 2160 * 0.5
        value = ev.cost(off) - (ev.cost(on) - deck_annual)
        window.append(dict(warming=warm_K, elec=elec, breakeven_per_m2=value / PRICE["crf"] / 2160, value_per_yr=value))
        print(f"  +{warm_K} K, ${elec}/kWh: deck worth ${value/PRICE['crf']/2160:.0f}/m2 (cost $40)")
PRICE["elec"] = 0.08
R["supp_tank"] = tank
R["supp_window"] = window
json.dump(R, open(os.path.join(OUT, "generations.json"), "w"), default=lambda o: o.item() if hasattr(o, "item") else str(o), indent=0)
