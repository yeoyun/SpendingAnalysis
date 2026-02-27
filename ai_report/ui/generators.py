from __future__ import annotations

from dataclasses import asdict

import streamlit as st
import pandas as pd

from ai_report.utils import load_ai_report, make_ai_report_key, save_ai_report

from ..features import build_ai_summary
from ..llm import call_llm_json
from ..prompt import build_messages
from .state import init_ai_report_state, _get_params_from_session


# =========================
# ✅ 생성 로직: 전체 기간
# =========================
def generate_ai_report_all(
    *,
    df_all,
    df_expense_filtered,
    start_date,
    end_date,
    model: str = "gemini-2.5-flash",
):
    """전체 기간 리포트 생성 → session_state['_all']에 저장"""
    init_ai_report_state()

    params = _get_params_from_session()

    with st.spinner("전체 기간 리포트 생성 중..."):
        summary = build_ai_summary(
            df_all=df_all,
            df_expense_filtered=df_expense_filtered,
            start_date=start_date,
            end_date=end_date,
            params=params,
        )

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
            st.success("전체 기간: 캐시된 리포트를 불러왔습니다. (토큰 사용 0)")
            st.rerun()

        messages = build_messages(summary, mode="all")
        result = call_llm_json(messages, model=model)

        st.session_state["ai_report_summary_all"] = summary
        st.session_state["ai_report_result_all"] = result

        save_ai_report(result=result, summary=summary, key=cache_key, mode="all")

    st.success("전체 기간 리포트 생성 완료")
    st.rerun()


# =========================
# ✅ 생성 로직: 단기
# =========================
def generate_ai_report_last_30_days(
    *,
    df_all,
    model: str = "gemini-2.5-flash",
):
    """기준일=데이터 최신 날짜, 최근 30일 단기 리포트 → session_state['_short'] 저장"""
    init_ai_report_state()

    if df_all is None or df_all.empty:
        st.warning("데이터가 없습니다.")
        return

    params = _get_params_from_session()

    df_all = df_all.copy()
    df_all["date"] = pd.to_datetime(df_all["date"], errors="coerce")
    df_all = df_all.dropna(subset=["date"]).copy()

    end_date = df_all["date"].max().normalize()
    start_date = end_date - pd.Timedelta(days=29)

    df_30 = df_all[(df_all["date"] >= start_date) & (df_all["date"] <= end_date)].copy()

    with st.spinner("최근 30일(단기) 리포트 생성 중."):
        summary = build_ai_summary(
            df_all=df_all,          # ✅ baseline(전체 히스토리) 포함 -> short_term_compare 근거 강화
            df_expense_filtered=df_30,
            start_date=start_date,
            end_date=end_date,
            params=params,
        )

        # ✅ 캐시 키(단기)
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
            st.success("단기: 캐시된 리포트를 불러왔습니다. (토큰 사용 0)")
            st.rerun()

        # ✅ 핵심: 단기 프롬프트 적용
        messages = build_messages(summary, mode="short")
        result = call_llm_json(messages, model=model)

        st.session_state["ai_report_summary_short"] = summary
        st.session_state["ai_report_result_short"] = result

        save_ai_report(result=result, summary=summary, key=cache_key, mode="short")

    st.success("최근 30일(단기) 리포트 생성 완료")
    st.rerun()