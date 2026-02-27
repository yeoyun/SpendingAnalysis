from __future__ import annotations

import streamlit as st
from typing import Any, Dict


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