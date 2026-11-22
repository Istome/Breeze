"""Figures for the round-3 (data centre) report, from results/dc/generations.json."""
import json, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import plt, C, ROOT, DARK, BG, INK, MUTED

OUT = os.path.join(ROOT, "results", "dc")
FIG = os.environ.get("DC_FIG_DIR", OUT)
os.makedirs(FIG, exist_ok=True)
R = json.load(open(os.path.join(OUT, "generations.json")))
STAT = {"confirmed": "#1a9e75", "refuted": "#d23b5a", "marginal": "#8a8f99"}


if DARK:
    STAT = {"confirmed": "#3fcf9a", "refuted": "#ff6b85", "marginal": "#9aa4b5"}


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, name), dpi=170, bbox_inches="tight")
    plt.close(fig)


# 1. progression
prog = R["progression"]
names = [p["name"].split(" ")[0] if p["name"].startswith("G") else "G0" for p in prog]
names[0] = "Baseline"
fig, axs = plt.subplots(1, 3, figsize=(12, 3.4))
for ax, key, lab, fmt in ((axs[0], "annual_cost", "annualised cost (k$/yr)", lambda v: v / 1e3), (axs[1], "PUE_eff", "effective PUE (cooling + IT-side)", lambda v: v),
                          (axs[2], "WUE", "water use (L per kWh of IT)", lambda v: v)):
    vals = [fmt(p[key]) for p in prog]
    bars = ax.bar(names, vals, color=[C[5]] + [C[0]] * (len(vals) - 2) + [C[1]])
    for b_, v in zip(bars, vals):
        ax.text(b_.get_x() + b_.get_width() / 2, b_.get_height(), f"{v:.3f}" if key != "annual_cost" else f"{v:.0f}", ha="center", va="bottom", fontsize=7.5)
    ax.set(ylabel=lab)
    ax.tick_params(axis="x", labelsize=8)
    if key == "PUE_eff":
        ax.set_ylim(1.0, max(vals) * 1.03)
save(fig, "d_progression.png")

# 2. GA convergence
fig, ax = plt.subplots(figsize=(7, 3.4))
off = 0
for j, g in enumerate(R["generations"]):
    tr = np.array(g["trace"]) / 1e3
    x = np.arange(off, off + len(tr))
    ax.plot(x, tr[:, 0], color=C[j % len(C)], lw=2, label=g["name"])
    ax.plot(x, tr[:, 1], color=C[j % len(C)], lw=1, ls=":")
    off += len(tr)
ax.set(xlabel="GA iteration (cumulative)", ylabel="annualised cost (k$/yr)", title="Best (solid) and elite mean (dotted) per generation", yscale="log")
ax.legend(fontsize=7)
save(fig, "d_convergence.png")

# 3. hypothesis ledger
rows = []
for g in R["generations"]:
    for gene, v in g.get("verdict", {}).items():
        rows.append((v["hyp"], v["status"], v["gain"]))
fig, ax = plt.subplots(figsize=(9, 0.32 * len(rows) + 0.8))
yv = np.arange(len(rows))
ax.barh(yv, [max(-60, min(60, r[2])) for r in rows], color=[STAT[r[1]] for r in rows])
ax.set_yticks(yv, [r[0] for r in rows], fontsize=7.4)
ax.invert_yaxis()
ax.axvline(0, color=INK, lw=0.8)
for i, r in enumerate(rows):
    ax.text(max(-60, min(60, r[2])) + (1 if r[2] >= 0 else -1), i, f"{r[2]:+.1f}%", va="center", ha="left" if r[2] >= 0 else "right", fontsize=6.8)
ax.set(xlabel="annual cost saved by the idea, after re-optimising everything else (%)", xlim=(-70, 70))
for k, c in STAT.items():
    ax.barh([-5], [0], color=c, label=k)
ax.legend(fontsize=7, loc="lower right")
ax.set_ylim(len(rows) - 0.5, -0.5)
save(fig, "d_ledger.png")

# 4. G2 sweeps
fig, axs = plt.subplots(1, 2, figsize=(10.5, 3.4))
for j, (dc, rows) in enumerate(R["supp_tank"].items()):
    axs[0].plot([s["V"] for s in rows], [s["chiller_kW"] for s in rows], marker="o", color=C[j], label=f"dry coolers {dc}× load")
