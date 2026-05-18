# Fundamental Screening Dashboard

Automated financial metrics screening dashboard for Korea, US, and global markets using Streamlit, data pipelines, and GitHub Actions.

This project converts rule-based financial analysis concepts into reproducible software workflows: data collection, metric calculation, scheduled screening, result generation, and interactive dashboard visualization.

The main focus is software engineering practice: building data pipelines, dashboard interfaces, automated update workflows, and reproducible screening outputs.

![Status](https://img.shields.io/badge/status-active-brightgreen)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Live Dashboards

- **Korea Dashboard**: https://peter-lynch-benjamin-graham-zw4fltw28rwfvafz8nvy67.streamlit.app
- **US Dashboard**: https://peter-lynch-benjamin-graham-md9wco596y8u5ctzoartms.streamlit.app/
- **Global / Asia Dashboard**: https://peter-lynch-benjamin-graham-gcadlutit8xihbjyjttdk3.streamlit.app/

---

## TL;DR

- Built a Streamlit-based financial metrics dashboard covering Korea, US, and global market universes.
- Implemented automated data pipelines using DART, pykrx, public market data, and scheduled GitHub Actions workflows.
- Generated reproducible screening outputs as TSV files for multiple universes.
- Designed dashboard views for company screening, valuation factor comparison, trend reference indicators, and filtering workflows.
- Added separate Korea, US, and Global / Asia dashboard entrypoints for region-specific data handling.

---

## Project Overview

This repository implements a rule-based financial metrics screening system with interactive dashboards and scheduled update workflows.

The system includes:

- Korea dashboard using DART financial data and pykrx-based market data
- US dashboard covering multiple major universes such as Dow 30, Nasdaq 100, S&P 500, growth lists, and dividend-focused lists
- Global / Asia dashboard for additional regional universes
- GitHub Actions workflows for scheduled screening runs
- TSV result files for reproducible screening outputs
- Streamlit dashboards for interactive exploration and filtering

This project is not positioned as an investment recommendation tool. It is designed as a data engineering and dashboard implementation project based on financial metrics and rule-based screening logic.

---

## Key Features

### 1. Korea Dashboard

Supported universe:

- KOSPI 200
- KOSDAQ 150

Data flow:

- DART financial data
- pykrx-based market data
- price adjustment workflow
- scheduled GitHub Actions execution

Main features:

- Ex-Cash PEG / Ex-Cash PEGY-style factor calculation
- Graham-style fair PER / intrinsic value / valuation gap estimation
- EPS growth comparison across 1-year, 3-year, and 5-year windows
- Net cash per share, FCF, and short-term risk debt filters
- External reference links to DART, FnGuide, Hankyung Consensus, Naver, and KRX KIND

### 2. US Dashboard

Supported universe:

- Dow 30
- Nasdaq 100
- S&P 500
- Company add-ons
- S&P 500 Growth
- Russell 1000 Growth
- Dividend Aristocrats
- Dividend Kings
- Growth Leaders tab generated from rule-based filters

Main features:

- Region-specific implementation of the same screening framework
- Ex-Cash PEG / Ex-Cash PEGY-style factor calculation
- EPS growth comparison across 1-year, 3-year, and 5-year windows
- FCF per share and FCF yield
- Net cash per share
- Reference trend indicators:
  - 3-month / 6-month / 12-month return
  - distance from 52-week high
  - 50-day / 200-day moving averages
  - trend reference label

Trend indicators are used only as reference fields and are not mixed into the main fundamental screening score.

### 3. Global / Asia Dashboard

The Global / Asia dashboard extends the screening interface to additional regional universes and dashboard views.

It is designed to reuse the same screening concept while keeping region-specific data handling separated.

---

## Automation Schedule

### Korea Workflow

| Task | Schedule | Notes |
|---|---:|---|
| Scheduled screening | Weekdays 16:00 KST | After the Korean regular market close |
| GitHub Actions cron | 07:00 UTC | Based on `.github/workflows/screening.yml` |
| Manual run | On demand | Run from the GitHub Actions page |

### US Workflow

| Task | Schedule | Notes |
|---|---:|---|
| Scheduled screening | Weekdays 17:30 America/New_York | After the US regular market close |
| GitHub Actions workflow | `.github/workflows/screening_us.yml` | Runs full universe generation |
| Manual run | On demand | Run from the GitHub Actions page with `mode: full` |

GitHub Actions scheduled workflows may be delayed depending on GitHub's scheduler. Manual workflow execution is supported when an immediate refresh is needed.

---

## Repository Structure

```text
repository/
├── .github/workflows/
│   ├── screening.yml              # Korea scheduled screening
│   └── screening_us.yml           # US scheduled screening
│
├── dashboard.py                   # Korea Streamlit dashboard
├── dashboard_us.py                # US Streamlit dashboard
│
├── process_screening.py           # Korea result sorting / post-processing
├── kr_lynch_screener_one_shot_powerfix_rulefit_mirae_capadj_lynch333_v3_graham_fixed3_narrowdebt.py
├── us_lynch_graham_screener.py
│
├── requirements.txt               # Base Streamlit app dependencies
├── requirements-actions.txt       # Korea GitHub Actions dependencies
├── requirements_us.txt            # US local / Actions dependencies
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

## Local Development

### Korea Dashboard

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

### US Dashboard

```bash
pip install -r requirements.txt
pip install -r requirements_us.txt
streamlit run dashboard_us.py
```

---

## GitHub Actions Setup

### Korea Workflow

The Korea workflow requires a DART API key.

Add the following repository secret:

```text
DART_API_KEY
```

GitHub path:

```text
Settings → Secrets and variables → Actions → New repository secret
```

Manual execution:

```text
Actions → Daily Stock Screening → Run workflow
```

### US Workflow

The US dashboard is designed to generate result files using public market and financial data sources.

Manual execution:

```text
Actions → US Daily Stock Screening → Run workflow → mode: full
```

---

## Screening Logic Summary

### Financial Metrics

The dashboard calculates and compares several financial metrics:

- **Net Cash per Share**: cash-like assets minus long-term debt, divided by shares outstanding
- **FCF per Share**: free cash flow divided by shares outstanding
- **FCF Yield**: FCF per share divided by current price
- **Ex-Cash P/E**: price adjusted by net cash per share, divided by EPS
- **Ex-Cash PEG**: Ex-Cash P/E divided by selected EPS growth rate
- **Ex-Cash PEGY Score**: a custom score combining growth and dividend yield

### Rule-Based Interpretation

The dashboard uses rule-based interpretation ranges for screening and comparison. These ranges are used for exploratory filtering and dashboard organization, not as investment recommendations.

Example ranges:

```text
Ex-Cash PEG <= 0.5  → very attractive by the rule
Ex-Cash PEG <  1.0  → attractive by the rule
Ex-Cash PEG <  2.0  → neutral by the rule
Ex-Cash PEG >= 2.0  → unfavorable by the rule

Ex-Cash PEGY Score >= 2.0 → strong by the rule
Ex-Cash PEGY Score >= 1.5 → positive by the rule
Ex-Cash PEGY Score 1~1.5  → neutral by the rule
Ex-Cash PEGY Score <  1.0 → weak by the rule
```

### Intrinsic Value Reference

The dashboard also estimates a Graham-style intrinsic value reference using EPS and growth assumptions.

The output includes:

- fair PER reference
- intrinsic value reference
- valuation gap versus current price
- multiple growth-window comparisons

These values are used as screening references and should be interpreted with sector, accounting quality, and data limitations in mind.

### Growth Leaders Tab

The Growth Leaders tab is generated from existing US universe outputs by applying rule-based filters.

Base conditions:

```text
EPS Growth 3Y >= 10%
FCF per Share > 0
Ex-Cash PEG < 1.0
Ex-Cash PEGY Score >= 1.5
```

Strict conditions:

```text
EPS Growth 3Y >= 15%
FCF per Share > 0
Ex-Cash PEG <= 0.5
Ex-Cash PEGY Score >= 2.0
```

---

## Default Sorting

The default sorting order is:

```text
1. Lower Lynch-style PER multiple
2. Higher dividend-adjusted score
3. Higher selected EPS growth rate
4. Higher selected Graham-style valuation gap
```

The dashboard allows users to change sorting priorities for different exploration workflows.

---

## Reference Trend Indicators

The US dashboard includes additional trend reference fields:

```text
3M return reference (%)
6M return reference (%)
12M return reference (%)
Distance from 52-week high (%)
50-day moving average
200-day moving average
Above 50-day moving average
Above 200-day moving average
Trend reference label
```

These indicators are not included in the main Lynch/Graham-style screening decision logic. They are provided as reference fields to compare financial metric outputs with market price behavior.

---

## Limitations

- Financial, insurance, and securities companies have different balance sheet structures, so cash, debt, and FCF-based metrics may not be directly comparable with manufacturing or software companies.
- Capital-intensive sectors such as telecom, utilities, energy, steel, chemicals, shipbuilding, and infrastructure may require sector-specific interpretation.
- ADRs and non-US companies may have incomplete or inconsistent accounting tags.
- Public data sources may contain missing, delayed, or restated values.
- Screening outputs should be treated as starting points for further analysis, not final conclusions.

---

## Troubleshooting

### GitHub Actions does not run automatically

- Check whether workflows are enabled in the `Actions` tab.
- For the Korea workflow, confirm that `DART_API_KEY` is registered as a repository secret.
- Use `Run workflow` for manual execution if scheduled runs are delayed.

### Streamlit does not show updated data

```bash
streamlit cache clear
streamlit run dashboard.py
```

US dashboard:

```bash
streamlit cache clear
streamlit run dashboard_us.py
```

### Result files are missing

Korea:

```text
results/kospi_screening_*_sorted.tsv
results/kosdaq_screening_*_sorted.tsv
```

US:

```text
results_us/*_screening_*.tsv
```

---

## Disclaimer

This project is for educational, research, and software engineering portfolio purposes only.

It is not financial advice, investment recommendation, or a trading signal service. All investment decisions are the responsibility of the user.
