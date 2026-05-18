#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fundamental Screening Dashboard

Streamlit dashboard for financial metrics screening across Korean market universes.
The app focuses on data processing, screening filters, dashboard interaction, and reproducible outputs.
"""

from __future__ import annotations

import glob
import inspect
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Fundamental Screening Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .block-container { padding-top: 1.25rem !important; }
    .small-muted { color: #888; font-size: 0.92rem; }
    .section-card {
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 12px;
        background: rgba(255,255,255,0.02);
    }
    .warning-box {
        background: rgba(245, 158, 11, 0.16);
        border-left: 4px solid #f59e0b;
        padding: 10px 12px;
        border-radius: 8px;
        margin-bottom: 8px;
    }
    .info-box {
        background: rgba(59, 130, 246, 0.12);
        border-left: 4px solid #3b82f6;
        padding: 10px 12px;
        border-radius: 8px;
        margin-bottom: 8px;
    }
    .mini-card {
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 12px;
        padding: 12px 14px;
        margin-bottom: 10px;
        background: rgba(255,255,255,0.025);
    }
    .mini-title { color: #aaa; font-size: 0.84rem; margin-bottom: 2px; }
    .mini-value { font-size: 1.25rem; font-weight: 700; }
    .mini-caption { color: #888; font-size: 0.78rem; line-height: 1.35; }
    .good { color: #22c55e; font-weight: 700; }
    .bad { color: #ef4444; font-weight: 700; }
    .hint-box {
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 12px;
        padding: 12px 14px;
        background: rgba(255,255,255,0.025);
        margin-bottom: 12px;
    }
    .hint-title { color:#aaa; font-size:0.84rem; margin-bottom:4px; }
    .hint-body { font-size:0.96rem; line-height:1.45; }
</style>
""",
    unsafe_allow_html=True,
)

TIMING_KEYWORDS = [
    "시장상승세", "시장사유", "업종상승세", "업종사유", "MA30", "피벗", "윗저항",
    "저항", "돌파", "거래량", "늦은진입", "기술점수", "타이밍", "종가",
]

EPS_BASIS_COL = {
    "1Y": "연간이익증가율(1년,%)",
    "3Y": "연간이익증가율(3년CAGR,%)",
    "5Y": "연간이익증가율(5년CAGR,%)",
    "Auto": "사용연성장률(%)",
}

GRAHAM_BASIS_COL = {
    "1Y": "그레이엄괴리율(1년,%)",
    "3Y": "그레이엄괴리율(3년,%)",
    "5Y": "그레이엄괴리율(5년,%)",
    "Auto": "그레이엄괴리율(선택,%)",
}

SORT_MODE_SPECS = {
    "Lynch-style ratio first (default)": [
        ("린치PER배수", True),
        ("배당감안점수", False),
        ("비교 EPS성장률(%)", False),
        ("비교 그레이엄괴리율(%)", False),
    ],
    "EPS growth first": [
        ("비교 EPS성장률(%)", False),
        ("린치PER배수", True),
        ("배당감안점수", False),
        ("비교 그레이엄괴리율(%)", False),
    ],
    "Graham gap first": [
        ("비교 그레이엄괴리율(%)", False),
        ("린치PER배수", True),
        ("배당감안점수", False),
        ("비교 EPS성장률(%)", False),
    ],
    "Dividend-adjusted score first": [
        ("배당감안점수", False),
        ("린치PER배수", True),
        ("비교 EPS성장률(%)", False),
        ("비교 그레이엄괴리율(%)", False),
    ],
}

TEXT_EXACT_COLS = {
    "종목코드", "종목명", "그룹", "판정구분", "Notes",
    "현금보다부채많음(린치형)", "현금보다부채많음(보수형)",
    "주주대부채판정", "업종보정유형", "업종보정판정",
    "그레이엄사용기준", "배당감안점수기준", "배당감안점수판정",
    "사용연성장률기준", "린치PER판정", "하드필터통과", "하드필터사유",
    "종합판정", "종합판정사유", "시장구분",
}

# 원본에서 그룹이 '직접추가'인 종목은 대시보드 표시용으로만 업종을 추정한다.
# 원본 TSV 자체를 바꾸지는 않는다.
GROUP_BY_CODE = {
    "307950": "IT서비스/모빌리티SW",  # 현대오토에버
    "204320": "자동차부품",          # HL만도: 수동 코드 목록에 없을 수 있음
    "000640": "제약/지주",
    "015360": "기타/확인필요",
}

GROUP_RULES = [
    ("금융/은행/증권/보험", ["금융", "은행", "증권", "보험", "화재", "생명", "카카오뱅크", "신한지주", "하나금융", "BNK"]),
    ("자동차/자동차부품", ["현대자동차", "기아", "현대모비스", "현대위아", "HL만도", "에스엘", "넥센타이어", "한국앤컴퍼니", "DH오토넥스", "KG모빌리티"]),
    ("IT서비스/인터넷/게임", ["NAVER", "카카오", "엔씨", "NC", "삼성에스디에스", "현대오토에버", "LG씨엔에스"]),
    ("전기전자/전력장비", ["삼성전기", "LG전자", "LG이노텍", "대한전선", "산일전기", "세방전지", "신일전자"]),
    ("디스플레이", ["LG디스플레이"]),
    ("건설/인프라", ["건설", "삼성E&A", "HDC", "아이에스동서"]),
    ("조선/기계", ["조선", "중공업", "미포", "한화엔진", "두산", "혜인", "현대엘리베이터"]),
    ("화학/소재", ["화학", "케미칼", "OCI", "정밀화학", "코스모", "한솔케미칼", "KCC", "미원상사", "이수화학", "롯데에너지머티리얼즈", "금양", "영풍"]),
    ("철강/금속", ["철강", "풍산", "고려제강", "대한전선"]),
    ("운송/물류", ["대한항공", "HMM", "한진", "CJ대한통운"]),
    ("유통/소비/레저", ["쇼핑", "리테일", "신세계", "호텔신라", "강원랜드", "GKL", "하나투어", "한샘", "코웨이", "한섬", "경방", "조광피혁"]),
    ("음식료/필수소비", ["식품", "오리온", "하이트진로", "대상", "빙그레", "롯데칠성", "삼립", "동원", "대한제당", "CJ씨푸드", "삼양", "제당"]),
    ("제약/바이오", ["제약", "약품", "녹십자", "유유제약", "보령", "부광", "한미사이언스", "일동", "진원생명", "HLB"]),
    ("지주/복합", ["홀딩스", "지주", "LG", "SK", "GS", "CJ", "HD현대", "DL", "한화", "효성", "LS", "코오롱", "대웅", "한진중공업홀딩스", "세방"]),
    ("광고/서비스", ["제일기획", "에스원"]),
    ("제지/목재", ["제지", "페이퍼", "홈데코", "성창기업"]),
    ("상사/무역", ["상사", "글로벌", "인터내셔널", "네트웍스"]),
]


