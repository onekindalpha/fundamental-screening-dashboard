# 📊 피터린치 + 그레이엄 대시보드 설정 가이드

이 문서는 한국/미국 투자 스크리닝 대시보드의 기본 설정 방법을 정리합니다.

---

## 1. 대시보드 링크

| 구분 | 링크 |
|---|---|
| 🇰🇷 국장 대시보드 | https://peter-lynch-benjamin-graham-zw4fltw28rwfvafz8nvy67.streamlit.app |
| 🇺🇸 미장 대시보드 | https://peter-lynch-benjamin-graham-md9wco596y8u5ctzoartms.streamlit.app |

---

## 2. Streamlit 앱 구성

같은 GitHub repository에서 Streamlit 앱을 2개 생성합니다.

### 국장 앱

```text
Repository: onekindalpha/PETER-LYNCH-BENJAMIN-GRAHAM
Branch: main
Main file path: dashboard.py
Python: 3.10 또는 3.11
Secrets: 불필요
```

### 미장 앱

```text
Repository: onekindalpha/PETER-LYNCH-BENJAMIN-GRAHAM
Branch: main
Main file path: dashboard_us.py
Python: 3.10 또는 3.11
Secrets: 불필요
```

대시보드는 이미 생성된 `results/`, `results_us/` TSV 파일을 읽는 구조이므로 Streamlit 앱에 API key를 넣을 필요는 없습니다.

---

## 3. GitHub Actions 설정

### 국장 workflow

파일:

```text
.github/workflows/screening.yml
```

필요한 GitHub Secret:

```text
DART_API_KEY
```

설정 위치:

```text
GitHub repository → Settings → Secrets and variables → Actions → New repository secret
```

자동 실행:

```text
평일 16:00 KST
```

수동 실행:

```text
Actions → Daily Stock Screening → Run workflow
```

### 미장 workflow

파일:

```text
.github/workflows/screening_us.yml
```

필요한 Secret:

```text
없음
```

자동 실행:

```text
평일 17:30 America/New_York
```

수동 실행:

```text
Actions → US Daily Stock Screening → Run workflow → mode: full
```

---

## 4. 로컬 실행

### 국장

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

### 미장

```bash
pip install -r requirements.txt
pip install -r requirements_us.txt
streamlit run dashboard_us.py
```

---

## 5. 결과 파일 구조

### 국장

```text
results/
├── kospi_screening_YYYYMMDD_checked.tsv
├── kospi_screening_YYYYMMDD_sorted.tsv
├── kosdaq_screening_YYYYMMDD_checked.tsv
└── kosdaq_screening_YYYYMMDD_sorted.tsv
```

### 미장

```text
results_us/
├── dow30_screening_YYYYMMDD.tsv
├── nasdaq100_screening_YYYYMMDD.tsv
├── sp500_screening_YYYYMMDD.tsv
├── company_addons_screening_YYYYMMDD.tsv
├── sp500_growth_screening_YYYYMMDD.tsv
├── russell1000_growth_screening_YYYYMMDD.tsv
├── dividend_aristocrats_screening_YYYYMMDD.tsv
└── dividend_kings_screening_YYYYMMDD.tsv
```

---

## 6. Universe 파일

### 국장

```text
kospi_codes_manual_fixed_v2.txt
kosdaq_codes_manual_fixed_v2.txt
```

### 미장

```text
dow30_tickers.txt
nasdaq100_tickers.txt
sp500_tickers.txt
us_company_addons_tickers.txt
sp500_growth_tickers.txt
russell1000_growth_tickers.txt
dividend_aristocrats_tickers.txt
dividend_kings_tickers.txt
```

---

## 7. 문제 해결

### GitHub Actions가 실패할 때

1. Actions 로그에서 실패 step 확인
2. 국장 workflow는 `DART_API_KEY` 확인
3. 결과 파일이 너무 오래된 경우 수동으로 `Run workflow` 실행

### Streamlit에서 데이터가 안 보일 때

```bash
streamlit cache clear
```

그 다음 앱 reboot 또는 재실행.

### Git push가 non-fast-forward로 막힐 때

GitHub Actions가 결과 파일을 먼저 commit한 경우입니다.

```bash
git fetch origin main
git rebase origin/main
git push
```

force push는 사용하지 않습니다.

---

## 8. 주의

- 이 대시보드는 투자 조언이 아니라 스크리닝 보조 도구입니다.
- Lynch/Graham 지표는 펀더멘털 기반 지표입니다.
- 미장 보조 추세지표는 참고용이며 종합판정에는 반영하지 않습니다.
