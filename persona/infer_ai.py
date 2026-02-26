from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .types import PersonaResult
from .legacy.benchmarks_kostat_2024q3 import BENCHMARK_2024Q3


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        return int(float(v))
    except Exception:
        return default


def _level_from_income(income: int) -> Tuple[str, int]:
    """
    income을 KOSTAT 분위 소득 기준에 대입해 nearest quintile을 찾고,
    기존 레벨 규칙(L1~L4)을 적용합니다.
    """
    quintile_incomes = {q: int(BENCHMARK_2024Q3["quintiles"][q]["income"]) for q in range(1, 6)}
    if income <= 0:
        nearest_q = 3
    else:
        nearest_q = min(quintile_incomes.keys(), key=lambda q: abs(quintile_incomes[q] - income))

    eq = float(nearest_q)
    if eq <= 2.0:
        return "L1", nearest_q
    if eq <= 3.0:
        return "L2", nearest_q
    if eq <= 4.0:
        return "L3", nearest_q
    return "L4", nearest_q


def _cat_hit(categories: List[str], keywords: List[str]) -> float:
    if not categories:
        return 0.0
    joined = " ".join([str(c) for c in categories])
    return 1.0 if any(k in joined for k in keywords) else 0.0


def infer_persona_from_ai_summary(summary: Dict[str, Any]) -> PersonaResult:
    """
    ✅ 메인: AI summary(JSON) 기반 페르소나 산정
    반환: PersonaResult(persona_key, estimated_income, signals)
    """
    inc = summary.get("income", {}) if isinstance(summary.get("income"), dict) else {}
    exp = summary.get("expense", {}) if isinstance(summary.get("expense"), dict) else {}

    income = _safe_int(inc.get("expected_income_next_month"), default=0)
    level, nearest_q = _level_from_income(income)

    # signals(요약 지표)
    spend_ratio = _safe_float(exp.get("spend_ratio"))
    late_ratio = _safe_float(exp.get("late_ratio"))
    small_tx_ratio = _safe_float(exp.get("small_tx_ratio"))
    easy_pay_ratio = _safe_float(exp.get("easy_pay_ratio"))
    fixed_cost_ratio = _safe_float(exp.get("fixed_cost_ratio_est"))

    top5 = exp.get("top_categories_top5", {})
    top_cats = list(top5.keys()) if isinstance(top5, dict) else []

    emotional_hit = _cat_hit(top_cats, ["카페", "커피", "디저트", "문화", "여가", "여행", "오락", "취미"])
    impulse_hit = _cat_hit(top_cats, ["쇼핑", "패션", "뷰티", "온라인", "배달"])
    stable_hit = _cat_hit(top_cats, ["주거", "공과금", "관리비", "통신", "생필품", "생활", "정기"])
    strategic_hit = _cat_hit(top_cats, ["교육", "보험", "저축", "투자"])

    # 스타일 스코어(가볍게 튜닝 가능)
    impulse_score = (easy_pay_ratio * 0.6) + (late_ratio * 0.4) + (impulse_hit * 0.7) + max(0.0, spend_ratio - 0.75)
    emotional_score = (small_tx_ratio * 0.4) + (emotional_hit * 0.9) + (late_ratio * 0.2)
    stable_score = (fixed_cost_ratio * 0.8) + (stable_hit * 0.6) + max(0.0, 0.65 - spend_ratio) * 0.2
    strategic_score = (strategic_hit * 0.7) + max(0.0, 0.7 - spend_ratio) * 0.8 + max(0.0, 0.5 - late_ratio) * 0.3

    style_scores = {
        "impulse": float(impulse_score),
        "emotional": float(emotional_score),
        "stable": float(stable_score),
        "strategic": float(strategic_score),
    }
    style = max(style_scores, key=style_scores.get)

    persona_key = f"{level}_{style}"

    # income fallback: 0이면 nearest_q 소득으로 대체
    if income <= 0:
        income = int(BENCHMARK_2024Q3["quintiles"][nearest_q]["income"])

    return PersonaResult(
        persona_key=persona_key,
        estimated_income=income,
        signals={
            "nearest_quintile": float(nearest_q),
            "spend_ratio": spend_ratio,
            "late_ratio": late_ratio,
            "small_tx_ratio": small_tx_ratio,
            "easy_pay_ratio": easy_pay_ratio,
            "fixed_cost_ratio_est": fixed_cost_ratio,
            "impulse_score": style_scores["impulse"],
            "emotional_score": style_scores["emotional"],
            "stable_score": style_scores["stable"],
            "strategic_score": style_scores["strategic"],
        }
    )