# app/sidebar.py

from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import Optional, Tuple, List

from expense_preprocess.preprocess import run_preprocess
from ai_report.ui import init_ai_report_state, render_ai_sidebar_controls

# ✅ 카테고리 느낌 메뉴 (option-menu)
# 없으면 selectbox로 자동 fallback
try:
    from streamlit_option_menu import option_menu
except Exception:
    option_menu = None


def render_sidebar_menu() -> str:
    """
    좌측 네비게이션 메뉴(카테고리 느낌)
    return: page string
    """
    with st.sidebar:
        st.markdown("## 📌 메뉴")

        if option_menu is not None:
            page = option_menu(
                menu_title=None,
                options=["🏠 홈", "🧠 AI 리포트"],
                icons=["house", "robot"],
                menu_icon="list",
                default_index=0,
                styles={
                    "container": {"padding": "0px 0px 8px 0px"},
                    "icon": {"font-size": "16px"},
                    "nav-link": {
                        "font-size": "15px",
                        "padding": "10px 12px",
                        "border-radius": "10px",
                    },
                    "nav-link-selected": {"font-weight": "700"},
                },
            )
        else:
            # 설치 안 되어 있어도 동작하도록 fallback
            page = st.selectbox("이동", ["🏠 홈", "🧠 AI 리포트"])

        st.divider()

    return page


def render_sidebar_uploader() -> Optional[pd.DataFrame]:
    """
    파일 업로드 + 전처리 후 df 반환.
    df는 st.session_state["df"]에 저장합니다.
    """
    st.sidebar.header("📂 데이터 업로드")

    uploaded_file = st.sidebar.file_uploader(
        "CSV / Excel 파일 업로드",
        type=["csv", "xlsx"],
    )

    if uploaded_file:
        try:
            st.session_state["df"] = run_preprocess(uploaded_file)
        except Exception as e:
            st.error(f"전처리 실패: {e}")
            st.stop()

    df = st.session_state.get("df")
    if df is None:
        st.info("좌측에서 CSV 파일을 업로드해주세요.")
        st.stop()

    return df


def render_sidebar_filters(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp, List[str]]:
    """
    기간/카테고리 필터를 사이드바에 렌더링하고,
    필터된 df_expense, start_date, end_date, selected_categories 를 반환합니다.
    """
    st.sidebar.header("🔎 필터")

    min_date = df["date"].min()
    max_date = df["date"].max()

    if "date_range" not in st.session_state:
        st.session_state.date_range = (min_date, max_date)

    date_range = st.sidebar.date_input(
        "📆 분석 기간 선택",
        value=st.session_state.date_range,
        min_value=min_date,
        max_value=max_date,
        key="date_picker",
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

    if start_date > end_date:
        st.warning("⚠ 시작일이 종료일보다 클 수 없습니다.")
        st.stop()

    st.session_state.date_range = (start_date, end_date)

    # 지출 데이터만 (기간)
    df_expense = df[
        (df["is_expense"])
        & (df["date"] >= pd.to_datetime(start_date))
        & (df["date"] <= pd.to_datetime(end_date))
    ].copy()

    # 카테고리 태그 필터
    st.sidebar.header("🏷 카테고리")

    all_categories = sorted(df_expense["category_lv1"].dropna().unique())
    selected_categories = st.sidebar.multiselect(
        "카테고리 선택 (태그)",
        options=all_categories,
        default=all_categories,
    )

    df_expense = df_expense[df_expense["category_lv1"].isin(selected_categories)].copy()

    return df_expense, pd.to_datetime(start_date), pd.to_datetime(end_date), selected_categories


def render_sidebar_ai_controls(
    *,
    df_all: pd.DataFrame,
    df_expense_filtered: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> None:
    """
    AI 리포트 생성 버튼/설정(페이지 무관 공통)
    """
    init_ai_report_state()
    render_ai_sidebar_controls(
        df_all=df_all,
        df_expense_filtered=df_expense_filtered,
        start_date=start_date,
        end_date=end_date,
    )


def build_sidebar() -> Tuple[str, pd.DataFrame, pd.DataFrame, pd.Timestamp, pd.Timestamp, List[str]]:
    """
    사이드바 전체를 한번에 구성하고,
    메인에서 쓸 값들을 반환합니다.
    """
    page = render_sidebar_menu()
    df = render_sidebar_uploader()
    df_expense, start_date, end_date, selected_categories = render_sidebar_filters(df)

    render_sidebar_ai_controls(
        df_all=df,
        df_expense_filtered=df_expense,
        start_date=start_date,
        end_date=end_date,
    )

    return page, df, df_expense, start_date, end_date, selected_categories