# expense_preprocess/data_manager/page.py
from __future__ import annotations

from pathlib import Path

import streamlit as st
import pandas as pd

from expense_preprocess.data_gen.raw_like import generate_test_raw_df
from expense_preprocess.data_gen.ui_test_data import render_test_data_generator

from .state import (
    init_data_manager_state,
    add_uploaded_file,
    get_raw_files,
    get_upload_log,
    get_clean_files,
    save_clean_df,
    set_active_df,
    get_active_df,
    get_active_source,
    get_timeline_max_date,
    delete_file,
    clear_active,
    clear_all,
    patch_clean_meta,
    SOURCE_COL,
)
from .io import load_df_from_bytes, ensure_date_col
from expense_preprocess.preprocess import run_preprocess


# ─────────────────────────────────────────────
# CSS 인젝션
# ─────────────────────────────────────────────
_CSS = """
<style>
/* ── 전체 폰트 ── */
@import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── 헤더 ── */
h1 { font-weight: 700 !important; letter-spacing: -0.5px; }
h3 { font-weight: 600 !important; color: #374151 !important; letter-spacing: -0.3px; }

/* ── 카드 컨테이너 ── */
.dm-card {
    background: #ffffff;
    border: 1px solid #ebebf0;
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}

/* ── 활성 데이터 배지 ── */
.dm-active-range {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: #f0f4ff;
    border: 1px solid #d0d9ff;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 0.95rem;
    font-weight: 600;
    color: #3451d1;
    margin-bottom: 10px;
}

.dm-meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    margin-top: 8px;
}
.dm-meta-item {
    font-size: 0.82rem;
    color: #6b7280;
    line-height: 1.5;
}
.dm-meta-item b {
    color: #111827;
    font-weight: 600;
}

/* ── 파일 정제 상태 배지 ── */
.dm-badge-ok {
    display: inline-block;
    background: #ecfdf5;
    color: #059669;
    border: 1px solid #a7f3d0;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 0.78rem;
    font-weight: 600;
}
.dm-badge-warn {
    display: inline-block;
    background: #fffbeb;
    color: #d97706;
    border: 1px solid #fde68a;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 0.78rem;
    font-weight: 600;
}

/* ── 구분선 ── */
hr.dm-divider {
    border: none;
    border-top: 1px solid #f0f0f5;
    margin: 28px 0;
}

/* ── 버튼 여백 ── */
.stButton > button {
    margin-top: 8px !important;
    margin-bottom: 8px !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 10px 20px !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.10) !important;
}

/* ── 다운로드 버튼 ── */
.stDownloadButton > button {
    margin-top: 8px !important;
    margin-bottom: 8px !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 10px 20px !important;
}

/* ── 섹션 타이틀 ── */
.dm-section-title {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #9ca3af;
    margin-bottom: 10px;
    margin-top: 4px;
}

/* ── info / warning 박스 커스텀 ── */
.stAlert {
    border-radius: 10px !important;
}

/* ── selectbox ── */
.stSelectbox > div > div {
    border-radius: 10px !important;
}

/* ── expander ── */
.streamlit-expanderHeader {
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    border-radius: 10px !important;
}
</style>
"""


# ─────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────
def _fmt_date(val: str | None) -> str:
    if not val:
        return "-"
    try:
        return pd.to_datetime(val).strftime("%Y-%m-%d")
    except Exception:
        return str(val)


