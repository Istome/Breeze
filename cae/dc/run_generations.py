"""Round 3: the Zenith Plate as a DATA CENTRE.  Generations 0-6.

Writes results/dc/generations.json and figures results/dc/g*.png.
"""
import json, os, sys, copy, time
from dataclasses import asdict, replace
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import plt, C, ROOT
from breeze.dc.climate_hourly import make_year
from breeze.dc.sim import Sim, Design, PRICE, ROOFS, open_panel, cell_panel, IT_CLASSES
from breeze.dc.evolve import Evolver, paired_test, reoptimise

OUT = os.path.join(ROOT, "results", "dc")
os.makedirs(OUT, exist_ok=True)
SITE_T0 = {"hot-dry": 24.0, "hot-humid": 21.3, "arid": 26.4}
s10 = json.load(open(os.path.join(ROOT, "results", "s10_ground.json")))


def mksim(site, **kw):
    return Sim(make_year(site, **kw), ground_T0=SITE_T0[site], pit_T_far=s10["pit"][site]["T_far_C"], pit_ua_coef=s10["pit"][site]["UA_coef"])


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name), dpi=150, bbox_inches="tight")
    plt.close(fig)


def summary(r):
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k not in ("rec",)}


SITE = "hot-dry"
sim = mksim(SITE)
y = sim.y
REPORT = {"site": SITE, "IT_MW": 1.0, "prices": PRICE, "generations": []}
t0 = time.time()

# ======================================================================= GEN 0
print("GEN 0: port round-2 design, challenge the physics", flush=True)
hw = np.flatnonzero((y["day"] == 195))  # heat-wave day
i_pm, i_am = hw[15], hw[4]
Tgrid = np.linspace(10, 70, 61)
sl = lambda arr, i: {k: (v[i:i + 1] if isinstance(v, np.ndarray) else v) for k, v in y.items()}
skins = {"round-2 skin: selective + film + 100 mm air": lambda yy: cell_panel(yy),
         "open selective": lambda yy: open_panel(yy, "selective"),
         "open PDRC film": lambda yy: open_panel(yy, "PDRC film"),
         "open white paint (broadband)": lambda yy: open_panel(yy, "white paint")}
flux = {}
for hname, i in (("15:00, 46 °C heat wave", i_pm), ("04:00, 32 °C night", i_am)):
    yy = sl(y, i)
    flux[hname] = {k: [float(f(yy)(t)[0]) for t in Tgrid] for k, f in skins.items()}
fig, axs = plt.subplots(1, 2, figsize=(11, 3.8), sharey=True)
for ax, (hname, fl) in zip(axs, flux.items()):
    for j, (k, v) in enumerate(fl.items()):
        ax.plot(Tgrid, v, color=C[j], lw=2.2 if "white" in k else 1.5, label=k)
    ax.axhline(0, color="k", lw=0.8)
    ax.axvspan(45, 60, color="#c9521f", alpha=0.08)
    ax.text(46, ax.get_ylim()[1] * 0.85 if ax.get_ylim()[1] > 0 else 50, "W45 warm loop", fontsize=8, color="#c9521f")
    ax.axvspan(18, 28, color="#2f6fdf", alpha=0.08)
    ax.set(xlabel="panel / coolant temperature (°C)", title=hname)
axs[0].set_ylabel("net heat rejected (W per m² of panel)")
axs[0].legend(fontsize=7.5)
save(fig, "g0_flip.png")
# round-2 design on a 1 MW air-cooled DC
r2 = sim.run(Design(it="Air-cooled", Tc=18, roof="canopy", roof_loop="cool", pit_m3=6000, dc_size=0, econ_size=0))
r2_free = r2["share"]["c_plate"] + r2["share"]["c_pit"]
plate_MWh = r2["heat_MWh"]["c_plate"] + r2["heat_MWh"]["c_pit"]
print(f"  round-2 plate covers {r2_free*100:.1f}% of a 1 MW DC ({plate_MWh:.0f} MWh/yr of {sum(r2['heat_MWh'].values()):.0f})")
REPORT["gen0"] = dict(flux=flux, Tgrid=Tgrid.tolist(), round2_cover=r2_free, round2_plate_MWh=plate_MWh, round2=summary(r2))

