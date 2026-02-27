# app/sidebar.py

from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import Tuple, List

from expense_preprocess.data_manager.state import get_active_df
from ai_report.ui import init_ai_report_state, render_ai_sidebar_controls

try:
    from streamlit_option_menu import option_menu
except Exception:
    option_menu = None

from datetime import date

def _clamp_date(d: date, min_d: date, max_d: date) -> date:
    if d < min_d:
        return min_d
    if d > max_d:
        return max_d
    return d

def _get_date_bounds(df: pd.DataFrame) -> tuple[date, date]:
    # ✅ 안전한 min/max: 전체를 datetime 변환 → NaT 제거 → min/max
    s = pd.to_datetime(df["date"], errors="coerce").dropna()
    if s.empty:
        # 데이터가 이상하면 오늘로 fallback (앱이 죽는 것 방지)
        today = pd.Timestamp.today().date()
        return today, today

    return s.min().date(), s.max().date()

def _get_clamped_default_range(df: pd.DataFrame, state_key: str) -> tuple[date, date]:
    min_d, max_d = _get_date_bounds(df)

    prev = st.session_state.get(state_key)
    if isinstance(prev, (list, tuple)) and len(prev) == 2:
        d0, d1 = prev

        # Timestamp/Datetime -> date로 정리
        if hasattr(d0, "date"):
            d0 = d0.date()
        if hasattr(d1, "date"):
            d1 = d1.date()

        if isinstance(d0, date) and isinstance(d1, date):
            d0 = _clamp_date(d0, min_d, max_d)
            d1 = _clamp_date(d1, min_d, max_d)
            if d0 > d1:
                return (min_d, max_d)
            return (d0, d1)

    # 세션값이 없거나 이상하면 데이터 범위로
    return (min_d, max_d)


def render_sidebar_menu() -> str:
    """
    좌측 네비게이션 메뉴(카테고리 느낌)
    return: page string
    """
    with st.sidebar:
        st.markdown("## 📌 메뉴")

        # ✅ '데이터 관리'를 마지막에 두고, 그 위에 구분선(시각적) 추가
        st.markdown(
            """
            <style>
            /* streamlit-option-menu 내부 링크(메뉴 항목) 중 3번째(=데이터 관리) 위에 구분선 */
            div[data-testid="stSidebar"] .nav.nav-pills > li:nth-child(3){
                margin-top: 8px !important;
                padding-top: 8px !important;
                border-top: 1px solid #E5E7EB !important; /* GRAY-200 */
            }
            </style>
            """,
            unsafe_allow_html=True
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
                    "icon": {"font-size": "16px"},
                    "nav-link": {
                        "font-size": "15px",
                        "padding": "10px 12px",
                        "border-radius": "10px",
                    },
                    "nav-link-selected": {"font-weight": "700"},
                },
            )
        else:
            # 설치 안 되어 있어도 동작하도록 fallback (구분선은 못 넣음)
            page = st.selectbox("이동", ["🏠 홈", "🧠 AI 리포트", "🧼 데이터 관리"])

        st.divider()

    return page

def _require_active_df_or_stop() -> pd.DataFrame:
    df = get_active_df()
    if df is None or df.empty:
        st.sidebar.info("먼저 ‘🧼 데이터 관리’에서 데이터를 업로드/전처리 후 활성화해주세요.")
        st.stop()
    return df


