# ai_report/ui.py
# 리팩토링 전 전체코드

from __future__ import annotations
from dataclasses import asdict

import streamlit as st
import pandas as pd
from typing import Any, Dict, Optional

from ai_report.utils import load_ai_report, make_ai_report_key, save_ai_report

from .params import AIRuleParams
from .features import build_ai_summary
from .prompt import build_messages
from .llm import call_llm_json


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
    st.markdown("<br>", unsafe_allow_html=True)
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


# -------------------------
# ✅ payload 기반 판정 (세션 의존 제거)
# -------------------------
def _get_spend_judgement_from_payload(
    *,
    result: Dict[str, Any],
    summary: Optional[Dict[str, Any]] = None,
) -> str | None:
    # 1) summary 우선
    if isinstance(summary, dict):
        j = _normalize_judgement(summary.get("expense", {}).get("spend_judgement"))
        if j:
            return j

    # 2) three_lines 스캔
    three = result.get("three_lines", [])
    if isinstance(three, list):
        joined = " ".join([str(x) for x in three])
        j = _normalize_judgement(joined)
        if j:
            return j

    # 3) sections 스캔
    sections = result.get("sections", {})
    if isinstance(sections, dict):
        joined = " ".join([str(v) for v in sections.values() if v])
        j = _normalize_judgement(joined)
        if j:
            return j

    return None


# -------------------------
# (호환용) 기존 판정 함수
# -------------------------
def _get_spend_judgement(result: Dict[str, Any]) -> str | None:
    summary = st.session_state.get("ai_report_summary") or {}
    return _get_spend_judgement_from_payload(result=result, summary=summary if isinstance(summary, dict) else None)


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
        run_all = st.button("📊 전체 생성", key="sb_run_all", width="stretch")
    with c2:
        run_short = st.button("🗓️ 단기 생성", key="sb_run_short", width="stretch")

    # -------------------------
    # 초기화 버튼(전체/단기/레거시 모두 같이 지움)
    # -------------------------
    clear = st.sidebar.button("🧹 리포트 초기화", key="sb_clear_reports", width="stretch")

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
#  3줄 요약 박스 렌더러 (공용)
# =========================
def render_three_lines_summary_box(
    result: Dict[str, Any],
    *,
    judgement: str | None = None,
) -> None:
    """
    result["three_lines"]를 카드(박스) UI로 렌더링합니다.
    """
    three = result.get("three_lines", [])
    if not isinstance(three, list) or len(three) == 0:
        st.write("- (요약이 생성되지 않았습니다)")
        return

    lines = [str(x).strip() for x in three if str(x).strip()]
    if len(lines) == 0:
        st.write("- (요약이 생성되지 않았습니다)")
        return

    style_map = {
        "정상": {"bg": "#ECFDF3", "fg": "#027A48", "bd": "#A6F4C5", "label": "정상"},
        "주의": {"bg": "#FFFAEB", "fg": "#B54708", "bd": "#FEDF89", "label": "주의"},
        "경고": {"bg": "#FEF3F2", "fg": "#B42318", "bd": "#FECDCA", "label": "경고"},
    }
    conf = style_map.get(judgement or "", None)

    pill_html = ""
    if conf:
        pill_html = f"""
        <div style="margin-bottom:10px;">
          <span style="
            display:inline-flex;
            align-items:center;
            gap:6px;
            padding:6px 10px;
            border-radius:999px;
            background:{conf["bg"]};
            color:{conf["fg"]};
            border:1px solid {conf["bd"]};
            font-weight:800;
            font-size:12px;
            line-height:1;
          ">
            상태: {conf["label"]}
          </span>
        </div>
        """

    lines_html = "".join([
        f"""
        <div style="
          font-size:16px;
          color:#454753;
          font-weight:400;
          margin-top:'12px';
          white-space:pre-wrap;
          word-break:keep-all;
        ">{line}</div>
        """
        for line in lines[:3]
    ])

    st.markdown(
        f"""
        <div style="
          border:1px solid #F3F4F6;
          border-radius:18px;
          padding:36px 40px;
          background:#FFFFFF;
          box-shadow:0 2px 10px rgba(17,24,39,0.06);
          margin: 8px 0 14px 0;
          line-height:1.8;
        ">
          {pill_html}
          {lines_html}
        </div>
        """,
        unsafe_allow_html=True
    )


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


# =========================
# Structured renderer helpers
# =========================
def _safe_list(x):
    return x if isinstance(x, list) else []


def _safe_dict(x):
    return x if isinstance(x, dict) else {}


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
        st.dataframe(df_three, width="stretch", hide_index=True)
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
        st.dataframe(df_alerts, width="stretch", hide_index=True)
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
        st.dataframe(df_plan, width="stretch", hide_index=True)
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

