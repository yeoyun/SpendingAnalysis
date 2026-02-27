# app/streamlit_app.py

import streamlit as st
import sys
import os
import pandas as pd
import calendar
import streamlit.components.v1 as components

# =====================
# 경로 설정 (가장 먼저)
# =====================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# =====================
# 페이지 설정
# =====================
st.set_page_config(
    page_title="개인 소비 패턴 대시보드",
    layout="wide"
)

from ai_report.utils import restore_latest_to_session_both
from ai_report.ui import (
    init_ai_report_state,
    render_ai_report_detail_all,
    render_short_report,
    render_short_report_mini,
)

from persona.card import get_persona_result_from_ai_all_session

from charts import (
    build_monthly_cum_summary,
    build_peak_pattern,
    build_period_one_line_message,
    calculate_month_progress_compare,
    calculate_recent_average_compare,
    draw_hour_compare,
    draw_monthly_daily_cumulative_compare,
    draw_period_trend,
    calculate_period_change_auto,
    draw_category_pie,
    draw_category_bar,
    draw_weekday_compare,
    draw_weekday_hour_heatmap,
    render_kpi_cards,
    render_mom_change_text,
    render_monthly_cum_summary_card_html,
    render_peak_pattern_card_html,
)

from persona import (
    infer_persona_from_ai_summary,
    render_persona_top_card,
)

from app.sidebar import build_sidebar
from app.ui_utils import render_month_addon_filter_only, render_period_filter, render_period_header

from expense_preprocess.data_manager import render_data_manage_page
from expense_preprocess.data_manager.state import init_data_manager_state, get_active_df


# =====================
# ✅ 세션 복구 + 상태 키 초기화
# =====================
restore_latest_to_session_both(st, force=False)
init_ai_report_state()

# ✅ 디스크 저장된 활성 데이터/메타 자동 복구
init_data_manager_state()

# =====================
# ✅ 사이드바 (페이지/기본 기간/카테고리)
# =====================
page, start_date, end_date, selected_categories = build_sidebar()

if page == "🧼 데이터 관리":
    render_data_manage_page()
    st.stop()

df_all = get_active_df()
if df_all is None or df_all.empty:
    st.info("먼저 ‘🧼 데이터 관리’에서 데이터를 업로드 후 활성화해주세요.")
    st.stop()

df_expense = df_all[df_all["is_expense"]].copy()

# =====================
# 공통: 필터 적용 함수
# =====================
def apply_common_filters(
    df_expense: pd.DataFrame,
    start_date,
    end_date,
    selected_categories,
) -> pd.DataFrame:
    df_filtered = df_expense.copy()

    # date 타입 보장
    if "date" not in df_filtered.columns:
        raise KeyError("df_expense must have 'date' column")

    df_filtered["date"] = pd.to_datetime(df_filtered["date"], errors="coerce")
    df_filtered = df_filtered[df_filtered["date"].notna()].copy()

    # ✅ 날짜(date) 단위로만 비교 
    start_d = pd.to_datetime(start_date).date()
    end_d = pd.to_datetime(end_date).date()

    d_only = df_filtered["date"].dt.date
    df_filtered = df_filtered[(d_only >= start_d) & (d_only <= end_d)]

    # 카테고리 필터
    if selected_categories:
        df_filtered = df_filtered[df_filtered["category_lv1"].isin(selected_categories)]

    return df_filtered


def _apply_year_month_addon_filter(df: pd.DataFrame, year: int | None, month: int | None) -> pd.DataFrame:
    """
    ✅ 추가 필터(년/월):
    - year가 None이면 적용 안 함
    - month가 None이면 '해당 연도 전체'
    - month가 있으면 '해당 연-월'만
    """
    if df.empty:
        return df

    if year is None:
        return df

    df2 = df.copy()

    if not pd.api.types.is_datetime64_any_dtype(df2["date"]):
        df2["date"] = pd.to_datetime(df2["date"], errors="coerce")

    if month is None:
        start = pd.Timestamp(year=year, month=1, day=1)
        end = pd.Timestamp(year=year, month=12, day=31)
    else:
        last_day = calendar.monthrange(year, month)[1]
        start = pd.Timestamp(year=year, month=month, day=1)
        end = pd.Timestamp(year=year, month=month, day=last_day)

    return df2[(df2["date"] >= start) & (df2["date"] <= end)]


