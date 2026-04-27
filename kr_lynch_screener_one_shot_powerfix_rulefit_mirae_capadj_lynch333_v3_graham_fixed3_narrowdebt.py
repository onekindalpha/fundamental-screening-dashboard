#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Temporary Korean Peter-Lynch-style screener.

Data sources:
- OpenDART (official): corpCode, fnlttSinglAcntAll, stockTotqySttus, alotMatter
- Yahoo Finance (temporary/unofficial): latest close price only

Why this exists:
- pykrx may fail depending on KRX access changes.
- KRX Open API requires a separate AUTH_KEY.
- This script is a practical interim tool for a curated universe.

What it does:
- Uses a built-in universe across semis, batteries, banks, telcos, steel, petrochem.
- Fetches latest prices automatically from Yahoo Finance.
- Pulls annual financials, dividend, and share count from OpenDART.
- Computes the user's custom Peter-Lynch-style metrics.

Install:
    pip install pandas requests yfinance lxml

Run:
    python -u kr_lynch_screener_one_shot.py \
        --dart-key YOUR_DART_KEY \
        --bsns-year 2025 \
        --out kr_lynch_one_shot.csv

Optional:
    --include-watchlist
    --codes 005930,000660,105560
    --sample 10
"""

from __future__ import annotations

import argparse
import io
import math
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests
import yfinance as yf
from xml.etree import ElementTree as ET

DART_BASE = "https://opendart.fss.or.kr/api"
REPORT_CODE = "11011"  # 사업보고서
USER_AGENT = "Mozilla/5.0 (compatible; lynch-screener/1.0)"

# ------------------------------
# Curated universe
# ------------------------------
# market suffix: KS=KOSPI, KQ=KOSDAQ
UNIVERSE: Dict[str, Dict[str, str]] = {
    # Semis / semi equipment / materials
    "005930": {"name": "삼성전자", "suffix": "KS", "group": "반도체"},
    "000660": {"name": "SK하이닉스", "suffix": "KS", "group": "반도체"},
    "042700": {"name": "한미반도체", "suffix": "KS", "group": "반도체소부장"},
    "058470": {"name": "리노공업", "suffix": "KQ", "group": "반도체소부장"},
    "357780": {"name": "솔브레인", "suffix": "KQ", "group": "반도체소부장"},
    "240810": {"name": "원익IPS", "suffix": "KQ", "group": "반도체소부장"},
    "036930": {"name": "주성엔지니어링", "suffix": "KQ", "group": "반도체소부장"},
    "095340": {"name": "ISC", "suffix": "KQ", "group": "반도체소부장"},
    # Batteries
    "373220": {"name": "LG에너지솔루션", "suffix": "KS", "group": "2차전지"},
    "006400": {"name": "삼성SDI", "suffix": "KS", "group": "2차전지"},
    "247540": {"name": "에코프로비엠", "suffix": "KQ", "group": "2차전지"},
    "003670": {"name": "포스코퓨처엠", "suffix": "KS", "group": "2차전지"},
    "066970": {"name": "엘앤에프", "suffix": "KQ", "group": "2차전지"},
    # Banks / finance
    "316140": {"name": "우리금융지주", "suffix": "KS", "group": "금융/은행"},
    "105560": {"name": "KB금융", "suffix": "KS", "group": "금융/은행"},
    "024110": {"name": "IBK기업은행", "suffix": "KS", "group": "금융/은행"},
    # Telco
    "030200": {"name": "KT", "suffix": "KS", "group": "통신"},
    "017670": {"name": "SK텔레콤", "suffix": "KS", "group": "통신"},
    "032640": {"name": "LG유플러스", "suffix": "KS", "group": "통신"},
    # Watchlist: steel / petrochem / cyclicals
    "005490": {"name": "POSCO홀딩스", "suffix": "KS", "group": "철강", "watch": "1"},
    "004020": {"name": "현대제철", "suffix": "KS", "group": "철강", "watch": "1"},
    "001430": {"name": "세아베스틸지주", "suffix": "KS", "group": "철강", "watch": "1"},
    "051910": {"name": "LG화학", "suffix": "KS", "group": "석유화학", "watch": "1"},
    "011170": {"name": "롯데케미칼", "suffix": "KS", "group": "석유화학", "watch": "1"},
    "011780": {"name": "금호석유", "suffix": "KS", "group": "석유화학", "watch": "1"},
    "009830": {"name": "한화솔루션", "suffix": "KS", "group": "석유화학", "watch": "1"},
    "011790": {"name": "SKC", "suffix": "KS", "group": "석유화학", "watch": "1"},
    # User-requested extras
    "017960": {"name": "한국카본", "suffix": "KS", "group": "조선/LNG사이클", "watch": "1"},
    "047050": {"name": "포스코인터내셔널", "suffix": "KS", "group": "에너지/상사", "watch": "1"},
    "010120": {"name": "LS ELECTRIC", "suffix": "KS", "group": "전력설비"},
    "100790": {"name": "미래에셋벤처투자", "suffix": "KQ", "group": "금융/벤처투자", "watch": "1"},
    "006800": {"name": "미래에셋증권", "suffix": "KS", "group": "금융/증권", "watch": "1"},
    "034020": {"name": "두산에너빌리티", "suffix": "KS", "group": "전력/에너지설비", "watch": "1"},
    "298040": {"name": "효성중공업", "suffix": "KS", "group": "전력설비"},
    "267260": {"name": "HD현대일렉트릭", "suffix": "KS", "group": "전력설비"},
    # Defense / Aerospace
    "012450": {"name": "한화에어로스페이스", "suffix": "KS", "group": "방산"},
    "064350": {"name": "현대로템", "suffix": "KS", "group": "방산"},
    "047810": {"name": "한국항공우주", "suffix": "KS", "group": "방산"},
    "079550": {"name": "LIG넥스원", "suffix": "KS", "group": "방산"},
    "272210": {"name": "한화시스템", "suffix": "KS", "group": "방산"},
    "012450": {"name": "한화에어로스페이스", "suffix": "KS", "group": "우주항공/방산"},
    "047810": {"name": "한국항공우주", "suffix": "KS", "group": "우주항공/방산"},
    "272210": {"name": "한화시스템", "suffix": "KS", "group": "우주항공/방산"},
    "079550": {"name": "LIG넥스원", "suffix": "KS", "group": "우주항공/방산"},
    # Nuclear / Utilities
    "015760": {"name": "한국전력", "suffix": "KS", "group": "유틸리티", "watch": "1"},
    "051600": {"name": "한전KPS", "suffix": "KS", "group": "원전/유틸리티"},
    "052690": {"name": "한전기술", "suffix": "KS", "group": "원전/유틸리티"},
    "036460": {"name": "한국가스공사", "suffix": "KS", "group": "유틸리티", "watch": "1"},
    "071320": {"name": "지역난방공사", "suffix": "KS", "group": "유틸리티", "watch": "1"},

    # Materials / Energy (new only)
    "010130": {"name": "고려아연", "suffix": "KS", "group": "소재"},
    "010950": {"name": "S-Oil", "suffix": "KS", "group": "에너지", "watch": "1"},
    "096770": {"name": "SK이노베이션", "suffix": "KS", "group": "에너지", "watch": "1"},
    "010170": {"name": "대한광통신", "suffix": "KQ", "group": "광통신/산업재", "watch": "1"},
    # Consumer Defensive
    "033780": {"name": "KT&G", "suffix": "KS", "group": "필수소비재"},
    "097950": {"name": "CJ제일제당", "suffix": "KS", "group": "필수소비재"},
    "271560": {"name": "오리온", "suffix": "KS", "group": "필수소비재"},
    "004370": {"name": "농심", "suffix": "KS", "group": "필수소비재"},
    "282330": {"name": "BGF리테일", "suffix": "KS", "group": "필수소비재"},

    # Healthcare
    "207940": {"name": "삼성바이오로직스", "suffix": "KS", "group": "헬스케어"},
    "068270": {"name": "셀트리온", "suffix": "KS", "group": "헬스케어"},
    "000100": {"name": "유한양행", "suffix": "KS", "group": "헬스케어"},
    "302440": {"name": "SK바이오사이언스", "suffix": "KS", "group": "헬스케어"},
    "128940": {"name": "한미약품", "suffix": "KS", "group": "헬스케어"},
}

DEFAULT_CODES = [c for c, meta in UNIVERSE.items() if meta.get("watch") != "1"]
WATCH_CODES = [c for c, meta in UNIVERSE.items() if meta.get("watch") == "1"]

BANK_TELCO_GROUPS = {"금융/은행", "금융/증권", "금융/벤처투자", "통신"}
CAPEX_HEAVY_GROUPS = {"철강", "석유화학", "조선/LNG사이클", "에너지/상사"}


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


class DARTError(RuntimeError):
    pass


@dataclass
class MetricRow:
    stock_code: str
    corp_name: str
    group: str
    fit_class: str
    current_price: Optional[float]
    dps: Optional[float]
    eps: Optional[float]
    cash_balance: Optional[float]
    marketable_balance: Optional[float]
    long_debt_balance: Optional[float]
    short_risky_debt: Optional[float]
    equity_balance: Optional[float]
    liability_balance: Optional[float]
    equity_ratio: Optional[float]
    debt_ratio: Optional[float]
    equity_debt_multiple: Optional[float]
    capital_structure_judgement: str
    sector_adjustment_type: str
    sector_adjusted_judgement: str
    net_cash_per_share: Optional[float]
    net_cash_per_share_cons: Optional[float]
    net_cash_adj_per: Optional[float]
    net_cash_adj_per_cons: Optional[float]
    debt_more_than_cash_lynch: str
    debt_more_than_cash_cons: str
    eps_growth_1y: Optional[float]
    eps_growth_3y: Optional[float]
    eps_growth_5y: Optional[float]
    graham_fair_pe_1y: Optional[float]
    graham_fair_pe_3y: Optional[float]
    graham_fair_pe_5y: Optional[float]
    graham_intrinsic_value_1y: Optional[float]
    graham_intrinsic_value_3y: Optional[float]
    graham_intrinsic_value_5y: Optional[float]
    graham_gap_pct_1y: Optional[float]
    graham_gap_pct_3y: Optional[float]
    graham_gap_pct_5y: Optional[float]
    graham_growth_label: str
    graham_fair_pe_selected: Optional[float]
    graham_intrinsic_value_selected: Optional[float]
    graham_gap_pct_selected: Optional[float]
    dividend_yield: Optional[float]
    adj_growth_1y: Optional[float]
    adj_growth_3y: Optional[float]
    adj_growth_5y: Optional[float]
    fcf_per_share: Optional[float]
    fcf_yield: Optional[float]
    adj_score_label: str
    adj_score: Optional[float]
    adj_score_status: str
    lynch_growth_label: str
    lynch_growth_rate: Optional[float]
    per_to_growth_ratio: Optional[float]
    lynch_per_judgement: str
    hard_filter_pass: str
    hard_filter_reason: str
    overall_judgement: str
    overall_judgement_reason: str
    shares_out: Optional[float]
    notes: str


class DARTClient:
    def __init__(self, api_key: str, sleep: float = 0.15):
        self.api_key = api_key
        self.sleep = sleep
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": USER_AGENT})
        self._corp_codes: Optional[pd.DataFrame] = None

    def _get_json(self, path: str, params: Dict[str, str]) -> Dict:
        time.sleep(self.sleep)
        url = f"{DART_BASE}/{path}.json"
        p = {"crtfc_key": self.api_key, **params}
        r = self.s.get(url, params=p, timeout=30)
        r.raise_for_status()
        data = r.json()
        status = str(data.get("status", ""))
        if status not in {"000", "013"}:
            raise DARTError(f"{path}: {status} {data.get('message', '')}")
        return data

    def corp_codes(self) -> pd.DataFrame:
        if self._corp_codes is not None:
            return self._corp_codes.copy()
        time.sleep(self.sleep)
        url = f"{DART_BASE}/corpCode.xml"
        r = self.s.get(url, params={"crtfc_key": self.api_key}, timeout=60)
        r.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        name = zf.namelist()[0]
        raw = zf.read(name)
        root = ET.fromstring(raw)
        rows = []
        for child in root.findall("list"):
            row = {e.tag: (e.text or "").strip() for e in child}
            if row.get("stock_code"):
                rows.append(row)
        df = pd.DataFrame(rows)
        df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
        self._corp_codes = df.copy()
        return df

    def resolve_codes(self, stock_codes: Iterable[str]) -> pd.DataFrame:
        cc = self.corp_codes()
        want = [normalize_code(c) for c in stock_codes]
        out = cc[cc["stock_code"].isin(want)].copy()
        return out[["corp_code", "corp_name", "stock_code"]].drop_duplicates()

    def financials(self, corp_code: str, year: int) -> Tuple[pd.DataFrame, str]:
        # Try consolidated first, then separate.
        for fs_div in ("CFS", "OFS"):
            data = self._get_json(
                "fnlttSinglAcntAll",
                {
                    "corp_code": corp_code,
                    "bsns_year": str(year),
                    "reprt_code": REPORT_CODE,
                    "fs_div": fs_div,
                },
            )
            if str(data.get("status")) == "000" and data.get("list"):
                df = pd.DataFrame(data["list"])
                return df, fs_div
        return pd.DataFrame(), ""

    def dividend(self, corp_code: str, year: int) -> pd.DataFrame:
        data = self._get_json(
            "alotMatter",
            {
                "corp_code": corp_code,
                "bsns_year": str(year),
                "reprt_code": REPORT_CODE,
            },
        )
        return pd.DataFrame(data.get("list", []))

    def stock_total(self, corp_code: str, year: int) -> pd.DataFrame:
        data = self._get_json(
            "stockTotqySttus",
            {
                "corp_code": corp_code,
                "bsns_year": str(year),
                "reprt_code": REPORT_CODE,
            },
        )
        return pd.DataFrame(data.get("list", []))


# ------------------------------
# Helpers
# ------------------------------
def normalize_code(s: str) -> str:
    s = str(s).strip()
    m = re.search(r"(\d{6})", s)
    return m.group(1) if m else s


def parse_number(x) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s == "-" or s.lower() == "nan":
        return None
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    s = s.replace(",", "").replace(" ", "")
    try:
        v = float(s)
        return -v if negative else v
    except Exception:
        return None


def pct_growth(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    if curr is None or prev is None or prev == 0:
        return None
    return (curr / prev - 1.0) * 100.0


def cagr(end: Optional[float], start: Optional[float], years: int) -> Optional[float]:
    if end is None or start is None or years <= 0:
        return None
    if end <= 0 or start <= 0:
        return None
    return ((end / start) ** (1.0 / years) - 1.0) * 100.0


def yahoo_symbol(code: str) -> str:
    meta = UNIVERSE.get(code)
    if not meta:
        raise KeyError(code)
    return f"{code}.{meta['suffix']}"


def fetch_prices(codes: List[str]) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {}
    symbols = {c: yahoo_symbol(c) for c in codes}
    for i, (code, symbol) in enumerate(symbols.items(), 1):
        try:
            hist = yf.Ticker(symbol).history(period="10d", auto_adjust=False)
            price = None
            if hist is not None and not hist.empty:
                s = hist["Close"].dropna()
                if not s.empty:
                    price = float(s.iloc[-1])
            out[code] = price
        except Exception:
            out[code] = None
        if i <= 5 or i % 5 == 0:
            log(f"Price fetch {i}/{len(symbols)}")
        time.sleep(0.05)
    return out


def choose_fit_class(group: str) -> str:
    if group in BANK_TELCO_GROUPS:
        return "보정필요"
    if group in CAPEX_HEAVY_GROUPS:
        return "watchlist"
    return "메인"


# ------------------------------
# Financial extraction rules
# ------------------------------
# Lynch-style interpretation used here:
# - 기본형: 현금및현금성자산 + 유가증권성 단기자산 - 장기부채
# - 보수형: 기본형 - 단기차입금/상업어음/유동성장기부채 등
# Important:
# - BS(재무상태표) 잔액만 사용
# - CF(취득/처분/증감/상환/차입) 및 평가손익 항목은 제외
CASH_PATTERNS = [
    "현금및현금성자산", "현금 및 현금성자산",
]

MARKETABLE_PATTERNS = [
    "단기금융상품",
    "단기투자자산",
    "금융기관예치금",
    "유동성당기손익-공정가치측정금융자산",
    "당기손익-공정가치측정금융자산",
    "당기손익공정가치측정금융자산",
    "유동성상각후원가측정금융자산",
    "상각후원가측정금융자산",
]

MARKETABLE_FALLBACK_PATTERNS = [
    "유동금융자산", "유동기타금융자산", "기타유동금융자산",
]

LONG_DEBT_PATTERNS = [
    "장기차입금", "비유동차입금", "사채", "장기사채",
    "비유동리스부채", "장기리스부채", "비유동금융부채",
]

CURRENT_DEBT_PATTERNS = [
    # 책 취지에 더 가깝게 축소: 은행성 단기차입 + 기업어음/상업어음 계열만 반영
    "단기차입금", "유동차입금",
    "기업어음", "상업어음", "전자단기사채",
]

COMMON_EXCLUDE_PATTERNS = [
    "취득", "처분", "증감", "증가", "감소",
    "의차입", "차입의", "의상환", "상환의",
    "평가", "환율", "손상", "손실", "이익", "기초", "기말",
]

MARKETABLE_EXCLUDE_PATTERNS = COMMON_EXCLUDE_PATTERNS + [
    "장기", "비유동", "사용제한", "담보", "질권", "보증", "파생",
]

LONG_DEBT_EXCLUDE_PATTERNS = COMMON_EXCLUDE_PATTERNS + [
    "유동성", "단기", "현재",
]

CURRENT_DEBT_EXCLUDE_PATTERNS = COMMON_EXCLUDE_PATTERNS + [
    "매입", "영업", "충당", "리스총부채",
]

EQUITY_PATTERNS = [
    "자본총계", "지배기업의소유주지분", "지배회사소유주지분", "지배주주지분",
]
EQUITY_EXCLUDE_PATTERNS = [
    "자본금", "자본잉여금", "기타자본", "비지배", "비지배지분", "자본수익",
]
LIABILITY_TOTAL_PATTERNS = [
    "부채총계", "총부채",
]
LIABILITY_TOTAL_EXCLUDE_PATTERNS = [
    "유동부채", "비유동부채", "리스총부채",
]

CFO_PATTERNS = [
    "영업활동현금흐름", "영업활동으로인한현금흐름",
]
PPE_CAPEX_PATTERNS = [
    "유형자산의 취득", "유형자산취득", "유형자산 취득",
]
INTANGIBLE_CAPEX_PATTERNS = [
    "무형자산의 취득", "무형자산취득", "무형자산 취득",
]
EPS_PATTERNS = [
    "기본 및 희석주당이익", "기본주당이익", "보통주기본주당이익", "주당순이익", "주당이익",
]
DPS_PATTERNS = [
    "주당 현금배당금", "주당배당금", "보통주 주당 현금배당금", "보통주 현금배당금",
]
DPS_EXCLUDE_PATTERNS = [
    "총액", "총 배당", "배당총액", "현금배당총액", "총배당금", "총배당",
]


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _contains_any(text: str, pats: Iterable[str]) -> bool:
    t = _norm_text(text)
    return any(_norm_text(p) in t for p in pats)


def _row_amount(r) -> Optional[float]:
    for col in ("thstrm_amount", "frmtrm_amount"):
        n = parse_number(r.get(col))
        if n is not None:
            return n
    return None


def _pick_rows(
    df: pd.DataFrame,
    pats: Iterable[str],
    *,
    sj_div: Optional[str] = None,
    exclude_pats: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    work = df.copy()
    if sj_div and "sj_div" in work.columns:
        work = work[work["sj_div"].astype(str) == sj_div].copy()

    names = work["account_nm"].astype(str)
    mask = names.map(lambda x: _contains_any(x, pats))
    if exclude_pats:
        mask = mask & ~names.map(lambda x: _contains_any(x, exclude_pats))

    work = work[mask].copy()
    if work.empty:
        return work

    dedupe_cols = [c for c in ("sj_div", "account_nm", "thstrm_amount", "frmtrm_amount") if c in work.columns]
    if dedupe_cols:
        work = work.drop_duplicates(subset=dedupe_cols, keep="first")
    return work


def _sum_amount(
    df: pd.DataFrame,
    pats: Iterable[str],
    *,
    sj_div: Optional[str] = None,
    exclude_pats: Optional[Iterable[str]] = None,
) -> Optional[float]:
    rows = _pick_rows(df, pats, sj_div=sj_div, exclude_pats=exclude_pats)
    if rows.empty:
        return None
    vals = []
    for _, r in rows.iterrows():
        n = _row_amount(r)
        if n is not None:
            vals.append(n)
    return sum(vals) if vals else None


def _first_amount(
    df: pd.DataFrame,
    pats: Iterable[str],
    *,
    sj_div: Optional[str] = None,
    exclude_pats: Optional[Iterable[str]] = None,
) -> Optional[float]:
    rows = _pick_rows(df, pats, sj_div=sj_div, exclude_pats=exclude_pats)
    if rows.empty:
        return None
    rows = rows.assign(_len=rows["account_nm"].astype(str).str.len()).sort_values("_len")
    for _, r in rows.iterrows():
        n = _row_amount(r)
        if n is not None:
            return n
    return None


def extract_snapshot(fin_df: pd.DataFrame) -> Dict[str, Optional[float]]:
    if fin_df is None or fin_df.empty:
        return {
            "cash": None,
            "marketable": None,
            "long_debt": None,
            "short_risky_debt": None,
            "equity": None,
            "liability_total": None,
            "cfo": None,
            "capex": None,
            "eps": None,
        }

    cfo = _first_amount(fin_df, CFO_PATTERNS, sj_div="CF")
    ppe_capex = _sum_amount(fin_df, PPE_CAPEX_PATTERNS, sj_div="CF")
    int_capex = _sum_amount(fin_df, INTANGIBLE_CAPEX_PATTERNS, sj_div="CF")
    capex = None
    if ppe_capex is not None or int_capex is not None:
        capex = abs(ppe_capex or 0.0) + abs(int_capex or 0.0)

    cash = _first_amount(fin_df, CASH_PATTERNS, sj_div="BS")
    marketable_specific = _sum_amount(
        fin_df,
        MARKETABLE_PATTERNS,
        sj_div="BS",
        exclude_pats=MARKETABLE_EXCLUDE_PATTERNS,
    )
    marketable_fallback = _sum_amount(
        fin_df,
        MARKETABLE_FALLBACK_PATTERNS,
        sj_div="BS",
        exclude_pats=MARKETABLE_EXCLUDE_PATTERNS,
    )
    marketable = marketable_specific if marketable_specific is not None else marketable_fallback
    long_debt = _sum_amount(
        fin_df,
        LONG_DEBT_PATTERNS,
        sj_div="BS",
        exclude_pats=LONG_DEBT_EXCLUDE_PATTERNS,
    )
    short_risky_debt = _sum_amount(
        fin_df,
        CURRENT_DEBT_PATTERNS,
        sj_div="BS",
        exclude_pats=CURRENT_DEBT_EXCLUDE_PATTERNS,
    )
    eps = _first_amount(fin_df, EPS_PATTERNS)

    return {
        "cash": cash,
        "marketable": marketable,
        "long_debt": long_debt,
        "short_risky_debt": short_risky_debt,
        "cfo": cfo,
        "capex": capex,
        "eps": eps,
    }



def extract_dps(div_df: pd.DataFrame) -> Optional[float]:
    if div_df is None or div_df.empty:
        return None
    work = div_df.copy()
    if "stock_knd" in work.columns:
        pref = work[work["stock_knd"].astype(str).str.contains("보통", na=False)]
        if not pref.empty:
            work = pref
    if "se" not in work.columns:
        return None

    se_norm = work["se"].astype(str).map(lambda x: re.sub(r"\s+", "", x))
    # Priority 1: explicit per-share cash dividend rows only.
    rows = work[
        se_norm.str.contains("주당", na=False)
        & se_norm.str.contains("배당", na=False)
        & ~se_norm.map(lambda x: _contains_any(x, DPS_EXCLUDE_PATTERNS))
    ].copy()
    # Priority 2: heuristic fallback but still exclude total-amount rows.
    if rows.empty:
        rows = work[
            work["se"].astype(str).map(lambda x: _contains_any(x, DPS_PATTERNS))
            & ~work["se"].astype(str).map(lambda x: _contains_any(x, DPS_EXCLUDE_PATTERNS))
        ].copy()
    if rows.empty:
        return None

    # Prefer rows whose label is closest to "주당 현금배당금".
    rows = rows.assign(
        _score=rows["se"].astype(str).map(
            lambda x: 0
            if "주당 현금배당금" in re.sub(r"\s+", "", x)
            else (1 if "주당" in re.sub(r"\s+", "", x) else 2)
        )
    ).sort_values(["_score"])

    for col in ("thstrm", "frmtrm", "lwfr"):
        if col in rows.columns:
            for v in rows[col].tolist():
                n = parse_number(v)
                # Guardrail: absurd per-share dividend almost certainly means total dividend amount.
                if n is not None and 0 <= n <= 100000:
                    return n
    return None



def extract_shares(stock_df: pd.DataFrame) -> Optional[float]:
    if stock_df is None or stock_df.empty:
        return None
    work = stock_df.copy()
    if "se" in work.columns:
        pref = work[work["se"].astype(str).str.contains("보통주|합계", regex=True, na=False)].copy()
        if not pref.empty:
            work = pref
    # Prefer 보통주, then 합계.
    if "se" in work.columns:
        common = work[work["se"].astype(str).str.contains("보통주", na=False)]
        if not common.empty:
            work = common
        else:
            total = work[work["se"].astype(str).str.contains("합계", na=False)]
            if not total.empty:
                work = total
    for col in ("istc_totqy", "distb_stock_co", "now_to_isu_stock_totqy"):
        if col in work.columns:
            vals = work[col].map(parse_number).dropna()
            if not vals.empty:
                return float(vals.iloc[0])
    return None



def choose_adj_score_for_screen(adj3: Optional[float], adj5: Optional[float], adj1: Optional[float]) -> Tuple[str, Optional[float]]:
    for label, value in (("3년", adj3), ("5년", adj5), ("1년", adj1)):
        if value is not None and not (isinstance(value, float) and math.isnan(value)):
            return label, value
    return "판정불가", None


def adj_score_status_label(adj_score: Optional[float]) -> str:
    if adj_score is None or (isinstance(adj_score, float) and math.isnan(adj_score)):
        return "판정불가"
    if adj_score < 1.0:
        return "불리(<1)"
    if adj_score >= 2.0:
        return "안심(>=2)"
    if adj_score >= 1.5:
        return "양호(>=1.5)"
    return "보통(1~1.5)"


def choose_lynch_growth_for_screen(eps3: Optional[float], eps5: Optional[float], eps1: Optional[float]) -> Tuple[str, Optional[float]]:
    for label, value in (("3년", eps3), ("5년", eps5), ("1년", eps1)):
        if value is not None and not (isinstance(value, float) and math.isnan(value)):
            return label, value
    return "판정불가", None


def graham_fair_pe(growth_pct: Optional[float]) -> Optional[float]:
    if growth_pct is None:
        return None
    if isinstance(growth_pct, float) and math.isnan(growth_pct):
        return None
    pe = 8.5 + 2.0 * growth_pct
    return pe if pe > 0 else None


def graham_intrinsic_value(eps_now: Optional[float], growth_pct: Optional[float]) -> Optional[float]:
    pe = graham_fair_pe(growth_pct)
    if eps_now is None or pe is None:
        return None
    if any(isinstance(v, float) and math.isnan(v) for v in (eps_now, pe)):
        return None
    return eps_now * pe if eps_now > 0 else None


def graham_gap_pct(price: Optional[float], intrinsic_value: Optional[float]) -> Optional[float]:
    if price is None or intrinsic_value is None:
        return None
    if any(isinstance(v, float) and math.isnan(v) for v in (price, intrinsic_value)):
        return None
    if price <= 0:
        return None
    return (intrinsic_value / price - 1.0) * 100.0


def choose_graham_for_screen(
    eps_now: Optional[float],
    price: Optional[float],
    g3: Optional[float],
    g5: Optional[float],
    g1: Optional[float],
) -> Tuple[str, Optional[float], Optional[float], Optional[float]]:
    label, growth_used = choose_lynch_growth_for_screen(g3, g5, g1)
    pe = graham_fair_pe(growth_used)
    value = graham_intrinsic_value(eps_now, growth_used)
    gap = graham_gap_pct(price, value)
    return label, pe, value, gap


def per_vs_growth_judgement(ncper: Optional[float], annual_growth_rate: Optional[float]) -> Tuple[Optional[float], str]:
    if ncper is None or annual_growth_rate is None:
        return None, "판정불가"
    if any(isinstance(v, float) and math.isnan(v) for v in (ncper, annual_growth_rate)):
        return None, "판정불가"
    if ncper <= 0 or annual_growth_rate <= 0:
        return None, "판정불가"
    ratio = ncper / annual_growth_rate
    if ratio <= 0.5:
        return ratio, "매우 유망"
    if ratio < 1.0:
        return ratio, "헐값"
    if ratio < 2.0:
        return ratio, "보통"
    return ratio, "매우 불리"


def overall_judgement_label(hard_pass: bool, adj_score: Optional[float], per_growth_ratio: Optional[float]) -> str:
    if not hard_pass:
        return "제외"
    if adj_score is None or per_growth_ratio is None:
        return "보류"
    if any(isinstance(v, float) and math.isnan(v) for v in (adj_score, per_growth_ratio)):
        return "보류"
    if adj_score >= 2.0 and per_growth_ratio <= 0.5:
        return "매우 유망"
    if adj_score >= 1.5 and per_growth_ratio < 1.0:
        return "양호"
    if adj_score < 1.0 or per_growth_ratio >= 2.0:
        return "제외"
    return "보류"


def hard_filter_reason_label(
    net_cash_ps: Optional[float],
    fcf_ps: Optional[float],
    ncper: Optional[float],
) -> str:
    failed = []
    def _bad(v: Optional[float]) -> bool:
        return v is None or (isinstance(v, float) and math.isnan(v)) or v <= 0
    if _bad(net_cash_ps):
        failed.append("주당순현금<=0")
    if _bad(fcf_ps):
        failed.append("주당FCF<=0")
    if _bad(ncper):
        failed.append("순현금차감PER<=0")
    return "통과" if not failed else " / ".join(failed)


def overall_judgement_reason_label(
    hard_pass: bool,
    adj_score: Optional[float],
    per_growth_ratio: Optional[float],
) -> str:
    if not hard_pass:
        return "하드필터 미통과"
    if adj_score is None or per_growth_ratio is None:
        return "배당감안점수 또는 린치PER배수 미산출"
    if any(isinstance(v, float) and math.isnan(v) for v in (adj_score, per_growth_ratio)):
        return "배당감안점수 또는 린치PER배수 미산출"
    if adj_score >= 2.0 and per_growth_ratio <= 0.5:
        return "배당감안점수>=2 & 린치PER배수<=0.5"
    if adj_score >= 1.5 and per_growth_ratio < 1.0:
        return "배당감안점수>=1.5 & 린치PER배수<1"
    if adj_score < 1.0:
        return "배당감안점수<1"
    if per_growth_ratio >= 2.0:
        return "린치PER배수>=2"
    return "중간구간(보류)"


def capital_structure_metrics(equity: Optional[float], liability_total: Optional[float]) -> Tuple[Optional[float], Optional[float], Optional[float], str]:
    if equity is None or liability_total is None:
        return None, None, None, "판정불가"
    if any(isinstance(v, float) and math.isnan(v) for v in (equity, liability_total)):
        return None, None, None, "판정불가"
    total = equity + liability_total
    if total <= 0:
        return None, None, None, "판정불가"
    eq_ratio = equity / total
    debt_ratio = liability_total / total
    multiple = None if liability_total <= 0 else equity / liability_total
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
    return eq_ratio, debt_ratio, multiple, label


def sector_adjustment_type_label(group: str) -> str:
    if "금융" in str(group):
        return "금융보정"
    if str(group) == "통신":
        return "통신보정"
    return "일반"


def sector_adjusted_judgement_label(
    group: str,
    growth_used: Optional[float],
    ncper: Optional[float],
    fcf_ps: Optional[float],
    div_yield: Optional[float],
    net_cash_ps: Optional[float],
    cap_judgement: str,
) -> str:
    g = str(group)
    if "금융" in g:
        if growth_used is None or ncper is None or (isinstance(growth_used, float) and math.isnan(growth_used)) or (isinstance(ncper, float) and math.isnan(ncper)):
            return "보정판정불가"
        if growth_used >= 2.0 and ncper > 0 and ncper <= 15:
            return "보정양호"
        if growth_used >= 1.5 and ncper > 0:
            return "보정보류"
        return "보정주의"
    if g == "통신":
        if fcf_ps is None or ncper is None or growth_used is None:
            return "보정판정불가"
        vals = [fcf_ps, ncper, growth_used]
        if any(isinstance(v, float) and math.isnan(v) for v in vals):
            return "보정판정불가"
        if fcf_ps > 0 and ncper > 0 and growth_used >= 1.5 and (div_yield or 0.0) >= 3.0:
            return "보정양호"
        if fcf_ps > 0 and ncper > 0 and growth_used >= 1.0:
            return "보정보류"
        return "보정주의"
    return "일반"


def build_row(
    code: str,
    corp_name: str,
    group: str,
    price: Optional[float],
    shares: Optional[float],
    dps: Optional[float],
    snaps: Dict[int, Dict[str, Optional[float]]],
    base_year: int,
) -> MetricRow:
    fit_class = choose_fit_class(group)
    notes: List[str] = []

    y0 = base_year
    y1 = base_year - 1
    y3 = base_year - 3
    y5 = base_year - 5

    s0 = snaps.get(y0, {})
    s1 = snaps.get(y1, {})
    s3 = snaps.get(y3, {})
    s5 = snaps.get(y5, {})

    eps0 = s0.get("eps")
    eps1_prev = s1.get("eps")
    eps3_prev = s3.get("eps")
    eps5_prev = s5.get("eps")

    eps1 = pct_growth(eps0, eps1_prev)
    eps3 = cagr(eps0, eps3_prev, 3)
    eps5 = cagr(eps0, eps5_prev, 5)

    cash_balance = s0.get("cash")
    marketable_balance = s0.get("marketable")
    long_debt_balance = s0.get("long_debt")
    short_risky_debt = s0.get("short_risky_debt")
    equity_balance = s0.get("equity")
    liability_balance = s0.get("liability_total")
    equity_ratio, debt_ratio, equity_debt_multiple, capital_structure_judgement = capital_structure_metrics(equity_balance, liability_balance)

    net_cash_ps = None
    net_cash_ps_cons = None
    ncper = None
    ncper_cons = None
    debt_more_than_cash_lynch = "판정불가"
    debt_more_than_cash_cons = "판정불가"
    fcf_ps = None
    fcf_yield = None
    div_yield = None

    if shares and shares > 0:
        cash_like = (cash_balance or 0.0) + (marketable_balance or 0.0)
        long_debt = long_debt_balance or 0.0
        short_risky = short_risky_debt or 0.0

        net_cash_ps = (cash_like - long_debt) / shares
        net_cash_ps_cons = (cash_like - long_debt - short_risky) / shares

        debt_more_than_cash_lynch = "Y" if (cash_like < long_debt) else "N"
        debt_more_than_cash_cons = "Y" if (cash_like < (long_debt + short_risky)) else "N"

        cfo = s0.get("cfo")
        capex = s0.get("capex")
        if cfo is not None and capex is not None:
            fcf_ps = (cfo - capex) / shares

    if price is not None and price > 0 and dps is not None:
        div_yield = dps / price * 100.0

    if price is not None and eps0 is not None and eps0 > 0 and net_cash_ps is not None:
        ncper = (price - net_cash_ps) / eps0
    if price is not None and eps0 is not None and eps0 > 0 and net_cash_ps_cons is not None:
        ncper_cons = (price - net_cash_ps_cons) / eps0

    if price is not None and price > 0 and fcf_ps is not None:
        fcf_yield = fcf_ps / price * 100.0

    def _adj(g: Optional[float]) -> Optional[float]:
        if g is None or ncper is None or ncper == 0:
            return None
        return (g + (div_yield or 0.0)) / ncper

    adj1 = _adj(eps1)
    adj3 = _adj(eps3)
    adj5 = _adj(eps5)

    graham_pe_1y = graham_fair_pe(eps1)
    graham_pe_3y = graham_fair_pe(eps3)
    graham_pe_5y = graham_fair_pe(eps5)

    graham_val_1y = graham_intrinsic_value(eps0, eps1)
    graham_val_3y = graham_intrinsic_value(eps0, eps3)
    graham_val_5y = graham_intrinsic_value(eps0, eps5)

    graham_gap_1y = graham_gap_pct(price, graham_val_1y)
    graham_gap_3y = graham_gap_pct(price, graham_val_3y)
    graham_gap_5y = graham_gap_pct(price, graham_val_5y)

    graham_growth_label, graham_pe_selected, graham_val_selected, graham_gap_selected = choose_graham_for_screen(
        eps_now=eps0,
        price=price,
        g3=eps3,
        g5=eps5,
        g1=eps1,
    )

    adj_score_label, adj_score = choose_adj_score_for_screen(adj3, adj5, adj1)
    adj_score_status = adj_score_status_label(adj_score)
    lynch_growth_label, lynch_growth_rate = choose_lynch_growth_for_screen(eps3, eps5, eps1)
    per_growth_ratio, lynch_per_judgement = per_vs_growth_judgement(ncper, lynch_growth_rate)
    hard_filter_ok = bool((net_cash_ps is not None) and (not isinstance(net_cash_ps, float) or not math.isnan(net_cash_ps)) and net_cash_ps > 0 and (fcf_ps is not None) and (not isinstance(fcf_ps, float) or not math.isnan(fcf_ps)) and fcf_ps > 0 and (ncper is not None) and (not isinstance(ncper, float) or not math.isnan(ncper)) and ncper > 0)
    hard_filter_reason = hard_filter_reason_label(net_cash_ps, fcf_ps, ncper)
    overall_judgement = overall_judgement_label(hard_filter_ok, adj_score, per_growth_ratio)
    overall_judgement_reason = overall_judgement_reason_label(hard_filter_ok, adj_score, per_growth_ratio)
    sector_adjustment_type = sector_adjustment_type_label(group)
    sector_adjusted_judgement = sector_adjusted_judgement_label(group, lynch_growth_rate, ncper, fcf_ps, div_yield, net_cash_ps, capital_structure_judgement)

    if fit_class != "메인":
        notes.append("린치식 단독판정 비중 낮춤")
    if net_cash_ps is not None and net_cash_ps < 0:
        notes.append("주당순현금 음수(린치식)")
    if net_cash_ps_cons is not None and net_cash_ps_cons < 0:
        notes.append("주당순현금 음수(보수형)")
    if short_risky_debt is not None and short_risky_debt > 0:
        notes.append("단기위험부채 존재")
    if fcf_ps is not None and fcf_ps < 0:
        notes.append("주당FCF 음수")
    if adj1 is not None and adj3 is not None and adj1 > adj3 * 3:
        notes.append("1년 점수 과열 가능")
    if price is None:
        notes.append("현재가 미수집")
    if eps0 is None:
        notes.append("EPS 미추출")
    if adj_score_status == "불리(<1)":
        notes.append("배당감안점수<1")
    if lynch_per_judgement.startswith("매우 불리"):
        notes.append("PER>연성장률의 2배")
    if capital_structure_judgement == "부채우위":
        notes.append("주주지분<부채")

    return MetricRow(
        stock_code=code,
        corp_name=corp_name,
        group=group,
        fit_class=fit_class,
        current_price=price,
        dps=dps,
        eps=eps0,
        cash_balance=cash_balance,
        marketable_balance=marketable_balance,
        long_debt_balance=long_debt_balance,
        short_risky_debt=short_risky_debt,
        equity_balance=equity_balance,
        liability_balance=liability_balance,
        equity_ratio=equity_ratio,
        debt_ratio=debt_ratio,
        equity_debt_multiple=equity_debt_multiple,
        capital_structure_judgement=capital_structure_judgement,
        sector_adjustment_type=sector_adjustment_type,
        sector_adjusted_judgement=sector_adjusted_judgement,
        net_cash_per_share=net_cash_ps,
        net_cash_per_share_cons=net_cash_ps_cons,
        net_cash_adj_per=ncper,
        net_cash_adj_per_cons=ncper_cons,
        debt_more_than_cash_lynch=debt_more_than_cash_lynch,
        debt_more_than_cash_cons=debt_more_than_cash_cons,
        eps_growth_1y=eps1,
        eps_growth_3y=eps3,
        eps_growth_5y=eps5,
        graham_fair_pe_1y=graham_pe_1y,
        graham_fair_pe_3y=graham_pe_3y,
        graham_fair_pe_5y=graham_pe_5y,
        graham_intrinsic_value_1y=graham_val_1y,
        graham_intrinsic_value_3y=graham_val_3y,
        graham_intrinsic_value_5y=graham_val_5y,
        graham_gap_pct_1y=graham_gap_1y,
        graham_gap_pct_3y=graham_gap_3y,
        graham_gap_pct_5y=graham_gap_5y,
        graham_growth_label=graham_growth_label,
        graham_fair_pe_selected=graham_pe_selected,
        graham_intrinsic_value_selected=graham_val_selected,
        graham_gap_pct_selected=graham_gap_selected,
        dividend_yield=div_yield,
        adj_growth_1y=adj1,
        adj_growth_3y=adj3,
        adj_growth_5y=adj5,
        fcf_per_share=fcf_ps,
        fcf_yield=fcf_yield,
        adj_score_label=adj_score_label,
        adj_score=adj_score,
        adj_score_status=adj_score_status,
        lynch_growth_label=lynch_growth_label,
        lynch_growth_rate=lynch_growth_rate,
        per_to_growth_ratio=per_growth_ratio,
        lynch_per_judgement=lynch_per_judgement,
        hard_filter_pass="Y" if hard_filter_ok else "N",
        hard_filter_reason=hard_filter_reason,
        overall_judgement=overall_judgement,
        overall_judgement_reason=overall_judgement_reason,
        shares_out=shares,
        notes="; ".join(notes),
    )



def to_frame(rows: List[MetricRow]) -> pd.DataFrame:
    df = pd.DataFrame([r.__dict__ for r in rows])
    if df.empty:
        return df
    
    rename = {
        "stock_code": "종목코드",
        "corp_name": "종목명",
        "group": "그룹",
        "fit_class": "판정구분",
        "current_price": "현재가",
        "dps": "현금배당금(FY2025 DPS)",
        "eps": "EPS(FY2025)",
        "cash_balance": "현금및현금성자산",
        "marketable_balance": "유가증권성자산",
        "long_debt_balance": "장기부채",
        "short_risky_debt": "단기위험부채",
        "equity_balance": "주주지분",
        "liability_balance": "총부채",
        "equity_ratio": "주주지분비중",
        "debt_ratio": "부채비중",
        "equity_debt_multiple": "주주대부채배수",
        "capital_structure_judgement": "주주대부채판정",
        "sector_adjustment_type": "업종보정유형",
        "sector_adjusted_judgement": "업종보정판정",
        "net_cash_per_share": "주당순현금(린치식)",
        "net_cash_per_share_cons": "주당순현금(보수형)",
        "net_cash_adj_per": "순현금차감PER(린치식)",
        "net_cash_adj_per_cons": "순현금차감PER(보수형)",
        "debt_more_than_cash_lynch": "현금보다부채많음(린치형)",
        "debt_more_than_cash_cons": "현금보다부채많음(보수형)",
        "eps_growth_1y": "연간이익증가율(1년,%)",
        "eps_growth_3y": "연간이익증가율(3년CAGR,%)",
        "eps_growth_5y": "연간이익증가율(5년CAGR,%)",
        "graham_fair_pe_1y": "그레이엄적정PER(1년)",
        "graham_fair_pe_3y": "그레이엄적정PER(3년)",
        "graham_fair_pe_5y": "그레이엄적정PER(5년)",
        "graham_intrinsic_value_1y": "그레이엄내재가치(1년)",
        "graham_intrinsic_value_3y": "그레이엄내재가치(3년)",
        "graham_intrinsic_value_5y": "그레이엄내재가치(5년)",
        "graham_gap_pct_1y": "그레이엄괴리율(1년,%)",
        "graham_gap_pct_3y": "그레이엄괴리율(3년,%)",
        "graham_gap_pct_5y": "그레이엄괴리율(5년,%)",
        "graham_growth_label": "그레이엄사용기준",
        "graham_fair_pe_selected": "그레이엄적정PER(선택)",
        "graham_intrinsic_value_selected": "그레이엄내재가치(선택)",
        "graham_gap_pct_selected": "그레이엄괴리율(선택,%)",
        "dividend_yield": "배당수익률(%)",
        "adj_growth_1y": "배당감안이익성장률(1년)",
        "adj_growth_3y": "배당감안이익성장률(3년)",
        "adj_growth_5y": "배당감안이익성장률(5년)",
        "fcf_per_share": "주당잉여현금흐름",
        "fcf_yield": "잉여현금흐름수익률(%)",
        "adj_score_label": "배당감안점수기준",
        "adj_score": "배당감안점수",
        "adj_score_status": "배당감안점수판정",
        "lynch_growth_label": "사용연성장률기준",
        "lynch_growth_rate": "사용연성장률(%)",
        "per_to_growth_ratio": "린치PER배수",
        "lynch_per_judgement": "린치PER판정",
        "hard_filter_pass": "하드필터통과",
        "hard_filter_reason": "하드필터사유",
        "overall_judgement": "종합판정",
        "overall_judgement_reason": "종합판정사유",
        "shares_out": "발행주식수",
        "notes": "비고",
    }
    df = df.rename(columns=rename)
    if "종목코드" in df.columns:
        df["종목코드"] = df["종목코드"].astype(str).str.replace(r"\D", "", regex=True).str.zfill(6).map(lambda x: f'="{x}"')
    return df



def apply_filters(
    df: pd.DataFrame,
    min1: float,
    min3: float,
    min5: float,
    max_ncper: Optional[float],
) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()

    hard = out["하드필터통과"].astype(str).eq("Y")
    growth_used = pd.to_numeric(out["사용연성장률(%)"], errors="coerce")
    per_growth_ratio = pd.to_numeric(out["린치PER배수"], errors="coerce")
    ncper = pd.to_numeric(out["순현금차감PER(린치식)"], errors="coerce")

    keep = (
        hard
        & (growth_used >= min3)
        & (per_growth_ratio <= 1.0)
        & (ncper > 0)
    )
    if max_ncper is not None:
        keep = keep & (ncper <= max_ncper)

    out = out[keep].copy()
    if out.empty:
        return out

    out = out.sort_values(
        by=[
            "종합판정",
            "사용연성장률(%)",
            "린치PER배수",
            "순현금차감PER(린치식)",
            "주당순현금(린치식)",
            "주당잉여현금흐름",
        ],
        ascending=[True, False, True, True, False, False],
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dart-key", required=True, help="OpenDART API key")
    ap.add_argument("--bsns-year", type=int, default=2025, help="Base fiscal year, currently expected 2025")
    ap.add_argument("--out", default="kr_lynch_one_shot.csv")
    ap.add_argument("--sleep", type=float, default=0.15, help="Delay between DART requests")
    ap.add_argument("--sample", type=int, default=None)
    ap.add_argument("--include-watchlist", action="store_true")
    ap.add_argument("--codes", default=None, help="Comma/space separated 6-digit stock codes (replace built-in universe)")
    ap.add_argument("--add-codes", default=None, help="Comma/space separated 6-digit stock codes to ADD to built-in universe")
    ap.add_argument("--tsv", action="store_true", help="Write TSV instead of CSV")
    ap.add_argument("--allow-unofficial-price", action="store_true", help="Accepted for CLI compatibility; ignored because this script already uses Yahoo price")
    ap.add_argument("--min1", type=float, default=1.0)
    ap.add_argument("--min3", type=float, default=1.5)
    ap.add_argument("--min5", type=float, default=1.5)
    ap.add_argument("--max-ncper", type=float, default=None)
    args = ap.parse_args()

    if args.bsns_year != 2025:
        log("Note: this script expects 2025 as the base year for 1Y/3Y/5Y calculations.")

    def _parse_code_list(s: Optional[str]) -> List[str]:
        parsed: List[str] = []
        if not s:
            return parsed
        for part in re.split(r"[\s,]+", s.strip()):
            if not part:
                continue
            c = normalize_code(part)
            if re.fullmatch(r"\d{6}", c):
                parsed.append(c)
                if c not in UNIVERSE:
                    UNIVERSE[c] = {"name": "", "suffix": "KS", "group": "직접추가"}
                    log(f"Added ad-hoc code not in built-in universe: {c} (default suffix=KS, group=직접추가)")
            else:
                log(f"Skipping invalid code: {part}")
        return list(dict.fromkeys(parsed))

    selected: List[str]
    if args.codes:
        # Backward compatible: --codes replaces the built-in universe.
        selected = _parse_code_list(args.codes)
    else:
        selected = DEFAULT_CODES + (WATCH_CODES if args.include_watchlist else [])
        if args.add_codes:
            selected = list(dict.fromkeys(selected + _parse_code_list(args.add_codes)))

    if args.sample:
        selected = selected[: args.sample]

    log(f"Universe size: {len(selected)}")
    if not selected:
        raise SystemExit("No stock codes selected.")

    client = DARTClient(args.dart_key, sleep=args.sleep)
    resolved = client.resolve_codes(selected)
    if resolved.empty:
        raise SystemExit("Could not resolve any corp codes from OpenDART. Check DART key.")

    # keep selected order
    resolved = resolved.set_index("stock_code").reindex(selected).reset_index()
    missing = resolved[resolved["corp_code"].isna()]["stock_code"].tolist()
    if missing:
        log(f"Missing corp-code resolution: {', '.join(missing)}")
    resolved = resolved[resolved["corp_code"].notna()].copy()

    log("Fetching latest prices from Yahoo Finance")
    prices = fetch_prices(resolved["stock_code"].tolist())

    years = [args.bsns_year, args.bsns_year - 1, args.bsns_year - 3, args.bsns_year - 5]
    rows: List[MetricRow] = []

    for i, r in resolved.iterrows():
        code = str(r["stock_code"]).zfill(6)
        corp_code = str(r["corp_code"]).zfill(8)
        universe_name = str(UNIVERSE.get(code, {}).get("name") or "").strip()
        dart_name = str(r.get("corp_name", "") or "").strip()
        if (not universe_name) or universe_name == code or universe_name.isdigit():
            corp_name = dart_name or code
        else:
            corp_name = universe_name
        group = UNIVERSE.get(code, {}).get("group", "기타")

        snaps: Dict[int, Dict[str, Optional[float]]] = {}
        fs_used = []
        for y in years:
            try:
                fin_df, fs_div = client.financials(corp_code, y)
                snaps[y] = extract_snapshot(fin_df)
                fs_used.append(f"{y}:{fs_div or 'NA'}")
            except Exception as e:
                snaps[y] = {}
                fs_used.append(f"{y}:ERR")
                log(f"{code} {corp_name} financials {y} failed: {e}")

        try:
            div_df = client.dividend(corp_code, 2025)
            dps = extract_dps(div_df)
        except Exception as e:
            dps = None
            log(f"{code} {corp_name} dividend failed: {e}")

        try:
            stock_df = client.stock_total(corp_code, 2025)
            shares = extract_shares(stock_df)
        except Exception as e:
            shares = None
            log(f"{code} {corp_name} shares failed: {e}")

        metric = build_row(
            code=code,
            corp_name=corp_name,
            group=group,
            price=prices.get(code),
            shares=shares,
            dps=dps,
            snaps=snaps,
            base_year=args.bsns_year,
        )
        if fs_used:
            metric.notes = (metric.notes + "; " if metric.notes else "") + f"fs={','.join(fs_used)}"
        rows.append(metric)

        if (i + 1) <= 5 or (i + 1) % 5 == 0:
            log(f"Processed {i + 1}/{len(resolved)}")

    raw = to_frame(rows)
    filtered = apply_filters(raw, args.min1, args.min3, args.min5, args.max_ncper)

    out_base = args.out
    if args.tsv and out_base.endswith(".csv"):
        out_base = out_base[:-4] + ".tsv"

    if out_base.endswith(".tsv"):
        raw_out = out_base.replace(".tsv", "_raw.tsv")
        filtered_out = out_base.replace(".tsv", "_filtered.tsv")
        raw.to_csv(raw_out, sep="	", index=False, encoding="utf-8-sig")
        filtered.to_csv(filtered_out, sep="	", index=False, encoding="utf-8-sig")
    else:
        raw_out = out_base.replace(".csv", "_raw.csv")
        filtered_out = out_base.replace(".csv", "_filtered.csv")
        raw.to_csv(raw_out, index=False, encoding="utf-8-sig")
        filtered.to_csv(filtered_out, index=False, encoding="utf-8-sig")

    log(f"Saved raw      -> {raw_out} ({len(raw):,} rows)")
    log(f"Saved filtered -> {filtered_out} ({len(filtered):,} rows)")

    if raw.empty:
        log("No rows produced. Check DART key / data availability.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