# =========================
# ✅ 생성 로직: 전체 기간
# =========================
def generate_ai_report_all(
    *,
    df_all,
    df_expense_filtered,
    start_date,
    end_date,
    model: str = "gemini-2.5-flash",
):
    """전체 기간 리포트 생성 → session_state['_all']에 저장"""
    init_ai_report_state()

    params = _get_params_from_session()

    with st.spinner("전체 기간 리포트 생성 중..."):
        summary = build_ai_summary(
            df_all=df_all,
            df_expense_filtered=df_expense_filtered,
            start_date=start_date,
            end_date=end_date,
            params=params,
        )

        # ✅ 캐시 키(전체)
        try:
            params_dict = asdict(params)
        except Exception:
            params_dict = {
                "overspend_ratio_ok": params.overspend_ratio_ok,
                "overspend_ratio_warn": params.overspend_ratio_warn,
                "late_hour_start": params.late_hour_start,
                "small_tx_threshold": params.small_tx_threshold,
            }
        params_dict["mode"] = "all"

        cache_key = make_ai_report_key(
            summary=summary,
            params_dict=params_dict,
            model=model,
            version="v2_all",
        )

        cached_result, cached_summary = load_ai_report(key=cache_key, mode="all")
        if isinstance(cached_result, dict) and cached_result:
            st.session_state["ai_report_summary_all"] = cached_summary or summary
            st.session_state["ai_report_result_all"] = cached_result
            st.success("전체 기간: 캐시된 리포트를 불러왔습니다. (토큰 사용 0)")
            st.rerun()

        messages = build_messages(summary, mode="all")
        result = call_llm_json(messages, model=model)

        st.session_state["ai_report_summary_all"] = summary
        st.session_state["ai_report_result_all"] = result

        save_ai_report(result=result, summary=summary, key=cache_key, mode="all")

    st.success("전체 기간 리포트 생성 완료")
    st.rerun()

# =========================
# ✅ 생성 로직: 단기
# =========================
def generate_ai_report_last_30_days(
    *,
    df_all,
    model: str = "gemini-2.5-flash",
):
    """기준일=데이터 최신 날짜, 최근 30일 단기 리포트 → session_state['_short'] 저장"""
    init_ai_report_state()

    if df_all is None or df_all.empty:
        st.warning("데이터가 없습니다.")
        return

    params = _get_params_from_session()

    df_all = df_all.copy()
    df_all["date"] = pd.to_datetime(df_all["date"], errors="coerce")
    df_all = df_all.dropna(subset=["date"]).copy()

    end_date = df_all["date"].max().normalize()
    start_date = end_date - pd.Timedelta(days=29)

    df_30 = df_all[(df_all["date"] >= start_date) & (df_all["date"] <= end_date)].copy()

    with st.spinner("최근 30일(단기) 리포트 생성 중..."):
        summary = build_ai_summary(
            df_all=df_all,          # ✅ baseline(전체 히스토리) 포함 -> short_term_compare 근거 강화
            df_expense_filtered=df_30,
            start_date=start_date,
            end_date=end_date,
            params=params,
        )

        # ✅ 캐시 키(단기)
        try:
            params_dict = asdict(params)
        except Exception:
            params_dict = {
                "overspend_ratio_ok": params.overspend_ratio_ok,
                "overspend_ratio_warn": params.overspend_ratio_warn,
                "late_hour_start": params.late_hour_start,
                "small_tx_threshold": params.small_tx_threshold,
            }
        params_dict["mode"] = "short"
        params_dict["window_days"] = 30

        cache_key = make_ai_report_key(
            summary=summary,
            params_dict=params_dict,
            model=model,
            version="v2_short",
        )

        cached_result, cached_summary = load_ai_report(key=cache_key, mode="short")
        if isinstance(cached_result, dict) and cached_result:
            st.session_state["ai_report_summary_short"] = cached_summary or summary
            st.session_state["ai_report_result_short"] = cached_result
            st.success("단기: 캐시된 리포트를 불러왔습니다. (토큰 사용 0)")
            st.rerun()

        # ✅ 핵심: 단기 프롬프트 적용
        messages = build_messages(summary, mode="short")
        result = call_llm_json(messages, model=model)

        st.session_state["ai_report_summary_short"] = summary
        st.session_state["ai_report_result_short"] = result

        save_ai_report(result=result, summary=summary, key=cache_key, mode="short")

    st.success("최근 30일(단기) 리포트 생성 완료")
    st.rerun()
    
    
    
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
            # 체크하면 아래 내용은 접어도 되지만, 일단 정보는 항상 보이게
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