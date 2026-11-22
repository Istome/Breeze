"""Hourly two-loop heat-rejection simulator for a data centre (round 3).

WARM loop: heat captured by liquid cooling (fraction f_cap of IT), supply T_s
(W32/W40/W45), return T_s + dT.  Sinks in series / priority:
  roof radiators (if assigned to this loop) -> dry coolers -> hot buffer tank ->
  borehole field -> adiabatic pre-cooling -> trim chiller.
COOL loop: air-side residual heat (1 - f_cap) + electrical losses (4 % of IT),
supply 18-26 C, return +6 K.  Sinks:
  sub-ambient sky plate (round-2 skin: selective emitter, film over 100 mm still air)
  -> economiser dry cooler -> cold buffer tank -> seasonal cold pit ->
  evaporative (closed-circuit) cooler -> air-cooled chiller.

Every passive field is a heat exchanger with an hourly-linearised surface flux
q(T) = b (T - T_eq), so Q = C (T_in - T_eq) (1 - exp(-b A / C)).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np

from .climate_hourly import band_E

SIGMA = 5.670374419e-8
IT_CLASSES = {  # f_cap (to warm loop), server-fan overhead, IT-side capex $/kW_IT (vs D2C 75 %)
    "Air-cooled": (0.0, 0.04, -60.0),
    "D2C 75%": (0.75, 0.02, 0.0),
    "D2C + liquid rear-door 85%": (0.85, 0.015, 40.0),
    "Immersion 95%": (0.95, 0.005, 150.0),
}
COATINGS = {  # eps_window, eps_other, alpha_sol, extra capex $/m2, upkeep $/m2/yr
    "white paint": (0.94, 0.94, 0.12, 0.0, 0.5),
    "PDRC film": (0.96, 0.90, 0.05, 25.0, 3.0),
    "selective": (0.95, 0.15, 0.06, 40.0, 1.0),
}
ROOFS = {  # area m2, bottom face active (warm use), structure+panel $/m2
    "none": (0.0, False, 0.0),
    "hall roof, integrated deck": (2160.0, False, 40.0),   # tile IS the roof: credits ~$80/m2 of membrane + insulation
    "hall roof": (2160.0, False, 120.0),
    "canopy": (3456.0, False, 320.0),
    "canopy 2-sided": (3456.0, True, 335.0),
}
PRICE = dict(elec=0.08, water=3.0, crf=0.1098, dc_kw=90.0, adiab_kw=15.0, chiller_kw=350.0, evap_kw=120.0,
             tank_m3=350.0, tank_fixed=20000.0, pit_m3=60.0, bore_m=55.0, fin_m2=120.0, cells_m2=70.0,
             cells_upkeep=3.0, redundancy=1.2)


@dataclass
class Design:
    it: str = "D2C 75%"
    Tw: float = 45.0                # warm supply (W32/W40/W45)
    dT: float = 10.0                # warm-loop dT across IT
    Tc: float = 22.0                # cool supply
    roof: str = "none"
    roof_loop: str = "warm"         # which loop the roof serves
    coating: str = "white paint"    # warm use; cool use always selective + film cells
    dc_size: float = 1.2            # warm dry coolers: rated / warm load at 15 K
    adiabatic: bool = False
    tank_m3: float = 0.0            # warm hot-buffer
    bores: int = 0
    sky_recharge: bool = False
    econ_size: float = 0.0          # cool-loop economiser dry cooler: rated / cool load at 10 K
    cold_tank_m3: float = 0.0
    pit_m3: float = 0.0             # seasonal cold pit (cool loop)
    evap_cool: bool = False         # closed-circuit evaporative cooler on cool loop
    fin_wall_m2: float = 0.0
    shift: bool = False
    sliding: bool = False
    soiling: float = 0.0
    P_IT: float = 1.0e6

    def key(self):
        return tuple(sorted(asdict(self).items()))


def _h_top(dT, wind):
    return np.cbrt((2.8 + 3.0 * wind) ** 3 + (1.52 * np.cbrt(np.abs(dT))) ** 3)


def _lin(fun, T_ref):
    q1, q2 = fun(T_ref - 4.0), fun(T_ref + 4.0)
    b = np.clip((q2 - q1) / 8.0, 1e-3, None)
    return b, (T_ref - 4.0) - q1 / b


def open_panel(y, coat, soiling=0.0, bottom=False):
    eW, eN, a, _, _ = COATINGS[coat]
    a = a + soiling

    def q(Tp):
        TK = Tp + 273.15
        EW, ENW = band_E(TK)
        out = eW * (EW - y["G_ir_W"]) + eN * (ENW - y["G_ir_NW"]) + _h_top(Tp - y["T"], y["wind"]) * (Tp - y["T"]) - a * y["G"]
        if bottom:
            out = out + 0.5 * (eW + eN) * SIGMA * (TK ** 4 - (y["T"] + 273.15) ** 4) + 0.5 * (2.8 + 3.0 * y["wind"]) * (Tp - y["T"]) - a * 0.05 * y["G"]
        return out
    return q


def cell_panel(y, soiling=0.0, gap=0.10):
    """Round-2 skin: selective emitter under 12 um LDPE film over a still-air gap."""
    U = 1.0 / (gap / 0.026 + 1.0 / (2.8 + 3.0 * 2.5)) + 0.2
    tau = 0.85

    def q(Tp):
        TK = Tp + 273.15
        EW, ENW = band_E(TK)
        BW, BNW = band_E(y["T"] - 1.0 + 273.15)
        inW = tau * y["G_ir_W"] + (1 - tau) * BW
        inN = tau * y["G_ir_NW"] + (1 - tau) * BNW
        rad = 0.97 * (0.95 * (EW - inW) + 0.15 * (ENW - inN))
        return rad - U * (y["T"] - Tp) - (0.05 + soiling) * 0.92 * y["G"]
    return q


def finwall(y, H=3.0, s=0.2, soiling=0.0):
    def q(Tp):
        TK = Tp + 273.15
        EW, ENW = band_E(TK)
        dT = Tp - y["T"]
        rad = 0.97 * ((EW - y["G_ir_W"]) + (ENW - y["G_ir_NW"])) + 0.97 * SIGMA * (TK ** 4 - (y["T"] + 273.15) ** 4)
        return rad + (2 * H / s) * (1.31 * np.cbrt(np.abs(dT)) + 0.9 * y["wind"]) * dT - (0.12 + soiling) * y["G"]
    return q


def field(C, Tin, b, Teq, A):
    return C * np.clip(Tin - Teq, 0, None) * (1 - np.exp(-b * A / C))


def cop_air(T_evap_C, Ta):
    Te = T_evap_C + 273.15
    return np.clip(0.4 * Te / np.clip(Ta + 15 + 273.15 - Te, 1.0, None), 2.0, 8.0)


class Sim:
    def __init__(self, year, ground_T0=24.0, pit_T_far=24.0, pit_ua_coef=27.0):
        self.y = year
        self.gT0, self.pit_Tfar, self.pit_ua = ground_T0, pit_T_far, pit_ua_coef
        self._c = {}

    def lin(self, kind, T_ref, coat="white paint", soiling=0.0):
        k = (kind, round(T_ref, 1), coat, soiling)
        if k not in self._c:
            f = {"top": lambda: open_panel(self.y, coat, soiling), "both": lambda: open_panel(self.y, coat, soiling, True),
                 "cells": lambda: cell_panel(self.y, soiling), "fin": lambda: finwall(self.y, soiling=soiling)}[kind]()
            self._c[k] = _lin(f, T_ref)
        return self._c[k]

    def run(self, d: Design, years=1, record=False):
        y = self.y
        n = len(y["T"])
        T = y["T"]
        P0 = d.P_IT
        f_cap, srv, it_capex = IT_CLASSES[d.it]
        liquid = f_cap > 0
        # ---------------- warm loop
        Tw = np.clip(T + 8.0, 32.0, d.Tw) if (d.sliding and liquid) else np.full(n, d.Tw)
        pen = 0.001 * np.clip(Tw - 30.0, 0, None) if liquid else np.zeros(n)
        Pw = f_cap * P0 * (1 + srv + pen)
        Cw = np.maximum(Pw / d.dT, 1.0)
        Trw = Tw + d.dT
        A_roof, two_sided, roof_cost = ROOFS[d.roof]
        warm_roof = A_roof > 0 and d.roof_loop == "warm" and liquid
        cool_roof = A_roof > 0 and (d.roof_loop == "cool" or not liquid)
        Qp = np.zeros(n)
        Tin = Trw.copy()
        if warm_roof:
            b, Teq = self.lin("both" if two_sided else "top", float(d.Tw + d.dT / 2), d.coating, d.soiling)
            Qr = field(Cw, Tin, b, Teq, A_roof)
            Qp += Qr
            Tin = Tin - Qr / Cw
            b_roof, Teq_roof = b, Teq
        if d.fin_wall_m2 > 0 and liquid:
            b, Teq = self.lin("fin", float(d.Tw + d.dT / 2), soiling=d.soiling)
            Qf = field(Cw, Tin, b, Teq, d.fin_wall_m2)
            Qp += Qf
        spare_p = np.clip(Qp - Pw, 0, None)
        Qp_used = np.minimum(Qp, Pw)
        Tmid = Trw - Qp_used / Cw
        need_w = Pw - Qp_used
        Gw = d.dc_size * f_cap * P0 / 15.0
        Tmw = 0.5 * (Tmid + Tw)
        cap_dry = Gw * np.clip(Tmw - T, 0, None)
        T_ad = T - 0.8 * (T - y["Twb"])
        cap_wet = Gw * np.clip(Tmw - T_ad, 0, None) if d.adiabatic else cap_dry
        fan_w_rated = 0.018 * d.dc_size * f_cap * P0
        m_air_w = d.dc_size * f_cap * P0 / (1006 * 10.0)
        cop_w = cop_air(Tw - 5, T)
        # ---------------- cool loop
        Pc = (1 - f_cap) * P0 * (1 + srv) + 0.04 * P0
        Cc = Pc / 6.0
        Tc, Trc = d.Tc, d.Tc + 6.0
        Qcp = np.zeros(n)
        Qcp_charge = np.zeros(n)
        if cool_roof:
            b, Teq = self.lin("cells", Tc + 3.0, soiling=d.soiling)
            Qcp = field(Cc, Trc, b, Teq, A_roof)
            Qcp_charge = field(Cc, np.full(n, Tc), b, Teq, A_roof)   # capacity when cooling store water
        Qcp_used = np.minimum(Qcp, Pc)
        spare_c = np.where(Qcp > 0, np.clip(1 - Pc / np.maximum(Qcp, 1.0), 0, 1) * Qcp_charge, 0.0)
        need_c = Pc - Qcp_used
        Gc = d.econ_size * Pc / 10.0
        Tmc = Tc + 3.0
        cap_econ = Gc * np.clip(Tmc - T, 0, None)
        cap_econ_charge = Gc * np.clip(Tc - 3.0 - T, 0, None)
        fan_c_rated = 0.02 * d.econ_size * Pc
        evap_ok = (y["Twb"] + 4.0 < Tmc) if d.evap_cool else np.zeros(n, bool)
        cop_c = cop_air(Tc - 5, T)
        crah = 0.04 * (1 - f_cap) * P0 + 0.01 * 0.04 * P0
        # ---------------- state
        Ew_max = d.tank_m3 * 1.163 * d.dT * 1000.0
        Ec_max = d.cold_tank_m3 * 1.163 * 10.0 * 1000.0
        Ep_max = d.pit_m3 * 1.163 * 8.0 * 1000.0
        ua_pit = self.pit_ua * d.pit_m3 ** (1 / 3) if d.pit_m3 > 0 else 0.0
        nb, Lb = d.bores, 120.0
        Gb = nb * Lb / 0.15
        Cg = nb * 36 * Lb * 2.2e6 / 3600.0
        Rf = math.sqrt(max(nb, 1) * 36 / math.pi)
        Gfar = (2 * math.pi * 2.0 * Lb / math.log((Rf + 10) / Rf)) if nb else 0.0
        Tg, Ew, Ec, Ep = self.gT0, 0.0, 0.0, 0.5 * Ep_max
        keys = ("w_pass", "w_dry", "w_tank", "w_ground", "w_wet", "w_chil", "c_plate", "c_econ", "c_tank", "c_pit", "c_evap", "c_chil")
        tot = {k: 0.0 for k in keys + ("fan", "chiller", "pump", "water", "crah", "evapfan")}
        pk = dict(w_chil=0.0, c_chil=0.0, c_evap=0.0)
        rec = {k: np.zeros(n) for k in keys + ("Ew", "Ec", "Ep", "Tg")} if record else None
        Tg_trace = []
        for yr in range(years):
            last = yr == years - 1
            for i in range(n):
                Ti = T[i]
                # ===== warm loop
                qn = need_w[i]
                cd = cap_dry[i]
                hot = d.shift and Ew < Ew_max and Ti > Tw[i] - 8
                q_dry = min(qn, cd * 0.7 if hot else cd)
                rem = qn - q_dry
                q_tank = min(rem, Ew_max - Ew) if Ew_max > 0 else 0.0
                Ew += q_tank
                rem -= q_tank
                q_g = 0.0
                if nb and rem > 0:
                    q_g = min(rem, max(0.0, Gb * (Tmw[i] - Tg)))
                    rem -= q_g
                q_wet = 0.0
                if d.adiabatic and rem > 0:
                    q_wet = min(rem, max(0.0, cap_wet[i] - q_dry))
                    rem -= q_wet
                q_wch = rem
                spare_d = 0.0 if hot else max(0.0, cd - q_dry)
                dis = min(Ew, spare_p[i] + spare_d) if Ew > 0 else 0.0
                Ew -= dis
                q_dis_fan = max(0.0, dis - spare_p[i])
                q_rec = 0.0
                if nb and d.sky_recharge and warm_roof and Tg > Teq_roof[i] + 1:
                    left = max(0.0, spare_p[i] - dis)
                    if left > 0:
                        q_rec = min(left / max(Qp[i], 1.0) * A_roof * b_roof[i] * (Tg - Teq_roof[i]), Gb * (Tg - Teq_roof[i]))
                if nb:
                    Tg += (q_g - q_rec - Gfar * (Tg - self.gT0)) / Cg
                load_f = q_dry + q_dis_fan + q_wet
                if load_f > 0:
                    capf = cap_wet[i] if q_wet > 0 else cd
                    s = min(1.0, (load_f / max(capf, 1.0)) ** (1 / 0.7))
                    fanW = fan_w_rated * s ** 3
                    waterW = m_air_w * s * 1006 * (Ti - T_ad[i]) / 2.45e6 * 1.25 * 3600 if q_wet > 0 else 0.0
                else:
                    fanW = waterW = 0.0
                chW = q_wch / cop_w[i] if q_wch > 0 else 0.0
                # ===== cool loop
                qc = need_c[i]
                q_econ = min(qc, cap_econ[i])
                rc = qc - q_econ
                q_ct = min(rc, Ec) if Ec > 0 else 0.0
                Ec -= q_ct
                rc -= q_ct
                q_pit = min(rc, Ep) if Ep > 0 else 0.0
                Ep -= q_pit
                rc -= q_pit
                q_ev = rc if (rc > 0 and evap_ok[i]) else 0.0
                rc -= q_ev
                q_cch = rc
                # charging: plate spare, then economiser spare, into cold tank then pit
                ch_src = spare_c[i] + max(0.0, cap_econ_charge[i] - q_econ)
                ch_t = min(ch_src, Ec_max - Ec) if Ec_max > 0 else 0.0
                Ec += ch_t
                ch_p = min(ch_src - ch_t, Ep_max - Ep) if Ep_max > 0 else 0.0
                Ep += ch_p
                if Ep_max > 0:
                    Tp_ = 20.0 - 8.0 * Ep / Ep_max
                    Ep = max(0.0, Ep - ua_pit * (self.pit_Tfar - Tp_))
                econ_load = q_econ + max(0.0, ch_t + ch_p - spare_c[i])
                fanC = fan_c_rated * min(1.0, econ_load / max(Gc * 10.0, 1.0)) ** 2.5 if econ_load > 0 else 0.0
                chC = q_cch / cop_c[i] if q_cch > 0 else 0.0
                evW = q_ev / 2.45e6 * 1.3 * 3600
                pump = 0.008 * P0 + 0.004 * (Qp_used[i] + Qcp_used[i]) + 0.003 * (q_g + q_rec) + 0.002 * (ch_t + ch_p)
                if last:
                    for kk, vv in (("w_pass", Qp_used[i]), ("w_dry", q_dry + q_dis_fan), ("w_tank", q_tank), ("w_ground", q_g), ("w_wet", q_wet),
                                   ("w_chil", q_wch), ("c_plate", Qcp_used[i]), ("c_econ", q_econ), ("c_tank", q_ct), ("c_pit", q_pit), ("c_evap", q_ev), ("c_chil", q_cch)):
                        tot[kk] += vv / 1000
                        if record:
                            rec[kk][i] = vv
                    tot["fan"] += (fanW + fanC) / 1000
                    tot["chiller"] += (chW + chC) / 1000
                    tot["evapfan"] += 0.01 * q_ev / 1000
                    tot["pump"] += pump / 1000
                    tot["crah"] += crah / 1000
                    tot["water"] += (waterW + evW) / 1000
                    pk["w_chil"] = max(pk["w_chil"], q_wch)
                    pk["c_chil"] = max(pk["c_chil"], q_cch)
                    pk["c_evap"] = max(pk["c_evap"], q_ev)
                    if record:
                        rec["Ew"][i], rec["Ec"][i], rec["Ep"][i], rec["Tg"][i] = Ew, Ec, Ep, Tg
            Tg_trace.append(Tg)
        # ---------------- money and metrics
        E_IT = P0 * n / 1000.0
        extra_it = float(np.sum(P0 * (srv + f_cap * pen)) / 1000.0)
        e_cool = tot["fan"] + tot["chiller"] + tot["pump"] + tot["crah"] + tot["evapfan"]
        coat_cx, coat_up = (COATINGS[d.coating][3], COATINGS[d.coating][4]) if warm_roof else (40.0 + PRICE["cells_m2"], PRICE["cells_upkeep"])
        R = PRICE["redundancy"]
        capex = dict(
            roof=A_roof * (roof_cost + coat_cx) if A_roof else 0.0,
            fin=d.fin_wall_m2 * 3.0 / 0.2 * PRICE["fin_m2"] if liquid else 0.0,
            dry=R * d.dc_size * f_cap * P0 / 1000 * (PRICE["dc_kw"] + (PRICE["adiab_kw"] if d.adiabatic else 0)),
            econ=R * d.econ_size * Pc / 1000 * PRICE["dc_kw"],
            chiller=R * (pk["w_chil"] + pk["c_chil"]) / 1000 * PRICE["chiller_kw"],
            evap=R * pk["c_evap"] / 1000 * PRICE["evap_kw"],
            tank=(d.tank_m3 * PRICE["tank_m3"] + PRICE["tank_fixed"]) if d.tank_m3 > 0 else 0.0,
            cold_tank=(d.cold_tank_m3 * PRICE["tank_m3"] + PRICE["tank_fixed"]) if d.cold_tank_m3 > 0 else 0.0,
            pit=d.pit_m3 * PRICE["pit_m3"],
            ground=nb * Lb * PRICE["bore_m"],
            it_side=it_capex * P0 / 1000,
        )
        capex_tot = sum(capex.values())
        opex = (e_cool + extra_it) * PRICE["elec"] + tot["water"] * PRICE["water"] + A_roof * coat_up
        annual = PRICE["crf"] * capex_tot + opex
        if d.Tc > 26 and f_cap < 0.95:
            annual += 1e7   # infeasible: IT air inlet would exceed ASHRAE recommended range
        heat = sum(tot[k] for k in keys) or 1.0
        res = dict(annual_cost=annual, capex=capex_tot, capex_parts=capex, opex=opex, e_cool_kWh=e_cool, extra_it_kWh=extra_it,
                   pPUE=1 + e_cool / E_IT, PUE_eff=1 + (e_cool + extra_it) / E_IT, WUE=tot["water"] * 1000 / E_IT,
                   water_m3=tot["water"], chiller_kWh=tot["chiller"], fan_kWh=tot["fan"], pump_kWh=tot["pump"], crah_kWh=tot["crah"],
                   peaks_kW={k: v / 1000 for k, v in pk.items()}, share={k: tot[k] / heat for k in keys}, heat_MWh={k: tot[k] / 1000 for k in keys},
                   Tg_trace=Tg_trace, warm_load_MW=float(Pw.mean() / 1e6), cool_load_MW=float(Pc / 1e6))
        if record:
            res["rec"] = rec
        return res
