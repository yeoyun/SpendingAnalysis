# app/styles.py
import numpy as np


# =====================
# Color Palette
# =====================
PRIMARY_COLOR = "#F00176"
GRAY_100 = "#F7F8F9"
GRAY_300 = "#D1D5DB"
GRAY_500 = "#9CA3AF"
GRAY_700 = "#72787F"


def gray_gradient(t: float) -> str:
    """
    t = 0 → 진한 회색
    t = 1 → 연한 회색
    """
    start = np.array([114, 120, 127])   # GRAY_700
    end   = np.array([247, 248, 249])   # GRAY_100
    rgb = (start + (end - start) * t).astype(int)
    return f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"
