from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, List, Any, Optional
import math

import numpy as np
import pandas as pd

from .benchmarks_kostat_2024q3 import BENCHMARK_2024Q3, COICOP_CATEGORIES
from .mapping import map_to_coicop


@dataclass
class PersonaResult:
    persona_key: str
    estimated_income: int                 # 원
    quintile_probs: Dict[int, float]      # 1~5
    expected_quintile: float              # 1.0~5.0
    signals: Dict[str, float]             # 해석에 쓰는 점수들
    category_share: Dict[str, float]      # coicop shares (0~1)


def _softmax(x: np.ndarray) -> np.ndarray:
    x = x - np.max(x)
    ex = np.exp(x)
    return ex / np.sum(ex)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def build_user_coicop_share(
    df: pd.DataFrame,
    *,
    amount_col: str = "amount",
    type_col: str = "type",
    category_col: str = "category_lv1",
) -> Dict[str, float]:
    if df is None or df.empty:
        return {c: 0.0 for c in COICOP_CATEGORIES}

    tmp = df.copy()

    if type_col in tmp.columns:
        exp = tmp[tmp[type_col].astype(str).str.contains("지출", na=False)]
    else:
        exp = tmp

    if amount_col in exp.columns:
        exp = exp[pd.to_numeric(exp[amount_col], errors="coerce").fillna(0) < 0]

    if exp.empty:
        return {c: 0.0 for c in COICOP_CATEGORIES}

    exp = exp.copy()
    exp["coicop"] = exp[category_col].astype(str).apply(map_to_coicop)
    exp["abs_amount"] = pd.to_numeric(exp[amount_col], errors="coerce").abs().fillna(0)

    agg = exp.groupby("coicop")["abs_amount"].sum().to_dict()
    total = float(sum(agg.values())) if agg else 0.0
    if total <= 0:
        return {c: 0.0 for c in COICOP_CATEGORIES}

    shares = {c: float(agg.get(c, 0.0)) / total for c in COICOP_CATEGORIES}
    return shares


def _benchmark_share_by_quintile() -> Dict[int, Dict[str, float]]:
    out: Dict[int, Dict[str, float]] = {}
    for q, info in BENCHMARK_2024Q3["quintiles"].items():
        total = float(info["consumption_total"])
        cats = info["categories"]
        out[q] = {c: float(cats[c]) / total for c in COICOP_CATEGORIES}
    return out