def render_data_manage_sidebar_uploader() -> None:
    """
    ✅ 데이터관리 페이지에서만 보이는 사이드바 업로더 동작 정책

    - 파일 선택(업로드) 즉시 자동 전처리/증분 반영 (추가 버튼 없음)
    - 중복 rerun으로 같은 파일이 반복 처리되지 않도록 토큰으로 방지
    - ✅ 증분 정책: 기존에 존재하는 '날짜(YYYY-MM-DD)'만 제외하고 나머지는 모두 추가
    - ✅ 삭제 정책을 위해: 이번 파일로 추가된 행에 __source_file 기록
    """

    import pandas as pd
    import streamlit as st

    from expense_preprocess.preprocess import run_preprocess
    from expense_preprocess.data_manager.state import (
        add_uploaded_file,
        get_raw_files,
        save_clean_df,
        set_active_df,
        get_active_df,
        get_timeline_max_date,
        get_active_source,
        patch_clean_meta,
        SOURCE_COL,
    )
    from expense_preprocess.data_manager.io import ensure_date_col, load_df_from_bytes

    def _date_only_series(s: pd.Series) -> pd.Series:
        d = pd.to_datetime(s, errors="coerce")
        return d.dt.date.astype(str)

    def _incremental_append_by_day(
        active_df: pd.DataFrame | None,
        new_df: pd.DataFrame,
        *,
        source_name: str,
    ) -> tuple[pd.DataFrame, dict]:
        """
        ✅ 요구사항 3:
        - 기존 active_df에 존재하는 'date(날짜)'는 new_df에서 제외하고 나머지는 전부 추가
        - 앞/뒤 기간 모두 허용
        - 이번에 실제 추가된 행에 SOURCE_COL(=__source_file) 박아둠 (요구사항 1 삭제 대응)

        return: merged_df, meta(dict)
        """
        new_df = ensure_date_col(new_df).copy()
        new_df[SOURCE_COL] = source_name
        new_df["__date_only"] = _date_only_series(new_df["date"])

        # active 없음: 전부 추가
        if active_df is None or active_df.empty:
            merged = new_df.sort_values("date").reset_index(drop=True)
            added_min = pd.to_datetime(new_df["date"], errors="coerce").dropna().min()
            added_max = pd.to_datetime(new_df["date"], errors="coerce").dropna().max()
            meta = {
                "added_rows": int(len(new_df)),
                "dropped_duplicate_days": 0,
                "added_min_date": (added_min.isoformat() if added_min is not None and pd.notna(added_min) else None),
                "added_max_date": (added_max.isoformat() if added_max is not None and pd.notna(added_max) else None),
            }
            merged = merged.drop(columns=["__date_only"], errors="ignore")
            return merged, meta

        active_df = ensure_date_col(active_df).copy()

        if "date" not in active_df.columns:
            merged = pd.concat([active_df, new_df], ignore_index=True)
            meta = {"added_rows": int(len(new_df)), "dropped_duplicate_days": 0, "added_min_date": None, "added_max_date": None}
            merged = merged.drop(columns=["__date_only"], errors="ignore")
            return merged, meta

        active_df["__date_only"] = _date_only_series(active_df["date"])
        existing_days = set(active_df["__date_only"].dropna().unique().tolist())

        dup_mask = new_df["__date_only"].isin(existing_days)
        dropped = int(dup_mask.sum())

        add_part = new_df.loc[~dup_mask].copy()

        merged = pd.concat([active_df, add_part], ignore_index=True)
        merged = merged.sort_values("date").reset_index(drop=True)

        # 내부 컬럼 정리
        merged = merged.drop(columns=["__date_only"], errors="ignore")

        added_min = None
        added_max = None
        if len(add_part) > 0:
            added_min = pd.to_datetime(add_part["date"], errors="coerce").dropna().min()
            added_max = pd.to_datetime(add_part["date"], errors="coerce").dropna().max()

        meta = {
            "added_rows": int(len(add_part)),
            "dropped_duplicate_days": dropped,
            "added_min_date": (added_min.isoformat() if added_min is not None and pd.notna(added_min) else None),
            "added_max_date": (added_max.isoformat() if added_max is not None and pd.notna(added_max) else None),
        }
        return merged, meta

    # -------------------------
    # UI
    # -------------------------
    st.sidebar.header("🗂️ 데이터 추가하기")

    uploaded_files = st.sidebar.file_uploader(
        "파일 추가하기 (CSV / Excel)",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        key="dm_uploader_sidebar",
    )

    # 상태 요약
    raw_count = len(get_raw_files() or {})
    tl_max = get_timeline_max_date()
    active_src = get_active_source()

    st.sidebar.caption(f"📦 업로드된 파일 수(세션): {raw_count}개")
    if tl_max is None:
        st.sidebar.caption("⏱️ 활성 타임라인: 없음")
    else:
        st.sidebar.caption(f"⏱️ 활성 소스: {active_src}")
        st.sidebar.caption(f"⏱️ 타임라인 max(date): {tl_max}")

    if not uploaded_files:
        return

    # ✅ rerun 중복 처리 방지 토큰 (파일명+바이트크기)
    token = "|".join([f"{f.name}:{len(f.getvalue())}" for f in uploaded_files])
    if st.session_state.get("dm_last_processed_token") == token:
        return
    st.session_state["dm_last_processed_token"] = token

    # -------------------------
    # 업로드 즉시 처리(자동 전처리/증분)
    # -------------------------
    active_df = get_active_df()
    has_active = active_df is not None and not active_df.empty

    with st.sidebar.status("자동 전처리 진행 중...", expanded=False):
        total_files = 0
        total_added_rows = 0
        total_dropped_days = 0

        for f in uploaded_files:
            total_files += 1

            # 1) raw 저장(목록/로그 유지)
            raw_bytes = f.getvalue()
            add_uploaded_file(f.name, raw_bytes)

            # 2) 전처리
            #    (run_preprocess는 UploadedFile도 받지만, bytes->df로 안정적으로 처리하고 싶으면 아래 방식이 더 안전)
            df_raw = load_df_from_bytes(f.name, raw_bytes)
            df_clean = run_preprocess(df_raw, warn_fn=st.sidebar.warning)

            # 3) 정제파일 저장(파일별)
            save_clean_df(f.name, df_clean)

            # 4) 활성 데이터 갱신(✅ 날짜 중복만 제외)
            if not has_active:
                set_active_df(df_clean.assign(**{SOURCE_COL: f.name}), f.name)
                active_df = get_active_df()
                has_active = True

                # meta 기록(첫 활성은 전부 추가)
                meta = {
                    "added_rows": int(df_clean.shape[0]),
                    "dropped_duplicate_days": 0,
                    "added_min_date": pd.to_datetime(df_clean["date"], errors="coerce").dropna().min().isoformat()
                        if "date" in df_clean.columns and not df_clean.empty else None,
                    "added_max_date": pd.to_datetime(df_clean["date"], errors="coerce").dropna().max().isoformat()
                        if "date" in df_clean.columns and not df_clean.empty else None,
                }
                patch_clean_meta(f.name, meta)

                st.sidebar.success(f"[{f.name}] 활성 데이터로 설정: {df_clean.shape[0]:,}행")
            else:
                merged, meta = _incremental_append_by_day(active_df, df_clean, source_name=f.name)
                set_active_df(merged, f.name)
                active_df = merged

                total_added_rows += int(meta.get("added_rows", 0) or 0)
                total_dropped_days += int(meta.get("dropped_duplicate_days", 0) or 0)

                patch_clean_meta(f.name, meta)

                st.sidebar.success(
                    f"[{f.name}] 병합 완료: +{meta.get('added_rows', 0):,}행 "
                    f"(중복날짜 제외 {meta.get('dropped_duplicate_days', 0):,}행) → 총 {merged.shape[0]:,}행"
                )

        st.sidebar.divider()
        st.sidebar.success(
            f"처리 완료: {total_files}개 파일 / "
            f"추가 합계 {total_added_rows:,}행 / "
            f"중복날짜 제외 합계 {total_dropped_days:,}행"
        )

    st.rerun()
    

