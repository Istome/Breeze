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
# plan additions: pit outline, light courts, stacks
pa = p.pit_volume / p.pit_depth
ex, ey = X / 2 - p.enclosure_inset, Y / 2 - p.enclosure_inset
sy = min(2 * ey, np.sqrt(pa * ey / ex)); sx = pa / sy
ax.add_patch(plt.Rectangle((-sx / 2, -sy / 2), sx, sy, fc="#2f6fdf", alpha=0.10, ec="#2f6fdf", lw=0.8, ls=":"))
ax.text(-sx / 2 + 0.5, -sy / 2 + 0.6, f"seasonal pit {p.pit_volume:,.0f} m³ (below)", fontsize=6.5, color="#2f6fdf")
for k in range(p.lightwells):
    cx = (-1 + 2 * (k + 0.5) / p.lightwells) * ex * 0.6
    ax.add_patch(plt.Rectangle((cx - p.lightwell_size / 2, -p.lightwell_size / 2), p.lightwell_size, p.lightwell_size, fc="#f2c14e", alpha=0.35, ec="#8a6d00", lw=0.6))
for k in range(p.stacks):
    cx = (-1 + 2 * (k % 2 + 0.5) / 2) * ex * 0.55
    cy = (-1 + 2 * (k // 2 + 0.5) / 2) * ey * 0.5 if p.stacks > 2 else 0.0
    ax.add_patch(plt.Circle((cx, cy), p.stack_diameter / 2, fc="#5d6b7a", ec="none"))

# N-S section through x = 0 (offset to pass through a stack)
ax2 = fig.add_subplot(1, 2, 2)
y = np.linspace(-p.plot_y / 2, p.plot_y / 2, 300)
zt = plate_z(p, 0, y)
d = p.core + 0.0022
ax2.fill_between(y, zt - d, zt, color="#2f6fdf", lw=0, label="radiant plate, 100 mm still-air cells")
ax2.plot(y, zt - d - p.beam_depth, color="#8a6d4b", lw=1.2, label="glulam grillage")
g = p.column_grid
for yc in np.arange(-p.plot_y / 2 + g / 2, p.plot_y / 2, g):
    zb = plate_z(p, 0, yc + g / 4) - d - p.beam_depth
    fork = zb - p.fork_drop
    ax2.plot([yc, yc], [0, fork], color="#5d6b7a", lw=2.2)
    for s_ in (-1, 1):
        ax2.plot([yc, yc + s_ * g / 4], [fork, plate_z(p, 0, yc + s_ * g / 4) - d - p.beam_depth], color="#5d6b7a", lw=1.3)
zb = -p.sunk_storeys * p.storey_height
ax2.add_patch(plt.Rectangle((-ey, zb), 2 * ey, -zb, fc="#e9e2d6", ec="#6e7781", lw=0.8, label=f"{p.sunk_storeys} sunk storeys (earth-sheltered)"))
for k in range(1, p.sunk_storeys):
    ax2.plot([-ey, ey], [-k * p.storey_height] * 2, color="#a39a8c", lw=0.6)
a_ = np.linspace(0, np.pi, 60)
ax2.fill_between(-ey * np.cos(a_), 0, (p.vault_rise + p.vault_cover) * np.sin(a_), color="#8c6e52", alpha=0.75, lw=0, label="earth vault: 0.6 m soil + PIR")
ax2.fill_between(-ey * np.cos(a_), 0, p.vault_rise * np.sin(a_), color="#e9e2d6", lw=0)
ax2.add_patch(plt.Rectangle((-sy / 2, zb - p.pit_depth), sy, p.pit_depth - 0.4, fc="#5b8fd9", ec="none", alpha=0.75, label=f"seasonal pit {p.pit_volume:,.0f} m³, 12–20 °C"))
ys = -ey * 0.25
ax2.add_patch(plt.Rectangle((ys - p.stack_diameter / 2, zb + p.storey_height * 0.2), p.stack_diameter, plate_z(p, 0, ys) + p.stack_above_plate - zb - p.storey_height * 0.2, fc="#5d6b7a", alpha=0.55, ec="none", label="night-flush stack"))
ax2.annotate("", xy=(ys, plate_z(p, 0, ys) + p.stack_above_plate + 2.5), xytext=(ys, plate_z(p, 0, ys) + p.stack_above_plate), arrowprops=dict(arrowstyle="->", color="#c9521f"))
ax2.plot([p.plot_y / 2 * 0.96, p.plot_y / 2 * 0.96, ey * 0.9], [1.5, -3, -3], color="#555", lw=1.4, ls="--", label="earth tube at −3 m")
ax2.axhline(0, color="#6e7781", lw=0.8)
for a in np.radians([-60, -30, 0, 30, 60]):
    ax2.annotate("", xy=(6 + np.sin(a) * 7, 13 + np.cos(a) * 7), xytext=(6, zt.max() + 0.3),
                 arrowprops=dict(arrowstyle="->", color="#e0642a", lw=0.8, alpha=0.4 + 0.6 * np.cos(a)))
ax2.set(xlabel="N–S (m)", ylabel="elevation (m)", title="Section A–A (N–S), round 2", ylim=(zb - p.pit_depth - 1.5, 22), aspect="equal")
ax2.legend(fontsize=6, loc="upper left", ncol=2)
save(fig, "fig0_cad.png")