# =====================
# ✅ 페이지 분기 렌더
# =====================
if page == "🏠 홈":
    st.title("📊 개인 소비 패턴 대시보드")
    
    # -----------------------------
    # 분석 필터: 기존 기간(date range) 유지 (전체 그래프 기준)
    # -----------------------------
    period_type, filter_start, filter_end = render_period_filter(
        pd.to_datetime(start_date),
        pd.to_datetime(end_date),
    )
    st.markdown("<br>", unsafe_allow_html=True)
    
    # -----------------------------
    #  전체기간 기준 df (기존처럼)
    # -----------------------------
    df_filtered = apply_common_filters(
        df_expense=df_expense,
        start_date=filter_start,
        end_date=filter_end,
        selected_categories=selected_categories,
    )
    
    render_kpi_cards(st, df_filtered, period_type=period_type)
    
    st.markdown("<br>", unsafe_allow_html=True)    
    
    # =====================
    # 📈 기간별 지출 추이 (전체 기간)
    # =====================
    st.subheader(f"📈 {period_type} 지출 추이")

    col1, col2 = st.columns([2, 1], vertical_alignment="top")

    with col1:
        if df_filtered.empty:
            st.info("선택된 조건에 해당하는 지출 데이터가 없습니다.")
        else:
            st.plotly_chart(
                draw_period_trend(df_filtered, period_type=period_type),
                width="stretch"
            )
            if period_type in ["주간", "일간"]:
                compare_data = calculate_recent_average_compare(
                    df_filtered,
                    period_type=period_type
                )
                if compare_data:
                    st.markdown(
                        build_period_one_line_message(compare_data, period_type),
                        unsafe_allow_html=True
                    )

            elif period_type == "월간":
                mdata = calculate_month_progress_compare(df_filtered)
                if mdata:
                    st.markdown(
                        build_period_one_line_message(mdata, period_type),
                        unsafe_allow_html=True
                    )

    with col2:
        if df_filtered.empty:
            st.info("선택된 기간에 지출 데이터가 없습니다.")
        else:
            change_df, current_p, previous_p = calculate_period_change_auto(
                df_filtered,
                period_type=period_type
            )

            if previous_p == "" or change_df.empty or change_df["previous"].sum() == 0:
                st.info("이전 기간 데이터가 없어 비교할 수 없습니다.")
            else:
                html = render_mom_change_text(
                    change_df,
                    current_month=current_p,
                    previous_month=previous_p,
                    top_n=8,
                    show_pct=True
                )
                st.markdown(html, unsafe_allow_html=True)

    st.divider()

    # =====================
    # 월간 분석 전용 필터
    # =====================
    
    addon_year, addon_month = render_month_addon_filter_only(
        df_filtered,
        key_prefix="addon",
        allow_all=False,
        all_label=f"{pd.to_datetime(filter_start):%Y/%m/%d} ~ {pd.to_datetime(filter_end):%Y/%m/%d}",
        filter_end=filter_end,
    )
    df_bottom = _apply_year_month_addon_filter(df_filtered, addon_year, addon_month)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # =====================
    # 월간 누적 그래프
    # =====================

    # st.subheader("📈 월간 지출 데일리 누적 (전월 비교)")

    fig_cum, cum_df = draw_monthly_daily_cumulative_compare(
        df_filtered=df_filtered,
        addon_year=addon_year,
        addon_month=addon_month,
        filter_end=filter_end,
        day_max=31,
    )

    summary = build_monthly_cum_summary(
        cum_df,
        year=addon_year,
        month=addon_month,
    )
    card_html = render_monthly_cum_summary_card_html(summary)

    left, right = st.columns([1.2, 0.8], gap="medium")

    with left:
        st.plotly_chart(fig_cum, width="stretch")

    with right:
        # ✅ st.markdown 대신 components.html로 렌더링 (CSS 노출 방지)
        components.html(card_html, height=240)
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # =====================
    # 🧩 카테고리별 지출 (✅ df_bottom 적용)
    # =====================
    st.subheader("🧩 카테고리별 지출")

    if selected_categories:
        tag_text = " ".join([f"#{c}" for c in selected_categories])
        st.markdown(
            f"<div style='color:#D1D5DB; margin-bottom:12px;'>{tag_text}</div>",
            unsafe_allow_html=True
        )

    if addon_year is not None:
        if addon_month is None:
            st.caption(f"추가필터 적용: {addon_year}년")
        else:
            st.caption(f"추가필터 적용: {addon_year}년 {addon_month:02d}월")

    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        if df_bottom.empty:
            st.info("추가 필터 조건에 해당하는 지출 데이터가 없습니다.")
        else:
            st.plotly_chart(draw_category_pie(df_bottom), width="stretch")

    with col_right:
        if df_bottom.empty:
            st.info("추가 필터 조건에 해당하는 지출 데이터가 없습니다.")
        else:
            st.plotly_chart(draw_category_bar(df_bottom), width="stretch")

    st.markdown("<br>", unsafe_allow_html=True)

    # =====================
    # 🔥 요일 · 시간대별 지출 패턴 (전월 비교)
    # =====================
    st.subheader("🔥 요일 · 시간대별 지출")
    st.markdown("<br>", unsafe_allow_html=True)
    
    if df_bottom.empty:
        st.info("추가 필터 조건에 해당하는 지출 데이터가 없습니다.")
    else:
        if "hour" not in df_bottom.columns:
            df_bottom = df_bottom.copy()
            df_bottom["hour"] = df_bottom["date"].dt.hour

        has_hour_data = df_bottom["hour"].notna().any()

        col_radar, col_area = st.columns([0.8, 1.2], gap="medium")

        with col_radar:
            st.plotly_chart(
                draw_weekday_compare(
                    df_filtered,        # ✅ df_bottom → df_filtered (전월 포함)
                    addon_year=addon_year,
                    addon_month=addon_month,
                    filter_end=filter_end,
                ),
                width="stretch",
            )
            # ✅ 피크 패턴 카드 (별도, 바로 아래)
            peak_info = build_peak_pattern(
                df_filtered,          # addon 필터 전 전체 데이터
                year=addon_year,
                month=addon_month,
            )
            peak_card_html = render_peak_pattern_card_html(peak_info)
            if peak_card_html:
                components.html(peak_card_html, height=240)

        with col_area:
            if has_hour_data:
                st.plotly_chart(
                    draw_hour_compare(
                        df_filtered,    # ✅ df_bottom → df_filtered (전월 포함)
                        addon_year=addon_year,
                        addon_month=addon_month,
                        filter_end=filter_end,
                    ),
                    width="stretch",
                    height="content"
                )
            else:
                st.info("시간 정보가 없어 시간대 분석은 표시되지 않습니다.")
    st.stop()
    
                
elif page == "🧼 데이터 관리":
    from expense_preprocess.data_manager.page import render_data_manage_page
    render_data_manage_page()
    st.stop()
    
elif page == "🧠 AI 리포트":
    st.title("🦕 AI 소비 리포트")
    render_period_header(pd.to_datetime(start_date), pd.to_datetime(end_date))

    # ✅ 페르소나 카드는 전체(all) 결과만 사용
    persona_result = get_persona_result_from_ai_all_session()
    render_persona_top_card(persona_result)

    # ✅ 전체 리포트(ALL)
    render_ai_report_detail_all(compact=True)

    st.subheader("🗓️ 단기 리포트")
    render_short_report(
        result=st.session_state["ai_report_result_short"],
        summary=st.session_state["ai_report_summary_short"],
    )