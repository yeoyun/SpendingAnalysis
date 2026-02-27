# ai_report/export.py
"""
AI 리포트 페이지 전체 → Markdown 내보내기

페이지 순서 (streamlit_app.py 기준):
  1. 헤더 (기간)
  2. 페르소나 카드
  3. 전체 기간 리포트 (all)
  4. 단기(최근 30일) 리포트 (short)

사용:
    from ai_report.export import build_md_bytes, build_md_filename

    md_bytes = build_md_bytes(
        start_date=start_date,
        end_date=end_date,
        persona_result=persona_result,
        result_all=st.session_state["ai_report_result_all"],
        summary_all=st.session_state["ai_report_summary_all"],
        result_short=st.session_state["ai_report_result_short"],
        summary_short=st.session_state["ai_report_summary_short"],
    )
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────────────────────
# 포맷 헬퍼
# ──────────────────────────────────────────────────────────────

def _s(v) -> str:
    return str(v).strip() if v is not None else ""

def _won(v) -> str:
    if not isinstance(v, (int, float)):
        return "—"
    return f"{v:,.0f}원"

def _won_signed(v) -> str:
    if not isinstance(v, (int, float)):
        return "—"
    return ("+" if v >= 0 else "−") + f"{abs(v):,.0f}원"

def _pct(v, signed=False) -> str:
    if not isinstance(v, (int, float)):
        return "—"
    s = f"{abs(v * 100):.1f}%"
    return (("+" if v >= 0 else "−") + s) if signed else s

def _lst(v) -> list:
    return v if isinstance(v, list) else []

def _dct(v) -> dict:
    return v if isinstance(v, dict) else {}

def _hr() -> str:
    return "\n\n---\n"

def _h2(t: str) -> str:
    return f"\n## {t}\n"

def _h3(t: str) -> str:
    return f"\n### {t}\n"

def _h4(t: str) -> str:
    return f"\n#### {t}\n"

def _p(text: str) -> str:
    t = _s(text)
    return ("\n" + t + "\n") if t else ""

def _table(headers: List[str], rows: List[List[str]]) -> str:
    if not rows:
        return ""
    sep  = "|".join(["---"] * len(headers))
    head = " | ".join(headers)
    lines = [f"| {head} |", f"| {sep} |"]
    for row in rows:
        cell = " | ".join(
            _s(c).replace("|", "\\|").replace("\n", " ")[:300]
            for c in row
        )
        lines.append(f"| {cell} |")
    return "\n" + "\n".join(lines) + "\n"


def _img_md_from_path(path: str, alt: str = "persona", width_px: int = 140) -> str:
    """
    이미지 파일을 base64로 인라인해 Markdown/HTML로 반환
    - Markdown 표준 ![]() 는 width 조절이 어려워서 <img> 태그 사용
    """
    if not path:
        return ""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return ""

    ext = p.suffix.lower().lstrip(".")
    mime = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif": "image/gif",
    }.get(ext, "image/png")

    b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
    return f'<img src="data:{mime};base64,{b64}" alt="{alt}" width="{int(width_px)}" />'


# ──────────────────────────────────────────────────────────────
# 판정
# ──────────────────────────────────────────────────────────────

def _extract_judgement(result: Dict, summary: Dict) -> Optional[str]:
    text = " ".join([
        _s(_dct(summary.get("expense")).get("spend_judgement")),
        " ".join(_s(x) for x in _lst(result.get("three_lines"))),
    ]).lower()
    for kw, label in [("정상","정상"),("주의","주의"),("경고","경고"),
                      ("ok","정상"),("warn","주의"),("danger","경고")]:
        if kw in text:
            return label
    return None

_J_ICON = {"정상":"🟢","주의":"🟡","경고":"🔴"}


# ──────────────────────────────────────────────────────────────
# 개별 섹션 MD 생성
# ──────────────────────────────────────────────────────────────

def _md_page_header(*, exported_at: str, start_date, end_date, mode_label: str) -> str:
    def _fmt(d) -> str:
        if d is None:
            return "—"
        try:
            return d.strftime("%Y-%m-%d")
        except Exception:
            return _s(d)

    return (
        "# 🧠 AI 소비 분석 리포트\n\n"
        f"> **생성일시:** {exported_at}  \n"
        f"> **분석 기간:** {_fmt(start_date)} ~ {_fmt(end_date)}  \n"
        f"> **리포트 유형:** {mode_label}\n"
    )


def _md_persona(persona_result: Optional[Dict]) -> str:
    """
    persona 모듈 결과를 MD로 변환.
    이미지가 있으면 base64로 인라인해 함께 출력.
    """
    if not isinstance(persona_result, dict) or not persona_result:
        return ""

    # ✅ 이름/설명/특성
    name = (
        _s(persona_result.get("name"))
        or _s(persona_result.get("label"))
        or _s(persona_result.get("persona_type"))
        or _s(persona_result.get("type"))
        or "—"
    )
    desc = (
        _s(persona_result.get("description"))
        or _s(persona_result.get("summary"))
        or ""
    )
    traits = _lst(
        persona_result.get("traits")
        or persona_result.get("keywords")
        or persona_result.get("characteristics")
        or []
    )

    # ✅ 이미지 경로 후보 키들 (프로젝트에 맞게 필요하면 더 추가)
    img_path = (
        _s(persona_result.get("image_path"))
        or _s(persona_result.get("image"))
        or _s(persona_result.get("img_path"))
        or _s(persona_result.get("path"))
    )

    img_md = _img_md_from_path(img_path, alt=name, width_px=150) if img_path else ""

    parts = [_h2("🧬 소비 페르소나")]

    # 이미지 + 기본 정보: 보기 좋게 표 형태로
    if img_md:
        parts.append(
            _table(
                ["항목", "내용"],
                [
                    ["이미지", img_md],
                    ["유형", f"**{name}**"],
                ],
            )
        )
    else:
        parts.append(f"**유형:** {name}\n")

    if desc:
        parts.append(_p(desc))

    if traits:
        bullet = "\n".join(f"- {_s(t)}" for t in traits if _s(t))
        parts.append("\n**특성:**\n" + bullet + "\n")

    # 그 외 미처리 문자열 필드
    skip = {
        "name","label","persona_type","type","description","summary",
        "traits","keywords","characteristics",
        "image_path","image","img_path","path",
    }
    extras = [
        (k, _s(v)) for k, v in persona_result.items()
        if k not in skip and isinstance(v, str) and _s(v)
    ]
    if extras:
        parts.append(_table(["항목","내용"], [[k, v] for k, v in extras]))

    return "\n".join(parts)


def _md_three_lines(result: Dict, summary: Dict) -> str:
    three = _lst(result.get("three_lines"))
    if not three:
        return ""
    j     = _extract_judgement(result, summary)
    badge = f"{_J_ICON.get(j,'⚪')} **소비 상태: {j}**\n\n" if j else ""
    labels = ["📊 요약", "⚠️ 문제", "🎯 액션"]
    rows = [[labels[i] if i < len(labels) else f"Line{i+1}", _s(line)]
            for i, line in enumerate(three[:3])]
    return badge + _table(["구분","내용"], rows)


def _md_period_kpi(summary: Dict) -> str:
    period  = _dct(summary.get("period"))
    expense = _dct(summary.get("expense"))
    income  = _dct(summary.get("income"))

    rows = [
        ["분석 기간",          f"{period.get('start','—')} ~ {period.get('end','—')}"],
        ["총 지출",            _won(expense.get("total_expense"))],
        ["월 평균 지출",       _won(expense.get("avg_monthly_expense"))],
        ["일 평균 지출",       _won(expense.get("avg_daily_expense"))],
        ["추정 수입(다음달)",  _won(income.get("expected_income_next_month"))],
        ["수입 추정 범위",     " ~ ".join([
                                  _won(v) for v in _lst(income.get("expected_income_range"))
                                  if isinstance(v,(int,float))
                              ]) or "—"],
        ["지출/수입 비율",     _pct(expense.get("spend_ratio"))],
        ["소비 판정",          _s(expense.get("spend_judgement")) or "—"],
        ["수입 추정 신뢰도",   _s(income.get("confidence")) or "—"],
    ]
    return _table(["항목","값"], rows)


def _md_category_top(summary: Dict) -> str:
    expense = _dct(summary.get("expense"))
    top = expense.get("top_categories_top5") or expense.get("top_categories") or {}

    if isinstance(top, dict):
        items = sorted(top.items(), key=lambda x: x[1] if isinstance(x[1],(int,float)) else 0, reverse=True)[:8]
    elif isinstance(top, list):
        items = [(_s(d.get("category") or d.get("name","?")),
                  d.get("amount") or d.get("total", 0)) for d in top[:8]]
    else:
        return ""

    if not items:
        return ""

    total = sum(v for _, v in items if isinstance(v,(int,float)))
    rows = []
    for cat, amt in items:
        share = f"{amt/total*100:.1f}%" if total > 0 and isinstance(amt,(int,float)) else "—"
        rows.append([_s(cat), _won(amt), share])

    return _h4("🏷 지출 상위 카테고리") + _table(["카테고리","금액","비중"], rows)


def _md_fixed_costs(summary: Dict) -> str:
    expense = _dct(summary.get("expense"))
    fixed   = expense.get("fixed_candidates")
    if not isinstance(fixed, dict) or not fixed:
        return ""

    rows = [[_s(k), _won(v)] for k, v in list(fixed.items())[:10]]
    total = expense.get("fixed_cost_est_monthly")
    if isinstance(total, (int, float)):
        rows.append([f"**합계 (월 추정)**", f"**{_won(total)}**"])

    return _h4("🔒 고정비 추정 항목") + _table(["항목","월 평균"], rows)


def _md_short_kpi(summary: Dict) -> str:
    stc = _dct(summary.get("short_term_compare"))
    if not stc.get("available"):
        return "\n> ℹ️ 단기 비교 데이터가 없습니다.\n"

    cur  = _dct(stc.get("current")).get("total")
    chg  = _dct(stc.get("change"))
    diff = chg.get("diff")
    pct  = chg.get("pct")
    wd   = chg.get("weekday_diff")
    we   = chg.get("weekend_diff")
    base = _dct(stc.get("baseline"))
    used = base.get("used","—")
    conf = base.get("confidence","—")
    base_total = base.get("total_for_window")
    window = _dct(stc.get("window"))

    base_label = {
        "previous_window":                "전 30일",
        "recent_full_months_daily_median":"최근 월평균(일환산)",
        "overall_daily_median":           "전체 일평균",
    }.get(used, _s(used))

    rows = [
        ["분석 기간",  f"{window.get('start','—')} ~ {window.get('end','—')}"],
        ["30일 지출",  _won(cur)],
        ["비교 기준",  f"{base_label} ({_won(base_total)})"],
        ["증감(원)",   _won_signed(diff)],
        ["증감(%)",    _pct(pct, signed=True)],
        ["평일 증감",  _won_signed(wd) if isinstance(wd,(int,float)) else "—"],
        ["주말 증감",  _won_signed(we) if isinstance(we,(int,float)) else "—"],
        ["비교 신뢰도",_s(conf)],
    ]
    return _table(["항목","값"], rows)


def _md_short_cat_delta(summary: Dict) -> str:
    stc    = _dct(summary.get("short_term_compare"))
    deltas = _lst(stc.get("category_deltas_top"))
    if not deltas:
        return ""

    rows = []
    for d in deltas:
        cat     = _s(d.get("category_lv1","—"))
        cur     = _won(d.get("current"))
        diff    = _won_signed(d.get("diff")) if isinstance(d.get("diff"),(int,float)) else "—"
        pct_v   = _pct(d.get("pct"), signed=True) if isinstance(d.get("pct"),(int,float)) else "—"
        reliable= "✓" if d.get("baseline_reliable") else "—"
        rows.append([cat, cur, diff, pct_v, reliable])

    return _h4("📊 카테고리별 변화") + _table(["카테고리","현재","증감(원)","증감(%)","신뢰"], rows)


_SECTION_TITLE = {
    "income_forecast":   "💰 수입 추정",
    "expense_vs_income": "📊 지출 진단",
    "persona":           "🧬 소비 패턴",
    "risks":             "⚠️ 위험 신호",
    "actions":           "🧭 실행 가이드",
    "limits":            "📎 데이터 한계",
}
_SECTION_ORDER_ALL   = ["income_forecast","expense_vs_income","persona","risks","actions","limits"]
_SECTION_ORDER_SHORT = ["income_forecast","expense_vs_income","persona","risks","actions","limits"]

def _md_sections(sections: Dict, order: Optional[List[str]] = None) -> str:
    parts = []
    for key in (order or _SECTION_ORDER_ALL):
        text = _s(sections.get(key))
        if text:
            parts.append(_h3(_SECTION_TITLE.get(key, key)))
            parts.append(_p(text))
    return "\n".join(parts)


_ALERT_ICONS = ["🔴","🟠","🟡","🟢","🔵"]

def _md_alerts(alerts: List[Dict]) -> str:
    if not alerts:
        return "\n> 감지된 알림이 없습니다.\n"
    rows = []
    for i, a in enumerate(alerts[:5]):
        rule = _s(a.get("rule","")) or f"알림 {i+1}"
        ev   = _s(a.get("evidence","")).replace("\n"," ")[:200]
        rec  = _s(a.get("recommendation","")).replace("\n"," ")[:200]
        rows.append([f"{_ALERT_ICONS[i]} {rule}", ev, rec])
    return _table(["알림","근거","권장 행동"], rows)


def _md_action_plan(plan: List[Dict]) -> str:
    if not plan:
        return "\n> 실행 플랜이 없습니다.\n"

    weekday = [p for p in plan if "[평일]" in _s(p.get("title",""))]
    weekend = [p for p in plan if "[주말]" in _s(p.get("title",""))]
    other   = [p for p in plan
               if "[평일]" not in _s(p.get("title",""))
               and "[주말]" not in _s(p.get("title",""))]

    def _group(items: List[Dict], label: str) -> str:
        if not items:
            return ""
        out = [_h4(label)]
        for i, p in enumerate(items, 1):
            title  = (_s(p.get("title",""))
                      .replace("[평일]","").replace("[주말]","").strip()) or f"항목 {i}"
            how    = _s(p.get("how",""))
            why    = _s(p.get("why",""))
            metric = _s(p.get("metric",""))

            out.append(f"**{i}. {title}**\n")
            if how:    out.append(f"- 📌 **실행 방법:** {how}")
            if why:    out.append(f"- 💬 **근거:** {why}")
            if metric: out.append(f"- 🎯 **주간 KPI:** {metric}")
            out.append("")
        return "\n".join(out)

    return (
        _group(weekday, "📅 평일 (월~금)")
        + _group(weekend, "🌿 주말 (토~일)")
        + _group(other,   "🧩 기타")
    )


# ──────────────────────────────────────────────────────────────
# 리포트별 조립
# ──────────────────────────────────────────────────────────────

def _md_long_report(result: Dict, summary: Dict) -> str:
    sections = _dct(result.get("sections"))
    plan     = _lst(result.get("action_plan"))
    alerts   = _lst(result.get("alerts"))

    return "\n".join([
        _h2("📋 전체 기간 리포트"),

        _h3("📌 3줄 요약"),
        _md_three_lines(result, summary),

        _h3("📈 핵심 지표"),
        _md_period_kpi(summary),
        _md_category_top(summary),
        _md_fixed_costs(summary),

        _hr(),
        _h2("🔍 상세 분석"),
        _md_sections(sections, _SECTION_ORDER_ALL),

        _hr(),
        _h2("✅ 실행 플랜"),
        _md_action_plan(plan),

        _hr(),
        _h2("🔔 알림"),
        _md_alerts(alerts),
    ])


def _md_short_report(result: Dict, summary: Dict) -> str:
    sections = _dct(result.get("sections"))
    plan     = _lst(result.get("action_plan"))
    alerts   = _lst(result.get("alerts"))

    return "\n".join([
        _h2("📋 단기(최근 30일) 리포트"),

        _h3("📌 3줄 요약"),
        _md_three_lines(result, summary),

        _h3("📈 30일 지출 현황"),
        _md_short_kpi(summary),
        _md_short_cat_delta(summary),

        _hr(),
        _h2("✅ 이번 주 실행 플랜"),
        _md_action_plan(plan),

        _hr(),
        _h2("🔔 알림"),
        _md_alerts(alerts),

        _hr(),
        _h2("🔍 상세 분석"),
        _md_sections(sections, _SECTION_ORDER_SHORT),
    ])


# ──────────────────────────────────────────────────────────────
# ✅ 공개 API
# ──────────────────────────────────────────────────────────────

def build_md_report(
    *,
    start_date=None,
    end_date=None,
    persona_result:  Optional[Dict[str, Any]] = None,
    result_all:      Optional[Dict[str, Any]] = None,
    summary_all:     Optional[Dict[str, Any]] = None,
    result_short:    Optional[Dict[str, Any]] = None,
    summary_short:   Optional[Dict[str, Any]] = None,
) -> str:
    """
    AI 리포트 페이지 전체를 단일 Markdown 문자열로 반환.

    Parameters
    ----------
    start_date, end_date : pd.Timestamp | str | None
        분석 기간. None이면 summary_all["period"]에서 자동 추출.
    persona_result : dict | None
        persona 모듈이 반환한 결과 dict.
    result_all / summary_all : dict | None
        전체 기간 리포트.
    result_short / summary_short : dict | None
        단기(최근 30일) 리포트.
    """
    has_all   = isinstance(result_all,   dict) and bool(result_all)
    has_short = isinstance(result_short, dict) and bool(result_short)

    if not has_all and not has_short:
        return "# AI 리포트\n\n> 생성된 리포트가 없습니다.\n"

    # 기간 자동 fallback
    if start_date is None or end_date is None:
        ref = (_dct(_dct(summary_all).get("period"))
               or _dct(_dct(summary_short).get("period")))
        if start_date is None:
            start_date = ref.get("start")
        if end_date is None:
            end_date = ref.get("end")

    mode_label = (
        "전체 기간 + 단기(최근 30일)" if (has_all and has_short)
        else ("전체 기간" if has_all else "단기(최근 30일)")
    )
    exported_at = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")

    parts: List[str] = [
        _md_page_header(
            exported_at=exported_at,
            start_date=start_date,
            end_date=end_date,
            mode_label=mode_label,
        )
    ]

    persona_md = _md_persona(persona_result)
    if persona_md:
        parts += [_hr(), persona_md]

    if has_all:
        parts += [_hr(), _md_long_report(
            result_all,
            summary_all if isinstance(summary_all, dict) else {},
        )]

    if has_short:
        parts += [_hr(), _md_short_report(
            result_short,
            summary_short if isinstance(summary_short, dict) else {},
        )]

    parts.append(
        "\n\n---\n\n"
        "> *본 리포트는 AI가 자동 생성한 참고용 분석입니다.  \n"
        "> 투자·대출·세무 등 고위험 금융 결정의 근거로 사용하지 마세요.*\n"
    )

    return "\n".join(parts)


def build_md_bytes(
    *,
    start_date=None,
    end_date=None,
    persona_result:  Optional[Dict[str, Any]] = None,
    result_all:      Optional[Dict[str, Any]] = None,
    summary_all:     Optional[Dict[str, Any]] = None,
    result_short:    Optional[Dict[str, Any]] = None,
    summary_short:   Optional[Dict[str, Any]] = None,
) -> bytes:
    """build_md_report() → UTF-8 bytes. st.download_button(data=...) 에 바로 전달."""
    return build_md_report(
        start_date=start_date,
        end_date=end_date,
        persona_result=persona_result,
        result_all=result_all,
        summary_all=summary_all,
        result_short=result_short,
        summary_short=summary_short,
    ).encode("utf-8")


def build_md_filename() -> str:
    """다운로드 파일명 자동 생성."""
    return f"ai_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md"