axs[0].set(xlabel="hot-water buffer (m³)", ylabel="warm-loop chiller needed (kW)", title="Water-free: a buffer only works with spare night capacity", xscale="symlog", xlim=(-10, 5000))
axs[0].legend(fontsize=7.5)
dt = R["g2_dT_sweep"]
axs[1].plot([d["dT"] for d in dt], [d["cost"] / 1e3 for d in dt], marker="o", color=C[0])
axs[1].set(xlabel="coolant temperature rise across the IT (K)", ylabel="annualised cost (k$/yr)", title="Wider ΔT across the IT")
save(fig, "d_g2.png")

# 5. break-even
be = R["g3_breakeven"]
fig, ax = plt.subplots(figsize=(8.5, 3.4))
ks = list(be)
x = np.arange(len(ks))
ax.bar(x - 0.2, [be[k]["cost_per_m2"] for k in ks], 0.4, color=C[5], label="installed cost")
ax.bar(x + 0.2, [max(0, be[k]["breakeven_per_m2"]) for k in ks], 0.4, color=C[2], label="what it is worth (break-even)")
for i, k in enumerate(ks):
    ax.text(i + 0.2, max(0, be[k]["breakeven_per_m2"]) + 4, f"${be[k]['breakeven_per_m2']:.0f}", ha="center", fontsize=7.5)
ax.set_xticks(x, [k.replace(" on ", "\n") for k in ks], fontsize=7.5)
ax.set(ylabel="$ per m² of radiator", title="Sky radiators: cost vs. value (re-optimised, 1 MW, hot-dry)")
ax.legend(fontsize=7.5)
save(fig, "d_breakeven.png")

# 6. ground drift
fig, ax = plt.subplots(figsize=(6, 3.3))
for j, (k, v) in enumerate(R["g4_ground"].items()):
    ax.plot(np.arange(1, len(v) + 1), v, marker="o", color=C[j], label=k)
ax.set(xlabel="year", ylabel="borehole field temperature, end of year (°C)", title="100 × 120 m boreholes, 1 MW warm loop")
ax.legend(fontsize=8)
save(fig, "d_ground.png")

# 7. heat-wave dispatch for the finals
fig, axs = plt.subplots(1, 2, figsize=(12, 3.8), sharey=True)
for ax, name in zip(axs, ("cost-optimal", "water-neutral")):
    h = R["g6_hourly"][name]["heatwave"]
    t = np.arange(len(R["g6_hourly"][name]["heatwave_T"]))
    order = [("w_pass", "sky radiators", C[0]), ("w_dry", "dry coolers", C[7]), ("w_tank", "into hot buffer", C[4]), ("w_wet", "adiabatic (water)", C[3]),
             ("w_chil", "chiller", C[6]), ("c_plate", "cool: sky plate", "#3355cc"), ("c_econ", "cool: economiser", C[2]), ("c_tank", "cool: cold tank", "#7fb7a8"),
             ("c_evap", "cool: evaporative", "#b48ad8"), ("c_chil", "cool: chiller", "#a83250")]
    stack = [np.array(h.get(k, [0] * len(t))) for k, _, _ in order]
    ax.stackplot(t, *stack, colors=[c for _, _, c in order], labels=[l for _, l, _ in order])
    ax2 = ax.twinx()
    ax2.plot(t, R["g6_hourly"][name]["heatwave_T"], color=INK, lw=1.2)
    ax2.set_ylabel("air °C")
    ax.set(xlabel="hour from 13 July (heat wave peaks at 46 °C)", title=f"{name} design", ylabel="heat rejected (kW)")
axs[0].legend(fontsize=6.5, loc="upper left", ncol=2)
save(fig, "d_heatwave.png")

# 8. annual daily sink mix
fig, axs = plt.subplots(1, 2, figsize=(12, 3.4), sharey=True)
for ax, name in zip(axs, ("cost-optimal", "water-neutral")):
    h = R["g6_hourly"][name]
    d = np.arange(365)
    order = [("w_pass", "sky radiators", C[0]), ("w_dry", "dry coolers", C[7]), ("w_wet", "adiabatic", C[3]), ("w_tank", "buffer", C[4]), ("w_chil", "chiller", C[6]),
             ("c_plate", "cool: sky", "#3355cc"), ("c_econ", "cool: economiser", C[2]), ("c_evap", "cool: evaporative", "#b48ad8"), ("c_chil", "cool: chiller", "#a83250")]
    ax.stackplot(d, *[np.array(h.get(k, [0] * 365)) for k, _, _ in order], colors=[c for _, _, c in order], labels=[l for _, l, _ in order])
    ax.set(xlabel="day of year", title=name, ylabel="daily-mean heat rejected (kW)")
