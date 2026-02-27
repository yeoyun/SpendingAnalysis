from __future__ import annotations

import streamlit as st
from typing import Any, Dict, Optional


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
# Structured renderer helpers
# =========================
def _safe_list(x):
    return x if isinstance(x, list) else []


def _safe_dict(x):
    return x if isinstance(x, dict) else {}

label_with_tooltip = _label_with_tooltip