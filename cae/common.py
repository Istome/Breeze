import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES = os.path.join(ROOT, "results")
os.makedirs(RES, exist_ok=True)

INK, MUTED, GRID = "#1f2328", "#6e7781", "#d8dee4"
C = ["#2f6fdf", "#e0642a", "#1a9e75", "#b4489c", "#8a6d00", "#5d6b7a", "#d23b5a", "#3fa7c9", "#111111"]
plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 160, "font.size": 9.5, "axes.edgecolor": MUTED,
    "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "axes.prop_cycle": matplotlib.cycler(color=C), "legend.frameon": False,
})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(RES, name), bbox_inches="tight")
    plt.close(fig)


def dump(name, obj):
    with open(os.path.join(RES, name), "w") as f:
        json.dump(obj, f, indent=1, default=float)
