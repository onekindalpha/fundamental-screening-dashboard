#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""US Peter Lynch + Graham Dashboard v13 - auxiliary trend indicators"""

from __future__ import annotations

import glob
import math
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="🇺🇸 US Lynch-Graham Dashboard",
    page_icon="🇺🇸",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1500px; }
.small-note { color: #9ca3af; font-size: 0.86rem; }
.metric-help { color: #9ca3af; font-size: 0.80rem; line-height: 1.25; }
.explain-box { color:#d1d5db; font-size:0.90rem; line-height:1.55; }
.explain-box ul { margin-top:0.25rem; padding-left:1.2rem; }
.explain-box li { margin-bottom:0.35rem; }
.section-gap { margin-top: 1.4rem; }
hr { margin-top: 0.6rem; margin-bottom: 0.8rem; }
[data-testid="stMetricValue"] { font-size: 2rem; }
</style>
""",
    unsafe_allow_html=True,
)

UNIVERSE_FILES = {
    # 각 universe는 여러 파일명 변형을 허용한다.
    # 이전 버전에서 파일명이 조금만 달라도 "결과 파일 없음"으로 뜨던 문제를 막기 위함.
    "Dow 30": ["results_us/dow30_screening_*.tsv", "results_us/*dow*30*.tsv"],
    "Nasdaq 100": ["results_us/nasdaq100_screening_*.tsv", "results_us/*nasdaq*100*.tsv"],
    "S&P 500": ["results_us/sp500_screening_*.tsv", "results_us/*sp500_screening*.tsv"],
    "Company Add-ons": ["results_us/company_addons_screening_*.tsv", "results_us/*company*addons*.tsv", "results_us/*add*ons*.tsv"],
    "S&P 500 Growth": ["results_us/sp500_growth_screening_*.tsv", "results_us/*sp500*growth*.tsv", "results_us/*s*p*500*growth*.tsv"],
    "Russell 1000 Growth": ["results_us/russell1000_growth_screening_*.tsv", "results_us/*russell*1000*growth*.tsv", "results_us/*russell*growth*.tsv"],
    "Dividend Aristocrats": ["results_us/dividend_aristocrats_screening_*.tsv", "results_us/*dividend*aristocrat*.tsv"],
    "Dividend Kings": ["results_us/dividend_kings_screening_*.tsv", "results_us/*dividend*king*.tsv"],
}

UNIVERSE_ORDER = [
    "Dow 30",
    "Nasdaq 100",
    "S&P 500",
    "Company Add-ons",
    "S&P 500 Growth",
    "Russell 1000 Growth",
    "Dividend Aristocrats",
    "Dividend Kings",
    "Growth Leaders",
]

GROWTH_COLUMNS = {
    "1년": "연간이익증가율(1년,%)",
    "3년": "연간이익증가율(3년CAGR,%)",
    "5년": "연간이익증가율(5년CAGR,%)",
    "자동": "사용연성장률(%)",
}

GRAHAM_COLUMNS = {
    "1년": "그레이엄괴리율(1년,%)",
    "3년": "그레이엄괴리율(3년,%)",
    "5년": "그레이엄괴리율(5년,%)",
    "자동": "그레이엄괴리율(선택,%)",
}

BASE_DISPLAY_COLS = [
    "상세",
    "순위",
    "티커",
    "종목명",
    "업종",
    "유니버스",
    "종합판정 (with filter)",
    "린치PER판정* (Ex-Cash PEG)",
    "린치PER배수*",
    "배당감안판정* (Ex-Cash PEGY)",
    "배당감안점수*",
    "EPS Growth (%)",
    "Graham Gap (%)",
    "추세판정(보조)",
    "6M수익률(보조,%)",
    "52주고점대비(보조,%)",
    "200일선상회(보조)",
    "현재가",
    "주당순현금(린치식)",
    "주당잉여현금흐름",
    "하드필터통과",
]


PROFILE_PATH = Path("results_us/us_company_profiles.csv")
PROFILE_COLS = ["섹터", "산업", "국가", "웹사이트", "사업설명"]

PEG_LABELS = ["전체", "매우 유망", "헐값", "보통", "매우 불리", "판정불가"]
PEGY_LABELS = ["전체", "안심(>=2)", "양호(>=1.5)", "보통(1~1.5)", "불리(<1)", "판정불가"]
TOTAL_LABELS = ["전체", "매우 유망", "양호", "보류", "제외", "판정불가"]

PEGY_DISPLAY_MAP = {
    "안심": "안심(>=2)",
    "양호": "양호(>=1.5)",
    "보통": "보통(1~1.5)",
    "불리": "불리(<1)",
    "불리(<1)": "불리(<1)",
    "판정불가": "판정불가",
}

PEGY_REVERSE_MAP = {v: k for k, v in PEGY_DISPLAY_MAP.items()}


def label_pegy(v: object) -> str:
    x = str(v).strip()
    return PEGY_DISPLAY_MAP.get(x, x)


def judgement_options(df: pd.DataFrame, col: str, fixed_order: list[str], labeler=None) -> list[str]:
    if col not in df.columns:
        return ["전체"]
    raw_values = []
    for v in df[col].astype(str).fillna("").map(str.strip):
        if not v or v in {"nan", "None", "-"}:
            continue
        val = labeler(v) if labeler else v
        if val not in raw_values:
            raw_values.append(val)
    ordered = [x for x in fixed_order if x == "전체" or x in raw_values]
    rest = sorted([x for x in raw_values if x not in ordered])
    return ordered + rest


def clean_code(x) -> str:
    if pd.isna(x):
        return ""
    return str(x).replace('="', "").replace('"', "").strip().upper()


def to_num(s):
    return pd.to_numeric(pd.Series(s).astype(str).str.replace(",", "", regex=False), errors="coerce")


def fmt_num(v, decimals=2):
    try:
        if pd.isna(v):
            return "-"
        f = float(v)
        if abs(f) >= 1000:
            return f"{f:,.0f}"
        return f"{f:.{decimals}f}"
    except Exception:
        return "-"


def latest_file(patterns) -> str | None:
    """Return newest TSV for a pattern or list of patterns."""
    if isinstance(patterns, (str, Path)):
        patterns = [str(patterns)]
    files: list[str] = []
    for pattern in patterns:
        files.extend(glob.glob(str(pattern)))
    # 중복 패턴에 같은 파일이 여러 번 잡히는 것을 제거
    files = sorted(set(files), key=lambda p: Path(p).stat().st_mtime, reverse=True)
    return files[0] if files else None


def available_result_files() -> list[str]:
    return sorted([str(p) for p in Path("results_us").glob("*.tsv")])


@st.cache_data(show_spinner=False)
def load_tsv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", dtype=str).fillna("")
    if "티커" in df.columns:
        df["티커"] = df["티커"].map(clean_code)
    return df


@st.cache_data(show_spinner=False)
def load_profiles_cached(path: str, mtime: float) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str).fillna("")
    if "티커" in df.columns:
        df["티커"] = df["티커"].map(clean_code)
    keep = ["티커"] + [c for c in PROFILE_COLS if c in df.columns]
    return df[keep].drop_duplicates("티커", keep="last")


def attach_profiles(df: pd.DataFrame) -> pd.DataFrame:
    """Attach sector/industry/one-line description cache if available."""
    d = df.copy()
    for c in PROFILE_COLS:
        if c not in d.columns:
            d[c] = ""
    if not PROFILE_PATH.exists() or "티커" not in d.columns:
        return d
    try:
        prof = load_profiles_cached(str(PROFILE_PATH), PROFILE_PATH.stat().st_mtime)
        d = d.drop(columns=[c for c in PROFILE_COLS if c in d.columns], errors="ignore")
        d = d.merge(prof, on="티커", how="left")
        for c in PROFILE_COLS:
            if c not in d.columns:
                d[c] = ""
        return d.fillna("")
    except Exception:
        return d


def load_universe(name: str) -> tuple[pd.DataFrame | None, str | None]:
    if name == "Growth Leaders":
        frames = []
        sources = []
        for label, patterns in UNIVERSE_FILES.items():
            p = latest_file(patterns)
            if p:
                d = load_tsv(p).copy()
                if "유니버스" not in d.columns:
                    d["유니버스"] = label
                frames.append(d)
                sources.append(Path(p).name)
        if not frames:
            return None, None
        df = pd.concat(frames, ignore_index=True)
        if "티커" in df.columns:
            df = df.drop_duplicates("티커", keep="first")
        return attach_profiles(df), " + ".join(sources)

    # 1) 우선 해당 universe 전용 파일을 찾는다.
    p = latest_file(UNIVERSE_FILES[name])
    if p:
        d = load_tsv(p).copy()
        if "유니버스" not in d.columns:
            d["유니버스"] = name
        return attach_profiles(d), p

    # 2) 파일명이 조금 달라졌거나 합산 결과 파일만 있는 경우를 대비해
    #    results_us/*.tsv 전체에서 유니버스 컬럼이 해당 이름인 행을 복구한다.
    frames = []
    sources = []
    for fp in available_result_files():
        try:
            d = load_tsv(fp).copy()
        except Exception:
            continue
        if "유니버스" not in d.columns:
            continue
        mask = d["유니버스"].astype(str).str.strip().eq(name)
        if mask.any():
            frames.append(d[mask].copy())
            sources.append(Path(fp).name)
    if frames:
        df = pd.concat(frames, ignore_index=True)
        if "티커" in df.columns:
            df = df.drop_duplicates("티커", keep="first")
        return attach_profiles(df), " + ".join(sources)

    return None, None


def add_compare_columns(df: pd.DataFrame, eps_basis: str, graham_basis: str) -> pd.DataFrame:
    df = df.copy()
    eps_col = GROWTH_COLUMNS[eps_basis]
    graham_col = GRAHAM_COLUMNS[graham_basis]
    df["EPS Growth (%)"] = to_num(df[eps_col]) if eps_col in df.columns else np.nan
    df["Graham Gap (%)"] = to_num(df[graham_col]) if graham_col in df.columns else np.nan
    df["린치PER배수*num"] = to_num(df.get("린치PER배수", ""))
    df["배당감안점수*num"] = to_num(df.get("배당감안점수", ""))
    return df


def apply_growth_leaders(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    d = df.copy()
    eps3 = to_num(d.get("연간이익증가율(3년CAGR,%)", ""))
    fcfps = to_num(d.get("주당잉여현금흐름", ""))
    peg = to_num(d.get("린치PER배수", ""))
    pegy = to_num(d.get("배당감안점수", ""))
    if mode == "엄격":
        mask = (eps3 >= 15) & (fcfps > 0) & (peg <= 0.5) & (pegy >= 2.0)
    else:
        mask = (eps3 >= 10) & (fcfps > 0) & (peg < 1.0) & (pegy >= 1.5)
    return d[mask].copy()


def apply_exception_filters(df: pd.DataFrame, netcash_positive: bool, fcf_positive: bool, no_short_debt: bool) -> pd.DataFrame:
    d = df.copy()
    mask = pd.Series(True, index=d.index)
    if netcash_positive and "주당순현금(린치식)" in d.columns:
        mask &= to_num(d["주당순현금(린치식)"]) > 0
    if fcf_positive and "주당잉여현금흐름" in d.columns:
        mask &= to_num(d["주당잉여현금흐름"]) > 0
    if no_short_debt and "단기위험부채" in d.columns:
        short = to_num(d["단기위험부채"])
        mask &= short.fillna(0) <= 0
    return d[mask].copy()


def unique_options(df: pd.DataFrame, col: str) -> list[str]:
    if col not in df.columns:
        return ["전체"]
    values = []
    for v in df[col].astype(str).fillna("").map(str.strip):
        if v and v not in {"nan", "None", "-"} and v not in values:
            values.append(v)

    # 국장 대시보드와 비슷하게 판정 순서를 고정한다.
    if col == "종합판정":
        order = ["매우 유망", "양호", "보류", "제외", "판정불가"]
    elif col == "린치PER판정":
        order = ["매우 유망", "헐값", "보통", "매우 불리", "판정불가"]
    elif col == "배당감안점수판정":
        order = ["안심", "양호", "보통", "불리(<1)", "판정불가"]
    else:
        order = []

    ordered = [x for x in order if x in values]
    rest = sorted([x for x in values if x not in ordered])
    return ["전체"] + ordered + rest


def latest_update_time(universe: str, source: str | None) -> str:
    paths = []
    if universe == "Growth Leaders":
        for patterns in UNIVERSE_FILES.values():
            p = latest_file(patterns)
            if p:
                paths.append(Path(p))
    elif source:
        src = str(source).split(" + ")[0]
        if src and Path(src).exists():
            paths.append(Path(src))
        elif src:
            p = Path("results_us") / Path(src).name
            if p.exists():
                paths.append(p)

    if not paths:
        return "-"
    ts = max(p.stat().st_mtime for p in paths)
    return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")


def filter_label(selected: list[str]) -> str:
    return ", ".join(selected) if selected else "전체"


def option_without_all(options: list[str]) -> list[str]:
    return [x for x in options if x != "전체"]


def apply_judgement_filters(df: pd.DataFrame, total_filters: list[str], peg_filters: list[str], pegy_filters: list[str]) -> pd.DataFrame:
    """KR dashboard-style multi-select judgement filters.

    선택값이 비어 있으면 전체 표시. 여러 값을 선택하면 OR 조건으로 필터링한다.
    PEG/PEGY는 판정 텍스트뿐 아니라 숫자 기준도 함께 사용한다.
    """
    d = df.copy()

    if total_filters and "종합판정" in d.columns:
        raw_total = d["종합판정"].astype(str).str.strip()
        d = d[raw_total.isin(total_filters)]

    if peg_filters:
        peg = to_num(d.get("린치PER배수", ""))
        raw = d.get("린치PER판정", pd.Series("", index=d.index)).astype(str).str.strip()
        mask = pd.Series(False, index=d.index)
        for peg_filter in peg_filters:
            if peg_filter == "매우 유망":
                mask |= (peg <= 0.5) | (raw == "매우 유망")
            elif peg_filter == "헐값":
                mask |= ((peg > 0.5) & (peg < 1.0)) | (raw == "헐값")
            elif peg_filter == "보통":
                mask |= ((peg >= 1.0) & (peg < 2.0)) | (raw == "보통")
            elif peg_filter == "매우 불리":
                mask |= (peg >= 2.0) | (raw == "매우 불리")
            elif peg_filter == "판정불가":
                mask |= peg.isna() | raw.isin(["판정불가", "", "-", "None", "nan"])
            else:
                mask |= (raw == peg_filter)
        d = d[mask.fillna(False)]

    if pegy_filters:
        pegy = to_num(d.get("배당감안점수", ""))
        raw = d.get("배당감안점수판정", pd.Series("", index=d.index)).astype(str).str.strip().map(label_pegy)
        mask = pd.Series(False, index=d.index)
        for pegy_filter in pegy_filters:
            if pegy_filter == "안심(>=2)":
                mask |= (pegy >= 2.0) | (raw == "안심(>=2)")
            elif pegy_filter == "양호(>=1.5)":
                mask |= ((pegy >= 1.5) & (pegy < 2.0)) | (raw == "양호(>=1.5)")
            elif pegy_filter == "보통(1~1.5)":
                mask |= ((pegy >= 1.0) & (pegy < 1.5)) | (raw == "보통(1~1.5)")
            elif pegy_filter == "불리(<1)":
                mask |= (pegy < 1.0) | (raw == "불리(<1)")
            elif pegy_filter == "판정불가":
                mask |= pegy.isna() | raw.isin(["판정불가", "", "-", "None", "nan"])
            else:
                mask |= (raw == pegy_filter)
        d = d[mask.fillna(False)]

    return d.copy()


def format_display_values(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    # 국장 대시보드처럼 PEGY 판정에는 기준 숫자를 함께 표시한다.
    if "배당감안판정* (Ex-Cash PEGY)" in d.columns:
        d["배당감안판정* (Ex-Cash PEGY)"] = d["배당감안판정* (Ex-Cash PEGY)"].map(label_pegy)
    numeric_cols = [
        "린치PER배수*",
        "배당감안점수*",
        "EPS Growth (%)",
        "Graham Gap (%)",
        "6M수익률(보조,%)",
        "52주고점대비(보조,%)",
        "현재가",
        "주당순현금(린치식)",
        "주당잉여현금흐름",
    ]
    for c in numeric_cols:
        if c in d.columns:
            d[c] = to_num(d[c]).map(lambda x: fmt_num(x, 2))
    return d


def sort_df(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    d = df.copy()
    if mode == "EPS성장률 우선":
        sort_cols = ["EPS Growth (%)", "린치PER배수*num", "배당감안점수*num", "Graham Gap (%)"]
        asc = [False, True, False, False]
    elif mode == "Graham괴리율 우선":
        sort_cols = ["Graham Gap (%)", "린치PER배수*num", "배당감안점수*num", "EPS Growth (%)"]
        asc = [False, True, False, False]
    elif mode == "배당감안점수 우선":
        sort_cols = ["배당감안점수*num", "린치PER배수*num", "EPS Growth (%)", "Graham Gap (%)"]
        asc = [False, True, False, False]
    else:
        sort_cols = ["린치PER배수*num", "배당감안점수*num", "EPS Growth (%)", "Graham Gap (%)"]
        asc = [True, False, False, False]
    sort_cols = [c for c in sort_cols if c in d.columns]
    asc = asc[: len(sort_cols)]
    return d.sort_values(sort_cols, ascending=asc, na_position="last") if sort_cols else d


def make_display_df(df: pd.DataFrame) -> pd.DataFrame:
    d = df.reset_index(drop=True).copy()
    # 표에서는 국장 대시보드의 "그룹/업종"처럼 한 칸만 보여준다.
    # 업종 = 산업(industry)이 있으면 산업, 없으면 섹터(sector).
    # 둘 다 비어 있으면 표에서 업종 컬럼 자체를 제거한다. 사업설명은 상세에서만 표시한다.
    industry = d["산업"].astype(str).str.strip() if "산업" in d.columns else pd.Series([""] * len(d), index=d.index)
    sector = d["섹터"].astype(str).str.strip() if "섹터" in d.columns else pd.Series([""] * len(d), index=d.index)
    d["업종"] = industry.where(industry.ne(""), sector)
    if d["업종"].astype(str).str.strip().replace({"nan": "", "None": "", "-": ""}).eq("").all():
        d = d.drop(columns=["업종"], errors="ignore")
    d.insert(0, "순위", range(1, len(d) + 1))
    d.insert(0, "상세", False)
    rename = {
        "종합판정": "종합판정 (with filter)",
        "린치PER판정": "린치PER판정* (Ex-Cash PEG)",
        "린치PER배수": "린치PER배수*",
        "배당감안점수판정": "배당감안판정* (Ex-Cash PEGY)",
        "배당감안점수": "배당감안점수*",
    }
    d = d.rename(columns=rename)
    cols = [c for c in BASE_DISPLAY_COLS if c in d.columns]
    return format_display_values(d[cols])



def render_us_interpretation_notes(compact: bool = False) -> None:
    """US-specific interpretation notes, modeled after the KR dashboard notes."""
    body = """
<div class="explain-box">
<b>단기위험부채로 보는 항목</b><br>
미장에서는 <b>Short-term debt, Current portion of long-term debt, Commercial paper, Notes payable</b>처럼
1년 안팎에 상환·차환 부담이 생길 수 있는 항목을 보수적으로 묶어 봅니다.
린치 관점에서는 단기 차환 부담이 커질수록 별도 주의 신호로 봅니다.
<br><br>
<b>주당순현금 / FCF 해석 메모</b>
<ul>
<li><b>금융·은행·보험·증권:</b> 예금, 보험부채, 운용자산, 레버리지가 사업모델의 일부라 제조업식 순현금 기준이 왜곡될 수 있습니다. 이 경우 순현금보다 자본적정성, 장부가, ROE, 손해율·combined ratio 등을 함께 봐야 합니다.</li>
<li><b>통신·유틸리티·전력·에너지 인프라:</b> 네트워크, 발전설비, 파이프라인 등 장기 인프라 투자 때문에 부채가 구조적으로 큽니다. 순현금 음수만으로 배제하기보다 FCF 안정성, 요금규제, 만기구조를 같이 봅니다.</li>
<li><b>소프트웨어·플랫폼·반도체·헬스케어:</b> 현금창출력이 강한 우량 기업은 FCF와 순현금이 더 중요합니다. 이 업종은 주당순현금 음수와 FCF 음수를 비교적 엄격하게 봐도 됩니다.</li>
<li><b>산업재·항공·자동차·소재·에너지 등 경기민감 업종:</b> 재고, 운전자본, CAPEX 사이클 때문에 특정 연도 FCF가 흔들릴 수 있습니다. 단일 연도보다 3~5년 평균 흐름과 부채 만기구조를 같이 봅니다.</li>
<li><b>배당귀족주·배당왕족주:</b> PEG가 아주 낮게 나오지 않을 수 있습니다. 이 탭은 고성장보다 배당 안정성·현금흐름 지속성을 보는 보조 universe로 해석합니다.</li>
<li><b>ADR·해외기업:</b> SEC/XBRL 태그나 회계기준 차이 때문에 일부 EPS·FCF·부채 항목이 덜 잡힐 수 있습니다. 결측이 많으면 원문 보고서와 Yahoo/IR 자료를 같이 확인합니다.</li>
</ul>
</div>
"""
    if compact:
        st.markdown(body, unsafe_allow_html=True)
    else:
        with st.expander("📘 미장 업종별 해석 메모", expanded=True):
            st.markdown(body, unsafe_allow_html=True)

def link_buttons(ticker: str, name: str, cik: str = "") -> None:
    q = quote_plus(f"{ticker} {name} earnings report investor relations")
    sec_url = f"https://www.sec.gov/edgar/browse/?CIK={cik}&owner=exclude" if cik else f"https://www.sec.gov/edgar/search/#/q={quote_plus(ticker)}"
    yahoo_url = f"https://finance.yahoo.com/quote/{ticker}"
    finviz_url = f"https://finviz.com/quote.ashx?t={ticker}"
    google_pdf_url = f"https://www.google.com/search?q={q}+filetype%3Apdf"
    nasdaq_url = f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.link_button("SEC EDGAR", sec_url, use_container_width=True)
    c2.link_button("Yahoo Finance", yahoo_url, use_container_width=True)
    c3.link_button("Finviz", finviz_url, use_container_width=True)
    c4.link_button("Nasdaq", nasdaq_url, use_container_width=True)
    c5.link_button("PDF Report Search", google_pdf_url, use_container_width=True)


def render_detail(row: pd.Series) -> None:
    ticker = clean_code(row.get("티커", ""))
    name = row.get("종목명", ticker)
    cik = str(row.get("CIK", "")).strip()
    st.markdown(f"### 🔍 선택 종목 상세: {name} ({ticker})")
    link_buttons(ticker, name, cik)

    sector = str(row.get("섹터", "")).strip()
    industry = str(row.get("산업", "")).strip()
    country = str(row.get("국가", "")).strip()
    website = str(row.get("웹사이트", "")).strip()
    desc = str(row.get("사업설명", "")).strip()
    meta = []
    if sector:
        meta.append(f"섹터: **{sector}**")
    if industry:
        meta.append(f"산업: **{industry}**")
    if country:
        meta.append(f"국가: **{country}**")
    if website:
        meta.append(f"웹사이트: {website}")
    if meta:
        st.markdown(" · ".join(meta))
    if desc:
        st.caption(desc[:420] + ("..." if len(desc) > 420 else ""))

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("현재가", fmt_num(row.get("현재가")))
    m2.metric("Ex-Cash PEG", fmt_num(row.get("린치PER배수")))
    m3.metric("Ex-Cash PEGY", fmt_num(row.get("배당감안점수")))
    m4.metric("EPS Growth", fmt_num(row.get("사용연성장률(%)")))
    m5.metric("Graham Gap", fmt_num(row.get("그레이엄괴리율(선택,%)")))

    st.markdown(
        '<div class="metric-help">* Ex-Cash PEG: 0.5 이하 = 매우 유망, 1 미만 = 헐값 · '
        'Ex-Cash PEGY Score: 2.0 이상 = 안심, 1.5 이상 = 양호</div>',
        unsafe_allow_html=True,
    )

    st.markdown("#### 보조 추세 지표")
    st.caption("아래 지표는 Lynch/Graham 판정에는 반영하지 않고, 차트 우상향 여부를 참고하기 위한 보조지표입니다.")
    t1, t2, t3, t4, t5 = st.columns(5)
    t1.metric("추세판정", str(row.get("추세판정(보조)", "-") or "-"))
    t2.metric("3M 수익률", fmt_num(row.get("3M수익률(보조,%)")))
    t3.metric("6M 수익률", fmt_num(row.get("6M수익률(보조,%)")))
    t4.metric("12M 수익률", fmt_num(row.get("12M수익률(보조,%)")))
    t5.metric("52주 고점 대비", fmt_num(row.get("52주고점대비(보조,%)")))
    t6, t7, t8 = st.columns(3)
    t6.metric("50일선 상회", str(row.get("50일선상회(보조)", "-") or "-"))
    t7.metric("200일선 상회", str(row.get("200일선상회(보조)", "-") or "-"))
    t8.metric("200일 이평", fmt_num(row.get("200일이평(보조)")))

    render_us_interpretation_notes(compact=False)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### 성장률 / 그레이엄")
        chart = pd.DataFrame({
            "구분": ["EPS 1Y", "EPS 3Y", "EPS 5Y", "Graham Gap 1Y", "Graham Gap 3Y", "Graham Gap 5Y"],
            "값": [
                pd.to_numeric(row.get("연간이익증가율(1년,%)", np.nan), errors="coerce"),
                pd.to_numeric(row.get("연간이익증가율(3년CAGR,%)", np.nan), errors="coerce"),
                pd.to_numeric(row.get("연간이익증가율(5년CAGR,%)", np.nan), errors="coerce"),
                pd.to_numeric(row.get("그레이엄괴리율(1년,%)", np.nan), errors="coerce"),
                pd.to_numeric(row.get("그레이엄괴리율(3년,%)", np.nan), errors="coerce"),
                pd.to_numeric(row.get("그레이엄괴리율(5년,%)", np.nan), errors="coerce"),
            ],
        }).dropna()
        if len(chart):
            st.bar_chart(chart.set_index("구분"))
        else:
            st.info("표시할 성장률/괴리율 데이터가 부족합니다.")

    with col_b:
        st.markdown("#### 현금성자산 / 부채 구조")
        chart = pd.DataFrame({
            "구분": ["현금성자산합계", "장기부채", "단기위험부채", "주주지분", "총부채"],
            "값": [
                pd.to_numeric(row.get("현금성자산합계", np.nan), errors="coerce"),
                pd.to_numeric(row.get("장기부채", np.nan), errors="coerce"),
                pd.to_numeric(row.get("단기위험부채", np.nan), errors="coerce"),
                pd.to_numeric(row.get("주주지분", np.nan), errors="coerce"),
                pd.to_numeric(row.get("총부채", np.nan), errors="coerce"),
            ],
        }).dropna()
        if len(chart):
            st.bar_chart(chart.set_index("구분"))
        else:
            st.info("표시할 현금/부채 데이터가 부족합니다.")

    st.markdown("#### 재무 원천값 / 상세 지표")
    cols = [
        "섹터", "산업", "국가", "웹사이트", "사업설명",
        "현재가", "EPS(FY)", "EPS기준연도", "배당수익률(%)",
        "추세판정(보조)", "3M수익률(보조,%)", "6M수익률(보조,%)", "12M수익률(보조,%)",
        "52주고점대비(보조,%)", "50일이평(보조)", "200일이평(보조)", "50일선상회(보조)", "200일선상회(보조)",
        "현금및현금성자산", "유가증권성자산", "현금성자산합계", "장기부채", "단기위험부채",
        "주주지분", "총부채", "주당순현금(린치식)", "주당순현금(보수형)",
        "순현금차감PER(린치식)", "순현금차감PER(보수형)",
        "주당잉여현금흐름", "잉여현금흐름수익률(%)",
        "사용연성장률기준", "사용연성장률(%)", "린치PER배수", "린치PER판정",
        "배당감안점수기준", "배당감안점수", "배당감안점수판정",
        "그레이엄사용기준", "그레이엄내재가치(선택)", "그레이엄괴리율(선택,%)",
        "하드필터통과", "하드필터사유", "종합판정", "종합판정사유", "비고",
    ]
    detail = pd.DataFrame([
        {"항목": c, "값": row.get(c, "")} for c in cols if c in row.index
    ])
    st.dataframe(detail, use_container_width=True, hide_index=True, height=520)


def main():
    st.title("🇺🇸 US Peter Lynch + Graham Dashboard")
    st.caption("S&P 500 / Nasdaq 100 / Dow 30 / Company Add-ons / Growth·Dividend Universe · Growth Leaders 자동 탭")

    with st.sidebar:
        st.markdown("## 시장 선택")
        universe = st.radio("Universe", UNIVERSE_ORDER, index=0)
        st.markdown(
            """
<div class="small-note">
각 Universe는 별도 결과 파일을 읽습니다.<br>
Growth Leaders는 생성된 모든 Universe 결과를 합친 뒤 조건에 맞는 종목만 자동 선별합니다.
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.markdown("## 예외 필터")
        netcash_positive = st.checkbox("주당순현금 > 0", value=False)
        fcf_positive = st.checkbox("FCF per Share > 0", value=False)
        no_short_debt = st.checkbox("단기위험부채 없음", value=False)
        st.markdown("---")
        st.markdown("## Growth Leaders")
        growth_mode = st.radio("기준", ["기본", "엄격"], index=0, help="Growth Leaders 탭에서만 적용")
        st.markdown(
            """
<div class="small-note">
기본: EPS Growth 3Y ≥ 10%, FCF > 0, Ex-Cash PEG < 1, PEGY ≥ 1.5<br>
엄격: EPS Growth 3Y ≥ 15%, FCF > 0, Ex-Cash PEG ≤ 0.5, PEGY ≥ 2.0
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.markdown("## 해석")
        st.markdown(
            """
<div class="small-note">
Ex-Cash PEG ≤ 0.5 = 매우 유망<br>
Ex-Cash PEG < 1.0 = 헐값<br>
Ex-Cash PEGY ≥ 1.5 = 양호<br>
Ex-Cash PEGY ≥ 2.0 = 안심
</div>
""",
            unsafe_allow_html=True,
        )
        with st.expander("미장 업종별 해석", expanded=False):
            render_us_interpretation_notes(compact=True)

    df, source = load_universe(universe)
    if df is None or len(df) == 0:
        st.warning("선택한 Universe의 결과 파일을 찾지 못했습니다. results_us 안의 파일명도 함께 확인합니다.")
        files = available_result_files()
        if files:
            st.caption("현재 감지된 results_us TSV 파일")
            st.code("\n".join(Path(x).name for x in files), language="text")
        else:
            st.code(
                "python -u us_lynch_graham_screener.py --universe dow30_tickers.txt --universe-name 'Dow 30' --out results_us/dow30_screening_$(date +%Y%m%d).tsv",
                language="bash",
            )
        return

    raw_total_count = len(df)
    update_datetime = latest_update_time(universe, source)

    st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
    st.markdown("## 판정 필터")
    st.caption("판정은 정렬이 아니라 필터입니다. 아무것도 선택하지 않으면 전체를 보여줍니다.")
    # 국장 대시보드처럼 판정 필터는 안정적인 다중선택 상태로 유지한다.
    # 이전 버전은 현재 데이터에 존재하는 옵션만 동적으로 만들면서 rerun 때 선택값이 풀릴 수 있었다.
    # 여기서는 전체 판정 옵션을 고정하고 session_state key를 명시해, 정렬/기준/예외필터 변경 후에도 선택값을 유지한다.
    total_options = option_without_all(TOTAL_LABELS)
    peg_options = option_without_all(PEG_LABELS)
    pegy_options = option_without_all(PEGY_LABELS)

    for state_key, valid_options in [
        ("us_total_filter", total_options),
        ("us_peg_filter", peg_options),
        ("us_pegy_filter", pegy_options),
    ]:
        if state_key not in st.session_state:
            st.session_state[state_key] = []
        else:
            st.session_state[state_key] = [x for x in st.session_state[state_key] if x in valid_options]

    f1, f2, f3 = st.columns(3)
    with f1:
        total_filter = st.multiselect(
            "종합판정 (with filter)",
            total_options,
            key="us_total_filter",
            placeholder="전체",
        )
    with f2:
        peg_filter = st.multiselect(
            "린치PER판정* (Ex-Cash PEG)",
            peg_options,
            key="us_peg_filter",
            placeholder="전체",
        )
    with f3:
        pegy_filter = st.multiselect(
            "배당감안판정* (Ex-Cash PEGY)",
            pegy_options,
            key="us_pegy_filter",
            placeholder="전체",
        )

    df = apply_judgement_filters(df, total_filter, peg_filter, pegy_filter)

    st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
    st.markdown(f"## {universe} 유망주 랭킹")
    st.caption("정렬: 린치PER배수 낮은순 → 배당감안점수 높은순 → 선택 EPS성장률 높은순 → 선택 그레이엄괴리율 높은순이 기본입니다.")

    c1, c2, c3 = st.columns(3)
    with c1:
        eps_basis = st.selectbox("EPS 성장률 기준", ["3년", "1년", "5년", "자동"], index=0)
    with c2:
        graham_basis = st.selectbox("그레이엄 괴리율 기준", ["3년", "1년", "5년", "자동"], index=0)
    with c3:
        sort_mode = st.selectbox("정렬 우선 방식", ["린치 우선", "EPS성장률 우선", "Graham괴리율 우선", "배당감안점수 우선"], index=0)

    df = add_compare_columns(df, eps_basis, graham_basis)
    if universe == "Growth Leaders":
        df = apply_growth_leaders(df, growth_mode)
    df = apply_exception_filters(df, netcash_positive, fcf_positive, no_short_debt)

    if universe == "Growth Leaders":
        data_label = "전체 생성 결과 합산"
    else:
        data_label = Path(str(source).split(" + ")[0]).name if source else "-"

    st.info(
        f"현재 기준: EPS {eps_basis} / Graham {graham_basis} / 정렬 {sort_mode} / "
        f"판정필터: 종합={filter_label(total_filter)}, PEG={filter_label(peg_filter)}, PEGY={filter_label(pegy_filter)} / 데이터 {data_label}"
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📊 전체 종목 수", f"{raw_total_count:,}")
    m2.metric("✅ 현재 표시 종목 수", f"{len(df):,}")
    m3.metric("🕘 마지막 업데이트", update_datetime)
    if "유니버스" in df.columns:
        universe_count = df["유니버스"].astype(str).replace("", np.nan).nunique()
    else:
        universe_count = 1
    m4.metric("🧩 유니버스 수", f"{universe_count:,}")

    df = sort_df(df, sort_mode)
    display_df = make_display_df(df)

    if len(display_df) == 0:
        st.warning("조건에 맞는 종목이 없습니다.")
        return

    edited = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=520,
        disabled=[c for c in display_df.columns if c != "상세"],
        column_config={
            "상세": st.column_config.CheckboxColumn("상세", help="체크하면 아래에 상세가 표시됩니다."),
            "순위": st.column_config.NumberColumn("순위", width="small"),
            "티커": st.column_config.TextColumn("티커", width="small"),
            "종목명": st.column_config.TextColumn("종목명", width="medium"),
            "업종": st.column_config.TextColumn("업종", width="medium"),
        },
        key=f"us_table_{universe}_{eps_basis}_{graham_basis}_{sort_mode}_{growth_mode}_{filter_label(total_filter)}_{filter_label(peg_filter)}_{filter_label(pegy_filter)}",
    )

    selected_idx = None
    if "상세" in edited.columns and edited["상세"].any():
        selected_idx = int(edited.index[edited["상세"]].tolist()[-1])
    else:
        selected_idx = 0

    selected_ticker = edited.iloc[selected_idx]["티커"]
    selected_row = df.reset_index(drop=True)[df.reset_index(drop=True)["티커"] == selected_ticker]
    if len(selected_row):
        st.markdown("---")
        render_detail(selected_row.iloc[0])


if __name__ == "__main__":
    main()
