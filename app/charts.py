# app/charts.py
import textwrap

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

from app.ui_utils import _daily_cum_for_year_month
from styles import GRAY_500, PRIMARY_COLOR, GRAY_300, _render_delta_row, gray_gradient


# =====================
# ✅ 소비(지출) 집계용 컬럼 선택
# - preprocess에서 spend_amount(지출만, 양수) 생성하는 것을 기준으로 사용
# - 없으면 amount_abs -> 없으면 abs(amount) fallback
# =====================
CONSUMPTION_CATEGORIES_12 = [
    "금융",
    "온라인쇼핑",
    "식비",
    "교통",
    "주거/통신",
    "구독",
    "문화/여가",
    "교육/학습",
    "생활",
    "카페/간식",
    "패션/쇼핑",
    "기타",
]

def _get_spend_series(df: pd.DataFrame) -> pd.Series:
    """지출(소비) 금액 시리즈를 반환합니다. (항상 양수)"""
    if df is None or len(df) == 0:
        return pd.Series([], dtype=float)

    if "spend_amount" in df.columns:
        return pd.to_numeric(df["spend_amount"], errors="coerce").fillna(0.0)

    if "amount_abs" in df.columns:
        return pd.to_numeric(df["amount_abs"], errors="coerce").fillna(0.0)

    if "amount" in df.columns:
        return pd.to_numeric(df["amount"], errors="coerce").fillna(0.0).abs()

    return pd.Series([0.0] * len(df), index=df.index, dtype=float)