DISPLAY_TRANSLATIONS = {
    "1Y": "1Y", "3Y": "3Y", "5Y": "5Y", "자동": "Auto",
    "메인": "Main", "직접추가": "Manually Added", "기타/확인필요": "Other / Needs Review",
    "매우 유망": "Very Attractive", "헐값": "Undervalued", "보통": "Neutral", "매우 불리": "Unfavorable",
    "안심(>=2)": "Strong (>=2)", "양호(>=1.5)": "Positive (>=1.5)", "보통(1~1.5)": "Neutral (1~1.5)", "불리(<1)": "Weak (<1)",
    "판정불가": "Not Available", "보류": "Hold / Review", "제외": "Excluded", "양호": "Positive",
    "금융/은행/증권/보험": "Financials / Banks / Securities / Insurance",
    "자동차/자동차부품": "Automotive / Auto Parts", "자동차부품": "Auto Parts",
    "IT서비스/인터넷/게임": "IT Services / Internet / Games", "IT서비스/모빌리티SW": "IT Services / Mobility SW",
    "전기전자/전력장비": "Electronics / Power Equipment", "디스플레이": "Display",
    "건설/인프라": "Construction / Infrastructure", "조선/기계": "Shipbuilding / Machinery",
    "화학/소재": "Chemicals / Materials", "철강/금속": "Steel / Metals", "운송/물류": "Transportation / Logistics",
    "유통/소비/레저": "Retail / Consumer / Leisure", "음식료/필수소비": "Food & Staples", "제약/바이오": "Pharma / Bio",
    "제약/지주": "Pharma / Holding Company", "지주/복합": "Holdings / Conglomerates", "광고/서비스": "Advertising / Services",
    "제지/목재": "Paper / Wood", "상사/무역": "Trading / Commerce",
    "현금보다부채많음": "Debt Exceeds Cash", "통과": "Pass", "실패": "Fail",
}

DISPLAY_COLUMN_LABELS = {
    "순위": "Rank", "종목코드": "Ticker", "종목명": "Company", "그룹": "Group", "원본그룹": "Original Group",
    "판정구분": "Classification", "Notes": "Notes", "종합판정": "Overall Signal", "종합판정사유": "Overall Reason",
    "린치PER배수": "Lynch-style Ratio*", "린치PER판정": "Lynch-style Signal*", "배당감안점수": "Dividend-adjusted Score*",
    "배당감안점수판정": "Dividend-adjusted Signal*", "성장률 기준": "EPS Growth Basis", "비교 EPS성장률(%)": "EPS Growth for Comparison (%)",
    "그레이엄 기준": "Graham Gap Basis", "비교 그레이엄괴리율(%)": "Graham Gap for Comparison (%)",
    "Dividend Yield (%)": "Dividend Yield (%)", "Net Cash / Share (Lynch-style)": "Net Cash / Share (Lynch-style)",
    "Net Cash / Share (Conservative)": "Net Cash / Share (Conservative)", "FCF / Share": "FCF / Share", "Short-term Risk Debt": "Short-term Risk Debt",
    "순현금차감PER(린치식)": "Ex-Cash P/E (Lynch-style)", "순현금차감PER(보수형)": "Ex-Cash P/E (Conservative)",
    "하드필터사유": "Hard Filter Reason", "현재가": "Current Price", "EPS(FY2025)": "EPS (FY2025)", "현금배당금(FY2025 DPS)": "Cash Dividend (FY2025 DPS)",
    "Cash & Cash Equivalents": "Cash & Cash Equivalents", "Marketable Securities": "Marketable Securities", "Long-term Debt": "Long-term Debt", "주주지분": "Shareholders' Equity",
    "총부채": "Total Liabilities", "발행주식수": "Shares Outstanding", "잉여현금흐름수익률(%)": "FCF Yield (%)",
    "연간이익증가율(1년,%)": "EPS Growth 1Y (%)", "연간이익증가율(3년CAGR,%)": "EPS Growth 3Y CAGR (%)", "연간이익증가율(5년CAGR,%)": "EPS Growth 5Y CAGR (%)",
    "그레이엄적정PER(선택)": "Graham Fair P/E (Selected)", "그레이엄내재가치(선택)": "Graham Intrinsic Value (Selected)", "그레이엄괴리율(선택,%)": "Graham Gap (Selected, %)",
    "그레이엄사용기준": "Graham Basis Used", "사용연성장률기준": "Growth Basis Used", "사용연성장률(%)": "Growth Used (%)",
    "현금보다부채많음(린치형)": "Debt > Cash (Lynch-style)", "현금보다부채많음(보수형)": "Debt > Cash (Conservative)",
    "주주대부채판정": "Equity-to-Debt Signal", "업종보정유형": "Sector Adjustment Type", "업종보정판정": "Sector-adjusted Signal",
    "그레이엄괴리율(1년,%)": "Graham Gap 1Y (%)", "그레이엄괴리율(3년,%)": "Graham Gap 3Y (%)", "그레이엄괴리율(5년,%)": "Graham Gap 5Y (%)",
    "시장구분": "Market", "하드필터통과": "Hard Filter Pass", "배당감안점수기준": "Dividend-adjusted Score Basis",
}

def display_text(value) -> str:
    s = clean_text(value)
    return DISPLAY_TRANSLATIONS.get(s, s)


def display_label(value) -> str:
    s = str(value)
    return DISPLAY_COLUMN_LABELS.get(s, DISPLAY_TRANSLATIONS.get(s, s))


def infer_group(code: str, name: str, group: str) -> str:
    group = clean_text(group)
    if group and group != "직접추가":
        return group
    code = clean_stock_code(code)
    name = clean_text(name)
    if code in GROUP_BY_CODE:
        return GROUP_BY_CODE[code]
    for label, keys in GROUP_RULES:
        if any(k in name for k in keys):
            return label
    return "기타/확인필요"


def enrich_display_groups(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if {"종목코드", "종목명", "그룹"}.issubset(out.columns):
        out["원본그룹"] = out["그룹"]
        out["그룹"] = out.apply(lambda r: infer_group(r.get("종목코드"), r.get("종목명"), r.get("그룹")), axis=1)
    return out


def clean_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    s = str(value).strip()
    if s.lower() in {"nan", "none", "nat", "<na>"}:
        return ""
    return s


def clean_stock_code(value) -> str:
    """종목코드 표시/링크용 정리.
    Google Sheets에서 앞자리 0 보존용으로 들어간 ="005930" 형태도 005930으로 바꾼다.
    """
    s = clean_text(value)
    if s == "":
        return ""
    s = s.strip()
    # ="005930" 또는 ='005930' 형태 제거
    if s.startswith('="') and s.endswith('"'):
        s = s[2:-1]
    elif s.startswith("='") and s.endswith("'"):
        s = s[2:-1]
    elif s.startswith("="):
        s = s[1:].strip().strip('"').strip("'")
    s = s.replace("'", "").replace('"', "").strip()
    s = s.replace(".0", "") if s.endswith(".0") else s
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) >= 6:
        return digits[-6:]
    return digits.zfill(6) if digits else s


def company_query_name(value) -> str:
    return clean_text(value).replace("(주)", "").replace("㈜", "").strip()


def to_num(value) -> float:
    s = clean_text(value).replace(",", "")
    if s == "" or s == "-":
        return np.nan
    try:
        return float(s)
    except Exception:
        return np.nan


def num_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return df[col].map(to_num)


def fmt(value, decimals: int = 2) -> str:
    s = clean_text(value)
    if s == "":
        return "-"
    n = to_num(value)
    if not pd.isna(n):
        if abs(n) >= 1000:
            return f"{n:,.0f}"
        return f"{n:.{decimals}f}"
    return display_text(s)


