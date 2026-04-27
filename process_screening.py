#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
스크리닝 결과를 정렬하고 필터링하는 스크립트

정렬 순서:
1. Lynch P/E 배수 (오름차순)
2. 배당감안점수 (내림차순)
3. 연간영업이익증가율(3년) (내림차순)
4. 그레이엄 괴리율(3년) (내림차순)

필터링 로직:
- 주당순현금 음수: 비고에 표시
- FCF 음수: 비고에 표시
- 단기위험부채: 별도 필터 (종합판정 제외)
- 하드웨어 Y/N: 종합판정에 포함
"""

import os
import glob
from pathlib import Path
import pandas as pd
import numpy as np

def safe_float(x):
    """문자열을 float로 안전하게 변환"""
    try:
        if pd.isna(x) or x == '':
            return np.nan
        s = str(x).replace(',', '').strip()
        return float(s)
    except:
        return np.nan

def process_tsv_file(input_file, output_file):
    """TSV 파일을 읽고 정렬/필터링 후 저장"""

    try:
        # TSV 읽기
        df = pd.read_csv(input_file, sep='\t', dtype=str)

        print(f"📖 처리 중: {Path(input_file).name}")
        print(f"   총 종목: {len(df)}")

        # 필요한 컬럼 확인
        required_cols = ['종목코드', '종목명']
        if not all(col in df.columns for col in required_cols):
            print(f"⚠️  필수 컬럼 부족: {input_file}")
            return

        # 수치형 변환 (정렬용)
        numeric_cols = {}
        for col in df.columns:
            if 'Lynch' in col or 'P/E' in col or 'PER' in col:
                numeric_cols[col] = 'lynch_pe'
            elif '배당' in col or '배당감안' in col:
                numeric_cols[col] = 'dividend_score'
            elif '영업이익' in col and '증가' in col:
                numeric_cols[col] = 'operating_profit_growth'
            elif '그레이엄' in col or '괴리' in col:
                numeric_cols[col] = 'graham_divergence'
            elif '주당순현금' in col:
                numeric_cols[col] = 'cash_per_share'
            elif 'FCF' in col or '자유현금' in col:
                numeric_cols[col] = 'fcf'
            elif '단기' in col and '부채' in col:
                numeric_cols[col] = 'short_term_debt'
            elif '하드웨어' in col:
                numeric_cols[col] = 'hardware'

        # 데이터 정제
        for col in df.columns:
            if col not in ['종목코드', '종목명', '그룹', '비고']:
                df[col] = df[col].apply(safe_float)

        # 필터링: 주당순현금 또는 FCF 음수인 경우 비고에 표시
        for idx, row in df.iterrows():
            flags = []

            for col in df.columns:
                if '주당순현금' in col:
                    val = safe_float(row[col])
                    if pd.notna(val) and val < 0:
                        flags.append('주당순현금⚠️')

                if 'FCF' in col or '자유현금' in col:
                    val = safe_float(row[col])
                    if pd.notna(val) and val < 0:
                        flags.append('FCF⚠️')

            if flags:
                current_note = str(row.get('비고', ''))
                if current_note and current_note != 'nan':
                    df.at[idx, '비고'] = current_note + ' | ' + ' '.join(flags)
                else:
                    df.at[idx, '비고'] = ' '.join(flags)

        # 정렬 순서 결정
        sort_columns = []
        ascending = []

        # 1. Lynch P/E (오름차순)
        for col in df.columns:
            if 'Lynch' in col or 'P/E' in col:
                if col not in sort_columns:
                    sort_columns.append(col)
                    ascending.append(True)
                    break

        # 2. 배당감안점수 (내림차순)
        for col in df.columns:
            if '배당' in col:
                if col not in sort_columns:
                    sort_columns.append(col)
                    ascending.append(False)
                    break

        # 3. 영업이익증가율(3년) (내림차순)
        for col in df.columns:
            if '영업이익' in col and ('증가' in col or '3년' in col):
                if col not in sort_columns:
                    sort_columns.append(col)
                    ascending.append(False)
                    break

        # 4. 그레이엄 괴리율(3년) (내림차순)
        for col in df.columns:
            if '그레이엄' in col and ('괴리' in col or '3년' in col):
                if col not in sort_columns:
                    sort_columns.append(col)
                    ascending.append(False)
                    break

        if sort_columns:
            # NaN 값 처리
            for col in sort_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # 정렬
            df = df.sort_values(
                by=sort_columns,
                ascending=ascending,
                na_position='last'
            ).reset_index(drop=True)

            print(f"✅ 정렬 기준: {sort_columns}")
        else:
            print("⚠️  정렬 기준 컬럼을 찾을 수 없습니다")

        # 저장
        df.to_csv(output_file, sep='\t', index=False, encoding='utf-8')
        print(f"💾 저장 완료: {Path(output_file).name}\n")

    except Exception as e:
        print(f"❌ 오류: {input_file}")
        print(f"   {str(e)}\n")

def main():
    """메인 처리 함수"""

    # results 폴더 생성
    os.makedirs('results', exist_ok=True)

    # 최신 _checked.tsv 파일 찾기
    kospi_files = sorted(glob.glob('results/kospi_screening_*_checked.tsv'), reverse=True)
    kosdaq_files = sorted(glob.glob('results/kosdaq_screening_*_checked.tsv'), reverse=True)

    if not kospi_files and not kosdaq_files:
        print("❌ 스크리닝 결과 파일을 찾을 수 없습니다")
        return

    print("="*60)
    print("📊 스크리닝 결과 처리 시작")
    print("="*60 + "\n")

    # 코스피 처리
    if kospi_files:
        latest_kospi = kospi_files[0]
        output_kospi = latest_kospi.replace('_checked.tsv', '_sorted.tsv')
        process_tsv_file(latest_kospi, output_kospi)

    # 코스닥 처리
    if kosdaq_files:
        latest_kosdaq = kosdaq_files[0]
        output_kosdaq = latest_kosdaq.replace('_checked.tsv', '_sorted.tsv')
        process_tsv_file(latest_kosdaq, output_kosdaq)

    print("="*60)
    print("✨ 모든 처리 완료!")
    print("="*60)

if __name__ == '__main__':
    main()