# =====================
# 공통: period 컬럼 생성
# =====================
def _ensure_datetime(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # --- date 보정 ---
    if "date" not in df.columns:
        raise KeyError("df must have 'date' column")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()

    # --- amount 보정 (핵심) ---
    if "amount" in df.columns:
        s = df["amount"]

        # 문자열/혼합 타입 대비: 콤마, 통화기호, 공백 제거
        # - 숫자/소수점/마이너스만 남기기
        s = s.astype(str).str.replace(",", "", regex=False)
        s = s.str.replace(r"[^\d\.-]", "", regex=True)

        df["amount"] = pd.to_numeric(s, errors="coerce").fillna(0)
        
    # --- spend_amount 보정 (전처리에서 만든 소비 전용 컬럼이 있으면 숫자화) ---
    if "spend_amount" in df.columns:
        df["spend_amount"] = pd.to_numeric(df["spend_amount"], errors="coerce").fillna(0.0)
    if "amount_abs" in df.columns:
        df["amount_abs"] = pd.to_numeric(df["amount_abs"], errors="coerce").fillna(0.0)
        
    return df


def _make_period_series(date_series: pd.Series, period_type: str) -> pd.Series:
    """
    period_type: '년간' | '월간' | '주간' | '일간'
    """
    period_type = (period_type or "월간").strip()

    if period_type == "년간":
        return date_series.dt.to_period("Y").astype(str)
    if period_type == "월간":
        return date_series.dt.to_period("M").astype(str)
    if period_type == "주간":
        return date_series.dt.to_period("W").astype(str)
    if period_type == "일간":
        return date_series.dt.to_period("D").astype(str)

    return date_series.dt.to_period("M").astype(str)


def _period_axis_title(period_type: str) -> str:
    period_type = (period_type or "월간").strip()
    return {
        "년간": "연도",
        "월간": "월",
        "주간": "주",
        "일간": "일",
    }.get(period_type, "월")


def _format_won(v: float) -> str:
    try:
        return f"{int(round(float(v))):,}원"
    except Exception:
        return "-"


def _format_manwon_1(v: float) -> str:
    """
    0.1만원 단위 표기 (소수점 1자리)
    예: 87112 -> 8.7만원
    """
    try:
        return f"{float(v)/10000:.1f}만원"
    except Exception:
        return "-"


def _spend_col(df: pd.DataFrame) -> str:
    """
    소비(지출) 합산에 사용할 컬럼명 반환
    - preprocess에서 spend_amount를 만들었으면 그걸 최우선 사용
    - 없으면 amount_abs
    - 없으면 abs(amount)
    """
    if df is None:
        return "amount"

    if "spend_amount" in df.columns:
        return "spend_amount"
    if "amount_abs" in df.columns:
        return "amount_abs"
    return "amount"


# =====================================================
# ✅ KPI 계산/렌더
# =====================================================

def draw_kpi_cards_data(df: pd.DataFrame, *, period_type: str = "월간") -> dict:
    period_type = (period_type or "월간").strip()

    if df is None or df.empty:
        return {
            "total_spend": 0.0,
            "current_spend": 0.0,
            "prev_spend": 0.0,
            "delta": 0.0,
            "pct": None,
            "current_period": "",
            "prev_period": "",
            "top_category": "-",
            "top_category_amount": 0.0,
        }

    tmp = _ensure_datetime(df).copy()

    # ✅ 소비 합산 컬럼 선택
    col = _spend_col(tmp)

    # ✅ spend_amount가 없다면 amount를 abs로 안전 처리 (기존 로직 호환)
    if col == "amount":
        tmp["_spend"] = pd.to_numeric(tmp["amount"], errors="coerce").fillna(0.0).abs()
    else:
        tmp["_spend"] = pd.to_numeric(tmp[col], errors="coerce").fillna(0.0)

    # ✅ period 컬럼 생성 (기존 로직 유지)
    tmp["period"] = _make_period_series(tmp["date"], period_type)

    # ✅ 현재 period = 최신 date가 속한 period (기존 방식 유지)
    tmp = tmp.sort_values("date")
    current_period = tmp["period"].iloc[-1]

    current_mask = tmp["period"] == current_period
    current_spend = float(tmp.loc[current_mask, "_spend"].sum())

    # ✅ 직전 period
    prev_period = ""
    prev_spend = 0.0
    prev_candidates = tmp.loc[~current_mask, "period"]
    if not prev_candidates.empty:
        prev_period = prev_candidates.iloc[-1]
        prev_spend = float(tmp.loc[tmp["period"] == prev_period, "_spend"].sum())

    delta = current_spend - prev_spend
    pct = None
    if prev_spend != 0:
        pct = (delta / prev_spend) * 100

    total_spend = float(tmp["_spend"].sum())

    # ✅ 최고 소비 분류
    top_category = "-"
    top_category_amount = 0.0
    if "category_lv1" in tmp.columns:
        cat_sum = (
            tmp.loc[current_mask]
            .groupby("category_lv1")["_spend"]
            .sum()
            .sort_values(ascending=False)
        )
        if not cat_sum.empty:
            top_category = str(cat_sum.index[0])
            top_category_amount = float(cat_sum.iloc[0])

    return {
        "total_spend": total_spend,
        "current_spend": current_spend,
        "prev_spend": prev_spend,
        "delta": delta,
        "pct": pct,
        "current_period": str(current_period),
        "prev_period": str(prev_period),
        "top_category": top_category,
        "top_category_amount": top_category_amount,
    }


def render_kpi_cards(
    st_module,
    df: pd.DataFrame,
    *,
    period_type: str = "월간",
):
    k = draw_kpi_cards_data(df, period_type=period_type)

    period_type = (period_type or "월간").strip()

    # 자연스러운 KPI 라벨
    label_map = {
        "년간": "올해 소비금액",
        "월간": "이번 달 소비금액",
        "주간": "이번 주 소비금액",
        "일간": "오늘 소비금액",
    }

    # delta 설명용 텍스트
    delta_map = {
        "년간": "전년 대비",
        "월간": "전월 대비",
        "주간": "전주 대비",
        "일간": "전일 대비",
    }

    current_label = label_map.get(period_type, "이번 달 소비금액")
    delta_label = delta_map.get(period_type, "이전 기간 대비")

    c1, c2, c3 = st_module.columns(3, vertical_alignment="top")

    with c1:
        st_module.metric("총 소비금액", _format_won(k["total_spend"]))

    with c2:
        st_module.metric(
            current_label,
            _format_won(k["current_spend"]),
            delta=None,  # ✅ 기본 delta 박스 제거
        )
        _render_delta_row(st_module, label=delta_label, delta_value=k["delta"])

    with c3:
        st_module.metric(
            "최고 소비 분류",
            f'{k["top_category"]} · {_format_won(k["top_category_amount"])}'
        )

# =====================
# ✅ 기간 단위 지출 추이 (년/월/주/일)
# =====================

def draw_period_trend(df: pd.DataFrame, period_type: str = "월간"):
    period_type = (period_type or "월간").strip()
    df = _ensure_datetime(df).copy()

    col = _spend_col(df)
    if col == "amount":
        df["_spend"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0).abs()
    else:
        df["_spend"] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # ✅ period 생성 로직은 그대로
    df["period"] = _make_period_series(df["date"], period_type)

    trend = (
        df.groupby("period")["_spend"]
        .sum()
        .reset_index()
        .sort_values("period")
        .rename(columns={"_spend": "amount"})
    )

    # 상단 텍스트(만원 단위)
    trend["label_manwon"] = trend["amount"].apply(_format_manwon_1)

    fig = go.Figure()
    fig.add_bar(
        x=trend["period"],
        y=trend["amount"],
        text=trend["label_manwon"],
        textposition="outside",
        marker_color=GRAY_300,
        hovertemplate=f"{_period_axis_title(period_type)}: %{{x}}<br>지출: %{{y:,.0f}}원<extra></extra>",
        name="지출",
    )
    fig.add_scatter(
        x=trend["period"],
        y=trend["amount"],
        mode="lines+markers",
        line=dict(color=PRIMARY_COLOR, width=3),
        hovertemplate=f"{_period_axis_title(period_type)}: %{{x}}<br>지출: %{{y:,.0f}}원<extra></extra>",
        name="추이",
    )

    fig.update_layout(
        xaxis_title=_period_axis_title(period_type),
        yaxis_title="지출 금액 (원)",
        hovermode="x unified",
        margin=dict(t=50),
    )
    fig.update_yaxes(tickformat=",", separatethousands=True)
    return fig


# =====================
# 월간 누적차트
# =====================
def draw_monthly_daily_cumulative_compare(
    df_filtered: pd.DataFrame,
    addon_year: int | None,
    addon_month: int | None,
    filter_end: str | pd.Timestamp | None = None,   # ✅ 추가
    day_max: int = 31,
) -> tuple[go.Figure, pd.DataFrame]:
    # =========================
    # ✅ None 보정: 월 선택이 없으면 filter_end 기준으로 현재월 자동 선택
    # =========================
    if addon_year is None or addon_month is None:
        # filter_end가 없으면 df에서 가장 최근 date로 fallback
        if filter_end is not None:
            end_dt = pd.to_datetime(filter_end)
        else:
            dfx = _ensure_datetime(df_filtered)
            if dfx["date"].notna().any():
                end_dt = dfx["date"].max()
            else:
                end_dt = pd.Timestamp.today()

        addon_year = int(end_dt.year)
        addon_month = int(end_dt.month)

    cur = pd.Period(f"{int(addon_year):04d}-{int(addon_month):02d}", freq="M")
    prev = cur - 1

    sel_df = _daily_cum_for_year_month(df_filtered, cur.year, cur.month, day_max=day_max)
    prev_df = _daily_cum_for_year_month(df_filtered, prev.year, prev.month, day_max=day_max)

    merged = pd.DataFrame({"day": range(1, day_max + 1)})
    merged = merged.merge(
        sel_df.rename(columns={"daily": "daily_selected", "cum": "cum_selected"}),
        on="day",
        how="left",
    ).merge(
        prev_df.rename(columns={"daily": "daily_prev", "cum": "cum_prev"}),
        on="day",
        how="left",
    )

    for c in ["daily_selected", "cum_selected", "daily_prev", "cum_prev"]:
        merged[c] = pd.to_numeric(merged[c], errors="coerce").fillna(0)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=merged["day"],
            y=merged["cum_prev"],
            mode="lines",
            name=f"전월 누적 ({prev.year}.{prev.month:02d})",
            line=dict(color=GRAY_500, width=2, dash="dot"),
            hovertemplate="Day %{x}<br>누적 %{y:,.0f}원<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=merged["day"],
            y=merged["cum_selected"],
            mode="lines",
            name=f"선택월 누적 ({cur.year}.{cur.month:02d})",
            line=dict(color=PRIMARY_COLOR, width=4),
            hovertemplate="Day %{x}<br>누적 %{y:,.0f}원<extra></extra>",
        )
    )

    non_zero_days = merged[merged["daily_selected"] > 0]
    last_day = int(non_zero_days["day"].max()) if not non_zero_days.empty else 1
    last_value = float(merged.loc[merged["day"] == last_day, "cum_selected"].iloc[0])

    fig.add_trace(
        go.Scatter(
            x=[last_day],
            y=[last_value],
            mode="markers+text",
            marker=dict(size=20, color=PRIMARY_COLOR, line=dict(width=3, color="#FFFFFF")),
            text=[f"{last_value:,.0f}원"],
            textposition="top center",
            textfont=dict(size=14, color=PRIMARY_COLOR),
            showlegend=False,
            hovertemplate="Day %{x}<br>누적 %{y:,.0f}원<extra></extra>",
        )
    )

    right_pad = 1.8
    x_right = max(day_max, last_day) + right_pad

    fig.update_layout(
        height=380,
        margin=dict(l=10, r=20, t=40, b=10),
        xaxis=dict(title="일자", tickmode="linear", dtick=1, range=[1, x_right], showgrid=True),
        yaxis=dict(title="누적 지출(원)", tickformat=",.0f", showgrid=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )

    return fig, merged


# =====================
# 카테고리별 파이 차트
# =====================
def draw_category_pie(df: pd.DataFrame):
    df = _ensure_datetime(df).copy()
    df["_spend"] = _get_spend_series(df)  # ✅ 소비만

    pie_df = (
        df.groupby("category_lv1")["_spend"]
        .sum()
        .reindex(CONSUMPTION_CATEGORIES_12, fill_value=0.0)
        .reset_index()
        .rename(columns={"_spend": "amount"})
    )

    total = float(pie_df["amount"].sum())
    pie_df["ratio"] = pie_df["amount"] / total if total != 0 else 0

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
                sort=False,
                hovertemplate="%{label}<br>%{value:,.0f}원 (%{percent})<extra></extra>",
            )
        ]
    )
    return fig

