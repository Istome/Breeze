"""Concept drawings of the final data-centre design (plan, section, loop schematic)."""
import json, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import plt, C, ROOT, DARK, BG, INK, MUTED
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle, FancyArrowPatch

OUT = os.path.join(ROOT, "results", "dc")
FIG = os.environ.get("DC_FIG_DIR", OUT)
os.makedirs(FIG, exist_ok=True)
R = json.load(open(os.path.join(OUT, "generations.json")))
fin = R["g6_finals"]


def tint(c):
    """Pastel fills become deep tints on a dark ground."""
    if not DARK or not isinstance(c, str) or not c.startswith("#"):
        return c
    a = [int(c[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(BG[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(0.30 * x + 0.70 * y):02x}" for x, y in zip(a, b))


_Rect, _Circ = Rectangle, Circle
Rectangle = lambda *a, fc=None, ec=None, **k: _Rect(*a, fc=tint(fc), ec=(MUTED if DARK and ec == "#1f2328" else ec), **k)
Circle = lambda *a, fc=None, ec=None, **k: _Circ(*a, fc=tint(fc), ec=ec, **k)


def box(ax, x, y, w, h, text, fc, ec="#1f2328", fs=8, tc="#0e1630", bold=False):
    fc, ec, tc = tint(fc), (MUTED if DARK else ec), (INK if DARK else tc)
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=1.0))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc, fontweight="bold" if bold else "normal", wrap=True)


def arrow(ax, p0, p1, color, lw=2.0, ls="-"):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=12, color=color, lw=lw, linestyle=ls))


def schematic(name, fname):
    d = fin[name]["design"]
    res = fin[name]["result"]
    hm = res["heat_MWh"]
    tot = sum(hm.values())
    pct = lambda k: 100 * hm.get(k, 0) / tot
    fig, ax = plt.subplots(figsize=(11, 5.2))
    ax.set_xlim(0, 11); ax.set_ylim(0, 6.2); ax.axis("off")
    warm, cool = "#f6d3c3", "#d6e2fb"
    box(ax, 0.2, 1.7, 2.1, 1.9, f"IT hall\n{d['it']}\n1.0 MW", "#eef0f4", bold=True, fs=9)
    tw_lo = 32 if d["sliding"] else d["Tw"]
    box(ax, 3.0, 3.55, 2.3, 1.2, f"WARM LOOP\nsupply {tw_lo:.0f}–{d['Tw']:.0f} °C\nreturn +{d['dT']:.0f} K", warm, fs=8.5, bold=True)
    box(ax, 3.0, 0.55, 2.3, 1.2, f"COOL LOOP\nsupply {d['Tc']:.0f} °C, return +6 K\nresidual air + electrical", cool, fs=8.5, bold=True)
    arrow(ax, (2.3, 3.2), (3.0, 4.0), "#c2410c", 2.4)
    arrow(ax, (2.3, 2.1), (3.0, 1.2), "#2346d6", 2.4)
    # warm sinks
    xs = 6.0
    wsinks = []
    if d["roof"] != "none" and d["roof_loop"] == "warm":
        wsinks.append((f"Sky radiators\n{d['roof']}\n{pct('w_pass'):.0f} % of heat", "#c9d6f7"))
    wsinks.append((f"Dry coolers ×{d['dc_size']:.1f}\n{pct('w_dry'):.0f} % of heat", "#f2e2c4"))
    if d["tank_m3"] > 0:
        wsinks.append((f"Hot buffer {d['tank_m3']:.0f} m³", "#f2d58a"))
    if d["adiabatic"]:
        wsinks.append((f"Adiabatic pads (peaks)\n{pct('w_wet'):.1f} % of heat", "#e3d3f2"))
    if res["peaks_kW"]["w_chil"] > 1:
        wsinks.append((f"Trim chiller {res['peaks_kW']['w_chil']:.0f} kW", "#f3c1cb"))
    for k, (t, c) in enumerate(wsinks):
        yk = 4.65 - k * 0.72
        box(ax, xs + 0.3 * k, yk - 0.3, 2.6, 0.6, t, c, fs=7.5)
        arrow(ax, (5.3, 4.15), (xs + 0.3 * k, yk), "#c2410c", 1.2)
    csinks = []
    if d["roof"] != "none" and d["roof_loop"] == "cool":
        csinks.append((f"Sky plate (cells)\n{pct('c_plate'):.0f} % of heat", "#c9d6f7"))
    if d["econ_size"] > 0:
        csinks.append((f"Economiser dry cooler\n{pct('c_econ'):.1f} % of heat", "#d4ecd9"))
    if d["cold_tank_m3"] > 0:
        csinks.append((f"Cold tank {d['cold_tank_m3']:.0f} m³", "#bfe0ef"))
    if d["evap_cool"]:
        csinks.append((f"Evaporative cooler\n{pct('c_evap'):.1f} % of heat", "#e3d3f2"))
    if res["peaks_kW"]["c_chil"] > 1:
        csinks.append((f"Chiller {res['peaks_kW']['c_chil']:.0f} kW\n{pct('c_chil'):.1f} % of heat", "#f3c1cb"))
    for k, (t, c) in enumerate(csinks):
        yk = 1.75 - k * 0.66
        box(ax, xs + 0.3 * k, yk - 0.28, 2.6, 0.56, t, c, fs=7.5)
        arrow(ax, (5.3, 1.15), (xs + 0.3 * k, yk), "#2346d6", 1.2)
    ax.text(0.2, 6.0, f"{name} design, hot-dry site", ha="left", fontsize=10, fontweight="bold")
    ax.text(0.2, 5.65, f"effective PUE {res['PUE_eff']:.3f} · WUE {res['WUE']:.2f} L/kWh · ${res['annual_cost']/1e3:.0f}k/yr", ha="left", fontsize=8.5, color=MUTED)
    fig.savefig(os.path.join(FIG, fname), dpi=170, bbox_inches="tight")
    plt.close(fig)


