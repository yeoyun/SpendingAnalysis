# ai_report/utils.py
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Literal

DEFAULT_CACHE_DIR = Path("ai_cache")

ReportMode = Literal["legacy", "all", "short"]


def _ensure_dir(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)


def _safe_json_dump(path: Path, payload: Dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _mode_dir(cache_dir: Path, mode: ReportMode) -> Path:
    """
    ✅ 모드별 캐시 폴더 분리
    - legacy: ai_cache/legacy
    - all:    ai_cache/all
    - short:  ai_cache/short
    """
    sub = "legacy" if mode == "legacy" else ("all" if mode == "all" else "short")
    return cache_dir / sub


def make_ai_report_key(
    *,
    summary: Dict[str, Any],
    params_dict: Dict[str, Any],
    model: str,
    version: str = "v1",
) -> str:
    """
    입력(summary/params/model)이 같으면 동일한 key를 생성합니다.
    - version을 올리면 캐시 무효화(스키마 변경 등) 용도로 사용 가능
    """
    payload = {
        "version": version,
        "model": model,
        "params": params_dict,
        "summary": summary,
    }
    s = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def save_ai_report(
    *,
    result: Dict[str, Any],
    summary: Dict[str, Any],
    key: str,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    mode: ReportMode = "legacy",
) -> str:
    """
    ✅ 저장 시 mode별 폴더로 분리 저장
    """
    base = _mode_dir(cache_dir, mode)
    _ensure_dir(base)
    path = base / f"report_{key}.json"

    payload = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "key": key,
        "mode": mode,
        "result": result or {},
        "summary": summary or {},
    }
    _safe_json_dump(path, payload)
    return str(path)


def load_ai_report(
    *,
    key: str,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    mode: ReportMode = "legacy",
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    ✅ mode별 폴더에서 불러오기
    """
    base = _mode_dir(cache_dir, mode)
    path = base / f"report_{key}.json"
    if not path.exists():
        return None, None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = data.get("result")
        summary = data.get("summary")
        if not isinstance(result, dict) or not isinstance(summary, dict):
            return None, None
        return result, summary
    except Exception:
        return None, None


def restore_latest_to_session(
    st,
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    force: bool = False,
) -> bool:
    """
    (호환 유지) legacy 세션키로 '가장 최신 1개' 복구
    - ai_report_result / ai_report_summary
    """
    return restore_latest_to_session_by_mode(st, cache_dir=cache_dir, mode="legacy", force=force)


def restore_latest_to_session_by_mode(
    st,
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    mode: ReportMode = "legacy",
    force: bool = False,
) -> bool:
    """
    ✅ 특정 mode(legacy/all/short)의 최신 파일 1개를 세션에 복구
    - legacy: ai_report_result / ai_report_summary
    - all:    ai_report_result_all / ai_report_summary_all
    - short:  ai_report_result_short / ai_report_summary_short
    """
    base = _mode_dir(cache_dir, mode)
    if not base.exists():
        return False

    # 이미 세션에 있으면 스킵(옵션)
    if not force:
        if mode == "legacy":
            cur = st.session_state.get("ai_report_result")
            if isinstance(cur, dict) and cur:
                return True
        elif mode == "all":
            cur = st.session_state.get("ai_report_result_all")
            if isinstance(cur, dict) and cur:
                return True
        else:  # short
            cur = st.session_state.get("ai_report_result_short")
            if isinstance(cur, dict) and cur:
                return True

    files = sorted(base.glob("report_*.json"), reverse=True)
    if not files:
        return False

    try:
        with open(files[0], "r", encoding="utf-8") as f:
            data = json.load(f)
        result = data.get("result")
        summary = data.get("summary")

        if not isinstance(result, dict):
            return False
        if not isinstance(summary, dict):
            summary = {}

        if mode == "legacy":
            st.session_state["ai_report_result"] = result
            st.session_state["ai_report_summary"] = summary
        elif mode == "all":
            st.session_state["ai_report_result_all"] = result
            st.session_state["ai_report_summary_all"] = summary
        else:
            st.session_state["ai_report_result_short"] = result
            st.session_state["ai_report_summary_short"] = summary

        return True
    except Exception:
        return False


def restore_latest_to_session_both(
    st,
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    force: bool = False,
) -> Dict[str, bool]:
    """
    ✅ 장기(all) + 단기(short) 최신을 각각 복구
    반환: {"all": True/False, "short": True/False}
    """
    ok_all = restore_latest_to_session_by_mode(st, cache_dir=cache_dir, mode="all", force=force)
    ok_short = restore_latest_to_session_by_mode(st, cache_dir=cache_dir, mode="short", force=force)
    return {"all": ok_all, "short": ok_short}