# app/streamlit_app.py
import streamlit as st
import sys
import os
import pandas as pd

# =====================
# 경로 설정 (Anaconda 대응)
# =====================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from expense_preprocess.preprocess import run_preprocess
from charts import (
    draw_monthly_trend,
    draw_category_pie,
    draw_category_bar,
    draw_weekday_hour_heatmap
)

# =====================
# 페이지 설정
# =====================
st.set_page_config(
    page_title="개인 소비 패턴 대시보드",
    layout="wide"
)

# =====================
# 파일 업로드
# =====================
st.sidebar.header("📂 데이터 업로드")

uploaded_file = st.sidebar.file_uploader(
    "CSV / Excel 파일 업로드",
    type=["csv", "xlsx"]
)

if uploaded_file:
    try:
        st.session_state["df"] = run_preprocess(uploaded_file)
    except Exception as e:
        st.error(f"전처리 실패: {e}")
        st.stop()

df = st.session_state.get("df")
if df is None:
    st.info("좌측 메뉴에서 CSV 파일을 업로드해주세요.")
    st.stop()

# =====================
# 필터
# =====================
st.sidebar.header("🔎 필터")

min_date = df["date"].min()
max_date = df["date"].max()

# ▶ 최초 1회만 기본값 세팅
if "date_range" not in st.session_state:
    st.session_state.date_range = (min_date, max_date)

# ▶ date_input (반드시 key 사용)
date_range = st.sidebar.date_input(
    "📆 분석 기간 선택",
    value=st.session_state.date_range,
    min_value=min_date,
    max_value=max_date,
    key="date_picker"
)

# ▶ 단일 선택 방어
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

# ▶ 기간 역전 방어
if start_date > end_date:
    st.warning("⚠ 시작일이 종료일보다 클 수 없습니다.")
    st.stop()

# ▶ session_state 업데이트
st.session_state.date_range = (start_date, end_date)

# ▶ 필터 적용
df_expense = df[
    (df["is_expense"]) &
    (df["date"] >= pd.to_datetime(start_date)) &
    (df["date"] <= pd.to_datetime(end_date))
].copy()


# ▶ 카테고리 태그 필터
st.sidebar.header("🏷 카테고리")

all_categories = sorted(
    df_expense["category_lv1"]
    .dropna()
    .unique()
)

selected_categories = st.sidebar.multiselect(
    "카테고리 선택 (태그)",
    options=all_categories,
    default=all_categories
)

df_expense = df_expense[
    df_expense["category_lv1"].isin(selected_categories)
].copy()

# =====================
# 메인
# =====================
st.title("📊 개인 소비 패턴 대시보드")

# ▶ 선택된 카테고리 해시태그 표시
if selected_categories:
    tag_text = " ".join([f"#{c}" for c in selected_categories])
    st.markdown(
        f"<div style='color:#6B7280; margin-bottom:12px;'>{tag_text}</div>",
        unsafe_allow_html=True
    )

# =====================
# 분석 기간 표시
# =====================
period_text = (
    f"{pd.to_datetime(start_date).strftime('%Y.%m.%d')} "
    f"~ {pd.to_datetime(end_date).strftime('%Y.%m.%d')}"
)

st.markdown(
    f"""
    <div style="
        margin-top:-8px;
        margin-bottom:20px;
        font-size:28px;
        font-weight:600;
        color:#374151;
    ">
        📆 분석 기간: <span style="color:#111827;">{period_text}</span>
    </div>
    """,
    unsafe_allow_html=True
)

# =====================
# 월별 지출 추이
# =====================
st.subheader("📈 월별 지출 추이")
st.plotly_chart(
    draw_monthly_trend(df_expense),
    use_container_width=True
)

st.divider()

# =====================
# 카테고리별 분석
# =====================
st.subheader("🧩 카테고리별 지출 비율")
st.plotly_chart(
    draw_category_pie(df_expense),
    use_container_width=True
)

st.subheader("📊 카테고리별 지출 금액")
st.plotly_chart(
    draw_category_bar(df_expense),
    use_container_width=True
)

# =====================
# 요일 · 시간대별 패턴
# =====================
st.subheader("🔥 요일 · 시간대별 지출 패턴")

if df_expense["hour"].notna().any():
    st.plotly_chart(
        draw_weekday_hour_heatmap(df_expense),
        use_container_width=True
    )
else:
    st.info("⏰ 시간 정보가 없어 요일/시간대 분석은 표시되지 않습니다.")
