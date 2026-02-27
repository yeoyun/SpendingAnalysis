# app/sidebar.py

from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import Tuple, List, Optional

from expense_preprocess.data_manager.state import get_active_df
from ai_report.ui import init_ai_report_state, render_ai_sidebar_controls

try:
    from streamlit_option_menu import option_menu
except Exception:
    option_menu = None

from datetime import date


# ──────────────────────────────────────────────────────────────
# 공통 날짜 헬퍼
# ──────────────────────────────────────────────────────────────

def _clamp_date(d: date, min_d: date, max_d: date) -> date:
    if d < min_d: return min_d
    if d > max_d: return max_d
    return d

def _get_date_bounds(df: pd.DataFrame) -> tuple[date, date]:
    s = pd.to_datetime(df["date"], errors="coerce").dropna()
    if s.empty:
        today = pd.Timestamp.today().date()
        return today, today
    return s.min().date(), s.max().date()


# ──────────────────────────────────────────────────────────────
# 네비게이션 메뉴
# ──────────────────────────────────────────────────────────────

def render_sidebar_menu() -> str:
    with st.sidebar:
        st.markdown("## 📌 메뉴")
        st.markdown(
            """<style>
            div[data-testid="stSidebar"] .nav.nav-pills > li:nth-child(3){
                margin-top:8px!important; padding-top:8px!important;
                border-top:1px solid #E5E7EB!important;
            }
            </style>""",
            unsafe_allow_html=True,
        )
        if option_menu is not None:
            page = option_menu(
                menu_title=None,
                options=["🏠 홈", "🧠 AI 리포트", "🧼 데이터 관리"],
                icons=["house", "robot", "database"],
                menu_icon="list",
                default_index=0,
                styles={
                    "container": {"padding": "0px 0px 8px 0px"},
                    "icon":      {"font-size": "16px"},
                    "nav-link":  {"font-size":"15px","padding":"10px 12px","border-radius":"10px"},
                    "nav-link-selected": {"font-weight":"700"},
                },
            )
        else:
            page = st.selectbox("이동", ["🏠 홈", "🧠 AI 리포트", "🧼 데이터 관리"])
        st.divider()
    return page


def _require_active_df_or_stop() -> pd.DataFrame:
    df = get_active_df()
    if df is None or df.empty:
        st.sidebar.info("먼저 '🧼 데이터 관리'에서 데이터를 업로드/전처리 후 활성화해주세요.")
        st.stop()
    return df


# ──────────────────────────────────────────────────────────────
# 데이터 관리 사이드바
# ──────────────────────────────────────────────────────────────

