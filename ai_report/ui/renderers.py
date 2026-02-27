from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import Any, Dict, Optional

from .helpers import (
    _render_section,
    _get_spend_judgement,
    _get_spend_judgement_from_payload,
    _safe_list,
    _safe_dict,
)
from .state import init_ai_report_state
from .summary_box import render_three_lines_summary_box


# =========================
# Main: summary-only renderer (기존 호환)
# =========================
def render_ai_report_summary(*, show_header: bool = True) -> None:
    """
    홈 화면용: 3줄 요약(박스)만 간단히 렌더링합니다. (기존 호환)
    """
    init_ai_report_state()

    result: Dict[str, Any] = st.session_state.get("ai_report_result") or {}
    if not result:
        return

    judgement = _get_spend_judgement(result)
    render_three_lines_summary_box(result, judgement=judgement)
    st.markdown("<br><br>", unsafe_allow_html=True)


# =========================
# ✅ 공용: payload 기반 상세 렌더러
# =========================
def _render_ai_report_detail_with_payload(
    *,
    result: Dict[str, Any],
    summary: Optional[Dict[str, Any]] = None,
    compact: bool = False,
    key_prefix: str = "ai",
) -> None:
    """
    result/summary payload를 받아 동일 UI로 상세 리포트를 렌더링합니다.
    - key_prefix: 동일 페이지에 2개 리포트를 동시에 띄울 때 위젯 key 충돌 방지
    """
    if not isinstance(result, dict) or not result:
        return

    if not isinstance(summary, dict):
        summary = {}

    judgement = _get_spend_judgement_from_payload(result=result, summary=summary)
    render_three_lines_summary_box(result, judgement=judgement)

    if compact:
        st.divider()

    st.markdown("<br><br>", unsafe_allow_html=True)
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

        # ✅ 같은 화면에 두 리포트를 띄울 때 key 충돌 방지
        show_json = st.checkbox(
            "근거 데이터(JSON) 보기",
            value=False,
            key=f"{key_prefix}_show_summary_json",
        )
        if show_json:
            st.json(summary)


# =========================
# Main: detail renderer (기존 호환)
# =========================
def render_ai_report_detail(*, compact: bool = False) -> None:
    """
    기존 단일 리포트(호환용) 상세 렌더러.
    - session_state["ai_report_result"], ["ai_report_summary"] 사용
    """
    init_ai_report_state()

    result: Dict[str, Any] = st.session_state.get("ai_report_result") or {}
    summary: Dict[str, Any] = st.session_state.get("ai_report_summary") or {}

    _render_ai_report_detail_with_payload(
        result=result if isinstance(result, dict) else {},
        summary=summary if isinstance(summary, dict) else {},
        compact=compact,
        key_prefix="ai_legacy",
    )


# =========================
# ✅ 신규: 전체 기간 출력 전용 함수
# =========================
def render_ai_report_detail_all(*, compact: bool = False) -> None:
    """
    전체 기간 리포트 출력 전용.
    - session_state["ai_report_result_all"], ["ai_report_summary_all"] 사용
    """
    init_ai_report_state()

    result: Dict[str, Any] = st.session_state.get("ai_report_result_all") or {}
    summary: Dict[str, Any] = st.session_state.get("ai_report_summary_all") or {}

    _render_ai_report_detail_with_payload(
        result=result if isinstance(result, dict) else {},
        summary=summary if isinstance(summary, dict) else {},
        compact=compact,
        key_prefix="ai_all",
    )
    st.markdown("<br>", unsafe_allow_html=True)
    st.divider()
    st.markdown("<br>", unsafe_allow_html=True)


# =========================
# ✅ 신규: 단기간(주간/30일 등) 출력 전용 함수
# =========================
def render_ai_report_detail_short(*, compact: bool = False) -> None:
    """
    ✅ 단기간(주간/30일 등) 리포트 출력 전용 - 플랜 중심 UI
    """
    init_ai_report_state()

    result: Dict[str, Any] = st.session_state.get("ai_report_result_short") or {}
    summary: Dict[str, Any] = st.session_state.get("ai_report_summary_short") or {}

    _render_ai_report_short_plan_focused(
        result=result if isinstance(result, dict) else {},
        summary=summary if isinstance(summary, dict) else {},
        compact=compact,
        key_prefix="ai_short_plan",
    )


