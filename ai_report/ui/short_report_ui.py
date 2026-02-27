# ai_report/ui/short_report_ui.py
"""
단기 소비 리포트 UI — 액션 카드 중심 리디자인
순서: 액션 플랜 → 알림 → KPI → 3줄 요약 → 상세
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import streamlit as st


# ──────────────────────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────────────────────
_CSS = """
<style>
:root {
  --c-bg:       #FFFFFF;
  --c-surface:  #F8F9FB;
  --c-border:   #E5E7EB;
  --c-text:     #111827;
  --c-muted:    #6B7280;
  --c-faint:    #9CA3AF;
  --c-blue:     #2563EB;
  --c-blue-bg:  #EFF6FF;
  --c-green:    #059669;
  --c-green-bg: #ECFDF5;
  --c-amber:    #D97706;
  --c-amber-bg: #FFFBEB;
  --c-red:      #DC2626;
  --shadow-sm:  0 1px 3px rgba(0,0,0,.06), 0 2px 8px rgba(0,0,0,.04);
}

/* ── 액션 카드 ── */
.sr-action-card {
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: 16px;
  padding: 28px 30px 26px 30px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-sm);
  position: relative;
  overflow: hidden;
}
.sr-action-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0;
  width: 4px; height: 100%;
  border-radius: 16px 0 0 16px;
}
.sr-action-wd::before { background: var(--c-blue); }
.sr-action-we::before { background: var(--c-green); }
.sr-action-ot::before { background: var(--c-amber); }

