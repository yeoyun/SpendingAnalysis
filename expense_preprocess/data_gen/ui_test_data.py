# expense_preprocess/data_gen/ui_test_data.py
from __future__ import annotations

from pathlib import Path
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
    """
    Streamlit 테스트 데이터 생성기 UI

    - generate_func만 외부에서 주입받아 실행 (페이지/활성데이터 의존 X)
    - 생성 결과는 session_state cache에 저장 후:
      1) 미리보기
      2) 다운로드 버튼 제공
      3) (옵션) 서버에 csv 저장

    generate_func는 아래 인자를 받을 수 있어야 합니다:
      start_date, end_date, reference_dist, rows_per_day, seed, currency, transfer_pair
    """

    st.divider()
    st.subheader("테스트 데이터 생성")

    with st.expander(expander_title, expanded=True):
        # ✅ 생성 결과 캐시 키
        TEST_CACHE_KEY = cache_key

        col1, col2, col3 = st.columns([1, 1, 1])

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
                value=25,
                step=1,
                key="dm_test_rows_per_day",
            )

        col4, col5, col6 = st.columns([1, 1, 1])
        with col4:
            seed = st.number_input(
                "seed",
                min_value=0,
                max_value=999999,
                value=42,
                step=1,
                key="dm_test_seed",
            )
        with col5:
            currency = st.selectbox(
                "화폐",
                ["KRW", "USD", "JPY"],
                index=0,
                key="dm_test_currency",
            )
        with col6:
            transfer_pair = st.checkbox(
                "이체를 2행(출금/입금) 페어로 생성",
                value=True,
                key="dm_test_transfer_pair",
            )

        st.caption("※ 테스트 데이터는 활성 데이터에 절대 반영되지 않으며, 생성 결과는 CSV로만 내보낼 수 있습니다.")

        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
        preview_btn = col_btn1.button("미리보기 생성", use_container_width=True, key="dm_test_preview_btn")
        download_btn = col_btn2.button("CSV 다운로드 준비", use_container_width=True, key="dm_test_download_ready_btn")
        save_server_btn = col_btn3.button("서버에 CSV 저장", use_container_width=True, key="dm_test_save_server_btn")

        # =========================
        # 1) 미리보기 생성 (활성데이터 참조 X)
        # =========================
        if preview_btn:
            try:
                if pd.Timestamp(end_date) < pd.Timestamp(start_date):
                    st.error("종료일은 시작일보다 빠를 수 없습니다.")
                else:
                    df_test = generate_func(
                        start_date=str(start_date),
                        end_date=str(end_date),
                        reference_dist=None,  # ✅ 활성데이터 참조 X
                        rows_per_day=int(rows_per_day),
                        seed=int(seed),
                        currency=str(currency),
                        transfer_pair=bool(transfer_pair),
                    )
                    st.session_state[TEST_CACHE_KEY] = df_test
                    st.success(f"생성 완료: {df_test.shape[0]:,} rows")
                    st.dataframe(df_test.head(50), use_container_width=True)
            except Exception as e:
                st.error("테스트 데이터 생성 실패")
                st.exception(e)

        # =========================
        # 2) 다운로드 버튼 렌더링 (캐시된 df_test 기반)
        # =========================
        df_cached = st.session_state.get(TEST_CACHE_KEY)

        if isinstance(df_cached, pd.DataFrame) and not df_cached.empty:
            fname = f"test_raw_{start_date}_{end_date}_rows{len(df_cached)}_seed{seed}.csv"

            if download_btn:
                st.info("아래 다운로드 버튼이 활성화되었습니다.")

            csv_bytes = df_cached.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                label="⬇️ 테스트 데이터 다운로드 (.csv)",
                data=csv_bytes,
                file_name=fname,
                mime="text/csv",
                use_container_width=True,
                key="dm_test_download_btn",
            )
        else:
            st.warning("먼저 '미리보기 생성'으로 테스트 데이터를 생성해주세요.")

        # =========================
        # 3) (옵션) 서버 저장
        # =========================
        if save_server_btn:
            try:
                df_cached = st.session_state.get(TEST_CACHE_KEY)
                if not isinstance(df_cached, pd.DataFrame) or df_cached.empty:
                    st.error("저장할 테스트 데이터가 없습니다. 먼저 생성해주세요.")
                else:
                    # ✅ 이 파일 경로: expense_preprocess/data_gen/ui_test_data.py
                    # parents[2] => repo root
                    PROJECT_ROOT = Path(__file__).resolve().parents[2]
                    save_dir = PROJECT_ROOT / save_subdir
                    save_dir.mkdir(parents=True, exist_ok=True)

                    fname = f"test_raw_{start_date}_{end_date}_rows{len(df_cached)}_seed{seed}.csv"
                    save_path = save_dir / fname

                    df_cached.to_csv(save_path, index=False, encoding="utf-8-sig")
                    st.success("서버 저장 완료")
                    st.caption(f"📁 저장 위치: {save_path}")
            except Exception as e:
                st.error("서버 저장 실패")
                st.exception(e)