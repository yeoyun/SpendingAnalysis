# expense_preprocess/data_manager/io.py
from __future__ import annotations

import pandas as pd
from io import BytesIO


def load_df_from_bytes(filename: str, data: bytes) -> pd.DataFrame:
    """
    업로드된 bytes를 파일 확장자 기준으로 DataFrame으로 로드
    """
    lower = (filename or "").lower().strip()

    if lower.endswith(".csv"):
        # BOM 고려
        return pd.read_csv(BytesIO(data), encoding="utf-8-sig")

    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return pd.read_excel(BytesIO(data))

    raise ValueError(f"지원하지 않는 확장자입니다: {filename}")


def ensure_date_col(df: pd.DataFrame) -> pd.DataFrame:
    """
    date 컬럼이 있으면 datetime으로 보정 (증분 병합 안정화)
    """
    if df is None or df.empty:
        return df
    if "date" not in df.columns:
        return df

    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    return out