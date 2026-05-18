import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from data.loader import TENOR_LABELS, get_spread

COLORS = ['#2D3F38','#E65100','#4A5E35','#9A7085','#005F73','#E87070']


def _date_filter(key, df):
    min_d, max_d = df['date'].min().date(), df['date'].max().date()
    presets = {'1M': 30, '3M': 90, '6M': 180, '1Y': 365, '전체': None}
    c1, c2 = st.columns([1, 2])
    with c1:
        preset = st.selectbox("기간", list(presets.keys()), index=3, key=f'{key}_pre')
    with c2:
        days = presets[preset]
        dv = (min_d, max_d) if days is None else (max_d - pd.Timedelta(days=days), max_d)
        dr = st.date_input("직접 지정", value=dv, min_value=min_d, max_value=max_d, key=f'{key}_dr')
    return (pd.Timestamp(dr[0]), pd.Timestamp(dr[1])) if len(dr) == 2 else (pd.Timestamp(min_d), pd.Timestamp(max_d))


def render(df: pd.DataFrame):
    st.header("Credit View")
    all_cats = sorted(df['category'].unique())
    default_base = next((c for c in all_cats if '국고채' in c), all_cats[0])

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        cat_a = st.selectbox("주계열", all_cats,
            index=next((i for i, c in enumerate(all_cats) if '회사채 AA' in c), 0), key='cv_a')
    with c2:
        cat_b = st.selectbox("기준계열", all_cats,
            index=all_cats.index(default_base) if default_base in all_cats else 0, key='cv_b')
    with c3:
        tenor = st.selectbox("만기", TENOR_LABELS, index=TENOR_LABELS.index('3Y'), key='cv_tnr')

    d0, d1 = _date_filter('cv', df)
    dff = df[(df['date'] >= d0) & (df['date'] <= d1)]

    s_a = dff[(dff['category'] == cat_a) & (dff['tenor'] == tenor)].sort_values('date')
    s_b = dff[(dff['category'] == cat_b) & (dff['tenor'] == tenor)].sort_values('date')
    merged = pd.merge(
        s_a[['date','yield']].rename(columns={'yield':'y_a'}),
        s_b[['date','yield']].rename(columns={'yield':'y_b'}),
        on='date', how='inner'
    )
    merged['spread_bp'] = (merged['y_a'] - merged['y_b']) * 100

    if len(merged) == 0:
        st.warning("공통 날짜 데이터 없음"); return

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=merged['date'], y=merged['spread_bp'],
        name='스프레드(bp, 우)',
        fill='tozeroy', fillcolor='rgba(221,232,192,0.35)',
        line=dict(color='rgba(141,193,117,0.6)', width=1.2)),
        secondary_y=True)
    avg = merged['spread_bp'].mean()
    fig.add_trace(go.Scatter(
        x=[merged['date'].min(), merged['date'].max()], y=[avg, avg],
        name=f'평균 {avg:.1f}bp',
        line=dict(color='gray', width=1, dash='dash'), hoverinfo='skip'),
        secondary_y=True)
    fig.add_trace(go.Scatter(x=s_b['date'], y=s_b['yield'],
        name=f'{cat_b}(좌)', line=dict(color='#9E9E9E', width=1.5, dash='dot')),
        secondary_y=False)
    fig.add_trace(go.Scatter(x=s_a['date'], y=s_a['yield'],
        name=f'{cat_a}(좌)', line=dict(color='#2D3F38', width=2.2)),
        secondary_y=False)
    fig.update_yaxes(title_text='금리(%)', ticksuffix='%', secondary_y=False)
    fig.update_yaxes(title_text='스프레드(bp)', ticksuffix='bp', secondary_y=True)
    fig.update_layout(height=450, template='plotly_white', hovermode='x unified',
                      margin=dict(l=55, r=65, t=50, b=40))
    st.plotly_chart(fig, use_container_width=True)

    last = merged['spread_bp'].iloc[-1]
    prev = merged.iloc[:-21] if len(merged) > 21 else merged
    mom = last - prev['spread_bp'].iloc[-1] if len(prev) else np.nan
    pct = (merged['spread_bp'] < last).sum() / len(merged) * 100
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("현재 스프레드", f"{last:.1f}bp")
    m2.metric("기간 평균", f"{avg:.1f}bp")
    m3.metric("1M 변화", f"{mom:+.1f}bp" if not np.isnan(mom) else "-")
    m4.metric("Percentile", f"{pct:.0f}%")

    st.divider()
    st.subheader("멀티 스프레드 비교")
    extras = st.multiselect("추가 계열", [c for c in all_cats if c != cat_a],
                             default=[], max_selections=5, key='cv_extra')
    if extras:
        fig2 = go.Figure()
        for i, cc in enumerate([cat_a] + extras):
            se = dff[(dff['category'] == cc) & (dff['tenor'] == tenor)].sort_values('date')
            m2df = pd.merge(
                se[['date','yield']].rename(columns={'yield':'y_e'}),
                s_b[['date','yield']].rename(columns={'yield':'y_b'}),
                on='date', how='inner'
            )
            m2df['sp'] = (m2df['y_e'] - m2df['y_b']) * 100
            fig2.add_trace(go.Scatter(x=m2df['date'], y=m2df['sp'], name=cc,
                line=dict(color=COLORS[i % len(COLORS)], width=2,
                          dash='solid' if i == 0 else 'dot')))
        fig2.update_layout(height=380, template='plotly_white', hovermode='x unified',
                           yaxis_ticksuffix='bp', margin=dict(l=50, r=20, t=40, b=40))
        st.plotly_chart(fig2, use_container_width=True)