# ======================================================================= GEN 1..5
ev = Evolver(sim, seed=5)
ev.elite = [Design(it="Air-cooled", Tw=32, Tc=18, dc_size=1.2)]
GENS = [
    ("G1 Warm water", {
        "it": (["Air-cooled", "D2C 75%"], "Air-cooled"),
        "Tw": ([32.0, 40.0, 45.0], 32.0),
        "Tc": ([18.0, 22.0], 18.0),
        "roof": (["none", "hall roof", "canopy"], "none"),
        "coating": (["white paint", "PDRC film", "selective"], "white paint"),
        "dc_size": ([0.0, 0.6, 0.9, 1.2, 1.5, 2.0], 1.2),
        "adiabatic": ([False, True], False)},
     {"it": "H1.1 Liquid-cool the IT so most heat leaves at 40-55 °C",
      "Tw": "H1.2 The warmer the supply, the cheaper the rejection",
      "Tc": "H1.3 A warmer cool loop (22 °C) cuts chiller energy",
      "roof": "H1.4 Above ambient, a radiator roof on the warm loop pays for itself",
      "coating": "H1.5 Above ambient, broadband paint beats selective or film coatings",
      "dc_size": "H1.6 Dry coolers should be sized for the design heat wave",
      "adiabatic": "H1.7 A little water on peak hours beats a chiller"}),
    ("G2 Time-shifting", {
        "tank_m3": ([0.0, 250.0, 500.0, 1000.0, 2000.0, 3000.0], 0.0),
        "dT": ([10.0, 15.0, 20.0], 10.0),
        "sliding": ([False, True], False)},
     {"tank_m3": "H2.1 A hot-water buffer bridges heat-wave afternoons into the night",
      "dT": "H2.2 A wider temperature rise across the IT raises the mean radiator temperature",
      "sliding": "H2.3 Let the supply temperature slide down when it is cool outside"}),
    ("G3 The forgotten cool loop", {
        "roof_loop": (["warm", "cool"], "warm"),
        "econ_size": ([0.0, 0.5, 1.0, 2.0], 0.0),
        "cold_tank_m3": ([0.0, 250.0, 500.0, 1000.0, 2000.0], 0.0),
        "Tc": ([18.0, 22.0, 26.0], 18.0),
        "evap_cool": ([False, True], False),
        "fin_wall_m2": ([0.0, 720.0], 0.0),
        "roof": (["none", "hall roof", "canopy", "canopy 2-sided"], "none")},
     {"roof_loop": "H3.1 The sky plate belongs on the COOL loop, where it beats a chiller instead of a fan",
      "econ_size": "H3.2 A small economiser dry cooler serves the cool loop most of the year",
      "cold_tank_m3": "H3.3 Night sky + economiser charge a cold tank that covers the day",
      "Tc": "H3.4 Relax the cool loop to 26 °C",
      "evap_cool": "H3.5 Evaporative cooling for the cool loop",
      "fin_wall_m2": "H3.6 Above ambient, a vertical fin wall multiplies radiator area per m² of land",
      "roof": "H3.7 A two-sided canopy doubles the warm radiator"}),
    ("G4 Capture and the ground", {
        "it": (["Air-cooled", "D2C 75%", "D2C + liquid rear-door 85%", "Immersion 95%"], "D2C 75%"),
        "pit_m3": ([0.0, 5000.0, 10000.0, 20000.0], 0.0),
        "bores": ([0, 50, 100, 200], 0),
        "sky_recharge": ([False, True], False)},
     {"it": "H4.1 Capture more heat in liquid (85-95 %) to shrink the cool loop",
      "pit_m3": "H4.2 The round-2 seasonal pit stores winter sky cold for the cool loop",
      "bores": "H4.3 At 45-55 °C, the 24 °C ground becomes a sink",
      "sky_recharge": "H4.4 The roof re-cools the ground every winter so it never saturates"}),
    ("G5 Integration and control", {
        "shift": ([False, True], False),
        "roof": (["none", "hall roof", "hall roof, integrated deck", "canopy", "canopy 2-sided"], "none"),
        "Tc": ([18.0, 22.0, 26.0, 30.0], 18.0)},
     {"shift": "H5.1 Predictive dispatch: throttle fans on hot afternoons, push heat to the buffer, reject it at night",
      "roof": "H5.2 Make the radiator the roof itself (integrated deck) to cut its net cost",
      "Tc": "H5.3 With immersion, electrical rooms can run at 30 °C and lose their chillers"}),
]
for gname, genes, hyps in GENS:
    print(gname, flush=True)
    for g in genes:  # a re-opened gene is un-frozen
        ev.frozen.pop(g, None)
    ev.open_genes(genes)
    rec = ev.run_generation(gname)
    champion = Design(**rec["best"])
    rec["verdict"] = {}
    for g in genes:
        t, better = paired_test(ev, champion, g)
        if ev.cost(better) < ev.cost(champion) - 1e-6:   # the test found a better design: adopt it
            champion = better
        rec["verdict"][g] = dict(hyp=hyps[g], status=t["status"], value=t["value"], gain=round(t["saving_pct"], 2),
                                 cost_on=t["cost_on"], cost_off=t["cost_off"])
        if t["status"] == "refuted":
            ev.frozen[g] = ev.baseline[g]
    champion = reoptimise(ev, champion, None)
    rec["best"] = asdict(champion)
    rec["result"] = ev.evaluate(champion)
    ev.elite = [champion] + [e for e in ev.elite if e.key() != champion.key()][:5]
    r = rec["result"]
    print(f"  best: cost ${r['annual_cost']/1e3:.1f}k/yr capex ${r['capex']/1e3:.0f}k PUEeff {r['PUE_eff']:.3f} WUE {r['WUE']:.3f} evaluated {rec['evaluated']}")
    print("  genes:", {g: rec["best"][g] for g in genes})
    for g, v in rec["verdict"].items():
        print(f"   {v['status']:9s} {v['gain']:7.2f}%  {v['hyp']}  -> {v['value']}  (on ${v['cost_on']/1e3:.1f}k / off ${v['cost_off']/1e3:.1f}k)")
    rec["result"] = summary(r)
    rec["top"] = [(d, c) for d, c in rec["top"]]
    REPORT["generations"].append(rec)

