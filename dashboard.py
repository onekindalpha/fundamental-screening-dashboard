#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
피터린치 + 그레이엄 투자 스크리닝 대시보드

핵심 설계
- 판정값(종합판정 / 린치PER판정 / 배당감안점수판정 / 하드필터통과)은 정렬 기준이 아니라 메인 테이블 위 필터 옵션으로 선택한다.
- 기본 비교 기준은 3년이다.
- 탐색용으로 EPS 성장률과 그레이엄 괴리율은 1년 / 3년 / 5년 / 자동 기준을 선택해 재정렬할 수 있다.
- 타이밍 컬럼과 섹터 필터는 대시보드에서 제외한다.
- 상세 화면은 표 왼쪽 체크박스로 선택된 종목을 카드/표/차트로 요약한다.
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
    page_title="피터린치 + 그레이엄 대시보드",
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
    "1년": "연간이익증가율(1년,%)",
    "3년": "연간이익증가율(3년CAGR,%)",
    "5년": "연간이익증가율(5년CAGR,%)",
    "자동": "사용연성장률(%)",
}

GRAHAM_BASIS_COL = {
    "1년": "그레이엄괴리율(1년,%)",
    "3년": "그레이엄괴리율(3년,%)",
    "5년": "그레이엄괴리율(5년,%)",
    "자동": "그레이엄괴리율(선택,%)",
}

SORT_MODE_SPECS = {
    "린치 우선(기본)": [
        ("린치PER배수", True),
        ("배당감안점수", False),
        ("비교 EPS성장률(%)", False),
        ("비교 그레이엄괴리율(%)", False),
    ],
    "EPS성장률 우선": [
        ("비교 EPS성장률(%)", False),
        ("린치PER배수", True),
        ("배당감안점수", False),
        ("비교 그레이엄괴리율(%)", False),
    ],
    "그레이엄괴리율 우선": [
        ("비교 그레이엄괴리율(%)", False),
        ("린치PER배수", True),
        ("배당감안점수", False),
        ("비교 EPS성장률(%)", False),
    ],
    "배당감안점수 우선": [
        ("배당감안점수", False),
        ("린치PER배수", True),
        ("비교 EPS성장률(%)", False),
        ("비교 그레이엄괴리율(%)", False),
    ],
}

TEXT_EXACT_COLS = {
    "종목코드", "종목명", "그룹", "판정구분", "비고",
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
    return s


def first_existing(cols: Iterable[str], df: pd.DataFrame) -> Optional[str]:
    for c in cols:
        if c in df.columns:
            return c
    return None


@st.cache_data(show_spinner=False)
def load_screening_data(market: str):
    """가능하면 원본 판정이 살아있는 _checked.tsv를 우선 로드한다."""
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


def add_comparison_columns(df: pd.DataFrame, eps_basis: str, graham_basis: str) -> pd.DataFrame:
    out = df.copy()

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
        st.caption(f"{label}: 해당 컬럼 없음")
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
        out = out[num_series(out, "주당순현금(린치식)") > 0]

    if require_fcf:
        fcf_col = first_existing(["주당잉여현금흐름", "FCF per Share", "FCF"], out)
        if fcf_col:
            out = out[num_series(out, fcf_col) > 0]

    if require_no_short_risky_debt and "단기위험부채" in out.columns:
        risky = num_series(out, "단기위험부채")
        # 위험부채는 >0이면 제외. 0 또는 공란/미추출은 통과로 둔다.
        out = out[risky.isna() | (risky <= 0)]

    return out


def sort_dashboard(df: pd.DataFrame, sort_mode: str) -> pd.DataFrame:
    out = df.copy()
    sort_specs = SORT_MODE_SPECS.get(sort_mode, SORT_MODE_SPECS["린치 우선(기본)"])

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
        "배당수익률(%)", "주당순현금(린치식)", "주당잉여현금흐름", "단기위험부채",
        "순현금차감PER(린치식)", "그레이엄괴리율(선택,%)", "잉여현금흐름수익률(%)",
    ]
    for c in numeric_like:
        if c in out.columns:
            out[c] = out[c].map(lambda x: fmt(x, 2))

    for c in out.columns:
        if c in TEXT_EXACT_COLS or c not in numeric_like:
            out[c] = out[c].map(lambda x: clean_text(x) or "-")
    return out


