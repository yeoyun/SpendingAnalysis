# ai_report/ui/short_report_ui.py
"""
단기 소비 리포트 UI — 간결·세련 버전
사용:
    from ai_report.ui.short_report_ui import render_short_report
    render_short_report(result=..., summary=...)
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import streamlit as st


# ────────────────────────────────────────────────────
# CSS (딱 필요한 것만)
# ────────────────────────────────────────────────────
_CSS = """
<style>
.rp-summary {
    background:#fff; border:1px solid #EAECF0; border-radius:16px;
    padding:28px 32px; margin-bottom:20px;
    box-shadow:0 1px 6px rgba(0,0,0,.06);
}
.rp-pill {
    display:inline-block; padding:3px 12px; border-radius:20px;
    font-size:12px; font-weight:700; margin-bottom:14px; border:1px solid;
}
.rp-line { font-size:15px; color:#374151; line-height:1.9; }

.rp-kpi { background:#F9FAFB; border:1px solid #EAECF0; border-radius:12px; padding:16px 18px; }
.rp-kpi-label { font-size:11px; color:#9CA3AF; font-weight:600; text-transform:uppercase; letter-spacing:.05em; }
.rp-kpi-val { font-size:20px; font-weight:800; color:#111827; margin-top:4px; }
.rp-up   { color:#DC2626; }
.rp-down { color:#059669; }

.rp-card {
    background:#fff; border:1px solid #EAECF0; border-radius:12px;
    padding:16px 18px; margin-bottom:8px;
    box-shadow:0 1px 4px rgba(0,0,0,.04);
}
.rp-tag {
    display:inline-block; font-size:11px; font-weight:600;
    padding:2px 8px; border-radius:6px; margin:4px 4px 0 0;
}

.rp-alert {
    display:flex; gap:12px;
    background:#fff; border:1px solid #EAECF0; border-radius:12px;
    padding:14px 16px; margin-bottom:8px;
}
.rp-section { background:#F9FAFB; border-radius:12px; padding:18px 20px; margin-bottom:10px; }
.rp-section-title { font-size:11px; font-weight:700; color:#9CA3AF; text-transform:uppercase; letter-spacing:.06em; margin-bottom:8px; }
.rp-section-body  { font-size:14px; color:#374151; line-height:1.75; }
</style>
"""

_INJECTED = False
def _css():
    global _INJECTED
    if not _INJECTED:
        st.markdown(_CSS, unsafe_allow_html=True)
        _INJECTED = True


# ────────────────────────────────────────────────────
# 헬퍼
# ────────────────────────────────────────────────────
def _won(v, signed=False):
    if not isinstance(v, (int, float)): return "—"
    s = f"{abs(v):,.0f}원"
    return ("+" if v >= 0 else "−") + s if signed else s

def _pct(v, signed=False):
    if not isinstance(v, (int, float)): return "—"
    s = f"{abs(v*100):.1f}%"
    return ("+" if v >= 0 else "−") + s if signed else s

def _judgement(result, summary):
    text = " ".join([
        str((summary.get("expense") or {}).get("spend_judgement", "")),
        " ".join(str(x) for x in (result.get("three_lines") or [])),
    ])
    for kw, label in [("정상","정상"),("주의","주의"),("경고","경고"),
                      ("ok","정상"),("warn","주의"),("danger","경고")]:
        if kw in text.lower(): return label
    return None


# ────────────────────────────────────────────────────
# 블록 1 — 요약 카드
# ────────────────────────────────────────────────────
def _summary_card(result, summary):
    lines = [str(x).strip() for x in (result.get("three_lines") or []) if str(x).strip()]
    if not lines:
        return

    J = _judgement(result, summary)
    pill_cfg = {
        "정상": ("#ECFDF3","#027A48","#A6F4C5","🟢"),
        "주의": ("#FFFAEB","#B54708","#FEDF89","🟡"),
        "경고": ("#FEF3F2","#B42318","#FECDCA","🔴"),
    }.get(J)

    pill = ""
    if pill_cfg:
        bg, fg, bd, icon = pill_cfg
        pill = f'<div><span class="rp-pill" style="background:{bg};color:{fg};border-color:{bd}">{icon} {J}</span></div>'

    prefix = ["📊", "⚠️", "✅"]
    body = "".join(f'<div class="rp-line">{prefix[i]} {l}</div>' for i, l in enumerate(lines[:3]))
    st.markdown(f'<div class="rp-summary">{pill}{body}</div>', unsafe_allow_html=True)


# ────────────────────────────────────────────────────
# 블록 2 — KPI 4개
# ────────────────────────────────────────────────────
def _kpi_row(summary):
    stc = summary.get("short_term_compare") or {}
    if not stc.get("available"):
        return

    cur  = (stc.get("current")  or {}).get("total")
    base = (stc.get("baseline") or {}).get("total_for_window")
    diff = (stc.get("change")   or {}).get("diff")
    pct  = (stc.get("change")   or {}).get("pct")
    base_label = (stc.get("baseline") or {}).get("used", "—")

    def _card(label, val, sub="", color_cls=""):
        sub_html = f'<div style="font-size:11px;color:#9CA3AF;margin-top:3px">{sub}</div>' if sub else ""
        return (
            f'<div class="rp-kpi">'
            f'<div class="rp-kpi-label">{label}</div>'
            f'<div class="rp-kpi-val {color_cls}">{val}</div>'
            f'{sub_html}</div>'
        )

    diff_cls = "rp-up" if isinstance(diff,(int,float)) and diff > 0 else "rp-down"
    pct_cls  = "rp-up" if isinstance(pct,(int,float))  and pct  > 0 else "rp-down"

    cols = st.columns(4)
    cards = [
        _card("최근 30일 지출", _won(cur)),
        _card("비교 기준", _won(base), sub=str(base_label)),
        _card("증감(원)", _won(diff, True), color_cls=diff_cls),
        _card("증감(%)",  _pct(pct, True),  color_cls=pct_cls),
    ]
    for col, card in zip(cols, cards):
        with col:
            st.markdown(card, unsafe_allow_html=True)


# ────────────────────────────────────────────────────
# 블록 3 — 플랜 체크리스트
# ────────────────────────────────────────────────────
def _plan_section(result, key_prefix):
    plan: List[Dict] = result.get("action_plan") or []
    if not plan:
        st.caption("실행 플랜이 없습니다.")
        return

    weekday = [p for p in plan if "[평일]" in str(p.get("title",""))]
    weekend = [p for p in plan if "[주말]" in str(p.get("title",""))]
    other   = [p for p in plan if "[평일]" not in str(p.get("title","")) and "[주말]" not in str(p.get("title",""))]

    def _group(items, icon, label, gkey):
        if not items:
            return
        st.markdown(f"**{icon} {label}**")
        for i, p in enumerate(items, 1):
            title  = str(p.get("title","")).replace("[평일]","").replace("[주말]","").strip() or f"항목 {i}"
            how    = str(p.get("how","")).strip()
            metric = str(p.get("metric","")).strip()
            why    = str(p.get("why","")).strip()

            done = st.checkbox(title, key=f"{key_prefix}_{gkey}_{i}")

            tags = ""
            if metric: tags += f'<span class="rp-tag" style="background:#F0FDF4;color:#166534">🎯 {metric}</span>'
            if how:    tags += f'<span class="rp-tag" style="background:#EFF6FF;color:#1D4ED8">📌 {how[:55]}{"…" if len(how)>55 else ""}</span>'
            if why:    tags += f'<span class="rp-tag" style="background:#FFFBEB;color:#92400E">📎 {why[:55]}{"…" if len(why)>55 else ""}</span>'

            fade = "opacity:.45;" if done else ""
            st.markdown(
                f'<div class="rp-card" style="{fade}"><div>{tags}</div></div>',
                unsafe_allow_html=True
            )

    col_l, col_r = st.columns(2, gap="medium")
    with col_l:
        _group(weekday, "📅", "평일 (월~금)", "wd")
    with col_r:
        _group(weekend, "🌿", "주말 (토~일)", "we")
    if other:
        st.markdown("---")
        _group(other, "🧩", "기타", "ot")


# ────────────────────────────────────────────────────
# 블록 4 — 알림
# ────────────────────────────────────────────────────
def _alerts_section(alerts: List[Dict]):
    if not alerts:
        st.caption("현재 감지된 알림이 없습니다.")
        return

    icons = ["🔴","🟠","🟡","🟢","🔵"]
    for i, a in enumerate(alerts[:5]):
        rule = str(a.get("rule","")).strip()
        ev   = str(a.get("evidence","")).strip()
        rec  = str(a.get("recommendation","")).strip()
        st.markdown(
            f'<div class="rp-alert">'
            f'<div style="font-size:22px;line-height:1.2">{icons[i]}</div>'
            f'<div style="flex:1">'
            f'<div style="font-size:13px;font-weight:700;color:#111827">{rule or f"알림 {i+1}"}</div>'
            f'{"<div style=font-size:12px;color:#6B7280;margin-top:4px>📎 "+ev+"</div>" if ev else ""}'
            f'{"<div style=font-size:12px;color:#1D4ED8;margin-top:4px>💡 "+rec+"</div>" if rec else ""}'
            f'</div></div>',
            unsafe_allow_html=True
        )


# ────────────────────────────────────────────────────
# 블록 5 — 텍스트 섹션
# ────────────────────────────────────────────────────
def _text_block(icon, title, text):
    if not text or not str(text).strip():
        return
    body = str(text).strip().replace("\n","<br>")
    st.markdown(
        f'<div class="rp-section">'
        f'<div class="rp-section-title">{icon} {title}</div>'
        f'<div class="rp-section-body">{body}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


# ────────────────────────────────────────────────────
# ✅ 공개 함수
# ────────────────────────────────────────────────────
def render_short_report(
    *,
    result: Dict[str, Any],
    summary: Optional[Dict[str, Any]] = None,
    key_prefix: str = "sr",
) -> None:
    """단기 소비 리포트 전체 렌더링"""
    if not isinstance(result, dict) or not result:
        st.info("단기 리포트가 없습니다. 사이드바에서 '단기 생성'을 눌러주세요.")
        return
    if not isinstance(summary, dict):
        summary = {}

    _css()
    sections: Dict = result.get("sections") or {}

    _summary_card(result, summary)
    _kpi_row(summary)

    st.markdown("<br>", unsafe_allow_html=True)

    t1, t2, t3 = st.tabs(["✅ 이번 주 플랜", "🔔 알림", "🔍 상세"])

    with t1:
        _plan_section(result, key_prefix)

    with t2:
        _alerts_section(result.get("alerts") or [])

    with t3:
        _text_block("💰", "수입 추정",    sections.get("income_forecast"))
        _text_block("📊", "지출 진단",    sections.get("expense_vs_income"))
        _text_block("🧬", "소비 패턴",    sections.get("persona"))
        _text_block("⚠️", "위험 신호",    sections.get("risks"))
        _text_block("🧭", "실행 가이드",   sections.get("actions"))
        _text_block("📎", "데이터 한계",   sections.get("limits"))
        with st.expander("근거 JSON", expanded=False):
            st.json(summary)


def render_short_report_mini(
    *,
    result: Dict[str, Any],
    summary: Optional[Dict[str, Any]] = None,
) -> None:
    """홈 위젯용 — 요약 + KPI만"""
    if not isinstance(result, dict) or not result:
        return
    _css()
    _summary_card(result, summary or {})
    _kpi_row(summary or {})