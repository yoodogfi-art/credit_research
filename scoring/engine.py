"""
Credit scoring engine.
Computes rate_level / spread_level / momentum / volatility scores
and maps total -> OW / NW / UW.
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _percentile_rank(series: pd.Series, window: int = 252) -> float:
    s = series.dropna()
    if len(s) < 10:
        return 0.5
    tail = s.iloc[-window:] if len(s) >= window else s
    return float((tail < tail.iloc[-1]).sum() / len(tail))


def _zscore_mom(series: pd.Series, window: int = 21) -> float:
    s = series.dropna().iloc[-window:]
    if len(s) < 5:
        return 0.0
    diff = s.diff().dropna()
    std  = diff.std()
    return float(diff.mean() / std) if std != 0 else 0.0


def _vol_threshold(series: pd.Series, window: int = 252, mul: float = 1.5) -> float:
    std_roll = series.rolling(20).std().dropna()
    hist = std_roll.iloc[-window:] if len(std_roll) >= window else std_roll
    return float(hist.quantile(0.75)) * mul if len(hist) > 0 else 0.01


# ---------------------------------------------------------------------------
# Score components
# ---------------------------------------------------------------------------
def _score_level(pct: float) -> int:
    if pct > 0.75:
        return +1
    if pct < 0.25:
        return -1
    return 0


def _score_momentum(z: float) -> int:
    if z > 1.0:
        return -1
    if z < -1.0:
        return +1
    return 0


def _score_vol(std_20: float, threshold: float) -> int:
    return -1 if std_20 > threshold else 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def compute_score(yield_series: pd.Series, spread_series: pd.Series | None = None) -> dict:
    ref = spread_series if (spread_series is not None and spread_series.dropna().shape[0] > 10) else yield_series

    rate_pct    = _percentile_rank(yield_series)
    spread_pct  = _percentile_rank(ref)
    mom_z       = _zscore_mom(ref)
    std_20      = float(yield_series.dropna().diff().iloc[-20:].std()) if yield_series.dropna().shape[0] >= 20 else 0.0
    threshold   = _vol_threshold(yield_series)

    r_sc  = _score_level(rate_pct)
    sp_sc = _score_level(spread_pct)
    m_sc  = _score_momentum(mom_z)
    v_sc  = _score_vol(std_20, threshold)
    total = r_sc + sp_sc + m_sc + v_sc

    view = "OW" if total >= 2 else "UW" if total <= -2 else "NW"

    return {
        "rate_pct":       round(rate_pct, 3),
        "rate_score":     r_sc,
        "spread_pct":     round(spread_pct, 3),
        "spread_score":   sp_sc,
        "momentum_z":     round(mom_z, 3),
        "momentum_score": m_sc,
        "vol_std":        round(std_20, 5),
        "vol_threshold":  round(threshold, 5),
        "vol_score":      v_sc,
        "total_score":    total,
        "view":           view,
        "comment":        _build_comment(r_sc, sp_sc, m_sc, v_sc, view),
    }


def _build_comment(rate: int, spread: int, mom: int, vol: int, view: str) -> str:
    parts = []
    parts.append(
        "금리 레벨 carry 유효" if rate == 1
        else "금리 매력 제한적"  if rate == -1
        else "금리 레벨 중립"
    )
    parts.append(
        "스프레드 밸류 양호"  if spread == 1
        else "스프레드 밸류 부담" if spread == -1
        else "스프레드 중립"
    )
    parts.append(
        "스프레드 확대 흐름" if mom == -1
        else "스프레드 축소 흐름" if mom == 1
        else "스프레드 안정"
    )
    if vol == -1:
        parts.append("변동성 주의")
    return " / ".join(parts) + f" => {view}"


VIEW_COLOR = {"OW": "#2E7D32", "NW": "#9E9E9E", "UW": "#C62828"}