def chart_series(row: pd.Series, mapping: dict[str, str]) -> pd.DataFrame:
    records = []
    for label, col in mapping.items():
        value = to_num(row.get(col))
        if not pd.isna(value):
            records.append({"항목": label, "값": value})
    return pd.DataFrame(records)


def render_method_text():
    st.markdown(
        """
#### 피터 린치
순현금·FCF·성장성을 함께 보고, **Ex-Cash P/E 기반 PEG·PEGY**로 성장 대비 가격 매력을 평가합니다.  
단, **순현금 음수 / FCF 음수 / 단기위험부채 존재** 종목은 하드필터로 제외할 수 있습니다.

#### 벤저민 그레이엄
EPS와 성장률로 **적정PER·내재가치·괴리율**을 계산해 현재가의 저평가 가능성을 봅니다.  
우선순위는 **EPS 성장률(기본 3년 CAGR)**과 **그레이엄 괴리율**이 큰 순으로 참고할 수 있습니다.
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
    cash = to_num(row.get("현금및현금성자산"))
    securities = to_num(row.get("유가증권성자산"))
    cash_like = sum_existing(row, ["현금및현금성자산", "유가증권성자산"])
    long_debt = to_num(row.get("장기부채"))
    short_risky = to_num(row.get("단기위험부채"))
    long_debt_zero = 0.0 if pd.isna(long_debt) else long_debt
    short_risky_zero = 0.0 if pd.isna(short_risky) else short_risky
    cash_like_zero = 0.0 if pd.isna(cash_like) else cash_like
    debt_total = long_debt_zero + short_risky_zero
    return {
        "현금및현금성자산": cash,
        "유가증권성자산": securities,
        "현금성자산합계": cash_like,
        "장기부채": long_debt,
        "단기위험부채": short_risky,
        "부채합계_장기+단기위험": debt_total if debt_total != 0 else np.nan,
        "순현금_린치식": cash_like_zero - long_debt_zero if not pd.isna(cash_like) else np.nan,
        "순현금_보수형": cash_like_zero - long_debt_zero - short_risky_zero if not pd.isna(cash_like) else np.nan,
        "현금성자산_부채커버": cash_like_zero / debt_total if debt_total > 0 else np.nan,
    }


def render_cash_debt_summary(row: pd.Series):
    vals = cash_debt_values(row)
    st.markdown("#### 현금성 자산 / 부채 구조")
    st.caption("현금성자산합계 = 현금및현금성자산 + 유가증권성자산. 부채는 장기부채와 단기위험부채를 분리해 봅니다.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("현금성자산 합계", fmt(vals["현금성자산합계"]))
    c2.metric("장기부채", fmt(vals["장기부채"]))
    c3.metric("단기위험부채", fmt(vals["단기위험부채"]))
    c4.metric("보수형 순현금", fmt(vals["순현금_보수형"]))

    chart_rows = []
    for label, key in [
        ("현금성자산 합계", "현금성자산합계"),
        ("장기부채", "장기부채"),
        ("단기위험부채", "단기위험부채"),
        ("장기+단기위험부채", "부채합계_장기+단기위험"),
    ]:
        v = vals.get(key)
        if not pd.isna(v):
            chart_rows.append({"항목": label, "값": v})
    if chart_rows:
        st.bar_chart(pd.DataFrame(chart_rows).set_index("항목"))

    table_rows = [
        {"구분": "현금성자산", "항목": "현금및현금성자산", "값": fmt(vals["현금및현금성자산"], 0), "해석": "가장 직접적인 현금"},
        {"구분": "현금성자산", "항목": "유가증권성자산", "값": fmt(vals["유가증권성자산"], 0), "해석": "현금화 가능한 금융자산"},
        {"구분": "부채", "항목": "장기부채", "값": fmt(vals["장기부채"], 0), "해석": "린치식 순현금 계산에서 차감"},
        {"구분": "부채", "항목": "단기위험부채", "값": fmt(vals["단기위험부채"], 0), "해석": "있으면 별도 위험 신호로 봄"},
        {"구분": "순현금", "항목": "린치식 순현금", "값": fmt(vals["순현금_린치식"], 0), "해석": "현금성자산 - 장기부채"},
        {"구분": "순현금", "항목": "보수형 순현금", "값": fmt(vals["순현금_보수형"], 0), "해석": "현금성자산 - 장기부채 - 단기위험부채"},
    ]
    st.dataframe(pd.DataFrame(table_rows), width="stretch", hide_index=True)


def render_short_risky_debt_detail(row: pd.Series):
    st.markdown("#### 단기위험부채 해석")
    total = to_num(row.get("단기위험부채"))
    if pd.isna(total) or total <= 0:
        st.success("이 종목은 현재 TSV 기준 단기위험부채가 0 또는 공란으로 표시됩니다.")
    else:
        st.warning(f"단기위험부채 총액이 {fmt(total, 0)}로 잡혀 있습니다. 원천 TSV에는 세부 항목별 금액이 분리되어 있지 않아 총액 기준으로 표시합니다.")

    rows = [
        {"구분": "은행성 단기조달", "후보 항목": "단기차입금", "대시보드 표시": "총액에 포함 가능", "비고": "1년 내 상환 부담"},
        {"구분": "은행성 단기조달", "후보 항목": "유동차입금", "대시보드 표시": "총액에 포함 가능", "비고": "유동성으로 분류된 차입"},
        {"구분": "어음/CP 계열", "후보 항목": "기업어음", "대시보드 표시": "총액에 포함 가능", "비고": "린치가 경계한 단기성 조달 취지에 가까움"},
        {"구분": "어음/CP 계열", "후보 항목": "상업어음", "대시보드 표시": "총액에 포함 가능", "비고": "단기 상환 압박 가능"},
        {"구분": "시장성 단기조달", "후보 항목": "전자단기사채", "대시보드 표시": "총액에 포함 가능", "비고": "한국 공시 실무 확장 항목"},
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=210)
    st.caption("세부 항목별 금액까지 보려면 스크리너 원본에서 단기차입금/유동차입금/기업어음/상업어음/전자단기사채를 각각 별도 컬럼으로 출력해야 합니다.")


def sector_note(row: pd.Series) -> str:
    group = clean_text(row.get("그룹"))
    fit = clean_text(row.get("판정구분"))
    adj_type = clean_text(row.get("업종보정유형"))
    adj_judge = clean_text(row.get("업종보정판정"))
    parts = []
    if fit and fit != "메인":
        parts.append(f"판정구분이 '{fit}'이므로 린치식 단독판정 비중을 낮춰 보는 편이 안전합니다.")
    if adj_type or adj_judge:
        parts.append(f"업종보정: {adj_type or '-'} / {adj_judge or '-'}")
    if any(k in group for k in ["금융", "은행", "증권", "보험"]):
        parts.append("금융주는 현금·부채 구조가 일반 제조업과 달라 Ex-Cash P/E·FCF 필터를 그대로 적용하면 왜곡될 수 있습니다.")
    elif any(k in group for k in ["통신", "유틸", "전력", "에너지", "철강", "석유", "화학", "조선"]):
        parts.append("자본집약 업종은 부채와 CAPEX가 구조적으로 크므로 FCF와 부채 필터를 업종 평균과 함께 봐야 합니다.")
    elif group:
        parts.append("일반 업종은 순현금·FCF·성장 대비 가격 매력을 비교적 직관적으로 적용할 수 있습니다.")
    return " ".join(parts) if parts else "업종 해석 정보가 부족합니다."



def business_hint(row: pd.Series) -> str:
    name = clean_text(row.get("종목명"))
    group = clean_text(row.get("그룹"))
    raw_group = clean_text(row.get("원본그룹"))
    known = {
        "현대오토에버": "현대차그룹의 IT서비스·차량 소프트웨어·모빌리티 플랫폼 관련 기업입니다.",
        "HL만도": "자동차 부품, 제동·조향·현가장치 및 전장 부품 관련 기업입니다.",
        "SK하이닉스": "DRAM·NAND 중심의 메모리 반도체 기업입니다.",
        "삼성전자": "반도체·스마트폰·가전 등 종합 전자 기업입니다.",
        "제룡전기": "변압기 등 전력기기 관련 기업입니다.",
        "이수페타시스": "고다층 PCB, 통신장비·AI 서버 기판 관련 기업입니다.",
        "동아쏘시오홀딩스": "동아쏘시오그룹 지주회사로 제약·바이오·물류 등 계열사를 보유합니다.",
    }
    for k, v in known.items():
        if k in name:
            extra = f" 표시 업종: {group}." if group else ""
            return v + extra

    if group in {"기타/확인필요", ""}:
        return "원본 TSV에 사업설명 컬럼이 없어 회사 설명은 제한적입니다. DART 사업보고서와 함께 확인하세요."

    raw = f" 원본 그룹은 '{raw_group}'이었고, 대시보드 표시용으로 업종을 추정했습니다." if raw_group == "직접추가" else ""
    return f"{group} 성격의 기업으로 분류해 표시합니다.{raw}"


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
          <button onclick="navigator.clipboard.writeText('{code}'); this.innerText='복사됨'; setTimeout(()=>this.innerText='종목코드 복사', 1200);"
             style="padding:6px 10px; border-radius:8px; border:1px solid #4b5563; background:#1f2937; color:#e5e7eb; cursor:pointer;">종목코드 복사</button>
        </div>
        """,
        height=44,
    )


