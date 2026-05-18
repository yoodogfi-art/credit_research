"""Shared Plotly layout helpers used across pages."""

import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from assets.styles import DEEP_GREEN, PLOTLY_TEMPLATE

# High-resolution export config — applied to every plotly_chart call
PLOTLY_CONFIG = dict(
    toImageButtonOptions=dict(
        format="png",
        filename="chart",
        scale=4,
        width=1600,
        height=900,
    ),
    displayModeBar=True,
    modeBarButtonsToRemove=["select2d", "lasso2d"],
)


def base_layout(fig: go.Figure, title: str = "", height: int = 420) -> go.Figure:
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        height=height,
        title=dict(text=f"<b>{title}</b>", font=dict(color=DEEP_GREEN, size=13), x=0),
        font=dict(family="Apple SD Gothic Neo, Noto Sans KR, sans-serif", size=12),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(size=11), bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#E0E0E0", borderwidth=1,
        ),
        margin=dict(l=65, r=75, t=52, b=44),
        plot_bgcolor="white", paper_bgcolor="white", hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False, showline=True, linecolor="#BDBDBD", linewidth=1.5, tickfont=dict(size=11))
    fig.update_yaxes(showgrid=True, gridcolor="#EEEEEE", gridwidth=1, tickfont=dict(size=11))
    return fig


def date_range_picker(
    df: pd.DataFrame,
    key: str,
    default_days: int = 365,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    min_d = df["date"].min().date()
    max_d = df["date"].max().date()

    # Read from the sidebar widgets (keys sb_date_start / sb_date_end set in app.py)
    g_start = st.session_state.get("sb_date_start")
    g_end   = st.session_state.get("sb_date_end")

    default_start = g_start if g_start else max(max_d - datetime.timedelta(days=default_days), min_d)
    default_end   = g_end   if g_end   else max_d

    c1, c2 = st.columns(2)
    with c1:
        start_d = st.date_input(
            "시작일", value=default_start,
            min_value=min_d, max_value=max_d,
            key=f"{key}_start",
        )
    with c2:
        end_d = st.date_input(
            "종료일", value=default_end,
            min_value=min_d, max_value=max_d,
            key=f"{key}_end",
        )
    if start_d > end_d:
        start_d, end_d = end_d, start_d
    return pd.Timestamp(start_d), pd.Timestamp(end_d)