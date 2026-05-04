#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
US Peter Lynch + Benjamin Graham Screener v3

- Universe: S&P 500 / Nasdaq 100 / Dow 30 / Company Add-ons ticker txt files
- Financials: SEC EDGAR companyfacts API
- Price/dividend: yfinance
- Output: TSV compatible with dashboard_us.py

This is intentionally separated from the KR screener.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"

DEFAULT_USER_AGENT = os.environ.get("SEC_USER_AGENT") or "PETER-LYNCH-BENJAMIN-GRAHAM/1.0 contact@example.com"

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def clean_ticker(t: str) -> str:
    t = str(t).strip().upper()
    if not t or t.startswith("#"):
        return ""
    # yfinance uses BRK-B, SEC ticker mapping usually BRK-B too.
    t = t.replace(".", "-")
    return t


def read_tickers(path: str | Path, limit: Optional[int] = None) -> List[str]:
    tickers: List[str] = []
    seen = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            t = clean_ticker(line.split("#", 1)[0])
            if not t or t in seen:
                continue
            seen.add(t)
            tickers.append(t)
            if limit and len(tickers) >= limit:
                break
    return tickers


def safe_float(x: Any) -> float:
    try:
        if x is None:
            return float("nan")
        if isinstance(x, str):
            s = x.replace(",", "").strip()
            if s in {"", "nan", "None", "-"}:
                return float("nan")
            return float(s)
        return float(x)
    except Exception:
        return float("nan")


def fmt(x: Any) -> str:
    v = safe_float(x)
    if math.isnan(v) or math.isinf(v):
        return ""
    return str(v)


def latest_by_year(items: List[Tuple[int, float]]) -> Dict[int, float]:
    out: Dict[int, float] = {}
    for year, val in items:
        if year and pd.notna(val):
            out[int(year)] = float(val)
    return dict(sorted(out.items()))


def cagr(new: float, old: float, years: int) -> float:
    if years <= 0 or not np.isfinite(new) or not np.isfinite(old) or old <= 0 or new <= 0:
        return float("nan")
    return ((new / old) ** (1.0 / years) - 1.0) * 100.0


def yoy(new: float, old: float) -> float:
    if not np.isfinite(new) or not np.isfinite(old) or old == 0:
        return float("nan")
    return ((new - old) / abs(old)) * 100.0


def choose_positive_growth(g1: float, g3: float, g5: float) -> Tuple[str, float]:
    for label, val in [("3년", g3), ("5년", g5), ("1년", g1)]:
        if np.isfinite(val) and val > 0:
            return label, float(val)
    return "판정불가", float("nan")


def judge_peg(x: float) -> str:
    if not np.isfinite(x):
        return "판정불가"
    if x <= 0.5:
        return "매우 유망"
    if x < 1.0:
        return "헐값"
    if x < 2.0:
        return "보통"
    return "불리"


def judge_pegy(x: float) -> str:
    if not np.isfinite(x):
        return "판정불가"
    if x >= 2.0:
        return "안심"
    if x >= 1.5:
        return "양호"
    if x < 1.0:
        return "불리(<1)"
    return "보통"


def final_judgment(peg: float, pegy: float, hard_pass: bool) -> str:
    if not hard_pass:
        return "제외"
    if np.isfinite(peg) and np.isfinite(pegy) and peg <= 0.5 and pegy >= 2.0:
        return "매우 유망"
    if np.isfinite(peg) and np.isfinite(pegy) and peg < 1.0 and pegy >= 1.5:
        return "양호"
    return "보류"

# -----------------------------------------------------------------------------
# SEC client
# -----------------------------------------------------------------------------