# =====================
# ✅ 카테고리별 막대 차트
# - 막대 상단: 0.1만원 단위 표기 (0.0만원)
# - hover: 원 단위 정확 표기
# =====================

def draw_category_bar(df: pd.DataFrame):
    df = _ensure_datetime(df).copy()
    df["_spend"] = _get_spend_series(df)  # ✅ 소비만

    bar_df = (
        df.groupby("category_lv1")["_spend"]
        .sum()
        .reindex(CONSUMPTION_CATEGORIES_12, fill_value=0.0)
        .reset_index()
        .rename(columns={"_spend": "amount"})
    )

    # 보기 좋게: 금액 큰 순으로 정렬
    bar_df = bar_df.sort_values("amount", ascending=False).reset_index(drop=True)
    bar_df["label_manwon"] = bar_df["amount"].apply(_format_manwon_1)

    fig = px.bar(
        bar_df,
        x="category_lv1",
        y="amount",
        text="label_manwon",
    )

    fig.update_traces(
        marker_color=PRIMARY_COLOR,
        textposition="outside",
        hovertemplate="카테고리: %{x}<br>지출: %{y:,.0f}원<extra></extra>",
    )

    fig.update_layout(
        xaxis_title="카테고리",
        yaxis_title="지출 금액 (원)",
    )
    fig.update_yaxes(tickformat=",", separatethousands=True)
    return fig

# =====================
# 요일 · 시간대 히트맵
# =====================
def draw_weekday_hour_heatmap(df: pd.DataFrame):
    weekday_map = {
        "Monday": "월", "Tuesday": "화", "Wednesday": "수",
        "Thursday": "목", "Friday": "금",
        "Saturday": "토", "Sunday": "일"
    }

    df = _ensure_datetime(df).copy()

    if "hour" not in df.columns:
        df["hour"] = df["date"].dt.hour

    df["weekday"] = df["date"].dt.day_name().map(weekday_map)

    # ✅ 소비만
    df["_spend"] = _get_spend_series(df)

    heatmap_df = (
        df.groupby(["weekday", "hour"])["_spend"]
        .sum()
        .reset_index()
        .rename(columns={"_spend": "amount"})
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
        ],
    )

    fig.update_layout(xaxis_title="시간대", yaxis_title="요일")
    fig.update_traces(
        hovertemplate="요일: %{y}<br>시간: %{x}시<br>지출: %{z:,.0f}원<extra></extra>"
    )
    return fig


# =====================
# ✅ 기간 대비 증감 계산 (년/월/주/일)
# =====================
def calculate_period_change_auto(df: pd.DataFrame, period_type: str = "월간"):
    df = _ensure_datetime(df)
    tmp = df.copy()
    tmp["period"] = _make_period_series(tmp["date"], period_type)
    tmp["_period_sort_key"] = tmp["date"]

    # ✅ 소비만
    tmp["_spend"] = _get_spend_series(tmp)

    current_period = tmp.sort_values("_period_sort_key")["period"].iloc[-1]
    current_mask = tmp["period"] == current_period
    before_current = tmp.loc[~current_mask].sort_values("_period_sort_key")

    if before_current.empty:
        empty = pd.DataFrame(columns=["category_lv1", "current", "previous", "diff", "pct_change"])
        return empty, str(current_period), ""

    previous_period = before_current["period"].iloc[-1]

    current_df = tmp[tmp["period"] == current_period]
    prev_df = tmp[tmp["period"] == previous_period]

    current_sum = current_df.groupby("category_lv1")["_spend"].sum()
    prev_sum = prev_df.groupby("category_lv1")["_spend"].sum()

    result = pd.concat([current_sum, prev_sum], axis=1)
    result.columns = ["current", "previous"]
    result = result.fillna(0)

    result["diff"] = result["current"] - result["previous"]
    denom = result["previous"].replace(0, np.nan)
    result["pct_change"] = (result["diff"] / denom) * 100
    result["pct_change"] = result["pct_change"].fillna(0)

    # ✅ 12개 고정 순서
    result = result.reindex(CONSUMPTION_CATEGORIES_12, fill_value=0.0)

    return result.reset_index(), str(current_period), str(previous_period)


