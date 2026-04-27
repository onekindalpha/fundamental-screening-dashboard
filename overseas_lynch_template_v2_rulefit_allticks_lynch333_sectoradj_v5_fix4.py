#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd
import requests

BASE_CANDIDATES = [
    'overseas_lynch_template_v2_rulefit_allticks_lynch333_sectoradj_v5_fix3.py',
    'overseas_lynch_template_v2_rulefit_allticks_lynch333_sectoradj_v5.py',
]

THIS_DIR = Path(__file__).resolve().parent
BASE_PATH = None
for name in BASE_CANDIDATES:
    p = THIS_DIR / name
    if p.exists() and p.name != Path(__file__).name:
        BASE_PATH = p
        break
if BASE_PATH is None:
    raise SystemExit('Base overseas script not found next to fix4.')

spec = importlib.util.spec_from_file_location('overseas_base_mod', str(BASE_PATH))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

SEC_ALLOWED_FORMS = {'10-K', '10-K/A', '10-KT', '20-F', '20-F/A', '40-F', '40-F/A'}
SEC_USER_AGENT = os.environ.get('SEC_USER_AGENT', 'jin-lynch-screener/1.0 contact@example.com')

CURRENT_TICKER: Optional[str] = None
CURRENT_YEAR: Optional[int] = None
CURRENT_CONTEXT: Dict[str, set] = {}


def _ctx_add(key: str, value: str) -> None:
    if CURRENT_CONTEXT is None:
        return
    CURRENT_CONTEXT.setdefault(key, set()).add(value)


def _is_us_like_ticker(ticker: str) -> bool:
    t = str(ticker or '').upper().strip()
    # SEC lookup is practical mainly for plain U.S.-style symbols (no country suffix / dot).
    return bool(t) and '.' not in t


class SECFactsClient:
    def __init__(self) -> None:
        self.s = requests.Session()
        self.s.headers.update({'User-Agent': SEC_USER_AGENT, 'Accept-Encoding': 'gzip, deflate'})

    @lru_cache(maxsize=1)
    def ticker_map(self) -> Dict[str, str]:
        url = 'https://www.sec.gov/files/company_tickers.json'
        r = self.s.get(url, timeout=60)
        r.raise_for_status()
        raw = r.json()
        out: Dict[str, str] = {}
        for _, item in raw.items():
            try:
                t = str(item.get('ticker', '')).upper().strip()
                cik = str(int(item.get('cik_str'))).zfill(10)
                if t:
                    out[t] = cik
            except Exception:
                continue
        return out

    @lru_cache(maxsize=512)
    def cik_for_ticker(self, ticker: str) -> Optional[str]:
        return self.ticker_map().get(str(ticker).upper().strip())

    @lru_cache(maxsize=512)
    def companyfacts(self, cik: str) -> Dict:
        url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
        r = self.s.get(url, timeout=60)
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        return r.json()

    def _unit_matches(self, unit: str, mode: str) -> bool:
        u = str(unit or '').lower()
        if mode == 'eps':
            return ('share' in u) and ('usd' in u)
        if mode == 'shares':
            return u == 'shares'
        if mode == 'money':
            return u.startswith('usd') or u == 'usd'
        return False

    def _annual_by_year(self, ticker: str, taxonomy: str, concepts: Iterable[str], mode: str) -> Dict[int, float]:
        if not _is_us_like_ticker(ticker):
            return {}
        cik = self.cik_for_ticker(ticker)
        if not cik:
            return {}
        facts = self.companyfacts(cik)
        if not facts:
            return {}
        tax = facts.get('facts', {}).get(taxonomy, {})
        best: Dict[int, tuple] = {}
        for concept in concepts:
            node = tax.get(concept, {})
            units = node.get('units', {}) if isinstance(node, dict) else {}
            for unit, arr in units.items():
                if not self._unit_matches(unit, mode):
                    continue
                for item in arr:
                    if str(item.get('form', '')) not in SEC_ALLOWED_FORMS:
                        continue
                    val = item.get('val')
                    if val is None:
                        continue
                    fy = item.get('fy')
                    year = None
                    try:
                        year = int(fy)
                    except Exception:
                        end = str(item.get('end', ''))
                        m = re.match(r'(\d{4})-', end)
                        if m:
                            year = int(m.group(1))
                    if year is None:
                        continue
                    filed = str(item.get('filed', ''))
                    key = (filed, concept)
                    prev = best.get(year)
                    if prev is None or key > prev[:2]:
                        try:
                            best[year] = (filed, concept, float(val))
                        except Exception:
                            pass
        return {y: v[2] for y, v in best.items()}

    def eps_by_year(self, ticker: str, years: Iterable[int]) -> Dict[int, float]:
        concepts = [
            'EarningsPerShareDiluted',
            'DilutedEarningsPerShare',
            'EarningsPerShareBasicAndDiluted',
            'EarningsPerShareBasic',
            'BasicEarningsPerShare',
        ]
        raw = self._annual_by_year(ticker, 'us-gaap', concepts, 'eps')
        return {y: raw.get(y, float('nan')) for y in years}

    def shares_outstanding(self, ticker: str, year: int) -> float:
        concepts = [
            ('dei', ['EntityCommonStockSharesOutstanding']),
            ('us-gaap', ['CommonStockSharesOutstanding', 'CommonStocksIncludingAdditionalPaidInCapitalSharesOutstanding']),
        ]
        best = {}
        for taxonomy, names in concepts:
            raw = self._annual_by_year(ticker, taxonomy, names, 'shares')
            best.update({k: v for k, v in raw.items() if k not in best})
        return best.get(year, float('nan'))

    def money_by_year(self, ticker: str, concepts: Iterable[str]) -> Dict[int, float]:
        return self._annual_by_year(ticker, 'us-gaap', concepts, 'money')


