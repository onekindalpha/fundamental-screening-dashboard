#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import pandas as pd

IMPORTANT = [
    "현재가",
    "EPS(FY2025)",
    "주당순현금(린치식)",
    "주당잉여현금흐름",
    "순현금차감PER(린치식)",
    "연간이익증가율(3년CAGR,%)",
    "배당수익률(%)",
    "린치PER배수",
    "린치PER판정",
    "배당감안점수",
    "배당감안점수판정",
    "종합판정",
]

EMPTY = {"", "-", "None", "nan", "NaN", "null"}


def nonempty_count(s: pd.Series) -> int:
    return (~s.astype(str).str.strip().isin(EMPTY)).sum()


def main() -> None:
    files = sorted(Path("results").glob("*_checked.tsv"))
    if not files:
        raise SystemExit("❌ results/*_checked.tsv 파일이 없습니다.")

    bad = False
    for p in files:
        df = pd.read_csv(p, sep="\t", dtype=str, encoding="utf-8-sig").fillna("")
        print(f"\n## {p} rows={len(df)}")
        for c in IMPORTANT:
            if c not in df.columns:
                print(f"MISSING: {c}")
                bad = True
            else:
                n = nonempty_count(df[c])
                print(f"{c}: {n}/{len(df)}")
        # fail only when almost everything valuation-related is empty
        for c in ["현재가", "EPS(FY2025)", "린치PER배수", "배당감안점수", "종합판정"]:
            if c in df.columns and nonempty_count(df[c]) == 0:
                bad = True

    if bad:
        raise SystemExit("❌ 핵심 컬럼이 비어 있습니다. Actions 결과 TSV 생성 파이프라인을 확인하세요.")
    print("\n✅ validation passed")


if __name__ == "__main__":
    main()