def render_sidebar_filters(df: pd.DataFrame) -> Tuple[pd.Timestamp, pd.Timestamp, List[str]]:
    st.sidebar.header("🔎 필터")

    # df 기반 min/max
    min_d, max_d = _get_date_bounds(df)

    # ✅ canonical: date_range (date, date)만 단일 진실로 사용
    if "date_range" not in st.session_state:
        st.session_state["date_range"] = (min_d, max_d)

    # canonical 클램프
    d0, d1 = st.session_state["date_range"]
    if hasattr(d0, "date"):
        d0 = d0.date()
    if hasattr(d1, "date"):
        d1 = d1.date()

    if not isinstance(d0, date) or not isinstance(d1, date):
        d0, d1 = (min_d, max_d)

    d0 = _clamp_date(d0, min_d, max_d)
    d1 = _clamp_date(d1, min_d, max_d)
    if d0 > d1:
        d0, d1 = (min_d, max_d)

    st.session_state["date_range"] = (d0, d1)

    # ✅ 위젯 키는 "없을 때만" 초기화 (매 rerun 덮어쓰기 금지!)
    if "date_picker" not in st.session_state:
        st.session_state["date_picker"] = st.session_state["date_range"]
    if "period_date_range" not in st.session_state:
        st.session_state["period_date_range"] = st.session_state["date_range"]

    def _on_change_sidebar_date():
        v = st.session_state.get("date_picker")
        if isinstance(v, (tuple, list)) and len(v) == 2 and v[0] and v[1] and v[0] <= v[1]:
            s, e = v
            s = _clamp_date(s, min_d, max_d)
            e = _clamp_date(e, min_d, max_d)
            if s <= e:
                # ✅ canonical 갱신
                st.session_state["date_range"] = (s, e)
                # ✅ 상단 위젯도 "콜백에서만" 동기화
                st.session_state["period_date_range"] = (s, e)

    date_range = st.sidebar.date_input(
        "📆 분석 기간 선택",
        value=st.session_state["date_range"],  # canonical
        min_value=min_d,
        max_value=max_d,
        key="date_picker",
        on_change=_on_change_sidebar_date,
    )

    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start_d, end_d = date_range
    else:
        start_d, end_d = st.session_state["date_range"]

    if start_d is None or end_d is None:
        st.sidebar.warning("⚠ 기간은 시작일과 종료일을 모두 선택해 주세요.")
        st.stop()

    if start_d > end_d:
        st.sidebar.warning("⚠ 시작일이 종료일보다 클 수 없습니다.")
        st.stop()

    # ✅ canonical 저장만 (여기서 period_date_range 덮어쓰기 금지)
    st.session_state["date_range"] = (start_d, end_d)

    # 앱 내부 로직에서는 Timestamp로 통일
    start_date = pd.to_datetime(start_d)
    end_date = pd.to_datetime(end_d)

    st.sidebar.header("🏷 카테고리")

    df_expense = df[df["is_expense"]].copy()
    all_categories = sorted(df_expense["category_lv1"].dropna().unique().tolist())

    selected_categories = st.sidebar.multiselect(
        "카테고리 선택 (태그)",
        options=all_categories,
        default=all_categories,
    )

    return start_date, end_date, selected_categories



