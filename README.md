# Breeze: Zenith Plate

This study asks one question from first principles: what building geometry rejects the most heat by thermal radiation? It contains:

- `breeze/`: physics and design code. It includes a two-band IR model with an angle-dependent sky, a clear-sky sun model, a vectorised Monte-Carlo ray tracer for cavities in the skin, a balance engine for convex massing, and a parametric CAD generator.
- `cae/`: the evaluations. Each script writes figures and JSON to `results/`.

| script | question |
|---|---|
| `s1_sky.py` | What does the sky look like to a surface? Coldness pattern ΔL(θ), crossover cone θ₀(ΔT), flux vs. tilt |
| `s2_massing.py` | Which convex massing (same volume and skin) rejects the most heat? |
| `s3_cells.py` | Do angular-selective cavities (CPC troughs, inverted-pyramid funnels) beat a flat emitter? MC ray tracing |
| `s4_panel_fea.py` | Hydronic channel pitch vs. sheet material (2-D finite-volume conduction) |
| `s5_structure.py` | Tile sandwich, glulam grillage and tree-column sizing, plus uplift and thermal movement |
| `s6_designday.py` | Whole-system design-day energy (radiation, absorbed sun, convection, wind-screen) for 9 roof systems in 2 climates |
| `s7_camber.py` | How much camber can the plate take before it loses sky? |
| `render_cad.py` | Plan and section drawing of the parametric model |

- `cad/`: `zenith_plate.scad` (OpenSCAD, Customizer-ready), plus OBJ/STL/JSON exports from `breeze/cad.py`. `skin_cell.stl` is one 300 mm skin cell.
- `docs/zenith_plate.html`: the interactive report, with a live parametric 3-D model and all CAE charts.

Run everything (about 15 min on 4 cores):

```bash
pip install numpy scipy matplotlib
for s in s1_sky s2_massing s3_cells s4_panel_fea s5_structure s6_designday s7_camber render_cad export_report_data; do python3 cae/$s.py; done
python3 -c "from breeze.cad import DesignParams, export_all; export_all(DesignParams(), 'cad')"
```

## Result in one paragraph

A convex envelope radiates P = ∫ A⊥(ω) ΔL(ω) dω. It acts as a projected-area filter laid over the sky's coldness pattern. The sky is cold only in a cone around the zenith, in the 8–13 µm window. So the optimum is a broad, sky-facing plate that covers the whole plot, with a shallow camber (rise/span ≤ 0.06 costs under 4 %). Its soffit and the enclosure walls are IR mirrors, which decouples them from the warm ground and horizon. The skin is a window-selective emitter under an LDPE wind-screen. Towers and cubes become net heat *gainers* below ambient. Angular-selective cavities were the starting hypothesis. They help only for deep sub-ambient operation with broadband emitters. At the system level they lose to spectral selectivity, because of mirror losses and extra absorbed sun. The optimiser drives their acceptance angle to about 85°, where the cavity becomes the rib grid that carries the wind-screen.
