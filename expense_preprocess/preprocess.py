import pandas as pd
import numpy as np
import re


# =========================
# Public Entry Point
# =========================
def run_preprocess(file) -> pd.DataFrame:
    """
    Streamlit에서 호출하는 단일 진입점
    raw CSV / Excel -> 분석용 DataFrame
    """
    df = _load(file)
    df = _standardize_columns(df)
    df = _clean_types(df)
    df = _enrich(df)
    df = _normalize(df)
    return df


# =========================
# Internal Functions
# =========================
def _load(file) -> pd.DataFrame:
    if file.name.endswith(".csv"):
        return pd.read_csv(file)
    elif file.name.endswith(".xlsx"):
        return pd.read_excel(file)
    else:
        raise ValueError("CSV 또는 Excel 파일만 업로드 가능합니다.")


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    컬럼 alias 기반 표준화
    CSV 포맷이 조금 달라도 대응
    """
    column_aliases = {
        "date": ["날짜", "date", "Date"],
        "time": ["시간", "time", "Time"],
        "type": ["타입", "type", "구분"],
        "category_lv1": ["대분류", "category", "카테고리"],
        "category_lv2": ["소분류", "subcategory", "세부카테고리"],
        "description": ["내용", "description", "적요", "메모"],
        "amount": ["금액", "amount", "금액(원)", "price"],
        "currency": ["화폐", "currency"],
        "payment_method": ["결제수단", "payment", "결제방법"]
    }

    rename_map = {}
    found_std_cols = set()

    for std_col, candidates in column_aliases.items():
        for c in candidates:
            if c in df.columns:
                rename_map[c] = std_col
                found_std_cols.add(std_col)
                break

    required = {"date", "amount"}
    if not required.issubset(found_std_cols):
        raise ValueError(
            f"필수 컬럼(date, amount) 누락. "
            f"현재 컬럼: {list(df.columns)}"
        )

    return df.rename(columns=rename_map)


def _clean_types(df: pd.DataFrame) -> pd.DataFrame:
    # 날짜
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if df["date"].isna().any():
        raise ValueError("날짜 컬럼 변환 실패 (yyyy-mm-dd 권장)")

    # 시간 (없어도 허용)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(
            df["time"],
            format="%H:%M",
            errors="coerce"
        ).dt.time
    else:
        df["time"] = pd.NaT

    # 금액
    df["amount"] = (
        df["amount"]
        .astype(str)
        .str.replace(",", "")
        .astype(float)
    )

    # 타입 (없으면 기타 처리)
    if "type" in df.columns:
        df["type"] = df["type"].astype(str).str.strip()
    else:
        # 타입이 없으면 지출로 가정
        df["type"] = "지출"

    return df


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    # 시간 파생
    df["hour"] = df["time"].apply(
        lambda x: x.hour if pd.notna(x) else np.nan
    )

    # ✅ 수입/지출 여부 (type 기반)
    # raw 데이터는 금액 부호가 일관되지 않을 수 있으므로 반드시 type으로 판정
    df["is_expense"] = df["type"] == "지출"
    df["is_income"] = df["type"] == "수입"
    df["is_transfer"] = df["type"] == "이체"

    # ✅ 분석 편의를 위한 절대값 컬럼(선택이지만 추천)
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

    # 이체: 이름 제거
    if row.get("type") == "이체":
        desc = re.sub(r"(토스\s*)?[가-힣]{2,4}", "", str(desc)).strip()
        return desc if desc else row.get("category_lv1", "이체")

    # 수입: 통일
    if row.get("type") == "수입":
        return "입금"

    return desc