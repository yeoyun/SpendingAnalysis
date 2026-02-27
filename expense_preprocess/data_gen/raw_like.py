# expense_preprocess/data_gen/raw_like.py
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional, Dict, Tuple, List, Any
import random
from datetime import datetime, timedelta

import pandas as pd
import numpy as np


# =========================
# 안전 단어장(가명 상호 생성용)
# =========================
SAFE_ADJECTIVES = [
    "따뜻한", "상냥한", "차분한", "산뜻한", "든든한", "깔끔한", "고소한", "부드러운",
    "빠른", "정직한", "꼼꼼한", "반짝이는", "포근한", "시원한", "조용한", "가벼운",
    "단정한", "귀여운", "심플한", "단단한",
]
SAFE_NOUNS = [
    "구름", "별", "달", "바람", "숲", "바다", "햇살", "연필", "책", "컵", "모자", "가방",
    "도토리", "호두", "복숭아", "감자", "토스트", "라면", "우유", "초코", "비누", "수건",
    "지도", "시계", "우산", "티켓", "노트", "카드", "라이트", "코인",
]
CATEGORY_SUFFIX = {
    "식비": ["식당", "분식", "한식", "간편식", "배달", "푸드"],
    "카페/간식": ["카페", "베이커리", "디저트", "간식"],
    "온라인쇼핑": ["스토어", "마켓", "쇼핑", "상점"],
    "패션/쇼핑": ["의류", "잡화", "편집샵", "패션"],
    "생활": ["편의점", "마트", "생활", "잡화"],
    "교통": ["교통", "이동", "택시", "주유"],
    "문화/여가": ["영화", "취미", "여가", "게임"],
    "주거/통신": ["통신", "주거", "관리", "정기"],
    "교육/학습": ["학습", "서점", "강의", "교육"],
    "금융": ["정산", "수수료", "납부", "결제"],
    "구독": ["구독", "정기"],
    "이체": ["이체", "송금"],
    "내계좌이체": ["계좌이체", "내계좌"],
    "수입": ["입금", "수익", "급여"],
    "미분류": ["결제", "내역"],
}

SAFE_PAYMENT_METHODS_CARD = ["신용카드", "체크카드", "간편결제"]
SAFE_PAYMENT_METHODS_BANK = ["계좌이체", "현금", "간편결제"]


def _make_korean_alias(rng: random.Random, *, big_category: str) -> str:
    adj = rng.choice(SAFE_ADJECTIVES)
    noun = rng.choice(SAFE_NOUNS)
    suffix = rng.choice(CATEGORY_SUFFIX.get(big_category, CATEGORY_SUFFIX["미분류"]))
    return f"{adj} {noun} {suffix}"


