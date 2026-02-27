# expense_preprocess/data_gen/ui_test_data.py
from __future__ import annotations
from typing import Callable

import pandas as pd
import streamlit as st


def render_test_data_generator(
    *,
    generate_func: Callable[..., pd.DataFrame],
    cache_key: str = "dm_test_df_cache",
    expander_title: str = "기간 입력 기반 테스트 데이터 생성기",
    default_days: int = 30,
    save_subdir: str = "data/test_generated",
) -> None:

    st.markdown("### 테스트 데이터 생성")

    TEST_CACHE_KEY = cache_key

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    with col1:
        start_date = st.date_input(
            "시작일",
            value=pd.Timestamp.today().date(),
            key="dm_test_start_date",
        )
    with col2:
        end_date = st.date_input(
            "종료일",
            value=(pd.Timestamp.today() + pd.Timedelta(days=int(default_days))).date(),
            key="dm_test_end_date",
        )
    with col3:
        rows_per_day = st.number_input(
            "일별 생성 개수",
            min_value=1,
            max_value=500,
            value=10,
            step=1,
            key="dm_test_rows_per_day",
        )
    with col4:
        seed = st.number_input(
            "seed",
            min_value=0,
            max_value=999999,
            value=42,
            step=1,
            key="dm_test_seed",
            help="동일한 seed 값을 입력하면 항상 같은 데이터가 생성됩니다. 재현 가능한 테스트가 필요할 때 고정해서 사용하세요.",
        )

    st.caption("테스트 데이터는 활성 데이터에 반영되지 않으며 CSV로만 내보낼 수 있습니다.")

    # ── 생성 버튼 ──────────────────────────────
    if st.button("테스트 데이터 생성", width="stretch", key="dm_test_preview_btn"):
        try:
            if pd.Timestamp(end_date) < pd.Timestamp(start_date):
                st.error("종료일은 시작일보다 빠를 수 없습니다.")
            else:
                with st.spinner("생성 중..."):
                    df_test = generate_func(
                        start_date=str(start_date),
                        end_date=str(end_date),
                        reference_dist=None,
                        rows_per_day=int(rows_per_day),
                        seed=int(seed),
                        currency="KRW",
                        transfer_pair=True,
                    )
                st.session_state[TEST_CACHE_KEY] = df_test
                st.success(f"생성 완료 — {df_test.shape[0]:,}개 행")
                st.dataframe(df_test.head(50), width="stretch")
        except Exception as e:
            st.error("테스트 데이터 생성 실패")
            st.exception(e)

    # ── 다운로드 버튼 ──────────────────────────
    df_cached = st.session_state.get(TEST_CACHE_KEY)
    if isinstance(df_cached, pd.DataFrame) and not df_cached.empty:
        fname = f"test_{start_date}_{end_date}_rows{len(df_cached)}_seed{seed}.csv"
        csv_bytes = df_cached.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            label="💾 테스트 데이터 다운로드 (.csv)",
            data=csv_bytes,
            file_name=fname,
            mime="text/csv",
            width="stretch",
            key="dm_test_download_btn",
        )