def render_company_overview(row: pd.Series):
    name = clean_text(row.get("종목명"))
    group = clean_text(row.get("그룹")) or "-"
    fit = clean_text(row.get("판정구분")) or "-"
    st.markdown("#### 회사 / 업종 요약")
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
        st.markdown("**공시 / 종목 리포트 바로가기**")
        b1, b2, b3, b4 = st.columns([1, 1, 1, 1])
        with b1:
            st.link_button("DART 공시", dart_search_url(name), width="stretch")
        with b2:
            st.link_button("FnGuide Snapshot", fnguide_url(code), width="stretch")
        with b3:
            st.link_button("FnGuide Consensus", fnguide_consensus_url(code), width="stretch")
        with b4:
            st.link_button("한경컨센서스", hankyung_consensus_url(code), width="stretch")

        b5, b6, b7, b8 = st.columns([1, 1, 1, 1])
        with b5:
            st.link_button("네이버 종목", naver_finance_url(code), width="stretch")
        with b6:
            st.link_button("네이버 리서치 목록", naver_research_company_list_url(), width="stretch")
        with b7:
            st.link_button("Google PDF 리포트 검색", google_pdf_report_search_url(name, code), width="stretch")
        with b8:
            st.link_button("KRX KIND 보고서 검색", kind_report_search_url(name, code), width="stretch")


