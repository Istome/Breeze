"""Render the parametric CAD model to PNG (isometric + section) for the report."""
import numpy as np
from common import plt, save
from breeze.cad import DesignParams, building, plate_z

p = DesignParams()
fig = plt.figure(figsize=(12, 4.4))
ax = fig.add_subplot(1, 2, 1)
X, Y, g = p.plot_x, p.plot_y, p.column_grid
for xt in np.arange(-X / 2, X / 2 + 1e-6, p.tile):
    ax.plot([xt, xt], [-Y / 2, Y / 2], color="#d8dee4", lw=0.4)
for yt in np.arange(-Y / 2, Y / 2 + 1e-6, p.tile):
    ax.plot([-X / 2, X / 2], [yt, yt], color="#d8dee4", lw=0.4)
for x in np.arange(-X / 2 + g / 4, X / 2, g / 2):
    ax.plot([x, x], [-Y / 2, Y / 2], color="#8a6d4b", lw=1.1)
for y in np.arange(-Y / 2 + g / 4, Y / 2, g / 2):
    ax.plot([-X / 2, X / 2], [y, y], color="#8a6d4b", lw=1.1)
for x in np.arange(-X / 2 + g / 2, X / 2, g):
    for y in np.arange(-Y / 2 + g / 2, Y / 2, g):
        for dx in (-1, 1):
            for dy in (-1, 1):
                ax.plot([x, x + dx * g / 4], [y, y + dy * g / 4], color="#5d6b7a", lw=1.0)
        ax.plot(x, y, "o", color="#5d6b7a", ms=5)
i = p.enclosure_inset
ax.add_patch(plt.Rectangle((-X / 2 + i, -Y / 2 + i), X - 2 * i, Y - 2 * i, fc="none", ec="#1f2328", lw=1.0, ls="--"))
zz = np.linspace(-X / 2, X / 2, 80)
GX, GY = np.meshgrid(zz, np.linspace(-Y / 2, Y / 2, 60))
cs = ax.contour(GX, GY, plate_z(p, GX, GY), levels=6, colors="#2f6fdf", linewidths=0.6)
ax.clabel(cs, fmt="%.1f m", fontsize=6)
ax.add_patch(plt.Rectangle((X / 2 - 6, -Y / 2), 6, 6, fc="#2f6fdf", alpha=0.15, ec="none"))
ax.text(X / 2 - 5.8, -Y / 2 + 6.4, "cell detail", fontsize=6.5, color="#2f6fdf")
ax.annotate("N", xy=(X / 2 + 3, Y / 2), xytext=(X / 2 + 3, Y / 2 - 7), arrowprops=dict(arrowstyle="->"), ha="center")
ax.set(aspect="equal", xlabel="E–W (m)", ylabel="N–S (m)",
       title=f"Plan: {X:.0f}×{Y:.0f} m plate · {p.tile:.0f} m tiles · {g/2:.0f} m grillage · tree columns @ {g:.0f} m")
ax.grid(False)
# N-S section through x = 0
ax2 = fig.add_subplot(1, 2, 2)
y = np.linspace(-p.plot_y / 2, p.plot_y / 2, 300)
zt = plate_z(p, 0, y)
d = p.core + 0.0022
ax2.fill_between(y, zt - d, zt, color="#2f6fdf", lw=0, label="radiant plate (emitter up, low-e soffit)")
ax2.plot(y, zt - d - p.beam_depth, color="#8a6d4b", lw=1.2, label="glulam grillage")
i = p.enclosure_inset
ax2.add_patch(plt.Rectangle((-p.plot_y / 2 + i, 0), p.plot_y - 2 * i, p.enclosure_height, fc="#e9ecef", ec="#6e7781", lw=0.8, label="low-e programme volume"))
g = p.column_grid
for yc in np.arange(-p.plot_y / 2 + g / 2, p.plot_y / 2, g):
    zb = plate_z(p, 0, yc + g / 4) - d - p.beam_depth
    fork = zb - p.fork_drop
    ax2.plot([yc, yc], [0, fork], color="#5d6b7a", lw=2.2)
    for s in (-1, 1):
        ax2.plot([yc, yc + s * g / 4], [fork, plate_z(p, 0, yc + s * g / 4) - d - p.beam_depth], color="#5d6b7a", lw=1.3)
r_t = (p.tank_volume_m3 / (np.pi * 5.0)) ** 0.5
ax2.add_patch(plt.Rectangle((-r_t, -6), 2 * r_t, 5, fc="#5b8fd9", ec="none", alpha=0.7, label=f"{p.tank_volume_m3:.0f} m³ buried water store"))
ax2.axhline(0, color="#6e7781", lw=0.8)
for a in np.radians([-85, -60, -30, 0, 30, 60, 85]):
    ax2.annotate("", xy=(np.sin(a) * 9, 9.5 + np.cos(a) * 9), xytext=(0, zt.max() + 0.3),
                 arrowprops=dict(arrowstyle="->", color="#e0642a", lw=0.8, alpha=0.4 + 0.6 * np.cos(a)))
ax2.text(0.6, 18.6, "sky window (8–13 µm) — coldest at zenith", fontsize=7.5, color="#e0642a")
ax2.set(xlabel="N–S (m)", ylabel="elevation (m)", title="Section A–A (N–S)", ylim=(-7, 24), aspect="equal")
ax2.legend(fontsize=6.5, loc="upper left", ncol=1)
save(fig, "fig0_cad.png")
