# expense_preprocess/data_manager/page.py
from __future__ import annotations

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


def _fmt_iso(iso: str | None) -> str:
    return iso if iso else "-"


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
    - 기존에 존재하는 '날짜(date)'는 신규에서 제외하고 나머지는 모두 추가
    - 앞/뒤 기간 모두 허용
    - 이번에 실제 추가된 행에 SOURCE_COL(=__source_file)을 박아 둠 (요구사항 1 삭제 가능)

    return:
      merged_df, merge_meta(dict)
    """
    new_df = ensure_date_col(new_df).copy()
    new_df[SOURCE_COL] = source_name
    new_df["__date_only"] = _date_only_series(new_df["date"])

    # active 없음: 전부 추가
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
        meta = {"added_rows": int(len(new_df)), "dropped_duplicate_days": 0, "added_min_date": None, "added_max_date": None}
        return merged, meta

    active_df["__date_only"] = _date_only_series(active_df["date"])
    existing_days = set(active_df["__date_only"].dropna().unique().tolist())

    # ✅ 날짜 중복만 제외
    dup_mask = new_df["__date_only"].isin(existing_days)
    dropped = int(dup_mask.sum())

    add_part = new_df.loc[~dup_mask].copy()

    merged = pd.concat([active_df, add_part], ignore_index=True)
    merged = merged.sort_values("date").reset_index(drop=True)

    # 내부 컬럼 정리(원하시면 남겨도 됨)
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


def render_data_manage_page() -> None:
    init_data_manager_state()

    st.header("🗂️ 데이터 관리")

    raw_files = get_raw_files()
    upload_log = get_upload_log()
    clean_files = get_clean_files()

    names = sorted(set(upload_log.keys()) | set(clean_files.keys()) | set(raw_files.keys()))

    if not names:
        st.info("업로드된 파일이 없습니다. 좌측 사이드바에서 파일을 업로드해주세요.")
        return
    else:
        st.info("좌측 사이드바에서 데이터 추가가 가능합니다.")

    # =========================
    # 현재 타임라인(활성 데이터 기준)
    # =========================
    active_src = get_active_source()
    df_active = get_active_df()

    c_active = clean_files.get(active_src, None) if active_src else None

    if df_active is None or df_active.empty:
        st.write("- 활성 데이터 없음")
    else:
        min_ts = None
        max_ts = None
        if "date" in df_active.columns:
            s = pd.to_datetime(df_active["date"], errors="coerce").dropna()
            if not s.empty:
                min_ts = s.min()
                max_ts = s.max()

        min_str = min_ts.strftime("%Y-%m-%d") if min_ts is not None else "-"
        max_str = max_ts.strftime("%Y-%m-%d") if max_ts is not None else "-"

        range_min = c_active.get("min_date") if c_active else None
        range_max = c_active.get("max_date") if c_active else None

        st.write(f"##### {(range_min or min_str)} ~ {(range_max or max_str)}")
        st.write(f"- 활성 소스 (마지막 처리 기준): **{active_src or '-'}**")
        st.write(f"- 크기: **{df_active.shape[0]:,} rows × {df_active.shape[1]:,} cols**")

    # =========================
    # 업로드 목록 + 로그/정제 상태
    # =========================
    st.markdown("### 📁 업로드 목록")

    default_idx = 0
    if active_src in names:
        default_idx = names.index(active_src)

    st.markdown("파일 선택")
    colA, colB = st.columns([1.2, 0.8])
    with colA:
        selected = st.selectbox(
            "파일 선택",
            names,
            index=default_idx,
            key="dm_selected",
            label_visibility="collapsed",
        )
    with colB:
        if st.button("🗑️ 선택 파일 삭제", use_container_width=True):
            delete_file(selected)
            st.rerun()

    u = upload_log.get(selected, {})
    c = clean_files.get(selected, None)

    st.write(f"- 업로드 시각: **{_fmt_iso(u.get('uploaded_at'))}** / size: {u.get('size_bytes', 0):,} bytes")
    if c:
        st.write(f"- 정제 rows: **{c.get('rows', 0):,}** / range: {c.get('min_date') or '-'} ~ {c.get('max_date') or '-'}")
        if c.get("added_rows") is not None:
            st.write(
                f"- ✅ 활성 반영(증분) 결과: **추가 {c.get('added_rows', 0):,}행**, "
                f"중복날짜 제외 {c.get('dropped_duplicate_days', 0):,}행 "
                f"/ 추가기간: {c.get('added_min_date') or '-'} ~ {c.get('added_max_date') or '-'}"
            )
    else:
        st.write("- 전처리 상태: 미생성")

    if selected not in raw_files:
        st.warning(
            "이 파일은 업로드/정제 메타(디스크 스냅샷)는 남아있지만, "
            "원본(raw bytes)은 현재 세션에 남지 않습니다.\n\n"
            "원본을 다시 읽고 싶은 경우, 재업로드해주세요."
        )

    st.divider()

    # =========================
    # ✅ 선택 파일 정제 + 활성 데이터 반영 버튼
    # =========================
    st.markdown("### 🧼 선택 파일 정제 & 활성 반영")

    can_process = selected in raw_files
    if not can_process:
        st.info("선택 파일의 원본 bytes가 세션에 없어 정제를 실행할 수 없습니다. 재업로드 후 진행해주세요.")
    else:
        if st.button("✨ 정제 실행 후 활성 데이터에 반영", use_container_width=True, key="dm_run_preprocess_apply"):
            try:
                raw_bytes = raw_files[selected]
                df_raw = load_df_from_bytes(selected, raw_bytes)
                df_clean = run_preprocess(df_raw)

                # 1) clean file 저장(디스크) + 메타 저장
                save_clean_df(selected, df_clean)

                # 2) 활성 데이터에 '날짜 중복만 제외' 증분 반영
                df_active_now = get_active_df()
                merged, merge_meta = _incremental_append_by_day(
                    df_active_now,
                    df_clean,
                    source_name=selected,
                )
                set_active_df(merged, source_name=selected)

                # 3) clean_files 메타에 “증분 반영 결과” 기록
                patch_clean_meta(selected, merge_meta)

                st.success(
                    f"반영 완료! 추가 {merge_meta['added_rows']:,}행 / "
                    f"중복날짜 제외 {merge_meta['dropped_duplicate_days']:,}행"
                )
                st.rerun()

            except Exception as e:
                st.error("정제/반영 중 오류가 발생했습니다.")
                st.exception(e)

    st.divider()

    # =========================================================
    # ✅ 테스트 데이터 생성 UI
    # =========================================================
    render_test_data_generator(
        generate_func=generate_test_raw_df,
        cache_key="dm_test_df_cache",
        expander_title="기간 입력 기반 테스트 데이터 생성기",
        default_days=30,
        save_subdir="data/test_generated",
    )

    st.divider()

    # =========================
    # 현재 활성 데이터 미리보기
    # =========================
    df_active = get_active_df()
    if df_active is None or df_active.empty:
        st.warning("현재 활성 데이터가 없습니다.")
        return

    with st.expander("미리보기 (상위 50행)"):
        st.dataframe(df_active.head(50), use_container_width=True)

    # ✅ 전체 삭제 버튼(하단 단일)
    if st.button("🧨 전체 데이터 삭제", use_container_width=True, key="dm_clear_all_bottom"):
        clear_all()
        st.rerun()
        return

    # =========================
    # 내보내기: 파일명 = 데이터 기간(min~max)
    # =========================
    min_ts = None
    max_ts = None
    if "date" in df_active.columns:
        s = pd.to_datetime(df_active["date"], errors="coerce").dropna()
        if not s.empty:
            min_ts = s.min()
            max_ts = s.max()

    min_str = min_ts.strftime("%Y-%m-%d") if min_ts is not None else None
    max_str = max_ts.strftime("%Y-%m-%d") if max_ts is not None else None

    if min_str and max_str:
        export_name = f"active_{min_str}.csv" if min_str == max_str else f"active_{min_str}_{max_str}.csv"
    else:
        export_name = "active_data.csv"

    from pathlib import Path
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    save_dir = PROJECT_ROOT / "data" / "active"
    save_dir.mkdir(parents=True, exist_ok=True)

    save_path = save_dir / export_name

    try:
        df_active.to_csv(save_path, index=False, encoding="utf-8-sig")
        st.caption(f"📁 저장 위치: {save_path}")
    except Exception as e:
        st.warning("서버 저장에 실패했습니다. (권한/경로 문제 가능)")
        st.exception(e)

    csv_bytes = df_active.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        label="⬇️ 데이터 내보내기 (.csv)",
        data=csv_bytes,
        file_name=export_name,
        mime="text/csv",
        use_container_width=True,
        key="dm_export_active_csv",
    )