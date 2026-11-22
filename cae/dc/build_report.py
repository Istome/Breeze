"""Assemble the round-3 Markdown report from results/dc/generations.json."""
import json, os, shutil, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import ROOT
from breeze.dc.sim import Design, PRICE, ROOFS

R = json.load(open(os.path.join(ROOT, "results", "dc", "generations.json")))
DOC = os.environ.get("DC_DOC_DIR", os.path.join(ROOT, "docs", "dc_report"))
SRC = os.environ.get("DC_FIG_DIR", os.path.join(ROOT, "results", "dc"))
os.makedirs(os.path.join(DOC, "fig"), exist_ok=True)
for f in os.listdir(SRC):
    if f.startswith("d_") and f.endswith(".png"):
        shutil.copy(os.path.join(SRC, f), os.path.join(DOC, "fig", f))
G = {g["name"].split(" ")[0]: g for g in R["generations"]}
prog = R["progression"]
base, opt = prog[0], R["g6_finals"]["cost-optimal"]["result"]
wn = R["g6_finals"]["water-neutral"]["result"]
fin = R["g6_finals"]
k = lambda v: f"${v/1e3:,.1f}k"
DEF = Design()


def active(d):
    out = []
    for key, v in d.items():
        if key in ("P_IT", "soiling"):
            continue
        if key in ("roof_loop", "coating") and d.get("roof", "none") == "none":
            continue
        if key == "sky_recharge" and not d.get("bores"):
            continue
        label = {"it": "IT cooling", "Tw": "warm supply (°C)", "dT": "warm rise across IT (K)", "Tc": "cool-loop supply (°C)", "roof": "radiator roof",
                 "roof_loop": "roof serves", "coating": "roof coating", "dc_size": "dry coolers (× warm load)", "adiabatic": "adiabatic pads",
                 "tank_m3": "hot buffer (m³)", "bores": "boreholes", "sky_recharge": "sky re-cools ground", "econ_size": "cool economiser (× cool load)",
                 "cold_tank_m3": "cold tank (m³)", "pit_m3": "seasonal pit (m³)", "evap_cool": "evaporative cool loop", "fin_wall_m2": "fin wall (m² land)",
                 "shift": "predictive dispatch", "sliding": "sliding supply"}[key]
        if isinstance(v, bool):
            v = "yes" if v else "no"
        elif isinstance(v, float) and v == int(v):
            v = int(v)
        out.append((label, v))
    return out


def gene_table(d):
    rows = active(d)
    s = "| Gene | Value |\n|---|---|\n"
    return s + "\n".join(f"| {a} | {b} |" for a, b in rows) + "\n"


def verdict_table(g):
    s = "| Hypothesis | Verdict | Best value | With idea | Without | Saving |\n|---|---|---|---|---|---|\n"
    for gene, v in g["verdict"].items():
        mark = {"confirmed": "**confirmed**", "refuted": "refuted", "marginal": "no effect"}[v["status"]]
        s += f"| {v['hyp']} | {mark} | {v['value']} | {k(v['cost_on'])} | {k(v['cost_off'])} | {v['gain']:+.1f} % |\n"
    return s


def metrics(r):
    return (f"annualised cooling cost **{k(r['annual_cost'])}/yr** (capital {k(r['capex'])}), effective PUE **{r['PUE_eff']:.3f}**, "
            f"cooling-only PUE {r['pPUE']:.3f}, WUE **{r['WUE']:.3f} L/kWh**")


f0 = R["gen0"]["flux"]
T0 = R["gen0"]["Tgrid"]
q = lambda h, s, t: f0[h][s][T0.index(t)]
H_PM, H_AM = list(f0)
be = R["g3_breakeven"]
sup_t = R["supp_tank"]
win = R["supp_window"]
sites = R["g6_sites"]
sc = R["g6_scale"]
gd = R["g4_ground"]
fw = R["g3_finwall"]
water_m3 = opt["WUE"] * 8760
cnt = {"confirmed": 0, "refuted": 0, "marginal": 0}
for g in R["generations"]:
    for v in g.get("verdict", {}).values():
        cnt[v["status"]] += 1
NH = sum(cnt.values())
w_break = 3.0 + (wn["annual_cost"] - opt["annual_cost"]) / max(opt["water_m3"], 1)
saved_GWh = (base["PUE_eff"] - opt["PUE_eff"]) * 8.76

