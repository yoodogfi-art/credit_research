"""
Excel loader: Wide-format -> Long-format DataFrame

Expected structure (per 11-column block):
  row 0 : category header  (col 0, 11, 22, ...)
  row 1 : column labels    (date, tenor1, tenor2, ...)
  row 2+: data rows        (date descending)

Special blocks detected dynamically by row-0 header content:
  - policy rate  : contains '기준금리'
  - KTB          : contains '국고채권(Ny)'
"""

import io
import re

import numpy as np
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TENORS = [
    "3월이하", "6월이하", "9월이하", "1년이하",
    "1.5년이하", "2년이하", "2.5년이하", "3년이하", "4년이하", "5년이하",
]
TENOR_LABELS = ["3M", "6M", "9M", "1Y", "1.5Y", "2Y", "2.5Y", "3Y", "4Y", "5Y"]
TENOR_MAP = dict(zip(TENORS, TENOR_LABELS))

POLICY_RATE_SECTOR = "기준금리"
POLICY_RATE_TENOR  = "기준금리"

KTB_TENOR_MAP = {
    "국고채권(1년)":  "1Y",
    "국고채권(2년)":  "2Y",
    "국고채권(3년)":  "3Y",
    "국고채권(5년)":  "5Y",
    "국고채권(10년)": None,
    "국고채권(20년)": None,
    "국고채권(30년)": None,
    "국고채권(50년)": None,
}
KTB_TENOR_VALID = {"1Y", "2Y", "3Y", "5Y"}

_SPECIAL_HEADERS = ("기준금리", "국고채권")


# ---------------------------------------------------------------------------
# Category parser
# ---------------------------------------------------------------------------
def _parse_category(raw: str) -> tuple[str, str]:
    """Return (sector, rating) from a raw category header string."""
    raw = raw.strip()
    for prefix in ("시가평가 3사평균", "금투협 최종호가", "금투협최종호가", "시가평가3사평균"):
        raw = raw.replace(prefix, "").strip()
    raw = raw.replace("(공모/무보증)", "").replace("AA0", "AA").strip()

    patterns = [
        (r"국고채",                        "국고채",        r"국고채권?"),
        (r"통안채|통화안정",               "통안채",        r"통화안정증권|통안채"),
        (r"공사/공단채",                    "공사/공단채",   r"공사/공단채"),
        (r"공사채",                        "공사/공단채",   r"공사채"),
        (r"금융채.*은행채|은행채",           "은행채",        r"금융채\s*은행채|은행채"),
        (r"금융채.*카드채|카드채",           "카드채",        r"금융채\s*카드채|카드채"),
        (r"기타금융채|여전채",              "기타금융채",    r"기타금융채|여전채"),
        (r"회사채",                        "회사채",        r"회사채"),
    ]
    for detect, sector, strip_pat in patterns:
        if re.search(detect, raw):
            rating = re.sub(strip_pat, "", raw).strip()
            rating = re.sub(r"\(.*?\)", "", rating).strip()
            rating = re.sub(r"\s+", "", rating)
            return sector, rating

    return raw, ""


# ---------------------------------------------------------------------------
# Block parsers
# ---------------------------------------------------------------------------
def _parse_policy_rate_blocks(raw: pd.DataFrame) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    visited: set[int] = set()

    for col in range(raw.shape[1] - 1):
        if col in visited:
            continue
        header = str(raw.iloc[0, col]).strip()
        if "기준금리" not in header:
            continue
        if "일자" not in str(raw.iloc[1, col]).strip():
            continue

        country = header.split(":")[0].strip() if ":" in header else re.sub(r"기준금리", "", header).strip() or "기준금리"
        val_col = col + 1
        if val_col >= raw.shape[1]:
            continue

        visited.update([col, val_col])
        block = raw.iloc[2:, [col, val_col]].copy()
        block.columns = ["date", "yield"]
        block["date"]  = pd.to_datetime(block["date"], errors="coerce")
        block["yield"] = pd.to_numeric(block["yield"], errors="coerce")
        block = block.dropna()

        if block.empty:
            continue

        block["sector"]   = POLICY_RATE_SECTOR
        block["rating"]   = country
        block["category"] = f"{country} 기준금리"
        block["tenor"]    = POLICY_RATE_TENOR
        frames.append(block[["date", "sector", "rating", "category", "tenor", "yield"]])

    return frames


def _parse_ktb_blocks(raw: pd.DataFrame) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    visited: set[int] = set()

    for col in range(raw.shape[1] - 1):
        if col in visited:
            continue
        header = str(raw.iloc[0, col]).strip()
        if "국고채권" not in header:
            continue
        m = re.search(r"국고채권\((.+?)\)", header)
        if not m:
            continue
        tenor_key = f"국고채권({m.group(1)})"
        tenor = KTB_TENOR_MAP.get(tenor_key)
        if tenor not in KTB_TENOR_VALID:
            continue
        if "일자" not in str(raw.iloc[1, col]).strip():
            continue

        val_col = col + 1
        if val_col >= raw.shape[1]:
            continue
        visited.update([col, val_col])

        block = raw.iloc[2:, [col, val_col]].copy()
        block.columns = ["date", "yield"]
        block["date"]  = pd.to_datetime(block["date"], errors="coerce")
        block["yield"] = pd.to_numeric(block["yield"], errors="coerce")
        block = block.dropna()

        if block.empty:
            continue

        block["sector"]   = "국고채"
        block["rating"]   = ""
        block["category"] = "국고채"
        block["tenor"]    = tenor
        frames.append(block[["date", "sector", "rating", "category", "tenor", "yield"]])

    return frames


