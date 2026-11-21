"""Figure for CAE-11 from results/s11_annual.json."""
import json, os
import numpy as np
from common import plt, save, C, RES

d = json.load(open(os.path.join(RES, "s11_annual.json")))
res = d["results"]
sites = list(d["inputs"]["sites"])
CFG = d["inputs"]["scenarios"]
MONTHS = d["inputs"]["months"]
fig, axs = plt.subplots(1, 4, figsize=(16, 3.9))
LS = ["-", "--", ":"]
for j, site in enumerate(sites):
    for i, name in enumerate(CFG):
        axs[0].plot([1, 2, 3, 4], [r["unmet_MWh"] for r in res[site][name]], marker="o", ms=3, color=C[i], ls=LS[j],
                    label=name if j == 0 else None)
axs[0].set(xlabel="storeys under the plate", ylabel="backup cooling needed (MWh/yr)", xticks=[1, 2, 3, 4],
           title="solid: hot-dry · dashed: humid · dotted: arid")
axs[0].legend(fontsize=6.3)
for j, site in enumerate(sites):
    mon = res[site]["F  E, pit also dehumidifies fresh air"][2]["monthly"]
    x = np.arange(12)
    ax = axs[1 + j]
    dd, pp, uu = (np.array(mon[k]) / 1e3 for k in ("direct", "pit", "unmet"))
    lp = np.array(mon["latent_pit"]) / 1e3
    ax.bar(x, dd, color=C[0], label="plate, direct")
    ax.bar(x, pp, bottom=dd, color=C[2], label="seasonal pit (sensible)")
    ax.bar(x, lp, bottom=dd + pp, color=C[7], label="seasonal pit (dehumidification)")
    ax.bar(x, uu, bottom=dd + pp + lp, color=C[6], label="unmet")
    ax.bar(x, -np.array(mon["charge_sky"]) / 1e3, color=C[1], alpha=0.6, label="sky charging the pit")
    ax2 = ax.twinx(); ax2.plot(x, np.array(mon["soc"]) * 100, color="k", lw=1.2); ax2.set_ylim(0, 105); ax2.set_ylabel("pit charge (%)", fontsize=8)
    ax.axhline(0, color="k", lw=0.6)
    ax.set(xticks=x, xticklabels=[m[0] for m in MONTHS], ylabel="MWh / month", title=f"{site}: config F, 3 storeys, 20,000 m³ pit")
axs[1].legend(fontsize=6.2, loc="lower left")
save(fig, "fig11_annual.png")
