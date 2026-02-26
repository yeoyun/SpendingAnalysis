# ai_report/ui.py

from __future__ import annotations

import streamlit as st
from typing import Any, Dict

from .params import AIRuleParams
from .features import build_ai_summary
from .prompt import build_messages
from .llm import call_llm_json


# =========================
# Session State
# =========================
def init_ai_report_state() -> None:
    if "ai_report_result" not in st.session_state:
        st.session_state["ai_report_result"] = None
    if "ai_report_summary" not in st.session_state:
        st.session_state["ai_report_summary"] = None
    if "ai_detail_open" not in st.session_state:
        st.session_state["ai_detail_open"] = False


# =========================
# Small UI helpers
# =========================
def _label_with_tooltip(title: str, tooltip: str):
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:6px; margin: 4px 0;">
          <span style="font-weight:600;">{title}</span>
          <span title="{tooltip}" style="
              cursor: help;
              color:#6B7280;
              border:1px solid #D1D5DB;
              border-radius:999px;
              padding:0px 6px;
              font-size:12px;
              line-height:18px;
          ">i</span>
        </div>
        """,
        unsafe_allow_html=True
    )


def _render_section(title: str, body: Any, *, divider: bool = True):
    if body is None:
        return
    text = str(body).strip()
    if not text:
        return
    st.markdown(f"#### {title}")
    st.markdown(text)
    if divider:
        st.divider()


def _normalize_judgement(value: str | None) -> str | None:
    if not value:
        return None
    v = str(value).strip().lower()
    if "정상" in v or v == "ok" or "normal" in v:
        return "정상"
    if "주의" in v or "warning" in v:
        return "주의"
    if "경고" in v or "danger" in v or "critical" in v:
        return "경고"
    if value in ("정상", "주의", "경고"):
        return value
    return None


def _get_spend_judgement(result: Dict[str, Any]) -> str | None:
    summary = st.session_state.get("ai_report_summary") or {}
    if isinstance(summary, dict):
        j = _normalize_judgement(summary.get("expense", {}).get("spend_judgement"))
        if j:
            return j

    three = result.get("three_lines", [])
    if isinstance(three, list):
        joined = " ".join([str(x) for x in three])
        j = _normalize_judgement(joined)
        if j:
            return j

    sections = result.get("sections", {})
    if isinstance(sections, dict):
        joined = " ".join([str(v) for v in sections.values() if v])
        j = _normalize_judgement(joined)
        if j:
            return j

    return None


def _render_status_pill(judgement: str | None):
    if not judgement:
        return

    style_map = {
        "정상": {"bg": "#ECFDF3", "fg": "#027A48", "bd": "#A6F4C5", "label": "정상"},
        "주의": {"bg": "#FFFAEB", "fg": "#B54708", "bd": "#FEDF89", "label": "주의"},
        "경고": {"bg": "#FEF3F2", "fg": "#B42318", "bd": "#FECDCA", "label": "경고"},
    }
    conf = style_map.get(judgement)
    if not conf:
        return

    st.markdown(
        f"""
        <div style="margin: 6px 0 10px 0;">
          <span style="
            display:inline-flex;
            align-items:center;
            gap:6px;
            padding:6px 10px;
            border-radius:999px;
            background:{conf["bg"]};
            color:{conf["fg"]};
            border:1px solid {conf["bd"]};
            font-weight:700;
            font-size:13px;
            line-height:1;
          ">
            상태: {conf["label"]}
          </span>
        </div>
        """,
        unsafe_allow_html=True
    )


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
    사이드바에 '리포트 설정' + 'AI 리포트 생성/초기화' 버튼만 렌더링합니다.
    생성 결과는 session_state["ai_report_summary"], ["ai_report_result"]에 저장됩니다.
    """
    init_ai_report_state()

    st.sidebar.subheader("🧠 AI 리포트")

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

    params = AIRuleParams(
        overspend_ratio_ok=float(st.session_state.get("ai_overspend_ok", 0.55)),
        overspend_ratio_warn=float(st.session_state.get("ai_overspend_warn", 0.70)),
        late_hour_start=int(st.session_state.get("ai_late_hour", 22)),
        small_tx_threshold=int(st.session_state.get("ai_small_tx", 10000)),
    )

    run = st.sidebar.button("✨ 내 소비 분석하기", type="primary", use_container_width=True)
    clear = st.sidebar.button("초기화", use_container_width=True)

    if clear:
        st.session_state["ai_report_result"] = None
        st.session_state["ai_report_summary"] = None
        st.session_state["ai_detail_open"] = False
        st.sidebar.success("초기화 완료")
        st.rerun()

    if run:
        try:
            with st.spinner("AI 리포트를 생성 중입니다..."):
                summary = build_ai_summary(
                    df_all=df_all,
                    df_expense_filtered=df_expense_filtered,
                    start_date=start_date,
                    end_date=end_date,
                    params=params
                )
                messages = build_messages(summary)
                result = call_llm_json(messages, model=model)

                st.session_state["ai_report_summary"] = summary
                st.session_state["ai_report_result"] = result

            st.sidebar.success("리포트 생성 완료")
            st.rerun()
        except Exception as e:
            st.sidebar.error("AI 리포트 생성 중 오류가 발생했습니다.")
            st.sidebar.caption(f"에러: {e}")


