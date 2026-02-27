# app/ui_utils.py

import streamlit as st
import pandas as pd


def _inject_filter_style():
    st.markdown(
        """
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

    /* date_input 위쪽 여백 조금 줄이기 */
    div[data-testid="stDateInput"]{
        margin-top: 0px !important;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

def _safe_segmented(label: str, options: list[str], default: str, key: str):
    """
    segmented_control -> pills -> fallback selectbox
    - label은 접근성용으로만 남기고 화면에는 숨김(label_visibility="collapsed")
    """
    # ✅ 1) segmented_control
    try:
        return st.segmented_control(
            label,
            options,
            default=default,
            key=key,
            label_visibility="collapsed", 
        )
    except Exception:
        pass

    # ✅ 2) pills
    try:
        return st.pills(
            label,
            options,
            default=default,
            key=key,
            label_visibility="collapsed",  
        )
    except Exception:
        pass

    # ✅ 3) fallback selectbox
    return st.selectbox(
        label,
        options,
        index=options.index(default),
        key=key,
        label_visibility="collapsed",  
    )


def render_period_filter(start_date: pd.Timestamp, end_date: pd.Timestamp):
    _inject_filter_style()
    st.markdown('<div id="period-filter-anchor"></div>', unsafe_allow_html=True)

    # 기본값(date)
    default_start = pd.to_datetime(start_date).date()
    default_end = pd.to_datetime(end_date).date()

    # ✅ canonical: date_range는 항상 (date, date)
    if "date_range" not in st.session_state:
        st.session_state["date_range"] = (default_start, default_end)

    # ✅ 페이지 위젯의 초기값은 canonical을 따라감
    # (여기서 date_picker는 건드리지 마세요! 이미 sidebar에서 만들어졌을 수 있음)
    if "period_date_range" not in st.session_state:
        st.session_state["period_date_range"] = st.session_state["date_range"]

    def _on_change_period():
        # 사용자가 페이지에서 변경 → canonical 갱신 + sidebar 위젯값도 갱신(콜백에서는 OK)
        v = st.session_state.get("period_date_range")
        if isinstance(v, (tuple, list)) and len(v) == 2 and v[0] and v[1] and v[0] <= v[1]:
            st.session_state["date_range"] = (v[0], v[1])
            st.session_state["date_picker"] = (v[0], v[1])  # ✅ 콜백에서만 업데이트

    with st.container():
        col1, col2 = st.columns([1.3, 2], vertical_alignment="center")

        with col1:
            period_type = _safe_segmented(
                "집계 단위",
                ["년간", "월간", "주간", "일간"],
                default=st.session_state.get("period_type", "월간"),
                key="period_type_control",
            )
            st.session_state["period_type"] = period_type

        with col2:
            selected_range = st.date_input(
                "날짜 선택",
                value=st.session_state["date_range"],   # ✅ canonical 사용
                label_visibility="collapsed",
                key="period_date_range",
                on_change=_on_change_period,            # ✅ 핵심
            )

    # 방어
    if not isinstance(selected_range, (tuple, list)) or len(selected_range) != 2:
        st.warning("⚠ 기간은 시작일과 종료일을 모두 선택해 주세요.")
        st.stop()

    filter_start, filter_end = selected_range
    if filter_start is None or filter_end is None:
        st.warning("⚠ 기간은 시작일과 종료일을 모두 선택해 주세요.")
        st.stop()

    if filter_start > filter_end:
        st.warning("⚠ 시작일이 종료일보다 클 수 없습니다.")
        st.stop()

    # ✅ 여기서는 canonical만 업데이트(다른 위젯 키 직접 대입 금지)
    st.session_state["date_range"] = (filter_start, filter_end)

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
        unsafe_allow_html=True,
    )
    
import textwrap

def render_month_navigator(
    *,
    key_prefix: str = "addon",
    default_month: int | None = None,  # ✅ 초기값(1~12) 주입
    allow_all: bool = True,
):
    """
    < 2월 > 형태 월 네비게이터
    - state: st.session_state[f"{key_prefix}_month_nav"]
    - default_month가 있으면 최초 1회 초기값으로 사용
    - 반환: (label, month_int) / month_int None이면 전체
    """
    state_key = f"{key_prefix}_month_nav"

    # ✅ 최초 초기값: default_month 우선
    if state_key not in st.session_state:
        if default_month is not None:
            st.session_state[state_key] = int(default_month)
        else:
            st.session_state[state_key] = "전체" if allow_all else 1

    def _prev():
        cur = st.session_state[state_key]
        if cur == "전체":
            st.session_state[state_key] = 12
        else:
            st.session_state[state_key] = 12 if cur == 1 else cur - 1

    def _next():
        cur = st.session_state[state_key]
        if cur == "전체":
            st.session_state[state_key] = 1
        else:
            st.session_state[state_key] = 1 if cur == 12 else cur + 1

    def _set_all():
        st.session_state[state_key] = "전체"

    left, mid, right = st.columns([1, 3, 1], vertical_alignment="center")

    with left:
        st.button("‹", key=f"{key_prefix}_month_prev", width="stretch", on_click=_prev)

    with mid:
        cur = st.session_state[state_key]
        center_text = "전체" if cur == "전체" else f"{cur}월"  # ✅ 04월 X -> 4월

        st.markdown(
            f"""
            <div style="text-align:center; padding:6px 0;">
                <span style="font-size:26px; font-weight:900; color:#111827;">
                    {center_text}
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )

        if allow_all:
            st.button("전체", key=f"{key_prefix}_month_all", width="stretch", on_click=_set_all)

    with right:
        st.button("›", key=f"{key_prefix}_month_next", width="stretch", on_click=_next)

    cur = st.session_state[state_key]
    if cur == "전체":
        return "전체", None
    return f"{cur}월", int(cur)

def render_month_addon_filter_only(
    df_filtered: "pd.DataFrame",
    *,
    key_prefix: str = "addon",
    allow_all: bool = True,
    all_label: str | None = None,

    # ✅ 상단 필터의 마지막 날짜(=당월 기준) 주입
    filter_end: "pd.Timestamp | str | None" = None,

    # ✅ 네비/높이 튜닝
    nav_height_px: int = 60,
    arrow_top_px: int = 62,
    month_top_px: int = 18,
    arrow_side_px: int = 16,
    # ✅ 전체/당월(네비 안) 위치 튜닝
    mode_top_px: int = 104,
    mode_right_px: int = 14,
):
    """
    ✅ 하단 월 네비게이터
    핵심 요구사항:
    - 상단 날짜 필터가 바뀌면(특히 filter_end) 하단의 '당월' 기준도
      상단 filter_end가 속한 월로 자동 리셋되어야 함.
    반환: (year, month) / 전체면 (None, None)
    """
    import pandas as pd
    import streamlit as st

    # -------------------------
    # 1) 연-월 목록 만들기 (df_filtered 기준)
    # -------------------------
    ym_list: list[tuple[int, int]] = []
    if df_filtered is not None and (not df_filtered.empty) and ("date" in df_filtered.columns):
        s = pd.to_datetime(df_filtered["date"], errors="coerce").dropna()
        if not s.empty:
            ym_df = pd.DataFrame({"y": s.dt.year.astype(int), "m": s.dt.month.astype(int)})
            ym_df = ym_df.drop_duplicates().sort_values(["y", "m"])
            ym_list = list(zip(ym_df["y"].tolist(), ym_df["m"].tolist()))

    if not ym_list:
        st.markdown(
            """
            <div style="margin-bottom:14px;">
              <div style="font-size:12px; color:#9CA3AF; margin-top:4px;">
                선택 가능한 데이터가 없습니다.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return None, None

    # -------------------------
    # 1.5) all_label 자동 생성
    # -------------------------
    if all_label is None:
        try:
            s_all = pd.to_datetime(df_filtered["date"], errors="coerce").dropna()
            if not s_all.empty:
                dmin = s_all.min().date()
                dmax = s_all.max().date()
                all_label = f"{dmin:%Y/%m/%d} ~ {dmax:%Y/%m/%d}"
            else:
                all_label = "전체기간"
        except Exception:
            all_label = "전체기간"

    # -------------------------
    # 2) 상단 filter_end 기반 '기준 월' 계산
    # -------------------------
    end_dt = None
    if filter_end is not None:
        try:
            end_dt = pd.to_datetime(filter_end)
            if pd.isna(end_dt):
                end_dt = None
        except Exception:
            end_dt = None

    # end_dt가 없으면 df_filtered 최신 날짜로 fallback
    if end_dt is None:
        s = pd.to_datetime(df_filtered["date"], errors="coerce").dropna()
        end_dt = s.max() if not s.empty else pd.Timestamp.today()

    target_y, target_m = int(end_dt.year), int(end_dt.month)

    # ym_list에서 target(=filter_end 월)에 가장 "가깝게" 맞추기
    # - 우선: 정확히 같은 (y,m)
    # - 없으면: target보다 작거나 같은 것 중 가장 최신
    # - 그것도 없으면: ym_list의 첫 값
    def _find_best_idx(y: int, m: int) -> int:
        try:
            exact_idx = ym_list.index((y, m))
            return exact_idx
        except ValueError:
            pass

        target_key = y * 100 + m
        keys = [yy * 100 + mm for (yy, mm) in ym_list]

        le = [i for i, k in enumerate(keys) if k <= target_key]
        if le:
            return max(le)

        return 0

    best_idx = _find_best_idx(target_y, target_m)
    latest_idx = len(ym_list) - 1

    # -------------------------
    # 3) 상태 (✅ filter_end 변경 감지해서 '당월' 리셋)
    # -------------------------
    state_key = f"{key_prefix}_ym_state"
    sync_key = f"{key_prefix}_ym_sync_end"  # ✅ 마지막으로 본 filter_end(연-월) 기억

    # 이번 렌더의 end(연-월) 토큰
    cur_sync_token = f"{target_y:04d}-{target_m:02d}"

    if state_key not in st.session_state:
        # 최초: 상단 filter_end 월로 시작(당월)
        st.session_state[state_key] = {"mode": "ym", "idx": best_idx}
        st.session_state[sync_key] = cur_sync_token
    else:
        # ✅ 상단 날짜 필터가 바뀌면 하단을 "당월(상단 end 월)"로 리셋
        prev_token = st.session_state.get(sync_key)
        if prev_token != cur_sync_token:
            st.session_state[state_key]["mode"] = "ym"
            st.session_state[state_key]["idx"] = best_idx
            st.session_state[sync_key] = cur_sync_token

    # idx 범위 방어
    st.session_state[state_key]["idx"] = max(0, min(st.session_state[state_key]["idx"], latest_idx))
    if st.session_state[state_key]["mode"] not in ("ym", "all"):
        st.session_state[state_key]["mode"] = "ym"

    def _prev():
        st.session_state[state_key]["mode"] = "ym"
        st.session_state[state_key]["idx"] = max(0, st.session_state[state_key]["idx"] - 1)

    def _next():
        st.session_state[state_key]["mode"] = "ym"
        st.session_state[state_key]["idx"] = min(latest_idx, st.session_state[state_key]["idx"] + 1)

    def _set_all():
        st.session_state[state_key]["mode"] = "all"

    def _set_latest():
        # ✅ "당월" 버튼 = 상단 end 기준 월로 이동하는 게 요구사항에 맞음
        st.session_state[state_key]["mode"] = "ym"
        st.session_state[state_key]["idx"] = best_idx

    # -------------------------
    # 4) 스타일/렌더 (기존 그대로)
    # -------------------------
    nav_anchor = f"{key_prefix}-month-nav-anchor"
    mode_anchor = f"{key_prefix}-mode-anchor"

    st.markdown(f'<div id="{nav_anchor}"></div>', unsafe_allow_html=True)

    st.markdown(
        f"""
        <style>
        #{nav_anchor} + div {{
            position: relative;
            --primary: #F00176;
            --border: #E5E7EB;
            --bg: #F7F8F9;
            --text: #111827;
            --muted: #6B7280;
        }}

        #{nav_anchor} + div div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {{
            padding-left: 0px !important;
            padding-right: 0px !important;
        }}

        .{key_prefix}-nav-canvas {{
            position: relative;
            width: 100%;
            height: {nav_height_px}px;
            margin: 6px 0 2px 0;
        }}

        .{key_prefix}-month {{
            position: absolute;
            left: 50%;
            top: {month_top_px}px;
            transform: translateX(-50%);
            display: inline-flex;
            align-items: flex-end;
            white-space: nowrap;
            line-height: 1;
            pointer-events: none;
            z-index: 3;
        }}
        .{key_prefix}-month-num {{
            font-size: 62px;
            font-weight: 900;
            letter-spacing: -1px;
            color: var(--primary);
        }}
        .{key_prefix}-month-suffix {{
            font-size: 30px;
            font-weight: 900;
            margin-left: 6px;
            color: #26282B;
            transform: translateY(-8px);
            display: inline-block;
        }}

        .{key_prefix}-all-range {{
            font-size: 20px;
            font-weight: 900;
            color: var(--text);
            letter-spacing: -0.2px;
        }}

        .{key_prefix}-arrow-row {{
            position: absolute;
            left: 0;
            right: 0;
            top: {arrow_top_px}px;
            transform: translateY(-50%);
            z-index: 4;
            padding: 0 {arrow_side_px}px;
        }}

        .{key_prefix}-arrow-row div[data-testid="stButton"] > button {{
            width: 40px !important;
            min-width: 40px !important;
            height: 40px !important;
            padding: 0 !important;
            border-radius: 10px !important;
            background: #FFFFFF !important;
            border: 1px solid var(--border) !important;
            box-shadow: none !important;
            font-size: 18px !important;
            font-weight: 800 !important;
            line-height: 40px !important;
        }}
        .{key_prefix}-arrow-row div[data-testid="stButton"] > button:hover {{
            background: var(--bg) !important;
        }}
        .{key_prefix}-arrow-row div[data-testid="stButton"] {{
            margin: 0 !important;
        }}

        #{mode_anchor} + div {{
            position: absolute !important;
            top: {mode_top_px}px !important;
            right: {mode_right_px}px !important;
            z-index: 20 !important;

            height: 34px !important;
            display: flex !important;
            align-items: center !important;
        }}

        #{mode_anchor} + div div[role="radiogroup"] {{
            display: flex !important;
            align-items: center !important;
            gap: 10px !important;
            height: 34px !important;
        }}

        #{mode_anchor} + div div[data-baseweb="radio"] > div:first-child {{
            display: none !important;
        }}

        #{mode_anchor} + div div[data-baseweb="radio"] label {{
            padding: 0 2px !important;
            margin: 0 !important;
            height: 34px !important;
            line-height: 34px !important;

            background: transparent !important;
            border: none !important;
            box-shadow: none !important;

            font-size: 14px !important;
            font-weight: 800 !important;
            color: var(--muted) !important;
            cursor: pointer !important;
        }}

        #{mode_anchor} + div div[data-baseweb="radio"] label:hover {{
            color: var(--primary) !important;
            text-decoration: underline;
            text-underline-offset: 4px;
        }}

        #{mode_anchor} + div div[data-baseweb="radio"][aria-checked="true"] label {{
            color: var(--primary) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown(f'<div class="{key_prefix}-nav-canvas">', unsafe_allow_html=True)

        mode = st.session_state[state_key]["mode"]
        if mode == "all":
            center_html = f'<span class="{key_prefix}-all-range">{all_label}</span>'
        else:
            _, m = ym_list[st.session_state[state_key]["idx"]]
            center_html = (
                f'<span class="{key_prefix}-month-num">{m}</span>'
                f'<span class="{key_prefix}-month-suffix">월</span>'
            )
        st.markdown(f'<div class="{key_prefix}-month">{center_html}</div>', unsafe_allow_html=True)

        st.markdown(f'<div class="{key_prefix}-arrow-row">', unsafe_allow_html=True)
        cL, cMid, cR = st.columns([1, 10, 1], vertical_alignment="center")
        with cL:
            st.button("‹", key=f"{key_prefix}_m_prev", on_click=_prev)
        with cMid:
            st.empty()
        with cR:
            st.button("›", key=f"{key_prefix}_m_next", on_click=_next)
        st.markdown("</div>", unsafe_allow_html=True)

        if allow_all:
            st.markdown(f'<div id="{mode_anchor}"></div>', unsafe_allow_html=True)

            radio_key = f"{key_prefix}_mode_choice"
            default_choice = "전체" if st.session_state[state_key]["mode"] == "all" else "당월"
            st.session_state[radio_key] = default_choice

            def _on_change_mode():
                v = st.session_state.get(radio_key)
                if v == "전체":
                    _set_all()
                else:
                    _set_latest()

            st.radio(
                "mode",
                ["전체", "당월"],
                horizontal=True,
                label_visibility="collapsed",
                key=radio_key,
                on_change=_on_change_mode,
            )

        st.markdown("</div>", unsafe_allow_html=True)

    # 반환
    if st.session_state[state_key]["mode"] == "all":
        return None, None

    y, m = ym_list[st.session_state[state_key]["idx"]]
    return int(y), int(m)


