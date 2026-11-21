import numpy as np


def ambient_profile(hours, T_min=297.15, T_max=311.15, t_min=5.0, t_max=15.0):
    """Asymmetric-sinusoid design day (default: hot-dry summer, 24-38 C)."""
    h = np.asarray(hours, float) % 24
    rise = (h >= t_min) & (h <= t_max)
    x_r = (h - t_min) / (t_max - t_min)
    x_f = ((h - t_max) % 24) / (24 - (t_max - t_min))
    T = np.where(rise, T_min + (T_max - T_min) * (1 - np.cos(np.pi * x_r)) / 2,
                 T_max - (T_max - T_min) * (1 - np.cos(np.pi * x_f)) / 2)
    return T
