# ai_report/ui/sidebar.py
from __future__ import annotations

from pathlib import Path

import streamlit as st

from .helpers import _label_with_tooltip
from .state import init_ai_report_state
from .generators import generate_ai_report_all, generate_ai_report_last_30_days
from ..export import build_md_bytes, build_md_filename

DEFAULT_CACHE_DIR = Path("ai_cache")


# ──────────────────────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────────────────────

def _clear_cache_files(cache_dir: Path = DEFAULT_CACHE_DIR) -> int:
    """ai_cache/{all,short,legacy}/*.json 삭제. 삭제 수 반환."""
    removed = 0
    for sub in ("all", "short", "legacy"):
        sub_dir = cache_dir / sub
        if sub_dir.exists():
            for f in sub_dir.glob("report_*.json"):
                try:
                    f.unlink()
                    removed += 1
                except Exception:
                    pass
    return removed


def _has_report() -> bool:
    return (
        bool(isinstance(st.session_state.get("ai_report_result_all"),   dict)
             and st.session_state["ai_report_result_all"])
        or
        bool(isinstance(st.session_state.get("ai_report_result_short"), dict)
             and st.session_state["ai_report_result_short"])
    )


# ──────────────────────────────────────────────────────────────
# 공개 함수
# ──────────────────────────────────────────────────────────────

def render_ai_sidebar_controls(
    *,
    df_all,
    df_expense_filtered,
    start_date,
    end_date,
    model: str = "gemini-2.5-flash",
    # ✅ 페르소나 결과: streamlit_app에서 넘겨받음
    persona_result=None,
) -> None:
    """
    사이드바: 리포트 설정 + (전체/단기) 생성 + MD 내보내기 + 초기화
    """
    init_ai_report_state()

    st.sidebar.subheader("🧠 AI 리포트")

    # ── 리포트 설정 ──────────────────────────────────────────
    with st.sidebar.expander("리포트 설정", expanded=False):
        _label_with_tooltip(
            "정상 소비율 상한(지출/예상수입)",
            "지출/예상수입 비율이 이 값 이하이면 '정상'으로 판단합니다.",
        )
        st.slider(
            "정상 소비율 상한", 0.30, 0.80, 0.55, 0.01,
            key="ai_overspend_ok", label_visibility="collapsed",
        )
        _label_with_tooltip(
            "주의 소비율 상한(지출/예상수입)",
            "정상 상한 초과~이 값 이하 '주의', 초과 시 '경고'",
        )
        st.slider(
            "주의 소비율 상한", 0.40, 1.00, 0.70, 0.01,
            key="ai_overspend_warn", label_visibility="collapsed",
        )
        _label_with_tooltip("야간 기준 시간", "이 시간 이후 결제를 야간 소비로 분류합니다.")
        st.slider(
            "야간 기준 시간", 20, 24, 22, 1,
            key="ai_late_hour", label_visibility="collapsed",
        )
        _label_with_tooltip("소액 결제 기준(원)", "이 금액 이하 결제를 소액 결제로 분류합니다.")
        st.number_input(
            "소액 결제 기준", min_value=1_000, max_value=100_000,
            value=10_000, step=1_000,
            key="ai_small_tx", label_visibility="collapsed",
        )

    st.sidebar.markdown("---")

    # ── 생성 버튼 ────────────────────────────────────────────
    c1, c2 = st.sidebar.columns(2)
    with c1:
        run_all   = st.button("📊 전체 생성",  key="sb_run_all",   width="stretch")
    with c2:
        run_short = st.button("🗓️ 단기 생성", key="sb_run_short", width="stretch")

    st.sidebar.markdown("")

    # ── MD 내보내기 ──────────────────────────────────────────
    if _has_report():
        md_bytes = build_md_bytes(
            start_date=start_date,
            end_date=end_date,
            persona_result=persona_result,
            result_all=st.session_state.get("ai_report_result_all"),
            summary_all=st.session_state.get("ai_report_summary_all"),
            result_short=st.session_state.get("ai_report_result_short"),
            summary_short=st.session_state.get("ai_report_summary_short"),
        )
        st.sidebar.download_button(
            label="📄 MD 리포트 내보내기",
            data=md_bytes,
            file_name=build_md_filename(),
            mime="text/markdown",
            key="sb_export_md",
            width="stretch",
            help="전체/단기 리포트 + 페르소나를 Markdown 파일로 저장합니다.",
        )
    else:
        st.sidebar.button(
            "📄 MD 리포트 내보내기",
            key="sb_export_md_disabled",
            width="stretch",
            disabled=True,
            help="리포트를 먼저 생성해야 내보낼 수 있습니다.",
        )

    # ── 초기화 버튼 ──────────────────────────────────────────
    clear = st.sidebar.button(
        "🧹 리포트 초기화",
        key="sb_clear_reports",
        width="stretch",
    )

    if clear:
        for key in (
            "ai_report_result",      "ai_report_summary",
            "ai_report_result_all",  "ai_report_summary_all",
            "ai_report_result_short","ai_report_summary_short",
        ):
            st.session_state[key] = None

        removed = _clear_cache_files()
        st.sidebar.success(f"초기화 완료 (캐시 {removed}개 삭제)")
        st.rerun()

    # ── 실행 ─────────────────────────────────────────────────
    if run_all:
        generate_ai_report_all(
            df_all=df_all,
            df_expense_filtered=df_expense_filtered,
            start_date=start_date,
            end_date=end_date,
            model=model,
        )

    if run_short:
        generate_ai_report_last_30_days(
            df_all=df_all,
            model=model,
        )