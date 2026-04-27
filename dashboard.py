#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
피터린치 + 그레이엄 투자 스크리닝 대시보드

특징:
- KOSPI / KOSDAQ 탭 분리
- 정렬: Lynch P/E ↑ → 배당감안점수 ↓ → 영업이익증가율 ↓ → Graham 괴리율 ↓
- 필터링: 주당순현금, FCF, 단기부채, 하드웨어 여부
- 기업 클릭 → Google Sheets 상세 데이터 보기
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import glob
from datetime import datetime
import webbrowser

# 페이지 설정
st.set_page_config(
    page_title="📈 투자 스크리닝 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일링
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    .highlight {
        background-color: #fff0f5;
        padding: 10px;
        border-radius: 5px;
        border-left: 4px solid #ff1493;
    }
    .success {
        background-color: #f0fff4;
        border-left: 4px solid #22c55e;
    }
    .warning {
        background-color: #fef3c7;
        border-left: 4px solid #f59e0b;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_screening_data(market: str):
    """스크리닝 데이터 로드"""
    pattern = f"results/{market.lower()}_screening_*_sorted.tsv"
    files = sorted(glob.glob(pattern), reverse=True)

    if not files:
        return None, None

    latest_file = files[0]
    df = pd.read_csv(latest_file, sep='\t', dtype=str)

    # 수치형 변환
    numeric_cols = {}
    for col in df.columns:
        if col not in ['종목코드', '종목명', '그룹', '비고', '보유선전문가']:
            try:
                df[col] = pd.to_numeric(df[col].str.replace(',', ''), errors='coerce')
                numeric_cols[col] = True
            except:
                pass

    return df, latest_file

def safe_float(val):
    """안전한 float 변환"""
    try:
        if pd.isna(val) or val == '' or val == 'nan':
            return np.nan
        return float(str(val).replace(',', ''))
    except:
        return np.nan

def apply_filters(df, filters: dict):
    """필터 적용"""
    filtered_df = df.copy()

    # 음수 값 제외 필터 (피터린치 스타일)
    if filters['exclude_negative']:
        exclude_mask = pd.Series([True] * len(filtered_df), index=filtered_df.index)

        # 주당순현금 < 0 제외
        for col in filtered_df.columns:
            if '주당순현금' in col:
                filtered_df[col] = pd.to_numeric(filtered_df[col], errors='coerce')
                exclude_mask &= (filtered_df[col] >= 0)

        # FCF < 0 제외
        for col in filtered_df.columns:
            if 'FCF' in col or '자유현금' in col:
                filtered_df[col] = pd.to_numeric(filtered_df[col], errors='coerce')
                exclude_mask &= (filtered_df[col] >= 0)

        # 단기부채 < 0 제외
        for col in filtered_df.columns:
            if '단기' in col and '부채' in col:
                filtered_df[col] = pd.to_numeric(filtered_df[col], errors='coerce')
                exclude_mask &= (filtered_df[col] >= 0)

        filtered_df = filtered_df[exclude_mask]

    # 하드웨어 필터
    if filters['hardware'] != '전체':
        for col in filtered_df.columns:
            if '하드웨어' in col:
                if filters['hardware'] == 'Yes':
                    filtered_df = filtered_df[filtered_df[col] == 'Y']
                elif filters['hardware'] == 'No':
                    filtered_df = filtered_df[filtered_df[col] == 'N']

    return filtered_df

def format_number(val, decimals=2):
    """숫자 포매팅"""
    try:
        val = safe_float(val)
        if pd.isna(val):
            return '-'
        if abs(val) >= 1000:
            return f"{val:,.0f}"
        return f"{val:.{decimals}f}"
    except:
        return str(val)

def main():
    # 헤더
    st.markdown("# 📈 피터린치 + 그레이엄 투자 스크리닝 대시보드")
    st.markdown("---")

    # 사이드바: 시장 선택 및 필터
    with st.sidebar:
        st.markdown("## 🎯 필터 설정")

        # 시장 선택
        market = st.radio(
            "시장 선택",
            options=['KOSPI', 'KOSDAQ'],
            horizontal=True
        )

        st.markdown("---")
        st.markdown("### 필터링 옵션")

        # 필터 옵션 토글
        st.markdown("#### 🎯 피터린치 스타일 필터")

        exclude_negative = st.checkbox(
            '음수 값 제외하기',
            value=True,
            help='주당순현금, FCF, 단기부채 중 음수인 기업 제외\n(산업 특성상 음수인 기업도 포함하려면 해제)'
        )

        if exclude_negative:
            st.info("""
            ✅ **다음 기업들이 제외됩니다:**
            - 주당순현금 < 0
            - FCF < 0
            - 단기부채 < 0
            """)
        else:
            st.warning("""
            ⚠️ **모든 기업 포함됩니다**
            - 음수 값도 함께 표시됩니다
            - 비고에서 위험 신호 확인하세요
            """)

        st.markdown("---")

        # 필터 설정
        filters = {
            'exclude_negative': exclude_negative,
            'min_cash': 0,  # 기본값
            'min_fcf': 0,   # 기본값
            'min_short_debt': 0,  # 기본값
            'hardware': st.selectbox(
                '하드웨어',
                options=['전체', 'Yes', 'No'],
                help='Y: 하드웨어 관련 기업'
            )
        }

        st.markdown("---")
        st.markdown("### 📊 데이터 갱신")
        if st.button('🔄 새로고침', use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        st.markdown("### 📌 설정 가이드")
        st.info("""
        **피터린치 스타일:**
        - P/E 배수가 낮을수록 좋음
        - 배당금 지급하는 기업 선호
        - 영업이익 증가세 확인

        **그레이엄 스타일:**
        - 내재가치 대비 괴리율 낮음
        - 안정적인 현금 흐름
        """)

    # 메인 콘텐츠
    df, latest_file = load_screening_data(market)

    if df is None:
        st.warning(f"⚠️ {market} 스크리닝 데이터를 찾을 수 없습니다.")
        st.info("GitHub Actions를 통해 스크리닝을 실행한 후 다시 시도해주세요.")
        return

    # 데이터 정보
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 총 종목 수", len(df))
    with col2:
        update_time = Path(latest_file).stat().st_mtime
        update_datetime = datetime.fromtimestamp(update_time).strftime('%m-%d %H:%M')
        st.metric("🕐 마지막 업데이트", update_datetime)
    with col3:
        groups = df['그룹'].nunique() if '그룹' in df.columns else 0
        st.metric("🏭 섹터 수", groups)
    with col4:
        st.metric("🎯 필터 적용", "준비중")

    st.markdown("---")

    # 필터 적용
    filtered_df = apply_filters(df, filters)

    st.markdown(f"### {market} 유망주 랭킹")
    st.markdown(f"**총 {len(filtered_df)}개 종목** (필터 적용 후)")

    # 테이블 표시
    if len(filtered_df) > 0:
        # 표시할 컬럼 선택
        display_cols = ['순위', '종목코드', '종목명', '그룹']

        for col in filtered_df.columns:
            if 'Lynch' in col or 'P/E' in col:
                display_cols.append(col)
            elif '배당' in col:
                display_cols.append(col)
            elif '영업이익' in col and '증가' in col:
                display_cols.append(col)
            elif '그레이엄' in col and '괴리' in col:
                display_cols.append(col)

        display_cols.append('비고')

        # 실제 존재하는 컬럼만 필터링
        display_cols = [col for col in display_cols if col in filtered_df.columns or col == '순위']

        # 순위 추가
        display_df = filtered_df.reset_index(drop=True).copy()
        display_df.insert(0, '순위', range(1, len(display_df) + 1))

        # Streamlit 테이블로 표시
        st.dataframe(
            display_df[display_cols],
            use_container_width=True,
            height=400,
            column_config={
                '종목코드': st.column_config.TextColumn(width=80),
                '종목명': st.column_config.TextColumn(width=150),
                '순위': st.column_config.NumberColumn(width=50),
            }
        )

        # 선택된 기업 상세 정보
        st.markdown("---")
        st.markdown("### 🔍 기업 상세 정보")

        selected_company = st.selectbox(
            "기업을 선택하세요",
            options=display_df['종목명'].tolist(),
            key='company_select'
        )

        if selected_company:
            company_data = display_df[display_df['종목명'] == selected_company].iloc[0]

            # 회사 정보 카드
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"**종목명:** {company_data['종목명']}")
                st.markdown(f"**종목코드:** {company_data['종목코드']}")
            with col2:
                if '그룹' in company_data:
                    st.markdown(f"**섹터:** {company_data['그룹']}")
            with col3:
                if '순위' in company_data:
                    st.markdown(f"**순위:** {int(company_data['순위'])}")

            st.markdown("---")

            # 주요 지표
            st.markdown("#### 📊 주요 투자 지표")
            metric_cols = st.columns(4)

            metric_idx = 0
            for col in display_df.columns:
                if col in display_cols and col not in ['순위', '종목코드', '종목명', '그룹', '비고']:
                    val = company_data[col]
                    with metric_cols[metric_idx % 4]:
                        st.metric(
                            col,
                            format_number(val)
                        )
                    metric_idx += 1

            # 비고
            if '비고' in company_data and company_data['비고']:
                st.markdown("#### ⚠️ 주의사항")
                st.markdown(f"""
                <div class="warning">
                    {company_data['비고']}
                </div>
                """, unsafe_allow_html=True)

            # Google Sheets 연동 (예시)
            st.markdown("#### 📋 상세 재무제표")
            st.info(f"""
            해당 기업의 상세 재무제표를 보려면 Google Sheets를 통해 확인할 수 있습니다.

            **준비 예정:**
            - Google Sheets API 연동
            - 종목별 상세 재무 데이터
            - 차트 및 추이 분석
            """)

    else:
        st.warning("필터 조건에 맞는 종목이 없습니다.")

    # 푸터
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #888; padding: 20px;">
        📈 피터린치 + 그레이엄 투자 스크리닝 대시보드 v1.0<br>
        매일 자동으로 업데이트됩니다 (오전/정오/저녁)<br>
        <small>투자는 본인의 책임입니다. 항상 분석 후 결정하세요.</small>
    </div>
    """, unsafe_allow_html=True)

if __name__ == '__main__':
    main()
