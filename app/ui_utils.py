# app/ui_utils.py

import streamlit as st
import pandas as pd


def _inject_filter_style():
    st.markdown("""
    <style>
    /* 앵커 다음에 오는 블록(=필터 컨테이너)에 카드 스타일 적용 */
    #period-filter-anchor + div[data-testid="stVerticalBlock"]{
        border:1px solid #F3F4F6;
        border-radius:16px;
        padding:14px 16px 8px 16px;
        background:#FFFFFF;
        box-shadow:0 2px 8px rgba(0,0,0,0.04);
        margin: 6px 0 14px 0;
    }

    /* segmented control */
    div[data-baseweb="segmented-control"]{
        background:#F7F8F9 !important;
        padding:4px !important;
        border-radius:12px !important;
    }
    div[data-baseweb="segmented-control"] button{
        border-radius:10px !important;
        font-weight:600 !important;
        padding:6px 14px !important;
    }

    /* pills */
    div[data-testid="stPills"] > div{
        background:#F7F8F9 !important;
        border-radius:12px !important;
        padding:6px !important;
    }
    div[data-testid="stPills"] button{
        border-radius:999px !important;
        font-weight:600 !important;
        padding:6px 14px !important;
    }

    /* date_input 위쪽 여백 조금 줄이기(선택) */
    div[data-testid="stDateInput"]{
        margin-top: 0px !important;
    }
    </style>
    """, unsafe_allow_html=True)


def render_period_filter(start_date: pd.Timestamp, end_date: pd.Timestamp):
    """
    라디오 없이:
    segmented_control → 없으면 pills → 최후 button 4개

    ✅ date_input 방어:
    - 단일 날짜가 반환되거나(끝 날짜 미선택)
    - tuple/list 길이가 2가 아니거나
    - start/end 중 하나가 None이거나
    - start > end 인 경우
    """
    _inject_filter_style()

    # ✅ 앵커 (이 다음 블록에 카드 CSS가 적용됨)
    st.markdown('<div id="period-filter-anchor"></div>', unsafe_allow_html=True)

    # 기본값(항상 date로)
    default_start = pd.to_datetime(start_date).date()
    default_end = pd.to_datetime(end_date).date()

    with st.container():
        st.markdown("##### 📅 분석 필터")

        col1, col2 = st.columns([1.3, 2], vertical_alignment="center")

        with col1:
            period_type = None

            try:
                period_type = st.segmented_control(
                    "집계 단위",
                    ["년간", "월간", "주간", "일간"],
                    default="월간",
                )
            except Exception:
                period_type = None

            if period_type is None:
                try:
                    period_type = st.pills(
                        "집계 단위",
                        ["년간", "월간", "주간", "일간"],
                        default="월간",
                    )
                except Exception:
                    if "period_type" not in st.session_state:
                        st.session_state["period_type"] = "월간"

                    b1, b2, b3, b4 = st.columns(4)

                    def _set(p):
                        st.session_state["period_type"] = p

                    with b1:
                        st.button("년간", use_container_width=True, on_click=_set, args=("년간",))
                    with b2:
                        st.button("월간", use_container_width=True, on_click=_set, args=("월간",))
                    with b3:
                        st.button("주간", use_container_width=True, on_click=_set, args=("주간",))
                    with b4:
                        st.button("일간", use_container_width=True, on_click=_set, args=("일간",))

                    period_type = st.session_state["period_type"]

        with col2:
            # ✅ 핵심: range 모드라도 단일 date가 돌아올 수 있으니 key를 주고 방어
            selected_range = st.date_input(
                "날짜 선택",
                value=(default_start, default_end),
                label_visibility="collapsed",
                key="period_date_range",
            )

    # =========================
    # ✅ selected_range 정규화/방어
    # =========================
    # 1) 단일 날짜(date / datetime)로 들어온 경우
    if not isinstance(selected_range, (tuple, list)):
        st.warning("⚠ 기간은 시작일과 종료일을 모두 선택해 주세요.")
        st.stop()

    # 2) tuple/list인데 길이가 2가 아닌 경우
    if len(selected_range) != 2:
        st.warning("⚠ 기간 선택이 완성되지 않았습니다. 시작일/종료일을 모두 선택해 주세요.")
        st.stop()

    filter_start, filter_end = selected_range

    # 3) None 방어
    if filter_start is None or filter_end is None:
        st.warning("⚠ 기간은 시작일과 종료일을 모두 선택해 주세요.")
        st.stop()

    # 4) 역전 방어
    if filter_start > filter_end:
        st.warning("⚠ 시작일이 종료일보다 클 수 없습니다.")
        st.stop()

    return period_type, pd.to_datetime(filter_start), pd.to_datetime(filter_end)

def render_period_header(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    *,
    show_icon: bool = True,
    large: bool = True,
) -> None:
    period_text = f"{start_date.strftime('%Y.%m.%d')} ~ {end_date.strftime('%Y.%m.%d')}"
    icon = "📆 " if show_icon else ""

    font_size = "22px" if large else "18px"
    font_weight = "600" if large else "500"

    st.markdown(
        f"""
        <div style="
            margin-top:-6px;
            margin-bottom:14px;
            font-size:{font_size};
            font-weight:{font_weight};
            color:#9CA3AF;
        ">
            {icon}<span>{period_text}</span>
        </div>
        """,
        unsafe_allow_html=True
    )