# expense_preprocess/data_manager/state.py
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from .storage import get_store_dir, load_snapshot, save_snapshot, save_clean_df_file


KST = ZoneInfo("Asia/Seoul")

RAW_FILES_KEY = "dm_raw_files"          # name -> bytes (옵션: 재시작 후엔 비우는 걸 권장)
UPLOAD_LOG_KEY = "dm_upload_log"        # name -> {uploaded_at_iso, size}
CLEAN_FILES_KEY = "dm_clean_files"      # name -> {processed_at_iso, rows, min_date, max_date, file_format, file_path, ...}
ACTIVE_DF_KEY = "dm_df_active"          # DataFrame
ACTIVE_SRC_KEY = "dm_data_source"       # str (마지막으로 처리/반영한 파일명)
TIMELINE_MAX_KEY = "dm_timeline_max"    # str(iso) or None
LOADED_KEY = "dm_loaded_from_disk"      # bool

# ✅ 이번 기능의 핵심: 업로드(파일) 단위로 추가된 행을 추적하기 위한 컬럼명
SOURCE_COL = "__source_file"


def _now_iso() -> str:
    return datetime.now(tz=KST).isoformat(timespec="seconds")


def _calc_max_date_iso(df: Optional[pd.DataFrame]) -> Optional[str]:
    if df is None or df.empty or "date" not in df.columns:
        return None
    s = pd.to_datetime(df["date"], errors="coerce").dropna()
    if s.empty:
        return None
    return s.max().isoformat()


def _persist() -> None:
    """
    디스크에 현재 상태 저장 (raw_files bytes는 저장하지 않음)
    """
    store_dir = get_store_dir()

    meta = {
        "upload_log": st.session_state.get(UPLOAD_LOG_KEY, {}),
        "clean_files": st.session_state.get(CLEAN_FILES_KEY, {}),
        "active_source": st.session_state.get(ACTIVE_SRC_KEY),
        "timeline_max": st.session_state.get(TIMELINE_MAX_KEY),
        "saved_at": _now_iso(),
        "version": 2,  # ✅ 버전 증가
    }
    active_df = st.session_state.get(ACTIVE_DF_KEY)
    clean_files = st.session_state.get(CLEAN_FILES_KEY, {})
    save_snapshot(store_dir=store_dir, meta=meta, active_df=active_df, clean_files=clean_files)


def init_data_manager_state() -> None:
    """
    1) session_state 초기화
    2) 최초 1회 디스크 스냅샷 자동 로드
    """
    if RAW_FILES_KEY not in st.session_state:
        st.session_state[RAW_FILES_KEY] = {}

    if UPLOAD_LOG_KEY not in st.session_state:
        st.session_state[UPLOAD_LOG_KEY] = {}

    if CLEAN_FILES_KEY not in st.session_state:
        st.session_state[CLEAN_FILES_KEY] = {}

    if ACTIVE_DF_KEY not in st.session_state:
        st.session_state[ACTIVE_DF_KEY] = None

    if ACTIVE_SRC_KEY not in st.session_state:
        st.session_state[ACTIVE_SRC_KEY] = None

    if TIMELINE_MAX_KEY not in st.session_state:
        st.session_state[TIMELINE_MAX_KEY] = None

    if LOADED_KEY not in st.session_state:
        st.session_state[LOADED_KEY] = False

    # ✅ 디스크에서 자동 복구 (최초 1회만)
    if not st.session_state[LOADED_KEY]:
        store_dir = get_store_dir()
        meta, active = load_snapshot(store_dir)

        if meta:
            st.session_state[UPLOAD_LOG_KEY] = meta.get("upload_log", {}) or {}
            st.session_state[CLEAN_FILES_KEY] = meta.get("clean_files", {}) or {}
            st.session_state[ACTIVE_SRC_KEY] = meta.get("active_source")
            st.session_state[TIMELINE_MAX_KEY] = meta.get("timeline_max")

        if active is not None:
            st.session_state[ACTIVE_DF_KEY] = active
            # 타임라인 재계산(메타가 깨져도 안전)
            st.session_state[TIMELINE_MAX_KEY] = _calc_max_date_iso(active)

        st.session_state[LOADED_KEY] = True


def get_raw_files() -> Dict[str, bytes]:
    init_data_manager_state()
    return st.session_state[RAW_FILES_KEY]


def get_upload_log() -> Dict[str, Dict[str, Any]]:
    init_data_manager_state()
    return st.session_state[UPLOAD_LOG_KEY]


