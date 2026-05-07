# 📈 피터린치 + 그레이엄 투자 스크리닝 대시보드

> **한국/미국 주요 주식 universe를 피터 린치 + 벤저민 그레이엄 관점으로 자동 스크리닝하는 Streamlit 대시보드**

![Status](https://img.shields.io/badge/status-active-brightgreen)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 🔗 대시보드

- 🇰🇷 **국장 대시보드:** https://peter-lynch-benjamin-graham-zw4fltw28rwfvafz8nvy67.streamlit.app
- 🇺🇸 **미장 대시보드:** https://peter-lynch-benjamin-graham-md9wco596y8u5ctzoartms.streamlit.app/
- 🌏 **글로벌/아시아 대시보드:** https://peter-lynch-benjamin-graham-gcadlutit8xihbjyjttdk3.streamlit.app/

---

## ✨ 주요 특징

### 🇰🇷 국장 대시보드

- 대상 universe
  - KOSPI 200
  - KOSDAQ 150
- 데이터 흐름
  - DART 재무 데이터
  - pykrx / 가격 보정
  - GitHub Actions 자동 실행
- 주요 기능
  - 피터 린치식 Ex-Cash PEG / Ex-Cash PEGY 판정
  - 벤저민 그레이엄식 적정PER / 내재가치 / 괴리율
  - EPS 성장률 기준 1년 / 3년 / 5년 / 자동 선택
  - 그레이엄 괴리율 기준 1년 / 3년 / 5년 / 자동 선택
  - 주당순현금, FCF, 단기위험부채 예외 필터
  - DART / FnGuide / 한경컨센서스 / 네이버 / KRX KIND 링크

### 🇺🇸 미장 대시보드

- 대상 universe
  - Dow 30
  - Nasdaq 100
  - S&P 500
  - Company Add-ons
  - S&P 500 Growth
  - Russell 1000 Growth
  - Dividend Aristocrats
  - Dividend Kings
  - Growth Leaders 자동 필터 탭
- 주요 기능
  - 국장과 동일한 Lynch + Graham 기본 구조
  - Ex-Cash PEG / Ex-Cash PEGY 판정
  - EPS Growth 1Y / 3Y / 5Y 비교
  - FCF per Share / FCF Yield 확인
  - Net Cash per Share 확인
  - 보조 추세지표
    - 3M / 6M / 12M 수익률
    - 52주 고점 대비
    - 50일선 / 200일선
    - 추세판정(보조)
  - 보조 추세지표는 Lynch/Graham 판정에 섞지 않고 참고용으로만 사용

---

## 📅 자동 실행 스케줄

### 🇰🇷 국장

| 실행 | 시간 | 비고 |
|---|---:|---|
| 자동 스크리닝 | **평일 16:00 KST** | 한국 정규장 종료 후 약 30분 뒤 |
| GitHub Actions cron | **07:00 UTC** | `.github/workflows/screening.yml` 기준 |
| 수동 실행 | 필요 시 | GitHub Actions 화면에서 `Run workflow` 클릭 |

### 🇺🇸 미장

| 실행 | 시간 | 비고 |
|---|---:|---|
| 자동 스크리닝 | **평일 17:30 America/New_York** | 미국 정규장 종료 후 실행 |
| GitHub Actions workflow | `.github/workflows/screening_us.yml` | `mode: full` 기준 전체 universe 생성 |
| 수동 실행 | 필요 시 | GitHub Actions 화면에서 `Run workflow` 클릭 |

> GitHub Actions scheduled workflow는 지연될 수 있으므로, 필요할 때는 `Run workflow`로 수동 갱신할 수 있습니다.

---

## 📂 파일 구조

```text
repository/
├── .github/workflows/
│   ├── screening.yml              # 국장 자동 스크리닝
│   └── screening_us.yml           # 미장 자동 스크리닝
│
├── dashboard.py                   # 국장 Streamlit 대시보드
├── dashboard_us.py                # 미장 Streamlit 대시보드
│
├── process_screening.py           # 국장 결과 정렬/후처리
├── kr_lynch_screener_one_shot_powerfix_rulefit_mirae_capadj_lynch333_v3_graham_fixed3_narrowdebt.py
├── us_lynch_graham_screener.py
│
├── requirements.txt               # Streamlit 앱 기본 의존성
├── requirements-actions.txt       # 국장 GitHub Actions용 의존성
├── requirements_us.txt            # 미장 로컬/Actions용 의존성
│
├── kospi_codes_manual_fixed_v2.txt
├── kosdaq_codes_manual_fixed_v2.txt
│
├── sp500_tickers.txt
├── nasdaq100_tickers.txt
├── dow30_tickers.txt
├── us_company_addons_tickers.txt
├── sp500_growth_tickers.txt
├── russell1000_growth_tickers.txt
├── dividend_aristocrats_tickers.txt
├── dividend_kings_tickers.txt
│
├── results/
│   ├── kospi_screening_YYYYMMDD_checked.tsv
│   ├── kospi_screening_YYYYMMDD_sorted.tsv
│   ├── kosdaq_screening_YYYYMMDD_checked.tsv
│   └── kosdaq_screening_YYYYMMDD_sorted.tsv
│
├── results_us/
│   ├── dow30_screening_YYYYMMDD.tsv
│   ├── nasdaq100_screening_YYYYMMDD.tsv
│   ├── sp500_screening_YYYYMMDD.tsv
│   ├── company_addons_screening_YYYYMMDD.tsv
│   ├── sp500_growth_screening_YYYYMMDD.tsv
│   ├── russell1000_growth_screening_YYYYMMDD.tsv
│   ├── dividend_aristocrats_screening_YYYYMMDD.tsv
│   └── dividend_kings_screening_YYYYMMDD.tsv
│
└── README.md
```

---

## 🚀 로컬 실행

### 국장 대시보드

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

### 미장 대시보드

```bash
pip install -r requirements.txt
pip install -r requirements_us.txt
streamlit run dashboard_us.py
```

---

## 🔐 GitHub Actions 설정

### 국장

국장 스크리너는 DART API Key가 필요합니다.

GitHub 저장소에서:

```text
Settings → Secrets and variables → Actions → New repository secret
```

다음 이름으로 저장합니다.

```text
DART_API_KEY
```

수동 실행:

```text
Actions → Daily Stock Screening → Run workflow
```

### 미장

미장 대시보드는 현재 기본적으로 공개 가격/재무 데이터 기반으로 동작합니다.  
별도 secret 없이도 결과 파일을 생성할 수 있도록 구성합니다.

수동 실행:

```text
Actions → US Daily Stock Screening → Run workflow → mode: full
```

---

## 🔍 계산 로직 요약

### 피터 린치 지표

- **Net Cash per Share**: 현금성자산에서 장기부채를 차감한 뒤 발행주식 수로 나눈 값
- **FCF per Share**: 잉여현금흐름을 발행주식 수로 나눈 값
- **FCF Yield**: 주당 FCF를 현재가로 나눈 값
- **Ex-Cash P/E**: 현재가에서 주당순현금을 차감한 뒤 EPS로 나눈 값
- **Ex-Cash PEG (Custom)**: Ex-Cash P/E를 선택 EPS 성장률로 나눈 값
- **Ex-Cash PEGY Score (Custom)**: EPS 성장률과 배당수익률을 함께 반영한 가격 매력 점수

판정 기준:

```text
Ex-Cash PEG <= 0.5  → 매우 유망
Ex-Cash PEG <  1.0  → 헐값
Ex-Cash PEG <  2.0  → 보통
Ex-Cash PEG >= 2.0  → 매우 불리

Ex-Cash PEGY Score >= 2.0 → 안심
Ex-Cash PEGY Score >= 1.5 → 양호
Ex-Cash PEGY Score 1~1.5  → 보통
Ex-Cash PEGY Score <  1.0 → 불리
```

### 벤저민 그레이엄 지표

- EPS와 성장률로 적정PER을 계산합니다.
- 적정PER과 EPS를 이용해 내재가치를 추정합니다.
- 현재가 대비 내재가치의 괴리율을 계산합니다.
- 괴리율이 높고 양수일수록 저평가 가능성이 큰 것으로 봅니다.

### 미장 Growth Leaders

Growth Leaders는 별도 universe 파일이 아니라, 생성된 미장 universe 결과를 합친 뒤 조건으로 자동 선별하는 압축 탭입니다.

기본 조건:

```text
EPS Growth 3Y >= 10%
FCF per Share > 0
Ex-Cash PEG < 1.0
Ex-Cash PEGY Score >= 1.5
```

엄격 조건:

```text
EPS Growth 3Y >= 15%
FCF per Share > 0
Ex-Cash PEG <= 0.5
Ex-Cash PEGY Score >= 2.0
```

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

## 🧭 보조 추세지표

미장 대시보드에는 보조 추세지표가 포함됩니다.

```text
3M수익률(보조,%)
6M수익률(보조,%)
12M수익률(보조,%)
52주고점대비(보조,%)
50일이평(보조)
200일이평(보조)
50일선상회(보조)
200일선상회(보조)
추세판정(보조)
```

이 지표들은 Lynch/Graham 판정에는 반영하지 않습니다.  
펀더멘털 유망 종목이 실제 시장 가격 흐름에서도 반응 중인지 확인하는 참고용입니다.

---

## ⚠️ 해석상 주의

- 이 도구는 투자 조언이 아니라 **스크리닝 보조 도구**입니다.
- Ex-Cash PEG / Ex-Cash PEGY는 성장 대비 가격 매력을 보는 지표이지, 주가 우상향을 보장하는 모멘텀 신호가 아닙니다.
- 금융, 보험, 증권 업종은 일반 제조업과 재무구조가 다르므로 순현금, FCF, 부채 지표를 그대로 비교하면 왜곡될 수 있습니다.
- 통신, 유틸리티, 전력, 에너지, 철강, 화학, 조선 등 자본집약 업종은 대규모 CAPEX와 부채 조달이 일반적이므로 FCF와 순현금 지표를 업종 특성과 함께 봐야 합니다.
- 미장 ADR/해외기업은 미국 기업과 공시/회계 태그가 달라 일부 지표가 결측일 수 있습니다.
- 모든 투자 결정은 본인의 추가 분석과 책임하에 진행해야 합니다.

---

## 🐛 문제 해결

### GitHub Actions가 자동 실행되지 않을 때

- `Actions` 탭에서 workflow가 활성화되어 있는지 확인
- 국장 workflow의 경우 `DART_API_KEY` Secret이 등록되어 있는지 확인
- 필요하면 `Run workflow`로 수동 실행

### Streamlit에서 데이터가 안 보일 때

```bash
streamlit cache clear
streamlit run dashboard.py
```

미장 대시보드:

```bash
streamlit cache clear
streamlit run dashboard_us.py
```

### 결과 파일이 없는 경우

국장:

```text
results/kospi_screening_*_sorted.tsv
results/kosdaq_screening_*_sorted.tsv
```

미장:

```text
results_us/*_screening_*.tsv
```

---

## ⚖️ 면책 조항

> 이 대시보드는 정보 제공 및 학습 목적의 도구입니다.  
> 투자 조언이 아니며, 투자 손익에 대한 책임은 투자자 본인에게 있습니다.
