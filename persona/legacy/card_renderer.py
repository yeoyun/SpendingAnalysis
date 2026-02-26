from __future__ import annotations

import base64
from typing import List, Optional

import streamlit as st

from .personas import PERSONA_16
from .scoring import PersonaResult
from app.styles import GRAY_300, GRAY_500, GRAY_700

from ai_report.ui import render_ai_report_detail, init_ai_report_state


def image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _get_ai_summary_income() -> Optional[int]:
    summary = st.session_state.get("ai_report_summary")
    if not isinstance(summary, dict):
        return None

    income = summary.get("income")
    if not isinstance(income, dict):
        return None

    v = income.get("expected_income_next_month")
    try:
        if v is None:
            return None
        return int(float(v))
    except Exception:
        return None


def _build_ai_reco_lines(max_lines: int = 3) -> List[str]:
    result = st.session_state.get("ai_report_result")
    if not isinstance(result, dict):
        return []

    lines: List[str] = []

    plan = result.get("action_plan")
    if isinstance(plan, list):
        for p in plan:
            if not isinstance(p, dict):
                continue
            title = str(p.get("title", "")).strip()
            if title:
                lines.append(title)
            if len(lines) >= max_lines:
                return lines

    sections = result.get("sections")
    if isinstance(sections, dict):
        actions_text = str(sections.get("actions", "") or "").strip()
        if actions_text:
            short = actions_text.split("\n")[0].strip()
            if short:
                lines.append(short)
            if len(lines) >= max_lines:
                return lines

    three = result.get("three_lines")
    if isinstance(three, list):
        for t in three:
            s = str(t).strip()
            if not s:
                continue
            if any(k in s for k in ["하세요", "추천", "줄이", "설정", "점검", "확인", "유지"]):
                lines.append(s)
            if len(lines) >= max_lines:
                return lines

    return lines[:max_lines]


def render_persona_top_card(result: Optional[PersonaResult]) -> None:
    """
    - AI 리포트 생성 전: 안내만 표시(카드 이미지/타이틀 없음)
    - AI 리포트 생성 후: 페르소나 카드 렌더 + 가이드 3줄 + 상세보기
    """
    init_ai_report_state()

    has_ai = isinstance(st.session_state.get("ai_report_result"), dict) and bool(st.session_state.get("ai_report_result"))

    st.subheader("✨ 내 소비유형")

    # ✅ AI 리포트 생성 전: 카드 영역엔 안내만
    if not has_ai or result is None:
        st.info("사이드바에서 ‘AI 리포트 생성’ 버튼을 누르면, 페르소나 분석 결과가 여기에 표시됩니다.")
        st.divider()
        return

    persona = PERSONA_16.get(result.persona_key)
    if persona is None:
        st.warning("페르소나 매핑 실패")
        st.divider()
        return

    # 1) 이미지
    img_base64 = image_to_base64(persona.image_path)
    st.markdown(
        f"""
        <div style="text-align:center;">
            <img src="data:image/png;base64,{img_base64}"
                 style="width:400px; display:inline-block;" />
        </div>
        """,
        unsafe_allow_html=True
    )

    # 2) 제목
    st.markdown(
        f"""
        <div style="
            text-align:center;
            font-size:27px;
            font-weight:900;
            color:{GRAY_700};
            margin-top:12px;
            margin-bottom:8px;
        ">
            {persona.title}
        </div>
        """,
        unsafe_allow_html=True
    )

    # 3) 예상 월 소득 (AI summary 우선)
    ai_income = _get_ai_summary_income()
    shown_income = ai_income if ai_income is not None else int(result.estimated_income)

    st.markdown(
        f"""
        <div style="
            text-align:center;
            font-size:19px;
            font-weight:600;
            color:{GRAY_300};
            margin-bottom:10px;
        ">
            예상 소득: {shown_income:,}원 / 월
        </div>
        """,
        unsafe_allow_html=True
    )

    # 4) 설명
    st.markdown(
        f"""
        <div style="
            text-align:center;
            font-size:16px;
            color:{GRAY_500};
            margin-bottom:20px;
        ">
            {persona.subtitle}
        </div>
        """,
        unsafe_allow_html=True
    )

    # 5) 가이드(3줄 요약/추천)
    st.markdown("### 💡 가이드")
    reco_lines = _build_ai_reco_lines(max_lines=3)

    if reco_lines:
        st.info("AI가 이번 소비 패턴을 바탕으로 추천하는 실행 항목입니다.")
        for line in reco_lines:
            st.write(f"- {line}")
    else:
        st.info("AI 리포트에서 실행 항목을 가져오지 못했습니다. (리포트 응답 구조를 확인해주세요.)")

    # 6) 상세보기 (기존 금융비서 리포트)
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("상세보기", use_container_width=True, key="btn_ai_detail_toggle"):
            st.session_state["ai_detail_open"] = not st.session_state.get("ai_detail_open", False)
            st.rerun()

    if st.session_state.get("ai_detail_open", False):
        with st.expander("AI 금융비서 리포트", expanded=True):
            render_ai_report_detail(compact=True)

    st.divider()