from __future__ import annotations

import streamlit as st

from .helpers import _label_with_tooltip
from .state import init_ai_report_state
from .generators import generate_ai_report_all, generate_ai_report_last_30_days


# =========================
# Sidebar: settings + run/clear
# =========================
def render_ai_sidebar_controls(
    *,
    df_all,
    df_expense_filtered,
    start_date,
    end_date,
    model: str = "gemini-2.5-flash",
) -> None:
    """
    ✅ 사이드바: 리포트 설정 + (전체/단기) 생성 + 초기화
    - 전체 생성: generate_ai_report_all()  → session_state *_all
    - 단기 생성: generate_ai_report_last_30_days() → session_state *_short
    """
    init_ai_report_state()

    st.sidebar.subheader("🧠 AI 리포트")

    # -------------------------
    # 설정(기존 UI 유지)
    # -------------------------
    with st.sidebar.expander("리포트 설정", expanded=False):
        _label_with_tooltip(
            "정상 소비율 상한(지출/예상수입)",
            "지출/예상수입 비율이 이 값 이하이면 ‘정상’으로 판단합니다."
        )
        st.slider(
            "정상 소비율 상한",
            0.30, 0.80, 0.55, 0.01,
            key="ai_overspend_ok",
            label_visibility="collapsed"
        )

        _label_with_tooltip(
            "주의 소비율 상한(지출/예상수입)",
            "정상 상한 초과~이 값 이하 ‘주의’, 초과 시 ‘경고’"
        )
        st.slider(
            "주의 소비율 상한",
            0.40, 1.00, 0.70, 0.01,
            key="ai_overspend_warn",
            label_visibility="collapsed"
        )

        _label_with_tooltip("야간 기준 시간", "이 시간 이후 결제를 야간 소비로 분류합니다.")
        st.slider(
            "야간 기준 시간",
            20, 24, 22, 1,
            key="ai_late_hour",
            label_visibility="collapsed"
        )

        _label_with_tooltip("소액 결제 기준(원)", "이 금액 이하 결제를 소액 결제로 분류합니다.")
        st.number_input(
            "소액 결제 기준",
            min_value=1000,
            max_value=100000,
            value=10000,
            step=1000,
            key="ai_small_tx",
            label_visibility="collapsed"
        )

    st.sidebar.markdown("---")

    # -------------------------
    # 생성 버튼(✅ v2로 통일)
    # -------------------------
    c1, c2 = st.sidebar.columns(2)
    with c1:
        run_all = st.button("📊 전체 생성", key="sb_run_all", use_container_width=True)
    with c2:
        run_short = st.button("🗓️ 단기 생성", key="sb_run_short", use_container_width=True)

    # -------------------------
    # 초기화 버튼(전체/단기/레거시 모두 같이 지움)
    # -------------------------
    clear = st.sidebar.button("🧹 리포트 초기화", key="sb_clear_reports", use_container_width=True)

    if clear:
        st.session_state["ai_report_result"] = None
        st.session_state["ai_report_summary"] = None

        st.session_state["ai_report_result_all"] = None
        st.session_state["ai_report_summary_all"] = None

        st.session_state["ai_report_result_short"] = None
        st.session_state["ai_report_summary_short"] = None

        st.sidebar.success("초기화 완료")
        st.rerun()

    # -------------------------
    # 실행
    # -------------------------
    if run_all:
        # ✅ v2_all 저장 (persona 카드도 이걸 보게 하려는 목적)
        generate_ai_report_all(
            df_all=df_all,
            df_expense_filtered=df_expense_filtered,
            start_date=start_date,
            end_date=end_date,
            model=model,
        )

    if run_short:
        # ✅ v2_short 저장
        generate_ai_report_last_30_days(
            df_all=df_all,
            model=model,
        )