def infer_income_and_persona(df: pd.DataFrame) -> PersonaResult:
    """
    (기존 로직 유지)
    """
    user_share = build_user_coicop_share(df)
    user_vec = np.array([user_share[c] for c in COICOP_CATEGORIES], dtype=float)

    bench_share = _benchmark_share_by_quintile()
    sims: List[float] = []
    for q in range(1, 6):
        bvec = np.array([bench_share[q][c] for c in COICOP_CATEGORIES], dtype=float)
        sims.append(_cosine_similarity(user_vec, bvec))

    sims_arr = np.array(sims, dtype=float)
    probs_arr = _softmax(sims_arr * 10.0)
    quintile_probs = {q: float(probs_arr[q - 1]) for q in range(1, 6)}
    expected_quintile = float(sum(q * quintile_probs[q] for q in range(1, 6)))

    estimated_income = int(
        sum(quintile_probs[q] * BENCHMARK_2024Q3["quintiles"][q]["income"] for q in range(1, 6))
    )

    # 간단 변동성(기존)
    volatility_cv = 0.0
    if df is not None and not df.empty:
        tmp = df.copy()
        if "year_month" not in tmp.columns and "date" in tmp.columns:
            d = pd.to_datetime(tmp["date"], errors="coerce")
            tmp["year_month"] = d.dt.to_period("M").astype(str)

        if "year_month" in tmp.columns and "amount" in tmp.columns:
            exp = tmp[tmp.get("type", "").astype(str).str.contains("지출", na=False)].copy()
            exp = exp[pd.to_numeric(exp["amount"], errors="coerce").fillna(0) < 0]
            if not exp.empty:
                exp["abs_amount"] = pd.to_numeric(exp["amount"], errors="coerce").abs().fillna(0)
                m = exp.groupby("year_month")["abs_amount"].sum()
                if len(m) >= 2:
                    mean = float(m.mean())
                    std = float(m.std(ddof=0))
                    volatility_cv = (std / mean) if mean > 0 else 0.0

    nearest_q = int(round(expected_quintile))
    nearest_q = min(max(nearest_q, 1), 5)

    def delta(cat: str) -> float:
        return float(user_share.get(cat, 0.0) - _benchmark_share_by_quintile()[nearest_q].get(cat, 0.0))

    impulse_signal = max(0.0, delta("clothing_footwear")) + max(0.0, delta("other_goods_services"))
    emotional_signal = max(0.0, delta("recreation_culture")) + max(0.0, delta("restaurants_hotels"))
    stable_signal = max(0.0, delta("housing_utilities")) + max(0.0, delta("food_non_alcoholic")) + max(0.0, delta("communication"))
    apc = float(BENCHMARK_2024Q3["quintiles"][nearest_q]["avg_propensity_to_consume"])
    savings_hint = max(0.0, (100.0 - apc) / 100.0)
    strategic_signal = max(0.0, (0.25 - volatility_cv)) + savings_hint * 0.5

    style_scores = {
        "impulse": impulse_signal,
        "emotional": emotional_signal,
        "stable": stable_signal,
        "strategic": strategic_signal,
    }
    style = max(style_scores, key=style_scores.get)

    if expected_quintile <= 2.0:
        level = "L1"
    elif expected_quintile <= 3.0:
        level = "L2"
    elif expected_quintile <= 4.0:
        level = "L3"
    else:
        level = "L4"

    persona_key = f"{level}_{style}"

    signals = {
        "expected_quintile": expected_quintile,
        "nearest_quintile": float(nearest_q),
        "volatility_cv": float(volatility_cv),
        "impulse_signal": float(impulse_signal),
        "emotional_signal": float(emotional_signal),
        "stable_signal": float(stable_signal),
        "strategic_signal": float(strategic_signal),
        "avg_propensity_to_consume_nearest_q": float(apc),
    }

    return PersonaResult(
        persona_key=persona_key,
        estimated_income=estimated_income,
        quintile_probs=quintile_probs,
        expected_quintile=expected_quintile,
        signals=signals,
        category_share=user_share,
    )