md = f"""# Zenith DC

## Evolutionary redesign of the radiative building as a data centre

**Round 3 report** · Breeze project · 22 November 2026 · reference load 1 MW IT on the 72 × 48 m Zenith Plate site (hot-dry, Phoenix-like), checked in hot-humid and arid climates.

> **Bottom line.** Housing a data centre flips the physics the Zenith Plate was built on. Liquid-cooled servers return their heat at 40–65 °C, above the outdoor air almost all year. Every surface and fan then becomes a sink, and the cold sky loses its special status. Over seven generations and about 3,000 simulated designs, the evolutionary search kept warm water and dropped the radiative roof. Its winner cuts the annualised cooling cost from {k(base['annual_cost'])} to {k(opt['annual_cost'])} per year (−{(1-opt['annual_cost']/base['annual_cost'])*100:.0f} %). Effective PUE falls from {base['PUE_eff']:.3f} to {opt['PUE_eff']:.3f}, and water use is {opt['WUE']:.2f} L per kWh of IT. A water-neutral variant reaches PUE {wn['PUE_eff']:.3f} with zero water for {k(wn['annual_cost'])}/yr.

---

## Executive summary

**The brief.** Re-run the whole analysis with the building housing a data centre and challenge everything. Remove what isn't practical. Propose new hypotheses in every generation, test them, and breed the best ideas forward for at least five generations.

**What was done.** A new hourly simulator covers both coolant loops of a data centre for a full year, including a design heat wave. It counts capital cost, fan, pump and chiller energy, extra IT power and water. Seven generations ran on it:

- **G0** challenged and pruned the round-1 and round-2 concepts.
- **G1–G6** each added 3–7 new hypotheses as "genes", ran a genetic algorithm over the expanded design space, then tested every hypothesis fairly. A fair test means the best design with the idea against the best design without it, everything else re-optimised in both cases.
- **G7** stress-tested the finalists.

In all, {NH} hypotheses were tested: {cnt['confirmed']} were confirmed, {cnt['refuted']} refuted and {cnt['marginal']} had no measurable effect in context.

**What survived and won**

| | Air-cooled baseline | **Zenith DC, cost-optimal** | **Zenith DC, water-neutral** |
|---|---|---|---|
| IT cooling | air + chilled water 18 °C | immersion, 95 % of heat to liquid | immersion, 95 % |
| Warm loop | — | 32–45 °C sliding supply, +20 K | same |
| Heat rejection | chillers | dry coolers + adiabatic pads on peaks | dry coolers + 250 m³ hot-water buffer |
| Electrical rooms | 18 °C chilled water | 30 °C loop: economiser + evaporative | 30 °C loop: economiser + small chiller |
| Effective PUE | {base['PUE_eff']:.3f} | **{opt['PUE_eff']:.3f}** | **{wn['PUE_eff']:.3f}** |
| Water (L/kWh IT) | {base['WUE']:.2f} | {opt['WUE']:.2f} (≈ {water_m3:,.0f} m³/yr) | 0.00 |
| Annualised cooling cost | {k(base['annual_cost'])}/yr | **{k(opt['annual_cost'])}/yr** | {k(wn['annual_cost'])}/yr |
| Capital cost | {k(base['capex'])} | {k(opt['capex'])} | {k(wn['capex'])} |

Against the baseline, the cost-optimal design saves about **{saved_GWh:.1f} GWh of electricity a year per MW of IT**.

**What did not survive.** The radiative roof was tested six separate ways: on the warm loop, on the cool loop, two-sided, as a fin wall, as an integrated roof deck, and in a water-free hotter future. It never paid. Re-optimised, a square metre of sky radiator is worth **$9–32** to a 1 MW data centre, against an installed cost of **$40–430**. The closest call is a radiator built in as the roof deck on the warm loop, worth $32/m² against $40/m². The ground, the seasonal pit, the cold tank, the predictive controller and the vertical fin wall were all refuted on cost.

![Generation-by-generation progress: annualised cost, effective PUE and water use](fig/d_progression.png)

---

## 1. What changes when the building is a data centre

**Scale.** One megawatt of IT produces {8.76:.2f} GWh of heat a year, about 24 MWh every day, at every hour. In round 2 the whole 3,456 m² plate moved between about 1 and 7 MWh a day to the sky at 19.5 °C water, depending on the month. Ported unchanged (G0), the round-2 design covers only **{R['gen0']['round2_cover']*100:.1f} %** of a 1 MW air-cooled data centre's heat ({R['gen0']['round2_plate_MWh']:,.0f} of 9,461 MWh a year).

**Temperature.** Modern liquid cooling (cold plates or immersion) lets the coolant leave the IT at 40–65 °C, while chips stay within limits. That temperature is above the outdoor air for almost every hour of a Phoenix year. Figure 1 shows the consequence.

![Figure 1: Net heat rejected per m² of panel vs. panel temperature, on the 46 °C heat-wave afternoon (left) and at night (right). The round-2 skin (film over still air) wins only below the air temperature (blue band); in the W45 warm-loop band (orange) an open broadband panel rejects 2–3× more.](fig/d_flip.png)

At a 55 °C panel on the heat-wave afternoon:

| Panel | Net heat rejected |
|---|---|
| Round-2 film skin | {q(H_PM,'round-2 skin: selective + film + 100 mm air',55.0):.0f} W/m² |
| Open selective panel | {q(H_PM,'open selective',55.0):.0f} W/m² |
| Open PDRC film | {q(H_PM,'open PDRC film',55.0):.0f} W/m² |
| Open white paint | {q(H_PM,'open white paint (broadband)',55.0):.0f} W/m² |

At night the open broadband panels reach {q(H_AM,'open white paint (broadband)',55.0):.0f} W/m². The film and still-air layer that won round 2 now **blocks** the convection that has become useful.

**Reliability.** A data centre must reject 100 % of its heat in the worst hour of the worst heat wave (designed here at 46 °C, four days), with redundant equipment. All active equipment is costed with a 20 % redundancy margin (N+1). Any heat no other sink can take falls to a chiller, which is sized for the worst hour and costed accordingly.

**Metrics.** Four are used:

- **Cooling-only PUE:** 1 + cooling energy ÷ IT energy.
- **Effective PUE:** cooling-only PUE plus the extra IT power that cooling choices cause (server fans, chip leakage at warmer coolant). It compares air and liquid cooling fairly.
- **WUE:** litres of water evaporated per kWh of IT.
- **Annualised cooling cost:** capital × 0.1098 (7 %, 15 years), plus energy at $0.08/kWh, water at $3/m³ and coating upkeep. This is the fitness the evolution minimises.

---

## 2. Method

### 2.1 Weather

A synthetic hourly year was built for each site from the monthly normals used in round 2. It adds:

- day-to-day temperature noise;
- clear and cloudy days drawn from monthly cloud fractions;
- wind with a daily cycle;
- the sun's position;
- the two-band infrared sky (window transmittance from the Berdahl–Martin emissivity and a cloud correction);
- an explicit four-day design heat wave in mid-July, peaking at 46 °C for hot-dry, 39 °C for hot-humid and 47 °C for arid.

The hot-dry year has 218 hours above 40 °C and 1,084 above 35 °C.

### 2.2 Two-loop heat-rejection simulator

The **warm loop** carries the heat captured by liquid cooling (fraction *f* of IT). It is supplied at *T*<sub>s</sub> (W32, W40 or W45) and returns at *T*<sub>s</sub> + Δ*T*. The **cool loop** carries the rest: residual air-side IT heat plus electrical and UPS losses (4 % of IT). It is supplied at 18–30 °C and returns 6 K warmer. Each hour, heat passes through the sinks in priority order:

- **Passive panels** (roof, canopy, fin wall) are treated as heat exchangers. Their surface flux is linearised each hour as *q* = *b*(*T* − *T*<sub>eq</sub>), so a field of area *A* cooling a stream of capacity rate *C* rejects exactly *Q* = *C*(*T*<sub>in</sub> − *T*<sub>eq</sub>)(1 − e<sup>−*bA*/*C*</sup>). The flux includes two-band sky radiation, wind and natural convection, and absorbed sun.
- **Dry coolers:** capacity *G*(*T*<sub>mean water</sub> − *T*<sub>air</sub>). Fan power follows speed³, and capacity follows speed<sup>0.7</sup>. Rated fan power is 1.8 % of rated heat.
- **Adiabatic pads** cool the inlet air to *T* − 0.8(*T* − *T*<sub>wb</sub>), and the water evaporated is counted (×1.25 for bleed).
- **Hot buffer (warm loop) and cold tank (cool loop):** stratified water. They absorb deficits and are emptied or charged with spare capacity.
- **Seasonal pit:** charged at 12–20 °C. Its soil losses come from the round-2 transient study.
- **Borehole field:** a lumped ground node of 120 m boreholes, with far-field recovery and optional sky recharge from spare roof capacity.
- **Evaporative cooler** (cool loop): used when the wet-bulb is at least 4 K below the loop.
- **Air-cooled chiller:** COP = 0.4 × Carnot, between evaporator (*T*<sub>s</sub> − 5) and condenser (*T*<sub>air</sub> + 15), clipped to 2–8.

Pumps take 0.8 % of IT, plus a share of passive and storage flows. CRAH fans take 4 % of the air-side heat. IT-side effects: server fans run at 4 % of IT for air cooling and 0.5–2 % for liquid cooling, and chip leakage adds 0.1 % per K of supply above 30 °C (an assumption).

### 2.3 Cost assumptions (indicative, US 2026, installed)

| Item | Price |
|---|---|
| Electricity / water | ${PRICE['elec']}/kWh · ${PRICE['water']}/m³ |
| Dry cooler / adiabatic kit | ${PRICE['dc_kw']:.0f} / ${PRICE['adiab_kw']:.0f} per kW rated |
| Air-cooled chiller / evaporative cooler | ${PRICE['chiller_kw']:.0f} / ${PRICE['evap_kw']:.0f} per kW |
| Water tank / seasonal pit | ${PRICE['tank_m3']:.0f}/m³ + $20k / ${PRICE['pit_m3']:.0f}/m³ |
| Boreholes | ${PRICE['bore_m']:.0f} per metre |
| Radiator panels: hall roof / integrated deck / canopy | $120 / $40 / $320 per m² (+$15 for two-sided) |
| Round-2 cool skin (selective + film cells) | +$110/m², film upkeep $3/m²/yr |
| IT-side premium vs. cold plates 75 % | air −$60, rear-door 85 % +$40, immersion 95 % +$150 per kW IT |
| Redundancy on active plant · capital recovery | ×1.2 · 0.1098/yr (7 %, 15 years) |

These are planning-level figures. Generation 7 shows the ranking survives ±30 % on all of them together.

### 2.4 Evolutionary search

A design is a set of genes, the fields of the `Design` record in `breeze/dc/sim.py`. Each generation runs the same steps:

1. **Open new genes**, which are that generation's hypotheses.
2. **Seed** the population with the previous elite, every single-gene variant of it, and random designs.
3. **Evolve:** 14 iterations of tournament selection, uniform crossover, 18 % mutation and an elite of four; then a coordinate-descent polish.
4. **Test each hypothesis fairly.** The best design *with* the idea (each non-baseline value, all other genes re-optimised) is compared with the best design *without* it (re-optimised the same way).
5. **Score it.** Saving above 0.5 % is *confirmed* and the idea reproduces. Below −0.5 % is *refuted* and the gene is frozen ("pruned"); it can only come back if a later generation re-opens it as a new hypothesis. In between is *no effect*.

The first pass used a simpler single-gene ablation, which was unfair to ideas that only pay when another gene changes too. A roof that allows smaller dry coolers is the example. The paired test replaced it. Across the seven generations about 3,000 distinct designs were simulated.

![GA convergence: best (solid) and elite mean (dotted) annualised cost in each generation](fig/d_convergence.png)

---

## 3. Generation 0: challenge and prune

Every concept from rounds 1 and 2 was put to one question: does it still make physical and practical sense when the heat is 1 MW, continuous, and at 40–65 °C?

| Concept | Verdict | Why |
|---|---|---|
| Comfort loop at 16–21 °C | **removed** | Liquid cooling moves most of the heat to 40–65 °C. Keeping cold water for everything throws away the main advantage. |
| Film over 100 mm still-air cells | **removed** | Above air temperature, convection is a sink, not a leak (Figure 1). A 12 µm film also lasts only about 1–3 years in Phoenix UV and dust, which is unacceptable for mission-critical cooling. |
| Window-selective coating | **removed (warm loop)** | Above ambient every infrared band helps. Broadband paint or PDRC film emits more. |
| Sunk storeys + earth vault | **removed** | Envelope gains are under 1 % of a 1 MW IT load. Excavation (~35,000 m³), flood and access risk buy nothing. |
| Night-flush stacks, earth tubes | **removed** | Liquid-cooled IT does not need outdoor air; desert dust and smoke harm electronics. |
| Mirror funnels | **removed** | Already refuted in round 1; they are also dust traps. |
| Radiator roof, canopy, fin wall | **kept for re-test** | Above ambient they become ordinary heat exchangers with free sky radiation. Tested in G1, G3, G5, G6. |
| Seasonal pit, ground, storage | **kept for re-test** | The roles change: the ground becomes a *sink* for 45–55 °C water. Tested in G2, G4, G6. |
| Air cooling with chillers | **baseline** | The industry reference the evolution must beat: effective PUE {base['PUE_eff']:.3f}, {k(base['annual_cost'])}/yr. |

---

## 4. Generation 1: warm water

The seed was the air-cooled baseline. The new genes were the IT cooling method, warm-loop supply temperature, cool-loop supply, radiator roof and its coating, dry-cooler size and adiabatic pads. {G['G1']['evaluated']} designs were evaluated.

{verdict_table(G['G1'])}
**Champion:** {metrics(G['G1']['result'])}.

**Reading.** Liquid cooling is the single biggest lever in the whole study, a 59 % cost saving. Once heat leaves at 45–55 °C, dry coolers reject it with fans drawing about 1 % of the heat, and a few hundred litres of water on the hottest afternoons replace a {G['G1']['verdict']['adiabatic']['cost_off']/1e3:.0f}k$/yr chiller-sized design.

The radiator roof on the warm loop is refuted, at −24 %. It saves fan energy worth almost nothing and cannot shrink the dry coolers, because on the 46 °C afternoon it delivers only a fraction of its night-time output.

The coating test shows "no effect" because, with no roof in the winning design, the coating changes nothing. Its physics is settled by Figure 1: a broadband emitter beats a selective one above ambient. PDRC film beats white paint in the sun, but costs more and degrades.

**Reproduces:** liquid cooling, W45, a warmer cool loop, adiabatic peak shaving. **Pruned:** the warm radiator roof.

---

## 5. Generation 2: time-shifting

Confirmed warm water leads to the next question: can heat be moved in time and temperature? {G['G2']['evaluated']} designs evaluated in total.

{verdict_table(G['G2'])}
**Champion:** {metrics(G['G2']['result'])}.

**Reading.** A larger temperature rise across the IT (20 K) and a supply temperature that slides down to 32 °C in cool weather both pay. The first raises the mean water temperature in the dry coolers. The second cuts chip leakage for most of the year.

The hot-water buffer is refuted *here* only because water is cheap and the adiabatic pads already cover the peak. Figure 2 (left) shows the buffer's real condition. It replaces the peak chiller only when the dry coolers have spare night-time capacity to empty it. With coolers at 1.5–2× load, 500 m³ removes the warm-loop chiller entirely. This finding returns in G6.

![Figure 2: Left, warm-loop chiller still needed vs. buffer size, for four dry-cooler sizes, with no water. Right, cost vs. temperature rise across the IT.](fig/d_g2.png)

**Reproduces:** 20 K rise, sliding supply. **Pruned for now:** the buffer.

---

## 6. Generation 3: the forgotten cool loop

After G2 the warm loop is nearly free. Most of the remaining cost sits in the **cool loop**: residual air-side heat and electrical losses that need 18–22 °C water, which means chillers. This generation returns the sky plate to the job it was designed for, sub-ambient cooling. {G['G3']['evaluated']} designs evaluated in total.

{verdict_table(G['G3'])}
**Champion:** {metrics(G['G3']['result'])}.

**Reading.** Relaxing the cool loop to 26 °C (ASHRAE's recommended inlet range for the residual air-side IT) is worth 32 %. An economiser dry cooler plus an evaporative cooler then remove most chiller hours. The sky plate, the cold tank, the two-sided canopy and the fin wall all lose on capital cost.

The fin wall would reject {fw['passive_MWh']/1000:.1f} GWh a year passively, but its {k(fw['capex'])} of wetted panels add {k(fw['d_cost'])}/yr. A fan-blown dry cooler does the same job with about 1 % of the metal.

The break-even study (Figure 3) re-optimises the whole design with and without each roof. It measures what each square metre of sky radiator is worth to a 1 MW data centre.

![Figure 3: Installed cost vs. break-even value of each radiator option, re-optimised (1 MW, hot-dry)](fig/d_breakeven.png)

| Option | Installed $/m² | Worth $/m² | Passive heat (MWh/yr) |
|---|---|---|---|
""" + "\n".join(f"| {key} | {v['cost_per_m2']:.0f} | {v['breakeven_per_m2']:.0f} | {v['passive_MWh']:,.0f} |" for key, v in be.items()) + f"""

**Reproduces:** 26 °C cool loop, economiser, evaporative cooling. **Pruned:** sky plate (both loops), cold tank, fin wall, two-sided canopy.

---

## 7. Generation 4: capture more, and try the ground

The confirmed "shrink the cool loop" result leads to capturing more heat in liquid. The warm loop's 45–65 °C also makes the 24 °C ground a sink for the first time. {G['G4']['evaluated']} designs evaluated in total.

{verdict_table(G['G4'])}
**Champion:** {metrics(G['G4']['result'])}.

**Reading.** Immersion (95 % of heat to liquid) beats cold plates even after a $150/kW IT-side premium. It would still win at a premium of up to about $220/kW. The ground is refuted: 100 boreholes cost about $660k and are only called on in peak hours. They barely warm in ten years (Figure 4) because they are hardly used. Sky recharge cools the field by about 1 K, but recharge has no value if the field is never short. The round-2 seasonal pit is refuted for the same reason: it would store cold for a loop that hardly needs it any more.

![Figure 4: Borehole-field temperature over ten years, with and without winter sky recharge](fig/d_ground.png)

**Reproduces:** immersion. **Pruned:** pit, boreholes, sky recharge.

---

## 8. Generation 5: integration and control

{G['G5']['evaluated']} designs evaluated in total.

{verdict_table(G['G5'])}
**Champion:** {metrics(G['G5']['result'])}.

**Reading.** With immersion, the cool loop is mostly electrical-room heat, and electrical rooms can run at 30 °C. That removes the last chiller, worth 15 %. Making the radiator the roof itself, crediting about $80/m² of membrane and insulation, brings it closest to paying, at −5.6 %, but still not. Predictive fan throttling has no effect because there is no buffer to defer heat into.

**Champion genes (cost-optimal finalist):**

{gene_table(G['G5']['best'])}
---

## 9. Generation 6: water-neutral desert, +2 K climate

Arizona data centres face growing pressure on water. This generation removes water from the design entirely, warms the climate by 2 K, and re-opens the sky, storage and ground hypotheses in that harsher setting.

{verdict_table(G['G6'])}
**Champion (+2 K climate):** {metrics(G['G6']['result'])}.

**Reading.** Without water, the **hot buffer comes back and is confirmed** (+9.4 %). 250 m³ of stratified water absorbs heat-wave afternoons, and dry coolers at 1.2× load plus a 2× economiser empty it at night.

Even here, with no water and a hotter climate, the sky loses (−9.7 % for the best roof option). So do the cold tank, the pit and the ground. Oversizing the dry coolers without a buffer is slightly worse than the buffer.

**Champion genes (water-neutral finalist):**

{gene_table(G['G6']['best'])}
---

## 10. Generation 7: robustness and selection

Three finalists were stress-tested on the base climate:

- **cost-optimal** (G5);
- **water-neutral** (G6);
- **sky-max**: the water-neutral design with the maximum radiative build-out, a 3,456 m² canopy of round-2 cool cells plus a 1,000 m³ cold tank. It shows what the sky would cost.

![Figure 5: Stress tests. Bars: single-factor stresses. Points: p10–p50–p90 of a Monte-Carlo over all prices ±30 %.](fig/d_robust.png)

| Stress | Cost-optimal | Water-neutral | Sky-max |
|---|---|---|---|
""" + "\n".join(f"| {c} | {k(fin['cost-optimal']['stress'][c])} | {k(fin['water-neutral']['stress'][c])} | {k(fin['sky-max']['stress'][c])} |" for c in fin["cost-optimal"]["stress"]) + f"""

The cost-optimal design stays cheapest under every stress, including water at $10/m³ ({k(fin['cost-optimal']['stress']['water $10/m³'])} against {k(fin['water-neutral']['stress']['water $10/m³'])}). The water-neutral design costs about {(wn['annual_cost']/opt['annual_cost']-1)*100:.0f} % more but uses no water at all. It becomes the cheaper option only if water costs more than about ${w_break:.0f}/m³, or is banned. Dust has no effect because neither finalist has sun-facing panels.

**Other climates.** The search was re-run from the finalists' genes for each site. The same architecture wins everywhere:

| Site | Annualised cost | Effective PUE | WUE (L/kWh) | Differences |
|---|---|---|---|---|
| hot-dry | {k(opt['annual_cost'])} | {opt['PUE_eff']:.3f} | {opt['WUE']:.3f} | — |
""" + "\n".join(f"| {st} | {k(v['result']['annual_cost'])} | {v['result']['PUE_eff']:.3f} | {v['result']['WUE']:.3f} | dry coolers {v['best']['dc_size']}×, economiser {v['best']['econ_size']}× |" for st, v in sites.items()) + f"""

**Scale.** The plot is fixed, so radiators cannot scale with the IT load. At 10 MW the sky-max roof carries {[s for s in sc if s['variant']=='sky-max' and s['P_MW']==10][0]['passive_share']*100:.1f} % of the heat, against {[s for s in sc if s['variant']=='sky-max' and s['P_MW']==0.5][0]['passive_share']*100:.1f} % at 0.5 MW. The water-neutral design holds about $67–71 per kW of IT per year at every size.

![Figure 6: Share of heat sent to the sky, and cost per kW, against IT load on the same plot](fig/d_scale.png)

**When would the sky win?** The integrated radiator deck was re-tested on the water-neutral design at $0.08–0.25/kWh and +0/+2/+4 K climates, re-optimising dry coolers, buffer and economiser each time. Its value is at most **${max(w['breakeven_per_m2'] for w in win):.0f}/m²**, against an installed cost of $40/m² (Figure 7). It falls as the climate warms, because the hottest hours, the ones that set the plant size, are exactly when the warm radiator does least.

![Figure 7: Break-even value of an integrated radiator roof deck vs. electricity price and climate warming](fig/d_window.png)

**Selection.** The **cost-optimal** design is the recommended base case. The **water-neutral** design is the alternative where water is scarce or regulated: it differs only in its heat-rejection plant and keeps the same IT, loops and building.

---

## 11. The final design: Zenith DC

![Figure 8: Cost-optimal design, two cooling loops](fig/d_schematic_opt.png)

![Figure 9: Water-neutral design, two cooling loops](fig/d_schematic_wn.png)

![Figure 10: Site plan and section, water-neutral design. The cost-optimal design is the same without the buffer and with adiabatic pads on the coolers.](fig/d_plan_wn.png)

**Building.** A single-storey IT hall at grade, with electrical and UPS rooms at 30 °C and a dry-cooler yard along the north edge of the plot. No sunk storeys, vault, canopy or film. The 72 × 48 m plot holds 1 MW easily and has room for several times that IT load. Space for heat-rejection plant, not the sky, becomes the limit.

**IT cooling.** Single-phase immersion tanks capture 95 % of IT heat in a dielectric fluid. A plate heat exchanger in each tank transfers it to the warm water loop.

**Warm loop.** The supply slides from 32 °C in cool weather to 45 °C at most; return is 20 K higher, up to 65 °C. Dry coolers are sized at 0.9× the warm load (1.2× in the water-neutral design), at 15 K approach, with N+1. Adiabatic pads run only on peak afternoons; in the water-neutral design a 250 m³ stratified hot buffer takes their place.

**Cool loop.** Supplied at 30 °C (36 °C return) for electrical rooms and the residual 5 % of IT heat. An economiser dry cooler runs whenever the air allows, then an evaporative cooler (cost-optimal) or a 90 kW chiller (water-neutral) covers the rest.

**Performance.** The heat-wave dispatch (Figure 11) shows how each design rides the 46 °C peak. The cost-optimal design uses its pads for a few hours each afternoon. The water-neutral design charges its buffer in the afternoon and empties it overnight.

![Figure 11: Heat-wave dispatch of the two finalists (kW, six days around the 46 °C peak; air temperature in {'white' if os.environ.get('DARK') == '1' else 'black'})](fig/d_heatwave.png)

![Figure 12: Daily-mean heat rejected by each sink over the year](fig/d_annual.png)

![Figure 13: Capital cost breakdown of the finalists](fig/d_capex.png)

| Key figures (1 MW IT, hot-dry) | Cost-optimal | Water-neutral |
|---|---|---|
| Effective PUE / cooling-only PUE | {opt['PUE_eff']:.3f} / {opt['pPUE']:.3f} | {wn['PUE_eff']:.3f} / {wn['pPUE']:.3f} |
| Cooling + pump + fan energy (MWh/yr) | {opt['e_cool_kWh']/1000:,.0f} | {wn['e_cool_kWh']/1000:,.0f} |
| Water (m³/yr) | {opt['water_m3']:,.0f} | {wn['water_m3']:,.0f} |
| Peak chiller (kW) | {opt['peaks_kW']['w_chil']+opt['peaks_kW']['c_chil']:.0f} | {wn['peaks_kW']['w_chil']+wn['peaks_kW']['c_chil']:.0f} |
| Capital cost | {k(opt['capex'])} | {k(wn['capex'])} |
| Annualised cooling cost | {k(opt['annual_cost'])}/yr | {k(wn['annual_cost'])}/yr |

---

## 12. What happened to the radiative building

Rounds 1 and 2 asked how a building can best shed heat to the sky, and the physics found there still holds. A sky-facing, broadband or window-selective plate is the right *shape*. Still air and spectral selectivity are the right *skin* below ambient. Storage across time is what turns sky cooling into a building service.

A data centre changes the *economics*, not the physics:

1. **The heat is warm.** Above ambient, every fan-blown fin is a sink. A dry cooler packs dozens of square metres of fin behind each square metre of face and costs about $90 per kW. A $120/m² sky panel delivers only about 0.2 kW/m² on the design afternoon, roughly $600 per kW.
2. **The heat is huge and constant.** This plot's sky can take about 0.5–1.7 MW of 50 °C heat, depending on the hour. That is significant at 1 MW and marginal at 10 MW.
3. **The sky is weakest exactly when it matters.** Plant is sized for the hottest hour, and on a 46 °C afternoon a warm radiator does a fraction of its night-time work.

The project's real lesson carries over: **match each heat stream to the coldest sink that is cheap at its temperature, and store heat across time only where the sinks are scarce.** For a data centre that means:

- warm water to dry air;
- a 30 °C cool loop to economisers;
- water or a buffer only for the few hours that set the plant size.

The sky plate is worth revisiting if radiator decks fall below about $25/m² installed, or for a sub-ambient process load such as a battery store or offices next to the data centre. Round 2 is the design for that case.

---

## 13. Limits and next steps

- **Weather:** a synthetic year from monthly normals plus one design heat wave, not typical-year or extreme-year weather files. Peak sizing should be checked against ASHRAE 0.4 % and record conditions.
- **Equipment models:** lumped models (dry-cooler UA, Carnot-fraction chillers, lumped ground node). No part-load curves from real equipment, and no CFD of the dry-cooler yard (recirculation, wind).
- **Costs:** planning-level and US-centric. The IT-side premium for immersion is an assumption; it would have to exceed about $220/kW to change the winner.
- **Leakage:** chip leakage of 0.1 %/K is an assumed figure. Higher leakage would favour lower supply temperatures; the sliding setpoint already captures most of that.
- **Not modelled:** electrical losses beyond 4 %, heat reuse (district heating, absorption cooling, desalination) and noise limits. Heat reuse could be the next generation's hypothesis.
- **Next:** hourly typical-year runs for the selected site, a vendor-based dry-cooler and immersion bill of quantities, and a heat-reuse generation.

---

## Appendix A: hypothesis ledger

![All {NH} hypotheses: annual cost saved by each idea after re-optimising everything else](fig/d_ledger.png)

## Appendix B: reproduction

| What | Where |
|---|---|
| Hourly climate generator | `breeze/dc/climate_hourly.py` |
| Two-loop simulator, cost model | `breeze/dc/sim.py` |
| Evolutionary search, paired hypothesis test | `breeze/dc/evolve.py` |
| Generations 0–7 driver | `cae/dc/run_generations.py` (about 7 min on 4 cores) |
| Supplementary checks (buffer sweep, deck window) | `cae/dc/supplement.py`, `cae/dc/rerecord.py` |
| Figures, drawings, this report | `cae/dc/figures.py`, `cae/dc/drawings.py`, `cae/dc/build_report.py`, `cae/dc/md2pdf.py` |
| Raw results | `results/dc/generations.json` |
"""
open(os.path.join(DOC, "Zenith_DC_report.md"), "w").write(md)
print("markdown written", len(md))
