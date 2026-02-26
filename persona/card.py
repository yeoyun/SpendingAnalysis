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
    """
    st.subheader("✨ 내 소비유형")

    # AI 생성 전
    if result is None:
        st.info("좌측 사이드바에서 ‘✨ 내 소비 분석하기’ 버튼을 누르면 분석 결과가 표시됩니다.")
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
