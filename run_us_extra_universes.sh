#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
mkdir -p results_us

DATE_TAG="$(date +%Y%m%d)"

echo "=== US extra universes: ${DATE_TAG} ==="

python -u us_lynch_graham_screener.py \
  --universe sp500_growth_tickers.txt \
  --universe-name "S&P 500 Growth" \
  --out "results_us/sp500_growth_screening_${DATE_TAG}.tsv"

python -u us_lynch_graham_screener.py \
  --universe russell1000_growth_tickers.txt \
  --universe-name "Russell 1000 Growth" \
  --out "results_us/russell1000_growth_screening_${DATE_TAG}.tsv"

python -u us_lynch_graham_screener.py \
  --universe dividend_aristocrats_tickers.txt \
  --universe-name "Dividend Aristocrats" \
  --out "results_us/dividend_aristocrats_screening_${DATE_TAG}.tsv"

python -u us_lynch_graham_screener.py \
  --universe dividend_kings_tickers.txt \
  --universe-name "Dividend Kings" \
  --out "results_us/dividend_kings_screening_${DATE_TAG}.tsv"

ls -lh results_us