SEC = SECFactsClient()

# Save originals
_orig_eps_by_year = base.eps_by_year
_orig_pick_shares = base.pick_shares
_orig_cash_by_year = base.cash_by_year
_orig_sti_by_year = base.sti_by_year
_orig_long_debt_by_year = base.long_debt_by_year
_orig_current_debt_by_year = base.current_debt_by_year
_orig_cp_by_year = base.cp_by_year
_orig_equity_by_year = base.equity_by_year
_orig_evaluate_ticker = base.evaluate_ticker


def _fill_missing_from_sec(existing: Dict[int, float], fallback: Dict[int, float], label: str) -> Dict[int, float]:
    out = dict(existing)
    filled_years = []
    for y, v in fallback.items():
        try:
            cur = out.get(y, float('nan'))
            cur_nan = pd.isna(cur)
        except Exception:
            cur_nan = True
        if cur_nan and not pd.isna(v):
            out[y] = v
            filled_years.append(str(y))
    if filled_years:
        _ctx_add('auto_fill', f'SEC {label}:{"/".join(filled_years)}')
    return out


def eps_by_year(fin: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    out = _orig_eps_by_year(fin, years)
    if CURRENT_TICKER and _is_us_like_ticker(CURRENT_TICKER):
        sec = SEC.eps_by_year(CURRENT_TICKER, years)
        out = _fill_missing_from_sec(out, sec, 'EPS')
    return out


def pick_shares(tk, bs: pd.DataFrame, price: float) -> float:
    out = _orig_pick_shares(tk, bs, price)
    if (pd.isna(out) or out <= 0) and CURRENT_TICKER and CURRENT_YEAR and _is_us_like_ticker(CURRENT_TICKER):
        sec = SEC.shares_outstanding(CURRENT_TICKER, CURRENT_YEAR)
        if not pd.isna(sec) and sec > 0:
            _ctx_add('auto_fill', f'SEC shares:{CURRENT_YEAR}')
            return sec
    return out


def cash_by_year(bs: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    out = _orig_cash_by_year(bs, years)
    if CURRENT_TICKER and _is_us_like_ticker(CURRENT_TICKER):
        sec = SEC.money_by_year(CURRENT_TICKER, [
            'CashAndCashEquivalentsAtCarryingValue',
            'Cash',
            'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
        ])
        out = _fill_missing_from_sec(out, {y: sec.get(y, float('nan')) for y in years}, 'cash')
    return out


def sti_by_year(bs: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    out = _orig_sti_by_year(bs, years)
    if CURRENT_TICKER and _is_us_like_ticker(CURRENT_TICKER):
        sec = SEC.money_by_year(CURRENT_TICKER, [
            'ShortTermInvestments',
            'AvailableForSaleSecuritiesCurrent',
            'MarketableSecuritiesCurrent',
        ])
        out = _fill_missing_from_sec(out, {y: sec.get(y, float('nan')) for y in years}, 'sti')
    return out


def long_debt_by_year(bs: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    out = _orig_long_debt_by_year(bs, years)
    if CURRENT_TICKER and _is_us_like_ticker(CURRENT_TICKER):
        sec = SEC.money_by_year(CURRENT_TICKER, [
            'LongTermDebtAndCapitalLeaseObligation',
            'LongTermDebtAndCapitalLeaseObligations',
            'LongTermDebtNoncurrent',
            'LongTermDebt',
        ])
        out = _fill_missing_from_sec(out, {y: sec.get(y, float('nan')) for y in years}, 'long_debt')
    return out


def current_debt_by_year(bs: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    out = _orig_current_debt_by_year(bs, years)
    if CURRENT_TICKER and _is_us_like_ticker(CURRENT_TICKER):
        sec = SEC.money_by_year(CURRENT_TICKER, [
            'LongTermDebtCurrent',
            'CurrentPortionOfLongTermDebt',
            'LongTermDebtAndCapitalLeaseObligationCurrent',
            'CurrentDebt',
            'ShortTermBorrowings',
        ])
        out = _fill_missing_from_sec(out, {y: sec.get(y, float('nan')) for y in years}, 'current_debt')
    return out


def cp_by_year(bs: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    out = _orig_cp_by_year(bs, years)
    if CURRENT_TICKER and _is_us_like_ticker(CURRENT_TICKER):
        sec = SEC.money_by_year(CURRENT_TICKER, [
            'CommercialPaper',
            'CommercialPaperCurrent',
            'NotesPayableCurrent',
            'ShortTermBorrowings',
        ])
        out = _fill_missing_from_sec(out, {y: sec.get(y, float('nan')) for y in years}, 'cp')
    return out


def equity_by_year(bs: pd.DataFrame, years: List[int]) -> Dict[int, float]:
    out = _orig_equity_by_year(bs, years)
    if CURRENT_TICKER and _is_us_like_ticker(CURRENT_TICKER):
        sec = SEC.money_by_year(CURRENT_TICKER, [
            'StockholdersEquity',
            'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
            'CommonStockholdersEquity',
            'PartnersCapitalIncludingPortionAttributableToNoncontrollingInterest',
        ])
        out = _fill_missing_from_sec(out, {y: sec.get(y, float('nan')) for y in years}, 'equity')
    return out


def _check_path(ticker: str) -> str:
    if _is_us_like_ticker(ticker):
        return '미국주: SEC companyfacts/10-K annual report 우선 확인'
    return '비미국/ETF: 공식 annual report 또는 IR dividend history 우선 확인'


def evaluate_ticker(ticker: str, bsns_year: int):
    global CURRENT_TICKER, CURRENT_YEAR, CURRENT_CONTEXT
    CURRENT_TICKER = ticker
    CURRENT_YEAR = bsns_year
    CURRENT_CONTEXT = {}
    row, template_df = _orig_evaluate_ticker(ticker, bsns_year)

    # Make remaining unresolved cases actionable.
    unresolved = bool(str(row.get('연간이익증가율빈칸사유', '')).strip() or str(row.get('린치PER판정불가사유', '')).strip())
    row['자동보강출처'] = '; '.join(sorted(CURRENT_CONTEXT.get('auto_fill', set())))
    row['추가확인경로'] = _check_path(ticker) if unresolved else ''
    return row, template_df


# Monkeypatch base module names that its evaluate_ticker resolves at runtime.
base.eps_by_year = eps_by_year
base.pick_shares = pick_shares
base.cash_by_year = cash_by_year
base.sti_by_year = sti_by_year
base.long_debt_by_year = long_debt_by_year
base.current_debt_by_year = current_debt_by_year
base.cp_by_year = cp_by_year
base.equity_by_year = equity_by_year
base.evaluate_ticker = evaluate_ticker


if __name__ == '__main__':
    base.main()