def calculate_mom_change_auto(df: pd.DataFrame):
    return calculate_period_change_auto(df, period_type="월간")


def render_mom_change_text(
    mom_df: pd.DataFrame,
    current_month: str,
    previous_month: str,
    top_n: int = 8,
    show_pct: bool = True,
):
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

# =====================
# 우측 서머리카드 차트 
# =====================
def build_monthly_cum_summary(cum_df: pd.DataFrame, year: int, month: int) -> dict:
    """
    cum_df(merged)에서 '현재 시점(=선택월 마지막 유효 지출일)' 기준 비교 요약을 계산합니다.
    기대 컬럼:
      - day
      - daily_selected, cum_selected
      - daily_prev,     cum_prev
    """
    df = cum_df.copy()

    # 선택월의 실제 지출 발생 마지막 날
    nz = df[df["daily_selected"] > 0]
    last_day = int(nz["day"].max()) if not nz.empty else 1

    cur_cum_to_day = float(df.loc[df["day"] == last_day, "cum_selected"].iloc[0])
    prev_cum_to_day = float(df.loc[df["day"] == last_day, "cum_prev"].iloc[0])

    diff_to_day = cur_cum_to_day - prev_cum_to_day
    pct_to_day = (diff_to_day / prev_cum_to_day * 100.0) if prev_cum_to_day > 0 else None

    return {
        "year": year,
        "month": month,
        "last_day": last_day,
        "cur_cum_to_day": cur_cum_to_day,
        "prev_cum_to_day": prev_cum_to_day,
        "diff_to_day": diff_to_day,
        "pct_to_day": pct_to_day,
    }


