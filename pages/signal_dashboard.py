"""Page: Signal Dashboard — Duration / Curve / Credit signals."""

import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from assets.styles import CHART_COLORS, CORAL, DEEP_GREEN, PLOTLY_TEMPLATE
from data.loader import TENOR_LABELS
from chart_utils import PLOTLY_CONFIG, base_layout

_VIEW_CFG = {
    "OW": {"label": "비중확대", "sym": "+", "bg": "#E8F5E9", "fg": "#1B5E20", "border": "#66BB6A"},
    "NW": {"label": "중립",     "sym": "-", "bg": "#F5F5F5", "fg": "#424242", "border": "#BDBDBD"},
    "UW": {"label": "비중축소", "sym": "-", "bg": "#FFEBEE", "fg": "#B71C1C", "border": "#EF9A9A"},
}


# ---------------------------------------------------------------------------
# Signal calculations
# ---------------------------------------------------------------------------
def _series(df: pd.DataFrame, cat: str, tenor: str) -> pd.Series:
    s = df[(df["category"] == cat) & (df["tenor"] == tenor)]
    return s.set_index("date")["yield"].sort_index().dropna()


def _weekly_change(s: pd.Series, days: int = 5) -> float:
    if len(s) < 2:
        return np.nan
    prev = s.iloc[-days] if len(s) > days else s.iloc[0]
    return (s.iloc[-1] - prev) * 100


def signal_duration(df: pd.DataFrame, gov_cat: str, tenor: str, thresh: float) -> dict:
    s   = _series(df, gov_cat, tenor)
    chg = _weekly_change(s)
    view = "NW" if np.isnan(chg) else ("OW" if chg <= -thresh else "UW" if chg >= thresh else "NW")
    return {"view": view, "chg_bp": chg, "current": s.iloc[-1] if len(s) else np.nan, "series": s}


def signal_curve(df: pd.DataFrame, gov_cat: str, long_t: str, short_t: str, thresh: float) -> dict:
    sl = _series(df, gov_cat, long_t)
    ss = _series(df, gov_cat, short_t)
    idx = sl.index.intersection(ss.index)
    if len(idx) == 0:
        return {"view": "NW", "chg_bp": np.nan, "slope_bp": np.nan, "series": pd.Series(dtype=float)}
    slope = ((sl - ss) * 100).reindex(idx).dropna()
    chg   = _weekly_change(slope)
    view  = "NW" if np.isnan(chg) else ("OW" if chg >= thresh else "UW" if chg <= -thresh else "NW")
    return {"view": view, "chg_bp": chg, "slope_bp": slope.iloc[-1] if len(slope) else np.nan, "series": slope}


def signal_credit(df: pd.DataFrame, credit_cat: str, gov_cat: str, tenor: str, thresh: float) -> dict:
    sc  = _series(df, credit_cat, tenor)
    sg  = _series(df, gov_cat, tenor)
    idx = sc.index.intersection(sg.index)
    if len(idx) == 0:
        return {"view": "NW", "chg_bp": np.nan, "spread_bp": np.nan, "series": pd.Series(dtype=float)}
    spread = ((sc - sg) * 100).reindex(idx).dropna()
    chg    = _weekly_change(spread)
    view   = "NW" if np.isnan(chg) else ("UW" if chg >= thresh else "OW" if chg <= -thresh else "NW")
    return {"view": view, "chg_bp": chg,
            "spread_bp": spread.iloc[-1] if len(spread) else np.nan, "series": spread}


# ---------------------------------------------------------------------------
# UI components
# ---------------------------------------------------------------------------
def _signal_card(title: str, sig: dict, lines: list[str]) -> None:
    c = _VIEW_CFG[sig["view"]]
    body = "".join(f'<div style="font-size:12px;color:#555;margin:2px 0">{l}</div>' for l in lines)
    st.markdown(
        f'<div style="border:1px solid {c["border"]};border-radius:6px;'
        f'padding:16px 18px;background:{c["bg"]}">'
        f'<div style="font-size:11px;color:#777;margin-bottom:4px">{title}</div>'
        f'<div style="font-size:20px;font-weight:700;color:{c["fg"]};margin-bottom:8px">{c["label"]}</div>'
        f"{body}</div>",
        unsafe_allow_html=True,
    )