def first_existing(cols: Iterable[str], df: pd.DataFrame) -> Optional[str]:
    for c in cols:
        if c in df.columns:
            return c
    return None


def load_screening_data(market: str):
    """가능하면 원본 판정이 살아있는 _checked.tsv를 우선 로드한다.
    Streamlit Cloud에서 오래된 results 파일명이 cache에 남는 문제를 피하려고 cache를 쓰지 않는다.
    """
    m = market.lower()
    checked_files = sorted(glob.glob(f"results/{m}_screening_*_checked.tsv"), reverse=True)
    sorted_files = sorted(glob.glob(f"results/{m}_screening_*_sorted.tsv"), reverse=True)
    files = checked_files or sorted_files

    if not files:
        return None, None

    latest = files[0]
    df = pd.read_csv(latest, sep="\t", dtype=str, encoding="utf-8-sig").fillna("")

    # 종목코드는 문자열 6자리 유지. ="005930" 같은 표시용 래퍼 제거.
    if "종목코드" in df.columns:
        df["종목코드"] = df["종목코드"].map(clean_stock_code)

    return df, latest



def _missing_mask(s: pd.Series) -> pd.Series:
    return s.map(lambda x: clean_text(x) in {"", "-"})


def _choose_growth_series(df: pd.DataFrame, eps_basis: str) -> tuple[pd.Series, str]:
    if eps_basis != "Auto":
        col = EPS_BASIS_COL.get(eps_basis, "연간이익증가율(3년CAGR,%)")
        return num_series(df, col), eps_basis

    if "사용연성장률(%)" in df.columns:
        out = num_series(df, "사용연성장률(%)")
    else:
        out = pd.Series(np.nan, index=df.index)
    for label, col in [("3Y", "연간이익증가율(3년CAGR,%)"), ("5Y", "연간이익증가율(5년CAGR,%)"), ("1Y", "연간이익증가율(1년,%)")]:
        cand = num_series(df, col)
        m = out.isna() & cand.notna()
        out.loc[m] = cand.loc[m]
    return out, "Auto"


def _classify_lynch_ratio(x) -> str:
    v = to_num(x)
    if pd.isna(v):
        return "Not Available"
    if v <= 0.5:
        return "Very Attractive"
    if v < 1:
        return "Undervalued"
    if v < 2:
        return "Neutral"
    return "Unfavorable"


def _classify_dividend_score(x) -> str:
    v = to_num(x)
    if pd.isna(v):
        return "Not Available"
    if v >= 2:
        return "Strong (>=2)"
    if v >= 1.5:
        return "Positive (>=1.5)"
    if v >= 1:
        return "Neutral (1~1.5)"
    return "Weak (<1)"


def _hard_filter_from_values(df: pd.DataFrame) -> pd.Series:
    net_cash = num_series(df, "Net Cash / Share (Lynch-style)")
    fcf_col = first_existing(["FCF / Share", "FCF per Share", "FCF"], df)
    fcf = num_series(df, fcf_col) if fcf_col else pd.Series(np.nan, index=df.index)
    ex_pe = num_series(df, "순현금차감PER(린치식)")
    return (net_cash > 0) & (fcf > 0) & (ex_pe > 0)


def repair_derived_metrics(df: pd.DataFrame, eps_basis: str) -> pd.DataFrame:
    """Actions 결과 TSV에서 린치/배당감안 파생 컬럼이 비어 있을 때 대시보드에서 보정한다."""
    out = df.copy()

    if "순현금차감PER(린치식)" not in out.columns:
        out["순현금차감PER(린치식)"] = np.nan
    ex_pe = num_series(out, "순현금차감PER(린치식)")
    price = num_series(out, "현재가")
    eps = num_series(out, "EPS(FY2025)")
    net_cash = num_series(out, "Net Cash / Share (Lynch-style)")
    calc_ex_pe = (price - net_cash) / eps.replace(0, np.nan)
    m = ex_pe.isna() & calc_ex_pe.notna()
    out.loc[m, "순현금차감PER(린치식)"] = calc_ex_pe.loc[m]
    ex_pe = num_series(out, "순현금차감PER(린치식)")

    growth, _ = _choose_growth_series(out, eps_basis)
    div_yield = num_series(out, "Dividend Yield (%)")

    if "린치PER배수" not in out.columns:
        out["린치PER배수"] = np.nan
    ratio = num_series(out, "린치PER배수")
    calc_ratio = ex_pe / growth.replace(0, np.nan)
    calc_ratio = calc_ratio.where((ex_pe > 0) & (growth > 0))
    m = ratio.isna() & calc_ratio.notna()
    out.loc[m, "린치PER배수"] = calc_ratio.loc[m]

    if "배당감안점수" not in out.columns:
        out["배당감안점수"] = np.nan
    adj = num_series(out, "배당감안점수")
    calc_adj = (growth + div_yield.fillna(0)) / ex_pe.replace(0, np.nan)
    calc_adj = calc_adj.where((ex_pe > 0) & (growth > 0))
    m = adj.isna() & calc_adj.notna()
    out.loc[m, "배당감안점수"] = calc_adj.loc[m]

    if "린치PER판정" not in out.columns:
        out["린치PER판정"] = ""
    m = _missing_mask(out["린치PER판정"])
    out.loc[m, "린치PER판정"] = out.loc[m, "린치PER배수"].map(_classify_lynch_ratio)

    if "배당감안점수판정" not in out.columns:
        out["배당감안점수판정"] = ""
    m = _missing_mask(out["배당감안점수판정"])
    out.loc[m, "배당감안점수판정"] = out.loc[m, "배당감안점수"].map(_classify_dividend_score)

    if "사용연성장률(%)" not in out.columns:
        out["사용연성장률(%)"] = np.nan
    use_growth = num_series(out, "사용연성장률(%)")
    m = use_growth.isna() & growth.notna()
    out.loc[m, "사용연성장률(%)"] = growth.loc[m]

    if "사용연성장률기준" not in out.columns:
        out["사용연성장률기준"] = ""
    m = _missing_mask(out["사용연성장률기준"])
    out.loc[m, "사용연성장률기준"] = eps_basis

    if "종합판정" not in out.columns:
        out["종합판정"] = ""
    m = _missing_mask(out["종합판정"])
    hard = _hard_filter_from_values(out)
    ratio2 = num_series(out, "린치PER배수")
    adj2 = num_series(out, "배당감안점수")
    recovered = pd.Series("Hold / Review", index=out.index, dtype=object)
    recovered.loc[~hard] = "Excluded"
    recovered.loc[hard & (ratio2 <= 0.5) & (adj2 >= 2)] = "Very Attractive"
    recovered.loc[hard & (ratio2 < 1) & (adj2 >= 1.5) & (recovered != "Very Attractive")] = "Positive"
    recovered.loc[ratio2.isna() | adj2.isna()] = "Not Available"
    out.loc[m, "종합판정"] = recovered.loc[m]

    return out

def add_comparison_columns(df: pd.DataFrame, eps_basis: str, graham_basis: str) -> pd.DataFrame:
    out = repair_derived_metrics(df, eps_basis)

    eps_col = EPS_BASIS_COL.get(eps_basis, "연간이익증가율(3년CAGR,%)")
    graham_col = GRAHAM_BASIS_COL.get(graham_basis, "그레이엄괴리율(3년,%)")

    out["성장률 기준"] = eps_basis
    out["비교 EPS성장률(%)"] = num_series(out, eps_col)

    out["그레이엄 기준"] = graham_basis
    out["비교 그레이엄괴리율(%)"] = num_series(out, graham_col)

    return out


