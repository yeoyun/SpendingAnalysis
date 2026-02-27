from __future__ import annotations

from typing import Dict, Any, Tuple, Optional, List
import pandas as pd
import numpy as np
import re

from .params import AIRuleParams


def _ensure_datetime(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


def _month_key(dt: pd.Series) -> pd.Series:
    return pd.to_datetime(dt).dt.to_period("M").astype(str)


def _get_amount_abs(df: pd.DataFrame) -> pd.Series:
    if "amount_abs" in df.columns:
        return pd.to_numeric(df["amount_abs"], errors="coerce").fillna(0).astype(float)
    if "amount" in df.columns:
        return pd.to_numeric(df["amount"], errors="coerce").fillna(0).abs().astype(float)
    return pd.Series([0.0] * len(df), index=df.index, dtype="float")


def _get_hour(df: pd.DataFrame) -> pd.Series:
    if "hour" in df.columns:
        return pd.to_numeric(df["hour"], errors="coerce")
    return pd.to_datetime(df["date"]).dt.hour


def _normalize_regex_pattern(pattern: str) -> str:
    if not pattern:
        return pattern
    return re.sub(r"\((?!\?)", "(?:", pattern)


def _contains_ratio(series: pd.Series, pattern: str) -> float:
    if series is None or len(series) == 0:
        return 0.0
    pattern = _normalize_regex_pattern(pattern)
    return float(series.astype(str).str.contains(pattern, flags=re.IGNORECASE, regex=True, na=False).mean())


def _days_in_range(start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> int:
    return int((end_ts.normalize() - start_ts.normalize()).days) + 1


def _calc_mom_change(monthly_series: pd.Series) -> Dict[str, Any]:
    if monthly_series is None or len(monthly_series) < 2:
        return {
            "available": False,
            "current_month": None,
            "prev_month": None,
            "current_amount": None,
            "prev_amount": None,
            "change_rate": None,
        }

    s = monthly_series.sort_index()
    cur_m = s.index[-1]
    prev_m = s.index[-2]
    cur_v = float(s.iloc[-1])
    prev_v = float(s.iloc[-2])
    rate = None if prev_v == 0 else (cur_v - prev_v) / prev_v

    return {
        "available": True,
        "current_month": str(cur_m),
        "prev_month": str(prev_m),
        "current_amount": cur_v,
        "prev_amount": prev_v,
        "change_rate": float(rate) if rate is not None else None,
    }


def _format_max_tx(row: pd.Series) -> Dict[str, Any]:
    return {
        "date": str(pd.to_datetime(row.get("date")).date()) if pd.notna(row.get("date")) else None,
        "amount": float(row.get("amount_abs", 0.0)),
        "category_lv1": row.get("category_lv1", None),
        "description": row.get("description", None),
        "payment_method": row.get("payment_method", None),
    }


def _recent_k(series: pd.Series, k: int) -> pd.Series:
    if series is None or len(series) == 0:
        return series
    s = series.sort_index()
    return s.iloc[-k:] if len(s) > k else s


def _estimate_income_from_expense(
    monthly_expense: pd.Series,
    fixed_cost_est_monthly: float,
    params: AIRuleParams,
) -> Dict[str, Any]:
    """
    지출 기반 수입(가처분 소득) 추정:
    - base_expense = 최근 k개월 월지출 대표값(중앙값)
    - income_range = base_expense / (1 - savings_rate)
    - fixed_cost 하한 보정: income >= fixed_cost / fixed_cost_max_ratio
    """
    if monthly_expense is None or len(monthly_expense) == 0:
        return {
            "available": False,
            "base_expense": None,
            "expected_income_next_month": None,
            "expected_income_range": (None, None),
            "confidence": "Low",
            "notes": ["월별 지출 데이터가 부족합니다."],
        }

    recent = _recent_k(monthly_expense, params.expense_recent_k)
    base = float(np.median(recent.values))

    # 저축률 범위로 역산 (저축률이 높을수록 소득은 커짐)
    low = float(params.savings_rate_low)
    high = float(params.savings_rate_high)
    low = min(max(low, 0.0), 0.9)
    high = min(max(high, 0.0), 0.9)
    if high < low:
        low, high = high, low

    # income_low: 저축률 낮게 잡았을 때 (소득이 더 작게 추정)
    income_low = base / (1.0 - low) if (1.0 - low) > 0 else None
    # income_high: 저축률 높게 잡았을 때 (소득이 더 크게 추정)
    income_high = base / (1.0 - high) if (1.0 - high) > 0 else None

    # 고정비 하한 보정
    floor_income = None
    if fixed_cost_est_monthly and fixed_cost_est_monthly > 0 and params.fixed_cost_max_ratio > 0:
        floor_income = fixed_cost_est_monthly / float(params.fixed_cost_max_ratio)
        if income_low is not None:
            income_low = max(income_low, floor_income)
        if income_high is not None:
            income_high = max(income_high, floor_income)

    # 대표값은 범위 중앙(또는 base/(1-중간저축률))
    mid_s = (low + high) / 2.0
    expected = base / (1.0 - mid_s) if (1.0 - mid_s) > 0 else None
    if floor_income is not None and expected is not None:
        expected = max(expected, floor_income)

    # 신뢰도: 최근 k개월 변동성 기반(간단)
    cv = float(np.std(recent.values) / (np.mean(recent.values) + 1e-9))
    if len(recent) >= 3 and cv < 0.25:
        conf = "High"
    elif len(recent) >= 2 and cv < 0.40:
        conf = "Med"
    else:
        conf = "Low"

    notes = [
        f"최근 {len(recent)}개월 월지출 중앙값을 기준으로 추정했습니다.",
        f"저축률 가정 범위: {low:.0%} ~ {high:.0%}",
    ]
    if floor_income is not None:
        notes.append(f"고정비 하한 보정 적용(고정비/소득 최대비중 {params.fixed_cost_max_ratio:.0%}).")

    return {
        "available": True,
        "base_expense": base,
        "expected_income_next_month": float(expected) if expected is not None else None,
        "expected_income_range": (
            float(income_low) if income_low is not None else None,
            float(income_high) if income_high is not None else None,
        ),
        "confidence": conf,
        "notes": notes,
    }


def _compute_budget_recommendation(
    df_expense_filtered: pd.DataFrame,
    budget_total: float,
    fixed_cost_est_monthly: float,
    top_n_categories: int = 8,
) -> List[Dict[str, Any]]:
    """
    예산 추천:
    - variable_budget = budget_total - fixed_cost_est_monthly
    - 최근 3개월 카테고리 비중으로 배분
    """
    if budget_total is None or budget_total <= 0:
        return []

    variable_budget = max(0.0, budget_total - fixed_cost_est_monthly)

    if len(df_expense_filtered) == 0 or "category_lv1" not in df_expense_filtered.columns:
        return []

    tmp = df_expense_filtered.copy()
    tmp["date"] = _ensure_datetime(tmp["date"])
    tmp = tmp.dropna(subset=["date"]).copy()
    tmp["amount_abs"] = _get_amount_abs(tmp)
    tmp["month"] = _month_key(tmp["date"])

    months_sorted = sorted(tmp["month"].dropna().unique())
    if not months_sorted:
        return []
    recent_months = months_sorted[-3:] if len(months_sorted) >= 3 else months_sorted

    recent = tmp[tmp["month"].isin(recent_months)].copy()
    if len(recent) == 0:
        return []

    cat_sum = recent.groupby("category_lv1")["amount_abs"].sum().sort_values(ascending=False).head(top_n_categories)
    if len(cat_sum) == 0:
        return []

    shares = (cat_sum / cat_sum.sum()).to_dict()
    current_spend = tmp.groupby("category_lv1")["amount_abs"].sum().to_dict()

    rows: List[Dict[str, Any]] = []
    for cat, share in shares.items():
        rec = variable_budget * float(share)
        cur = float(current_spend.get(cat, 0.0))
        rows.append({
            "category_lv1": cat,
            "recommended_budget": float(rec),
            "current_spend": cur,
            "diff": float(rec - cur),
            "basis": f"최근 {len(recent_months)}개월 비중 {float(share):.1%}",
        })
    rows.sort(key=lambda x: x["recommended_budget"], reverse=True)
    return rows


def _compute_short_term_compare(
    *,
    df_expense_all: pd.DataFrame,
    end_ts: pd.Timestamp,
    window_days: int = 30,
    baseline_months: int = 3,
    top_n_categories: int = 3,
) -> Dict[str, Any]:
    """
    ✅ 단기(최근 window_days) 소비를 비교근거로 만들기 위한 요약 블록.
    - baseline 우선순위:
      1) 직전 window_days (previous window)
      2) 최근 baseline_months개 '완전한 월'의 일평균 중앙값(robust)
      3) 전체 기간 일평균 중앙값(robust)
    """
    if df_expense_all is None or len(df_expense_all) == 0:
        return {"available": False, "reason": "지출 데이터가 없습니다."}

    tmp = df_expense_all.copy()
    tmp["date"] = _ensure_datetime(tmp["date"])
    tmp = tmp.dropna(subset=["date"]).copy()
    tmp["amount_abs"] = _get_amount_abs(tmp)

    # category 없는 경우도 대비
    if "category_lv1" not in tmp.columns:
        tmp["category_lv1"] = "기타"

    # 요일/주말
    tmp["weekday"] = tmp["date"].dt.weekday  # 0=Mon ... 6=Sun
    tmp["is_weekend"] = tmp["weekday"].isin([5, 6])

    # ---------------------------
    # 1) Current window (최근 30일)
    # ---------------------------
    end_ts = pd.to_datetime(end_ts).normalize()
    cur_start = end_ts - pd.Timedelta(days=window_days - 1)

    cur = tmp[(tmp["date"] >= cur_start) & (tmp["date"] <= end_ts)].copy()
    cur_days = int(cur["date"].dt.normalize().nunique()) if len(cur) else 0
    cur_total = float(cur["amount_abs"].sum()) if len(cur) else 0.0

    cur_weekday_total = float(cur[~cur["is_weekend"]]["amount_abs"].sum()) if len(cur) else 0.0
    cur_weekend_total = float(cur[cur["is_weekend"]]["amount_abs"].sum()) if len(cur) else 0.0

    # 카테고리 TopN (현재)
    cur_cat = (
        cur.groupby("category_lv1")["amount_abs"].sum().sort_values(ascending=False)
        if len(cur) else pd.Series(dtype=float)
    )
    cur_top = cur_cat.head(top_n_categories).to_dict() if len(cur_cat) else {}

    # ---------------------------
    # 2) Baseline 후보 A: previous window (직전 30일)
    # ---------------------------
    prev_end = cur_start - pd.Timedelta(days=1)
    prev_start = prev_end - pd.Timedelta(days=window_days - 1)
    prev = tmp[(tmp["date"] >= prev_start) & (tmp["date"] <= prev_end)].copy()

    prev_days = int(prev["date"].dt.normalize().nunique()) if len(prev) else 0
    prev_total = float(prev["amount_abs"].sum()) if len(prev) else 0.0

    prev_weekday_total = float(prev[~prev["is_weekend"]]["amount_abs"].sum()) if len(prev) else 0.0
    prev_weekend_total = float(prev[prev["is_weekend"]]["amount_abs"].sum()) if len(prev) else 0.0

    prev_cat = (
        prev.groupby("category_lv1")["amount_abs"].sum().sort_values(ascending=False)
        if len(prev) else pd.Series(dtype=float)
    )

    # previous window가 “충분히” 있는지 (너무 적으면 비교 왜곡)
    prev_ok = prev_days >= max(10, window_days // 3)  # 최소 10일(또는 1/3)

    # ---------------------------
    # 3) Baseline 후보 B: 최근 '완전한 월'의 일평균 중앙값
    # ---------------------------
    # end_ts가 속한 월은 "부분월"일 가능성이 높으니 baseline에서 제외
    tmp["month"] = _month_key(tmp["date"])  # 이미 features.py에 있는 헬퍼 사용
    end_month = _month_key(pd.Series([end_ts]))[0]

    months_sorted = sorted([m for m in tmp["month"].dropna().unique().tolist() if isinstance(m, str)])
    # end_month 이전의 월만 사용
    full_months = [m for m in months_sorted if m < end_month]
    use_months = full_months[-baseline_months:] if len(full_months) else []

    month_daily_avgs = []
    month_totals = {}
    for m in use_months:
        m_df = tmp[tmp["month"] == m]
        if len(m_df) == 0:
            continue
        # 해당 월 '실제 데이터 존재 일수'로 나눠서 일평균 (누락 월 방어)
        days = int(m_df["date"].dt.normalize().nunique())
        if days <= 0:
            continue
        total = float(m_df["amount_abs"].sum())
        month_totals[m] = total
        month_daily_avgs.append(total / days)

    month_ok = len(month_daily_avgs) >= 2  # 최소 2개월은 있어야 안정적
    month_daily_median = float(np.median(month_daily_avgs)) if month_ok else None
    month_baseline_total_for_window = (month_daily_median * window_days) if month_daily_median is not None else None

    # ---------------------------
    # 4) Baseline 후보 C: 전체기간 일평균 중앙값
    # ---------------------------
    tmp["day"] = tmp["date"].dt.normalize()
    daily_total = tmp.groupby("day")["amount_abs"].sum()
    overall_ok = len(daily_total) >= 14
    overall_daily_median = float(np.median(daily_total.values)) if overall_ok else None
    overall_baseline_total_for_window = (overall_daily_median * window_days) if overall_daily_median is not None else None

    # ---------------------------
    # 5) Baseline 선택 (adaptive)
    # ---------------------------
    baseline_used = None
    baseline_total = None
    baseline_meta: Dict[str, Any] = {}

    if prev_ok:
        baseline_used = "previous_window"
        baseline_total = prev_total
        baseline_meta = {
            "prev_start": str(prev_start.date()),
            "prev_end": str(prev_end.date()),
            "prev_days_with_data": int(prev_days),
        }
    elif month_ok:
        baseline_used = "recent_full_months_daily_median"
        baseline_total = float(month_baseline_total_for_window)
        baseline_meta = {
            "months_used": use_months,
            "months_total": month_totals,
            "daily_median": float(month_daily_median),
            "note": "부분월/누락월 왜곡을 줄이기 위해 '월합계'가 아닌 '월 일평균 중앙값'을 사용",
        }
    elif overall_ok:
        baseline_used = "overall_daily_median"
        baseline_total = float(overall_baseline_total_for_window)
        baseline_meta = {
            "days_used": int(len(daily_total)),
            "daily_median": float(overall_daily_median),
        }
    else:
        return {"available": False, "reason": "비교 기준을 만들 데이터가 부족합니다."}

    # 증감
    diff = float(cur_total - baseline_total) if baseline_total is not None else None
    pct = None if (baseline_total in (None, 0.0)) else float(diff / baseline_total)

    # weekday/weekend 변화(가능할 때만)
    weekday_diff = weekend_diff = None
    if baseline_used == "previous_window":
        weekday_diff = float(cur_weekday_total - prev_weekday_total)
        weekend_diff = float(cur_weekend_total - prev_weekend_total)

    # 카테고리 변화 (baseline이 previous window이면 카테고리 delta가 제일 신뢰도 높음)
    cat_deltas = []
    for cat, cur_amt in cur_top.items():
        base_amt = None
        if baseline_used == "previous_window":
            base_amt = float(prev_cat.get(cat, 0.0))
        elif baseline_used in ("recent_full_months_daily_median", "overall_daily_median"):
            # 일평균 기반 baseline에서는 카테고리별 baseline을 “안전하게” 생략(오류 방지)
            base_amt = None

        cat_deltas.append({
            "category_lv1": cat,
            "current": float(cur_amt),
            "baseline": base_amt,
            "diff": (float(cur_amt - base_amt) if base_amt is not None else None),
            "pct": (None if (base_amt in (None, 0.0)) else float((cur_amt - base_amt) / base_amt)),
            "baseline_reliable": (baseline_used == "previous_window"),
        })

    # 신뢰도(대략)
    confidence = "High" if baseline_used == "previous_window" else ("Medium" if baseline_used == "recent_full_months_daily_median" else "Low")

    return {
        "available": True,
        "window": {
            "days": int(window_days),
            "start": str(cur_start.date()),
            "end": str(end_ts.date()),
            "days_with_data": int(cur_days),
        },
        "current": {
            "total": float(cur_total),
            "weekday_total": float(cur_weekday_total),
            "weekend_total": float(cur_weekend_total),
            "top_categories": cur_top,
        },
        "baseline": {
            "used": baseline_used,
            "total_for_window": float(baseline_total),
            "meta": baseline_meta,
            "confidence": confidence,
        },
        "change": {
            "diff": diff,
            "pct": pct,
            "weekday_diff": weekday_diff,
            "weekend_diff": weekend_diff,
        },
        "category_deltas_top": cat_deltas,
        "notes": [
            "단기 비교는 평균보다 중앙값/직전기간 비교를 우선해 왜곡을 줄입니다.",
            "카테고리별 baseline은 직전기간 비교일 때만 신뢰도 높게 제공합니다.",
        ],
    }


def build_ai_summary(
    df_all: pd.DataFrame,
    df_expense_filtered: pd.DataFrame,
    start_date,
    end_date,
    params: Optional[AIRuleParams] = None,
) -> Dict[str, Any]:
    params = params or AIRuleParams()

    start_ts = pd.to_datetime(start_date)
    end_ts = pd.to_datetime(end_date)

    work = df_all.copy()
    work["date"] = _ensure_datetime(work["date"])
    work = work.dropna(subset=["date"]).copy()
    work_period = work[(work["date"] >= start_ts) & (work["date"] <= end_ts)].copy()

    if "is_expense" not in work_period.columns:
        raise ValueError("전처리 결과에 is_expense 컬럼이 없습니다. preprocess.py의 _enrich()를 확인해주세요.")

    df_expense_period = work_period[work_period["is_expense"] == True].copy()

    df_expense = df_expense_filtered.copy()
    df_expense["date"] = _ensure_datetime(df_expense["date"])
    df_expense = df_expense.dropna(subset=["date"]).copy()

    df_expense_period["amount_abs"] = _get_amount_abs(df_expense_period)
    df_expense["amount_abs"] = _get_amount_abs(df_expense)

    df_expense_period["hour"] = _get_hour(df_expense_period)
    df_expense["hour"] = _get_hour(df_expense)

    # -----------------------
    # expense summary (필터 반영)
    # -----------------------
    total_expense = float(df_expense["amount_abs"].sum())
    days_total = _days_in_range(start_ts, end_ts)
    avg_daily_expense = total_expense / days_total if days_total > 0 else None
    avg_weekly_expense = avg_daily_expense * 7 if avg_daily_expense is not None else None

    df_expense["month"] = _month_key(df_expense["date"])
    monthly_expense = df_expense.groupby("month")["amount_abs"].sum().sort_index()
    avg_monthly_expense = float(monthly_expense.mean()) if len(monthly_expense) else None

    max_expense_tx = None
    if len(df_expense) > 0:
        max_idx = df_expense["amount_abs"].idxmax()
        max_expense_tx = _format_max_tx(df_expense.loc[max_idx])

    top5: Dict[str, float] = {}
    top3: Dict[str, float] = {}
    if "category_lv1" in df_expense.columns and len(df_expense) > 0:
        top_cat = df_expense.groupby("category_lv1")["amount_abs"].sum().sort_values(ascending=False)
        top5 = top_cat.head(5).to_dict()
        top3 = top_cat.head(3).to_dict()

    mom_change = _calc_mom_change(monthly_expense)

    # -----------------------
    # fixed candidates (반복 결제)
    # -----------------------
    fixed_candidates: Dict[str, float] = {}
    fixed_cost_est_monthly = 0.0

    if len(df_expense_period) > 0 and "description" in df_expense_period.columns:
        tmp = df_expense_period.copy()
        tmp["date"] = _ensure_datetime(tmp["date"])
        tmp = tmp.dropna(subset=["date"]).copy()
        tmp["amount_abs"] = _get_amount_abs(tmp)
        tmp["month"] = _month_key(tmp["date"])

        rep = tmp.groupby("description")["month"].nunique().sort_values(ascending=False)
        fixed_desc = rep[rep >= 3].head(10).index.tolist()
        if fixed_desc:
            fixed_df = tmp[tmp["description"].isin(fixed_desc)]
            fixed_candidates = (
                fixed_df.groupby("description")["amount_abs"].mean()
                .sort_values(ascending=False)
                .head(10)
                .to_dict()
            )

    if fixed_candidates:
        fixed_cost_est_monthly = float(sum(fixed_candidates.values()))
    fixed_cost_ratio_est = (fixed_cost_est_monthly / total_expense) if total_expense > 0 else None

    # -----------------------
    # ✅ income estimate from expense
    # -----------------------
    income_est = _estimate_income_from_expense(
        monthly_expense=monthly_expense,
        fixed_cost_est_monthly=fixed_cost_est_monthly,
        params=params,
    )

    expected_income_next_month = income_est["expected_income_next_month"]

    # 소비 비율(지출/추정수입)
    if expected_income_next_month is None or expected_income_next_month <= 0:
        spend_ratio = None
        spend_judgement = "추정 수입 산정 불가"
    else:
        spend_ratio = total_expense / expected_income_next_month
        if spend_ratio < params.overspend_ratio_ok:
            spend_judgement = "정상"
        elif spend_ratio < params.overspend_ratio_warn:
            spend_judgement = "주의"
        else:
            spend_judgement = "경고"

    # -----------------------
    # proxies
    # -----------------------
    late_ratio = float((df_expense["hour"] >= params.late_hour_start).mean()) if len(df_expense) else 0.0
    small_tx_ratio = float((df_expense["amount_abs"] <= params.small_tx_threshold).mean()) if len(df_expense) else 0.0

    easy_pay_ratio = None
    if "payment_method" in df_expense.columns and len(df_expense):
        easy_pay_ratio = _contains_ratio(df_expense["payment_method"], params.easy_pay_regex)

    # -----------------------
    # budget
    # -----------------------
    target_ratio = float(params.budget_target_ratio)

    if expected_income_next_month is None:
        budget_total = None
        budget_variable = None
        budget_recommendation = []
    else:
        budget_total = expected_income_next_month * target_ratio
        budget_variable = max(0.0, budget_total - fixed_cost_est_monthly)
        budget_recommendation = _compute_budget_recommendation(
            df_expense_filtered=df_expense,
            budget_total=budget_total,
            fixed_cost_est_monthly=fixed_cost_est_monthly,
            top_n_categories=8,
        )
        
    # -----------------------
    # ✅ short_term_compare (단기 리포트 근거용)
    # -----------------------
    # 전체 지출 데이터(히스토리)에서 baseline을 만들기 위해 work_period가 아닌 work 전체에서 expense만 사용
    df_expense_all = work[work["is_expense"] == True].copy()
    df_expense_all["amount_abs"] = _get_amount_abs(df_expense_all)

    short_term_compare = _compute_short_term_compare(
        df_expense_all=df_expense_all,
        end_ts=end_ts,
        window_days=30,
        baseline_months=3,
        top_n_categories=3,
    )
    
    return {
        "period": {"start": str(start_ts.date()), "end": str(end_ts.date())},

        # 수입은 "지출 기반 추정" 결과로 제공
        "income": {
            "mode": "expense_based_estimation",
            "available": bool(income_est["available"]),
            "base_expense": income_est["base_expense"],
            "expected_income_next_month": income_est["expected_income_next_month"],
            "expected_income_range": income_est["expected_income_range"],
            "confidence": income_est["confidence"],
            "notes": income_est["notes"],
        },

        "expense": {
            "total_expense": float(total_expense),

            "days_in_range": int(days_total),
            "avg_daily_expense": float(avg_daily_expense) if avg_daily_expense is not None else None,
            "avg_weekly_expense": float(avg_weekly_expense) if avg_weekly_expense is not None else None,
            "avg_monthly_expense": float(avg_monthly_expense) if avg_monthly_expense is not None else None,

            "monthly_expense": monthly_expense.to_dict(),
            "mom_change": mom_change,

            "spend_ratio": float(spend_ratio) if spend_ratio is not None else None,
            "spend_judgement": spend_judgement,

            "top_categories_top5": top5,
            "overspend_top3": top3,

            "max_expense_tx": max_expense_tx,

            "late_ratio": float(late_ratio),
            "small_tx_ratio": float(small_tx_ratio),
            "easy_pay_ratio": float(easy_pay_ratio) if easy_pay_ratio is not None else None,

            "fixed_candidates": fixed_candidates,
            "fixed_cost_est_monthly": float(fixed_cost_est_monthly),
            "fixed_cost_ratio_est": float(fixed_cost_ratio_est) if fixed_cost_ratio_est is not None else None,

            "budget_target_ratio": float(target_ratio),
            "budget_total": float(budget_total) if budget_total is not None else None,
            "budget_variable": float(budget_variable) if budget_variable is not None else None,
            "budget_recommendation": budget_recommendation,
        },

        "params": {
            "expense_recent_k": int(params.expense_recent_k),
            "savings_rate_low": float(params.savings_rate_low),
            "savings_rate_high": float(params.savings_rate_high),
            "fixed_cost_max_ratio": float(params.fixed_cost_max_ratio),

            "overspend_ratio_ok": float(params.overspend_ratio_ok),
            "overspend_ratio_warn": float(params.overspend_ratio_warn),
            "small_tx_threshold": int(params.small_tx_threshold),
            "late_hour_start": int(params.late_hour_start),
            "easy_pay_regex": _normalize_regex_pattern(params.easy_pay_regex),
            "budget_target_ratio": float(params.budget_target_ratio),
        },
        "short_term_compare": short_term_compare,
    }