class SECClient:
    def __init__(self, user_agent: str = DEFAULT_USER_AGENT, sleep: float = 0.12):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        })
        self.map_session = requests.Session()
        self.map_session.headers.update({
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        })
        self.sleep = sleep
        self._ticker_map: Optional[Dict[str, Dict[str, Any]]] = None

    def ticker_map(self) -> Dict[str, Dict[str, Any]]:
        if self._ticker_map is not None:
            return self._ticker_map
        r = self.map_session.get(SEC_TICKERS_URL, timeout=30)
        r.raise_for_status()
        raw = r.json()
        m: Dict[str, Dict[str, Any]] = {}
        for _, item in raw.items():
            t = clean_ticker(item.get("ticker", ""))
            if not t:
                continue
            m[t] = {
                "cik": int(item["cik_str"]),
                "title": item.get("title", t),
            }
        self._ticker_map = m
        return m

    def companyfacts(self, cik: int) -> Dict[str, Any]:
        time.sleep(self.sleep)
        cik10 = str(int(cik)).zfill(10)
        url = SEC_COMPANYFACTS_URL.format(cik10=cik10)
        r = self.session.get(url, timeout=45)
        r.raise_for_status()
        return r.json()

# -----------------------------------------------------------------------------
# Fact extraction
# -----------------------------------------------------------------------------

@dataclass
class FactSet:
    ticker: str
    name: str
    cik: Optional[int]
    facts: Dict[str, Any]


def get_units_for_tag(facts: Dict[str, Any], tag: str) -> Dict[str, List[Dict[str, Any]]]:
    return facts.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {})


def extract_annual_values(
    facts: Dict[str, Any],
    tags: Iterable[str],
    unit_priority: Iterable[str],
) -> Dict[int, float]:
    """Return annual 10-K FY values by fiscal year for first tag with usable data."""
    for tag in tags:
        units = get_units_for_tag(facts, tag)
        if not units:
            continue
        records: List[Tuple[int, str, float]] = []
        for unit in unit_priority:
            for rec in units.get(unit, []):
                form = str(rec.get("form", ""))
                fp = str(rec.get("fp", ""))
                fy = rec.get("fy")
                val = rec.get("val")
                filed = str(rec.get("filed", ""))
                if form not in {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}:
                    continue
                if fp and fp != "FY":
                    continue
                if fy is None or val is None:
                    continue
                try:
                    records.append((int(fy), filed, float(val)))
                except Exception:
                    continue
        if records:
            # latest filed per fiscal year
            by_year: Dict[int, Tuple[str, float]] = {}
            for fy, filed, val in records:
                if fy not in by_year or filed >= by_year[fy][0]:
                    by_year[fy] = (filed, val)
            return {fy: val for fy, (_, val) in sorted(by_year.items())}
    return {}


def latest_value(values: Dict[int, float]) -> float:
    if not values:
        return float("nan")
    return float(values[max(values.keys())])


def sum_latest(*vals: float) -> float:
    total = 0.0
    any_val = False
    for v in vals:
        if np.isfinite(v):
            total += float(v)
            any_val = True
    return total if any_val else float("nan")


TAGS = {
    "eps": [
        "EarningsPerShareDiluted",
        "EarningsPerShareBasicAndDiluted",
        "EarningsPerShareBasic",
    ],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ],
    "shares": [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingBasic",
        "CommonStocksIncludingAdditionalPaidInCapitalSharesOutstanding",
        "EntityCommonStockSharesOutstanding",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "CashCashEquivalentsAndShortTermInvestments",
    ],
    "marketable": [
        "ShortTermInvestments",
        "MarketableSecuritiesCurrent",
        "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    ],
    "long_debt": [
        "LongTermDebtNoncurrent",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
        "LongTermDebt",
    ],
    "short_debt": [
        "ShortTermBorrowings",
        "ShortTermDebt",
        "CommercialPaper",
        "CommercialPaperCurrent",
        "CurrentPortionOfLongTermDebt",
        "LongTermDebtCurrent",
        "CurrentPortionOfLongTermDebtAndFinanceLeaseObligations",
    ],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "liabilities": ["Liabilities"],
    "cfo": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
}

# -----------------------------------------------------------------------------
# Price and dividend
# -----------------------------------------------------------------------------

