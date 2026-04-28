# 📈 피터린치 + 그레이엄 투자 스크리닝 대시보드

> **KOSPI 200 & KOSDAQ 150을 피터 린치 + 벤저민 그레이엄 관점으로 매일 스크리닝하는 Streamlit 대시보드**

![Status](https://img.shields.io/badge/status-active-brightgreen)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## 🔗 대시보드

**Dashboard:** https://peter-lynch-benjamin-graham-zw4fltw28rwfvafz8nvy67.streamlit.app

---

## ✨ 주요 특징

### 🤖 자동화

- **GitHub Actions**로 매일 1회 자동 실행
- 권장 실행 시각: **평일 16:00 KST**
- 한국 정규장 종료 후 약 30분 뒤에 실행되도록 설정합니다.
- GitHub Actions의 cron은 **UTC 기준**이므로, 16:00 KST는 **07:00 UTC**입니다.
- 자동 실행이 누락될 경우를 대비해 **수동 실행(workflow_dispatch)** 도 지원합니다.

### 📊 분석 엔진

#### 피터 린치 방식

- 순현금, FCF, EPS 성장률을 함께 봅니다.
- **Ex-Cash P/E** 기반으로 성장 대비 가격 매력을 평가합니다.
- 주요 지표:
  - **린치PER배수 = Ex-Cash PEG (Custom)**
  - **배당감안점수 = Ex-Cash PEGY Score (Custom)**
- 단기위험부채는 한국 공시 계정에 맞춰 다음 항목을 단기성 위험부채 후보로 봅니다.
  - 단기차입금
  - 유동차입금
  - 기업어음
  - 상업어음
  - 전자단기사채

#### 벤저민 그레이엄 방식

- EPS와 성장률로 **적정PER, 내재가치, 괴리율**을 계산합니다.
- **그레이엄 괴리율이 높고 양수일수록** 현재가 대비 저평가 가능성이 큰 것으로 해석합니다.
- 기본 비교 기준은 **3년 CAGR**이며, 대시보드에서 **1년 / 3년 / 5년 / 자동** 기준을 바꿔볼 수 있습니다.

### 🎯 대시보드 기능

- KOSPI / KOSDAQ 시장 선택
- 판정 필터
  - 종합판정 (with filter)
  - 린치PER판정* (Ex-Cash PEG)
  - 배당감안판정* (Ex-Cash PEGY)
- 비교 기준 선택
  - EPS 성장률 기준: 1년 / 3년 / 5년 / 자동
  - 그레이엄 괴리율 기준: 1년 / 3년 / 5년 / 자동
- 정렬 우선 방식 선택
- 예외 필터
  - 주당순현금 > 0
  - 주당잉여현금흐름 > 0
  - 단기위험부채 없음
- 테이블에서 종목을 선택하면 상세 재무지표, 원천값, 공시/리포트 링크 확인

---

## 📅 자동 실행 스케줄

| 실행 | 시간 | 비고 |
|---|---:|---|
| 자동 스크리닝 | **평일 16:00 KST** | 정규장 종료 후 약 30분 뒤 |
| GitHub Actions cron | **07:00 UTC** | `.github/workflows/screening.yml` 기준 |
| 수동 실행 | 필요 시 | GitHub Actions 화면에서 `Run workflow` 클릭 |

> GitHub Actions 스케줄은 정확한 실행 시각을 항상 보장하지 않을 수 있습니다. 그래서 이 프로젝트는 자동 실행과 함께 수동 실행도 같이 지원합니다.

---

## 📂 파일 구조

```text
repository/
├── .github/workflows/
│   └── screening.yml
│
├── dashboard.py
├── process_screening.py
├── requirements.txt
│
├── kr_lynch_screener_one_shot_powerfix_rulefit_mirae_capadj_lynch333_v3_graham_fixed3_narrowdebt.py
│
├── kospi_codes_manual_fixed_v2.txt
├── kosdaq_codes_manual_fixed_v2.txt
│
├── results/
│   ├── kospi_screening_YYYYMMDD_checked.tsv
│   ├── kospi_screening_YYYYMMDD_sorted.tsv
│   ├── kosdaq_screening_YYYYMMDD_checked.tsv
│   └── kosdaq_screening_YYYYMMDD_sorted.tsv
│
└── README.md
```

> `add_pykrx_timing_checks_...py`는 타이밍 체크를 다시 붙일 때 사용할 수 있지만, 현재 대시보드 기본 흐름에서는 사용하지 않습니다.

---

## 🚀 로컬 실행

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

---

## 🔐 GitHub Actions 설정

### 1. DART API Key 등록

GitHub 저장소에서:

```text
Settings → Secrets and variables → Actions → New repository secret
```

다음 이름으로 저장합니다.

```text
DART_API_KEY
```

### 2. 수동 테스트

GitHub 저장소에서:

```text
Actions → Daily Stock Screening → Run workflow
```

성공하면 `results/` 폴더에 최신 TSV가 커밋됩니다.

---

## 🔍 계산 로직 요약

### 피터 린치 지표

- **Net Cash per Share**: 현금성자산에서 장기부채를 차감한 뒤 발행주식 수로 나눈 값
- **Ex-Cash P/E**: 현재가에서 주당순현금을 차감한 뒤 EPS로 나눈 값
- **Ex-Cash PEG (Custom)**: Ex-Cash P/E를 선택 EPS 성장률로 나눈 값
- **Ex-Cash PEGY Score (Custom)**: EPS 성장률과 배당수익률을 함께 반영한 가격 매력 점수

판정 기준:

```text
Ex-Cash PEG <= 0.5  → 매우 유망
Ex-Cash PEG <  1.0  → 헐값
Ex-Cash PEG <  2.0  → 보통
Ex-Cash PEG >= 2.0  → 매우 불리

Ex-Cash PEGY Score >= 2.0 → 강한 편
Ex-Cash PEGY Score >= 1.5 → 양호
Ex-Cash PEGY Score <  1.0 → 불리
```

### 그레이엄 지표

- EPS와 성장률로 적정PER을 계산합니다.
- 적정PER과 EPS를 이용해 내재가치를 추정합니다.
- 현재가 대비 내재가치의 괴리율을 계산합니다.
- 괴리율이 높고 양수일수록 저평가 가능성이 큰 것으로 봅니다.

---

## 📊 기본 정렬

기본 정렬은 다음 순서를 따릅니다.

```text
1. 린치PER배수 낮은순
2. 배당감안점수 높은순
3. 선택 EPS 성장률 높은순
4. 선택 그레이엄 괴리율 높은순
```

대시보드에서 정렬 우선 방식을 바꿔 탐색할 수 있습니다.

---

## 🧾 리포트 / 공시 링크

종목 상세에서 다음 링크를 제공합니다.

- DART 공시
- FnGuide Snapshot
- FnGuide Consensus
- 한경컨센서스
- 네이버 종목
- 네이버 리서치 목록
- Google PDF 리포트 검색
- KRX KIND 보고서 검색

---

## ⚠️ 해석상 주의

- 이 도구는 투자 조언이 아니라 **스크리닝 보조 도구**입니다.
- 금융, 보험, 증권 업종은 일반 제조업과 재무구조가 다르므로 순현금, FCF, 부채 지표를 그대로 비교하면 왜곡될 수 있습니다.
- 통신, 유틸리티, 전력, 에너지, 철강, 화학, 조선 등 자본집약 업종은 대규모 CAPEX와 부채 조달이 일반적이므로 FCF와 순현금 지표를 업종 특성과 함께 봐야 합니다.
- 단기위험부채는 린치 관점에서 별도 확인 대상으로 둡니다.
- 모든 투자 결정은 본인의 추가 분석과 책임하에 진행해야 합니다.

---

## 🐛 문제 해결

### GitHub Actions가 자동 실행되지 않을 때

- `Actions` 탭에서 workflow가 활성화되어 있는지 확인
- `DART_API_KEY` Secret이 등록되어 있는지 확인
- 필요하면 `Run workflow`로 수동 실행

### Streamlit에서 데이터가 안 보일 때

```bash
streamlit cache clear
streamlit run dashboard.py
```

### 결과 파일이 없는 경우

`results/` 폴더에 다음 패턴의 파일이 있는지 확인합니다.

```text
kospi_screening_*_sorted.tsv
kosdaq_screening_*_sorted.tsv
```

---

## ⚖️ 면책 조항

> 이 대시보드는 정보 제공 및 학습 목적의 도구입니다.  
> 투자 조언이 아니며, 투자 손익에 대한 책임은 투자자 본인에게 있습니다.