# --- generation-specific CAE
champ = [Design(**g["best"]) for g in REPORT["generations"]]
# G2: buffer size vs warm-loop chiller peak (water-free variant of G1 champion)
base = replace(champ[0], adiabatic=False)
sweep = []
for V in [0, 250, 500, 1000, 1500, 2000, 3000, 4000]:
    rr = sim.run(replace(base, tank_m3=V))
    sweep.append(dict(V=V, chiller_kW=rr["peaks_kW"]["w_chil"], cost=rr["annual_cost"], chiller_MWh=rr["heat_MWh"]["w_chil"]))
dts = []
for dT_ in (6, 8, 10, 12, 15, 20, 25):
    rr = sim.run(replace(champ[1], dT=float(dT_)))
    dts.append(dict(dT=dT_, cost=rr["annual_cost"], pPUE=rr["pPUE"], dry_MWh=rr["heat_MWh"]["w_dry"]))
REPORT["g2_tank_sweep"], REPORT["g2_dT_sweep"] = sweep, dts
# G3/G5: break-even panel cost, re-optimised with and without each roof (all genes open)
be = {}
ev_be = Evolver(sim, seed=2)
allg0 = {}
for _, genes, _ in GENS:
    allg0.update(genes)
ev_be.open_genes(allg0)
c5 = champ[-1]
off = reoptimise(ev_be, replace(c5, roof="none"), "roof")
for loop in ("warm", "cool"):
    for roof in ("hall roof", "hall roof, integrated deck", "canopy", "canopy 2-sided"):
        if loop == "cool" and roof == "canopy 2-sided":
            continue
        ev_be.frozen = {"roof_loop": loop}
        on = reoptimise(ev_be, replace(c5, roof=roof, roof_loop=loop), "roof")
        ron = ev_be.evaluate(on)
        A = ROOFS[roof][0]
        roof_annual = PRICE["crf"] * ron["capex_parts"]["roof"] + (ron["opex"] - (ron["e_cool_kWh"] + ron["extra_it_kWh"]) * PRICE["elec"] - ron["water_m3"] * PRICE["water"])
        saving = ev_be.cost(off) - (ev_be.cost(on) - roof_annual)
        be[f"{roof} on {loop} loop"] = dict(saving_per_yr=saving, breakeven_per_m2=saving / PRICE["crf"] / A,
                                         cost_per_m2=ron["capex_parts"]["roof"] / A, extra_cost_per_yr=ev_be.cost(on) - ev_be.cost(off),
                                         passive_MWh=ron["heat_MWh"]["w_pass"] + ron["heat_MWh"]["c_plate"])
        print(f"  break-even {roof} / {loop}: saves ${saving/1e3:.1f}k/yr -> worth ${saving/PRICE['crf']/A:.0f}/m2 vs cost ${ron['capex_parts']['roof']/A:.0f}/m2")