def unique_values(df: pd.DataFrame, col: str) -> list[str]:
    if col not in df.columns:
        return []
    vals: list[str] = []
    for v in df[col].tolist():
        s = clean_text(v)
        if s and s not in vals:
            vals.append(s)
    return vals


def checkbox_group(label: str, df: pd.DataFrame, col: str, key_prefix: str, *, expanded: bool = False) -> Optional[set[str]]:
    vals = unique_values(df, col)
    if not vals:
        st.caption(f"{label}: column not found")
        return None

    selected: set[str] = set()
    with st.expander(label, expanded=expanded):
        for v in vals:
            if st.checkbox(v, value=True, key=f"{key_prefix}_{v}"):
                selected.add(v)
    return selected


def apply_filters(
    df: pd.DataFrame,
    *,
    selected_overall: Optional[set[str]],
    selected_lynch: Optional[set[str]],
    selected_dividend: Optional[set[str]],
    require_net_cash: bool,
    require_fcf: bool,
    require_no_short_risky_debt: bool
) -> pd.DataFrame:
    out = df.copy()

    def apply_text_filter(col: str, selected: Optional[set[str]]):
        nonlocal out
        if not selected or col not in out.columns:
            return
        out = out[out[col].map(clean_text).isin(selected)]

    apply_text_filter("종합판정", selected_overall)
    apply_text_filter("린치PER판정", selected_lynch)
    apply_text_filter("배당감안점수판정", selected_dividend)

    if require_net_cash:
        out = out[num_series(out, "Net Cash / Share (Lynch-style)") > 0]

    if require_fcf:
        fcf_col = first_existing(["FCF / Share", "FCF per Share", "FCF"], out)
        if fcf_col:
            out = out[num_series(out, fcf_col) > 0]

    if require_no_short_risky_debt and "Short-term Risk Debt" in out.columns:
        risky = num_series(out, "Short-term Risk Debt")
        # 위험부채는 >0이면 제외. 0 또는 공란/미추출은 통과로 둔다.
        out = out[risky.isna() | (risky <= 0)]

    return out


def sort_dashboard(df: pd.DataFrame, sort_mode: str) -> pd.DataFrame:
    out = df.copy()
    sort_specs = SORT_MODE_SPECS.get(sort_mode, SORT_MODE_SPECS["Lynch-style ratio first (default)"])

    sort_cols = []
    ascending = []
    for col, asc in sort_specs:
        if col in out.columns:
            tmp = f"__sort_{col}"
            out[tmp] = num_series(out, col)
            sort_cols.append(tmp)
            ascending.append(asc)

    if sort_cols:
        out = out.sort_values(sort_cols, ascending=ascending, na_position="last")
        out = out.drop(columns=sort_cols)

    return out.reset_index(drop=True)


def without_timing(cols: Iterable[str]) -> list[str]:
    out = []
    for c in cols:
        if any(k in c for k in TIMING_KEYWORDS):
            continue
        out.append(c)
    return out