def render_sector_guidance(row: pd.Series):
    st.markdown("#### 업종별 해석 메모")
    st.info(sector_note(row))


def render_method_legend_compact():
    with st.expander("지표 기준 설명", expanded=False):
        st.markdown(
            """
- **린치PER배수\***: **Ex-Cash PEG (Custom)**. `0.5 이하 = 매우 유망`, `1 미만 = 헐값`.
- **배당감안점수\***: **Ex-Cash PEGY Score (Custom)**. `2.0 이상 = 강한 편`, `1.5 이상 = 양호`.
- **0.00처럼 보이는 린치PER배수**는 실제 값이 매우 작아서 반올림됐거나, 순현금이 주가에 거의 근접한 경우일 수 있습니다. 상세에서는 순현금차감PER를 같이 확인하세요.
            """
        )

def render_visuals(row: pd.Series):
    st.markdown("#### 시각 요약")
    v1, v2 = st.columns(2)

    with v1:
        st.markdown("**EPS 성장률 비교**")
        growth_df = chart_series(row, {
            "1년": "연간이익증가율(1년,%)",
            "3년 CAGR": "연간이익증가율(3년CAGR,%)",
            "5년 CAGR": "연간이익증가율(5년CAGR,%)",
        })
        if growth_df.empty:
            st.caption("표시 가능한 EPS 성장률 데이터가 없습니다.")
        else:
            st.bar_chart(growth_df.set_index("항목"))

    with v2:
        st.markdown("**그레이엄 괴리율 비교**")
        graham_df = chart_series(row, {
            "1년": "그레이엄괴리율(1년,%)",
            "3년": "그레이엄괴리율(3년,%)",
            "5년": "그레이엄괴리율(5년,%)",
            "선택": "그레이엄괴리율(선택,%)",
        })
        if graham_df.empty:
            st.caption("표시 가능한 그레이엄 괴리율 데이터가 없습니다.")
        else:
            st.bar_chart(graham_df.set_index("항목"))

    v3, v4 = st.columns(2)
    with v3:
        st.markdown("**현금성 자산 / 부채 구조**")
        bs_df = chart_series(row, {
            "현금및현금성자산": "현금및현금성자산",
            "유가증권성자산": "유가증권성자산",
            "장기부채": "장기부채",
            "단기위험부채": "단기위험부채",
            "주주지분": "주주지분",
            "총부채": "총부채",
        })
        if bs_df.empty:
            st.caption("표시 가능한 재무상태표 데이터가 없습니다.")
        else:
            st.bar_chart(bs_df.set_index("항목"))

    with v4:
        st.markdown("**주당 지표 / 수익률**")
        per_share_df = chart_series(row, {
            "주당순현금(린치식)": "주당순현금(린치식)",
            "주당순현금(보수형)": "주당순현금(보수형)",
            "주당잉여현금흐름": "주당잉여현금흐름",
            "배당수익률(%)": "배당수익률(%)",
            "FCF수익률(%)": "잉여현금흐름수익률(%)",
        })
        if per_share_df.empty:
            st.caption("표시 가능한 주당 지표 데이터가 없습니다.")
        else:
            st.bar_chart(per_share_df.set_index("항목"))