def plan(name, fname):
    d = fin[name]["design"]
    res = fin[name]["result"]
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"width_ratios": [1.25, 1]})
    ax = axs[0]
    ax.add_patch(Rectangle((-36, -24), 72, 48, fc="#f5f7fb", ec="#6e7781", lw=1.2, ls="--"))
    hall_w = 34 if d["it"].startswith("Immersion") else 40
    ax.add_patch(Rectangle((-30, -18), hall_w, 26, fc="#eef0f4", ec="#1f2328"))
    ax.text(-30 + hall_w / 2, -5, f"IT hall\n{d['it']}", ha="center", va="center", fontsize=8)
    ax.add_patch(Rectangle((-30 + hall_w + 2, -18), 18, 26, fc="#d6e2fb", ec="#1f2328"))
    ax.text(-30 + hall_w + 11, -5, f"Electrical\n+ UPS\nrooms {d['Tc']:.0f} °C", ha="center", va="center", fontsize=7.5)
    n_dc = max(1, int(round(d["dc_size"] * 0.95 * 1.2 / 0.25)))  # 250 kW units, N+1
    for k in range(n_dc):
        x = -32 + k * (64 / max(n_dc, 1))
        ax.add_patch(Rectangle((x, 12), 64 / max(n_dc, 1) - 1.2, 8, fc="#f2e2c4", ec="#8a6d00"))
        for f in range(2):
            ax.add_patch(Circle((x + (64 / max(n_dc, 1) - 1.2) * (0.3 + 0.4 * f), 16), 1.6, fc="none", ec="#8a6d00", lw=0.8))
    ax.text(0, 21.5, f"warm-loop dry coolers ({n_dc} × 250 kW incl. N+1)" + (", adiabatic pads" if d["adiabatic"] else ""), ha="center", fontsize=7.5)
    if d["econ_size"] > 0 or d["evap_cool"]:
        ax.add_patch(Rectangle((24, -18), 9, 12, fc="#d4ecd9", ec="#1a9e75"))
        ax.text(28.5, -12, "cool-loop\neconomiser" + ("\n+ evap." if d["evap_cool"] else ""), ha="center", va="center", fontsize=7)
    if d["tank_m3"] > 0 or d["cold_tank_m3"] > 0:
        r = np.sqrt((d["tank_m3"] + d["cold_tank_m3"]) / (np.pi * 8))
        ax.add_patch(Circle((28.5, 2), r, fc="#f2d58a", ec="#8a6d00"))
        ax.text(28.5, 2, f"buffer\n{d['tank_m3'] + d['cold_tank_m3']:.0f} m³", ha="center", va="center", fontsize=7)
    if d["roof"] != "none":
        ax.add_patch(Rectangle((-30, -18), 54 if "hall" in d["roof"] else 72, 26, fc="#2346d6", alpha=0.15, ec="#2346d6", hatch="//"))
    ax.set(xlim=(-38, 38), ylim=(-26, 25), aspect="equal", xlabel="E–W (m)", ylabel="N–S (m)", title=f"Site plan, {name}")
    ax.grid(False)
    # section (N-S): dry-cooler yard at grade on the north side
    ax = axs[1]
    ax.add_patch(Rectangle((-18, 0), 26, 7, fc="#eef0f4", ec="#1f2328"))
    ax.text(-5, 3.5, "IT hall + electrical\n(single storey, at grade)", ha="center", va="center", fontsize=7.5)
    ax.add_patch(Rectangle((12, 0.6), 8, 3.2, fc="#f2e2c4", ec="#8a6d00"))
    ax.text(16, 2.2, "dry coolers", ha="center", fontsize=7)
    for k in range(3):
        ax.annotate("", xy=(13.5 + 2.5 * k, 8), xytext=(13.5 + 2.5 * k, 4.0), arrowprops=dict(arrowstyle="->", color="#c2410c"))
    ax.plot([8, 12], [2.0, 2.0], color="#c2410c", lw=2)
    ax.text(10, 2.5, "warm\nloop", ha="center", fontsize=6.5, color="#c2410c")
    if d["roof"] != "none":
        ax.add_patch(Rectangle((-18, 7.0), 26, 0.4, fc="#2346d6", ec="none"))
    ax.axhline(0, color="#8a6a4f", lw=1.5)
    ax.text(-18, -2, "S", fontsize=8); ax.text(21, -2, "N", fontsize=8)
    ax.set(xlim=(-22, 24), ylim=(-3, 12), aspect="equal", xlabel="m", title="Section S–N")
    ax.grid(False)
    fig.savefig(os.path.join(FIG, fname), dpi=170, bbox_inches="tight")
    plt.close(fig)


for nm, tag in (("cost-optimal", "opt"), ("water-neutral", "wn")):
    schematic(nm, f"d_schematic_{tag}.png")
    plan(nm, f"d_plan_{tag}.png")
print("drawings done")
