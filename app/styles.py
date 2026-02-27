# app/styles.py
import numpy as np


# =====================
# Color Palette
# =====================
PRIMARY_COLOR = "#F00176"
GRAY_100 = "#F7F8F9"
GRAY_300 = "#D1D5DB"
GRAY_500 = "#9CA3AF"
GRAY_600 = "#72787F"
GRAY_700 = "#454753"
GRAY_800 = "#26282B"

BLACK = "#0B1215"

def gray_gradient(t: float) -> str:
    """
    t = 0 → 진한 회색
    t = 1 → 연한 회색
    """
    start = np.array([114, 120, 127])   # GRAY_700
    end   = np.array([247, 248, 249])   # GRAY_100
    rgb = (start + (end - start) * t).astype(int)
    return f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"

def _render_delta_row(st_module, *, label: str, delta_value: float) -> None:
    from app.charts import _format_won
    """전년/전월 대비 텍스트 + 예쁜 delta pill(금액) 한 줄 렌더"""
    v = float(delta_value)

    if v > 0:
        arrow, bg, color = "▲", "#FEE2E2", "#DC2626"
    elif v < 0:
        arrow, bg, color = "▼", "#DBEAFE", "#2563EB"
    else:
        arrow, bg, color = "•", "#F3F4F6", "#6B7280"

    st_module.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:8px; margin-top:-20px;">
          <span style="font-size:13px; color:#9CA3AF; font-weight:300;">{label}</span>
          <span style="
            display:inline-flex; align-items:center; gap:6px;
            padding:4px 10px; border-radius:999px;
            background:{bg}; color:{color};
            font-size:13px; font-weight:800; line-height:1;
          ">{arrow} {_format_won(v)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )