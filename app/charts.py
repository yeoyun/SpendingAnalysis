# app/charts.py
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

from styles import PRIMARY_COLOR, GRAY_300, gray_gradient


# =====================
# 월별 지출 추이
# =====================
def draw_monthly_trend(df: pd.DataFrame):
    monthly_df = (
        df
        .groupby(df["date"].dt.to_period("M"))["amount"]
        .sum()
        .abs()
        .reset_index()
    )
    monthly_df["date"] = monthly_df["date"].dt.to_timestamp()

    fig = go.Figure()

    fig.add_bar(
        x=monthly_df["date"],
        y=monthly_df["amount"],
        marker_color=GRAY_300,
        name="월별 지출"
    )

    fig.add_scatter(
        x=monthly_df["date"],
        y=monthly_df["amount"],
        mode="lines+markers",
        line=dict(color=PRIMARY_COLOR, width=3),
        name="지출 추이"
    )

    fig.update_layout(
        xaxis_title="월",
        yaxis_title="지출 금액 (원)",
        hovermode="x unified"
    )

    return fig


# =====================
# 카테고리별 파이 차트
# =====================
def draw_category_pie(df: pd.DataFrame):
    pie_df = (
        df
        .groupby("category_lv1")["amount"]
        .sum()
        .abs()
        .reset_index()
    )

    total = pie_df["amount"].sum()
    pie_df["ratio"] = pie_df["amount"] / total

    major = pie_df[pie_df["ratio"] >= 0.05]
    minor = pie_df[pie_df["ratio"] < 0.05]

    if not minor.empty:
        pie_df = pd.concat([
            major,
            pd.DataFrame({
                "category_lv1": ["기타"],
                "amount": [minor["amount"].sum()],
                "ratio": [minor["ratio"].sum()]
            })
        ])

    pie_df = pie_df.sort_values("amount", ascending=False).reset_index(drop=True)

    colors = []
    for i, t in enumerate(np.linspace(0, 1, len(pie_df))):
        colors.append(PRIMARY_COLOR if i == 0 else gray_gradient(t))

    fig = go.Figure(
        data=[
            go.Pie(
                labels=pie_df["category_lv1"],
                values=pie_df["amount"],
                hole=0.4,
                marker=dict(colors=colors),
                textinfo="label+percent",
                sort=False
            )
        ]
    )

    return fig


# =====================
# 카테고리별 막대 차트
# =====================
def draw_category_bar(df: pd.DataFrame):
    bar_df = (
        df
        .groupby("category_lv1")["amount"]
        .sum()
        .abs()
        .sort_values(ascending=False)
        .reset_index()
    )

    fig = px.bar(
        bar_df,
        x="category_lv1",
        y="amount",
        text=bar_df["amount"].apply(lambda x: f"{int(x):,}원")
    )

    fig.update_traces(
        marker_color=PRIMARY_COLOR,
        textposition="outside"
    )

    fig.update_layout(
        xaxis_title="카테고리",
        yaxis_title="지출 금액 (원)"
    )

    return fig


# =====================
# 요일 · 시간대 히트맵
# =====================
def draw_weekday_hour_heatmap(df: pd.DataFrame):
    weekday_map = {
        "Monday": "월", "Tuesday": "화", "Wednesday": "수",
        "Thursday": "목", "Friday": "금",
        "Saturday": "토", "Sunday": "일"
    }

    df = df.copy()
    df["weekday"] = df["date"].dt.day_name().map(weekday_map)

    heatmap_df = (
        df
        .groupby(["weekday", "hour"])["amount"]
        .sum()
        .abs()
        .reset_index()
    )

    fig = px.density_heatmap(
        heatmap_df,
        x="hour",
        y="weekday",
        z="amount",
        color_continuous_scale=[
            "#F7F8F9",
            "#D1D5DB",
            "#9CA3AF",
            "#72787F"
        ]
    )

    fig.update_layout(
        xaxis_title="시간대",
        yaxis_title="요일"
    )

    return fig