axs[1].legend(fontsize=6.5, loc="upper right", ncol=2)
save(fig, "d_annual.png")

# 9. robustness
fin = R["g6_finals"]
fig, ax = plt.subplots(figsize=(10, 3.6))
cases = ["base", "water $10/m³", "electricity $0.15/kWh", "dust (+0.10 solar absorptance)", "climate +2 K"]
x = np.arange(len(cases))
w = 0.26
for j, (name, v) in enumerate(fin.items()):
    ax.bar(x + (j - 1) * w, [v["stress"][c] / 1e3 for c in cases], w, color=C[j], label=name)
    ax.errorbar([len(cases) + (j - 1) * w], [v["stress"]["MC p50"] / 1e3], yerr=[[v["stress"]["MC p50"] / 1e3 - v["stress"]["MC p10"] / 1e3], [v["stress"]["MC p90"] / 1e3 - v["stress"]["MC p50"] / 1e3]],
                fmt="o", color=C[j], capsize=4)
ax.set_xticks(list(x) + [len(cases)], cases + ["prices ±30 %\n(p10–p90)"], fontsize=7.5)
ax.set(ylabel="annualised cost (k$/yr)", yscale="log", title="Stress tests of the finalists")
ax.legend(fontsize=7.5)
save(fig, "d_robust.png")

# 10. scale
sc = R["g6_scale"]
fig, axs = plt.subplots(1, 2, figsize=(10, 3.3))
for j, name in enumerate(("water-neutral", "sky-max")):
    rows = [s for s in sc if s["variant"] == name]
    axs[0].plot([r["P_MW"] for r in rows], [r["passive_share"] * 100 for r in rows], marker="o", color=C[j], label=name)
    axs[1].plot([r["P_MW"] for r in rows], [r["cost_per_kW"] for r in rows], marker="o", color=C[j], label=name)
axs[0].set(xscale="log", xlabel="IT load (MW) on the same 72 × 48 m plot", ylabel="heat sent to the sky (%)", title="The sky's share shrinks with load")
axs[1].set(xscale="log", xlabel="IT load (MW)", ylabel="$ per kW of IT per year", title="Cost per kW")
axs[0].legend(fontsize=8)
save(fig, "d_scale.png")

# 11. capex of finals
fig, ax = plt.subplots(figsize=(8, 3.2))
parts = ["dry", "econ", "chiller", "evap", "tank", "cold_tank", "pit", "ground", "roof", "fin", "it_side"]
bottom = np.zeros(len(fin))
for j, p in enumerate(parts):
    v = np.array([fin[n]["result"]["capex_parts"][p] / 1e3 for n in fin])
    if v.sum() > 0:
        ax.bar(list(fin), v, bottom=bottom, color=C[j % len(C)], label=p.replace("_", " "))
        bottom += v
ax.set(ylabel="capital cost (k$)", title="Capital cost of the finalists (1 MW)")
ax.legend(fontsize=7, ncol=2)
save(fig, "d_capex.png")
print("figures done")

# 12. sky window
win = R["supp_window"]
fig, ax = plt.subplots(figsize=(6.2, 3.3))
for j, wK in enumerate((0.0, 2.0, 4.0)):
    rows = [w for w in win if w["warming"] == wK]
    ax.plot([r["elec"] for r in rows], [r["breakeven_per_m2"] for r in rows], marker="o", color=C[j], label=f"climate +{wK:.0f} K")
ax.axhline(40, color="#d23b5a", ls="--", lw=1)
ax.text(0.081, 42, "installed cost of the integrated radiator deck, $40/m²", fontsize=7.5, color="#d23b5a")
ax.set(xlabel="electricity price ($/kWh)", ylabel="what the deck is worth ($/m²)", title="Water-neutral design: is a radiator roof deck worth it?", ylim=(-20, 60))
ax.legend(fontsize=7.5)
save(fig, "d_window.png")
print("figure 12 done")