ev_be.frozen = {}
REPORT["g3_breakeven"] = be
fw = sim.run(replace(champ[2], fin_wall_m2=720.0))
fw0 = sim.run(replace(champ[2], fin_wall_m2=0.0))
REPORT["g3_finwall"] = dict(capex=fw["capex_parts"]["fin"], d_cost=fw["annual_cost"] - fw0["annual_cost"], passive_MWh=fw["heat_MWh"]["w_pass"])
# G4: ground drift over 10 years, with/without sky recharge (hall roof on warm loop)
gd = {}
for rech in (False, True):
    rr = sim.run(replace(champ[3], bores=100, sky_recharge=rech, roof="hall roof", roof_loop="warm", adiabatic=False, tank_m3=0.0), years=10)
    gd["with sky recharge" if rech else "no recharge"] = rr["Tg_trace"]
REPORT["g4_ground"] = gd
# progression over generations
prog = [dict(name="G0 air-cooled + chillers (industry baseline)", **{k: summary(sim.run(Design(it="Air-cooled", Tw=32, Tc=18, dc_size=1.2)))[k] for k in ("annual_cost", "capex", "PUE_eff", "pPUE", "WUE")})]
for g in REPORT["generations"]:
    prog.append(dict(name=g["name"], **{k: g["result"][k] for k in ("annual_cost", "capex", "PUE_eff", "pPUE", "WUE")}))
REPORT["progression"] = prog

# ======================================================================= GEN 6: water-neutral, +2 K
print("G6 Water-neutral desert, +2 K", flush=True)
sim6 = mksim(SITE, warming=2.0)
ev6 = Evolver(sim6, seed=9, fixed={"adiabatic": False, "evap_cool": False})
ev6.elite = [replace(champ[-1], adiabatic=False, evap_cool=False)]
allg = {}
for _, genes, _ in GENS:
    allg.update(genes)
ev6.open_genes(allg)
for g in ("adiabatic", "evap_cool"):
    ev6.space[g] = [False]
g6_genes = {
    "tank_m3": "H6.1 Without water, a hot buffer replaces the peak chiller",
    "roof": "H6.2 Without water, the cold sky beats a chiller on the hottest hours",
    "dc_size": "H6.3 Without water, oversize the dry coolers instead",
    "cold_tank_m3": "H6.4 A cold tank charged at night covers the cool loop's hottest hours",
    "pit_m3": "H6.5 The seasonal pit returns when water is not an option",
    "bores": "H6.6 The ground as a heat-wave sink, re-cooled by the sky",
}
rec6 = ev6.run_generation("G6 Water-neutral, +2 K climate", pop=30, iters=14)
champion = Design(**rec6["best"])
rec6["verdict"] = {}
for g, hyp in g6_genes.items():
    t, better = paired_test(ev6, champion, g)
    if ev6.cost(better) < ev6.cost(champion) - 1e-6:
        champion = better
    rec6["verdict"][g] = dict(hyp=hyp, status=t["status"], value=t["value"], gain=round(t["saving_pct"], 2), cost_on=t["cost_on"], cost_off=t["cost_off"])
    print(f"   {t['status']:9s} {t['saving_pct']:7.2f}%  {hyp} -> {t['value']}  (on ${t['cost_on']/1e3:.1f}k / off ${t['cost_off']/1e3:.1f}k)")
champion = reoptimise(ev6, champion, None)
rec6["best"], rec6["result"] = asdict(champion), summary(ev6.evaluate(champion))
print("  best:", {k: v for k, v in rec6["best"].items() if v != getattr(Design(), k)}, round(rec6["result"]["annual_cost"] / 1e3, 1), rec6["result"]["PUE_eff"])
REPORT["generations"].append(rec6)
REPORT["progression"].append(dict(name="G6 Water-neutral, +2 K climate", **{k: rec6["result"][k] for k in ("annual_cost", "capex", "PUE_eff", "pPUE", "WUE")}))