def _ensure_datetime(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "date" not in df.columns:
        raise KeyError("df must have 'date' column")
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def _daily_cum_for_year_month(
    df: pd.DataFrame,
    year: int,
    month: int,
    *,
    day_max: int = 31,
) -> pd.DataFrame:
    """
    특정 연/월의 일자별 지출(daily)과 누적(cum) 반환
    ✅ 소비(지출)만 집계: spend_amount 우선, 없으면 amount_abs, 없으면 abs(amount)
    반환 컬럼: day, daily, cum
    """
    if df is None or df.empty:
        base = pd.DataFrame({"day": range(1, day_max + 1)})
        base["daily"] = 0.0
        base["cum"] = 0.0
        return base

    dfx = df.copy()
    dfx["date"] = pd.to_datetime(dfx["date"], errors="coerce")
    dfx = dfx[dfx["date"].notna()].copy()

    # ✅ 소비만
    if "spend_amount" in dfx.columns:
        spend = pd.to_numeric(dfx["spend_amount"], errors="coerce").fillna(0.0)
    elif "amount_abs" in dfx.columns:
        spend = pd.to_numeric(dfx["amount_abs"], errors="coerce").fillna(0.0)
    else:
        spend = pd.to_numeric(dfx["amount"], errors="coerce").fillna(0.0).abs()

    dfx["_spend"] = spend

    dfx = dfx[(dfx["date"].dt.year == int(year)) & (dfx["date"].dt.month == int(month))].copy()

    base = pd.DataFrame({"day": range(1, day_max + 1)})

    if dfx.empty:
        base["daily"] = 0.0
        base["cum"] = 0.0
        return base

    dfx["day"] = dfx["date"].dt.day

    daily = (
        dfx.groupby("day")["_spend"]
        .sum()
        .reindex(range(1, day_max + 1), fill_value=0.0)
        .reset_index()
        .rename(columns={"_spend": "daily"})
    )
    daily["cum"] = daily["daily"].cumsum()

    return base.merge(daily, on="day", how="left").fillna(0.0)