def render_data_manage_sidebar_uploader() -> None:
    import pandas as pd
    import streamlit as st

    from expense_preprocess.preprocess import run_preprocess
    from expense_preprocess.data_manager.state import (
        add_uploaded_file, get_raw_files, save_clean_df,
        set_active_df, get_active_df, get_timeline_max_date,
        get_active_source, patch_clean_meta, SOURCE_COL,
    )
    from expense_preprocess.data_manager.io import ensure_date_col, load_df_from_bytes

    def _date_only_series(s: pd.Series) -> pd.Series:
        return pd.to_datetime(s, errors="coerce").dt.date.astype(str)

    def _incremental_append_by_day(active_df, new_df, *, source_name):
        new_df = ensure_date_col(new_df).copy()
        new_df[SOURCE_COL] = source_name
        new_df["__date_only"] = _date_only_series(new_df["date"])
        if active_df is None or active_df.empty:
            merged = new_df.sort_values("date").reset_index(drop=True)
            added_min = pd.to_datetime(new_df["date"], errors="coerce").dropna().min()
            added_max = pd.to_datetime(new_df["date"], errors="coerce").dropna().max()
            meta = {"added_rows": int(len(new_df)), "dropped_duplicate_days": 0,
                    "added_min_date": added_min.isoformat() if pd.notna(added_min) else None,
                    "added_max_date": added_max.isoformat() if pd.notna(added_max) else None}
            return merged.drop(columns=["__date_only"], errors="ignore"), meta

        active_df = ensure_date_col(active_df).copy()
        active_df["__date_only"] = _date_only_series(active_df["date"])
        existing_days = set(active_df["__date_only"].dropna().unique())
        dup_mask = new_df["__date_only"].isin(existing_days)
        add_part = new_df.loc[~dup_mask].copy()
        merged = pd.concat([active_df, add_part], ignore_index=True)
        merged = merged.sort_values("date").reset_index(drop=True)
        merged = merged.drop(columns=["__date_only"], errors="ignore")
        added_min = pd.to_datetime(add_part["date"], errors="coerce").dropna().min() if len(add_part) else None
        added_max = pd.to_datetime(add_part["date"], errors="coerce").dropna().max() if len(add_part) else None
        meta = {"added_rows": int(len(add_part)), "dropped_duplicate_days": int(dup_mask.sum()),
                "added_min_date": added_min.isoformat() if added_min is not None and pd.notna(added_min) else None,
                "added_max_date": added_max.isoformat() if added_max is not None and pd.notna(added_max) else None}
        return merged, meta

    st.sidebar.header("🗂️ 데이터 추가하기")
    uploaded_files = st.sidebar.file_uploader(
        "파일 추가하기 (CSV / Excel)",
        type=["csv","xlsx","xls"], accept_multiple_files=True,
        key="dm_uploader_sidebar",
    )

    raw_count  = len(get_raw_files() or {})
    tl_max     = get_timeline_max_date()
    active_src = get_active_source()
    st.sidebar.caption(f"📦 업로드된 파일 수(세션): {raw_count}개")
    if tl_max is None:
        st.sidebar.caption("⏱️ 활성 타임라인: 없음")
    else:
        st.sidebar.caption(f"⏱️ 활성 소스: {active_src}")
        st.sidebar.caption(f"⏱️ 타임라인 max(date): {tl_max}")

    if not uploaded_files:
        return

    token = "|".join([f"{f.name}:{len(f.getvalue())}" for f in uploaded_files])
    if st.session_state.get("dm_last_processed_token") == token:
        return
    st.session_state["dm_last_processed_token"] = token

    active_df  = get_active_df()
    has_active = active_df is not None and not active_df.empty
    total_added_rows = total_dropped_days = 0

    with st.sidebar.status("자동 전처리 진행 중...", expanded=False):
        for f in uploaded_files:
            raw_bytes = f.getvalue()
            add_uploaded_file(f.name, raw_bytes)
            df_raw   = load_df_from_bytes(f.name, raw_bytes)
            df_clean = run_preprocess(df_raw, warn_fn=st.sidebar.warning)
            save_clean_df(f.name, df_clean)

            if not has_active:
                set_active_df(df_clean.assign(**{SOURCE_COL: f.name}), f.name)
                active_df  = get_active_df()
                has_active = True
                meta = {
                    "added_rows": int(df_clean.shape[0]), "dropped_duplicate_days": 0,
                    "added_min_date": pd.to_datetime(df_clean["date"],errors="coerce").dropna().min().isoformat()
                        if "date" in df_clean.columns and not df_clean.empty else None,
                    "added_max_date": pd.to_datetime(df_clean["date"],errors="coerce").dropna().max().isoformat()
                        if "date" in df_clean.columns and not df_clean.empty else None,
                }
                patch_clean_meta(f.name, meta)
                st.sidebar.success(f"[{f.name}] 활성 데이터로 설정: {df_clean.shape[0]:,}행")
            else:
                merged, meta = _incremental_append_by_day(active_df, df_clean, source_name=f.name)
                set_active_df(merged, f.name)
                active_df = merged
                total_added_rows  += int(meta.get("added_rows",0) or 0)
                total_dropped_days += int(meta.get("dropped_duplicate_days",0) or 0)
                patch_clean_meta(f.name, meta)
                st.sidebar.success(
                    f"[{f.name}] 병합 완료: +{meta.get('added_rows',0):,}행 "
                    f"(중복날짜 제외 {meta.get('dropped_duplicate_days',0):,}행)"
                )

        st.sidebar.divider()
        st.sidebar.success(f"처리 완료: {len(uploaded_files)}개 파일 / 추가 {total_added_rows:,}행 / 중복 {total_dropped_days:,}행")

    st.rerun()


