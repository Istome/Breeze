"""Approximate monthly climate normals for the two study sites and a synthetic
'average day' per month.  Values are rounded long-term normals typical of a
Phoenix-like (hot-dry) and a Houston-like (hot-humid) and a Riyadh-like (arid) site; they are inputs for a
comparative study, not a substitute for TMY weather files."""
import numpy as np

from .climate_day import ambient_profile

C = lambda f: (np.asarray(f, float) - 32) / 1.8 + 273.15
SITES = {
    "hot-dry": dict(
        lat=33.45,
        Tmax=C([67, 71, 77, 85, 95, 104, 106, 105, 100, 89, 76, 66]),
        Tmin=C([46, 49, 54, 60, 69, 78, 84, 83, 77, 65, 53, 45]),
        Tdp=C([33, 33, 34, 33, 34, 37, 55, 59, 52, 41, 34, 33]),
        cloud=np.array([0.40, 0.38, 0.35, 0.25, 0.18, 0.12, 0.35, 0.35, 0.22, 0.25, 0.30, 0.38]),
    ),
    "hot-humid": dict(
        lat=29.76,
        Tmax=C([63, 67, 74, 80, 87, 92, 94, 95, 90, 83, 73, 65]),
        Tmin=C([43, 47, 54, 60, 68, 74, 75, 75, 70, 61, 51, 45]),
        Tdp=C([41, 44, 51, 58, 65, 70, 72, 72, 68, 59, 50, 43]),
        cloud=np.array([0.60, 0.58, 0.55, 0.55, 0.55, 0.50, 0.50, 0.50, 0.50, 0.45, 0.55, 0.60]),
    ),
    "arid": dict(  # Riyadh-like: very dry, no monsoon
        lat=24.7,
        Tmax=np.array([20, 23, 28, 33, 39, 42, 43, 43, 40, 35, 27, 22], float) + 273.15,
        Tmin=np.array([9, 11, 15, 20, 26, 28, 29, 29, 26, 21, 15, 10], float) + 273.15,
        Tdp=np.array([3, 2, 2, 3, 2, 0, 0, 1, 1, 2, 4, 4], float) + 273.15,
        cloud=np.array([0.25, 0.25, 0.30, 0.30, 0.15, 0.05, 0.05, 0.05, 0.05, 0.10, 0.20, 0.25]),
    ),
}
MONTH_DOY = np.array([15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349])
DAYS = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def month_hours(site, m, hours):
    s = SITES[site]
    return ambient_profile(hours, s["Tmin"][m], s["Tmax"][m])


def soil_temperature(site, z, doy, alpha=0.05, shaded=True):
    """Kusuda-Achenbach soil temperature (K) at depth z (m), day of year doy.
    alpha in m^2/day. Under the plate the surface sees no sun, so the surface mean
    is the air mean; sunlit desert soil runs ~4 K warmer on average."""
    s = SITES[site]
    Tm = 0.5 * (s["Tmax"] + s["Tmin"])
    mean = Tm.mean() + (0.0 if shaded else 4.0)
    amp = 0.5 * (Tm.max() - Tm.min()) * (1.0 if shaded else 1.15)
    t0 = MONTH_DOY[np.argmin(Tm)]
    d = np.sqrt(365 * alpha / np.pi)
    return mean - amp * np.exp(-z / d) * np.cos(2 * np.pi / 365 * (doy - t0 - z / 2 * np.sqrt(365 / (np.pi * alpha))))
