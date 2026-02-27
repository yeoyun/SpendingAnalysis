from __future__ import annotations

import streamlit as st

from ..params import AIRuleParams


# =========================
# Session State
# =========================
def init_ai_report_state() -> None:
    """
    ✅ 세션 키를 2벌로 준비합니다.
    - (호환용) 기존 단일 키: ai_report_result / ai_report_summary
    - (신규) 전체 기간: ai_report_result_all / ai_report_summary_all
    - (신규) 단기간(주간/30일 등): ai_report_result_short / ai_report_summary_short
    """
    # ---- 기존 호환용 ----
    if "ai_report_result" not in st.session_state:
        st.session_state["ai_report_result"] = None
    if "ai_report_summary" not in st.session_state:
        st.session_state["ai_report_summary"] = None
    if "ai_detail_open" not in st.session_state:
        st.session_state["ai_detail_open"] = False

    # ---- 신규: 전체기간 ----
    if "ai_report_result_all" not in st.session_state:
        st.session_state["ai_report_result_all"] = None
    if "ai_report_summary_all" not in st.session_state:
        st.session_state["ai_report_summary_all"] = None

    # ---- 신규: 단기간(주간/30일 등) ----
    if "ai_report_result_short" not in st.session_state:
        st.session_state["ai_report_result_short"] = None
    if "ai_report_summary_short" not in st.session_state:
        st.session_state["ai_report_summary_short"] = None


def _get_params_from_session() -> AIRuleParams:
    """사이드바에서 설정한 파라미터를 그대로 사용 (없으면 기본값)."""
    return AIRuleParams(
        overspend_ratio_ok=float(st.session_state.get("ai_overspend_ok", 0.55)),
        overspend_ratio_warn=float(st.session_state.get("ai_overspend_warn", 0.70)),
        late_hour_start=int(st.session_state.get("ai_late_hour", 22)),
        small_tx_threshold=int(st.session_state.get("ai_small_tx", 10000)),
    )