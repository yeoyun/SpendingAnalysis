from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class AIRuleParams:
    # =========================
    # 소비 판단 기준 (지출/추정수입)
    # =========================
    overspend_ratio_ok: float = 0.55
    overspend_ratio_warn: float = 0.70

    # =========================
    # 지출 기반 수입 추정(핵심)
    # =========================
    # 최근 몇 개월 지출을 사용해 "다음달 지출"을 대표값으로 잡을지
    expense_recent_k: int = 3

    # 저축률 가정 (수입 역산용) -> range로 사용
    # 예: 0.1이면 "지출이 소득의 90%" 가정
    savings_rate_low: float = 0.10   # 보수적(저축 적게)
    savings_rate_high: float = 0.30  # 공격적(저축 많이)

    # 고정비 기반 하한 보정(선택)
    # "고정비가 소득의 fixed_cost_max_ratio를 넘기기 어렵다" 가정으로 최소 소득 하한 설정
    fixed_cost_max_ratio: float = 0.40

    # =========================
    # 트렌드/위험 신호 proxy
    # =========================
    small_tx_threshold: int = 10_000
    late_hour_start: int = 22
    easy_pay_regex: str = r"간편|페이|pay|npay|kakao|카카오|토스|toss"

    # =========================
    # 예산 추천 기준
    # =========================
    budget_target_ratio: float = 0.55