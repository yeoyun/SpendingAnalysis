# app/charts.py
import textwrap

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

from styles import PRIMARY_COLOR, GRAY_300, gray_gradient


# =====================
# 공통: period 컬럼 생성
# =====================
def _ensure_datetime(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "date" not in df.columns:
        raise KeyError("df must have 'date' column")
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"])
    return df


def _make_period_series(date_series: pd.Series, period_type: str) -> pd.Series:
    """
    period_type: '년간' | '월간' | '주간' | '일간'
    """
    period_type = (period_type or "월간").strip()

    if period_type == "년간":
        # 예: 2025
        return date_series.dt.to_period("Y").astype(str)
    if period_type == "월간":
        # 예: 2025-02
        return date_series.dt.to_period("M").astype(str)
    if period_type == "주간":
        # 예: 2025-02-03/2025-02-09 (ISO week period 표기)
        return date_series.dt.to_period("W").astype(str)
    if period_type == "일간":
        # 예: 2025-02-03
        return date_series.dt.to_period("D").astype(str)

    # fallback
    return date_series.dt.to_period("M").astype(str)


def _period_axis_title(period_type: str) -> str:
    period_type = (period_type or "월간").strip()
    return {
        "년간": "연도",
        "월간": "월",
        "주간": "주",
        "일간": "일",
    }.get(period_type, "월")


# =====================
# ✅ (NEW) 기간 단위 지출 추이 (년/월/주/일)
# 기존 draw_monthly_trend를 확장한 버전
# =====================
def draw_period_trend(df: pd.DataFrame, period_type: str = "월간"):
    df = _ensure_datetime(df)

    tmp = df.copy()
    tmp["period"] = _make_period_series(tmp["date"], period_type)

    period_df = (
        tmp
        .groupby("period")["amount"]
        .sum()
        .abs()
        .reset_index()
        .sort_values("period")
    )

    fig = go.Figure()

    fig.add_bar(
        x=period_df["period"],
        y=period_df["amount"],
        marker_color=GRAY_300,
        name=f"{period_type} 지출"
    )

    fig.add_scatter(
        x=period_df["period"],
        y=period_df["amount"],
        mode="lines+markers",
        line=dict(color=PRIMARY_COLOR, width=3),
        name="지출 추이"
    )

    fig.update_layout(
        xaxis_title=_period_axis_title(period_type),
        yaxis_title="지출 금액 (원)",
        hovermode="x unified"
    )

    return fig


# =====================
# (기존 호환) 월별 지출 추이
# - 기존 streamlit_app.py에서 draw_monthly_trend(df) 호출하던 부분 그대로 동작
# =====================
def draw_monthly_trend(df: pd.DataFrame):
    return draw_period_trend(df, period_type="월간")


# =====================
# 카테고리별 파이 차트
# (기간 단위 필터는 streamlit_app.py에서 df를 미리 필터링해서 넣어주면 됨)
# =====================
def draw_category_pie(df: pd.DataFrame):
    pie_df = (
        df
        .groupby("category_lv1")["amount"]
        .sum()
        .abs()
        .reset_index()
    )

    total = pie_df["amount"].sum()
    pie_df["ratio"] = pie_df["amount"] / total if total != 0 else 0

    major = pie_df[pie_df["ratio"] >= 0.05]
    minor = pie_df[pie_df["ratio"] < 0.05]

    if not minor.empty:
        pie_df = pd.concat([
            major,
            pd.DataFrame({
                "category_lv1": ["기타"],
                "amount": [minor["amount"].sum()],
                "ratio": [minor["ratio"].sum()]
            })
        ])

    pie_df = pie_df.sort_values("amount", ascending=False).reset_index(drop=True)

    colors = []
    for i, t in enumerate(np.linspace(0, 1, len(pie_df))):
        colors.append(PRIMARY_COLOR if i == 0 else gray_gradient(t))

    fig = go.Figure(
        data=[
            go.Pie(
                labels=pie_df["category_lv1"],
                values=pie_df["amount"],
                hole=0.4,
                marker=dict(colors=colors),
                textinfo="label+percent",
                sort=False
            )
        ]
    )

    return fig


# =====================
# 카테고리별 막대 차트
# =====================
def draw_category_bar(df: pd.DataFrame):
    bar_df = (
        df
        .groupby("category_lv1")["amount"]
        .sum()
        .abs()
        .sort_values(ascending=False)
        .reset_index()
    )

    fig = px.bar(
        bar_df,
        x="category_lv1",
        y="amount",
        text=bar_df["amount"].apply(lambda x: f"{int(x):,}원")
    )

    fig.update_traces(
        marker_color=PRIMARY_COLOR,
        textposition="outside"
    )

    fig.update_layout(
        xaxis_title="카테고리",
        yaxis_title="지출 금액 (원)"
    )

    return fig


# =====================
# 요일 · 시간대 히트맵
# (이건 '주간' 집계랑 다른 개념이라 period_type과 무관하게 유지)
# =====================
def draw_weekday_hour_heatmap(df: pd.DataFrame):
    weekday_map = {
        "Monday": "월", "Tuesday": "화", "Wednesday": "수",
        "Thursday": "목", "Friday": "금",
        "Saturday": "토", "Sunday": "일"
    }

    df = _ensure_datetime(df)
    df = df.copy()

    # hour 컬럼이 없다면 생성 (안전장치)
    if "hour" not in df.columns:
        df["hour"] = df["date"].dt.hour

    df["weekday"] = df["date"].dt.day_name().map(weekday_map)

    heatmap_df = (
        df
        .groupby(["weekday", "hour"])["amount"]
        .sum()
        .abs()
        .reset_index()
    )

    fig = px.density_heatmap(
        heatmap_df,
        x="hour",
        y="weekday",
        z="amount",
        color_continuous_scale=[
            "#F7F8F9",
            "#D1D5DB",
            "#9CA3AF",
            "#72787F"
        ]
    )

    fig.update_layout(
        xaxis_title="시간대",
        yaxis_title="요일"
    )

    return fig


# =====================
# ✅ (NEW) 기간 대비 증감 계산 (년/월/주/일)
# - 기존 calculate_mom_change_auto는 "월간" 고정이라 period_type 기반으로 일반화
# =====================
def calculate_period_change_auto(df: pd.DataFrame, period_type: str = "월간"):
    """
    period_type 기준으로 '최근 period' vs '이전 period' 카테고리별 증감 계산
    return: (result_df, current_period_str, previous_period_str)
    """
    df = _ensure_datetime(df)
    tmp = df.copy()
    tmp["period"] = _make_period_series(tmp["date"], period_type)

    # 문자열 period를 정렬 가능한 period 객체로 다시 만들기 어려운 케이스가 있어
    # 여기서는 'date' 기준으로 가장 최신 기간을 잡는 방식으로 처리합니다.
    # (기간 필터가 적용된 df를 넣는 걸 전제로 하면 정확함)
    tmp["_period_sort_key"] = tmp["date"]

    # 현재 period
    current_period = tmp.sort_values("_period_sort_key")["period"].iloc[-1]

    # 이전 period: current_period를 가진 row들 중 가장 이른 date 이전의 period 중 마지막
    current_mask = tmp["period"] == current_period
    before_current = tmp.loc[~current_mask].sort_values("_period_sort_key")

    if before_current.empty:
        # 비교 대상 없음
        empty = pd.DataFrame(columns=["category_lv1", "current", "previous", "diff", "pct_change"])
        return empty, str(current_period), ""

    previous_period = before_current["period"].iloc[-1]

    current_df = tmp[tmp["period"] == current_period]
    prev_df = tmp[tmp["period"] == previous_period]

    current_sum = (
        current_df.groupby("category_lv1")["amount"]
        .sum()
        .abs()
    )

    prev_sum = (
        prev_df.groupby("category_lv1")["amount"]
        .sum()
        .abs()
    )

    result = pd.concat([current_sum, prev_sum], axis=1)
    result.columns = ["current", "previous"]
    result = result.fillna(0)

    result["diff"] = result["current"] - result["previous"]
    denom = result["previous"].replace(0, np.nan)
    result["pct_change"] = (result["diff"] / denom) * 100
    result["pct_change"] = result["pct_change"].fillna(0)

    return result.reset_index(), str(current_period), str(previous_period)


# =====================
# (기존 호환) 전월 대비 카테고리 증감 (월간 고정)
# =====================
def calculate_mom_change_auto(df: pd.DataFrame):
    return calculate_period_change_auto(df, period_type="월간")


# =====================
# 전월/전기간 대비 카테고리 증감 (텍스트 그래프)
# - 기존 함수 그대로 사용 가능
# =====================
def render_mom_change_text(
    mom_df: pd.DataFrame,
    current_month: str,
    previous_month: str,
    top_n: int = 8,
    show_pct: bool = True,
):
    """
    - 상단: 전월 대비 총 증감(합계 diff)
    - 하단: 카테고리별 증감 Top N 텍스트 리스트(막대/차트 없음)
    """
    if mom_df is None or mom_df.empty:
        return "<div style='color:#9CA3AF;'>비교할 데이터가 없습니다.</div>"

    df = mom_df.copy()

    total_current = float(df["current"].sum())
    total_previous = float(df["previous"].sum())
    total_diff = total_current - total_previous

    total_arrow = "▲" if total_diff >= 0 else "▼"
    total_color = PRIMARY_COLOR if total_diff >= 0 else "#3B82F6"

    total_pct = 0.0
    if total_previous != 0:
        total_pct = (total_diff / total_previous) * 100

    df = df.sort_values("diff", key=lambda s: s.abs(), ascending=False).head(top_n)

    df["sign"] = np.where(df["diff"] >= 0, 1, -1)
    df = df.sort_values(["sign", "diff"], ascending=[False, False])

    rows = []
    for _, r in df.iterrows():
        cat = str(r["category_lv1"])
        diff = float(r["diff"])
        pct = float(r.get("pct_change", 0.0))

        arrow = "▲" if diff >= 0 else "▼"
        color = PRIMARY_COLOR if diff >= 0 else "#3B82F6"
        diff_abs = abs(diff)

        pct_text = f" ({pct:+.1f}%)" if show_pct else ""

        rows.append(
            f"<div style='display:flex; justify-content:space-between; align-items:center; padding:6px 0; border-bottom:1px solid #F3F4F6;'>"
            f"  <div style='font-size:14px; color:#111827;'>{cat}</div>"
            f"  <div style='font-size:14px; font-weight:600; color:{color};'>{arrow} {diff_abs:,.0f}원{pct_text}</div>"
            f"</div>"
        )

    html = f"""
    <div style="border:1px solid #F3F4F6; border-radius:12px; padding:12px; background:#FFFFFF;">
      <div style="font-size:12px; color:#9CA3AF; margin-bottom:6px;">
        {previous_month} → {current_month}
      </div>

      <div style="display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:10px;">
        <div style="font-size:18px; font-weight:600; color:#111827;">전체</div>
        <div style="font-size:21px; font-weight:800; color:{total_color};">
          {total_arrow} {abs(total_diff):,.0f}원 ({total_pct:+.1f}%)
        </div>
      </div>

      <div style="height:1px; background:#F3F4F6; margin:10px 0;"></div>

      {''.join(rows)}

      <div style="margin-top:8px; font-size:12px; color:#9CA3AF;">
        ▲ 증가 / ▼ 감소 (이전 기간 대비)
      </div>
    </div>
    """

    return textwrap.dedent(html).strip()