# ======================================================================= GEN 7: robustness + selection
print("G7 robustness", flush=True)
final = champ[-1]
finals = {"cost-optimal": final, "water-neutral": Design(**rec6["best"])}
finals["sky-max"] = replace(finals["water-neutral"], roof="canopy", roof_loop="cool", cold_tank_m3=max(finals["water-neutral"].cold_tank_m3, 1000.0))
rob = {}
rng = np.random.default_rng(3)
keys = ["elec", "water", "dc_kw", "chiller_kw", "tank_m3", "pit_m3", "bore_m", "cells_m2"]
for name, d in finals.items():
    base_r = sim.run(d)
    stress = {}
    stress["base"] = base_r["annual_cost"]
    stress["water $10/m³"] = (base_r["annual_cost"] + base_r["water_m3"] * 7.0)
    stress["electricity $0.15/kWh"] = base_r["annual_cost"] + (base_r["e_cool_kWh"] + base_r["extra_it_kWh"]) * 0.07
    stress["dust (+0.10 solar absorptance)"] = sim.run(replace(d, soiling=0.10))["annual_cost"]
    warm = mksim(SITE, warming=2.0)
    stress["climate +2 K"] = warm.run(d)["annual_cost"]
    # Monte Carlo over prices +-30 %
    mc = []
    orig = dict(PRICE)
    for _ in range(60):
        for k in keys:
            PRICE[k] = orig[k] * rng.uniform(0.7, 1.3)
        mc.append(sim.run(d)["annual_cost"])
    PRICE.update(orig)
    stress["MC p10"], stress["MC p50"], stress["MC p90"] = np.percentile(mc, [10, 50, 90]).tolist()
    rob[name] = dict(design=asdict(d), result=summary(base_r), stress=stress)
    print(f"  {name:12s}", {k: round(v / 1e3, 1) for k, v in stress.items()})
REPORT["g6_finals"] = rob
# other climates: re-optimise from the final elite
sites = {}
for st in ("hot-humid", "arid"):
    s2 = mksim(st)
    e2 = Evolver(s2, seed=4)
    e2.elite = [finals["cost-optimal"], finals["water-neutral"]]
    e2.open_genes(allg)
    r_ = e2.run_generation(f"G6 {st}", pop=26, iters=10)
    sites[st] = dict(best=r_["best"], result=summary(r_["result"]))
    print(f"  {st}: ${r_['result']['annual_cost']/1e3:.1f}k PUEeff {r_['result']['PUE_eff']:.3f} WUE {r_['result']['WUE']:.3f}", {k: v for k, v in r_["best"].items() if v != getattr(Design(), k)})
REPORT["g6_sites"] = sites
# scale: 0.5-10 MW with the same plot
scale = []
for P in (0.5e6, 1e6, 2e6, 5e6, 10e6):
    for name in ("water-neutral", "sky-max"):
        rr = sim.run(replace(finals[name], P_IT=P, tank_m3=finals[name].tank_m3 * P / 1e6, cold_tank_m3=finals[name].cold_tank_m3 * P / 1e6))
        scale.append(dict(P_MW=P / 1e6, variant=name, PUE_eff=rr["PUE_eff"], cost_per_kW=rr["annual_cost"] / (P / 1000),
                          passive_share=rr["share"]["w_pass"] + rr["share"]["c_plate"]))
REPORT["g6_scale"] = scale
# hourly record of the cost-optimal and water-free finals for plots
for name in ("cost-optimal", "water-neutral"):
    rr = (sim if name == "cost-optimal" else sim6).run(finals[name], record=True)
    rec = rr["rec"]
    REPORT.setdefault("g6_hourly", {})[name] = {k: (np.add.reduceat(v, np.arange(0, 8760, 24)) / 24 / 1000).round(2).tolist() for k, v in rec.items() if not k.startswith(("E", "T"))}
    REPORT["g6_hourly"][name]["T_daily_max"] = np.maximum.reduceat(y["T"], np.arange(0, 8760, 24)).round(1).tolist()
    REPORT["g6_hourly"][name]["heatwave"] = {k: (v[hw[0]-24:hw[0]+5*24] / 1000).round(1).tolist() for k, v in rec.items() if k in ("w_dry", "w_tank", "w_wet", "w_chil", "w_pass", "c_plate", "c_econ", "c_tank", "c_chil", "c_evap")}
    REPORT["g6_hourly"][name]["heatwave_T"] = y["T"][hw[0]-24:hw[0]+5*24].round(1).tolist()
    REPORT["g6_hourly"][name]["Ew"] = (rec["Ew"][hw[0]-24:hw[0]+5*24] / 1e6).round(2).tolist()
print(f"done in {time.time()-t0:.0f}s")


def default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


json.dump(REPORT, open(os.path.join(OUT, "generations.json"), "w"), default=default, indent=0)
