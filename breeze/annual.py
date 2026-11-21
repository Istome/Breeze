"""Year-round balance of the Zenith Plate system (daily steps, monthly climate).

Sinks: plate (sky), evaporative cooler (wet-bulb).  Stores: diurnal tank (assumed
sufficient), seasonal pit.  Barriers: envelope options.  Transport: night flush.
"""
from __future__ import annotations

import numpy as np

from .climate_year import DAYS

RHO_CP_W = 4186.0 * 1000 / 3.6e6  # kWh/m3K


def simulate(C_direct, C_charge, load, plate_area, pit_V=0.0, pit_UA_coef=0.0, T_far=24.0,
             evap_avail=None, evap_charge_avail=None, use_evap=False, years=3, latent=None):
    """All per-month arrays are daily values (kWh/day) except C_* per m2 of plate.
    Returns annual totals (kWh) of the final year and month-by-month breakdown."""
    E_max = pit_V * RHO_CP_W * 8.0
    UA = pit_UA_coef * pit_V ** (1 / 3) if pit_V > 0 else 0.0
    E = 0.5 * E_max
    out = None
    for y in range(years):
        mon = {k: np.zeros(12) for k in ("load", "direct", "pit", "evap", "unmet", "charge_sky", "charge_evap", "loss", "soc", "heat", "latent", "latent_pit", "latent_unmet")}
        for m in range(12):
            for _ in range(DAYS[m]):
                L = load[m]
                if L < 0:
                    mon["heat"][m] += -L
                    L = 0.0
                cd = C_direct[m] * plate_area
                cc = C_charge[m] * plate_area
                lat = latent[m] if latent is not None else 0.0
                lp = min(lat, E)          # 12-14 C pit water runs the fresh-air dehumidifying coil
                E -= lp
                mon["latent"][m] += lat; mon["latent_pit"][m] += lp; mon["latent_unmet"][m] += lat - lp
                direct = min(L, cd)
                rem = L - direct
                take = min(rem, E)
                E -= take
                rem -= take
                ev = 0.0
                if use_evap and rem > 0 and evap_avail[m] > 0:
                    ev = rem
                    rem = 0.0
                spare = 1.0 - (direct / cd if cd > 0 else 1.0)
                ch = min(spare * cc, E_max - E) if E_max > 0 else 0.0
                E += ch
                ce = 0.0
                if use_evap and E_max > 0 and evap_charge_avail[m] > 0:
                    ce = E_max - E
                    E = E_max
                T_pit = 20.0 - 8.0 * (E / E_max if E_max > 0 else 0)
                loss = UA * (T_far - T_pit) * 24 / 1000
                E = max(0.0, E - loss)
                for k, v in (("load", L), ("direct", direct), ("pit", take), ("evap", ev), ("unmet", rem),
                             ("charge_sky", ch), ("charge_evap", ce), ("loss", loss)):
                    mon[k][m] += v
            mon["soc"][m] = E / E_max if E_max > 0 else 0.0
        out = mon
    tot = {k: float(v.sum()) for k, v in out.items() if k != "soc"}
    return tot, {k: v.tolist() for k, v in out.items()}
