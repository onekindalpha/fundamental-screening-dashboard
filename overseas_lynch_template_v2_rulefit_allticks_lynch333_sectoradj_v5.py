
#!/usr/bin/env python3
"""
overseas_lynch_template_v2.py

What this does:
1) Fetches overseas ticker data from Yahoo Finance (yfinance)
2) Calculates Peter Lynch-style metrics using ex-cash PER (순현금차감 PER)
3) Adds extra judgement requested by the user:
   - PER vs growth rule:
       * ex-cash PER / annual growth <= 0.5 -> 매우 유망
       * ex-cash PER / annual growth <  1.0 -> 헐값
       * ex-cash PER / annual growth <  2.0 -> 보통
       * ex-cash PER / annual growth >= 2.0 -> 매우 불리
   - Debt / equity structure:
       * equity:debt around 8:2 / 9:1 is good
       * reverse is risky
       * commercial paper / current debt / notes payable are flagged as higher-risk
       * long-term debt is treated as relatively safer
4) Exports:
   - <prefix>_raw.csv
   - <prefix>_filtered.csv
   - templates/<TICKER>_template.csv   (SK hynix-like per-ticker template)

Notes:
- REITs should still be interpreted with care (AFFO/NAV often matter more than EPS).
- If 3Y/5Y growth is missing, the script explains why:
    * prior-year EPS <= 0  -> CAGR not meaningful
    * row missing          -> data missing
- Default tickers can be changed by --tickers

Install:
    pip install yfinance pandas numpy
Run:
    python -u overseas_lynch_template_v2.py --out overseas_v2_all.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf


UNIVERSE: Dict[str, Dict[str, str]] = {
    "CINF":        {"name": "Cincinnati Financial",                 "group": "금융/보험",               "verdict": "보정필요"},
    "UVV":         {"name": "Universal Corp.",                      "group": "담배",                    "verdict": "메인"},
    "MPLX":        {"name": "MPLX LP",                              "group": "에너지/미드스트림",        "verdict": "보정필요"},
    "ENB":         {"name": "Enbridge",                             "group": "에너지/파이프라인",        "verdict": "보정필요"},
    "TRGP":        {"name": "Targa Resources",                      "group": "에너지/미드스트림",        "verdict": "보정필요"},
    "KMI":         {"name": "Kinder Morgan",                        "group": "에너지/파이프라인",        "verdict": "보정필요"},
    "WMB":         {"name": "Williams Companies",                   "group": "에너지/가스인프라",        "verdict": "보정필요"},
    "ET":          {"name": "Energy Transfer",                      "group": "에너지/미드스트림",        "verdict": "보정필요"},
    "OKE":         {"name": "ONEOK",                                "group": "에너지/NGL 인프라",        "verdict": "보정필요"},
    "PBA":         {"name": "Pembina Pipeline",                     "group": "에너지/파이프라인",        "verdict": "보정필요"},
    "CQP":         {"name": "Cheniere Energy Partners",             "group": "LNG/수출터미널",          "verdict": "보정필요"},
    "LNG":         {"name": "Cheniere Energy",                      "group": "LNG/수출터미널",          "verdict": "보정필요"},
    "FRT":         {"name": "Federal Realty",                       "group": "REIT/부동산임대",         "verdict": "보정필요"},
    "MO":          {"name": "Altria Group",                         "group": "담배",                    "verdict": "메인"},
    "O":           {"name": "Realty Income",                        "group": "REIT/부동산임대",         "verdict": "보정필요"},
    "ESS":         {"name": "Essex Property Trust",                 "group": "REIT/부동산임대",         "verdict": "보정필요"},
    "NNN":         {"name": "NNN REIT",                             "group": "REIT/부동산임대",         "verdict": "보정필요"},
    "PG":          {"name": "Procter & Gamble",                     "group": "필수소비재",               "verdict": "메인"},
    "MCD":         {"name": "McDonald's",                           "group": "소비재/프랜차이즈",        "verdict": "메인"},
    "EPD":         {"name": "Enterprise Products Partners",         "group": "에너지/미드스트림",        "verdict": "보정필요"},
    "CL":          {"name": "Colgate-Palmolive",                    "group": "필수소비재",               "verdict": "메인"},
    "LOW":         {"name": "Lowe's",                               "group": "소비재/리테일",            "verdict": "메인"},
    "NEE":         {"name": "NextEra Energy",                       "group": "유틸리티",                "verdict": "보정필요"},
    "EQIX":        {"name": "Equinix",                              "group": "데이터센터/REIT",          "verdict": "보정필요"},
    "DLR":         {"name": "Digital Realty",                       "group": "데이터센터/REIT",          "verdict": "보정필요"},
    "IRM":         {"name": "Iron Mountain",                        "group": "데이터보관/REIT",          "verdict": "보정필요"},
    "SBAC":        {"name": "SBA Communications",                   "group": "통신타워/REIT",            "verdict": "보정필요"},
    "SRVR":        {"name": "Pacer Benchmark Data & Infrastructure", "group": "REIT/인프라 ETF",          "verdict": "보정필요"},
    "WEC":         {"name": "WEC Energy",                           "group": "유틸리티",                "verdict": "보정필요"},
    "T":           {"name": "AT&T",                                 "group": "통신",                    "verdict": "보정필요"},
    "VOD":         {"name": "Vodafone",                             "group": "통신",                    "verdict": "보정필요"},
    "VRT":         {"name": "Vertiv Holdings",                      "group": "전력설비/데이터센터",       "verdict": "메인"},
    "IRDM":        {"name": "Iridium",                              "group": "위성통신/우주통신",        "verdict": "watchlist"},
    "VZ":          {"name": "Verizon",                              "group": "통신",                    "verdict": "보정필요"},
    "GLW":         {"name": "Corning",                              "group": "광통신/산업재",            "verdict": "메인"},
    "GSAT":        {"name": "Globalstar",                           "group": "위성통신/우주통신",        "verdict": "watchlist"},
    "TDS":         {"name": "Telephone and Data Systems",           "group": "통신",                    "verdict": "보정필요"},
    "FCX":         {"name": "Freeport-McMoRan",                     "group": "소재/원자재",              "verdict": "watchlist"},
    "ASTS":        {"name": "AST SpaceMobile",                      "group": "위성통신/우주통신",        "verdict": "watchlist"},
    "PRY.MI":      {"name": "Prysmian",                             "group": "전력케이블/전력망",        "verdict": "메인"},
    "PWR":         {"name": "Quanta Services",                      "group": "재건/전력망 인프라",       "verdict": "메인"},
    "EME":         {"name": "EMCOR Group",                          "group": "재건/전기·기계 설비",      "verdict": "메인"},
    "CAT":         {"name": "Caterpillar",                          "group": "재건/중장비",             "verdict": "메인"},
    "URI":         {"name": "United Rentals",                       "group": "재건/장비렌탈",           "verdict": "보정필요"},
    "GVA":         {"name": "Granite Construction",                 "group": "재건/토목",               "verdict": "보정필요"},
    "J":           {"name": "Jacobs Solutions",                     "group": "재건/엔지니어링",          "verdict": "보정필요"},
    "VMC":         {"name": "Vulcan Materials",                     "group": "재건/골재",               "verdict": "보정필요"},
    "MLM":         {"name": "Martin Marietta Materials",            "group": "재건/골재",               "verdict": "보정필요"},
    "5801.T":      {"name": "Furukawa Electric",                    "group": "전력망/소재",              "verdict": "메인"},
    "5802.T":      {"name": "Sumitomo Electric",                    "group": "전력망/소재",              "verdict": "메인"},
    "VISN":        {"name": "VISN",                                 "group": "광통신/산업재",            "verdict": "watchlist"},
    "600487.SS":   {"name": "600487.SS",                            "group": "광통신/전력망",            "verdict": "메인"},
    "601869.SS":   {"name": "601869.SS",                            "group": "광통신/전력망",            "verdict": "메인"},
    "STLTECH.NS":  {"name": "Sterlite Technologies",                "group": "광통신/전력망",            "verdict": "메인"},
}

YEAR_WINDOW = 5  # target year back to target-4


def log(msg: str) -> None:
    print(msg, flush=True)


def safe_float(x) -> float:
    try:
        if x is None:
            return np.nan
        if isinstance(x, str) and not x.strip():
            return np.nan
        return float(x)
    except Exception:
        return np.nan


def first_non_nan(values: Iterable[object]) -> float:
    for v in values:
        fv = safe_float(v)
        if not pd.isna(fv):
            return fv
    return np.nan


def normalize_statement(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out.columns = [pd.to_datetime(c) for c in out.columns]
    out = out.sort_index(axis=1)  # oldest -> newest
    out.index = [str(i).strip() for i in out.index]
    return out


def row_first(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[pd.Series]:
    if df.empty:
        return None

    lower_map = {str(idx).strip().lower(): idx for idx in df.index}

    # exact
    for cand in candidates:
        k = cand.strip().lower()
        if k in lower_map:
            return df.loc[lower_map[k]]

    # fuzzy contains
    idx_lower = [str(idx).strip().lower() for idx in df.index]
    for cand in candidates:
        k = cand.strip().lower()
        for orig, low in zip(df.index, idx_lower):
            if k in low:
                return df.loc[orig]
    return None


def value_at_year(row: Optional[pd.Series], year: int) -> float:
    if row is None or len(row) == 0:
        return np.nan
    s = row.copy()
    try:
        s.index = [pd.to_datetime(i) for i in s.index]
    except Exception:
        return np.nan
    vals = [safe_float(v) for dt, v in s.items() if getattr(dt, "year", None) == year]
    vals = [v for v in vals if not pd.isna(v)]
    if not vals:
        return np.nan
    return vals[-1]


def series_by_year(row: Optional[pd.Series], years: List[int]) -> Dict[int, float]:
    return {y: value_at_year(row, y) for y in years}


def latest_close(hist: pd.DataFrame) -> float:
    if hist is None or hist.empty or "Close" not in hist.columns:
        return np.nan
    s = hist["Close"].dropna()
    return safe_float(s.iloc[-1]) if len(s) else np.nan


def dps_for_year(dividends: pd.Series, year: int) -> float:
    if dividends is None or len(dividends) == 0:
        return np.nan
    s = dividends.copy()
    try:
        s.index = pd.to_datetime(s.index)
    except Exception:
        return np.nan
    vals = s[s.index.year == year]
    if len(vals) == 0:
        return np.nan
    return safe_float(vals.sum())


def annual_dividends(dividends: pd.Series) -> pd.Series:
    if dividends is None or len(dividends) == 0:
        return pd.Series(dtype=float)
    s = dividends.copy()
    try:
        s.index = pd.to_datetime(s.index)
    except Exception:
        return pd.Series(dtype=float)
    out = s.groupby(s.index.year).sum().astype(float)
    out = out.sort_index()
    return out


def consecutive_dividend_paid_years(annual_divs: pd.Series, target_year: int) -> float:
    if annual_divs is None or len(annual_divs) == 0:
        return np.nan
    years = sorted(int(y) for y in annual_divs.index)
    count = 0
    y = target_year
    while y in years:
        v = safe_float(annual_divs.loc[y])
        if pd.isna(v) or v <= 0:
            break
        count += 1
        y -= 1
    return float(count) if count > 0 else np.nan


def consecutive_dividend_growth_years(annual_divs: pd.Series, target_year: int) -> float:
    if annual_divs is None or len(annual_divs) == 0:
        return np.nan
    years = sorted(int(y) for y in annual_divs.index)
    if target_year not in years:
        return np.nan
    count = 0
    y = target_year
    while (y in years) and ((y - 1) in years):
        cur = safe_float(annual_divs.loc[y])
        prev = safe_float(annual_divs.loc[y - 1])
        if pd.isna(cur) or pd.isna(prev) or cur <= 0 or prev <= 0 or cur <= prev:
            break
        count += 1
        y -= 1
    return float(count) if count > 0 else np.nan


def price_trend_metrics(hist_long: pd.DataFrame) -> Tuple[float, float, float, str]:
    if hist_long is None or hist_long.empty or 'Close' not in hist_long.columns:
        return np.nan, np.nan, np.nan, '판정불가'
    s = hist_long['Close'].dropna().astype(float)
    if len(s) < 30:
        return np.nan, np.nan, np.nan, '판정불가'
    try:
        idx = pd.to_datetime(s.index)
        s.index = idx
    except Exception:
        pass
    end = safe_float(s.iloc[-1])
    ma200 = safe_float(s.tail(200).mean()) if len(s) >= 50 else np.nan

    def _cagr_from_offset(years: int) -> float:
        if not isinstance(s.index, pd.DatetimeIndex):
            return np.nan
        target = s.index[-1] - pd.DateOffset(years=years)
        sub = s[s.index >= target]
        if len(sub) < 2:
            return np.nan
        start = safe_float(sub.iloc[0])
        return cagr_pct(end, start, years)

    cagr3 = _cagr_from_offset(3)
    cagr5 = _cagr_from_offset(5)
    if not pd.isna(end) and not pd.isna(ma200) and end > ma200 and not pd.isna(cagr3) and cagr3 > 0 and (pd.isna(cagr5) or cagr5 > 0):
        label = 'Y'
    elif not pd.isna(cagr3) and cagr3 > 0:
        label = '약Y'
    elif not pd.isna(cagr3):
        label = 'N'
    else:
        label = '판정불가'
    return cagr3, cagr5, ma200, label


def lynch_dividend_stock_label(div_paid_years: float, div_growth_years: float) -> str:
    if pd.isna(div_paid_years) or pd.isna(div_growth_years):
        return ''
    return 'Y' if div_paid_years >= 10 and div_growth_years >= 10 else ''


def custom_dividend_stock_label(div_growth_years: float, price_uptrend: str) -> str:
    if pd.isna(div_growth_years):
        return ''
    if str(price_uptrend) not in {'Y', '약Y'}:
        return ''
    if div_growth_years >= 30:
        return 'Y(30+)'
    if div_growth_years >= 20:
        return 'Y(20+)'
    return ''


def growth_pct(new: float, old: float) -> float:
    if pd.isna(new) or pd.isna(old) or old == 0:
        return np.nan
    try:
        return (new / old - 1.0) * 100.0
    except Exception:
        return np.nan


def cagr_pct(end: float, start: float, years: int) -> float:
    if years <= 0 or pd.isna(end) or pd.isna(start) or start <= 0 or end <= 0:
        return np.nan
    try:
        return ((end / start) ** (1.0 / years) - 1.0) * 100.0
    except Exception:
        return np.nan


def eps_missing_reason(current_eps: float, past_eps: float, label: str) -> str:
    if pd.isna(current_eps):
        return f"{label} 현재 EPS 미추출"
    if pd.isna(past_eps):
        return f"{label} 기준 EPS 미추출"
    if past_eps <= 0 or current_eps <= 0:
        return f"{label} CAGR 불가(EPS<=0)"
    return ""


def pick_shares(tk: yf.Ticker, bs: pd.DataFrame, price: float) -> float:
    # info / fast_info
    for attr in ("fast_info", "info"):
        try:
            obj = getattr(tk, attr)
            if isinstance(obj, dict):
                shares = first_non_nan([
                    obj.get("shares"),
                    obj.get("sharesOutstanding"),
                    obj.get("impliedSharesOutstanding"),
                ])
                if not pd.isna(shares):
                    return shares
        except Exception:
            pass

    row = row_first(bs, [
        "Ordinary Shares Number",
        "Share Issued",
        "Common Stock Shares Outstanding",
        "Shares Outstanding",
    ])
    if row is not None:
        vals = row.dropna()
        if len(vals):
            out = safe_float(vals.iloc[-1])
            if not pd.isna(out):
                return out

    try:
        market_cap = first_non_nan([
            tk.fast_info.get("marketCap"),
            tk.info.get("marketCap"),
        ])
        if not pd.isna(market_cap) and not pd.isna(price) and price > 0:
            return market_cap / price
    except Exception:
        pass
    return np.nan


def fcf_by_year(cf: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    op = row_first(cf, [
        "Operating Cash Flow",
        "Cash Flow From Continuing Operating Activities",
        "Net Cash Provided By Operating Activities",
        "Net Cash Provided by Operating Activities",
    ])
    cap = row_first(cf, [
        "Capital Expenditure",
        "Capital Expenditures",
        "Purchase Of PPE",
        "Purchase of Property Plant and Equipment",
        "Investments In Property Plant And Equipment",
    ])
    result = {}
    for y in years:
        op_v = value_at_year(op, y)
        cap_v = value_at_year(cap, y)
        if pd.isna(op_v) and pd.isna(cap_v):
            result[y] = np.nan
        elif pd.isna(cap_v):
            result[y] = op_v
        elif pd.isna(op_v):
            result[y] = np.nan
        else:
            result[y] = op_v - abs(cap_v)
    return result


def ocf_by_year(cf: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    row = row_first(cf, [
        "Operating Cash Flow",
        "Cash Flow From Continuing Operating Activities",
        "Net Cash Provided By Operating Activities",
        "Net Cash Provided by Operating Activities",
    ])
    return series_by_year(row, years)


def capex_by_year(cf: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    row = row_first(cf, [
        "Capital Expenditure",
        "Capital Expenditures",
        "Purchase Of PPE",
        "Purchase of Property Plant and Equipment",
        "Investments In Property Plant And Equipment",
    ])
    out = series_by_year(row, years)
    # show capex as positive spend
    return {y: (abs(v) if not pd.isna(v) else np.nan) for y, v in out.items()}


def cash_by_year(bs: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    row = row_first(bs, [
        "Cash And Cash Equivalents",
        "Cash",
        "Cash Equivalents",
    ])
    return series_by_year(row, years)


def combined_cash_and_sti_by_year(bs: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    row = row_first(bs, [
        "Cash Cash Equivalents And Short Term Investments",
        "Cash Cash Equivalents And Federal Funds Sold",
    ])
    return series_by_year(row, years)


def sti_by_year(bs: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    row = row_first(bs, [
        "Other Short Term Investments",
        "Short Term Investments",
        "Available For Sale Securities",
        "Marketable Securities",
        "Trading Securities",
    ])
    return series_by_year(row, years)


def long_debt_by_year(bs: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    row = row_first(bs, [
        "Long Term Debt",
        "Long Term Debt And Capital Lease Obligation",
        "Long Term Debt And Lease Obligation",
        "Non Current Debt",
    ])
    return series_by_year(row, years)


def current_debt_by_year(bs: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    row = row_first(bs, [
        "Current Debt",
        "Current Debt And Capital Lease Obligation",
        "Current Debt And Lease Obligation",
        "Short Long Term Debt",
        "Current Portion Of Long Term Debt",
    ])
    return series_by_year(row, years)


def cp_by_year(bs: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    row = row_first(bs, [
        "Commercial Paper",
        "Notes Payable",
        "Short Term Borrowings",
        "Other Current Borrowings",
    ])
    return series_by_year(row, years)


def equity_by_year(bs: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    row = row_first(bs, [
        "Total Equity Gross Minority Interest",
        "Stockholders Equity",
        "Total Stockholder Equity",
        "Common Stock Equity",
        "Net Tangible Assets",
    ])
    return series_by_year(row, years)


def eps_by_year(fin: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    row = row_first(fin, [
        "Diluted EPS",
        "Basic EPS",
        "Reported EPS",
        "Normalized EPS",
    ])
    return series_by_year(row, years)


def build_debt_structure_note(current_debt: float, cp: float, long_debt: float) -> str:
    risky = np.nansum([current_debt, cp])
    safe = long_debt
    if pd.isna(risky) and pd.isna(safe):
        return "부채 구조 미확인"
    if pd.isna(risky):
        risky = 0.0
    if pd.isna(safe):
        safe = 0.0
    total = risky + safe
    if total <= 0:
        return "이자부채 미미"
    risky_ratio = risky / total
    if risky_ratio <= 0.2:
        return "장기차입 중심(상대적으로 안전)"
    elif risky_ratio <= 0.4:
        return "혼합형(보통)"
    else:
        return "단기/상업어음 비중 높음(위험)"


def lynch_per_vs_growth_label(ex_cash_per: float, growth_used: float) -> Tuple[float, str]:
    if pd.isna(ex_cash_per) or pd.isna(growth_used) or growth_used <= 0:
        return np.nan, "판정불가"
    ratio = ex_cash_per / growth_used
    if ratio <= 0.5:
        label = "매우 유망"
    elif ratio < 1.0:
        label = "헐값"
    elif ratio < 2.0:
        label = "보통"
    else:
        label = "매우 불리"
    return ratio, label


def choose_growth_for_lynch(g3: float, g5: float, g1: float) -> Tuple[str, float]:
    # Prefer 3Y CAGR, then 5Y CAGR, then 1Y growth
    if not pd.isna(g3) and g3 > 0:
        return "3년", g3
    if not pd.isna(g5) and g5 > 0:
        return "5년", g5
    if not pd.isna(g1) and g1 > 0:
        return "1년", g1
    return "판정불가", np.nan


def choose_dividend_adjusted_score(score3: float, score5: float, score1: float) -> Tuple[str, float]:
    if not pd.isna(score3):
        return "3년", score3
    if not pd.isna(score5):
        return "5년", score5
    if not pd.isna(score1):
        return "1년", score1
    return "판정불가", np.nan


def dividend_adjusted_score_label(score: float) -> str:
    if pd.isna(score):
        return "판정불가"
    if score >= 2.0:
        return "안심(>=2)"
    if score >= 1.5:
        return "양호(>=1.5)"
    if score >= 1.0:
        return "보통(1~1.5)"
    return "불리(<1)"


def judge_equity_debt(eq: float, debt: float) -> Tuple[float, float, float, str]:
    if pd.isna(eq) and pd.isna(debt):
        return np.nan, np.nan, np.nan, "판정불가"
    eq = 0.0 if pd.isna(eq) else eq
    debt = 0.0 if pd.isna(debt) else debt
    total = eq + debt
    if total <= 0:
        return np.nan, np.nan, np.nan, "판정불가"
    eq_ratio = eq / total
    debt_ratio = debt / total
    multiple = np.nan if debt <= 0 else (eq / debt)
    if eq_ratio >= 0.9:
        label = "9:1급"
    elif eq_ratio >= 0.8:
        label = "8:2급"
    elif eq_ratio >= 0.7:
        label = "7:3급"
    elif eq_ratio >= 0.5:
        label = "중립"
    else:
        label = "부채우위"
    return eq_ratio * 100.0, debt_ratio * 100.0, multiple, label


def sector_adjustment_type_label(group: str) -> str:
    g = str(group)
    # REIT / tower REIT / data-center REIT should be treated as REIT first,
    # not as plain telecom.
    if "REIT" in g:
        return "REIT보정"
    if "금융" in g:
        return "금융보정"
    if "담배" in g:
        return "담배보정"
    if "통신" in g:
        return "통신보정"
    return "일반"


def sector_adjusted_judgement_label(
    group: str,
    divadj_score: float,
    ex_cash_per: float,
    fcf_ps: float,
    div_yield: float,
    debt_structure_label: str,
    lynch_label: str,
    div_paid_years: float,
    div_growth_years: float,
    price_uptrend: str,
) -> str:
    g = str(group)
    debt_note = "" if debt_structure_label is None else str(debt_structure_label)
    risky_short = "위험" in debt_note
    safe_long = "장기차입 중심" in debt_note
    has_div = not pd.isna(div_yield) and div_yield > 0

    if "금융" in g:
        if pd.isna(divadj_score) or pd.isna(ex_cash_per):
            return "보정판정불가"
        if divadj_score >= 2.0 and ex_cash_per > 0 and ex_cash_per <= 15:
            return "보정양호"
        if divadj_score >= 1.5 and ex_cash_per > 0:
            return "보정보류"
        return "보정주의"

    if "REIT" in g:
        if pd.isna(div_paid_years) and pd.isna(div_yield):
            return "보정판정불가"
        if has_div and safe_long and not risky_short and (
            (not pd.isna(div_paid_years) and div_paid_years >= 5)
            or lynch_label in {"매우 유망", "헐값", "보통"}
        ):
            return "보정양호"
        if has_div and not risky_short:
            return "보정보류"
        return "보정주의"

    if "담배" in g:
        if pd.isna(fcf_ps) and pd.isna(div_paid_years):
            return "보정판정불가"
        if (
            not pd.isna(fcf_ps)
            and fcf_ps > 0
            and has_div
            and not risky_short
            and (
                (not pd.isna(div_growth_years) and div_growth_years >= 10)
                or lynch_label in {"매우 유망", "헐값", "보통"}
            )
        ):
            return "보정양호"
        if not pd.isna(fcf_ps) and fcf_ps > 0 and has_div:
            return "보정보류"
        return "보정주의"

    if "통신" in g:
        if pd.isna(fcf_ps) or pd.isna(divadj_score):
            return "보정판정불가"
        if fcf_ps > 0 and divadj_score >= 1.5 and has_div and not risky_short:
            return "보정양호"
        if fcf_ps > 0 and divadj_score >= 1.0:
            return "보정보류"
        return "보정주의"

    return "일반"


def overall_judgement_label(hard_filter_ok: bool, divadj_score: float, lynch_ratio: float) -> str:
    if not hard_filter_ok:
        return "제외"
    if pd.isna(divadj_score) or pd.isna(lynch_ratio):
        return "보류"
    if divadj_score >= 2.0 and lynch_ratio <= 0.5:
        return "매우 유망"
    if divadj_score >= 1.5 and lynch_ratio < 1.0:
        return "양호"
    if divadj_score < 1.0 or lynch_ratio >= 2.0:
        return "제외"
    return "보류"
def remarks(meta_group: str, net_cash_ps: float, fcf_ps: float, eps_y0: float, g1: float,
            g3_reason: str, g5_reason: str, debt_structure_label: str, lynch_label: str) -> str:
    notes: List[str] = []
    if "REIT" in str(meta_group):
        notes.append("린치식 단독판정 비중 낮춤(REIT)")
    if not pd.isna(net_cash_ps) and net_cash_ps < 0:
        notes.append("주당순현금 음수")
    if not pd.isna(fcf_ps) and fcf_ps < 0:
        notes.append("주당FCF 음수")
    if not pd.isna(eps_y0) and eps_y0 <= 0:
        notes.append("EPS 음수/약함")
    if not pd.isna(g1) and g1 > 100:
        notes.append("1년 점수 과열 가능")
    if g3_reason:
        notes.append(g3_reason)
    if g5_reason:
        notes.append(g5_reason)
    if debt_structure_label:
        notes.append(debt_structure_label)
    if lynch_label:
        notes.append(f"린치PER판정:{lynch_label}")
    return "; ".join(dict.fromkeys(notes))


def growth_priority_score(score1: float, score3: float, score5: float, fcf_yield: float, div_yield: float,
                         eps_y0: float, g3: float, g5: float, eq_ratio: float, debt_structure_label: str,
                         ex_cash_per: float, growth_used: float) -> float:
    score = 0.0
    score += 0 if pd.isna(score3) else score3 * 0.35
    score += 0 if pd.isna(score1) else score1 * 0.20
    score += 0 if pd.isna(score5) else score5 * 0.15
    score += 0 if pd.isna(fcf_yield) else fcf_yield * 0.15
    score += 0 if pd.isna(div_yield) else div_yield * 0.05

    if not pd.isna(eq_ratio):
        if eq_ratio >= 80:
            score += 0.75
        elif eq_ratio >= 70:
            score += 0.40
        elif eq_ratio < 50:
            score -= 0.50

    if "위험" in str(debt_structure_label):
        score -= 0.50

    if pd.isna(g3) and pd.isna(g5):
        score -= 0.75

    if not pd.isna(eps_y0) and eps_y0 <= 0:
        score -= 2.0

    ratio, _label = lynch_per_vs_growth_label(ex_cash_per, growth_used)
    if not pd.isna(ratio):
        if ratio <= 0.5:
            score += 1.0
        elif ratio < 1.0:
            score += 0.5
        elif ratio >= 2.0:
            score -= 0.5

    return score


def dividend_priority_score(div_paid_years: float, div_growth_years: float, div_yield: float,
                            fcf_yield: float, price_uptrend: str) -> float:
    score = 0.0
    score += 0 if pd.isna(div_paid_years) else min(div_paid_years, 30.0) * 0.10
    score += 0 if pd.isna(div_growth_years) else min(div_growth_years, 30.0) * 0.20
    score += 0 if pd.isna(div_yield) else div_yield * 0.60
    score += 0 if pd.isna(fcf_yield) else max(min(fcf_yield, 20.0), -20.0) * 0.20

    if str(price_uptrend) == 'Y':
        score += 1.0
    elif str(price_uptrend) == '약Y':
        score += 0.4
    elif str(price_uptrend) == 'N':
        score -= 0.5

    return score


def lynch_growth_stock_label(overall_judgement: str) -> str:
    return 'Y' if str(overall_judgement) in {'매우 유망', '양호'} else ''


def build_template_rows(meta: Dict[str, str],
                        years: List[int],
                        cash: Dict[int, float],
                        sti: Dict[int, float],
                        long_debt: Dict[int, float],
                        current_debt: Dict[int, float],
                        cp: Dict[int, float],
                        equity: Dict[int, float],
                        ocf: Dict[int, float],
                        capex: Dict[int, float],
                        fcf: Dict[int, float],
                        eps: Dict[int, float],
                        shares_current: float,
                        dps_y0: float,
                        price: float,
                        ex_cash_per: float,
                        g1: float, g3: float, g5: float,
                        div_yield: float, payout_ratio: float,
                        score1: float, score3: float, score5: float,
                        fcf_ps: float, fcf_yield: float,
                        eq_ratio: float, debt_ratio: float, eq_multiple: float,
                        short_risky_amt: float, long_debt_y0: float, debt_structure_label: str,
                        growth_rate_label: str, growth_rate: float, lynch_ratio: float, lynch_label: str,
                        divadj_label: str, divadj_score: float, divadj_status: str,
                        sector_adj_type: str, sector_adj_judgement: str,
                        div_paid_years: float, div_growth_years: float,
                        price_cagr3: float, price_cagr5: float, price_ma200: float, price_uptrend: str,
                        lynch_dividend_flag: str, custom_dividend_flag: str,
                        g3_reason: str, g5_reason: str, final_note: str) -> pd.DataFrame:
    cols = ["항목"] + [str(y) for y in years]
    rows = []

    def add(label: str, d: Dict[int, float]):
        rows.append([label] + [d.get(y, np.nan) for y in years])

    cash_total = {y: np.nansum([cash.get(y, np.nan), sti.get(y, np.nan)]) for y in years}
    lynch_net_cash = {y: np.nan if pd.isna(cash_total.get(y, np.nan)) and pd.isna(long_debt.get(y, np.nan))
                      else cash_total.get(y, np.nan) - long_debt.get(y, np.nan) for y in years}
    conservative_net_cash = {y: np.nan if pd.isna(cash_total.get(y, np.nan)) and pd.isna(long_debt.get(y, np.nan))
                             else cash_total.get(y, np.nan) - long_debt.get(y, np.nan) - current_debt.get(y, np.nan) - cp.get(y, np.nan) for y in years}

    add("현금및현금성자산", cash)
    add("유가증권/단기운용자산", sti)
    add("현금성자산 합계 (A)", cash_total)
    add("장기부채 + 비유동차입금 (B)", long_debt)
    add("유동 차입금 (C)", current_debt)
    add("상업어음/단기위험부채 (D)", cp)
    add("린치식 순현금 = A - B", lynch_net_cash)
    add("보수형 순현금 = A - B - C - D", conservative_net_cash)
    add("주주지분", equity)
    total_debt = {y: np.nansum([long_debt.get(y, np.nan), current_debt.get(y, np.nan), cp.get(y, np.nan)]) for y in years}
    add("총이자부채", total_debt)
    add("영업현금흐름(OCF)", ocf)
    add("CAPEX", capex)
    add("잉여현금흐름(FCF)", fcf)
    add("EPS(기본/희석)", eps)

    # current-year only block
    rows.extend([
        ["주식수(현재)", shares_current] + [np.nan] * (len(years)-1),
        ["현금배당금(FY target DPS)", dps_y0] + [np.nan] * (len(years)-1),
        ["주당순현금(린치식)", np.nan if pd.isna(shares_current) or shares_current <= 0 else lynch_net_cash[years[0]] / shares_current] + [np.nan] * (len(years)-1),
        ["주당순현금(보수형)", np.nan if pd.isna(shares_current) or shares_current <= 0 else conservative_net_cash[years[0]] / shares_current] + [np.nan] * (len(years)-1),
        ["현재가", price] + [np.nan] * (len(years)-1),
        ["순현금차감PER(린치식)", ex_cash_per] + [np.nan] * (len(years)-1),
        ["연간 이익 증가율(1년,%)", g1] + [np.nan] * (len(years)-1),
        ["연간 이익 증가율(3년CAGR,%)", g3] + [np.nan] * (len(years)-1),
        ["연간 이익 증가율(5년CAGR,%)", g5] + [np.nan] * (len(years)-1),
        ["배당수익률(%)", div_yield] + [np.nan] * (len(years)-1),
        ["배당성향(%)", payout_ratio] + [np.nan] * (len(years)-1),
        ["배당감안 이익성장률(1년)", score1] + [np.nan] * (len(years)-1),
        ["배당감안 이익성장률(3년)", score3] + [np.nan] * (len(years)-1),
        ["배당감안 이익성장률(5년)", score5] + [np.nan] * (len(years)-1),
        ["주당잉여현금흐름", fcf_ps] + [np.nan] * (len(years)-1),
        ["잉여현금흐름 수익률(%)", fcf_yield] + [np.nan] * (len(years)-1),
        ["주주지분 비중(%)", eq_ratio] + [np.nan] * (len(years)-1),
        ["부채 비중(%)", debt_ratio] + [np.nan] * (len(years)-1),
        ["주주지분 대 부채 배수", eq_multiple] + [np.nan] * (len(years)-1),
        ["단기위험부채(현재)", short_risky_amt] + [np.nan] * (len(years)-1),
        ["장기차입금(현재)", long_debt_y0] + [np.nan] * (len(years)-1),
        ["부채구조 판정", debt_structure_label] + [np.nan] * (len(years)-1),
        ["배당감안점수기준", divadj_label] + [np.nan] * (len(years)-1),
        ["배당감안점수", divadj_score] + [np.nan] * (len(years)-1),
        ["배당감안점수판정", divadj_status] + [np.nan] * (len(years)-1),
        ["연성장률기준", growth_rate_label] + [np.nan] * (len(years)-1),
        ["연성장률(%)", growth_rate] + [np.nan] * (len(years)-1),
        ["린치PER배수", lynch_ratio] + [np.nan] * (len(years)-1),
        ["린치PER판정", lynch_label] + [np.nan] * (len(years)-1),
        ["업종보정유형", sector_adj_type] + [np.nan] * (len(years)-1),
        ["업종보정판정", sector_adj_judgement] + [np.nan] * (len(years)-1),
        ["배당연속지급연수", div_paid_years] + [np.nan] * (len(years)-1),
        ["배당연속증가연수", div_growth_years] + [np.nan] * (len(years)-1),
        ["주가3년CAGR(%)", price_cagr3] + [np.nan] * (len(years)-1),
        ["주가5년CAGR(%)", price_cagr5] + [np.nan] * (len(years)-1),
        ["주가200일이평", price_ma200] + [np.nan] * (len(years)-1),
        ["주가우상향", price_uptrend] + [np.nan] * (len(years)-1),
        ["린치식배당주", lynch_dividend_flag] + [np.nan] * (len(years)-1),
        ["내식배당주", custom_dividend_flag] + [np.nan] * (len(years)-1),
        ["3Y 결측 사유", g3_reason] + [np.nan] * (len(years)-1),
        ["5Y 결측 사유", g5_reason] + [np.nan] * (len(years)-1),
        ["비고", final_note] + [np.nan] * (len(years)-1),
    ])

    df = pd.DataFrame(rows, columns=cols)
    return df


def evaluate_ticker(ticker: str, bsns_year: int) -> Tuple[dict, pd.DataFrame]:
    meta = UNIVERSE.get(ticker, {"name": ticker, "group": "기타", "verdict": "메인"})
    tk = yf.Ticker(ticker)

    hist = tk.history(period="1mo", auto_adjust=False)
    hist_long = tk.history(period="10y", auto_adjust=True)
    price = latest_close(hist)

    fin = normalize_statement(getattr(tk, "income_stmt", pd.DataFrame()))
    bs = normalize_statement(getattr(tk, "balance_sheet", pd.DataFrame()))
    cf = normalize_statement(getattr(tk, "cashflow", pd.DataFrame()))
    dividends = getattr(tk, "dividends", pd.Series(dtype=float))

    years = list(range(bsns_year, bsns_year - YEAR_WINDOW, -1))

    cash = cash_by_year(bs, years)
    sti = sti_by_year(bs, years)
    combined_cash_sti = combined_cash_and_sti_by_year(bs, years)
    for y in years:
        if pd.isna(sti.get(y, np.nan)) and not pd.isna(combined_cash_sti.get(y, np.nan)):
            cash_v = cash.get(y, np.nan)
            combined_v = combined_cash_sti.get(y, np.nan)
            if pd.isna(cash_v):
                sti[y] = np.nan
            else:
                sti[y] = max(combined_v - cash_v, 0.0)
    long_debt = long_debt_by_year(bs, years)
    current_debt = current_debt_by_year(bs, years)
    cp = cp_by_year(bs, years)
    equity = equity_by_year(bs, years)
    ocf = ocf_by_year(cf, years)
    capex = capex_by_year(cf, years)
    fcf = fcf_by_year(cf, years)
    eps = eps_by_year(fin, years)

    shares_current = pick_shares(tk, bs, price)

    y0, y1, y3, y5 = bsns_year, bsns_year - 1, bsns_year - 3, bsns_year - 5
    eps_y0 = eps.get(y0, np.nan)
    eps_y1 = eps.get(y1, np.nan)
    eps_y3 = eps.get(y3, np.nan)
    eps_y5 = eps.get(y5, np.nan)

    g1 = growth_pct(eps_y0, eps_y1)
    g3 = cagr_pct(eps_y0, eps_y3, 3)
    g5 = cagr_pct(eps_y0, eps_y5, 5)
    g3_reason = "" if not pd.isna(g3) else eps_missing_reason(eps_y0, eps_y3, "3Y")
    g5_reason = "" if not pd.isna(g5) else eps_missing_reason(eps_y0, eps_y5, "5Y")

    dps = dps_for_year(dividends, bsns_year)
    annual_divs = annual_dividends(dividends)
    div_paid_years = consecutive_dividend_paid_years(annual_divs, bsns_year)
    div_growth_years = consecutive_dividend_growth_years(annual_divs, bsns_year)
    price_cagr3, price_cagr5, price_ma200, price_uptrend = price_trend_metrics(hist_long)
    lynch_dividend_flag = lynch_dividend_stock_label(div_paid_years, div_growth_years)
    custom_dividend_flag = custom_dividend_stock_label(div_growth_years, price_uptrend)
    dividend_yield = (dps / price * 100.0) if not pd.isna(dps) and not pd.isna(price) and price > 0 else np.nan
    payout_ratio = (dps / eps_y0 * 100.0) if not pd.isna(dps) and not pd.isna(eps_y0) and eps_y0 > 0 else np.nan

    cash_total_y0 = np.nansum([cash.get(y0, np.nan), sti.get(y0, np.nan)])
    long_debt_y0 = long_debt.get(y0, np.nan)
    current_debt_y0 = current_debt.get(y0, np.nan)
    cp_y0 = cp.get(y0, np.nan)

    net_cash_ps = np.nan
    conservative_net_cash_ps = np.nan
    if not pd.isna(shares_current) and shares_current > 0:
        net_cash_ps = (cash_total_y0 - long_debt_y0) / shares_current
        conservative_net_cash_ps = (cash_total_y0 - long_debt_y0 - current_debt_y0 - cp_y0) / shares_current

    ex_cash_per = np.nan
    if not pd.isna(price) and not pd.isna(net_cash_ps) and not pd.isna(eps_y0) and eps_y0 != 0:
        ex_cash_per = (price - net_cash_ps) / eps_y0

    score1 = (g1 + dividend_yield) / ex_cash_per if not pd.isna(g1) and not pd.isna(dividend_yield) and not pd.isna(ex_cash_per) and ex_cash_per > 0 else np.nan
    score3 = (g3 + dividend_yield) / ex_cash_per if not pd.isna(g3) and not pd.isna(dividend_yield) and not pd.isna(ex_cash_per) and ex_cash_per > 0 else np.nan
    score5 = (g5 + dividend_yield) / ex_cash_per if not pd.isna(g5) and not pd.isna(dividend_yield) and not pd.isna(ex_cash_per) and ex_cash_per > 0 else np.nan

    fcf_y0 = fcf.get(y0, np.nan)
    fcf_ps = (fcf_y0 / shares_current) if not pd.isna(fcf_y0) and not pd.isna(shares_current) and shares_current > 0 else np.nan
    fcf_yield = (fcf_ps / price * 100.0) if not pd.isna(fcf_ps) and not pd.isna(price) and price > 0 else np.nan

    total_debt_y0 = np.nansum([long_debt_y0, current_debt_y0, cp_y0])
    eq_ratio, debt_ratio, eq_multiple, eq_label = judge_equity_debt(equity.get(y0, np.nan), total_debt_y0)

    short_risky_amt = np.nansum([current_debt_y0, cp_y0])
    debt_structure_label = build_debt_structure_note(current_debt_y0, cp_y0, long_debt_y0)

    divadj_label, divadj_score = choose_dividend_adjusted_score(score3, score5, score1)
    divadj_status = dividend_adjusted_score_label(divadj_score)
    growth_rate_label, growth_rate = choose_growth_for_lynch(g3, g5, g1)
    lynch_ratio, lynch_label = lynch_per_vs_growth_label(ex_cash_per, growth_rate)
    sector_adj_type = sector_adjustment_type_label(meta["group"])
    sector_adj_judgement = sector_adjusted_judgement_label(
        meta["group"],
        divadj_score,
        ex_cash_per,
        fcf_ps,
        dividend_yield,
        debt_structure_label,
        lynch_label,
        div_paid_years,
        div_growth_years,
        price_uptrend,
    )
    hard_filter_ok = bool((not pd.isna(net_cash_ps)) and net_cash_ps > 0 and (not pd.isna(fcf_ps)) and fcf_ps > 0 and (not pd.isna(ex_cash_per)) and ex_cash_per > 0)
    overall_judgement = overall_judgement_label(hard_filter_ok, divadj_score, lynch_ratio)

    note = remarks(meta["group"], net_cash_ps, fcf_ps, eps_y0, g1, g3_reason, g5_reason, debt_structure_label, lynch_label)
    if not pd.isna(divadj_score) and divadj_score < 1.0:
        note = (note + '; ' if note else '') + '배당감안점수<1'
    if lynch_label == '매우 불리':
        note = (note + '; ' if note else '') + 'PER>연성장률의 2배'

    growth_priority = growth_priority_score(
        score1, score3, score5, fcf_yield, dividend_yield,
        eps_y0, g3, g5, eq_ratio, debt_structure_label, ex_cash_per, growth_rate
    )

    dividend_priority = dividend_priority_score(div_paid_years, div_growth_years, dividend_yield, fcf_yield, price_uptrend)
    growth_flag = lynch_growth_stock_label(overall_judgement)

    row = {
        "티커": ticker,
        "종목명": meta["name"],
        "그룹": meta["group"],
        "판정구분": meta["verdict"],
        "현재가": price,
        f"현금배당금(FY{bsns_year} DPS)": dps,
        f"EPS(FY{bsns_year})": eps_y0,
        "주당순현금(린치식)": net_cash_ps,
        "주당순현금(보수형)": conservative_net_cash_ps,
        "순현금차감PER(린치식)": ex_cash_per,
        "연간이익증가율(1년,%)": g1,
        "연간이익증가율(3년CAGR,%)": g3,
        "연간이익증가율(5년CAGR,%)": g5,
        "배당수익률(%)": dividend_yield,
        "배당성향(%)": payout_ratio,
        "배당감안이익성장률(1년)": score1,
        "배당감안이익성장률(3년)": score3,
        "배당감안이익성장률(5년)": score5,
        "주당잉여현금흐름": fcf_ps,
        "잉여현금흐름수익률(%)": fcf_yield,
        "주주지분": equity.get(y0, np.nan),
        "총이자부채": total_debt_y0,
        "주주지분비중(%)": eq_ratio,
        "부채비중(%)": debt_ratio,
        "주주지분대부채배수": eq_multiple,
        "단기위험부채": short_risky_amt,
        "장기차입금": long_debt_y0,
        "부채구조판정": debt_structure_label,
        "배당감안점수기준": divadj_label,
        "배당감안점수": divadj_score,
        "배당감안점수판정": divadj_status,
        "연성장률기준": growth_rate_label,
        "연성장률(%)": growth_rate,
        "린치PER배수": lynch_ratio,
        "린치PER판정": lynch_label,
        "업종보정유형": sector_adj_type,
        "업종보정판정": sector_adj_judgement,
        "배당연속지급연수": div_paid_years,
        "배당연속증가연수": div_growth_years,
        "주가3년CAGR(%)": price_cagr3,
        "주가5년CAGR(%)": price_cagr5,
        "주가200일이평": price_ma200,
        "주가우상향": price_uptrend,
        "린치식성장주": growth_flag,
        "린치식배당주": lynch_dividend_flag,
        "내식배당주": custom_dividend_flag,
        "하드필터통과": "Y" if hard_filter_ok else "N",
        "종합판정": overall_judgement,
        "3Y결측사유": g3_reason,
        "5Y결측사유": g5_reason,
        "발행주식수": shares_current,
        "비고": note,
        "성장주우선순위": growth_priority,
        "배당주우선순위": dividend_priority,
    }

    template_df = build_template_rows(
        meta=meta,
        years=years,
        cash=cash, sti=sti, long_debt=long_debt, current_debt=current_debt, cp=cp, equity=equity,
        ocf=ocf, capex=capex, fcf=fcf, eps=eps,
        shares_current=shares_current,
        dps_y0=dps, price=price, ex_cash_per=ex_cash_per,
        g1=g1, g3=g3, g5=g5,
        div_yield=dividend_yield, payout_ratio=payout_ratio, score1=score1, score3=score3, score5=score5,
        fcf_ps=fcf_ps, fcf_yield=fcf_yield,
        eq_ratio=eq_ratio, debt_ratio=debt_ratio, eq_multiple=eq_multiple,
        short_risky_amt=short_risky_amt, long_debt_y0=long_debt_y0,
        debt_structure_label=debt_structure_label,
        growth_rate_label=growth_rate_label, growth_rate=growth_rate,
        lynch_ratio=lynch_ratio, lynch_label=lynch_label,
        divadj_label=divadj_label, divadj_score=divadj_score, divadj_status=divadj_status,
        sector_adj_type=sector_adj_type, sector_adj_judgement=sector_adj_judgement,
        div_paid_years=div_paid_years, div_growth_years=div_growth_years,
        price_cagr3=price_cagr3, price_cagr5=price_cagr5, price_ma200=price_ma200, price_uptrend=price_uptrend,
        lynch_dividend_flag=lynch_dividend_flag, custom_dividend_flag=custom_dividend_flag,
        g3_reason=g3_reason, g5_reason=g5_reason, final_note=note
    )

    return row, template_df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="CINF,UVV,MPLX,ENB,TRGP,KMI,WMB,ET,OKE,PBA,CQP,LNG,FRT,MO,O,ESS,NNN,PG,MCD,EPD,CL,LOW,NEE,EQIX,DLR,IRM,SBAC,SRVR,WEC,T,VOD,VRT,IRDM,VZ,GLW,GSAT,TDS,FCX,ASTS,PWR,EME,CAT,URI,GVA,J,VMC,MLM,PRY.MI,5801.T,5802.T,VISN,600487.SS,601869.SS,STLTECH.NS")
    ap.add_argument("--bsns-year", type=int, default=2025)
    ap.add_argument("--out", default="overseas_v2.csv", help="prefix name")
    args = ap.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    out_prefix = args.out.replace(".csv", "")

    rows = []
    template_dir = Path(f"{out_prefix}_templates")
    template_dir.mkdir(parents=True, exist_ok=True)

    for i, ticker in enumerate(tickers, 1):
        log(f"[{i}/{len(tickers)}] {ticker}")
        try:
            row, tdf = evaluate_ticker(ticker, args.bsns_year)
            rows.append(row)
            tdf.to_csv(template_dir / f"{ticker}_template.csv", index=False, encoding="utf-8-sig")
        except Exception as e:
            rows.append({
                "티커": ticker,
                "종목명": UNIVERSE.get(ticker, {}).get("name", ticker),
                "그룹": UNIVERSE.get(ticker, {}).get("group", "기타"),
                "판정구분": UNIVERSE.get(ticker, {}).get("verdict", "메인"),
                "비고": f"ERROR: {e}",
                "성장주우선순위": np.nan,
                "배당주우선순위": np.nan,
            })

    df = pd.DataFrame(rows)

    def _series(name: str, default=np.nan):
        if name in df.columns:
            return df[name]
        return pd.Series([default] * len(df), index=df.index)

    hard_filter = _series("하드필터통과", "N").astype(str).eq("Y")
    divadj_score = pd.to_numeric(_series("배당감안점수"), errors="coerce")
    lynch_ratio = pd.to_numeric(_series("린치PER배수"), errors="coerce")
    ex_cash_per = pd.to_numeric(_series("순현금차감PER(린치식)"), errors="coerce")
    strict = (
        hard_filter &
        (divadj_score >= 1.5) &
        (lynch_ratio < 1.0) &
        (ex_cash_per > 0)
    )

    raw_path = f"{out_prefix}_raw.csv"
    filtered_path = f"{out_prefix}_filtered.csv"

    sort_cols = []
    ascending = []
    for col, asc in [
        ("종합판정", True),
        ("배당감안점수", False),
        ("린치PER배수", True),
        ("성장주우선순위", False),
        ("배당주우선순위", False),
    ]:
        if col in df.columns:
            sort_cols.append(col)
            ascending.append(asc)

    if sort_cols:
        df = df.sort_values(sort_cols, ascending=ascending, na_position="last")

    df.to_csv(raw_path, index=False, encoding="utf-8-sig")

    filtered_df = df.loc[strict].copy()
    if "성장주우선순위" in filtered_df.columns:
        sort_cols_filtered = [c for c in ["성장주우선순위", "배당주우선순위"] if c in filtered_df.columns]
        filtered_df = filtered_df.sort_values(sort_cols_filtered, ascending=[False] * len(sort_cols_filtered), na_position="last")
    filtered_df.to_csv(filtered_path, index=False, encoding="utf-8-sig")

    with pd.option_context("display.max_columns", None, "display.width", 260):
        print(df.to_string(index=False))

    print(f"\nSaved raw      -> {raw_path}")
    print(f"Saved filtered -> {filtered_path}")
    print(f"Saved templates -> {template_dir}/<TICKER>_template.csv")


if __name__ == "__main__":
    main()