def render_sidebar_ai_controls(
    *,
    df_all: pd.DataFrame,
    df_expense_filtered: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> None:
    init_ai_report_state()
    render_ai_sidebar_controls(
        df_all=df_all,
        df_expense_filtered=df_expense_filtered,
        start_date=start_date,
        end_date=end_date,
    )


def build_sidebar() -> Tuple[str, pd.Timestamp | None, pd.Timestamp | None, List[str]]:
    page = render_sidebar_menu()

    # 🧼 데이터 관리
    if page == "🧼 데이터 관리":
        render_data_manage_sidebar_uploader()
        return page, None, None, []

    # 🏠 홈 / 🧠 AI 리포트 공통: 활성 df 필요
    df = _require_active_df_or_stop()

    # =========================
    # 🧠 AI 리포트 → 카테고리 필터 숨김
    # =========================
    if page == "🧠 AI 리포트":
        st.sidebar.header("🔎 필터")

        s = pd.to_datetime(df["date"], errors="coerce").dropna()
        min_d = s.min().date() if not s.empty else pd.Timestamp.today().date()
        max_d = s.max().date() if not s.empty else pd.Timestamp.today().date()

        # canonical(date,date)
        if "date_range" not in st.session_state:
            st.session_state["date_range"] = (min_d, max_d)

        # 위젯 키 동기화
        st.session_state["date_picker"] = st.session_state["date_range"]
        st.session_state["period_date_range"] = st.session_state["date_range"]

        date_range = st.sidebar.date_input(
            "📆 분석 기간 선택",
            value=st.session_state["date_range"],
            min_value=min_d,
            max_value=max_d,
            key="date_picker",
        )

        if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
            start_d, end_d = date_range
        else:
            start_d, end_d = st.session_state["date_range"]

        if start_d > end_d:
            st.sidebar.warning("⚠ 시작일이 종료일보다 클 수 없습니다.")
            st.stop()

        # canonical 저장(항상 date,date)
        st.session_state["date_range"] = (start_d, end_d)
        st.session_state["period_date_range"] = (start_d, end_d)

        start_date = pd.to_datetime(start_d)
        end_date = pd.to_datetime(end_d)

        df_expense = df[df["is_expense"]].copy()
        render_sidebar_ai_controls(
            df_all=df,
            df_expense_filtered=df_expense,
            start_date=start_date,
            end_date=end_date,
        )

        return page, start_date, end_date, []

    # =========================
    # 🏠 홈 → 기존 필터 유지 (카테고리 포함)
    # =========================
    start_date, end_date, selected_categories = render_sidebar_filters(df)
    return page, start_date, end_date, selected_categories