def _ts_chart(series_dict: dict, title: str, y_suffix: str, height: int = 280) -> go.Figure:
    fig = go.Figure()
    for i, (name, s) in enumerate(series_dict.items()):
        if s is None or s.empty:
            continue
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, name=name,
            line=dict(color=CHART_COLORS[i % len(CHART_COLORS)], width=2),
            hovertemplate=f"{name}: %{{y:.2f}}{y_suffix}<extra></extra>",
        ))
    fig.add_hline(y=0, line_dash="dash", line_color="#CCCCCC", line_width=1)
    base_layout(fig, title, height)
    fig.update_yaxes(ticksuffix=y_suffix, zeroline=True, zerolinecolor="#CCCCCC")
    return fig


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def render(df: pd.DataFrame) -> None:
    st.header("Signal Dashboard")
    st.caption("Duration / Curve / Credit 투자의견 자동 산출")

    all_cats = sorted(df["category"].unique().tolist())
    gov_cat  = next((c for c in all_cats if "국고채" in c), None)
    if gov_cat is None:
        st.error("국고채 데이터가 없습니다.")
        return

    # Date filter
    min_d = df["date"].min().date()
    max_d = df["date"].max().date()
    with st.expander("분석 기간", expanded=False):
        c1, c2 = st.columns(2)
        start_d = c1.date_input("시작일", value=max(max_d - datetime.timedelta(days=180), min_d),
                                 min_value=min_d, max_value=max_d, key="sig_start")
        end_d   = c2.date_input("종료일", value=max_d, min_value=min_d, max_value=max_d, key="sig_end")
    dff = df[df["date"].between(pd.Timestamp(start_d), pd.Timestamp(end_d))]

    # Threshold settings
    with st.expander("임계값 설정", expanded=False):
        t1, t2, t3 = st.columns(3)
        dur_t = t1.number_input("Duration (bp)", value=10, min_value=1, max_value=50, key="dur_t")
        cur_t = t2.number_input("Curve (bp)",    value=10, min_value=1, max_value=50, key="cur_t")
        crd_t = t3.number_input("Credit (bp)",   value=15, min_value=1, max_value=50, key="crd_t")

    st.markdown("---")
    o1, o2, o3 = st.columns(3)
    dur_tenor   = o1.selectbox("Duration 만기", ["3Y", "5Y", "2Y", "1Y"], key="dur_t_sel")
    curve_long  = o2.selectbox("커브 장기단",   ["5Y", "3Y", "4Y"],       key="cur_long")
    curve_short = o2.selectbox("커브 단기단",   ["1Y", "6M", "2Y"],       key="cur_short")
    crd_tenor   = o3.selectbox("Credit 만기",   ["3Y", "5Y", "2Y"],       key="crd_t_sel")

    # Compute signals
    sig_dur = signal_duration(dff, gov_cat, dur_tenor, dur_t)
    sig_cur = signal_curve(dff, gov_cat, curve_long, curve_short, cur_t)

    credit_cats_avail = [c for c in all_cats if "국고채" not in c]
    rep_cr_cats = [c for c in all_cats if any(x in c for x in ["공사/공단채 AAA", "회사채 AA-", "카드채 AA"])][:3]
    sig_cr_map  = {c: signal_credit(dff, c, gov_cat, crd_tenor, crd_t) for c in rep_cr_cats}
    cr_views    = [v["view"] for v in sig_cr_map.values()]
    rep_cr_view = max(set(cr_views), key=cr_views.count) if cr_views else "NW"
    rep_cr_chg  = float(np.nanmean([v["chg_bp"] for v in sig_cr_map.values()]))

    latest = dff["date"].max()
    st.caption(f"기준일: {latest.strftime('%Y-%m-%d')} | 주간변화 = 최근 5영업일")

    # Signal cards
    c1, c2, c3 = st.columns(3)
    with c1:
        _signal_card(
            f"Duration ({gov_cat} {dur_tenor})", sig_dur,
            [f"현재 금리: {sig_dur['current']:.3f}%" if not np.isnan(sig_dur['current']) else "현재 금리: -",
             f"주간 변화: {sig_dur['chg_bp']:+.1f}bp" if not np.isnan(sig_dur['chg_bp']) else "주간 변화: -",
             f"임계값: +/-{dur_t}bp"],
        )
    with c2:
        _signal_card(
            f"Curve ({curve_long}-{curve_short})", sig_cur,
            [f"현재 Slope: {sig_cur['slope_bp']:+.1f}bp" if not np.isnan(sig_cur['slope_bp']) else "Slope: -",
             f"주간 변화: {sig_cur['chg_bp']:+.1f}bp" if not np.isnan(sig_cur['chg_bp']) else "주간 변화: -",
             f"임계값: +/-{cur_t}bp"],
        )
    with c3:
        _signal_card(
            f"Credit ({crd_tenor} 스프레드)", {"view": rep_cr_view},
            [f"주간 변화: {rep_cr_chg:+.1f}bp" if not np.isnan(rep_cr_chg) else "주간 변화: -",
             f"임계값: +/-{crd_t}bp",
             f"대상: {len(rep_cr_cats)}개 계열"],
        )

    # Summary bar
    label = lambda v: {"OW": "비중확대", "NW": "중립", "UW": "비중축소"}[v]
    st.markdown(
        f'<div style="background:#F7F8F5;border-radius:6px;padding:14px 18px;'
        f'border-left:4px solid {DEEP_GREEN};margin:12px 0">'
        f'<div style="font-size:11px;color:#888;margin-bottom:4px">종합 포지션</div>'
        f'<div style="font-size:14px;font-weight:600;color:{DEEP_GREEN}">'
        f'Duration: {label(sig_dur["view"])} &nbsp;|&nbsp; '
        f'Curve: {label(sig_cur["view"])} &nbsp;|&nbsp; '
        f'Credit: {label(rep_cr_view)}'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # Per-sector credit table
    st.markdown("#### 섹터별 크레딧 시그널")
    sel_cr = st.multiselect(
        "분석 계열 (vs 국고채)", credit_cats_avail,
        default=credit_cats_avail[:min(6, len(credit_cats_avail))],
        key="sig_cr_cats",
    )
    if sel_cr:
        rows = []
        for cat in sel_cr:
            sig = signal_credit(dff, cat, gov_cat, crd_tenor, crd_t)
            rows.append({
                "cat": cat,
                "sp":  f"{sig['spread_bp']:.1f}bp" if not np.isnan(sig.get("spread_bp", np.nan)) else "-",
                "chg": f"{sig['chg_bp']:+.1f}bp"   if not np.isnan(sig.get("chg_bp", np.nan))    else "-",
                "v":   sig["view"],
            })

        html = (
            '<style>.st2{border-collapse:collapse;width:100%;font-size:12px;'
            "font-family:'Apple SD Gothic Neo',sans-serif}"
            '.st2 th{background:#2D3F38;color:#fff;padding:8px 12px;text-align:left}'
            '.st2 td{padding:7px 12px;border-bottom:1px solid #EEEEEE}'
            '.st2 tr:hover td{background:#F7F8F5}'
            '.ow{color:#1B5E20;font-weight:700}.nw{color:#424242}.uw{color:#B71C1C;font-weight:700}'
            '</style>'
            '<table class="st2"><thead><tr>'
            "<th>계열</th><th>현재 스프레드</th><th>주간 변화</th><th>투자의견</th>"
            "</tr></thead><tbody>"
        )
        for r in rows:
            cls   = {"OW": "ow", "NW": "nw", "UW": "uw"}[r["v"]]
            label_str = _VIEW_CFG[r["v"]]["label"]
            html += f'<tr><td>{r["cat"]}</td><td>{r["sp"]}</td><td>{r["chg"]}</td><td class="{cls}">{label_str}</td></tr>'
        html += "</tbody></table>"
        st.markdown(html, unsafe_allow_html=True)

    # Time series charts
    st.markdown("---")
    st.markdown("#### 시계열 차트")
    tab1, tab2, tab3 = st.tabs(["금리 레벨", "커브 Slope", "크레딧 스프레드"])

    with tab1:
        series = {f"{gov_cat} {tn}": _series(dff, gov_cat, tn) for tn in ["1Y", "3Y", "5Y"]}
        fig = _ts_chart({k: v for k, v in series.items() if not v.empty}, f"{gov_cat} 금리", "%", 300)
        fig.update_yaxes(ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    with tab2:
        sl = _series(dff, gov_cat, curve_long)
        ss = _series(dff, gov_cat, curve_short)
        idx = sl.index.intersection(ss.index)
        if len(idx):
            slope = (sl - ss).reindex(idx) * 100
            fig = _ts_chart({f"Slope {curve_long}-{curve_short}": slope},
                            f"커브 Slope ({gov_cat})", "bp", 300)
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        else:
            st.warning("커브 데이터 없음")

    with tab3:
        sp_dict = {}
        for cat in (sel_cr or rep_cr_cats)[:5]:
            sig = signal_credit(dff, cat, gov_cat, crd_tenor, crd_t)
            if not sig["series"].empty:
                sp_dict[cat] = sig["series"]
        if sp_dict:
            fig = _ts_chart(sp_dict, f"크레딧 스프레드 vs {gov_cat} ({crd_tenor})", "bp", 300)
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        else:
            st.warning("스프레드 데이터 없음")

    # Signal history
    st.markdown("---")
    st.markdown("#### 시그널 히스토리 (최근 20영업일)")
    avail_dates = sorted(dff["date"].unique(), reverse=True)[:20]
    hist = []
    for d in avail_dates:
        sub = dff[dff["date"] <= d]
        if len(sub) < 6:
            continue
        sd  = signal_duration(sub, gov_cat, dur_tenor, dur_t)
        sc  = signal_curve(sub, gov_cat, curve_long, curve_short, cur_t)
        cvs = [signal_credit(sub, c, gov_cat, crd_tenor, crd_t)["view"]
               for c in rep_cr_cats if not _series(sub, c, crd_tenor).empty]
        crv = max(set(cvs), key=cvs.count) if cvs else "NW"
        hist.append({"date": d.strftime("%Y-%m-%d"), "dur": sd["view"], "cur": sc["view"], "crd": crv})

    if hist:
        cls_map = {"OW": "ow2", "NW": "nw2", "UW": "uw2"}
        lbl_map = {k: v["label"] for k, v in _VIEW_CFG.items()}
        html2 = (
            '<style>.ht{border-collapse:collapse;width:100%;font-size:12px;'
            "font-family:'Apple SD Gothic Neo',sans-serif}"
            '.ht th{background:#2D3F38;color:#fff;padding:7px 14px;text-align:center}'
            '.ht td{padding:6px 14px;border-bottom:1px solid #EEEEEE;text-align:center}'
            '.ow2{color:#1B5E20;font-weight:700}.nw2{color:#777}.uw2{color:#B71C1C;font-weight:700}'
            '</style>'
            '<table class="ht"><thead><tr>'
            "<th>날짜</th><th>Duration</th><th>Curve</th><th>Credit</th>"
            "</tr></thead><tbody>"
        )
        for r in hist:
            html2 += (
                f'<tr><td>{r["date"]}</td>'
                f'<td class="{cls_map[r["dur"]]}">{lbl_map[r["dur"]]}</td>'
                f'<td class="{cls_map[r["cur"]]}">{lbl_map[r["cur"]]}</td>'
                f'<td class="{cls_map[r["crd"]]}">{lbl_map[r["crd"]]}</td></tr>'
            )
        html2 += "</tbody></table>"
        st.markdown(html2, unsafe_allow_html=True)