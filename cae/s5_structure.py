"""CAE-5  Structural sizing of the plate (hand-calc level, Eurocode-style factors).

Load path: 3x3 m sandwich tiles -> purlins @3 m (6 m span) -> glulam grillage on a
uniform 6 m grid formed by the branch tips of tree columns at 12 m centres.
"""
import numpy as np
from common import plt, save, dump, C

E_al, G_core, E_core, tau_core = 69e9, 2.5e6, 4.0e6, 0.12e6
t_top, t_bot = 1.5e-3, 0.7e-3
gk_tile = 0.15e3   # Pa: skin, core, water, film, ribs
gk_frame = 0.10e3  # Pa: purlins + grillage smeared
qk_live, w_up = 0.6e3, 1.2e3  # maintenance/snow ; net wind uplift (exposed canopy)
ULS = lambda g, q: 1.35 * g + 1.5 * q


def tile(core, L=3.0):
    d = core + (t_top + t_bot) / 2
    D = E_al * t_top * t_bot * d**2 / (t_top + t_bot)  # per m width
    S = G_core * d**2 / core
    q = gk_tile + qk_live
    defl = 5 * q * L**4 / (384 * D) + q * L**2 / (8 * S)
    qu = ULS(gk_tile, qk_live)
    M, V = qu * L**2 / 8, qu * L / 2
    sig_face = M / (d * t_bot)          # bottom face tension / top compression ~ M/(d t)
    sig_top = M / (d * t_top)
    wrinkle = 0.5 * (E_al * E_core * G_core) ** (1 / 3)
    tau = V / d
    up_defl = 5 * (w_up - gk_tile) * L**4 / (384 * D) + (w_up - gk_tile) * L**2 / (8 * S)
    return dict(core_mm=core * 1e3, defl_mm=defl * 1e3, limit_mm=L / 200 * 1e3, sig_top_MPa=sig_top / 1e6,
                wrinkle_MPa=wrinkle / 1e6, tau_core_kPa=tau / 1e3, tau_allow_kPa=tau_core / 1e3, uplift_defl_mm=up_defl * 1e3)


cores = np.array([0.04, 0.06, 0.08, 0.10, 0.12])
tiles = [tile(c) for c in cores]
for t in tiles:
    print({k: round(v, 2) for k, v in t.items()})
chosen = tile(0.08)

# glulam GL28h purlins (3 m tributary, 6 m span) and primaries (6 m trib, 6 m span)
E_gl, f_m = 12.6e9, 28e6 * 0.8 / 1.25  # kmod/gammaM
def beam(trib, L, b):
    g = (gk_tile + gk_frame) * trib
    q = qk_live * trib
    I_req = 5 * (g + q) * L**4 / (384 * E_gl * (L / 300))
    M = ULS(g, q) * L**2 / 8
    h_I = (12 * I_req / b) ** (1 / 3)
    h_M = np.sqrt(6 * M / (b * f_m))
    return dict(b_mm=b * 1e3, h_req_mm=max(h_I, h_M) * 1e3, governs="deflection" if h_I > h_M else "bending", M_kNm=M / 1e3)
purlin = beam(3.0, 6.0, 0.10)
primary = beam(6.0, 6.0, 0.20)
print("purlin", purlin, "\nprimary", primary)

# tree column: 12x12 m tributary, 4 diagonal branches, tips at (+-3,+-3) m, fork 2.2 m below beam
A_trib = 144.0
N = ULS(gk_tile + gk_frame, qk_live) * A_trib
alpha = np.arctan(3 * np.sqrt(2) / 2.2)
N_branch = N / 4 / np.cos(alpha)
H_branch = N / 4 * np.tan(alpha)      # horizontal thrust, balanced by opposite branch through node
# steel CHS trunk S355, buckling (Euler + 0.49 imperfection curve approximation)
def chs(D, t, L):
    A = np.pi * (D**2 - (D - 2 * t) ** 2) / 4
    I = np.pi * (D**4 - (D - 2 * t) ** 4) / 64
    Ncr = np.pi**2 * 210e9 * I / L**2
    lam = np.sqrt(A * 355e6 / Ncr)
    phi = 0.5 * (1 + 0.21 * (lam - 0.2) + lam**2)
    chi = min(1, 1 / (phi + np.sqrt(phi**2 - lam**2)))
    return chi * A * 355e6 / 1.0
trunk_L = 6.0 - 0.6 - 2.2 + 1.0
trunk = dict(N_Ed_kN=N / 1e3, N_bRd_kN=chs(0.273, 0.008, trunk_L * 2) / 1e3, section="CHS 273x8 (cantilever, Lcr=2L)")
branch = dict(N_Ed_kN=N_branch / 1e3, H_kN=H_branch / 1e3, N_bRd_kN=chs(0.1683, 0.008, 2.2 / np.cos(alpha)) / 1e3, section="CHS 168.3x8")
uplift = dict(net_uplift_per_col_kN=(w_up * 1.5 - gk_tile - gk_frame) * A_trib / 1e3)
print("trunk", trunk, "\nbranch", branch, "\nuplift", uplift)

# thermal movement of aluminium skin, 3 m tile, 60 K swing (night -> sun)
dL_tile = 23e-6 * 60 * 3.0 * 1e3
fig, ax = plt.subplots(1, 1, figsize=(5.4, 3.4))
ax.plot(cores * 1e3, [t["defl_mm"] for t in tiles], marker="o", label="gravity SLS (0.75 kPa)")
ax.plot(cores * 1e3, [t["uplift_defl_mm"] for t in tiles], marker="s", label="wind uplift (1.2 kPa)")
ax.axhline(15, color="#b4489c", ls="--", lw=0.9, label="limit L/200 = 15 mm")
ax.set(xlabel="PIR core depth (mm)", ylabel="mid-span deflection (mm)", title="3 m roll-bond sandwich tile")
ax.legend(fontsize=7.5)
save(fig, "fig5_structure.png")
dump("s5_structure.json", dict(tiles=tiles, chosen_tile=chosen, purlin=purlin, primary=primary, trunk=trunk,
                               branch=branch, uplift=uplift, tile_thermal_movement_mm=dL_tile))
print("tile movement mm", dL_tile)