def render_financial_table(row: pd.Series):
    st.markdown("#### 재무 원천값 / 상세 지표")
    st.caption("원천 재무값과 계산 지표를 나눠서 봅니다. 표가 길면 스크롤해서 확인하세요.")

    raw_cols = [
        "현재가", "EPS(FY2025)", "현금배당금(FY2025 DPS)",
        "현금및현금성자산", "유가증권성자산", "장기부채", "단기위험부채",
        "주주지분", "총부채", "발행주식수",
    ]
    calc_cols = [
        "주당순현금(린치식)", "주당순현금(보수형)",
        "순현금차감PER(린치식)", "순현금차감PER(보수형)",
        "주당잉여현금흐름", "잉여현금흐름수익률(%)", "배당수익률(%)",
        "연간이익증가율(1년,%)", "연간이익증가율(3년CAGR,%)", "연간이익증가율(5년CAGR,%)",
        "그레이엄적정PER(선택)", "그레이엄내재가치(선택)", "그레이엄괴리율(선택,%)",
    ]

    def make_rows(cols):
        return pd.DataFrame([
            {"항목": c, "값": fmt(row.get(c), 4)} for c in cols if c in row.index
        ])

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**원천 재무값**")
        raw_df = make_rows(raw_cols)
        if not raw_df.empty:
            st.dataframe(raw_df, width="stretch", hide_index=True, height=360)
    with c2:
        st.markdown("**계산 지표**")
        calc_df = make_rows(calc_cols)
        if not calc_df.empty:
            st.dataframe(calc_df, width="stretch", hide_index=True, height=360)