def render_ai_report_structured(*, show_json_toggle: bool = False) -> None:
    """
    (기존 호환) 단일 리포트를 '표/체크리스트 중심'으로 재구성해 보여주는 렌더러.
    - session_state["ai_report_result"]
    - session_state["ai_report_summary"]
    """
    result: Dict[str, Any] = st.session_state.get("ai_report_result") or {}
    summary: Dict[str, Any] = st.session_state.get("ai_report_summary") or {}

    if not result:
        return

    exp = _safe_dict(summary.get("expense"))
    inc = _safe_dict(summary.get("income"))
    period = _safe_dict(summary.get("period"))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("기간", f'{period.get("start","-")} ~ {period.get("end","-")}')
    with c2:
        total = exp.get("total_expense")
        st.metric("총 지출", f'{total:,.0f}원' if isinstance(total, (int, float)) else "-")
    with c3:
        expected = inc.get("expected_income_next_month")
        st.metric("추정 소득(다음달)", f'{expected:,.0f}원' if isinstance(expected, (int, float)) else "-")
    with c4:
        ratio = exp.get("spend_ratio")
        st.metric("지출/소득 비율", f'{ratio:.1%}' if isinstance(ratio, (int, float)) else "-")

    st.divider()

    three = _safe_list(result.get("three_lines"))
    three_rows = []
    labels = ["요약", "문제", "액션"]
    for i, line in enumerate(three[:3]):
        three_rows.append({"구분": labels[i] if i < len(labels) else f"Line{i+1}", "내용": str(line).strip()})

    st.subheader("🧾 요약 3줄")
    if three_rows:
        df_three = pd.DataFrame(three_rows)
        st.dataframe(df_three, use_container_width=True, hide_index=True)
    else:
        st.info("요약 3줄 데이터가 없습니다.")

    st.divider()

    st.subheader("🚨 알림/룰 기반 체크")
    alerts = _safe_list(result.get("alerts"))
    if alerts:
        df_alerts = pd.DataFrame([{
            "Rule": a.get("rule", ""),
            "Trigger": a.get("trigger", ""),
            "Evidence": a.get("evidence", ""),
            "Recommendation": a.get("recommendation", ""),
        } for a in alerts[:8]])
        st.dataframe(df_alerts, use_container_width=True, hide_index=True)
    else:
        st.caption("알림 항목이 없습니다.")

    st.divider()

    st.subheader("✅ 액션 플랜")
    plan = _safe_list(result.get("action_plan"))
    if plan:
        for idx, p in enumerate(plan[:6], start=1):
            title = str(p.get("title", "")).strip() or f"Action {idx}"
            how = str(p.get("how", "")).strip()
            why = str(p.get("why", "")).strip()
            metric = str(p.get("metric", "")).strip()

            with st.expander(f"{idx}. {title}", expanded=(idx <= 2)):
                if how:
                    st.write(f"**방법**: {how}")
                if why:
                    st.write(f"**이유**: {why}")
                if metric:
                    st.write(f"**측정지표**: {metric}")

        df_plan = pd.DataFrame([{
            "Title": p.get("title", ""),
            "How": p.get("how", ""),
            "Why": p.get("why", ""),
            "Metric": p.get("metric", ""),
        } for p in plan[:10]])
        st.dataframe(df_plan, use_container_width=True, hide_index=True)
    else:
        st.caption("액션 플랜이 없습니다.")

    st.divider()

    st.subheader("📚 섹션(서술형 리포트)")
    sections = _safe_dict(result.get("sections"))

    tab1, tab2, tab3 = st.tabs(["수입/지출", "패턴/리스크", "가이드/한계"])
    with tab1:
        if sections.get("income_forecast"):
            st.markdown(sections["income_forecast"])
        if sections.get("expense_vs_income"):
            st.markdown(sections["expense_vs_income"])

    with tab2:
        if sections.get("persona"):
            st.markdown(sections["persona"])
        if sections.get("risks"):
            st.markdown(sections["risks"])

    with tab3:
        if sections.get("actions"):
            st.markdown(sections["actions"])
        if sections.get("limits"):
            st.markdown(sections["limits"])

    if show_json_toggle:
        show = st.checkbox("LLM 결과 JSON 보기", value=False)
        if show:
            st.json(result)


