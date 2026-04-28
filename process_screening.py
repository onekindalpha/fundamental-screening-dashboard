#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Safe sorter for screening TSVs.

Important:
- Do NOT coerce judgement/basis/reason text columns to numeric.
- Keep *_checked.tsv as the source-of-truth input.
- Write *_sorted.tsv for dashboard convenience only.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

RESULTS_DIR = Path("results")

TEXT_COL_KEYWORDS = (
    "판정", "기준", "사유", "비고", "통과", "구분", "그룹", "업종", "시장", "종목명", "종목코드"
)

SORT_CANDIDATES = [
    ("린치PER배수", True),
    ("배당감안점수", False),
    ("연간이익증가율(3년CAGR,%)", False),
    ("그레이엄괴리율(3년,%)", False),
]


def clean_code(x: object) -> str:
    s = str(x).strip()
    # Google Sheets style: ="005930"
    m = re.fullmatch(r'=\s*"?([0-9A-Za-z]+)"?', s)
    if m:
        s = m.group(1)
    if s.endswith(".0"):
        s = s[:-2]
    digits = "".join(ch for ch in s if ch.isdigit())
    return digits.zfill(6) if digits else s


def to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .replace({"": np.nan, "-": np.nan, "None": np.nan, "nan": np.nan, "NaN": np.nan}),
        errors="coerce",
    )


def latest_checked_files() -> list[Path]:
    files = sorted(RESULTS_DIR.glob("*_checked.tsv"), key=lambda p: p.stat().st_mtime)
    return files


def sort_file(path: Path) -> Path:
    df = pd.read_csv(path, sep="\t", dtype=str, encoding="utf-8-sig").fillna("")
    if "종목코드" in df.columns:
        df["종목코드"] = df["종목코드"].map(clean_code)

    tmp_cols: list[str] = []
    sort_cols: list[str] = []
    ascending: list[bool] = []

    for col, asc in SORT_CANDIDATES:
        if col in df.columns:
            tmp = f"__sort_{len(tmp_cols)}"
            df[tmp] = to_num(df[col])
            tmp_cols.append(tmp)
            sort_cols.append(tmp)
            ascending.append(asc)

    if sort_cols:
        df = df.sort_values(sort_cols, ascending=ascending, na_position="last").reset_index(drop=True)

    df.insert(0, "순위", range(1, len(df) + 1)) if "순위" not in df.columns else None
    if tmp_cols:
        df = df.drop(columns=tmp_cols)

    out = path.with_name(path.name.replace("_checked.tsv", "_sorted.tsv"))
    df.to_csv(out, sep="\t", index=False, encoding="utf-8-sig")
    print(f"✅ {path.name} -> {out.name} ({len(df)} rows)")
    return out


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    files = latest_checked_files()
    if not files:
        raise SystemExit("❌ results/*_checked.tsv 파일이 없습니다.")
    for path in files:
        sort_file(path)


if __name__ == "__main__":
    main()