def render_detail(row: pd.Series, show_excash_pe: bool):
    st.markdown("---")
    name = clean_text(row.get("종목명"))
    code = clean_stock_code(row.get("종목코드"))
    st.markdown(f"### 🔎 선택 종목 상세: {name} ({code})")
    render_copy_code_button(code)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        mini_card("종합판정 (with filter)", row.get("종합판정"), f"판정구분: {fmt(row.get('판정구분'))}")
    with c2:
        mini_card("린치PER배수*", row.get("린치PER배수"), "Ex-Cash PEG Custom · 0.5 이하 매우 유망 / 1 미만 헐값")
    with c3:
        mini_card("배당감안점수*", row.get("배당감안점수"), "Ex-Cash PEGY Score Custom · 2.0 이상 강한 편 / 1.5 이상 양호")
    with c4:
        mini_card("비교 그레이엄괴리율", row.get("비교 그레이엄괴리율(%)"), f"비교 기준: {fmt(row.get('그레이엄 기준'))}")

    render_method_legend_compact()

    render_company_overview(row)

    left, mid, right = st.columns([1.0, 1.0, 1.0])

    with left:
        st.markdown("#### 기본")
        base_rows = [
            ("종목코드", clean_stock_code(row.get("종목코드"))),
            ("종목명", clean_text(row.get("종목명"))),
            ("그룹", clean_text(row.get("그룹"))),
            ("판정구분", fmt(row.get("판정구분"))),
            ("단기위험부채", fmt(row.get("단기위험부채"))),
        ]
        st.dataframe(pd.DataFrame(base_rows, columns=["항목", "값"]), width="stretch", hide_index=True, height=250)

    with mid:
        st.markdown("#### 린치")
        lynch_rows = [
            ("린치PER판정*", fmt(row.get("린치PER판정"))),
            ("사용연성장률기준", fmt(row.get("사용연성장률기준"))),
            ("사용연성장률(%)", fmt(row.get("사용연성장률(%)"))),
            ("배당감안점수판정*", fmt(row.get("배당감안점수판정"))),
            ("배당수익률(%)", fmt(row.get("배당수익률(%)"))),
            ("FCF수익률(%)", fmt(row.get("잉여현금흐름수익률(%)"))),
        ]
        if show_excash_pe:
            lynch_rows += [
                ("순현금차감PER(린치식)", fmt(row.get("순현금차감PER(린치식)"))),
                ("순현금차감PER(보수형)", fmt(row.get("순현금차감PER(보수형)"))),
            ]
        st.dataframe(pd.DataFrame(lynch_rows, columns=["항목", "값"]), width="stretch", hide_index=True, height=250)

    with right:
        st.markdown("#### 그레이엄")
        graham_rows = [
            ("그레이엄사용기준", fmt(row.get("그레이엄사용기준"))),
            ("그레이엄 괴리율 기준", fmt(row.get("그레이엄 기준"))),
            ("1년 괴리율", fmt(row.get("그레이엄괴리율(1년,%)"))),
            ("3년 괴리율", fmt(row.get("그레이엄괴리율(3년,%)"))),
            ("5년 괴리율", fmt(row.get("그레이엄괴리율(5년,%)"))),
            ("선택 괴리율", fmt(row.get("그레이엄괴리율(선택,%)"))),
        ]
        st.dataframe(pd.DataFrame(graham_rows, columns=["항목", "값"]), width="stretch", hide_index=True, height=250)

    render_cash_debt_summary(row)

    v1, v2 = st.columns(2)
    with v1:
        st.markdown("#### EPS 성장률 비교")
        growth_df = chart_series(row, {
            "1년": "연간이익증가율(1년,%)",
            "3년 CAGR": "연간이익증가율(3년CAGR,%)",
            "5년 CAGR": "연간이익증가율(5년CAGR,%)",
        })
        if growth_df.empty:
            st.caption("표시 가능한 EPS 성장률 데이터가 없습니다.")
        else:
            st.bar_chart(growth_df.set_index("항목"))
    with v2:
        st.markdown("#### 그레이엄 괴리율 비교")
        graham_df = chart_series(row, {
            "1년": "그레이엄괴리율(1년,%)",
            "3년": "그레이엄괴리율(3년,%)",
            "5년": "그레이엄괴리율(5년,%)",
            "선택": "그레이엄괴리율(선택,%)",
        })
        if graham_df.empty:
            st.caption("표시 가능한 그레이엄 괴리율 데이터가 없습니다.")
        else:
            st.bar_chart(graham_df.set_index("항목"))

    render_financial_table(row)

    notes = []
    for col in ["종합판정사유", "하드필터사유", "비고"]:
        s = clean_text(row.get(col))
        if s:
            notes.append((col, s))
    if notes:
        with st.expander("비고 / 사유", expanded=True):
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
    work.insert(0, "선택", False)
    if len(work):
        work.loc[current_idx, "선택"] = True

    disabled_cols = [c for c in work.columns if c != "선택"]
    column_config = {
        "선택": st.column_config.CheckboxColumn("상세", width="small"),
        "순위": st.column_config.NumberColumn(width="small"),
        "종목코드": st.column_config.TextColumn(width="small"),
        "종목명": st.column_config.TextColumn(width="medium"),
        "그룹": st.column_config.TextColumn(width="medium"),
    }

    edited = st.data_editor(
        work,
        width="stretch",
        height=470,
        hide_index=True,
        disabled=disabled_cols,
        column_config=column_config,
        key="ranking_table_editor",
    )

    try:
        selected_rows = edited.index[edited["선택"] == True].tolist()
        if selected_rows:
            return int(selected_rows[-1])
    except Exception:
        return None
    return None