# =========================================================
# ✅ NEW: AI summary(JSON) 기반 페르소나 산정
# =========================================================
def infer_persona_from_ai_summary(summary: Dict[str, Any]) -> PersonaResult:
    """
    AI 리포트의 근거 summary(JSON)를 기반으로 페르소나를 산정합니다.

    - income: summary["income"]["expected_income_next_month"] 우선
    - level: 예상 소득을 분위 벤치마크 소득과 비교해서 nearest quintile 추정 후 L1~L4
    - style: summary["expense"]의 proxies(소비율/야간/소액/간편결제/고정비 비중 + top category 힌트)로 산정
    """
    income = 0
    exp = {}

    if isinstance(summary, dict):
        inc = summary.get("income", {})
        if isinstance(inc, dict):
            v = inc.get("expected_income_next_month")
            try:
                if v is not None:
                    income = int(float(v))
            except Exception:
                income = 0

        exp = summary.get("expense", {}) if isinstance(summary.get("expense"), dict) else {}

    # 1) 분위 추정(가장 가까운 소득 분위)
    quintile_incomes = {q: int(BENCHMARK_2024Q3["quintiles"][q]["income"]) for q in range(1, 6)}
    if income <= 0:
        nearest_q = 3
    else:
        nearest_q = min(quintile_incomes.keys(), key=lambda q: abs(quintile_incomes[q] - income))

    expected_quintile = float(nearest_q)
    quintile_probs = {q: (1.0 if q == nearest_q else 0.0) for q in range(1, 6)}

    # 2) 레벨(L1~L4)
    if expected_quintile <= 2.0:
        level = "L1"
    elif expected_quintile <= 3.0:
        level = "L2"
    elif expected_quintile <= 4.0:
        level = "L3"
    else:
        level = "L4"

    # 3) style 계산용 시그널
    spend_ratio = float(exp.get("spend_ratio") or 0.0)
    late_ratio = float(exp.get("late_ratio") or 0.0)
    small_tx_ratio = float(exp.get("small_tx_ratio") or 0.0)
    easy_pay_ratio = float(exp.get("easy_pay_ratio") or 0.0) if exp.get("easy_pay_ratio") is not None else 0.0
    fixed_cost_ratio = float(exp.get("fixed_cost_ratio_est") or 0.0)

    top5 = exp.get("top_categories_top5", {})
    top_cats = list(top5.keys()) if isinstance(top5, dict) else []

    # top category 힌트(간단 키워드 기반)
    def _cat_hit(keys: List[str], keywords: List[str]) -> float:
        if not keys:
            return 0.0
        joined = " ".join([str(k) for k in keys])
        return 1.0 if any(kw in joined for kw in keywords) else 0.0

    emotional_hit = _cat_hit(top_cats, ["카페", "커피", "디저트", "문화", "여가", "여행", "오락", "취미"])
    impulse_hit = _cat_hit(top_cats, ["쇼핑", "패션", "뷰티", "온라인쇼핑"])
    stable_hit = _cat_hit(top_cats, ["주거", "공과금", "관리비", "통신", "생필품", "생활"])
    strategic_hit = _cat_hit(top_cats, ["교육", "저축", "보험", "투자"])

    # style score (가볍게 튜닝 가능)
    impulse_score = (easy_pay_ratio * 0.6) + (late_ratio * 0.4) + (impulse_hit * 0.6) + max(0.0, spend_ratio - 0.75)
    emotional_score = (small_tx_ratio * 0.4) + (emotional_hit * 0.8) + (late_ratio * 0.2)
    stable_score = (fixed_cost_ratio * 0.8) + (stable_hit * 0.6) + max(0.0, 0.6 - spend_ratio) * 0.2
    strategic_score = (strategic_hit * 0.7) + max(0.0, 0.7 - spend_ratio) * 0.8 + max(0.0, 0.5 - late_ratio) * 0.3

    style_scores = {
        "impulse": float(impulse_score),
        "emotional": float(emotional_score),
        "stable": float(stable_score),
        "strategic": float(strategic_score),
    }
    style = max(style_scores, key=style_scores.get)

    persona_key = f"{level}_{style}"

    signals = {
        "expected_quintile": expected_quintile,
        "nearest_quintile": float(nearest_q),
        "spend_ratio": float(spend_ratio),
        "late_ratio": float(late_ratio),
        "small_tx_ratio": float(small_tx_ratio),
        "easy_pay_ratio": float(easy_pay_ratio),
        "fixed_cost_ratio_est": float(fixed_cost_ratio),
        "impulse_score": style_scores["impulse"],
        "emotional_score": style_scores["emotional"],
        "stable_score": style_scores["stable"],
        "strategic_score": style_scores["strategic"],
    }

    # category_share는 AI summary만으로는 coicop share를 완벽히 재구성하기 어려워서 0벡터로 둡니다.
    category_share = {c: 0.0 for c in COICOP_CATEGORIES}

    return PersonaResult(
        persona_key=persona_key,
        estimated_income=int(income) if income > 0 else quintile_incomes.get(nearest_q, 0),
        quintile_probs=quintile_probs,
        expected_quintile=expected_quintile,
        signals=signals,
        category_share=category_share,
    )