.sr-action-tag {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  padding: 4px 11px; border-radius: 999px; margin-bottom: 14px;
  border: 1px solid;
}
.sr-action-tag-wd { background: var(--c-blue-bg);  color: var(--c-blue);  border-color: #BFDBFE; }
.sr-action-tag-we { background: var(--c-green-bg); color: var(--c-green); border-color: #6EE7B7; }
.sr-action-tag-ot { background: var(--c-amber-bg); color: var(--c-amber); border-color: #FCD34D; }

.sr-action-title {
  font-size: 19px;
  font-weight: 700;
  color: var(--c-text);
  line-height: 1.4;
  margin-bottom: 18px;
}

.sr-action-divider {
  height: 1px;
  background: var(--c-border);
  margin: 16px 0;
}

.sr-action-row {
  display: flex; align-items: flex-start; gap: 13px;
  padding: 10px 0;
}
.sr-action-row + .sr-action-row {
  border-top: 1px solid var(--c-surface);
}
.sr-action-row-icon { font-size: 17px; min-width: 24px; padding-top: 2px; }
.sr-action-row-label {
  font-size: 11px; font-weight: 700; color: var(--c-faint);
  text-transform: uppercase; letter-spacing: .07em;
  margin-bottom: 5px;
}
.sr-action-row-text { font-size: 14px; color: #374151; line-height: 1.75; }

.sr-metric-pill {
  display: inline-flex; align-items: center; gap: 7px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: 10px;
  padding: 10px 16px;
  font-size: 14px; font-weight: 700; color: var(--c-text);
  margin-top: 14px;
}

/* ── 알림 카드 ── */
.sr-alert {
  display: flex; align-items: flex-start; gap: 14px;
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: 12px;
  padding: 18px 20px;
  margin-bottom: 10px;
  box-shadow: var(--shadow-sm);
}
.sr-alert-dot  { width: 9px; height: 9px; border-radius: 50%; margin-top: 6px; flex-shrink: 0; }
.sr-alert-rule { font-size: 14px; font-weight: 700; color: var(--c-text); margin-bottom: 5px; }
.sr-alert-ev   { font-size: 13px; color: var(--c-muted); margin-bottom: 4px; line-height: 1.65; }
.sr-alert-rec  { font-size: 13px; color: var(--c-blue);  font-weight: 600;  line-height: 1.65; }

/* ── KPI ── */
.sr-kpi-row {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.sr-kpi {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: 12px;
  padding: 18px 20px;
}
.sr-kpi-label { font-size: 10px; font-weight: 700; color: var(--c-faint); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 8px; }
.sr-kpi-val   { font-size: 20px; font-weight: 800; color: var(--c-text); }
.sr-kpi-sub   { font-size: 11px; color: var(--c-muted); margin-top: 4px; }
.kpi-up   { color: var(--c-red); }
.kpi-down { color: var(--c-green); }

/* ── 요약 히어로 ── */
.sr-hero {
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: 16px;
  padding: 26px 30px;
  box-shadow: var(--shadow-sm);
}
.sr-hero-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 13px; border-radius: 999px;
  font-size: 12px; font-weight: 700;
  border: 1px solid; margin-bottom: 16px;
}
.sr-hero-line {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--c-surface);
  font-size: 15px; color: #374151; line-height: 1.8;
}
.sr-hero-line:last-child { border-bottom: none; padding-bottom: 0; }
.sr-hero-icon { min-width: 22px; font-size: 16px; padding-top: 2px; }

/* ── 상세 블록 ── */
.sr-detail-block {
  background: var(--c-surface);
  border-radius: 12px;
  padding: 18px 22px;
  margin-bottom: 10px;
}
.sr-detail-label {
  font-size: 10px; font-weight: 700; color: var(--c-faint);
  text-transform: uppercase; letter-spacing: .08em; margin-bottom: 10px;
}
.sr-detail-text { font-size: 14px; color: #374151; line-height: 1.85; }
</style>
"""

_CSS_INJECTED = False
def _inject_css():
    global _CSS_INJECTED
    if not _CSS_INJECTED:
        st.markdown(_CSS, unsafe_allow_html=True)
        _CSS_INJECTED = True


# ──────────────────────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────────────────────
def _won(v, signed=False):
    if not isinstance(v, (int, float)):
        return "—"
    s = f"{abs(v):,.0f}원"
    return ("+" if v >= 0 else "−") + s if signed else s

def _pct(v, signed=False):
    if not isinstance(v, (int, float)):
        return "—"
    s = f"{abs(v * 100):.1f}%"
    return ("+" if v >= 0 else "−") + s if signed else s

def _judgement(result: Dict, summary: Dict) -> Optional[str]:
    text = " ".join([
        str((summary.get("expense") or {}).get("spend_judgement", "")),
        " ".join(str(x) for x in (result.get("three_lines") or [])),
    ]).lower()
    for kw, label in [("정상","정상"),("주의","주의"),("경고","경고"),
                      ("ok","정상"),("warn","주의"),("danger","경고")]:
        if kw in text:
            return label
    return None

def _badge_html(judgement: Optional[str]) -> str:
    cfg = {
        "정상": ("#ECFDF5","#065F46","#6EE7B7","✓ 정상"),
        "주의": ("#FFFBEB","#92400E","#FCD34D","! 주의"),
        "경고": ("#FFF1F2","#9F1239","#FDA4AF","✗ 경고"),
    }.get(judgement or "")
    if not cfg:
        return ""
    bg, fg, bd, label = cfg
    return (
        f'<span class="sr-hero-badge" '
        f'style="background:{bg};color:{fg};border-color:{bd}">'
        f'{label}</span>'
    )


# ──────────────────────────────────────────────────────────────
# 블록 1 — 액션 카드 (최상단)
# ──────────────────────────────────────────────────────────────
def _action_cards(plan: List[Dict]):
    if not plan:
        st.caption("실행 플랜이 없습니다.")
        return

    weekday = [p for p in plan if "[평일]" in str(p.get("title", ""))]
    weekend = [p for p in plan if "[주말]" in str(p.get("title", ""))]
    other   = [p for p in plan
               if "[평일]" not in str(p.get("title",""))
               and "[주말]" not in str(p.get("title",""))]

    def _card(p: Dict, tag_cls: str, tag_label: str, card_cls: str):
        title  = (str(p.get("title",""))
                  .replace("[평일]","").replace("[주말]","").strip()) or "실행 항목"
        how    = str(p.get("how","")).strip()
        metric = str(p.get("metric","")).strip()
        why    = str(p.get("why","")).strip()

        rows_html = ""
        if how or why:
            rows_html += '<div class="sr-action-divider"></div>'
            if how:
                rows_html += (
                    f'<div class="sr-action-row">'
                    f'<div class="sr-action-row-icon">📌</div>'
                    f'<div style="flex:1"><div class="sr-action-row-label">실행 방법</div>'
                    f'<div class="sr-action-row-text">{how}</div></div>'
                    f'</div>'
                )
            if why:
                rows_html += (
                    f'<div class="sr-action-row">'
                    f'<div class="sr-action-row-icon">💬</div>'
                    f'<div style="flex:1"><div class="sr-action-row-label">근거</div>'
                    f'<div class="sr-action-row-text">{why}</div></div>'
                    f'</div>'
                )

        metric_html = ""
        if metric:
            metric_html = (
                f'<div style="margin-top:16px">'
                f'<div class="sr-metric-pill">🎯 &nbsp;{metric}</div>'
                f'</div>'
            )

        st.markdown(
            f'<div class="sr-action-card {card_cls}">'
            f'<span class="sr-action-tag {tag_cls}">{tag_label}</span>'
            f'<div class="sr-action-title">{title}</div>'
            f'{rows_html}'
            f'{metric_html}'
            f'</div>',
            unsafe_allow_html=True,
        )

    if weekday and weekend:
        col_l, col_r = st.columns(2, gap="medium")
        with col_l:
            for p in weekday:
                _card(p, "sr-action-tag-wd", "📅 평일", "sr-action-wd")
        with col_r:
            for p in weekend:
                _card(p, "sr-action-tag-we", "🌿 주말", "sr-action-we")
    else:
        for p in weekday:
            _card(p, "sr-action-tag-wd", "📅 평일", "sr-action-wd")
        for p in weekend:
            _card(p, "sr-action-tag-we", "🌿 주말", "sr-action-we")

    for p in other:
        _card(p, "sr-action-tag-ot", "🧩 기타", "sr-action-ot")


# ──────────────────────────────────────────────────────────────
# 블록 2 — 알림
# ──────────────────────────────────────────────────────────────
_ALERT_DOTS = ["#DC2626","#EA580C","#CA8A04","#16A34A","#2563EB"]

def _alerts(alerts: List[Dict]):
    if not alerts:
        return
    for i, a in enumerate(alerts[:5]):
        rule = str(a.get("rule", f"알림 {i+1}")).strip()
        ev   = str(a.get("evidence", "")).strip()
        rec  = str(a.get("recommendation", "")).strip()
        ev_html  = f'<div class="sr-alert-ev">📎 &nbsp;{ev}</div>'  if ev  else ""
        rec_html = f'<div class="sr-alert-rec">💡 &nbsp;{rec}</div>' if rec else ""
        st.markdown(
            f'<div class="sr-alert">'
            f'<div class="sr-alert-dot" style="background:{_ALERT_DOTS[i]}"></div>'
            f'<div style="flex:1">'
            f'<div class="sr-alert-rule">{rule}</div>'
            f'{ev_html}{rec_html}'
            f'</div></div>',
            unsafe_allow_html=True,
        )


# ──────────────────────────────────────────────────────────────
# 블록 3 — KPI
# ──────────────────────────────────────────────────────────────
def _kpi(summary: Dict):
    stc = summary.get("short_term_compare") or {}
    if not stc.get("available"):
        return

    cur  = (stc.get("current")  or {}).get("total")
    diff = (stc.get("change")   or {}).get("diff")
    pct  = (stc.get("change")   or {}).get("pct")

    diff_cls = "kpi-up" if isinstance(diff,(int,float)) and diff > 0 else "kpi-down"
    pct_cls  = "kpi-up" if isinstance(pct,(int,float))  and pct  > 0 else "kpi-down"

    base_used = (stc.get("baseline") or {}).get("used","")
    base_label = {
        "previous_window":                  "전 30일 대비",
        "recent_full_months_daily_median":  "최근 월평균 대비",
        "overall_daily_median":             "전체 일평균 대비",
    }.get(base_used, base_used)

    def card(label, val, cls="", sub=""):
        sub_html = f'<div class="sr-kpi-sub">{sub}</div>' if sub else ""
        return (
            f'<div class="sr-kpi">'
            f'<div class="sr-kpi-label">{label}</div>'
            f'<div class="sr-kpi-val {cls}">{val}</div>'
            f'{sub_html}</div>'
        )

    st.markdown(
        '<div class="sr-kpi-row">'
        + card("30일 지출", _won(cur))
        + card("증감", _won(diff, True), diff_cls, base_label)
        + card("변화율", _pct(pct, True), pct_cls)
        + '</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────
# 블록 4 — 3줄 요약 히어로
# ──────────────────────────────────────────────────────────────
def _hero(result: Dict, summary: Dict):
    lines = [str(x).strip() for x in (result.get("three_lines") or []) if str(x).strip()]
    if not lines:
        return

    J = _judgement(result, summary)
    icons = ["📊","⚠️","🎯"]
    rows = "".join(
        f'<div class="sr-hero-line">'
        f'<span class="sr-hero-icon">{icons[i]}</span>'
        f'<span>{l}</span></div>'
        for i, l in enumerate(lines[:3])
    )
    st.markdown(
        f'<div class="sr-hero">{_badge_html(J)}{rows}</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────
# 블록 5 — 상세 텍스트 블록
# ──────────────────────────────────────────────────────────────
def _detail_block(icon: str, label: str, text: Optional[str]):
    if not text or not str(text).strip():
        return
    body = str(text).strip().replace("\n","<br>")
    st.markdown(
        f'<div class="sr-detail-block">'
        f'<div class="sr-detail-label">{icon} {label}</div>'
        f'<div class="sr-detail-text">{body}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────
# ✅ 공개 함수: render_short_report
# ──────────────────────────────────────────────────────────────
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

    _inject_css()
    sections: Dict = result.get("sections") or {}
    plan:     List = result.get("action_plan") or []
    alerts:   List = result.get("alerts") or []

    # ── 1. 액션 카드
    st.markdown("#### 이번 주 실행 플랜")
    _action_cards(plan)

    st.markdown("")

    # ── 2. 알림
    if alerts:
        st.markdown("#### 알림")
        _alerts(alerts)
        st.markdown("")

    # ── 3. KPI
    kpi_ok = (summary.get("short_term_compare") or {}).get("available", False)
    if kpi_ok:
        st.markdown("#### 30일 지출 현황")
        _kpi(summary)
        st.markdown("")

    # ── 4. 3줄 요약
    st.markdown("#### 요약")
    _hero(result, summary)

    st.markdown("")

    # ── 5. 상세 (접힘)
    with st.expander("🔍 상세 분석", expanded=False):
        _detail_block("💰","수입 추정",   sections.get("income_forecast"))
        _detail_block("📊","지출 진단",   sections.get("expense_vs_income"))
        _detail_block("🧬","소비 패턴",   sections.get("persona"))
        _detail_block("⚠️","위험 신호",   sections.get("risks"))
        _detail_block("🧭","실행 가이드", sections.get("actions"))
        _detail_block("📎","데이터 한계", sections.get("limits"))

    with st.expander("근거 JSON", expanded=False):
        st.json(summary)


# ──────────────────────────────────────────────────────────────
# ✅ 공개 함수: render_short_report_mini (홈 위젯용)
# ──────────────────────────────────────────────────────────────
def render_short_report_mini(
    *,
    result: Dict[str, Any],
    summary: Optional[Dict[str, Any]] = None,
) -> None:
    """홈 위젯용 — 요약 + KPI만"""
    if not isinstance(result, dict) or not result:
        return
    _inject_css()
    _hero(result, summary or {})
    _kpi(summary or {})