def present_table(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    existing = [c for c in cols if c in df.columns]
    out = df[existing].copy()
    if "종목코드" in out.columns:
        out["종목코드"] = out["종목코드"].map(clean_stock_code)

    numeric_like = [
        "현재가", "린치PER배수", "배당감안점수", "비교 EPS성장률(%)", "비교 그레이엄괴리율(%)",
        "Dividend Yield (%)", "Net Cash / Share (Lynch-style)", "FCF / Share", "Short-term Risk Debt",
        "순현금차감PER(린치식)", "그레이엄괴리율(선택,%)", "잉여현금흐름수익률(%)",
    ]
    for c in numeric_like:
        if c in out.columns:
            out[c] = out[c].map(lambda x: fmt(x, 2))

    for c in out.columns:
        if c in TEXT_EXACT_COLS or c not in numeric_like:
            out[c] = out[c].map(lambda x: display_text(clean_text(x) or "-"))
    out = out.rename(columns=DISPLAY_COLUMN_LABELS)
    return out


def chart_series(row: pd.Series, mapping: dict[str, str]) -> pd.DataFrame:
    records = []
    for label, col in mapping.items():
        value = to_num(row.get(col))
        if not pd.isna(value):
            records.append({"Metric": display_label(label), "Value": value})
    return pd.DataFrame(records)


def render_method_text():
    st.markdown(
        """
#### Lynch-style metrics
The dashboard compares net cash, free cash flow, growth, and price using Ex-Cash P/E based PEG / PEGY-style metrics.

Optional hard filters can exclude companies with negative net cash, negative FCF, or short-term risk debt.

#### Graham-style reference
The dashboard estimates a fair P/E, intrinsic value reference, and valuation gap using EPS and growth assumptions.

The output should be used as a screening reference, not as an investment recommendation.
        """
    )




def mini_card(title: str, value: object, caption: str = ""):
    st.markdown(
        f"""
<div class='mini-card'>
  <div class='mini-title'>{title}</div>
  <div class='mini-value'>{fmt(value)}</div>
  <div class='mini-caption'>{caption}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def sum_existing(row: pd.Series, cols: list[str]) -> float:
    vals = [to_num(row.get(c)) for c in cols]
    vals = [v for v in vals if not pd.isna(v)]
    if not vals:
        return np.nan
    return float(sum(vals))


def cash_debt_values(row: pd.Series) -> dict[str, float]:
    cash = to_num(row.get("Cash & Cash Equivalents"))
    securities = to_num(row.get("Marketable Securities"))
    cash_like = sum_existing(row, ["Cash & Cash Equivalents", "Marketable Securities"])
    long_debt = to_num(row.get("Long-term Debt"))
    short_risky = to_num(row.get("Short-term Risk Debt"))
    long_debt_zero = 0.0 if pd.isna(long_debt) else long_debt
    short_risky_zero = 0.0 if pd.isna(short_risky) else short_risky
    cash_like_zero = 0.0 if pd.isna(cash_like) else cash_like
    debt_total = long_debt_zero + short_risky_zero
    return {
        "Cash & Cash Equivalents": cash,
        "Marketable Securities": securities,
        "현금성자산합계": cash_like,
        "Long-term Debt": long_debt,
        "Short-term Risk Debt": short_risky,
        "부채합계_장기+단기위험": debt_total if debt_total != 0 else np.nan,
        "순현금_린치식": cash_like_zero - long_debt_zero if not pd.isna(cash_like) else np.nan,
        "순현금_보수형": cash_like_zero - long_debt_zero - short_risky_zero if not pd.isna(cash_like) else np.nan,
        "현금성자산_부채커버": cash_like_zero / debt_total if debt_total > 0 else np.nan,
    }


def render_cash_debt_summary(row: pd.Series):
    vals = cash_debt_values(row)
    st.markdown("#### Cash-like Assets / Debt Structure")
    st.caption("Cash-like assets = cash & cash equivalents + marketable securities. Debt is separated into long-term debt and short-term risk debt.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cash-like Assets", fmt(vals["현금성자산합계"]))
    c2.metric("Long-term Debt", fmt(vals["Long-term Debt"]))
    c3.metric("Short-term Risk Debt", fmt(vals["Short-term Risk Debt"]))
    c4.metric("Conservative Net Cash", fmt(vals["순현금_보수형"]))

    chart_rows = []
    for label, key in [
        ("Cash-like Assets", "현금성자산합계"),
        ("Long-term Debt", "Long-term Debt"),
        ("Short-term Risk Debt", "Short-term Risk Debt"),
        ("Long-term + Short-term Risk Debt", "부채합계_장기+단기위험"),
    ]:
        v = vals.get(key)
        if not pd.isna(v):
            chart_rows.append({"Item": label, "Value": v})
    if chart_rows:
        st.bar_chart(pd.DataFrame(chart_rows).set_index("Metric"))

    table_rows = [
        {"Category": "Cash-like Assets", "Item": "Cash & Cash Equivalents", "Value": fmt(vals["Cash & Cash Equivalents"], 0), "Interpretation": "Most direct cash item"},
        {"Category": "Cash-like Assets", "Item": "Marketable Securities", "Value": fmt(vals["Marketable Securities"], 0), "Interpretation": "Liquid financial assets"},
        {"Category": "Debt", "Item": "Long-term Debt", "Value": fmt(vals["Long-term Debt"], 0), "Interpretation": "Subtracted in Lynch-style net cash calculation"},
        {"Category": "Debt", "Item": "Short-term Risk Debt", "Value": fmt(vals["Short-term Risk Debt"], 0), "Interpretation": "Interpreted as a separate risk signal if present"},
        {"Category": "Net Cash", "Item": "Lynch-style Net Cash", "Value": fmt(vals["순현금_린치식"], 0), "Interpretation": "Cash-like assets - long-term debt"},
        {"Category": "Net Cash", "Item": "Conservative Net Cash", "Value": fmt(vals["순현금_보수형"], 0), "Interpretation": "Cash-like assets - long-term debt - short-term risk debt"},
    ]
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)


def render_short_risky_debt_detail(row: pd.Series):
    st.markdown("#### Short-term Risk Debt Interpretation")
    total = to_num(row.get("Short-term Risk Debt"))
    if pd.isna(total) or total <= 0:
        st.success("Short-term risk debt is zero or blank in the current TSV output.")
    else:
        st.warning(f"Short-term risk debt is recorded as {fmt(total, 0)}. The source TSV does not split this into detailed sub-items, so the dashboard shows the total value.")

    rows = [
        {"Category": "Bank-like short-term funding", "Candidate Item": "Short-term borrowings", "Dashboard Display": "May be included in total", "Notes": "1년 내 상환 부담"},
        {"Category": "Bank-like short-term funding", "Candidate Item": "Current borrowings", "Dashboard Display": "May be included in total", "Notes": "유동성으로 분류된 차입"},
        {"Category": "어음/CP 계열", "Candidate Item": "Commercial paper", "Dashboard Display": "May be included in total", "Notes": "린치가 경계한 단기성 조달 취지에 가까움"},
        {"Category": "어음/CP 계열", "Candidate Item": "Trade bills", "Dashboard Display": "May be included in total", "Notes": "단기 상환 압박 가능"},
        {"Category": "시장성 단기조달", "Candidate Item": "Short-term electronic bonds", "Dashboard Display": "May be included in total", "Notes": "한국 공시 실무 확장 항목"},
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=210)
    st.caption("To inspect detailed sub-items, the original screener should export short-term borrowings, current borrowings, commercial paper, trade bills, and short-term electronic bonds as separate columns.")


def sector_note(row: pd.Series) -> str:
    group = clean_text(row.get("그룹"))
    fit = clean_text(row.get("판정구분"))
    adj_type = clean_text(row.get("업종보정유형"))
    adj_judge = clean_text(row.get("업종보정판정"))
    parts = []
    if fit and fit != "메인":
        parts.append(f"Classification is '{display_text(fit)}', so the Lynch-style standalone signal should be interpreted with lower weight.")
    if adj_type or adj_judge:
        parts.append(f"Sector adjustment: {display_text(adj_type) or '-'} / {display_text(adj_judge) or '-'}")
    if any(k in group for k in ["금융", "은행", "증권", "보험"]):
        parts.append("Financial companies have balance-sheet structures that differ from manufacturers, so cash, debt, Ex-Cash P/E, and FCF filters can be distorted.")
    elif any(k in group for k in ["통신", "유틸", "전력", "에너지", "철강", "석유", "화학", "조선"]):
        parts.append("Capital-intensive sectors require sector-aware interpretation of debt, CAPEX, and FCF cycles.")
    elif group:
        parts.append("For general operating companies, net cash, FCF, and growth-to-price metrics can be interpreted more directly.")
    return " ".join(parts) if parts else "Sector interpretation data is limited."


def business_hint(row: pd.Series) -> str:
    name = clean_text(row.get("종목명"))
    group = clean_text(row.get("그룹"))
    raw_group = clean_text(row.get("원본그룹"))
    known = {
        "현대오토에버": "Hyundai AutoEver is related to IT services, vehicle software, and mobility platforms within Hyundai Motor Group.",
        "HL만도": "HL Mando is an auto-parts company focused on braking, steering, suspension, and electronic systems.",
        "SK하이닉스": "SK hynix is a memory semiconductor company focused on DRAM and NAND.",
        "삼성전자": "Samsung Electronics is a diversified electronics company spanning semiconductors, smartphones, and consumer electronics.",
        "제룡전기": "Jeryong Electric is related to power equipment such as transformers.",
        "이수페타시스": "Isu Petasys is related to multilayer PCBs for telecom equipment and AI server infrastructure.",
        "동아쏘시오홀딩스": "Dong-A Socio Holdings is a holding company with pharma, bio, and logistics subsidiaries.",
    }
    for k, v in known.items():
        if k in name:
            extra = f" Display group: {display_text(group)}." if group else ""
            return v + extra

    if group in {"기타/확인필요", ""}:
        return "The source TSV does not include a business description column. Check DART filings for more details."

    raw = " The original group was 'Manually Added'; the dashboard inferred a display group." if raw_group == "직접추가" else ""
    return f"Displayed as a {display_text(group)} company.{raw}"


def dart_search_url(name: str) -> str:
    # API 키 없이도 브라우저에서 DART 회사명 검색 페이지를 열 수 있다.
    return "https://dart.fss.or.kr/dsab007/main.do?textCrpNm=" + quote_plus(clean_text(name))


def hankyung_consensus_url(code: str) -> str:
    code = clean_stock_code(code)
    return f"https://markets.hankyung.com/stock/{code}/consensus"


def naver_finance_url(code: str) -> str:
    code = clean_stock_code(code)
    return f"https://finance.naver.com/item/main.naver?code={code}"


def naver_research_company_list_url() -> str:
    # 네이버 금융 리서치 > 종목분석 리포트 목록
    return "https://finance.naver.com/research/company_list.naver"


def google_pdf_report_search_url(name: str, code: str) -> str:
    # 종목 관련 PDF 리포트만 최대한 잡히도록 종목명/코드/filetype을 함께 사용한다.
    q = f"{company_query_name(name)} {clean_stock_code(code)} 기업분석 리포트 증권사 filetype:pdf"
    return "https://www.google.com/search?q=" + quote_plus(q)


def kind_report_search_url(name: str, code: str) -> str:
    # KRX KIND 내부검색 딥링크가 안정적이지 않아 Google site 검색으로 연결한다.
    q = f"site:kind.krx.co.kr {company_query_name(name)} {clean_stock_code(code)} 기업분석보고서"
    return "https://www.google.com/search?q=" + quote_plus(q)


def fnguide_url(code: str) -> str:
    code = clean_stock_code(code)
    return f"https://comp.fnguide.com/SVO2/ASP/SVD_Main.asp?gicode=A{code}"


def fnguide_consensus_url(code: str) -> str:
    code = clean_stock_code(code)
    return f"https://comp.fnguide.com/SVO2/ASP/SVD_Consensus.asp?gicode=A{code}"


def render_copy_code_button(code: str):
    code = clean_stock_code(code)
    if not code:
        return
    components.html(
        f"""
        <div style="display:flex; gap:8px; align-items:center; margin: 2px 0 10px 0;">
          <code id="stock-code-copy" style="font-size:16px; padding:6px 10px; border-radius:8px; background:#111827; color:#e5e7eb;">{code}</code>
          <button onclick="navigator.clipboard.writeText('{code}'); this.innerText='Copied'; setTimeout(()=>this.innerText='Copy Ticker', 1200);"
             style="padding:6px 10px; border-radius:8px; border:1px solid #4b5563; background:#1f2937; color:#e5e7eb; cursor:pointer;">Copy Ticker</button>
        </div>
        """,
        height=44,
    )


def render_company_overview(row: pd.Series):
    name = clean_text(row.get("종목명"))
    group = clean_text(row.get("그룹")) or "-"
    fit = clean_text(row.get("판정구분")) or "-"
    st.markdown("#### Company / Sector Overview")
    st.markdown(
        f"""
<div class='hint-box'>
  <div class='hint-title'>{name} · {group} · 판정구분 {fit}</div>
  <div class='hint-body'>{business_hint(row)}</div>
</div>
""",
        unsafe_allow_html=True,
    )
    if name:
        code = clean_text(row.get("종목코드"))
        st.markdown("**Disclosure / Research Links**")
        b1, b2, b3, b4 = st.columns([1, 1, 1, 1])
        with b1:
            st.link_button("DART Disclosure", dart_search_url(name), use_container_width=True)
        with b2:
            st.link_button("FnGuide Snapshot", fnguide_url(code), use_container_width=True)
        with b3:
            st.link_button("FnGuide Consensus", fnguide_consensus_url(code), use_container_width=True)
        with b4:
            st.link_button("Hankyung Consensus", hankyung_consensus_url(code), use_container_width=True)

        b5, b6, b7, b8 = st.columns([1, 1, 1, 1])
        with b5:
            st.link_button("Naver Finance", naver_finance_url(code), use_container_width=True)
        with b6:
            st.link_button("Naver Research List", naver_research_company_list_url(), use_container_width=True)
        with b7:
            st.link_button("Google PDF Report Search", google_pdf_report_search_url(name, code), use_container_width=True)
        with b8:
            st.link_button("KRX KIND Report Search", kind_report_search_url(name, code), use_container_width=True)


def render_sector_guidance(row: pd.Series):
    st.markdown("#### Sector Interpretation Notes")
    st.info(sector_note(row))


def render_method_legend_compact():
    with st.expander("Metric Guide", expanded=False):
        st.markdown(
            """
- **Lynch-style Ratio\***: **Ex-Cash PEG (Custom)**. `<= 0.5 = Very Attractive`, `< 1 = Undervalued`.
- **Dividend-adjusted Score\***: **Ex-Cash PEGY Score (Custom)**. `>= 2.0 = Strong`, `>= 1.5 = Positive`.
- A Lynch-style ratio displayed as **0.00** may be a very small rounded value or may indicate that net cash is close to the current price. Check Ex-Cash P/E in the detail panel.
            """
        )

def render_visuals(row: pd.Series):
    st.markdown("#### Visual Summary")
    v1, v2 = st.columns(2)

    with v1:
        st.markdown("**EPS Growth Comparison**")
        growth_df = chart_series(row, {
            "1Y": "연간이익증가율(1년,%)",
            "3년 CAGR": "연간이익증가율(3년CAGR,%)",
            "5년 CAGR": "연간이익증가율(5년CAGR,%)",
        })
        if growth_df.empty:
            st.caption("No EPS growth data available for display.")
        else:
            st.bar_chart(growth_df.set_index("Metric"))

    with v2:
        st.markdown("**Graham Gap Comparison**")
        graham_df = chart_series(row, {
            "1Y": "그레이엄괴리율(1년,%)",
            "3Y": "그레이엄괴리율(3년,%)",
            "5Y": "그레이엄괴리율(5년,%)",
            "Selected": "그레이엄괴리율(선택,%)",
        })
        if graham_df.empty:
            st.caption("No Graham gap data available for display.")
        else:
            st.bar_chart(graham_df.set_index("Metric"))

    v3, v4 = st.columns(2)
    with v3:
        st.markdown("**Cash-like Assets / Debt Structure**")
        bs_df = chart_series(row, {
            "Cash & Cash Equivalents": "Cash & Cash Equivalents",
            "Marketable Securities": "Marketable Securities",
            "Long-term Debt": "Long-term Debt",
            "Short-term Risk Debt": "Short-term Risk Debt",
            "주주지분": "주주지분",
            "총부채": "총부채",
        })
        if bs_df.empty:
            st.caption("No balance sheet data available for display.")
        else:
            st.bar_chart(bs_df.set_index("Metric"))

    with v4:
        st.markdown("**Per-share Metrics / Yields**")
        per_share_df = chart_series(row, {
            "Net Cash / Share (Lynch-style)": "Net Cash / Share (Lynch-style)",
            "Net Cash / Share (Conservative)": "Net Cash / Share (Conservative)",
            "FCF / Share": "FCF / Share",
            "Dividend Yield (%)": "Dividend Yield (%)",
            "FCF Yield (%)": "잉여현금흐름수익률(%)",
        })
        if per_share_df.empty:
            st.caption("No per-share metric data available for display.")
        else:
            st.bar_chart(per_share_df.set_index("Metric"))


def render_financial_table(row: pd.Series):
    st.markdown("#### Source Financial Values / Detailed Metrics")
    st.caption("Source values and calculated metrics are separated below. Scroll the tables if needed.")

    raw_cols = [
        "현재가", "EPS(FY2025)", "현금배당금(FY2025 DPS)",
        "Cash & Cash Equivalents", "Marketable Securities", "Long-term Debt", "Short-term Risk Debt",
        "주주지분", "총부채", "발행주식수",
    ]
    calc_cols = [
        "Net Cash / Share (Lynch-style)", "Net Cash / Share (Conservative)",
        "순현금차감PER(린치식)", "순현금차감PER(보수형)",
        "FCF / Share", "잉여현금흐름수익률(%)", "Dividend Yield (%)",
        "연간이익증가율(1년,%)", "연간이익증가율(3년CAGR,%)", "연간이익증가율(5년CAGR,%)",
        "그레이엄적정PER(선택)", "그레이엄내재가치(선택)", "그레이엄괴리율(선택,%)",
    ]

    def make_rows(cols):
        return pd.DataFrame([
            {"Item": display_label(c), "Value": fmt(row.get(c), 4)} for c in cols if c in row.index
        ])

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Source Financial Values**")
        raw_df = make_rows(raw_cols)
        if not raw_df.empty:
            st.dataframe(raw_df, use_container_width=True, hide_index=True, height=360)
    with c2:
        st.markdown("**Calculated Metrics**")
        calc_df = make_rows(calc_cols)
        if not calc_df.empty:
            st.dataframe(calc_df, use_container_width=True, hide_index=True, height=360)


def render_detail(row: pd.Series, show_excash_pe: bool):
    st.markdown("---")
    name = clean_text(row.get("종목명"))
    code = clean_stock_code(row.get("종목코드"))
    st.markdown(f"### Company Detail: {name} ({code})")
    render_copy_code_button(code)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        mini_card("Overall Signal (with filter)", row.get("종합판정"), f"Classification: {fmt(row.get('판정구분'))}")
    with c2:
        mini_card("Lynch-style Ratio*", row.get("린치PER배수"), "Ex-Cash PEG Custom · <= 0.5 Very Attractive / < 1 Undervalued")
    with c3:
        mini_card("Dividend-adjusted Score*", row.get("배당감안점수"), "Ex-Cash PEGY Score Custom · >= 2.0 Strong / >= 1.5 Positive")
    with c4:
        mini_card("Graham Gap for Comparison", row.get("비교 그레이엄괴리율(%)"), f"Basis: {fmt(row.get('그레이엄 기준'))}")

    render_method_legend_compact()

    render_company_overview(row)

    left, mid, right = st.columns([1.0, 1.0, 1.0])

    with left:
        st.markdown("#### Basic Info")
        base_rows = [
            ("종목코드", clean_stock_code(row.get("종목코드"))),
            ("종목명", clean_text(row.get("종목명"))),
            ("그룹", clean_text(row.get("그룹"))),
            ("판정구분", fmt(row.get("판정구분"))),
            ("Short-term Risk Debt", fmt(row.get("Short-term Risk Debt"))),
        ]
        st.dataframe(pd.DataFrame(base_rows, columns=["Item", "Value"]), use_container_width=True, hide_index=True, height=250)

    with mid:
        st.markdown("#### Lynch-style Metrics")
        lynch_rows = [
            ("린치PER판정*", fmt(row.get("린치PER판정"))),
            ("사용연성장률기준", fmt(row.get("사용연성장률기준"))),
            ("사용연성장률(%)", fmt(row.get("사용연성장률(%)"))),
            ("배당감안점수판정*", fmt(row.get("배당감안점수판정"))),
            ("Dividend Yield (%)", fmt(row.get("Dividend Yield (%)"))),
            ("FCF Yield (%)", fmt(row.get("잉여현금흐름수익률(%)"))),
        ]
        if show_excash_pe:
            lynch_rows += [
                ("순현금차감PER(린치식)", fmt(row.get("순현금차감PER(린치식)"))),
                ("순현금차감PER(보수형)", fmt(row.get("순현금차감PER(보수형)"))),
            ]
        st.dataframe(pd.DataFrame(lynch_rows, columns=["Item", "Value"]), use_container_width=True, hide_index=True, height=250)

    with right:
        st.markdown("#### Graham-style Metrics")
        graham_rows = [
            ("그레이엄사용기준", fmt(row.get("그레이엄사용기준"))),
            ("그레이엄 괴리율 기준", fmt(row.get("그레이엄 기준"))),
            ("1년 괴리율", fmt(row.get("그레이엄괴리율(1년,%)"))),
            ("3년 괴리율", fmt(row.get("그레이엄괴리율(3년,%)"))),
            ("5년 괴리율", fmt(row.get("그레이엄괴리율(5년,%)"))),
            ("선택 괴리율", fmt(row.get("그레이엄괴리율(선택,%)"))),
        ]
        st.dataframe(pd.DataFrame(graham_rows, columns=["Item", "Value"]), use_container_width=True, hide_index=True, height=250)

    render_cash_debt_summary(row)

    v1, v2 = st.columns(2)
    with v1:
        st.markdown("#### EPS Growth Comparison")
        growth_df = chart_series(row, {
            "1Y": "연간이익증가율(1년,%)",
            "3년 CAGR": "연간이익증가율(3년CAGR,%)",
            "5년 CAGR": "연간이익증가율(5년CAGR,%)",
        })
        if growth_df.empty:
            st.caption("No EPS growth data available for display.")
        else:
            st.bar_chart(growth_df.set_index("Metric"))
    with v2:
        st.markdown("#### Graham Gap Comparison")
        graham_df = chart_series(row, {
            "1Y": "그레이엄괴리율(1년,%)",
            "3Y": "그레이엄괴리율(3년,%)",
            "5Y": "그레이엄괴리율(5년,%)",
            "Selected": "그레이엄괴리율(선택,%)",
        })
        if graham_df.empty:
            st.caption("No Graham gap data available for display.")
        else:
            st.bar_chart(graham_df.set_index("Metric"))

    render_financial_table(row)

    notes = []
    for col in ["종합판정사유", "하드필터사유", "Notes"]:
        s = clean_text(row.get(col))
        if s:
            notes.append((col, s))
    if notes:
        with st.expander("Notes / Reasons", expanded=True):
            for col, s in notes:
                st.markdown(f"**{col}**")
                st.markdown(f"<div class='warning-box'>{s}</div>", unsafe_allow_html=True)


def dataframe_with_optional_selection(table: pd.DataFrame):
    """표 왼쪽 체크박스로 상세 종목을 선택한다.
    Streamlit 행 클릭 지원 여부에 의존하지 않도록 data_editor 체크박스 컬럼을 사용한다.
    """
    work = table.copy()
    current_idx = int(st.session_state.get("detail_idx", 0)) if len(work) else 0
    current_idx = max(0, min(current_idx, len(work) - 1)) if len(work) else 0
    work.insert(0, "Select", False)
    if len(work):
        work.loc[current_idx, "Select"] = True

    disabled_cols = [c for c in work.columns if c != "Select"]
    column_config = {
        "Select": st.column_config.CheckboxColumn("Detail", width="small"),
        "Rank": st.column_config.NumberColumn(width="small"),
        "Ticker": st.column_config.TextColumn(width="small"),
        "Company": st.column_config.TextColumn(width="medium"),
        "Group": st.column_config.TextColumn(width="medium"),
    }

    edited = st.data_editor(
        work,
        use_container_width=True,
        height=470,
        hide_index=True,
        disabled=disabled_cols,
        column_config=column_config,
        key="ranking_table_editor",
    )

    try:
        selected_rows = edited.index[edited["Select"] == True].tolist()
        if selected_rows:
            return int(selected_rows[-1])
    except Exception:
        return None
    return None


def main():
    st.markdown("# Fundamental Screening Dashboard")
    st.markdown(
        "<div class='small-muted'>기본 판정은 3년 기준을 중심으로 보고, 탐색용으로 1년·3년·5년·자동 기준을 바꿔 비교합니다.</div>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("## Dashboard Settings")
        market = st.radio("Market", options=["KOSPI", "KOSDAQ"], horizontal=True)

    df, latest_file = load_screening_data(market)
    if df is not None:
        df = enrich_display_groups(df)
    if df is None:
        st.warning(f"{market} screening data was not found.")
        st.code("results/kospi_screening_YYYYMMDD_checked.tsv or results/kospi_screening_YYYYMMDD_sorted.tsv")
        return

    with st.sidebar:
        st.markdown("---")
        st.markdown("### Exception Filters")
        require_net_cash = st.checkbox("Net Cash / Share (Lynch-style) > 0", value=False)
        require_fcf = st.checkbox("FCF / Share > 0", value=False)
        require_no_short_risky_debt = st.checkbox("No short-term risk debt (0 or blank)", value=False)

        st.markdown("---")
        st.markdown("### Display Options")
        show_reason_cols = st.checkbox("Show notes / reason columns", value=False)
        show_excash_pe = st.checkbox("Show Ex-Cash P/E", value=False)

        st.markdown("---")
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        with st.expander("Metric / Exception Filter Guide", expanded=False):
            render_method_text()
            st.markdown("""
---
**Short-term risk debt items**

The screener treats short-term borrowings, current borrowings, commercial paper, trade bills, and short-term electronic bonds as short-term risk debt. If the value is greater than zero, it is interpreted as a separate liquidity risk signal.

**Sectors where negative net cash or negative FCF require context**

- **Financials / Banks / Insurance / Securities**: deposits, insurance liabilities, and leverage are part of the business model. Capital adequacy, loss ratio, NIM, provisions, and ROE should be checked together.
- **Telecom / Utilities / Power / Energy Infrastructure**: infrastructure CAPEX, regulated pricing, long-term contracts, and investment cycles can distort FCF and debt metrics.
- **Steel / Chemicals / Refining / Shipbuilding / Construction**: working capital, inventory, order cycles, and CAPEX cycles can make FCF and net cash volatile.
- **Semiconductors / Batteries and other expansion-heavy sectors**: FCF can be temporarily negative during investment phases, so debt burden and future profitability should be reviewed together.
            """)

    st.markdown("### Signal Filters")
    st.caption("Signals are filters, not ranking rules. If nothing is selected, all rows are shown.")

    # Actions 결과에서 파생 판정 컬럼이 비어 있을 수 있어, 필터 옵션도 3년 기준으로 1차 복구해서 만든다.
    filter_option_df = repair_derived_metrics(df, "3Y")

    f1, f2, f3 = st.columns(3)
    with f1:
        selected_overall = set(st.multiselect("Overall Signal", unique_values(filter_option_df, "종합판정"), default=[], placeholder="All", format_func=display_text))
    with f2:
        selected_lynch = set(st.multiselect("Lynch-style Signal* (Ex-Cash PEG)", unique_values(filter_option_df, "린치PER판정"), default=[], placeholder="All", format_func=display_text))
    with f3:
        selected_dividend = set(st.multiselect("Dividend-adjusted Signal* (Ex-Cash PEGY)", unique_values(filter_option_df, "배당감안점수판정"), default=[], placeholder="All", format_func=display_text))

    st.markdown("---")
    st.markdown(f"### {market} Screening Ranking")
    st.caption("Default sorting: lower Lynch-style ratio → higher dividend-adjusted score → higher selected EPS growth → higher selected Graham gap.")

    ctrl1, ctrl2, ctrl3 = st.columns([1, 1, 1.2])
    with ctrl1:
        eps_basis = st.selectbox("EPS Growth Basis", ["1Y", "3Y", "5Y", "Auto"], index=1)
    with ctrl2:
        graham_basis = st.selectbox("Graham Gap Basis", ["1Y", "3Y", "5Y", "Auto"], index=1)
    with ctrl3:
        sort_mode = st.selectbox("Sorting Priority", list(SORT_MODE_SPECS.keys()), index=0)

    st.markdown(
        f"<div class='info-box'>Current basis: EPS growth <b>{eps_basis}</b> / Graham gap <b>{graham_basis}</b> / sorting <b>{sort_mode}</b> / data <b>{Path(str(latest_file)).name if latest_file else '-'}</b></div>",
        unsafe_allow_html=True,
    )

    working_df = add_comparison_columns(df, eps_basis, graham_basis)
    filtered_df = apply_filters(
        working_df,
        selected_overall=selected_overall,
        selected_lynch=selected_lynch,
        selected_dividend=selected_dividend,
        require_net_cash=require_net_cash,
        require_fcf=require_fcf,
        require_no_short_risky_debt=require_no_short_risky_debt,
    )
    ranked_df = sort_dashboard(filtered_df, sort_mode)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📊 Total Companies", len(df))
    c2.metric("✅ Displayed Companies", len(ranked_df))
    latest_path = Path(str(latest_file)) if latest_file else None
    if latest_path is not None and latest_path.exists():
        update_datetime = datetime.fromtimestamp(latest_path.stat().st_mtime).strftime("%m-%d %H:%M")
    else:
        update_datetime = "Check file update"
    c3.metric("🕐 Last Update", update_datetime)
    c4.metric("🏭 Group Count", df["그룹"].nunique() if "그룹" in df.columns else 0)

    if ranked_df.empty:
        st.warning("No companies match the current filters. Relax the signal filters or exception filters.")
        return

    display_df = ranked_df.copy().reset_index(drop=True)
    display_df.insert(0, "순위", range(1, len(display_df) + 1))

    display_cols = [
        "순위", "종목코드", "종목명", "그룹", "판정구분",
        "종합판정", "린치PER배수", "린치PER판정", "배당감안점수", "배당감안점수판정",
        "성장률 기준", "비교 EPS성장률(%)", "그레이엄 기준", "비교 그레이엄괴리율(%)",
        "Dividend Yield (%)", "Net Cash / Share (Lynch-style)", "FCF / Share", "Short-term Risk Debt",
    ]

    if show_excash_pe:
        display_cols += ["순현금차감PER(린치식)"]
    if show_reason_cols:
        display_cols += ["하드필터사유", "종합판정사유", "Notes"]

    display_cols = without_timing(display_cols)
    table = present_table(display_df, display_cols)
    table = table.rename(columns={
        "Overall Signal": "Overall Signal (with filter)",
        "Lynch-style Ratio*": "Lynch-style Ratio*",
        "Lynch-style Signal*": "Lynch-style Signal* (Ex-Cash PEG)",
        "Dividend-adjusted Score*": "Dividend-adjusted Score*",
        "Dividend-adjusted Signal*": "Dividend-adjusted Signal* (Ex-Cash PEGY)",
        "EPS Growth Basis": "EPS Growth Basis",
        "EPS Growth for Comparison (%)": "EPS Growth for Comparison (%)",
        "Graham Gap Basis": "Graham Gap Basis",
        "Graham Gap for Comparison (%)": "Graham Gap for Comparison (%)",
    })

    clicked_pos = dataframe_with_optional_selection(table)
    if "detail_idx" not in st.session_state:
        st.session_state["detail_idx"] = 0
    if clicked_pos is not None and 0 <= clicked_pos < len(display_df):
        st.session_state["detail_idx"] = int(clicked_pos)

    selected_idx = max(0, min(int(st.session_state.get("detail_idx", 0)), len(display_df) - 1))
    selected_row = display_df.iloc[selected_idx]
    st.caption("Select the detail checkbox on the left side of the table to update the detail panel below.")
    render_detail(selected_row, show_excash_pe=show_excash_pe)

    st.markdown("---")
    st.caption("This dashboard is for educational, research, and software engineering portfolio purposes only. It is not financial advice or an investment recommendation.")


if __name__ == "__main__":
    main()
