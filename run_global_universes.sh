#!/usr/bin/env bash
set -e
TODAY=$(date +%Y%m%d)
mkdir -p results_global
python -u build_global_universe_files.py
python -u global_lynch_graham_screener.py --universe taiwan50_tickers.txt --universe-name "Taiwan 50" --out "results_global/taiwan50_screening_${TODAY}.tsv"
python -u global_lynch_graham_screener.py --universe japan_nikkei225_tickers.txt --universe-name "Japan Nikkei 225" --out "results_global/japan_nikkei225_screening_${TODAY}.tsv"
python -u global_lynch_graham_screener.py --universe china_hk_tickers.txt --universe-name "China / Hong Kong" --out "results_global/china_hk_screening_${TODAY}.tsv"
python -u global_lynch_graham_screener.py --universe india_nifty50_tickers.txt --universe-name "India Nifty 50" --out "results_global/india_nifty50_screening_${TODAY}.tsv"
python -u global_lynch_graham_screener.py --universe global_semicon_pcb_memory_osat_tickers.txt --universe-name "Global Semicon / PCB / Memory / OSAT" --out "results_global/global_semicon_pcb_memory_osat_screening_${TODAY}.tsv"
ls -lh results_global