def render_monthly_cum_summary_card_html(summary: dict) -> str:
    """
    오른쪽에 붙일 '총액 카드' HTML 생성 (Streamlit 의존 없음)
    - components.html(iframe)에서 우측 border/shadow가 잘리는 문제를
      wrapper padding으로 방지합니다.
    """
    last_day = int(summary.get("last_day", 1))
    cur_cum = float(summary.get("cur_cum_to_day", 0.0))
    prev_cum = float(summary.get("prev_cum_to_day", 0.0))
    diff = float(summary.get("diff_to_day", 0.0))
    pct = summary.get("pct_to_day", None)
    year = summary.get("year")
    month = summary.get("month")

    if pct is None:
        headline = f"현재 시점({last_day}일)은 전월 데이터가 없어 비교가 어렵습니다."
        subline = ""
        badge_html = ""
    else:
        # 금액 기준 문구
        if diff > 0:
            headline = f"전월보다 {diff:,.0f}원 더 썼어요."
            badge_color = "#DC2626"   # 빨강
            badge_bg = "#FEECEC"
        elif diff < 0:
            headline = f"전월보다 {abs(diff):,.0f}원 덜 썼어요."
            badge_color = "#2563EB"   # 파랑
            badge_bg = "#E8F1FF"
        else:
            headline = "전월과 동일하게 썼어요."
            badge_color = "#6B7280"
            badge_bg = "#F3F4F6"

        subline = f"{month}월 {last_day}일 기준"

        # 퍼센트 계산
        if prev_cum > 0:
            pct_value = (diff / prev_cum) * 100

            if pct_value > 0:
                arrow = "▲"
                badge_color = "#DC2626"   # 증가 → 빨강
                badge_bg = "#FEECEC"
            elif pct_value < 0:
                arrow = "▼"
                badge_color = "#2563EB"   # 감소 → 파랑
                badge_bg = "#E8F1FF"
            else:
                arrow = "—"
                badge_color = "#6B7280"
                badge_bg = "#F3F4F6"

            badge_text = f"{arrow} {abs(pct_value):.1f}%"
        else:
            badge_text = "비교불가"
            badge_color = "#6B7280"
            badge_bg = "#F3F4F6"


        badge_html = f"""
        <span style="
            display:inline-block;
            font-size:12px;
            padding:4px 10px;
            border-radius:999px;
            background:{badge_bg};
            color:{badge_color};
            font-weight:800;
            margin-top:16px;
        ">
            {badge_text}
        </span>
        """

    html = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <style>
          * {{ box-sizing: border-box; }}
          body {{
            margin: 0;
            padding: 0;
            background: transparent;
            font-family: Pretendard, -apple-system, BlinkMacSystemFont, 'Segoe UI',
                         Roboto, 'Noto Sans KR', sans-serif;
          }}
          .wrap {{
            padding: 0 18px 0 0;  
          }}
          .card {{
            width: 100%;
            border: 1px solid #F3F4F6;
            border-radius: 16px;
            padding: 20px 20px 16px 20px;
            background: #FFFFFF;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
          }}
          .headline {{
            font-size: 20px;
            color: #454753;
            margin-top: 10px;
            font-weight: 600;
          }}
          .subline {{
            font-size: 14px;
            color: #D1D5DB;
            margin-top: 6px;
          }}
          .divider {{
            border-top: 1px solid #F3F4F6;
            padding-top: 10px;
            margin-top: 10px;
          }}
          .row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 12px;
          }}
          .label {{
            font-size: 16px;
            color: #D1D5DB; 
          }}
          .value {{
            font-size: 16px;
            font-weight: 600;
            color: #454753;
          }}
        </style>
      </head>
      <body>
        <div class="wrap">
          <div class="card">
            <div class="headline">{headline}</div>
            <div class="subline">{subline}</div>
            {badge_html}
            <div class="divider">
              <div class="row">
                <span class="label">당월 소비 금액 ({last_day}일)</span>
                <span class="value">{cur_cum:,.0f}원</span>
              </div>
              <div class="row" style="margin-bottom:0;">
                <span class="label">전월 소비 금액 ({last_day}일)</span>
                <span class="value">{prev_cum:,.0f}원</span>
              </div>
            </div>
          </div>
        </div>
      </body>
    </html>
    """
    return html

# =====================
# ✅ 최근 평균 대비 비교 (주간/일간 전용)
# =====================

def calculate_recent_average_compare(df: pd.DataFrame, period_type: str):
    if df is None or df.empty:
        return None

    df = _ensure_datetime(df).copy()
    df["_spend"] = _get_spend_series(df)  # ✅ 소비만

    if period_type == "주간":
        df["period"] = df["date"].dt.to_period("W")
        group = df.groupby("period")["_spend"].sum().sort_index()

        if len(group) < 2:
            return None

        current = float(group.iloc[-1])
        recent = group.iloc[-6:-1]  # 최근 5주
        if len(recent) == 0:
            return None

        recent_avg = float(recent.mean())
        diff = current - recent_avg

    elif period_type == "일간":
        df["period"] = df["date"].dt.to_period("D")
        group = df.groupby("period")["_spend"].sum().sort_index()

        if len(group) < 2:
            return None

        current = float(group.iloc[-1])
        recent = group.iloc[-31:-1]  # 최근 30일
        if len(recent) == 0:
            return None

        recent_avg = float(recent.mean())
        diff = current - recent_avg

    else:
        return None

    return {"current": current, "recent_avg": recent_avg, "diff": diff}


def build_period_one_line_message(data: dict, period_type: str) -> str:
    if not data:
        return ""

    diff = float(data["diff"])
    diff_text = _format_manwon_1(abs(diff))  # 0.1만원 단위
    if diff > 0:
        text = f"{diff_text} 더 썼어요."
        # color = "#DC2626"
    elif diff < 0:
        text = f"{diff_text} 덜 썼어요."
        # color = "#2563EB"
    else:
        text = "평균과 동일하게 썼어요."
        # color = "#6B7280"

    if period_type == "주간":
        headline = f"  🎈 이번 주는 최근 5주 평균보다 {text}"
    elif period_type == "일간":
        headline = f" ✨ 오늘은 최근 30일 평균보다 {text}"
    elif period_type == "월간":
        headline = f" 💰 이번 달은 지난 달 이때보다 {text}"
    else:
        headline = text

    return f"""
    <div style="
        margin-top:10px;
        font-size:20px;
        font-weight:600;
        color:#454753;
    ">
        {headline}
    </div>
    """

def calculate_month_progress_compare(df: pd.DataFrame):
    """
    이번 달(데이터 기준 '가장 최신 날짜'가 속한 달) 누적(1일~그 날짜) vs
    지난 달 동일 일자 누적 비교
    """
    if df is None or df.empty:
        return None

    tmp = _ensure_datetime(df).copy()
    tmp["_spend"] = pd.to_numeric(tmp["amount"], errors="coerce").fillna(0).abs()

    latest_date = pd.to_datetime(tmp["date"].max())
    y, m, d = int(latest_date.year), int(latest_date.month), int(latest_date.day)

    # 이번 달 1일~d일 누적
    cur_start = pd.Timestamp(year=y, month=m, day=1)
    cur_end = pd.Timestamp(year=y, month=m, day=d, hour=23, minute=59, second=59)

    cur_sum = float(tmp[(tmp["date"] >= cur_start) & (tmp["date"] <= cur_end)]["_spend"].sum())

    # 지난 달 동일 '일자'까지 누적 (지난 달이 더 짧으면 말일로 보정)
    cur_period = pd.Period(f"{y:04d}-{m:02d}", freq="M")
    prev_period = cur_period - 1
    prev_y, prev_m = int(prev_period.year), int(prev_period.month)

    import calendar
    prev_last_day = calendar.monthrange(prev_y, prev_m)[1]
    prev_day = min(d, prev_last_day)

    prev_start = pd.Timestamp(year=prev_y, month=prev_m, day=1)
    prev_end = pd.Timestamp(year=prev_y, month=prev_m, day=prev_day, hour=23, minute=59, second=59)

    prev_sum = float(tmp[(tmp["date"] >= prev_start) & (tmp["date"] <= prev_end)]["_spend"].sum())

    diff = cur_sum - prev_sum

    return {
        "current": cur_sum,
        "previous": prev_sum,
        "diff": diff,
        "asof_day": d,              # 이번 달 기준 '이때' = d일
        "cur_ym": f"{y:04d}-{m:02d}",
        "prev_ym": f"{prev_y:04d}-{prev_m:02d}",
        "prev_day": prev_day,
    }
    
# ------------------------------------------------------------------
# ① 내부 헬퍼: addon_year/month None 보정
# ------------------------------------------------------------------
def _resolve_year_month(
    df: pd.DataFrame,
    addon_year: "int | None",
    addon_month: "int | None",
    filter_end=None,
) -> "tuple[int, int]":
    """
    addon_year / addon_month 가 None 이면
    filter_end 또는 df 최신 날짜 기준으로 자동 결정합니다.
    """
    if addon_year is None or addon_month is None:
        if filter_end is not None:
            end_dt = pd.to_datetime(filter_end)
        else:
            dfx = df.copy()
            if not pd.api.types.is_datetime64_any_dtype(dfx["date"]):
                dfx["date"] = pd.to_datetime(dfx["date"], errors="coerce")
            end_dt = dfx["date"].max() if dfx["date"].notna().any() else pd.Timestamp.today()
        return int(end_dt.year), int(end_dt.month)
    return int(addon_year), int(addon_month)


# ------------------------------------------------------------------
# ② 요일별 평균 지출 비교 — Radar(극좌표) Chart
# ------------------------------------------------------------------
def draw_weekday_compare(
    df: pd.DataFrame,
    addon_year: "int | None",
    addon_month: "int | None",
    filter_end=None,
) -> go.Figure:
    """
    현재 선택월 vs 전월 — 요일별 평균 지출 비교 (레이더 차트)

    · 각 꼭짓점 = 요일(월~일)
    · 값 = "해당 요일 날짜들의 1일 평균 지출"
    · 선택월(핑크) + 전월(회색) 두 레이어로 비교
    · hover : 요일 + 평균 금액
    """
    # --- 상수 ---
    WEEKDAY_ORDER = ["월", "화", "수", "목", "금", "토", "일"]
    EN_TO_KO = {
        "Monday": "월", "Tuesday": "화", "Wednesday": "수",
        "Thursday": "목", "Friday": "금", "Saturday": "토", "Sunday": "일",
    }

    # --- 연/월 결정 ---
    year, month = _resolve_year_month(df, addon_year, addon_month, filter_end)
    cur_period = pd.Period(f"{year:04d}-{month:02d}", freq="M")
    prev_period = cur_period - 1

    # --- 전처리 ---
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["ym"]      = df["date"].dt.to_period("M")
    df["weekday"] = df["date"].dt.day_name().map(EN_TO_KO)
    df["day_key"] = df["date"].dt.date          # 날짜별 일합 키
    df["spend"] = _get_spend_series(df)

    def _weekday_avg(period: pd.Period) -> pd.Series:
        """요일별 평균 지출(일합 → 요일 평균)"""
        sub = df[df["ym"] == period]
        if sub.empty:
            return pd.Series(0.0, index=WEEKDAY_ORDER)
        # ① 날짜별 합산
        daily = (
            sub.groupby("day_key")["spend"].sum()
            .reset_index()
        )
        daily.columns = ["day_key", "spend"]
        daily["weekday"] = pd.to_datetime(daily["day_key"]).dt.day_name().map(EN_TO_KO)
        # ② 요일별 평균
        return (
            daily.groupby("weekday")["spend"]
            .mean()
            .reindex(WEEKDAY_ORDER)
            .fillna(0)
        )

    cur_avg  = _weekday_avg(cur_period)
    prev_avg = _weekday_avg(prev_period)

    # 레이더는 첫 점을 마지막에 반복해야 닫힘
    theta    = WEEKDAY_ORDER + [WEEKDAY_ORDER[0]]
    cur_r    = cur_avg.tolist()  + [cur_avg.iloc[0]]
    prev_r   = prev_avg.tolist() + [prev_avg.iloc[0]]

    # --- Figure ---
    fig = go.Figure()

    # 전월 레이어 (회색, 얇은 점선)
    fig.add_trace(go.Scatterpolar(
        r=prev_r,
        theta=theta,
        fill="toself",
        name=f"전월 ({prev_period.year}.{prev_period.month:02d})",
        line=dict(color="#9CA3AF", width=2, dash="dot"),
        fillcolor="rgba(156,163,175,0.12)",
        hovertemplate="<b>%{theta}</b><br>전월 평균 %{r:,.0f}원<extra></extra>",
    ))

    # 선택월 레이어 (PRIMARY_COLOR, 굵은 선)
    fig.add_trace(go.Scatterpolar(
        r=cur_r,
        theta=theta,
        fill="toself",
        name=f"선택월 ({cur_period.year}.{cur_period.month:02d})",
        line=dict(color="#F00176", width=3),
        fillcolor="rgba(240,1,118,0.10)",
        hovertemplate="<b>%{theta}</b><br>선택월 평균 %{r:,.0f}원<extra></extra>",
    ))

    # 최고 지출 요일 강조 포인트
    peak_idx = int(cur_avg.values.argmax())
    peak_val = float(cur_avg.iloc[peak_idx])
    if peak_val > 0:
        fig.add_trace(go.Scatterpolar(
            r=[peak_val],
            theta=[WEEKDAY_ORDER[peak_idx]],
            mode="markers+text",
            marker=dict(size=14, color="#F00176", symbol="star",
                        line=dict(width=2, color="#fff")),
            text=[f"{peak_val:,.0f}원"],
            textposition="top center",
            textfont=dict(size=10, color="#F00176"),
            showlegend=False,
            hoverinfo="skip",
        ))

    fig.update_layout(
        height=400,
        margin=dict(l=70, r=70, t=110, b=70),
        polar=dict(
            domain=dict(x=[0.05, 0.95], y=[0.0, 0.95]),
            radialaxis=dict(
                visible=True,
                tickformat=",d",
                tickfont=dict(size=9, color="#9CA3AF"),
                gridcolor="#F3F4F6",
                linecolor="#E5E7EB",
                showline=False,
            ),
            angularaxis=dict(
                tickfont=dict(size=15, family="Pretendard, sans-serif", color="#26282B"),
                linecolor="#E5E7EB",
                gridcolor="#F3F4F6",
            ),
            bgcolor="rgba(247,248,249,0.6)",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.06,
            xanchor="center", x=0.5,
            font=dict(size=12),
        ),
        title=dict(
            text=f"<b>요일별 평균 지출</b>",
            font=dict(size=20, color="#D1D5DB"),
            x=0,
            y=0.97,
            xanchor="left",
            pad=dict(b=6),
        ),
        paper_bgcolor="white",
    )

    return fig


# ------------------------------------------------------------------
# ③ 시간대별 평균 지출 비교 — Area Chart + 시간대 구간 강조
# ------------------------------------------------------------------
def draw_hour_compare(
    df: pd.DataFrame,
    addon_year: "int | None",
    addon_month: "int | None",
    filter_end=None,
) -> go.Figure:
    """
    현재 선택월 vs 전월 — 시간대별(0~23시) 평균 지출 비교

    · x축 : 0~23시
    · y축 : "해당 시간의 거래 건별 평균 지출"  ← 일평균이 아닌 '거래 건 평균'
    · 배경 : 새벽/오전/오후/저녁/밤 구간 색상 분리
    · 피크 시간 : ⭐ 마커 + 금액 라벨
    · hover   : x=시간대, 선택월/전월 동시 표기 (unified)
    """
    ALL_HOURS = list(range(24))
    HOUR_LABELS = [f"{h:02d}시" for h in ALL_HOURS]

    TIME_ZONES = [
        (0,  4,  "새벽", "rgba(99,102,241,0.04)"),
        (5, 10,  "오전", "rgba(251,191,36,0.05)"),
        (11, 13, "점심", "rgba(16,185,129,0.05)"),
        (14, 17, "오후", "rgba(59,130,246,0.04)"),
        (18, 21, "저녁", "rgba(249,115,22,0.06)"),
        (22, 23, "밤",   "rgba(99,102,241,0.04)"),
    ]

    # --- 연/월 결정 ---
    year, month = _resolve_year_month(df, addon_year, addon_month, filter_end)
    cur_period  = pd.Period(f"{year:04d}-{month:02d}", freq="M")
    prev_period = cur_period - 1

    # --- 전처리 ---
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["ym"]    = df["date"].dt.to_period("M")
    df["hour"]  = df.get("hour", df["date"].dt.hour)
    df["spend"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0).abs()

    def _hour_avg(period: pd.Period) -> np.ndarray:
        """시간별 '날짜 × 시간 조합' 기준 평균 지출"""
        sub = df[df["ym"] == period]
        if sub.empty:
            return np.zeros(24)
        # 날짜+시간 조합별 합산 → 시간별 평균
        dh = sub.groupby([sub["date"].dt.date, "hour"])["spend"].sum()
        avg = dh.groupby("hour").mean().reindex(ALL_HOURS).fillna(0)
        return avg.values

    cur_vals  = _hour_avg(cur_period)
    prev_vals = _hour_avg(prev_period)

    # --- Figure ---
    fig = go.Figure()

    # ① 시간대 배경 vrect
    for s, e, label, color in TIME_ZONES:
        fig.add_vrect(
            x0=s - 0.5, x1=e + 0.5,
            fillcolor=color, opacity=1,
            layer="below", line_width=0,
            annotation_text=label,
            annotation_position="top left",
            annotation_font=dict(size=10, color="#9CA3AF"),
            annotation_bgcolor="rgba(255,255,255,0)",
        )

    # ② 전월 에어리어 (회색 점선 + 연한 fill)
    fig.add_trace(go.Scatter(
        x=ALL_HOURS,
        y=prev_vals,
        name=f"전월 ({prev_period.year}.{prev_period.month:02d})",
        mode="lines",
        line=dict(color="#9CA3AF", width=2, dash="dot"),
        fill="tozeroy",
        fillcolor="rgba(156,163,175,0.08)",
        hovertemplate="%{x}시&nbsp;&nbsp;전월 %{y:,.0f}원<extra></extra>",
    ))

    # ③ 선택월 에어리어 (핑크 실선 + 선명한 fill)
    fig.add_trace(go.Scatter(
        x=ALL_HOURS,
        y=cur_vals,
        name=f"선택월 ({cur_period.year}.{cur_period.month:02d})",
        mode="lines+markers",
        line=dict(color="#F00176", width=3),
        fill="tozeroy",
        fillcolor="rgba(240,1,118,0.07)",
        marker=dict(size=4, color="#F00176", opacity=0.6),
        hovertemplate="%{x}시&nbsp;&nbsp;선택월 %{y:,.0f}원<extra></extra>",
    ))

    # ④ 피크 시간 강조 ⭐
    peak_h = int(np.argmax(cur_vals))
    peak_v = float(cur_vals[peak_h])
    if peak_v > 0:
        fig.add_trace(go.Scatter(
            x=[peak_h],
            y=[peak_v],
            mode="markers+text",
            marker=dict(
                size=18, color="#F00176", symbol="star",
                line=dict(width=2, color="#fff"),
            ),
            text=[f"  {peak_v:,.0f}원"],
            textposition="middle right",
            textfont=dict(size=11, color="#F00176", family="Pretendard, sans-serif"),
            showlegend=False,
            hoverinfo="skip",
        ))

    # ⑤ 전월 대비 증감 차이 영역 (diff shading)
    diff = cur_vals - prev_vals
    fig.add_trace(go.Scatter(
        x=ALL_HOURS,
        y=np.where(diff > 0, cur_vals, prev_vals),   # 위 경계
        line=dict(width=0),
        showlegend=False,
        hoverinfo="skip",
        fillcolor="rgba(240,1,118,0.0)",
    ))

    # --- 레이아웃 ---
    fig.update_layout(
        height=560,
        margin=dict(l=10, r=10, t=160, b=10),
        hovermode="x unified",
        plot_bgcolor="white",
        paper_bgcolor="white",
        title=dict(
            text="<b>시간대별 평균 지출</b>",
            font=dict(size=20, color="#D1D5DB"),
            x=0,
            y=0.97,
            xanchor="left",
            pad=dict(b=6),
        ),
        xaxis=dict(
            title="시간대",
            tickmode="array",
            tickvals=list(range(0, 24, 2)),
            ticktext=[f"{h:02d}시" for h in range(0, 24, 2)],
            showgrid=True,
            gridcolor="#F7F8F9",
            gridwidth=1,
            zeroline=False,
            range=[-0.5, 23.5],
        ),
        yaxis=dict(
            title="평균 지출(원)",
            tickformat=",d",
            showgrid=True,
            gridcolor="#F7F8F9",
            gridwidth=1,
            zeroline=False,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.04,
            xanchor="left", x=0,
            font=dict(size=12),
        ),
    )

    return fig


# 시간대 구간 정의 (draw_hour_compare 와 동일하게 맞춤)
_TIME_ZONE_LABELS = [
    (0,  4,  "새벽"),
    (5,  10, "오전"),
    (11, 13, "점심"),
    (14, 17, "오후"),
    (18, 21, "저녁"),
    (22, 23, "밤"),
]

def _hour_to_zone(hour: int) -> str:
    """0~23시 → 새벽/오전/점심/오후/저녁/밤"""
    for start, end, label in _TIME_ZONE_LABELS:
        if start <= hour <= end:
            return label
    return f"{hour:02d}시"


def build_peak_pattern(
    df: pd.DataFrame,
    year: "int | None",
    month: "int | None",
) -> dict:
    """
    선택월 기준 피크 요일·시간대·카테고리 계산
    df 는 addon 필터 전 df_filtered 를 넘겨야 전체 데이터 참조 가능
    """
    WEEKDAY_KO = {
        "Monday": "월", "Tuesday": "화", "Wednesday": "수",
        "Thursday": "목", "Friday": "금", "Saturday": "토", "Sunday": "일",
    }
    empty = dict(peak_weekday=None, peak_hour=None, peak_zone=None,
                 peak_category=None, peak_amount=None, year=year, month=month)

    if df is None or df.empty:
        return empty

    df2 = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df2["date"]):
        df2["date"] = pd.to_datetime(df2["date"], errors="coerce")

    if year is None or month is None:
        latest = df2["date"].max()
        if pd.isna(latest):
            return empty
        year, month = int(latest.year), int(latest.month)

    df2 = df2[
        (df2["date"].dt.year == int(year)) &
        (df2["date"].dt.month == int(month))
    ].copy()

    if df2.empty:
        return empty

    df2["spend"]   = pd.to_numeric(df2["amount"], errors="coerce").fillna(0).abs()
    df2["weekday"] = df2["date"].dt.day_name().map(WEEKDAY_KO)
    df2["hour"]    = df2["hour"] if "hour" in df2.columns else df2["date"].dt.hour

    # ① 피크 요일
    wd_sum = df2.groupby("weekday")["spend"].sum()
    peak_weekday = wd_sum.idxmax() if not wd_sum.empty else None

    # ② 피크 시간대 (구간별 합산 → 구간명)
    df2["zone"] = df2["hour"].apply(_hour_to_zone)
    zone_sum = df2.groupby("zone")["spend"].sum()
    peak_zone = zone_sum.idxmax() if not zone_sum.empty else None

    # 피크 시간(raw) — 레이더/에어리어 차트용으로도 유지
    hr_sum = df2.groupby("hour")["spend"].sum()
    peak_hour = int(hr_sum.idxmax()) if not hr_sum.empty else None

    # ③ 피크 요일 × 피크 구간 교차 → 최다 카테고리
    peak_category = None
    peak_amount   = None
    if peak_weekday and peak_zone and "category_lv1" in df2.columns:
        cross = df2[(df2["weekday"] == peak_weekday) & (df2["zone"] == peak_zone)]
        src   = cross if not cross.empty else df2[df2["weekday"] == peak_weekday]
        if not src.empty:
            cat_sum       = src.groupby("category_lv1")["spend"].sum()
            peak_category = cat_sum.idxmax()
            peak_amount   = float(cat_sum.max())

    return dict(
        peak_weekday=peak_weekday,
        peak_hour=peak_hour,
        peak_zone=peak_zone,          # "새벽" | "오전" | "점심" | "오후" | "저녁" | "밤"
        peak_category=peak_category,
        peak_amount=peak_amount,
        year=year,
        month=month,
    )


def render_peak_pattern_card_html(peak_info: dict) -> str:
    """
    피크 소비 패턴 전용 카드 HTML
    기존 summary 카드 아래 components.html() 로 별도 렌더링
    """
    wd    = peak_info.get("peak_weekday")
    zone  = peak_info.get("peak_zone")          # "저녁" 등 구간명
    cat   = peak_info.get("peak_category")
    amt   = peak_info.get("peak_amount")
    month = peak_info.get("month", "")

    if not wd or not zone:
        return ""

    amt_str = f"{amt:,.0f}원" if amt else ""

    cat_block = ""
    if cat:
        cat_block = f"""
        <div class="divider"></div>
        <div style="
            display:flex;
            justify-content:space-between;
            align-items:center;
            margin-top:12px;
            padding:10px 14px;
            background:#F7F8F9;
            border-radius:10px;
        ">
            <div>
                <div style="font-size:11px;color:#9CA3AF;margin-bottom:3px;font-weight:600;">
                    최다 소비 카테고리
                </div>
                <div style="font-size:16px;font-weight:700;color:#26282B;">{cat}</div>
            </div>
            <div style="font-size:16px;font-weight:800;color:#454753;">{amt_str}</div>
        </div>
        """

    return f"""
    <html>
      <head>
        <meta charset="utf-8"/>
        <style>
          * {{ box-sizing:border-box; }}
          body {{
            margin:0; padding:0; background:transparent;
            font-family: Pretendard, -apple-system, BlinkMacSystemFont,
                         'Segoe UI', Roboto, 'Noto Sans KR', sans-serif;
          }}
          .wrap {{ padding:0 18px 12px 0; }}
          .card {{
            width:100%;
            border:1px solid #F3F4F6;
            border-radius:16px;
            padding:18px 20px 18px 20px;
            background:#FFFFFF;
            box-shadow:0 2px 8px rgba(0,0,0,0.04);
          }}
          .tag {{
            display:inline-block;
            font-size:11px;
            font-weight:700;
            letter-spacing:0.5px;
            color:#F00176;
            background:#FFF0F6;
            border-radius:999px;
            padding:3px 10px;
            margin-bottom:12px;
          }}
          .main {{
            font-size:18px;
            font-weight:600;
            color:#454753;
            line-height:1.65;
          }}
          .main b {{ color:#F00176; }}
          .divider {{
            border-top:1px solid #F3F4F6;
            margin-top:14px;
          }}
        </style>
      </head>
      <body>
        <div class="wrap">
          <div class="card">
            <div class="tag">{month}월 소비 패턴</div>
            <div class="main">
              주로 <b>{wd}요일 {zone}</b>에<br>가장 많은 소비를 해요.
            </div>
            {cat_block}
          </div>
        </div>
      </body>
    </html>
    """