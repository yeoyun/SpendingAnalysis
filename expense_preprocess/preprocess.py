# expense_preprocess/preprocess.py

from __future__ import annotations

import re
import warnings
from typing import Callable, Optional

import numpy as np
import pandas as pd

WarnFn = Callable[[str], None]


# =========================
# Public Entry Point
# =========================
def run_preprocess(file, warn_fn: Optional[WarnFn] = None) -> pd.DataFrame:
    """
    Streamlit에서 호출하는 단일 진입점
    raw CSV / Excel -> 분석용 DataFrame

    warn_fn:
      - Streamlit에서는 warn_fn=st.warning 로 넘기면 경고를 UI에 표시할 수 있습니다.
      - 미지정 시 warnings.warn 로 처리합니다.
    """
    _warn = warn_fn or (lambda msg: warnings.warn(msg, stacklevel=2))

    df = _load(file, _warn)
    df = _standardize_columns(df, _warn)
    df = _clean_types(df, _warn)
    df = _enrich(df)
    df = _normalize(df)
    return df


# =========================
# Internal Functions
# =========================
def _load(file, warn_fn: WarnFn) -> pd.DataFrame:
    name = getattr(file, "name", "") or ""
    lower = name.lower()

    if lower.endswith(".csv"):
        # ✅ BOM(utf-8-sig) 대응 + 한글(cp949) 재시도 + 구분자 자동추정
        try:
            file.seek(0)
            return pd.read_csv(file, encoding="utf-8-sig", sep=None, engine="python")
        except UnicodeDecodeError:
            warn_fn("CSV 인코딩이 UTF-8이 아니어서 cp949로 재시도합니다.")
            file.seek(0)
            return pd.read_csv(file, encoding="cp949", sep=None, engine="python")

    if lower.endswith(".xlsx"):
        file.seek(0)
        return pd.read_excel(file)  # openpyxl 필요

    raise ValueError("CSV 또는 Excel(.xlsx) 파일만 업로드 가능합니다.")


def _standardize_columns(df: pd.DataFrame, warn_fn: WarnFn) -> pd.DataFrame:
    """
    컬럼 alias 기반 표준화
    CSV 포맷이 조금 달라도 대응
    """
    # ✅ 컬럼명 BOM/공백 제거 (혹시 로더에서 못 잡는 경우도 대비)
    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
    )

    column_aliases = {
        "date": ["날짜", "date", "Date"],
        "time": ["시간", "time", "Time"],
        "type": ["타입", "type", "구분"],
        "category_lv1": ["대분류", "category", "카테고리"],
        "category_lv2": ["소분류", "subcategory", "세부카테고리"],
        "description": ["내용", "description", "적요", "메모"],
        "amount": ["금액", "amount", "금액(원)", "price"],
        "currency": ["화폐", "currency"],
        "payment_method": ["결제수단", "payment", "결제방법"],
    }

    rename_map: dict[str, str] = {}
    found_std_cols = set()

    for std_col, candidates in column_aliases.items():
        for c in candidates:
            if c in df.columns:
                rename_map[c] = std_col
                found_std_cols.add(std_col)
                break

    # 필수 컬럼 체크
    required = {"date", "amount"}
    if not required.issubset(found_std_cols):
        raise ValueError(
            "필수 컬럼(date, amount) 누락. "
            f"현재 컬럼: {list(df.columns)}"
        )

    df = df.rename(columns=rename_map)

    # ✅ 옵션 A: category_lv1 없으면 '기타' 생성 (차트가 죽지 않도록)
    if "category_lv1" not in df.columns:
        warn_fn("category 컬럼이 없어 category_lv1을 '기타'로 생성합니다.")
        df["category_lv1"] = "기타"

    return df


def _clean_types(df: pd.DataFrame, warn_fn: WarnFn) -> pd.DataFrame:
    # -------------------------
    # date: 부분 실패 허용
    # -------------------------
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    bad_date = int(df["date"].isna().sum())
    if bad_date:
        warn_fn(f"date 파싱 실패 {bad_date}건 제외합니다.")
        df = df.loc[df["date"].notna()].copy()

    if df.empty:
        raise ValueError("유효한 date가 없어 데이터가 비었습니다. date 형식을 확인해주세요.")

    # -------------------------
    # time: 없어도 허용 + 다양한 형태 대응
    # -------------------------
    if "time" in df.columns:
        t = df["time"]
        t_str = t.astype(str).where(t.notna(), other=None)
        # 시간 포맷 명시 (HH:MM 또는 HH:MM:SS 대응)
        parsed = pd.to_datetime(
            t_str,
            format="%H:%M",
            errors="coerce"
        )

        # HH:MM:SS 형태 재시도
        mask = parsed.isna()
        if mask.any():
            parsed2 = pd.to_datetime(
                t_str[mask],
                format="%H:%M:%S",
                errors="coerce"
            )
            parsed.loc[mask] = parsed2

        df["time"] = parsed.dt.time
    else:
        df["time"] = pd.NaT

    # -------------------------
    # amount: 실전형 정규화 + 부분 실패 허용
    # -------------------------
    s = df["amount"].astype(str)

    # (1) 괄호 음수: (1234) -> -1234
    s = s.str.replace(r"^\((.*)\)$", r"-\1", regex=True)

    # (2) 통화/공백/콤마 제거
    s = s.str.replace(",", "", regex=False)
    s = s.str.replace("원", "", regex=False)
    s = s.str.replace(r"\s+", "", regex=True)

    # (3) 숫자/부호/소수점 이외 제거
    s = s.str.replace(r"[^0-9\-\.+]", "", regex=True)

    df["amount"] = pd.to_numeric(s, errors="coerce")
    bad_amt = int(df["amount"].isna().sum())
    if bad_amt:
        warn_fn(f"amount 파싱 실패 {bad_amt}건 제외합니다.")
        df = df.loc[df["amount"].notna()].copy()

    if df.empty:
        raise ValueError("유효한 amount가 없어 데이터가 비었습니다. amount 형식을 확인해주세요.")

    # -------------------------
    # type: 없으면 지출로 가정
    # -------------------------
    if "type" in df.columns:
        df["type"] = df["type"].astype(str).str.strip()
        df.loc[df["type"] == "", "type"] = "지출"
    else:
        df["type"] = "지출"

    # category_lv1: 결측/빈값 방어
    df["category_lv1"] = df["category_lv1"].astype(str)
    df.loc[df["category_lv1"].isna() | (df["category_lv1"].str.strip() == ""), "category_lv1"] = "기타"

    return df


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    # 시간 파생
    df["hour"] = df["time"].apply(lambda x: x.hour if pd.notna(x) else np.nan)

    # ✅ 수입/지출 여부 (type 기반)
    df["is_expense"] = df["type"] == "지출"
    df["is_income"] = df["type"] == "수입"
    df["is_transfer"] = df["type"] == "이체"

    # ✅ 분석 편의 절대값
    df["amount_abs"] = df["amount"].abs()

    return df


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    if "description" in df.columns:
        df["description"] = df.apply(_anonymize_description, axis=1)
    return df


def _anonymize_description(row) -> str:
    desc = row.get("description")
    if pd.isna(desc):
        return desc

    desc = str(desc)

    # 이체: 이름 제거 (오탐/누락 가능 → 3주차에서 옵션화 권장)
    if row.get("type") == "이체":
        desc = re.sub(r"(토스\s*)?[가-힣]{2,4}", "", desc).strip()
        return desc if desc else row.get("category_lv1", "이체")

    # 수입: 통일
    if row.get("type") == "수입":
        return "입금"

    return desc