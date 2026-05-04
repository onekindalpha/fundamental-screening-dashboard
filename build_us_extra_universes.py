#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build extra US universe ticker files from public ETF holdings / dividend lists.

Outputs:
- sp500_growth_tickers.txt              (SPYG holdings)
- russell1000_growth_tickers.txt        (IWF holdings)
- dividend_aristocrats_tickers.txt      (NOBL/S&P 500 Dividend Aristocrats static list)
- dividend_kings_tickers.txt            (Dividend Kings static list)

Notes:
- SPYG/IWF are fetched from ETF issuer holdings files when internet is available.
- Dividend Aristocrats/Kings are kept as explicit lists because the public sources
  are PDF/article style and are more stable as curated lists.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pandas as pd
import requests

SPYG_XLSX_URL = "https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spyg.xlsx"
IWF_CSV_URL = "https://www.ishares.com/us/products/239706/ishares-russell-1000-growth-etf/1467271812596.ajax?fileType=csv&fileName=IWF_holdings&dataType=fund"

DIVIDEND_ARISTOCRATS = """
KO CL DOV EMR GPC JNJ PG NDSN SWK HRL BDX ITW PPG TGT GWW ABT ABBV FRT KMB PEP NUE SPGI ADM ADP ED LOW CLX MCD PNR WMT MDT SHW SYY BEN AFL APD CINF XOM AMCR BF-B CTAS ECL MKC TROW ATO CAH CVX GD AOS LIN ROP WST BRO CAT CB ALB ESS EXPD O IBM NEE CHD CHRW KVUE SJM FAST ERIE ES FDS
""".split()

# SureDividend 2026 list uses MZTI after Marzetti/Lancaster name change in some places.
# Use LANC here because it is the regular Yahoo/SEC-compatible ticker at the time of writing.
DIVIDEND_KINGS = """
MO ADM CL KO HRL KMB LANC PEP PG SYY TGT TR UVV WMT ABM ADP DOV EMR GRC ITW MSA NDSN PH PNR SWK TNC GWW ABT ABBV BDX JNJ KVUE GPC LOW CBSH CINF FMCB RLI SPGI UBSI FUL PPG NUE RPM SON SCL NFG FRT AWR BKH CWT CDUAF ED FTS MGEE MSEX NWN HTO
""".split()


def norm_ticker(x: str) -> str:
    return str(x).strip().replace(".", "-").upper()


def is_ticker(x: str) -> bool:
    return bool(re.match(r"^[A-Z][A-Z0-9.\-]*$", str(x).strip()))


def dedupe(seq):
    seen = set()
    out = []
    for x in seq:
        x = norm_ticker(x)
        if x and x not in seen and is_ticker(x):
            seen.add(x)
            out.append(x)
    return out


def write_txt(path: str, tickers: list[str]) -> None:
    Path(path).write_text("\n".join(dedupe(tickers)) + "\n", encoding="utf-8")


def fetch_spyg() -> list[str]:
    r = requests.get(SPYG_XLSX_URL, timeout=60)
    r.raise_for_status()
    df = pd.read_excel(io.BytesIO(r.content), header=None)
    # Row 4 is header; column 1 is ticker.
    rows = df.iloc[5:].copy()
    return dedupe(rows[1].dropna().astype(str).tolist())


def fetch_iwf() -> list[str]:
    r = requests.get(IWF_CSV_URL, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.BytesIO(r.content), skiprows=9)
    if "Asset Class" in df.columns:
        df = df[df["Asset Class"].astype(str).str.strip().eq("Equity")]
    return dedupe(df["Ticker"].dropna().astype(str).tolist())


def main() -> None:
    spyg = fetch_spyg()
    iwf = fetch_iwf()

    write_txt("sp500_growth_tickers.txt", spyg)
    write_txt("russell1000_growth_tickers.txt", iwf)
    write_txt("dividend_aristocrats_tickers.txt", DIVIDEND_ARISTOCRATS)
    write_txt("dividend_kings_tickers.txt", DIVIDEND_KINGS)

    print(f"sp500_growth_tickers.txt: {len(spyg)}")
    print(f"russell1000_growth_tickers.txt: {len(iwf)}")
    print(f"dividend_aristocrats_tickers.txt: {len(dedupe(DIVIDEND_ARISTOCRATS))}")
    print(f"dividend_kings_tickers.txt: {len(dedupe(DIVIDEND_KINGS))}")


if __name__ == "__main__":
    main()