def _dt_to_yyyymmddhhmmss(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S")


def _parse_yyyymmddhhmmss(s: str) -> datetime:
    return datetime.strptime(s, "%Y%m%d%H%M%S")


def _sample_amount_abs(rng: random.Random, big_category: str) -> int:
    # ✅ "현실적인 1회 결제"에 가까운 중앙값(원)
    median_map = {
        "식비": 13000,
        "카페/간식": 4500,
        "온라인쇼핑": 35000,
        "패션/쇼핑": 32000,
        "생활": 12000,
        "교통": 1600,          # 대중교통/택시 섞인 느낌
        "문화/여가": 18000,
        "주거/통신": 35000,     # 통신비/관리비 일부 결제
        "교육/학습": 45000,
        "금융": 25000,          # 수수료/이자/보험료 일부
        "구독": 9900,
        "이체": 50000,
        "내계좌이체": 50000,
        "미분류": 10000,
        # 수입은 별도 처리(아래)
        "수입": 1500000,
    }

    # ✅ "현실적인 상한" (원) - 긴 꼬리 컷
    cap_map = {
        "식비": 80000,
        "카페/간식": 25000,
        "온라인쇼핑": 250000,
        "패션/쇼핑": 200000,
        "생활": 120000,
        "교통": 60000,
        "문화/여가": 200000,
        "주거/통신": 250000,
        "교육/학습": 400000,
        "금융": 500000,
        "구독": 50000,
        "이체": 2000000,
        "내계좌이체": 3000000,
        "미분류": 150000,
        "수입": 6000000,
    }

    # ✅ 변동성(꼬리)을 줄이기 위한 sigma (작을수록 보수적)
    #   - 쇼핑/이체/금융은 조금 더 넓게
    sigma_map = {
        "온라인쇼핑": 0.45,
        "패션/쇼핑": 0.45,
        "금융": 0.55,
        "이체": 0.65,
        "내계좌이체": 0.65,
        "교육/학습": 0.55,
    }

    median = int(median_map.get(big_category, 12000))
    cap = int(cap_map.get(big_category, 200000))
    sigma = float(sigma_map.get(big_category, 0.35))

    # ✅ 수입은 "한 달 급여/부수입" 느낌이라 꼬리보다 범위형이 더 자연스러움
    if big_category == "수입":
        # 120만 ~ 350만 정도를 중심으로, 가끔 500만대까지
        x = rng.gauss(mu=1800000, sigma=450000)
        x = max(300000, min(x, cap))
        snapped = int(round(x / 10.0) * 10)
        return max(snapped, 100)

    # ✅ lognormal: median = exp(mu) 이므로 mu = log(median)
    mu = math.log(max(median, 100.0))

    # rng 기반 lognormal 샘플링
    x = rng.lognormvariate(mu, sigma)

    # 상한/하한 적용 (꼬리 컷)
    x = max(100.0, min(x, float(cap)))

    # 10원 단위 스냅
    snapped = int(round(x / 10.0) * 10)
    return max(snapped, 100)


# =========================
# 카드: MCC → 대/소분류
# =========================
MCC_TO_CATEGORY: Dict[str, Tuple[str, str]] = {
    "5814": ("식비", "배달/패스트푸드"),
    "5812": ("식비", "일반음식점"),
    "5815": ("카페/간식", "카페/디저트"),
    "5411": ("생활", "마트/슈퍼"),
    "5499": ("생활", "편의점"),
    "4121": ("교통", "택시"),
    "4111": ("교통", "대중교통"),
    "5541": ("교통", "주유"),
    "5311": ("온라인쇼핑", "종합몰"),
    "5651": ("패션/쇼핑", "의류/잡화"),
    "7993": ("문화/여가", "게임"),
    "7832": ("문화/여가", "영화"),
    "5942": ("교육/학습", "서점/문구"),
}


def map_category_from_mcc(mcc: Optional[str]) -> Tuple[str, str]:
    if not mcc:
        return ("미분류", "미분류")
    mcc = str(mcc).strip()
    return MCC_TO_CATEGORY.get(mcc, ("미분류", "미분류"))


# =========================
# 은행: 적요/거래구분 기반
# =========================
BANK_KEYWORD_TO_CATEGORY: List[Tuple[List[str], Tuple[str, str]]] = [
    (["급여", "월급", "salary"], ("수입", "급여")),
    (["보너스", "성과", "bonus"], ("수입", "보너스")),
    (["보험", "보험료"], ("금융", "보험")),
    (["통신", "요금"], ("주거/통신", "통신비")),
    (["구독", "정기"], ("구독", "정기구독")),
    (["충전", "페이"], ("금융", "간편결제")),
    (["이체", "송금"], ("이체", "송금")),
]


def map_category_from_bank(print_content: str, trans_type: str) -> Tuple[str, str]:
    text = (print_content or "").strip()

    # 입금
    if str(trans_type).strip() == "02":
        for keywords, pair in BANK_KEYWORD_TO_CATEGORY:
            if any(k in text for k in keywords):
                return pair
        return ("수입", "기타수입")

    # 출금
    for keywords, pair in BANK_KEYWORD_TO_CATEGORY:
        if any(k in text for k in keywords):
            return pair
    return ("미분류", "미분류")


@dataclass(frozen=True)
class GenConfig:
    seed: int = 42
    currency: str = "KRW"
    rows_per_day: int = 25
    card_share: float = 0.65
    card_cancel_rate: float = 0.08
    bank_income_rate: float = 0.20
    transfer_pair: bool = True


def _generate_mydata_api_raw(
    *,
    start_date: str,
    end_date: str,
    config: GenConfig,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Step1: 카드/은행 MyData API RAW 생성
    """
    rng = random.Random(config.seed)
    np.random.seed(config.seed)

    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    if len(dates) == 0:
        raise ValueError("start_date ~ end_date 범위가 비어 있습니다.")

    mcc_pool = list(MCC_TO_CATEGORY.keys())
    card_rows: List[Dict[str, Any]] = []
    bank_rows: List[Dict[str, Any]] = []

    for d in dates:
        base_dt = datetime(d.year, d.month, d.day, 0, 0, 0)

        for _ in range(int(config.rows_per_day)):
            dt = base_dt + timedelta(
                hours=rng.randint(0, 23),
                minutes=rng.randint(0, 59),
                seconds=rng.randint(0, 59),
            )

            # 카드 vs 은행
            if rng.random() < float(config.card_share):
                mcc = rng.choice(mcc_pool)
                big, _sub = map_category_from_mcc(mcc)

                amt_abs = _sample_amount_abs(rng, big if big != "미분류" else "미분류")
                is_cancel = rng.random() < float(config.card_cancel_rate)

                status = "01" if not is_cancel else "02"
                amt_signed = amt_abs if not is_cancel else -amt_abs

                card_rows.append({
                    "approved_dttm": _dt_to_yyyymmddhhmmss(dt),
                    "merchant_id": f"M{rng.randint(1, 999999):06d}",
                    "merchant_name": _make_korean_alias(rng, big_category=big),
                    "mcc": mcc,
                    "approved_amt": float(amt_signed),
                    "pay_method": rng.choice(SAFE_PAYMENT_METHODS_CARD),
                    "status": status,
                    "currency": config.currency,
                })

            else:
                is_income = rng.random() < float(config.bank_income_rate)
                trans_type = "02" if is_income else "01"

                content_templates = [
                    "급여 입금",
                    "보너스 입금",
                    "보험료 납부",
                    "통신 요금",
                    "정기 구독 결제",
                    "간편결제 충전",
                    "계좌 이체",
                    "송금",
                ]
                print_content = rng.choice(content_templates)

                big, sub = map_category_from_bank(print_content, trans_type)

                scale_cat = big
                if scale_cat == "미분류":
                    scale_cat = "수입" if is_income else "이체"

                amt_abs = _sample_amount_abs(rng, scale_cat)

                base_row = {
                    "trans_dttm": _dt_to_yyyymmddhhmmss(dt),
                    "print_content": print_content,
                    "trans_type": trans_type,
                    "trans_amt": float(amt_abs if is_income else -amt_abs),
                    "account_name": "안전 통장",
                    "balance_amt": float(rng.randrange(500_000, 8_000_000, 10_000)),
                    "currency": config.currency,
                }

                # transfer_pair: 출금이면서 이체류면 2행 생성
                if (not is_income) and config.transfer_pair and (big in ("이체", "내계좌이체") or print_content in ["계좌 이체", "송금"]):
                    out_row = base_row.copy()
                    out_row["print_content"] = "내계좌 이체"
                    out_row["trans_type"] = "01"
                    out_row["trans_amt"] = float(-amt_abs)

                    in_row = base_row.copy()
                    in_row["print_content"] = "내계좌 이체"
                    in_row["trans_type"] = "02"
                    in_row["trans_amt"] = float(amt_abs)

                    bank_rows.extend([out_row, in_row])
                else:
                    bank_rows.append(base_row)

    return pd.DataFrame(card_rows), pd.DataFrame(bank_rows)


def _convert_to_step2_raw(
    df_card_raw: pd.DataFrame,
    df_bank_raw: pd.DataFrame,
    *,
    currency_default: str = "KRW",
) -> pd.DataFrame:
    """
    Step2: 1차 가공 통합 포맷 (프로젝트 내부 raw-like)
    출력 컬럼(10):
      날짜, 시간, 타입, 대분류, 소분류, 내용, 금액, 화폐, 결제수단, 메모
    """
    rows: List[Dict[str, Any]] = []

    # 카드
    if df_card_raw is not None and not df_card_raw.empty:
        for r in df_card_raw.to_dict(orient="records"):
            dt = _parse_yyyymmddhhmmss(str(r["approved_dttm"]))
            big, sub = map_category_from_mcc(r.get("mcc"))

            rows.append({
                "날짜": dt.strftime("%Y-%m-%d"),
                "시간": dt.strftime("%H:%M"),
                "타입": "지출",
                "대분류": big,
                "소분류": sub,
                "내용": str(r.get("merchant_name") or ""),
                "금액": float(r.get("approved_amt", 0.0)),
                "화폐": str(r.get("currency") or currency_default),
                "결제수단": str(r.get("pay_method") or "신용카드"),
                "메모": "",
            })

    # 은행
    if df_bank_raw is not None and not df_bank_raw.empty:
        for r in df_bank_raw.to_dict(orient="records"):
            dt = _parse_yyyymmddhhmmss(str(r["trans_dttm"]))
            trans_type = str(r.get("trans_type") or "").strip()
            print_content = str(r.get("print_content") or "")

            big, sub = map_category_from_bank(print_content, trans_type)

            if trans_type == "02":
                tx_type = "수입"
            else:
                # 키워드상 이체면 이체로
                tx_type = "이체" if (big in ("이체", "내계좌이체") or "이체" in print_content) else "지출"

            if print_content == "내계좌 이체":
                big, sub = ("내계좌이체", "미분류")
                tx_type = "이체"

            rows.append({
                "날짜": dt.strftime("%Y-%m-%d"),
                "시간": dt.strftime("%H:%M"),
                "타입": tx_type,
                "대분류": big,
                "소분류": sub,
                "내용": print_content,
                "금액": float(r.get("trans_amt", 0.0)),
                "화폐": str(r.get("currency") or currency_default),
                "결제수단": str(r.get("account_name") or "계좌이체"),
                "메모": "",
            })

    out = pd.DataFrame(rows)
    if not out.empty:
        dt_series = pd.to_datetime(out["날짜"] + " " + out["시간"], errors="coerce")
        out["_dt"] = dt_series
        out = out.sort_values("_dt", ascending=False).drop(columns=["_dt"]).reset_index(drop=True)

    cols = ["날짜", "시간", "타입", "대분류", "소분류", "내용", "금액", "화폐", "결제수단", "메모"]
    out = out[cols]
    return out


# ============================================================
# ✅ 외부에서 import할 "정식 엔트리" (이름 고정!)
# ============================================================
def generate_test_raw_df(
    *,
    start_date: str,
    end_date: str,
    reference_dist=None,  # ✅ UI 호환용(현재 사용 안 함)
    rows_per_day: int = 25,
    seed: int = 42,
    currency: str = "KRW",
    transfer_pair: bool = True,
) -> pd.DataFrame:
    """
    UI에서 호출하는 최종 테스트 데이터 생성 함수 (이름 고정: generate_test_raw_df)

    - Step1: MyData API RAW 생성
    - Step2: 1차 가공 통합 포맷으로 변환
    """
    cfg = GenConfig(
        seed=int(seed),
        currency=str(currency),
        rows_per_day=int(rows_per_day),
        transfer_pair=bool(transfer_pair),
    )

    df_card, df_bank = _generate_mydata_api_raw(
        start_date=str(start_date),
        end_date=str(end_date),
        config=cfg,
    )

    df_out = _convert_to_step2_raw(df_card, df_bank, currency_default=str(currency))
    return df_out