# =========================
# Main: summary-only renderer (NEW)
# =========================
def render_ai_report_summary(*, show_header: bool = True) -> None:
    """
    홈 화면용: 상태 pill + 3줄 요약만 간단히 렌더링합니다.
    """
    init_ai_report_state()

    result: Dict[str, Any] = st.session_state.get("ai_report_result") or {}
    if not result:
        return

    judgement = _get_spend_judgement(result)
    _render_status_pill(judgement)

    if show_header:
        st.subheader("🧠 AI 리포트")

    st.markdown("### ✅ 3줄 요약")
    three = result.get("three_lines", [])
    if isinstance(three, list) and len(three) > 0:
        for line in three[:3]:
            st.write(f"- {line}")
    else:
        st.write("- (요약이 생성되지 않았습니다)")


# =========================
# Main: detail renderer (existing)
# =========================
def render_ai_report_detail(*, compact: bool = False) -> None:
    """
    이미 생성된 AI 리포트를 '메인 영역'에 상세 렌더링합니다.
    (사이드바 컨트롤/생성 버튼은 여기서 렌더링하지 않습니다.)
    """
    init_ai_report_state()

    result: Dict[str, Any] = st.session_state.get("ai_report_result") or {}
    if not result:
        return

    judgement = _get_spend_judgement(result)
    _render_status_pill(judgement)

    st.subheader("🧠 AI 리포트")
    st.markdown("### ✅ 3줄 요약")
    three = result.get("three_lines", [])
    if isinstance(three, list) and len(three) > 0:
        for line in three[:3]:
            st.write(f"- {line}")
    else:
        st.write("- (요약이 생성되지 않았습니다)")

    if compact:
        st.divider()

    st.markdown("### 📌 상세 리포트")
    tabs = st.tabs(["요약", "분석", "실행", "참고"])

    sections = result.get("sections", {})
    if not isinstance(sections, dict):
        sections = {}

    with tabs[0]:
        _render_section("수입 추정", sections.get("income_forecast"))
        _render_section("지출 진단", sections.get("expense_vs_income"), divider=False)

    with tabs[1]:
        _render_section("소비 패턴", sections.get("persona"))
        _render_section("위험 신호", sections.get("risks"), divider=False)

    with tabs[2]:
        _render_section("실행 가이드", sections.get("actions"))

        plan = result.get("action_plan", [])
        if isinstance(plan, list) and len(plan) > 0:
            st.markdown("#### 체크리스트")
            for p in plan[:5]:
                title = p.get("title", "")
                how = p.get("how", "")
                metric = p.get("metric", "")

                if title:
                    st.markdown(f"- **{title}**")
                if how:
                    st.write(f"방법: {how}")
                if metric:
                    st.caption(f"측정지표: {metric}")
                st.write("")
        else:
            st.info("체크리스트 항목이 없습니다.")

    with tabs[3]:
        _render_section("데이터 참고", sections.get("limits"))

        alerts = result.get("alerts", [])
        if isinstance(alerts, list) and len(alerts) > 0:
            st.markdown("#### 알림")
            for a in alerts[:5]:
                rule = a.get("rule", "")
                evidence = a.get("evidence", "")
                rec = a.get("recommendation", "")

                if rule:
                    st.markdown(f"- **{rule}**")
                if evidence:
                    st.write(f"근거: {evidence}")
                if rec:
                    st.write(f"권장: {rec}")
                st.write("")
        else:
            st.info("현재 알림이 없습니다.")

        show_json = st.checkbox("근거 데이터(JSON) 보기", value=False, key="ai_show_summary_json")
        if show_json:
            st.json(st.session_state.get("ai_report_summary"))