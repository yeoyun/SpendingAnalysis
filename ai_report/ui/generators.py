from __future__ import annotations

from dataclasses import asdict
import time

import streamlit as st
import pandas as pd

from ai_report.utils import load_ai_report, make_ai_report_key, save_ai_report

from ..features import build_ai_summary
from ..llm import call_llm_json
from ..prompt import build_messages
from .state import init_ai_report_state, _get_params_from_session


def _fmt_sec(x: float) -> str:
    return f"{x:.1f}s"


def generate_ai_report_all(
    *,
    df_all,
    df_expense_filtered,
    start_date,
    end_date,
    model: str = "gemini-2.5-flash",
):
    init_ai_report_state()
    params = _get_params_from_session()

    # ✅ 빠른 진단용: 데이터 크기
    try:
        st.caption(
            f"DEBUG: df_all={len(df_all):,} rows / df_expense_filtered={len(df_expense_filtered):,} rows"
        )
    except Exception:
        pass

    status = st.status("전체 기간 리포트 생성 준비 중...", expanded=True)
    t0 = time.perf_counter()

    try:
        status.update(label="1/4 요약(Features) 생성 중...", state="running")
        t1 = time.perf_counter()
        summary = build_ai_summary(
            df_all=df_all,
            df_expense_filtered=df_expense_filtered,
            start_date=start_date,
            end_date=end_date,
            params=params,
        )
        status.write(f"✅ 요약 생성 완료: {_fmt_sec(time.perf_counter() - t1)}")

        # ✅ 캐시 키(전체)
        try:
            params_dict = asdict(params)
        except Exception:
            params_dict = {
                "overspend_ratio_ok": params.overspend_ratio_ok,
                "overspend_ratio_warn": params.overspend_ratio_warn,
                "late_hour_start": params.late_hour_start,
                "small_tx_threshold": params.small_tx_threshold,
            }
        params_dict["mode"] = "all"

        status.update(label="2/4 캐시 확인 중...", state="running")
        cache_key = make_ai_report_key(
            summary=summary,
            params_dict=params_dict,
            model=model,
            version="v2_all",
        )

        cached_result, cached_summary = load_ai_report(key=cache_key, mode="all")
        if isinstance(cached_result, dict) and cached_result:
            st.session_state["ai_report_summary_all"] = cached_summary or summary
            st.session_state["ai_report_result_all"] = cached_result
            status.update(label=f"✅ 캐시 로드 완료 (총 {_fmt_sec(time.perf_counter()-t0)})", state="complete")
            st.success("전체 기간: 캐시된 리포트를 불러왔습니다. (토큰 사용 0)")
            st.rerun()

        status.update(label="3/4 프롬프트 구성 중...", state="running")
        messages = build_messages(summary, mode="all")
        status.write("✅ 프롬프트 구성 완료")

        status.update(label="4/4 LLM 호출 중... (네트워크/모델 응답 대기)", state="running")
        t2 = time.perf_counter()
        result = call_llm_json(messages, model=model)  # llm.py에서 timeout/retry 적용 권장
        status.write(f"✅ LLM 응답 완료: {_fmt_sec(time.perf_counter() - t2)}")

        st.session_state["ai_report_summary_all"] = summary
        st.session_state["ai_report_result_all"] = result

        status.update(label="저장 중...", state="running")
        save_ai_report(result=result, summary=summary, key=cache_key, mode="all")

        status.update(label=f"✅ 전체 완료 (총 {_fmt_sec(time.perf_counter()-t0)})", state="complete")
        st.success("전체 기간 리포트 생성 완료")
        st.rerun()

    except Exception as e:
        status.update(label="❌ 생성 실패", state="error")
        st.error("AI 리포트 생성 중 오류가 발생했습니다. 아래 에러를 확인해주세요.")
        st.exception(e)
        return


def generate_ai_report_last_30_days(
    *,
    df_all,
    model: str = "gemini-2.5-flash",
):
    init_ai_report_state()

    if df_all is None or df_all.empty:
        st.warning("데이터가 없습니다.")
        return

    params = _get_params_from_session()

    status = st.status("최근 30일 리포트 생성 준비 중...", expanded=True)
    t0 = time.perf_counter()

    try:
        df_all = df_all.copy()
        df_all["date"] = pd.to_datetime(df_all["date"], errors="coerce")
        df_all = df_all.dropna(subset=["date"]).copy()

        end_date = df_all["date"].max().normalize()
        start_date = end_date - pd.Timedelta(days=29)
        df_30 = df_all[(df_all["date"] >= start_date) & (df_all["date"] <= end_date)].copy()

        status.write(f"DEBUG: df_all={len(df_all):,}, df_30={len(df_30):,}, range={start_date.date()}~{end_date.date()}")

        status.update(label="1/4 요약(Features) 생성 중...", state="running")
        t1 = time.perf_counter()
        summary = build_ai_summary(
            df_all=df_all,
            df_expense_filtered=df_30,
            start_date=start_date,
            end_date=end_date,
            params=params,
        )
        status.write(f"✅ 요약 생성 완료: {_fmt_sec(time.perf_counter() - t1)}")

        try:
            params_dict = asdict(params)
        except Exception:
            params_dict = {
                "overspend_ratio_ok": params.overspend_ratio_ok,
                "overspend_ratio_warn": params.overspend_ratio_warn,
                "late_hour_start": params.late_hour_start,
                "small_tx_threshold": params.small_tx_threshold,
            }
        params_dict["mode"] = "short"
        params_dict["window_days"] = 30

        status.update(label="2/4 캐시 확인 중...", state="running")
        cache_key = make_ai_report_key(
            summary=summary,
            params_dict=params_dict,
            model=model,
            version="v2_short",
        )

        cached_result, cached_summary = load_ai_report(key=cache_key, mode="short")
        if isinstance(cached_result, dict) and cached_result:
            st.session_state["ai_report_summary_short"] = cached_summary or summary
            st.session_state["ai_report_result_short"] = cached_result
            status.update(label=f"✅ 캐시 로드 완료 (총 {_fmt_sec(time.perf_counter()-t0)})", state="complete")
            st.success("단기: 캐시된 리포트를 불러왔습니다. (토큰 사용 0)")
            st.rerun()

        status.update(label="3/4 프롬프트 구성 중...", state="running")
        messages = build_messages(summary, mode="short")
        status.write("✅ 프롬프트 구성 완료")

        status.update(label="4/4 LLM 호출 중...", state="running")
        t2 = time.perf_counter()
        result = call_llm_json(messages, model=model)
        status.write(f"✅ LLM 응답 완료: {_fmt_sec(time.perf_counter() - t2)}")

        st.session_state["ai_report_summary_short"] = summary
        st.session_state["ai_report_result_short"] = result
        save_ai_report(result=result, summary=summary, key=cache_key, mode="short")

        status.update(label=f"✅ 전체 완료 (총 {_fmt_sec(time.perf_counter()-t0)})", state="complete")
        st.success("최근 30일(단기) 리포트 생성 완료")
        st.rerun()

    except Exception as e:
        status.update(label="❌ 생성 실패", state="error")
        st.error("최근 30일 리포트 생성 중 오류가 발생했습니다.")
        st.exception(e)
        return