from __future__ import annotations

import base64
from typing import Optional

import streamlit as st

from .types import PersonaResult
from .registry import get_persona


GRAY_300 = "#9CA3AF"
GRAY_500 = "#6B7280"
GRAY_700 = "#111827"


def _image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def render_persona_top_card(result: Optional[PersonaResult]) -> None:
    """
    ✅ 정책
    - AI 리포트 생성 전: 안내만 표시
    - 생성 후: PersonaResult를 받아 persona registry 매핑 후 카드 렌더
    - 페르소나 카드는 '전체 기간(all)' 분석 결과만 반영
    """
    st.subheader("✨ 내 소비유형")

    # AI 생성 전 (전체 분석이 아직 없을 때)
    if result is None:
        st.info(
            "좌측 사이드바에서 **‘📊 전체 생성’**을 누르면 소비유형(페르소나)이 표시됩니다.\n\n"
            "※ ‘🗓️ 단기 생성’ 결과는 페르소나 카드에 반영되지 않습니다."
        )
        return

    persona = get_persona(result.persona_key)
    if persona is None:
        st.warning("페르소나 매핑 실패")
        st.caption(f"persona_key: {result.persona_key}")
        return

    # 이미지
    img_base64 = _image_to_base64(persona.image_path)
    st.markdown(
        f"""
        <div style="text-align:center;">
            <img src="data:image/png;base64,{img_base64}" style="width:380px;" />
        </div>
        """,
        unsafe_allow_html=True
    )

    # 타이틀
    st.markdown(
        f"""
        <div style="
            text-align:center;
            font-size:26px;
            font-weight:900;
            color:{GRAY_700};
            margin-top:12px;
            margin-bottom:6px;
        ">
            {persona.title}
        </div>
        """,
        unsafe_allow_html=True
    )

    # 공감 한 줄(one_liner)
    st.markdown(
        f"""
        <div style="
            text-align:center;
            font-size:16px;
            font-weight:600;
            color:{GRAY_500};
            margin-bottom:10px;
        ">
            {persona.one_liner}
        </div>
        """,
        unsafe_allow_html=True
    )

    # 예상 소득
    st.markdown(
        f"""
        <div style="
            text-align:center;
            font-size:18px;
            font-weight:600;
            color:{GRAY_300};
            margin-bottom:10px;
        ">
            예상 소득: {int(result.estimated_income):,}원 / 월
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown("<br><br>", unsafe_allow_html=True)

def get_persona_result_from_ai_all_session() -> Optional[PersonaResult]:
    """
    ✅ 전체기간(ai_report_*_all) 기반으로 PersonaResult를 구성해서 반환합니다.
    - 단기(short) 세션은 절대 보지 않음
    - PersonaResult는 (persona_key, estimated_income, signals) 3필드이므로 반드시 signals 포함
    """
    summary = st.session_state.get("ai_report_summary_all")
    result = st.session_state.get("ai_report_result_all")

    if not isinstance(summary, dict) or not isinstance(result, dict):
        return None

    # 1) 기본은 summary 기반 infer를 최우선 (signals까지 완비됨)
    inferred: Optional[PersonaResult] = None
    try:
        # persona/infer_ai.py 의 infer_persona_from_ai_summary 사용
        from persona import infer_persona_from_ai_summary
        inferred = infer_persona_from_ai_summary(summary)
    except Exception:
        inferred = None

    # 2) persona_key는 summary에 직접 들어있는 케이스도 지원
    persona_key = None
    persona_block = summary.get("persona")
    if isinstance(persona_block, dict):
        persona_key = persona_block.get("persona_key") or persona_block.get("key")

    # infer 결과가 있으면 그걸 기본으로 사용
    if inferred is not None:
        persona_key = persona_key or inferred.persona_key

    # 3) estimated_income는 summary 구조 변경 대응
    estimated_income = None
    income_block = summary.get("income")
    if isinstance(income_block, dict):
        estimated_income = income_block.get("expected_income_next_month")

    if estimated_income is None:
        estimated_income = summary.get("expected_income_next_month") or summary.get("estimated_income")

    # infer가 있으면 infer income을 fallback으로 사용
    if inferred is not None and (estimated_income is None):
        estimated_income = inferred.estimated_income

    # 4) signals: infer가 있으면 그대로 사용, 없으면 최소 dict라도 넣기
    signals = {}
    if inferred is not None and isinstance(getattr(inferred, "signals", None), dict):
        signals = inferred.signals

    # 5) 최종 검증
    if not persona_key or estimated_income is None:
        return None

    try:
        return PersonaResult(
            persona_key=str(persona_key),
            estimated_income=int(float(estimated_income)),
            signals=signals,
        )
    except Exception:
        return None