def fetch_yahoo_prices(tickers: List[str]) -> Dict[str, float]:
    out = {t: float("nan") for t in tickers}
    if yf is None or not tickers:
        return out
    try:
        data = yf.download(
            tickers=" ".join(tickers),
            period="7d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
        # Use the unadjusted daily Close, not Adj Close.
        # Adj Close is dividend/split-adjusted and can differ from the visible quote price,
        # which made dashboard "current price" look inconsistent with market quote pages.
        if isinstance(data.columns, pd.MultiIndex):
            field = "Close" if "Close" in data.columns.get_level_values(0) else "Adj Close"
            close = data[field]
            for t in tickers:
                if t in close.columns:
                    s = close[t].dropna()
                    if len(s):
                        out[t] = float(s.iloc[-1])
        else:
            field = "Close" if "Close" in data.columns else "Adj Close"
            s = data[field].dropna()
            if len(tickers) == 1 and len(s):
                out[tickers[0]] = float(s.iloc[-1])
    except Exception as e:
        log(f"Yahoo batch price failed: {repr(e)}")
    return out



def _close_frame_from_yf(data: pd.DataFrame, tickers: List[str]) -> pd.DataFrame:
    """Return Close price DataFrame from yfinance download result."""
    if data is None or len(data) == 0:
        return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        field = "Close" if "Close" in data.columns.get_level_values(0) else "Adj Close"
        close = data[field].copy()
        if isinstance(close, pd.Series):
            close = close.to_frame(name=tickers[0])
        return close
    field = "Close" if "Close" in data.columns else "Adj Close"
    if field not in data.columns:
        return pd.DataFrame()
    close = data[[field]].copy()
    if len(tickers) == 1:
        close.columns = [tickers[0]]
    return close


def fetch_yahoo_momentum(tickers: List[str]) -> Dict[str, Dict[str, float | str]]:
    """Fetch auxiliary price-trend metrics. These are NOT used in Lynch/Graham judgments."""
    blank = {
        "3M수익률(보조,%)": float("nan"),
        "6M수익률(보조,%)": float("nan"),
        "12M수익률(보조,%)": float("nan"),
        "52주고점대비(보조,%)": float("nan"),
        "50일이평(보조)": float("nan"),
        "200일이평(보조)": float("nan"),
        "50일선상회(보조)": "판정불가",
        "200일선상회(보조)": "판정불가",
        "추세판정(보조)": "판정불가",
    }
    out: Dict[str, Dict[str, float | str]] = {t: dict(blank) for t in tickers}
    if yf is None or not tickers:
        return out
    try:
        data = yf.download(
            tickers=" ".join(tickers),
            period="1y",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
        close = _close_frame_from_yf(data, tickers)
        for t in tickers:
            if t not in close.columns:
                continue
            s = pd.to_numeric(close[t], errors="coerce").dropna()
            if len(s) < 20:
                continue
            last = float(s.iloc[-1])

            def ret(days: int) -> float:
                if len(s) <= days:
                    return float("nan")
                base = float(s.iloc[-days])
                return (last / base - 1.0) * 100.0 if base > 0 else float("nan")

            r3 = ret(63)
            r6 = ret(126)
            r12 = ret(252)
            hi52 = float(s.tail(252).max()) if len(s) else float("nan")
            gap52 = (last / hi52 - 1.0) * 100.0 if np.isfinite(hi52) and hi52 > 0 else float("nan")
            ma50 = float(s.tail(50).mean()) if len(s) >= 50 else float("nan")
            ma200 = float(s.tail(200).mean()) if len(s) >= 200 else float("nan")
            above50 = "Y" if np.isfinite(ma50) and last > ma50 else "N" if np.isfinite(ma50) else "판정불가"
            above200 = "Y" if np.isfinite(ma200) and last > ma200 else "N" if np.isfinite(ma200) else "판정불가"

            if np.isfinite(ma50) and np.isfinite(ma200) and last > ma50 > ma200 and np.isfinite(r6) and r6 > 0:
                trend = "강한 상승추세"
            elif np.isfinite(ma200) and last > ma200 and np.isfinite(r3) and r3 > 0:
                trend = "상승전환"
            elif (np.isfinite(ma200) and last > ma200) or (np.isfinite(r3) and r3 > 0):
                trend = "중립/개선"
            elif np.isfinite(ma200) and last < ma200 and np.isfinite(r6) and r6 < 0:
                trend = "주의"
            else:
                trend = "판정불가"

            out[t] = {
                "3M수익률(보조,%)": r3,
                "6M수익률(보조,%)": r6,
                "12M수익률(보조,%)": r12,
                "52주고점대비(보조,%)": gap52,
                "50일이평(보조)": ma50,
                "200일이평(보조)": ma200,
                "50일선상회(보조)": above50,
                "200일선상회(보조)": above200,
                "추세판정(보조)": trend,
            }
    except Exception as e:
        log(f"Yahoo momentum failed: {repr(e)}")
    return out

def fetch_yahoo_dividend_yields(tickers: List[str], prices: Dict[str, float]) -> Dict[str, float]:
    out = {t: float("nan") for t in tickers}
    if yf is None:
        return out
    for i, t in enumerate(tickers, 1):
        try:
            tk = yf.Ticker(t)
            info = {}
            try:
                info = tk.get_info()
            except Exception:
                info = getattr(tk, "info", {}) or {}
            dy = info.get("dividendYield")
            if dy is not None and np.isfinite(float(dy)):
                # yfinance sometimes returns 0.0123, sometimes 1.23 in edge cases.
                val = float(dy)
                out[t] = val * 100.0 if val <= 1.0 else val
                continue
            divs = tk.dividends
            if divs is not None and len(divs):
                last = divs.tail(8)  # enough for quarterly dividends
                annual = float(last.tail(4).sum()) if len(last) >= 4 else float(last.sum())
                p = prices.get(t, float("nan"))
                if np.isfinite(p) and p > 0:
                    out[t] = annual / p * 100.0
        except Exception:
            pass
        if i % 50 == 0:
            log(f"Dividend fetch {i}/{len(tickers)}")
    return out

# -----------------------------------------------------------------------------
# Row calculation
# -----------------------------------------------------------------------------

def annual_series_for_metric(facts: Dict[str, Any], metric: str, units: Iterable[str]) -> Dict[int, float]:
    return extract_annual_values(facts, TAGS[metric], units)


def get_metric_latest(facts: Dict[str, Any], metric: str, units: Iterable[str]) -> float:
    return latest_value(annual_series_for_metric(facts, metric, units))


def calc_row(ticker: str, universe: str, sec: SECClient, price: float, div_yield: float, momentum: Optional[Dict[str, float | str]] = None) -> Dict[str, Any]:
    momentum = momentum or {}
    mapping = sec.ticker_map()
    m = mapping.get(clean_ticker(ticker))
    if not m:
        return {
            "티커": ticker,
            "종목명": ticker,
            "유니버스": universe,
            "비고": "SEC ticker mapping 없음",
            "종합판정": "판정불가",
        }
    name = m["title"]
    cik = m["cik"]
    try:
        facts = sec.companyfacts(cik)
    except Exception as e:
        return {
            "티커": ticker,
            "종목명": name,
            "CIK": str(cik).zfill(10),
            "유니버스": universe,
            "비고": f"SEC companyfacts 실패: {type(e).__name__}",
            "종합판정": "판정불가",
        }

    eps_by_year = annual_series_for_metric(facts, "eps", ["USD/shares", "USD / shares"])
    net_income_by_year = annual_series_for_metric(facts, "net_income", ["USD"])
    shares_by_year = annual_series_for_metric(facts, "shares", ["shares"])

    # Fallback EPS = net income / shares if EPS tag is not usable.
    if not eps_by_year and net_income_by_year and shares_by_year:
        for fy in sorted(set(net_income_by_year) & set(shares_by_year)):
            sh = shares_by_year.get(fy, float("nan"))
            ni = net_income_by_year.get(fy, float("nan"))
            if np.isfinite(ni) and np.isfinite(sh) and sh > 0:
                eps_by_year[fy] = ni / sh

    years = sorted(eps_by_year.keys())
    eps = latest_value(eps_by_year)
    latest_year = max(years) if years else None
    eps_prev1 = eps_by_year.get(latest_year - 1, float("nan")) if latest_year else float("nan")
    eps_prev3 = eps_by_year.get(latest_year - 3, float("nan")) if latest_year else float("nan")
    eps_prev5 = eps_by_year.get(latest_year - 5, float("nan")) if latest_year else float("nan")

    g1 = yoy(eps, eps_prev1)
    g3 = cagr(eps, eps_prev3, 3)
    g5 = cagr(eps, eps_prev5, 5)
    growth_label, growth = choose_positive_growth(g1, g3, g5)

    shares = latest_value(shares_by_year)
    if not np.isfinite(shares):
        shares = get_metric_latest(facts, "shares", ["shares"])

    cash = get_metric_latest(facts, "cash", ["USD"])
    marketable = get_metric_latest(facts, "marketable", ["USD"])
    if np.isfinite(cash) and np.isfinite(marketable) and marketable > cash * 1.5:
        # If cash tag was Cash+ST investments, avoid double count.
        pass
    long_debt = get_metric_latest(facts, "long_debt", ["USD"])
    short_debt = get_metric_latest(facts, "short_debt", ["USD"])
    equity = get_metric_latest(facts, "equity", ["USD"])
    liabilities = get_metric_latest(facts, "liabilities", ["USD"])
    cfo = get_metric_latest(facts, "cfo", ["USD"])
    capex = get_metric_latest(facts, "capex", ["USD"])

    cash_like = sum_latest(cash, marketable)
    net_cash = cash_like - (long_debt if np.isfinite(long_debt) else 0.0) if np.isfinite(cash_like) else float("nan")
    conservative_cash = net_cash - (short_debt if np.isfinite(short_debt) else 0.0) if np.isfinite(net_cash) else float("nan")

    net_cash_ps = net_cash / shares if np.isfinite(net_cash) and np.isfinite(shares) and shares > 0 else float("nan")
    cons_cash_ps = conservative_cash / shares if np.isfinite(conservative_cash) and np.isfinite(shares) and shares > 0 else float("nan")

    fcf = cfo - capex if np.isfinite(cfo) and np.isfinite(capex) else float("nan")
    fcf_ps = fcf / shares if np.isfinite(fcf) and np.isfinite(shares) and shares > 0 else float("nan")
    fcf_yield = fcf_ps / price * 100.0 if np.isfinite(fcf_ps) and np.isfinite(price) and price > 0 else float("nan")

    ex_cash_pe = (price - net_cash_ps) / eps if np.isfinite(price) and np.isfinite(net_cash_ps) and np.isfinite(eps) and eps > 0 else float("nan")
    ex_cash_pe_cons = (price - cons_cash_ps) / eps if np.isfinite(price) and np.isfinite(cons_cash_ps) and np.isfinite(eps) and eps > 0 else float("nan")

    peg = ex_cash_pe / growth if np.isfinite(ex_cash_pe) and np.isfinite(growth) and growth > 0 else float("nan")
    pegy_1 = (g1 + div_yield) / ex_cash_pe if np.isfinite(g1) and np.isfinite(div_yield) and np.isfinite(ex_cash_pe) and ex_cash_pe > 0 else float("nan")
    pegy_3 = (g3 + div_yield) / ex_cash_pe if np.isfinite(g3) and np.isfinite(div_yield) and np.isfinite(ex_cash_pe) and ex_cash_pe > 0 else float("nan")
    pegy_5 = (g5 + div_yield) / ex_cash_pe if np.isfinite(g5) and np.isfinite(div_yield) and np.isfinite(ex_cash_pe) and ex_cash_pe > 0 else float("nan")

    pegy_label, pegy = choose_positive_growth(pegy_1, pegy_3, pegy_5)
    # choose_positive_growth labels work because we only need 3Y->5Y->1Y; values are scores.

    def graham(g: float) -> Tuple[float, float, float]:
        if not np.isfinite(g) or not np.isfinite(eps) or not np.isfinite(price) or price <= 0:
            return float("nan"), float("nan"), float("nan")
        fair = 8.5 + 2.0 * g
        intrinsic = eps * fair if np.isfinite(eps) else float("nan")
        gap = (intrinsic / price - 1.0) * 100.0 if np.isfinite(intrinsic) else float("nan")
        return fair, intrinsic, gap

    gp1, gv1, gg1 = graham(g1)
    gp3, gv3, gg3 = graham(g3)
    gp5, gv5, gg5 = graham(g5)
    graham_label, _ = choose_positive_growth(g1, g3, g5)
    if graham_label == "3년":
        gp_sel, gv_sel, gg_sel = gp3, gv3, gg3
    elif graham_label == "5년":
        gp_sel, gv_sel, gg_sel = gp5, gv5, gg5
    elif graham_label == "1년":
        gp_sel, gv_sel, gg_sel = gp1, gv1, gg1
    else:
        gp_sel = gv_sel = gg_sel = float("nan")

    hard_reasons: List[str] = []
    if not (np.isfinite(net_cash_ps) and net_cash_ps > 0):
        hard_reasons.append("주당순현금<=0")
    if not (np.isfinite(fcf_ps) and fcf_ps > 0):
        hard_reasons.append("FCF<=0")
    if not (np.isfinite(ex_cash_pe) and ex_cash_pe > 0):
        hard_reasons.append("순현금차감PER<=0/불가")
    hard_pass = len(hard_reasons) == 0

    peg_j = judge_peg(peg)
    pegy_j = judge_pegy(pegy)
    final = final_judgment(peg, pegy, hard_pass)

    total_debt = sum_latest(long_debt, short_debt)
    equity_ratio = equity / (equity + liabilities) * 100.0 if np.isfinite(equity) and np.isfinite(liabilities) and (equity + liabilities) != 0 else float("nan")
    debt_ratio = liabilities / (equity + liabilities) * 100.0 if np.isfinite(equity) and np.isfinite(liabilities) and (equity + liabilities) != 0 else float("nan")
    equity_debt = equity / liabilities if np.isfinite(equity) and np.isfinite(liabilities) and liabilities != 0 else float("nan")

    note = []
    if np.isfinite(short_debt) and short_debt > 0:
        note.append("단기위험부채 존재")
    if not np.isfinite(price):
        note.append("현재가 없음")
    if not np.isfinite(eps):
        note.append("EPS 없음")

    return {
        "티커": ticker,
        "종목명": name,
        "CIK": str(cik).zfill(10),
        "유니버스": universe,
        "현재가": fmt(price),
        "EPS(FY)": fmt(eps),
        "EPS기준연도": latest_year or "",
        "현금및현금성자산": fmt(cash),
        "유가증권성자산": fmt(marketable),
        "현금성자산합계": fmt(cash_like),
        "장기부채": fmt(long_debt),
        "단기위험부채": fmt(short_debt),
        "주주지분": fmt(equity),
        "총부채": fmt(liabilities),
        "주주지분비중": fmt(equity_ratio),
        "부채비중": fmt(debt_ratio),
        "주주대부채배수": fmt(equity_debt),
        "주당순현금(린치식)": fmt(net_cash_ps),
        "주당순현금(보수형)": fmt(cons_cash_ps),
        "순현금차감PER(린치식)": fmt(ex_cash_pe),
        "순현금차감PER(보수형)": fmt(ex_cash_pe_cons),
        "연간이익증가율(1년,%)": fmt(g1),
        "연간이익증가율(3년CAGR,%)": fmt(g3),
        "연간이익증가율(5년CAGR,%)": fmt(g5),
        "그레이엄적정PER(1년)": fmt(gp1),
        "그레이엄적정PER(3년)": fmt(gp3),
        "그레이엄적정PER(5년)": fmt(gp5),
        "그레이엄내재가치(1년)": fmt(gv1),
        "그레이엄내재가치(3년)": fmt(gv3),
        "그레이엄내재가치(5년)": fmt(gv5),
        "그레이엄괴리율(1년,%)": fmt(gg1),
        "그레이엄괴리율(3년,%)": fmt(gg3),
        "그레이엄괴리율(5년,%)": fmt(gg5),
        "그레이엄사용기준": graham_label,
        "그레이엄적정PER(선택)": fmt(gp_sel),
        "그레이엄내재가치(선택)": fmt(gv_sel),
        "그레이엄괴리율(선택,%)": fmt(gg_sel),
        "배당수익률(%)": fmt(div_yield),
        "배당감안점수(1년)": fmt(pegy_1),
        "배당감안점수(3년)": fmt(pegy_3),
        "배당감안점수(5년)": fmt(pegy_5),
        "주당잉여현금흐름": fmt(fcf_ps),
        "잉여현금흐름수익률(%)": fmt(fcf_yield),
        "배당감안점수기준": pegy_label,
        "배당감안점수": fmt(pegy),
        "배당감안점수판정": pegy_j,
        "사용연성장률기준": growth_label,
        "사용연성장률(%)": fmt(growth),
        "린치PER배수": fmt(peg),
        "린치PER판정": peg_j,
        "하드필터통과": "Y" if hard_pass else "N",
        "하드필터사유": " | ".join(hard_reasons),
        "종합판정": final,
        "종합판정사유": f"PEG={peg_j}, PEGY={pegy_j}",
        "발행주식수": fmt(shares),
        "3M수익률(보조,%)": fmt(momentum.get("3M수익률(보조,%)")),
        "6M수익률(보조,%)": fmt(momentum.get("6M수익률(보조,%)")),
        "12M수익률(보조,%)": fmt(momentum.get("12M수익률(보조,%)")),
        "52주고점대비(보조,%)": fmt(momentum.get("52주고점대비(보조,%)")),
        "50일이평(보조)": fmt(momentum.get("50일이평(보조)")),
        "200일이평(보조)": fmt(momentum.get("200일이평(보조)")),
        "50일선상회(보조)": str(momentum.get("50일선상회(보조)", "")),
        "200일선상회(보조)": str(momentum.get("200일선상회(보조)", "")),
        "추세판정(보조)": str(momentum.get("추세판정(보조)", "")),
        "비고": " | ".join(note),
    }


OUTPUT_COLUMNS = [
    "티커", "종목명", "CIK", "유니버스", "종합판정", "종합판정사유",
    "현재가", "EPS(FY)", "EPS기준연도", "배당수익률(%)",
    "현금및현금성자산", "유가증권성자산", "현금성자산합계", "장기부채", "단기위험부채",
    "주주지분", "총부채", "주주지분비중", "부채비중", "주주대부채배수",
    "주당순현금(린치식)", "주당순현금(보수형)", "순현금차감PER(린치식)", "순현금차감PER(보수형)",
    "연간이익증가율(1년,%)", "연간이익증가율(3년CAGR,%)", "연간이익증가율(5년CAGR,%)",
    "그레이엄적정PER(1년)", "그레이엄적정PER(3년)", "그레이엄적정PER(5년)",
    "그레이엄내재가치(1년)", "그레이엄내재가치(3년)", "그레이엄내재가치(5년)",
    "그레이엄괴리율(1년,%)", "그레이엄괴리율(3년,%)", "그레이엄괴리율(5년,%)",
    "그레이엄사용기준", "그레이엄적정PER(선택)", "그레이엄내재가치(선택)", "그레이엄괴리율(선택,%)",
    "배당감안점수(1년)", "배당감안점수(3년)", "배당감안점수(5년)",
    "주당잉여현금흐름", "잉여현금흐름수익률(%)",
    "배당감안점수기준", "배당감안점수", "배당감안점수판정",
    "사용연성장률기준", "사용연성장률(%)", "린치PER배수", "린치PER판정",
    "하드필터통과", "하드필터사유", "발행주식수",
    "3M수익률(보조,%)", "6M수익률(보조,%)", "12M수익률(보조,%)", "52주고점대비(보조,%)",
    "50일이평(보조)", "200일이평(보조)", "50일선상회(보조)", "200일선상회(보조)", "추세판정(보조)",
    "비고",
]


def sort_df(df: pd.DataFrame) -> pd.DataFrame:
    tmp = df.copy()
    for c in ["린치PER배수", "배당감안점수", "연간이익증가율(3년CAGR,%)", "그레이엄괴리율(3년,%)"]:
        if c in tmp.columns:
            tmp[c] = pd.to_numeric(tmp[c], errors="coerce")
    sort_cols = [c for c in ["린치PER배수", "배당감안점수", "연간이익증가율(3년CAGR,%)", "그레이엄괴리율(3년,%)"] if c in tmp.columns]
    asc = [True, False, False, False][: len(sort_cols)]
    if sort_cols:
        tmp = tmp.sort_values(sort_cols, ascending=asc, na_position="last")
    return tmp


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", required=True, help="Ticker txt file")
    ap.add_argument("--universe-name", default=None, help="Universe label, e.g. Dow 30")
    ap.add_argument("--out", required=True, help="Output TSV path")
    ap.add_argument("--limit", type=int, default=None, help="Only first N tickers for smoke test")
    ap.add_argument("--sec-user-agent", default=DEFAULT_USER_AGENT)
    ap.add_argument("--sleep", type=float, default=0.12, help="SEC request delay seconds")
    args = ap.parse_args()

    universe_file = Path(args.universe)
    universe_name = args.universe_name or universe_file.stem.replace("_tickers", "").upper()
    tickers = read_tickers(universe_file, args.limit)
    if not tickers:
        raise SystemExit(f"No tickers found in {universe_file}")

    log(f"Universe={universe_name}, tickers={len(tickers)}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    prices = fetch_yahoo_prices(tickers)
    price_ok = sum(1 for v in prices.values() if np.isfinite(v))
    log(f"Prices collected: {price_ok}/{len(tickers)}")
    div_yields = fetch_yahoo_dividend_yields(tickers, prices)
    div_ok = sum(1 for v in div_yields.values() if np.isfinite(v))
    log(f"Dividend yields collected: {div_ok}/{len(tickers)}")

    momentum_map = fetch_yahoo_momentum(tickers)
    momentum_ok = sum(1 for m in momentum_map.values() if str(m.get("추세판정(보조)", "")).strip() not in {"", "판정불가"})
    log(f"Aux momentum collected: {momentum_ok}/{len(tickers)}")

    sec = SECClient(args.sec_user_agent, sleep=args.sleep)
    rows: List[Dict[str, Any]] = []
    for i, t in enumerate(tickers, 1):
        try:
            row = calc_row(t, universe_name, sec, prices.get(t, float("nan")), div_yields.get(t, float("nan")), momentum_map.get(t, {}))
        except Exception as e:
            row = {"티커": t, "종목명": t, "유니버스": universe_name, "종합판정": "판정불가", "비고": f"row error: {type(e).__name__}: {e}"}
        rows.append(row)
        if i % 10 == 0 or i == len(tickers):
            log(f"Processed {i}/{len(tickers)}")

    df = pd.DataFrame(rows)
    for c in OUTPUT_COLUMNS:
        if c not in df.columns:
            df[c] = ""
    df = df[OUTPUT_COLUMNS]
    df_sorted = sort_df(df)
    df_sorted.to_csv(args.out, sep="\t", index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)
    log(f"Saved -> {args.out} ({len(df_sorted)} rows)")

    # quick health summary
    for c in ["현재가", "EPS(FY)", "순현금차감PER(린치식)", "린치PER배수", "배당감안점수", "추세판정(보조)", "종합판정"]:
        if c in df_sorted.columns:
            s = df_sorted[c].astype(str).str.strip()
            nonempty = (~s.isin(["", "nan", "None", "-"])).sum()
            log(f"{c}: {nonempty}/{len(df_sorted)}")


if __name__ == "__main__":
    main()