def _render_ai_report_short_plan_focused(
    *,
    result: Dict[str, Any],
    summary: Optional[Dict[str, Any]] = None,
    compact: bool = False,
    key_prefix: str = "ai_short",
) -> None:
    """
    ✅ 단기 리포트 전용: '플랜(체크리스트)' 중심 UI
    - 상단: 3줄 요약 + 상태 pill
    - 메인: action_plan 체크리스트(평일/주말 그룹) + 바로 실행 KPI
    - 보조: sections.actions(이번 주 목표/평일/주말/체크방법)만 노출
    - 참고: alerts + JSON 토글(옵션)
    """
    if not isinstance(result, dict) or not result:
        return
    if not isinstance(summary, dict):
        summary = {}

    # 1) 상단 요약 박스
    judgement = _get_spend_judgement_from_payload(result=result, summary=summary)
    render_three_lines_summary_box(result, judgement=judgement)
    if compact:
        st.divider()

    # 2) 단기 핵심 KPI 카드(있으면)
    stc = summary.get("short_term_compare", {})
    if isinstance(stc, dict) and stc.get("available") is True:
        cur_total = stc.get("current", {}).get("total")
        base_total = stc.get("baseline", {}).get("total_for_window")
        diff = stc.get("change", {}).get("diff")
        pct = stc.get("change", {}).get("pct")
        baseline_used = stc.get("baseline", {}).get("used")
        conf = stc.get("baseline", {}).get("confidence")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("최근 30일 지출", f"{cur_total:,.0f}원" if isinstance(cur_total, (int, float)) else "-")
        with c2:
            st.metric("비교 기준", str(baseline_used or "-"))
        with c3:
            st.metric("증감(원)", f"{diff:,.0f}원" if isinstance(diff, (int, float)) else "-")
        with c4:
            st.metric("증감(%)", f"{pct*100:.1f}%" if isinstance(pct, (int, float)) else "-", str(conf or ""))

        st.divider()

    # 3) 메인: 플랜(체크리스트) 섹션
    st.markdown("### ✅ 이번 주 실행 플랜 (체크리스트)")
    plan = result.get("action_plan", [])
    if not isinstance(plan, list) or len(plan) == 0:
        st.info("체크리스트(action_plan)가 없습니다. 단기 프롬프트가 적용되었는지 확인해주세요.")
        return

    # 평일/주말 그룹핑
    weekday_items, weekend_items, other_items = [], [], []
    for p in plan:
        title = str(p.get("title", "")).strip()
        if title.startswith("[평일]"):
            weekday_items.append(p)
        elif title.startswith("[주말]"):
            weekend_items.append(p)
        else:
            other_items.append(p)

    # ✅ 체크박스로 "완료 체크" UX (세션 key 충돌 방지)
    def _render_plan_group(group_title: str, items: list, group_key: str):
        if not items:
            return
        st.markdown(f"#### {group_title}")
        for idx, p in enumerate(items, start=1):
            title = str(p.get("title", "")).strip() or f"Action {idx}"
            how = str(p.get("how", "")).strip()
            why = str(p.get("why", "")).strip()
            metric = str(p.get("metric", "")).strip()

            checked = st.checkbox(
                title,
                value=False,
                key=f"{key_prefix}_{group_key}_{idx}_done",
            )
            if how:
                st.caption(f"방법: {how}")
            if metric:
                st.caption(f"KPI: {metric}")
            if why:
                st.caption(f"근거: {why}")
            st.markdown("")

    colL, colR = st.columns(2)
    with colL:
        _render_plan_group("📅 평일(월~금)", weekday_items, "weekday")
    with colR:
        _render_plan_group("🌿 주말(토~일)", weekend_items, "weekend")

    if other_items:
        st.divider()
        _render_plan_group("🧩 기타", other_items, "other")

    # 4) 보조: 실행 가이드(= sections.actions)만 보여주기
    sections = result.get("sections", {}) if isinstance(result.get("sections", {}), dict) else {}
    actions_text = sections.get("actions")
    if actions_text:
        st.divider()
        st.markdown("### 🧭 실행 가이드(요약)")
        st.markdown(str(actions_text))

    # 5) 참고: alerts + limits
    st.divider()
    with st.expander("📎 참고(알림/한계/근거 JSON)", expanded=False):
        limits = sections.get("limits")
        if limits:
            st.markdown("#### 한계/주의")
            st.markdown(str(limits))

        alerts = result.get("alerts", [])
        if isinstance(alerts, list) and alerts:
            st.markdown("#### 알림")
            for a in alerts[:5]:
                rule = a.get("rule", "")
                evidence = a.get("evidence", "")
                rec = a.get("recommendation", "")
                if rule:
                    st.markdown(f"- **{rule}**")
                if evidence:
                    st.caption(f"근거: {evidence}")
                if rec:
                    st.caption(f"권장: {rec}")
                st.markdown("")

        show_json = st.checkbox(
            "근거 데이터(JSON) 보기",
            value=False,
            key=f"{key_prefix}_show_summary_json_plan",
        )
        if show_json:
            st.json(summary)