def main():
    st.markdown("# 📈 피터린치 + 그레이엄 투자 스크리닝 대시보드")
    st.markdown(
        "<div class='small-muted'>기본 판정은 3년 기준을 중심으로 보고, 탐색용으로 1년·3년·5년·자동 기준을 바꿔 비교합니다.</div>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("## 🎯 대시보드 설정")
        market = st.radio("시장 선택", options=["KOSPI", "KOSDAQ"], horizontal=True)

    df, latest_file = load_screening_data(market)
    if df is not None:
        df = enrich_display_groups(df)
    if df is None:
        st.warning(f"{market} 스크리닝 데이터를 찾을 수 없습니다.")
        st.code("results/kospi_screening_YYYYMMDD_checked.tsv 또는 results/kospi_screening_YYYYMMDD_sorted.tsv")
        return

    with st.sidebar:
        st.markdown("---")
        st.markdown("### 예외 필터")
        require_net_cash = st.checkbox("주당순현금(린치식) > 0", value=False)
        require_fcf = st.checkbox("주당잉여현금흐름 > 0", value=False)
        require_no_short_risky_debt = st.checkbox("단기위험부채 없음 (0 또는 공란)", value=False)

        st.markdown("---")
        st.markdown("### 표시 옵션")
        show_reason_cols = st.checkbox("비고/사유 열 함께 보기", value=False)
        show_excash_pe = st.checkbox("순현금차감PER 표시", value=False)

        st.markdown("---")
        if st.button("🔄 새로고침", width="stretch"):
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        with st.expander("🔎 지표/예외 필터 해석", expanded=False):
            render_method_text()
            st.markdown("""
---
**단기위험부채로 보는 항목**  
단기차입금, 유동차입금, 기업어음, 상업어음, 전자단기사채를 총액으로 묶어 봅니다. `> 0`이면 단기 차환·상환 부담이 있다는 뜻이라 별도 주의 신호로 봅니다.

**주당순현금 음수 / FCF 음수를 감안해서 볼 수 있는 업종**
- **금융·은행·보험·증권**: 예금, 보험부채, 레버리지 자체가 영업모델의 일부라 제조업식 순현금 기준이 왜곡될 수 있습니다. 이 경우 순현금보다 자본적정성, 손해율, NIM, 충당금, ROE를 같이 봐야 합니다.
- **통신·유틸리티·전력·에너지 인프라**: 네트워크·발전설비·인프라 투자가 커서 구조적으로 부채와 감가상각이 큽니다. FCF가 특정 연도에 약해도 요금규제, 장기계약, 설비투자 사이클을 같이 봐야 합니다.
- **철강·화학·정유·조선·건설 등 자본집약/사이클 업종**: 재고, 운전자본, 수주·CAPEX 사이클 때문에 FCF와 순현금이 크게 흔들릴 수 있습니다. 업황 저점/고점과 부채 만기구조를 같이 확인해야 합니다.
- **반도체·2차전지처럼 대규모 증설 업종**: 성장투자 구간에서는 FCF 음수가 일시적으로 나올 수 있습니다. 다만 증설이 수익성으로 연결되는지와 차입 부담을 같이 봐야 합니다.

            """)

    st.markdown("### 판정 필터")
    st.caption("판정은 정렬이 아니라 필터입니다. 아무것도 선택하지 않으면 전체를 보여줍니다.")

    f1, f2, f3 = st.columns(3)
    with f1:
        selected_overall = set(st.multiselect("종합판정 (with filter)", unique_values(df, "종합판정"), default=[], placeholder="전체"))
    with f2:
        selected_lynch = set(st.multiselect("린치PER판정* (Ex-Cash PEG)", unique_values(df, "린치PER판정"), default=[], placeholder="전체"))
    with f3:
        selected_dividend = set(st.multiselect("배당감안판정* (Ex-Cash PEGY)", unique_values(df, "배당감안점수판정"), default=[], placeholder="전체"))

    st.markdown("---")
    st.markdown(f"### {market} 유망주 랭킹")
    st.caption("정렬: 린치PER배수 낮은순 → 배당감안점수 높은순 → 선택 EPS성장률 높은순 → 선택 그레이엄괴리율 높은순이 기본입니다.")

    ctrl1, ctrl2, ctrl3 = st.columns([1, 1, 1.2])
    with ctrl1:
        eps_basis = st.selectbox("EPS 성장률 기준", ["1년", "3년", "5년", "자동"], index=1)
    with ctrl2:
        graham_basis = st.selectbox("그레이엄 괴리율 기준", ["1년", "3년", "5년", "자동"], index=1)
    with ctrl3:
        sort_mode = st.selectbox("정렬 우선 방식", list(SORT_MODE_SPECS.keys()), index=0)

    st.markdown(
        f"<div class='info-box'>현재 기준: EPS성장률 <b>{eps_basis}</b> / 그레이엄괴리율 <b>{graham_basis}</b> / 정렬 <b>{sort_mode}</b> / 데이터 <b>{Path(latest_file).name}</b></div>",
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
    c1.metric("📊 전체 종목 수", len(df))
    c2.metric("✅ 현재 표시 종목 수", len(ranked_df))
    update_datetime = datetime.fromtimestamp(Path(latest_file).stat().st_mtime).strftime("%m-%d %H:%M")
    c3.metric("🕐 마지막 업데이트", update_datetime)
    c4.metric("🏭 그룹 수", df["그룹"].nunique() if "그룹" in df.columns else 0)

    if ranked_df.empty:
        st.warning("필터 조건에 맞는 종목이 없습니다. 판정 필터 또는 예외 필터를 완화해보세요.")
        return

    display_df = ranked_df.copy().reset_index(drop=True)
    display_df.insert(0, "순위", range(1, len(display_df) + 1))

    display_cols = [
        "순위", "종목코드", "종목명", "그룹", "판정구분",
        "종합판정", "린치PER배수", "린치PER판정", "배당감안점수", "배당감안점수판정",
        "성장률 기준", "비교 EPS성장률(%)", "그레이엄 기준", "비교 그레이엄괴리율(%)",
        "배당수익률(%)", "주당순현금(린치식)", "주당잉여현금흐름", "단기위험부채",
    ]

    if show_excash_pe:
        display_cols += ["순현금차감PER(린치식)"]
    if show_reason_cols:
        display_cols += ["하드필터사유", "종합판정사유", "비고"]

    display_cols = without_timing(display_cols)
    table = present_table(display_df, display_cols)
    table = table.rename(columns={
        "종합판정": "종합판정 (with filter)",
        "린치PER배수": "린치PER배수*",
        "린치PER판정": "린치PER판정* (Ex-Cash PEG)",
        "배당감안점수": "배당감안점수*",
        "배당감안점수판정": "배당감안판정* (Ex-Cash PEGY)",
        "성장률 기준": "EPS 성장률 기준",
        "비교 EPS성장률(%)": "비교 EPS성장률(%)",
        "그레이엄 기준": "그레이엄 괴리율 기준",
        "비교 그레이엄괴리율(%)": "비교 그레이엄괴리율(%)",
    })

    clicked_pos = dataframe_with_optional_selection(table)
    if "detail_idx" not in st.session_state:
        st.session_state["detail_idx"] = 0
    if clicked_pos is not None and 0 <= clicked_pos < len(display_df):
        st.session_state["detail_idx"] = int(clicked_pos)

    selected_idx = max(0, min(int(st.session_state.get("detail_idx", 0)), len(display_df) - 1))
    selected_row = display_df.iloc[selected_idx]
    st.caption("표 왼쪽의 상세 체크박스를 선택하면 아래 상세가 해당 종목으로 바뀝니다.")
    render_detail(selected_row, show_excash_pe=show_excash_pe)

    st.markdown("---")
    st.caption("이 대시보드는 정보 제공용이며 투자 판단은 본인 책임입니다.")


if __name__ == "__main__":
    main()