# ──────────────────────────────────────────────────────────────
# 🏠 홈 필터
# ──────────────────────────────────────────────────────────────

def render_sidebar_filters(df: pd.DataFrame) -> Tuple[pd.Timestamp, pd.Timestamp, List[str]]:
    st.sidebar.header("🔎 필터")
    min_d, max_d = _get_date_bounds(df)

    if "date_range" not in st.session_state:
        st.session_state["date_range"] = (min_d, max_d)

    d0, d1 = st.session_state["date_range"]
    if hasattr(d0,"date"): d0 = d0.date()
    if hasattr(d1,"date"): d1 = d1.date()
    if not isinstance(d0, date) or not isinstance(d1, date):
        d0, d1 = min_d, max_d
    d0 = _clamp_date(d0, min_d, max_d)
    d1 = _clamp_date(d1, min_d, max_d)
    if d0 > d1:
        d0, d1 = min_d, max_d
    st.session_state["date_range"] = (d0, d1)

    if "date_picker" not in st.session_state:
        st.session_state["date_picker"] = (d0, d1)
    if "period_date_range" not in st.session_state:
        st.session_state["period_date_range"] = (d0, d1)

    def _on_change():
        v = st.session_state.get("date_picker")
        if isinstance(v,(tuple,list)) and len(v)==2 and v[0] and v[1] and v[0]<=v[1]:
            s,e = _clamp_date(v[0],min_d,max_d), _clamp_date(v[1],min_d,max_d)
            if s <= e:
                st.session_state["date_range"]       = (s,e)
                st.session_state["period_date_range"] = (s,e)

    date_range = st.sidebar.date_input(
        "📆 분석 기간 선택",
        value=st.session_state["date_range"],
        min_value=min_d, max_value=max_d,
        key="date_picker", on_change=_on_change,
    )

    if isinstance(date_range,(tuple,list)) and len(date_range)==2:
        start_d, end_d = date_range
    else:
        start_d, end_d = st.session_state["date_range"]

    if start_d is None or end_d is None:
        st.sidebar.warning("⚠ 기간은 시작일과 종료일을 모두 선택해 주세요.")
        st.stop()
    if start_d > end_d:
        st.sidebar.warning("⚠ 시작일이 종료일보다 클 수 없습니다.")
        st.stop()

    st.session_state["date_range"] = (start_d, end_d)

    st.sidebar.header("🏷 카테고리")
    df_expense     = df[df["is_expense"]].copy()
    all_categories = sorted(df_expense["category_lv1"].dropna().unique().tolist())
    selected_categories = st.sidebar.multiselect(
        "카테고리 선택 (태그)", options=all_categories, default=all_categories,
    )

    return pd.to_datetime(start_d), pd.to_datetime(end_d), selected_categories


# ──────────────────────────────────────────────────────────────
# 🧠 AI 리포트 날짜 필터 (홈과 키 분리)
# ──────────────────────────────────────────────────────────────