def _parse_standard_blocks(raw: pd.DataFrame) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    n_cols = raw.shape[1]

    for b in range(n_cols // 11 + 1):
        base = b * 11
        if base >= n_cols:
            break
        cat_raw = str(raw.iloc[0, base]).strip()
        if cat_raw in ("nan", ""):
            continue
        if any(s in cat_raw for s in _SPECIAL_HEADERS):
            continue

        sector, rating = _parse_category(cat_raw)
        end_col   = min(base + 11, n_cols)
        block_w   = end_col - base
        if block_w < 2:
            continue

        tenor_cols = TENORS[: block_w - 1]
        block = raw.iloc[2:, base:end_col].copy()
        block.columns = ["date"] + tenor_cols

        block["date"] = pd.to_datetime(block["date"], errors="coerce")
        block = block.dropna(subset=["date"])

        melted = block.melt(id_vars="date", var_name="tenor_raw", value_name="yield")
        melted["tenor"]    = melted["tenor_raw"].map(TENOR_MAP)
        melted["yield"]    = pd.to_numeric(melted["yield"], errors="coerce")
        melted["sector"]   = sector
        melted["rating"]   = rating
        melted["category"] = f"{sector} {rating}".strip()
        melted = melted.dropna(subset=["yield", "tenor"])

        if melted.empty:
            continue
        frames.append(melted[["date", "sector", "rating", "category", "tenor", "yield"]])

    return frames


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_excel(file_bytes: bytes) -> tuple[pd.DataFrame, list[str]]:
    """Returns (df, warnings) — no Streamlit calls inside."""
    raw = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0, header=None)

    frames: list[pd.DataFrame] = []
    frames.extend(_parse_standard_blocks(raw))

    policy_frames = _parse_policy_rate_blocks(raw)
    frames.extend(policy_frames)

    frames.extend(_parse_ktb_blocks(raw))

    if not frames:
        raise ValueError("파싱된 데이터가 없습니다. 파일 형식을 확인하세요.")

    df = pd.concat(frames, ignore_index=True).sort_values("date").reset_index(drop=True)
    warnings = _validate(df)

    if policy_frames:
        cats  = ", ".join({f["category"].iloc[0] for f in policy_frames})
        total = sum(len(f) for f in policy_frames)
        warnings.insert(0, f"__toast__기준금리 로드: {cats} ({total:,}건)")

    return df, warnings


def _validate(df: pd.DataFrame) -> list[str]:
    msgs: list[str] = []
    out_of_range = df[(df["yield"] < 0) | (df["yield"] > 20)]
    if not out_of_range.empty:
        msgs.append(f"이상 금리 {len(out_of_range)}건 (0~20% 범위 벗어남)")

    max_date = df["date"].max()
    stale = [
        f"{cat}({(max_date - df.loc[df['category']==cat,'date'].max()).days}일)"
        for cat in df["category"].unique()
        if (max_date - df.loc[df["category"] == cat, "date"].max()).days > 30
    ]
    if stale:
        msgs.append(f"데이터 지연 계열: {', '.join(stale[:3])}")
    return msgs


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def get_policy_rate(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["sector"] == POLICY_RATE_SECTOR].copy()


def get_bond_data(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["sector"] != POLICY_RATE_SECTOR].copy()


def get_spread(df: pd.DataFrame, cat_a: str, cat_b: str, tenor: str) -> pd.DataFrame:
    a = df[(df["category"] == cat_a) & (df["tenor"] == tenor)].set_index("date")["yield"]
    b = df[(df["category"] == cat_b) & (df["tenor"] == tenor)].set_index("date")["yield"]
    spread = ((a - b) * 100).rename("spread").dropna()
    return spread.reset_index()


def get_curve(df: pd.DataFrame, category: str, date: pd.Timestamp) -> pd.DataFrame:
    sub = df[(df["category"] == category) & (df["date"] == date)].copy()
    order = {t: i for i, t in enumerate(TENOR_LABELS)}
    sub["_ord"] = sub["tenor"].map(order)
    return sub.sort_values("_ord").drop(columns="_ord")


def get_mom_change(df: pd.DataFrame, category: str, tenor: str) -> pd.Series:
    sub = (
        df[(df["category"] == category) & (df["tenor"] == tenor)]
        .set_index("date")["yield"]
        .sort_index()
    )
    return ((sub - sub.shift(21)) * 100).dropna()