def get_clean_files() -> Dict[str, Dict[str, Any]]:
    init_data_manager_state()
    return st.session_state[CLEAN_FILES_KEY]


def add_uploaded_file(name: str, data: bytes) -> None:
    """
    업로드 파일(원본)은 세션에만 저장.
    업로드 로그는 디스크에도 저장됨.
    """
    init_data_manager_state()

    st.session_state[RAW_FILES_KEY][name] = data
    st.session_state[UPLOAD_LOG_KEY][name] = {
        "uploaded_at": _now_iso(),
        "size_bytes": len(data),
    }
    _persist()


def patch_clean_meta(name: str, patch: Dict[str, Any]) -> None:
    """
    ✅ clean_files[name] 메타를 부분 업데이트 (증분 추가 결과 등 기록용)
    """
    init_data_manager_state()
    cur = st.session_state[CLEAN_FILES_KEY].get(name, {}) or {}
    cur.update(patch or {})
    st.session_state[CLEAN_FILES_KEY][name] = cur
    _persist()


def delete_file(name: str) -> None:
    """
    ✅ 요구사항 1:
    - 업로드 목록에서 파일 삭제 시, '그 파일로 추가된 행'만 ACTIVE_DF에서 제거
    - raw/upload_log/clean_meta는 제거
    - active_source가 해당 파일이면 active_source만 None 처리 (df는 유지)
    """
    init_data_manager_state()

    # 1) ACTIVE_DF에서 해당 파일로 추가된 행만 제거
    df_active = st.session_state.get(ACTIVE_DF_KEY)

    if df_active is not None and isinstance(df_active, pd.DataFrame) and not df_active.empty:
        if SOURCE_COL in df_active.columns:
            df_active = df_active.loc[df_active[SOURCE_COL] != name].copy()
            # 정렬/인덱스 정리
            if "date" in df_active.columns:
                df_active = df_active.sort_values("date").reset_index(drop=True)
            st.session_state[ACTIVE_DF_KEY] = df_active
            st.session_state[TIMELINE_MAX_KEY] = _calc_max_date_iso(df_active)

    # 2) 메타/원본 제거
    st.session_state[RAW_FILES_KEY].pop(name, None)
    st.session_state[UPLOAD_LOG_KEY].pop(name, None)
    st.session_state[CLEAN_FILES_KEY].pop(name, None)

    # 3) active_source 정리 (df는 유지)
    if st.session_state.get(ACTIVE_SRC_KEY) == name:
        st.session_state[ACTIVE_SRC_KEY] = None

    _persist()


def clear_all() -> None:
    init_data_manager_state()
    st.session_state[RAW_FILES_KEY] = {}
    st.session_state[UPLOAD_LOG_KEY] = {}
    st.session_state[CLEAN_FILES_KEY] = {}
    st.session_state[ACTIVE_DF_KEY] = None
    st.session_state[ACTIVE_SRC_KEY] = None
    st.session_state[TIMELINE_MAX_KEY] = None
    _persist()


def clear_active() -> None:
    init_data_manager_state()
    st.session_state[ACTIVE_DF_KEY] = None
    st.session_state[ACTIVE_SRC_KEY] = None
    st.session_state[TIMELINE_MAX_KEY] = None
    _persist()


def set_active_df(df: pd.DataFrame, source_name: str | None) -> None:
    init_data_manager_state()
    st.session_state[ACTIVE_DF_KEY] = df
    st.session_state[ACTIVE_SRC_KEY] = source_name
    st.session_state[TIMELINE_MAX_KEY] = _calc_max_date_iso(df)
    _persist()


def get_active_df() -> Optional[pd.DataFrame]:
    init_data_manager_state()
    return st.session_state[ACTIVE_DF_KEY]


def get_active_source() -> Optional[str]:
    init_data_manager_state()
    return st.session_state[ACTIVE_SRC_KEY]


def get_timeline_max_date() -> Optional[pd.Timestamp]:
    init_data_manager_state()
    iso = st.session_state.get(TIMELINE_MAX_KEY)
    if not iso:
        return None
    try:
        return pd.to_datetime(iso)
    except Exception:
        return None


def save_clean_df(name: str, df_clean: pd.DataFrame) -> None:
    """
    전처리 결과(정제 파일)를 디스크에 저장하고,
    clean_files 메타를 session+disk에 반영
    """
    init_data_manager_state()

    store_dir = get_store_dir()
    file_meta = save_clean_df_file(store_dir=store_dir, name=name, df=df_clean)

    st.session_state[CLEAN_FILES_KEY][name] = {
        "processed_at": _now_iso(),
        **file_meta,
    }
    _persist()