from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd


def get_store_dir(project_root: str | None = None) -> Path:
    """
    저장 디렉토리:
    - project_root를 넘기면 <project_root>/.dm_store
    - 아니면 현재 작업 디렉토리 기준 .dm_store
    """
    base = Path(project_root) if project_root else Path.cwd()
    d = base / ".dm_store"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _paths(store_dir: Path) -> Dict[str, Path]:
    return {
        "meta": store_dir / "meta.json",
        "active": store_dir / "active.parquet",
        "active_csv": store_dir / "active.csv",
        "clean_dir": store_dir / "clean_files",
    }


def _safe_write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _safe_read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # 메타가 깨졌으면 빈 값으로 시작
        return {}


def _try_write_parquet(df: pd.DataFrame, path: Path) -> bool:
    """
    parquet 저장 시도 (pyarrow/fastparquet 없으면 False)
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        df.to_parquet(tmp, index=False)
        tmp.replace(path)
        return True
    except Exception:
        return False


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(path)


def _try_read_parquet(path: Path) -> Optional[pd.DataFrame]:
    try:
        if path.exists():
            return pd.read_parquet(path)
    except Exception:
        return None
    return None


def _read_csv(path: Path) -> Optional[pd.DataFrame]:
    try:
        if path.exists():
            return pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return None
    return None


def save_snapshot(
    *,
    store_dir: Path,
    meta: dict,
    active_df: Optional[pd.DataFrame],
    clean_files: Dict[str, Dict[str, Any]],
) -> None:
    """
    meta.json + active_df + clean_files(각 파일별 parquet/csv) 저장
    """
    p = _paths(store_dir)
    p["clean_dir"].mkdir(parents=True, exist_ok=True)

    # 1) meta 저장 (raw_files bytes는 저장하지 않습니다: 용량/보안 이슈)
    _safe_write_json(p["meta"], meta)

    # 2) active 저장 (parquet 우선, 실패 시 csv)
    if active_df is None:
        # 활성 파일 삭제
        if p["active"].exists():
            p["active"].unlink(missing_ok=True)
        if p["active_csv"].exists():
            p["active_csv"].unlink(missing_ok=True)
    else:
        ok = _try_write_parquet(active_df, p["active"])
        if not ok:
            _write_csv(active_df, p["active_csv"])

    # 3) clean_files 저장 (각 파일별로 저장)
    for name, info in clean_files.items():
        # info에는 parquet_bytes 같은 in-memory를 넣지 말고, df 자체는 state가 저장 전에 별도로 넘겨주지 않는 구조가 안정적입니다.
        # 여기서는 clean_files 메타만 저장하고, 실제 df 파일은 아래 save_clean_df_file()로 별도 저장하는 방식이 안전합니다.
        # -> 따라서 여기서는 파일 저장은 하지 않고, meta.json에만 clean_files 메타가 담기게 합니다.
        pass


def save_clean_df_file(
    *,
    store_dir: Path,
    name: str,
    df: pd.DataFrame,
) -> Dict[str, Any]:
    """
    정제 파일 1개를 디스크에 저장하고, 그 메타를 반환합니다.
    - clean_files/<safe_name>.parquet (가능하면)
    - 실패하면 clean_files/<safe_name>.csv
    """
    p = _paths(store_dir)
    p["clean_dir"].mkdir(parents=True, exist_ok=True)

    safe_name = name.replace("/", "_").replace("\\", "_").replace("..", "_")
    parquet_path = p["clean_dir"] / f"{safe_name}.parquet"
    csv_path = p["clean_dir"] / f"{safe_name}.csv"

    rows = int(df.shape[0])
    min_iso = None
    max_iso = None
    if rows > 0 and "date" in df.columns:
        s = pd.to_datetime(df["date"], errors="coerce").dropna()
        if not s.empty:
            min_iso = s.min().isoformat()
            max_iso = s.max().isoformat()

    ok = _try_write_parquet(df, parquet_path)
    fmt = "parquet" if ok else "csv"
    if not ok:
        _write_csv(df, csv_path)

    # parquet 저장 성공했으면 csv는 정리
    if ok and csv_path.exists():
        csv_path.unlink(missing_ok=True)

    return {
        "rows": rows,
        "min_date": min_iso,
        "max_date": max_iso,
        "file_format": fmt,
        "file_path": str(parquet_path if ok else csv_path),
    }


def load_snapshot(store_dir: Path) -> Tuple[dict, Optional[pd.DataFrame]]:
    """
    meta.json + active_df 불러오기
    """
    p = _paths(store_dir)
    meta = _safe_read_json(p["meta"])

    active = _try_read_parquet(p["active"])
    if active is None:
        active = _read_csv(p["active_csv"])

    return meta, active


def load_clean_df_file(store_dir: Path, file_path: str) -> Optional[pd.DataFrame]:
    path = Path(file_path)
    if not path.is_absolute():
        # 안전하게 store_dir 기준 상대경로만 허용하고 싶다면 여기서 제한 가능
        path = store_dir / file_path

    if path.suffix.lower() == ".parquet":
        return _try_read_parquet(path)
    if path.suffix.lower() == ".csv":
        return _read_csv(path)
    return None