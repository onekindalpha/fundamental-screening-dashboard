#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
BASE_PATH = THIS_DIR / 'overseas_lynch_template_v2_rulefit_allticks_lynch333_sectoradj_v5_fix4.py'
if not BASE_PATH.exists():
    raise SystemExit(f'Base script not found: {BASE_PATH}')

spec = importlib.util.spec_from_file_location('overseas_fix4_mod_for_v9', str(BASE_PATH))
if spec is None or spec.loader is None:
    raise SystemExit(f'Failed to load base script: {BASE_PATH}')
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors='coerce')


def _choose_col(df: pd.DataFrame, names) -> Optional[str]:
    low = {str(c).strip().lower(): c for c in df.columns}
    for name in names:
        if name.lower() in low:
            return low[name.lower()]
    for c in df.columns:
        s = str(c).strip().lower()
        for name in names:
            if name.lower() in s:
                return c
    return None


def _load_sector_per_tsv(path: Optional[str]) -> dict:
    if not path:
        return {}
    df = pd.read_csv(path, sep=None, engine='python', dtype=str, encoding='utf-8-sig').fillna('')
    group_col = _choose_col(df, ['그룹', '업종', 'sector', 'sector_name'])
    per_col = _choose_col(df, ['업종평균PER(공식참고)', '업종평균PER', '업종PER', 'PER', 'per'])
    if not group_col or not per_col:
        raise SystemExit(f'sector-per TSV must contain group/sector and PER columns. columns={list(df.columns)}')
    out = {}
    for _, r in df.iterrows():
        g = str(r[group_col]).strip()
        v = str(r[per_col]).replace(',', '').strip()
        if not g or not v:
            continue
        try:
            out[g] = float(v)
        except Exception:
            continue
    return out


def _insert_after(cols, anchor, new_cols):
    cols_wo = [c for c in cols if c not in new_cols]
    present_new = [c for c in new_cols if c in cols]
    if anchor not in cols_wo:
        return cols_wo + present_new
    idx = cols_wo.index(anchor) + 1
    return cols_wo[:idx] + present_new + cols_wo[idx:]


def _augment_df(df: pd.DataFrame, sector_map: dict) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()

    price_col = '현재가'
    eps_col = 'EPS(FY2025)'
    anchor = '순현금차감PER(린치식)'

    if price_col in out.columns and eps_col in out.columns:
        price = _to_num(out[price_col])
        eps = _to_num(out[eps_col])
        out['일반PER(현재가/EPS)'] = price.where(eps > 0) / eps.where(eps > 0)
    else:
        out['일반PER(현재가/EPS)'] = pd.NA

    if '그룹' in out.columns and sector_map:
        out['업종평균PER(공식참고)'] = out['그룹'].map(sector_map)
    else:
        out['업종평균PER(공식참고)'] = pd.NA

    drop_cols = [
        '업종순현금차감PER(그룹중위값,참고)',
        '업종PER(그룹중위값,참고)',
        '업종PER대비(현재PER/업종PER)',
    ]
    for c in drop_cols:
        if c in out.columns:
            out = out.drop(columns=[c])

    new_cols = ['일반PER(현재가/EPS)', '업종평균PER(공식참고)']
    out = out[_insert_after(list(out.columns), anchor, new_cols)]
    return out


def _save_sheet_tsv(df: pd.DataFrame, path: Path) -> None:
    out = df.copy()
    if '티커' in out.columns:
        out['티커'] = out['티커'].astype(str)
    out.to_csv(path, sep='\t', index=False, encoding='utf-8-sig')


def _postprocess(out_prefix: str, save_tsv: bool, sector_map: dict) -> None:
    for p in [Path(f'{out_prefix}_raw.csv'), Path(f'{out_prefix}_filtered.csv')]:
        if not p.exists():
            continue
        df = pd.read_csv(p, dtype=str, encoding='utf-8-sig')
        df = _augment_df(df, sector_map)
        df.to_csv(p, index=False, encoding='utf-8-sig')
        if save_tsv:
            _save_sheet_tsv(df, p.with_name(p.stem + '_sheet.tsv'))


def _parse_known():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--out', default='overseas_v5_fix9_all.csv')
    ap.add_argument('--tsv', action='store_true')
    ap.add_argument('--sector-per-tsv')
    return ap.parse_known_args()[0]


def main() -> None:
    known = _parse_known()
    sector_map = _load_sector_per_tsv(known.sector_per_tsv)
    mod.base.main()
    _postprocess(str(known.out).replace('.csv', ''), bool(known.tsv), sector_map)


if __name__ == '__main__':
    main()
