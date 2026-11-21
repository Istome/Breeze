"""CAE-10  Deep subterranean pit: seasonal cold store + earth-sheltered programme.

(a) Transient radial finite-volume model of a buried, well-mixed water pit
    (sphere-equivalent radius R) in soil, cycled annually between 12 and 20 C
    against far-field soil at the 10 m temperature.  Gives the effective loss
    conductance UA(R) used by the annual model and the soil-shell storage gain.
(b) Envelope conductance and boundary temperatures for an exposed single storey
    vs. a programme sunk 4.5 m under a thick earth vault ('insulating dome').
"""
import numpy as np
from common import plt, save, dump, C
from breeze.climate_year import SITES, MONTH_DOY, soil_temperature, MONTHS

k_s, rc_s = 1.5, 2.2e6            # soil W/mK, J/m3K
day = 86400.0


def pit_cycle(R, T_far, years=6, nr=160, dt_days=1.0):
    r_out = 12 * R
    edges = R + (r_out - R) * (np.linspace(0, 1, nr + 1) ** 2)
    rc = 0.5 * (edges[1:] + edges[:-1])
    vol = 4 / 3 * np.pi * (edges[1:] ** 3 - edges[:-1] ** 3)
    A = 4 * np.pi * edges ** 2
    G = k_s * A[1:-1] / (rc[1:] - rc[:-1])
    G0 = k_s * A[0] / (rc[0] - R)
    T = np.full(nr, T_far)
    dt = dt_days * day
    flux, Tp_hist = [], []
    # implicit tridiagonal
    from scipy.linalg import solve_banded
    for n in range(int(365 * years / dt_days)):
        t = n * dt_days
        Tp = 16.0 + 273.15 - 4.0 * np.cos(2 * np.pi * (t - 75) / 365)   # coldest mid-March
        ab = np.zeros((3, nr)); b = rc_s * vol / dt * T
        diag = rc_s * vol / dt
        diag = diag.copy()
        diag[0] += G0; b[0] += G0 * Tp
        diag[:-1] += G; diag[1:] += G
        ab[0, 1:] = -G; ab[2, :-1] = -G
        Gfar = k_s * A[-1] / (edges[-1] - rc[-1]); diag[-1] += Gfar; b[-1] += Gfar * T_far
        ab[1] = diag
        T = solve_banded((1, 1), ab, b)
        if n >= int(365 * (years - 1) / dt_days):
            flux.append(G0 * (T[0] - Tp)); Tp_hist.append(Tp)
    flux, Tp_hist = np.array(flux), np.array(Tp_hist)
    UA_eff = flux.mean() / (T_far - Tp_hist.mean())
    return UA_eff, flux, Tp_hist, rc, T


res = {"pit": {}, "envelope": {}}
for site in SITES:
    T_far = float(np.mean(soil_temperature(site, 10, MONTH_DOY)))
    rows = []
    for V in (1000, 3000, 6000, 12000, 20000):
        R = (3 * V / (4 * np.pi)) ** (1 / 3)
        UA, flux, Tp, rc, T = pit_cycle(R, T_far)
        E_cap = V * 1000 * 4186 * 8 / 3.6e6 / 1000  # MWh for 8 K
        loss = flux.sum() * day / 3.6e9          # MWh/yr into the pit
        rows.append({"V": V, "R": R, "UA_W_K": UA, "UA_steady": 4 * np.pi * k_s * R, "E_cap_MWh": E_cap, "loss_MWh_yr": loss,
                     "flux_daily_kW": (flux / 1e3)[::7].tolist()})
        print(f"{site:9s} V={V:6d} R={R:5.1f} UA_eff={UA:7.0f} W/K (steady sphere {4*np.pi*k_s*R:6.0f})  cap={E_cap:6.1f} MWh  loss={loss:6.1f} MWh/yr  far={T_far-273.15:.1f}C")
    res["pit"][site] = {"T_far_C": T_far - 273.15, "rows": rows}
    # UA(V) fit: UA = a * V^(1/3)
    Vs = np.array([r["V"] for r in rows]); UAs = np.array([r["UA_W_K"] for r in rows])
    a = float(np.sum(UAs * Vs ** (1 / 3)) / np.sum(Vs ** (2 / 3)))
    res["pit"][site]["UA_coef"] = a * 1.2  # x1.2 cube-vs-sphere area
    # envelope boundary temperatures by month
    res["envelope"][site] = {
        "soil_1m": (soil_temperature(site, 1, MONTH_DOY) - 273.15).tolist(),
        "soil_2_5m": (soil_temperature(site, 2.5, MONTH_DOY) - 273.15).tolist(),
        "soil_5m": (soil_temperature(site, 5, MONTH_DOY) - 273.15).tolist(),
        "soil_8m": (soil_temperature(site, 8, MONTH_DOY) - 273.15).tolist(),
    }
# thick-dome decrement: periodic conduction through a slab (admittance), daily cycle
def decrement(L, k, rc):
    w = 2 * np.pi / day
    d = np.sqrt(2 * k / (rc * w))
    return float(np.exp(-L / d)), float(L / d / w / 3600)  # amplitude ratio, lag hours
res["dome"] = {name: {"L": L, "U_steady": 1 / (L / k + 0.17), "decrement": decrement(L, k, rc)[0], "lag_h": decrement(L, k, rc)[1]}
               for name, L, k, rc in (("rammed earth 0.6 m", 0.6, 1.0, 1.8e6), ("rammed earth 1.2 m", 1.2, 1.0, 1.8e6),
                                      ("PIR 0.15 m", 0.15, 0.022, 0.05e6), ("soil cover 0.6 m + PIR 0.15 m", 0.75, 0.1, 1.2e6))}
for k, v in res["dome"].items():
    print(f"{k:32s} U={v['U_steady']:.2f}  decrement={v['decrement']:.3f}  lag={v['lag_h']:.1f} h")
dump("s10_ground.json", res)

fig, axs = plt.subplots(1, 2, figsize=(10.5, 3.6))
for j, site in enumerate(SITES):
    r = res["pit"][site]["rows"]
    axs[0].plot([x["V"] for x in r], [x["loss_MWh_yr"] / x["E_cap_MWh"] * 100 for x in r], marker="o", color=C[j], label=site)
axs[0].set(xscale="log", xlabel="pit volume (m³)", ylabel="annual soil gain / 8 K capacity (%)", title="Seasonal pit: losses shrink with scale")
axs[0].legend()
x = np.arange(12)
for j, site in enumerate(SITES):
    e = res["envelope"][site]
    axs[1].plot(x, e["soil_2_5m"], color=C[j], marker="o", ms=3, label=f"{site}: soil at 2.5 m")
    axs[1].plot(x, 0.5 * (SITES[site]["Tmax"] + SITES[site]["Tmin"]) - 273.15, color=C[j], ls="--", label=f"{site}: air mean")
axs[1].axhline(25, color="#999", lw=0.8, ls=":")
axs[1].set(xticks=x, xticklabels=[m[0] for m in MONTHS], ylabel="°C", title="What a sunk wall sees vs. an exposed wall")
axs[1].legend(fontsize=7)
save(fig, "fig10_ground.png")