def _render_ai_date_filter(df: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    """
    AI 리포트 전용 날짜 필터.
    - canonical: ai_date_range  (홈의 date_range와 분리)
    - 위젯 키:   ai_date_picker (홈의 date_picker와 분리)
    - on_change 콜백으로만 canonical 갱신 → 매 rerun 덮어쓰기 없음
    """
    s = pd.to_datetime(df["date"], errors="coerce").dropna()
    min_d = s.min().date() if not s.empty else pd.Timestamp.today().date()
    max_d = s.max().date() if not s.empty else pd.Timestamp.today().date()

    if "ai_date_range" not in st.session_state:
        st.session_state["ai_date_range"] = (min_d, max_d)

    d0, d1 = st.session_state["ai_date_range"]
    if hasattr(d0,"date"): d0 = d0.date()
    if hasattr(d1,"date"): d1 = d1.date()
    if not isinstance(d0, date) or not isinstance(d1, date):
        d0, d1 = min_d, max_d
    d0 = _clamp_date(d0, min_d, max_d)
    d1 = _clamp_date(d1, min_d, max_d)
    if d0 > d1:
        d0, d1 = min_d, max_d
    st.session_state["ai_date_range"] = (d0, d1)

    if "ai_date_picker" not in st.session_state:
        st.session_state["ai_date_picker"] = (d0, d1)

    def _on_change():
        v = st.session_state.get("ai_date_picker")
        if isinstance(v,(tuple,list)) and len(v)==2 and v[0] and v[1]:
            s_d, e_d = v[0], v[1]
            if hasattr(s_d,"date"): s_d = s_d.date()
            if hasattr(e_d,"date"): e_d = e_d.date()
            s_d = _clamp_date(s_d, min_d, max_d)
            e_d = _clamp_date(e_d, min_d, max_d)
            if s_d <= e_d:
                st.session_state["ai_date_range"] = (s_d, e_d)

    picked = st.sidebar.date_input(
        "📆 분석 기간 선택",
        value=st.session_state["ai_date_range"],
        min_value=min_d, max_value=max_d,
        key="ai_date_picker", on_change=_on_change,
    )

    if isinstance(picked,(tuple,list)) and len(picked)==2 and picked[0] and picked[1]:
        start_d, end_d = picked[0], picked[1]
    else:
        start_d, end_d = st.session_state["ai_date_range"]

    if hasattr(start_d,"date"): start_d = start_d.date()
    if hasattr(end_d,"date"):   end_d   = end_d.date()

    if start_d > end_d:
        st.sidebar.warning("⚠ 시작일이 종료일보다 클 수 없습니다.")
        st.stop()

    return pd.to_datetime(start_d), pd.to_datetime(end_d)


def render_sidebar_ai_controls(
    *,
    df_all: pd.DataFrame,
    df_expense_filtered: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    persona_result=None,               # ✅ 추가
) -> None:
    init_ai_report_state()
    render_ai_sidebar_controls(
        df_all=df_all,
        df_expense_filtered=df_expense_filtered,
        start_date=start_date,
        end_date=end_date,
        persona_result=persona_result,  # ✅ 전달
    )


# ──────────────────────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────────────────────

def build_sidebar(
    *,
    persona_result=None,               # ✅ streamlit_app에서 넘겨받음
) -> Tuple[str, Optional[pd.Timestamp], Optional[pd.Timestamp], List[str]]:
    page = render_sidebar_menu()

    if page == "🧼 데이터 관리":
        render_data_manage_sidebar_uploader()
        return page, None, None, []

    df = _require_active_df_or_stop()

    # ── 🧠 AI 리포트 ──────────────────────────────────────────
    if page == "🧠 AI 리포트":
        st.sidebar.header("🔎 필터")
        start_date, end_date = _render_ai_date_filter(df)

        df_expense = df[df["is_expense"]].copy()
        render_sidebar_ai_controls(
            df_all=df,
            df_expense_filtered=df_expense,
            start_date=start_date,
            end_date=end_date,
            persona_result=persona_result,   # ✅ 전달
        )
        return page, start_date, end_date, []

    # ── 🏠 홈 ────────────────────────────────────────────────
    start_date, end_date, selected_categories = render_sidebar_filters(df)
    return page, start_date, end_date, selected_categories