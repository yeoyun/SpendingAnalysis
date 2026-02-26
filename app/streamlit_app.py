# app/streamlit_app.py

import streamlit as st
import sys
import os
import pandas as pd

# =====================
# 경로 설정
# =====================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from charts import (
    draw_period_trend,
    calculate_period_change_auto,
    draw_category_pie,
    draw_category_bar,
    draw_weekday_hour_heatmap,
    render_mom_change_text,
)

from persona import (
    infer_persona_from_ai_summary,
    render_persona_top_card,
)

from ai_report.ui import (
    render_ai_report_detail,
    render_ai_report_summary,
)

from app.sidebar import build_sidebar

# ✅ 여기만 변경: 필터/헤더를 ui_utils에서 가져오기
from app.ui_utils import render_period_filter, render_period_header


# =====================
# 페이지 설정
# =====================
st.set_page_config(
    page_title="개인 소비 패턴 대시보드",
    layout="wide"
)


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
    if not pd.api.types.is_datetime64_any_dtype(df_filtered["date"]):
        df_filtered["date"] = pd.to_datetime(df_filtered["date"])

    # 날짜 필터
    df_filtered = df_filtered[
        (df_filtered["date"] >= pd.to_datetime(start_date)) &
        (df_filtered["date"] <= pd.to_datetime(end_date))
    ]

    # 카테고리 필터
    if selected_categories:
        df_filtered = df_filtered[df_filtered["category_lv1"].isin(selected_categories)]

    return df_filtered


# =====================
# ✅ 사이드바 (업로드/기본 기간/카테고리)
# =====================
page, df, df_expense, start_date, end_date, selected_categories = build_sidebar()


# =====================
# ✅ 페르소나 카드 (AI 생성 후에만)
# =====================
persona_result = None
ai_summary = st.session_state.get("ai_report_summary")
if isinstance(ai_summary, dict) and ai_summary:
    persona_result = infer_persona_from_ai_summary(ai_summary)


# =====================
# ✅ 페이지 분기 렌더
# =====================
if page == "🏠 홈":
    st.title("📊 개인 소비 패턴 대시보드")

    # -----------------------------
    # 1️⃣ 상단 카드
    # -----------------------------
    render_period_header(start_date, end_date)
    render_persona_top_card(persona_result)
    render_ai_report_summary(show_header=False)

    # -----------------------------
    # 2️⃣ 분석 필터
    # -----------------------------
    period_type, filter_start, filter_end = render_period_filter(
        pd.to_datetime(start_date),
        pd.to_datetime(end_date),
    )
    
    # -----------------------------
    # 3️⃣ df 필터 생성
    # -----------------------------
    df_filtered = apply_common_filters(
        df_expense=df_expense,
        start_date=filter_start,
        end_date=filter_end,
        selected_categories=selected_categories,
    )

    # =====================
    # 📈 기간별 지출 추이
    # =====================
    st.subheader(f"📈 {period_type} 지출 추이")

    col1, col2 = st.columns([2, 1], vertical_alignment="top")

    with col1:
        if df_filtered.empty:
            st.info("선택된 조건에 해당하는 지출 데이터가 없습니다.")
        else:
            st.plotly_chart(
                draw_period_trend(df_filtered, period_type=period_type),
                use_container_width=True
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
    # 🧩 카테고리별 지출
    # =====================
    st.subheader("🧩 카테고리별 지출")

    if selected_categories:
        tag_text = " ".join([f"#{c}" for c in selected_categories])
        st.markdown(
            f"<div style='color:#D1D5DB; margin-bottom:12px;'>{tag_text}</div>",
            unsafe_allow_html=True
        )

    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        if df_filtered.empty:
            st.info("선택된 조건에 해당하는 지출 데이터가 없습니다.")
        else:
            st.plotly_chart(draw_category_pie(df_filtered), use_container_width=True)

    with col_right:
        if df_filtered.empty:
            st.info("선택된 조건에 해당하는 지출 데이터가 없습니다.")
        else:
            st.plotly_chart(draw_category_bar(df_filtered), use_container_width=True)

    st.divider()

    # =====================
    # 🔥 요일 · 시간대별 지출 패턴
    # =====================
    st.subheader("🔥 요일 · 시간대별 지출 패턴")

    if df_filtered.empty:
        st.info("선택된 조건에 해당하는 지출 데이터가 없습니다.")
    else:
        if "hour" not in df_filtered.columns:
            df_filtered = df_filtered.copy()
            df_filtered["hour"] = df_filtered["date"].dt.hour

        if df_filtered["hour"].notna().any():
            st.plotly_chart(draw_weekday_hour_heatmap(df_filtered), use_container_width=True)
        else:
            st.info("⏰ 시간 정보가 없어 요일/시간대 분석은 표시되지 않습니다.")


else:
    st.title("🦕 AI 소비 리포트")
    render_period_header(pd.to_datetime(start_date), pd.to_datetime(end_date))

    render_persona_top_card(persona_result)
    render_ai_report_detail(compact=False)