def _fmt_uploaded_at(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        return pd.to_datetime(iso).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(iso)


def _date_only_series(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce").dt.date.astype(str)


def _incremental_append_by_day(
    active_df: pd.DataFrame | None,
    new_df: pd.DataFrame,
    *,
    source_name: str,
) -> tuple[pd.DataFrame, dict]:
    new_df = ensure_date_col(new_df).copy()
    new_df[SOURCE_COL] = source_name
    new_df["__date_only"] = _date_only_series(new_df["date"])

    if active_df is None or active_df.empty:
        merged = new_df.sort_values("date").reset_index(drop=True)
        meta = {
            "added_rows": int(len(new_df)),
            "dropped_duplicate_days": 0,
            "added_min_date": (pd.to_datetime(new_df["date"]).min().isoformat() if len(new_df) else None),
            "added_max_date": (pd.to_datetime(new_df["date"]).max().isoformat() if len(new_df) else None),
        }
        return merged, meta

    active_df = ensure_date_col(active_df).copy()
    if "date" not in active_df.columns:
        merged = pd.concat([active_df, new_df], ignore_index=True)
        return merged, {"added_rows": int(len(new_df)), "dropped_duplicate_days": 0, "added_min_date": None, "added_max_date": None}

    active_df["__date_only"] = _date_only_series(active_df["date"])
    existing_days = set(active_df["__date_only"].dropna().unique())
    dup_mask = new_df["__date_only"].isin(existing_days)
    dropped = int(dup_mask.sum())
    add_part = new_df.loc[~dup_mask].copy()

    merged = pd.concat([active_df, add_part], ignore_index=True)
    merged = merged.sort_values("date").reset_index(drop=True)
    merged = merged.drop(columns=["__date_only"], errors="ignore")

    added_min = added_max = None
    if len(add_part) > 0:
        added_min = pd.to_datetime(add_part["date"], errors="coerce").dropna().min()
        added_max = pd.to_datetime(add_part["date"], errors="coerce").dropna().max()

    return merged, {
        "added_rows": int(len(add_part)),
        "dropped_duplicate_days": dropped,
        "added_min_date": (added_min.isoformat() if added_min is not None and pd.notna(added_min) else None),
        "added_max_date": (added_max.isoformat() if added_max is not None and pd.notna(added_max) else None),
    }


# ─────────────────────────────────────────────
# 메인 렌더 함수
# ─────────────────────────────────────────────
def render_data_manage_page() -> None:
    init_data_manager_state()

    # CSS 삽입
    st.markdown(_CSS, unsafe_allow_html=True)

    st.header("데이터 관리")

    raw_files  = get_raw_files()
    upload_log = get_upload_log()
    clean_files = get_clean_files()
    names = sorted(set(upload_log.keys()) | set(clean_files.keys()) | set(raw_files.keys()))

    # ── 파일 없음 ──────────────────────────────
    if not names:
        st.info("업로드된 파일이 없습니다. 좌측 사이드바에서 파일을 업로드해주세요.")
        st.markdown('<hr class="dm-divider">', unsafe_allow_html=True)
        _render_test_section()
        return

    st.markdown("### 데이터 현황")

    # ── 활성 데이터 요약 카드 ──────────────────
    active_src = get_active_source()
    df_active  = get_active_df()
    c_active   = clean_files.get(active_src) if active_src else None

    if df_active is not None and not df_active.empty:
        min_ts = max_ts = None
        if "date" in df_active.columns:
            s = pd.to_datetime(df_active["date"], errors="coerce").dropna()
            if not s.empty:
                min_ts, max_ts = s.min(), s.max()

        d_min = _fmt_date(c_active.get("min_date")) if c_active else (min_ts.strftime("%Y-%m-%d") if min_ts else "-")
        d_max = _fmt_date(c_active.get("max_date")) if c_active else (max_ts.strftime("%Y-%m-%d") if max_ts else "-")

        st.markdown(f"""
        <div class="dm-card">
            <div class="dm-active-range">📅 {d_min} &nbsp;→&nbsp; {d_max}</div>
            <div class="dm-meta-row">
                <span class="dm-meta-item">소스<br><b>{active_src or "-"}</b></span>
                <span class="dm-meta-item">총 행수<br><b>{df_active.shape[0]:,} rows</b></span>
                <span class="dm-meta-item">컬럼 수<br><b>{df_active.shape[1]:,} cols</b></span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="dm-card" style="color:#9ca3af; font-size:0.88rem;">
            활성 데이터 없음
        </div>
        """, unsafe_allow_html=True)

    # ── 업로드 목록 ────────────────────────────
    st.markdown('<hr class="dm-divider">', unsafe_allow_html=True)
    st.markdown("### 업로드 목록")

    default_idx = names.index(active_src) if active_src in names else 0
    colA, colB = st.columns([1.6, 0.4])
    with colA:
        selected = st.selectbox(
            "파일 선택",
            names,
            index=default_idx,
            key="dm_selected",
            label_visibility="collapsed",
        )
    with colB:
        if st.button("🗑️ 삭제", use_container_width=True, key="dm_delete_btn"):
            delete_file(selected)
            st.rerun()

    u = upload_log.get(selected, {})
    c = clean_files.get(selected)

    # 파일 메타 카드
    clean_status_html = ""
    if c:
        rows_val  = c.get("rows", 0)
        range_str = f"{_fmt_date(c.get('min_date'))} ~ {_fmt_date(c.get('max_date'))}"
        clean_status_html = f'<span class="dm-badge-ok">정제 완료 · {rows_val:,}행 · {range_str}</span>'
        if c.get("added_rows") is not None:
            added   = c.get("added_rows", 0)
            dropped = c.get("dropped_duplicate_days", 0)
            a_min   = _fmt_date(c.get("added_min_date"))
            a_max   = _fmt_date(c.get("added_max_date"))
            clean_status_html += f'<br><span style="font-size:0.78rem; color:#6b7280; margin-top:4px; display:inline-block">추가 {added:,}행 · 중복제외 {dropped:,}행 · {a_min} ~ {a_max}</span>'
    else:
        clean_status_html = '<span class="dm-badge-warn">미처리</span>'

    st.markdown(f"""
    <div class="dm-card" style="padding: 16px 24px;">
        <div class="dm-meta-row">
            <span class="dm-meta-item">업로드<br><b>{_fmt_uploaded_at(u.get('uploaded_at'))}</b></span>
            <span class="dm-meta-item">크기<br><b>{u.get('size_bytes', 0):,} bytes</b></span>
            <span class="dm-meta-item">처리 상태<br>{clean_status_html}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if selected not in raw_files:
        st.warning("원본 파일이 현재 세션에 없습니다. 재업로드 후 정제를 진행해주세요.")

    # ── 미리보기 ───────────────────────────────
    if df_active is not None and not df_active.empty:
        st.markdown('<hr class="dm-divider">', unsafe_allow_html=True)
        st.markdown("### 데이터 미리보기")

        with st.expander("상위 50행 보기"):
            st.dataframe(df_active.head(50), use_container_width=True)

        # ── 전체 삭제 + 내보내기 ─────────────────
        st.markdown('<hr class="dm-divider">', unsafe_allow_html=True)
        st.markdown("### 데이터 관리")

        col_del, col_exp = st.columns(2)

        with col_del:
            if st.button("🗑️ 전체 데이터 삭제", use_container_width=True, key="dm_clear_all"):
                clear_all()
                st.rerun()
                return

        # 내보내기 파일명 계산
        min_ts = max_ts = None
        if "date" in df_active.columns:
            s = pd.to_datetime(df_active["date"], errors="coerce").dropna()
            if not s.empty:
                min_ts, max_ts = s.min(), s.max()

        min_str = min_ts.strftime("%Y-%m-%d") if min_ts else None
        max_str = max_ts.strftime("%Y-%m-%d") if max_ts else None
        export_name = (
            f"active_{min_str}_{max_str}.csv" if (min_str and max_str and min_str != max_str)
            else f"active_{min_str}.csv" if min_str
            else "active_data.csv"
        )

        # 서버 저장 시도
        try:
            PROJECT_ROOT = Path(__file__).resolve().parents[2]
            save_dir = PROJECT_ROOT / "data" / "active"
            save_dir.mkdir(parents=True, exist_ok=True)
            df_active.to_csv(save_dir / export_name, index=False, encoding="utf-8-sig")
        except Exception:
            pass

        csv_bytes = df_active.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        with col_exp:
            st.download_button(
                label="💾 데이터 내보내기 (.csv)",
                data=csv_bytes,
                file_name=export_name,
                mime="text/csv",
                use_container_width=True,
                key="dm_export_active_csv",
            )

    else:
        st.markdown('<hr class="dm-divider">', unsafe_allow_html=True)
        st.info("현재 활성 데이터가 없습니다.")

    # ── 테스트 데이터 생성 ─────────────────────
    st.markdown('<hr class="dm-divider">', unsafe_allow_html=True)
    _render_test_section()


def _render_test_section() -> None:
    render_test_data_generator(
        generate_func=generate_test_raw_df,
        cache_key="dm_test_df_cache",
        expander_title="기간 입력 기반 테스트 데이터 생성기",
        default_days=30,
        save_subdir="data/test_generated",
    )