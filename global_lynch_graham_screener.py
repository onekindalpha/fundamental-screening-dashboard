#!/usr/bin/env python3
import argparse, time
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import yfinance as yf

NA_STRINGS={"","nan","None","NaN","-"}
def log(msg): print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)
def safe_float(x):
    try:
        if x is None: return np.nan
        if isinstance(x,str):
            x=x.replace(',','').strip()
            if x in NA_STRINGS: return np.nan
        return float(x)
    except Exception: return np.nan

def read_tickers(path):
    out=[]
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        t=line.strip().split('#')[0].strip()
        if t and t not in out: out.append(t)
    return out

def latest_value(df, keys):
    if df is None or df.empty: return np.nan
    for k in keys:
        if k in df.index:
            s=df.loc[k].dropna()
            if len(s): return safe_float(s.iloc[0])
    return np.nan

def values_by_year(df, keys):
    if df is None or df.empty: return []
    for k in keys:
        if k in df.index:
            return [safe_float(v) for v in df.loc[k].dropna().tolist() if not pd.isna(safe_float(v))]
    return []

def cagr(first,last,years):
    first=safe_float(first); last=safe_float(last)
    if pd.isna(first) or pd.isna(last) or first<=0 or last<=0 or years<=0: return np.nan
    return ((last/first)**(1/years)-1)*100

def get_price_metrics(ticker):
    out={"현재가":np.nan,"3M수익률(보조,%)":np.nan,"6M수익률(보조,%)":np.nan,"12M수익률(보조,%)":np.nan,"52주고점대비(보조,%)":np.nan,"40일이평(보조)":np.nan,"200일이평(보조)":np.nan,"40일선상회(보조)":"","200일선상회(보조)":"","추세판정(보조)":""}
    try:
        hist=yf.download(ticker, period='1y', interval='1d', progress=False, auto_adjust=False, threads=False)
        if hist is None or hist.empty: return out
        close=hist['Close']
        if isinstance(close,pd.DataFrame): close=close.iloc[:,0]
        close=close.dropna()
        if close.empty: return out
        cur=safe_float(close.iloc[-1]); out['현재가']=cur
        def ret(days):
            if len(close)>days and close.iloc[-days-1]>0: return (cur/close.iloc[-days-1]-1)*100
            return np.nan
        out['3M수익률(보조,%)']=ret(63); out['6M수익률(보조,%)']=ret(126); out['12M수익률(보조,%)']=ret(252)
        hi=safe_float(close.max())
        if hi>0: out['52주고점대비(보조,%)']=(cur/hi-1)*100
        ma40=safe_float(close.tail(40).mean()) if len(close)>=40 else np.nan
        ma200=safe_float(close.tail(200).mean()) if len(close)>=200 else np.nan
        out['40일이평(보조)']=ma40; out['200일이평(보조)']=ma200
        if not pd.isna(ma40): out['40일선상회(보조)']='Y' if cur>ma40 else 'N'
        if not pd.isna(ma200): out['200일선상회(보조)']='Y' if cur>ma200 else 'N'
        if not pd.isna(ma40) and not pd.isna(ma200) and cur>ma40>ma200 and safe_float(out['6M수익률(보조,%)'])>0 and safe_float(out['12M수익률(보조,%)'])>0 and safe_float(out['52주고점대비(보조,%)'])>=-20:
            out['추세판정(보조)']='강한 상승추세'
        elif (not pd.isna(ma40) and cur>ma40 and safe_float(out['3M수익률(보조,%)'])>0) or (not pd.isna(ma200) and cur>ma200): out['추세판정(보조)']='상승전환/양호'
        elif not pd.isna(ma200) and cur<ma200 and safe_float(out['6M수익률(보조,%)'])<0: out['추세판정(보조)']='주의'
        else: out['추세판정(보조)']='중립'
    except Exception: pass
    return out

def get_info(tkr):
    try:
        info=tkr.get_info()
        return info if isinstance(info,dict) else {}
    except Exception: return {}

def div_yield(ticker, price, info):
    dy=safe_float(info.get('dividendYield'))
    if not pd.isna(dy) and dy<1: return dy*100
    if not pd.isna(dy): return dy
    try:
        divs=yf.Ticker(ticker).dividends
        if divs is not None and len(divs) and price>0:
            return safe_float(divs.tail(4).sum())/price*100
    except Exception: pass
    return np.nan

def judgement_peg(x):
    x=safe_float(x)
    if pd.isna(x) or x<=0: return '판정불가'
    if x<=0.5: return '매우 유망'
    if x<1.0: return '헐값'
    if x<2.0: return '보통'
    return '매우 불리'

def judgement_pegy(x):
    x=safe_float(x)
    if pd.isna(x): return '판정불가'
    if x>=2.0: return '안심(>=2)'
    if x>=1.5: return '양호(>=1.5)'
    if x>=1.0: return '보통(1~1.5)'
    return '불리(<1)'

def overall(row):
    if safe_float(row.get('주당잉여현금흐름'))<=0: return '보류'
    if safe_float(row.get('린치PER배수'))<=0.5 and safe_float(row.get('배당감안점수'))>=2 and safe_float(row.get('그레이엄괴리율(3년,%)'))>0: return '매우 유망'
    if safe_float(row.get('린치PER배수'))<1 and safe_float(row.get('배당감안점수'))>=1.5: return '양호'
    if pd.isna(safe_float(row.get('린치PER배수'))) and pd.isna(safe_float(row.get('배당감안점수'))): return '판정불가'
    return '보류'

def process_ticker(ticker, universe):
    row={'티커':ticker,'종목코드':ticker,'유니버스':universe}
    tkr=yf.Ticker(ticker)
    row.update(get_price_metrics(ticker))
    info=get_info(tkr); price=safe_float(row['현재가'])
    row['종목명']=info.get('shortName') or info.get('longName') or ticker
    row['시장']=info.get('exchange') or ''; row['통화']=info.get('currency') or ''
    row['섹터']=info.get('sector') or ''; row['산업']=info.get('industry') or ''; row['업종']=row['산업'] or row['섹터']
    row['사업설명']=(info.get('longBusinessSummary') or '')[:500]
    row['시가총액']=safe_float(info.get('marketCap')); row['배당수익률(%)']=div_yield(ticker,price,info)
    try: fin=tkr.financials
    except Exception: fin=pd.DataFrame()
    try: bs=tkr.balance_sheet
    except Exception: bs=pd.DataFrame()
    try: cf=tkr.cashflow
    except Exception: cf=pd.DataFrame()
    shares=safe_float(info.get('sharesOutstanding'))
    eps=safe_float(info.get('trailingEps'))
    ni=values_by_year(fin,['Net Income','NetIncome','Net Income Common Stockholders'])
    if pd.isna(eps) and ni and shares and shares>0: eps=ni[0]/shares
    row['EPS(FY)']=eps
    row['EPS Growth 1Y(%)']=(ni[0]/ni[1]-1)*100 if len(ni)>=2 and ni[0]>0 and ni[1]>0 else (safe_float(info.get('earningsQuarterlyGrowth'))*100 if info.get('earningsQuarterlyGrowth') is not None else np.nan)
    row['EPS Growth 3Y CAGR(%)']=cagr(ni[3],ni[0],3) if len(ni)>=4 else np.nan
    row['EPS Growth 5Y CAGR(%)']=cagr(ni[4],ni[0],4) if len(ni)>=5 else np.nan
    cash=latest_value(bs,['Cash Cash Equivalents And Short Term Investments','Cash And Cash Equivalents','Cash']); cash=0 if pd.isna(cash) else cash
    st_inv=latest_value(bs,['Other Short Term Investments','Short Term Investments']); st_inv=0 if pd.isna(st_inv) else st_inv
    ltd=latest_value(bs,['Long Term Debt','LongTermDebt']); ltd=0 if pd.isna(ltd) else ltd
    cur_debt=latest_value(bs,['Current Debt','Short Long Term Debt','Current Debt And Capital Lease Obligation']); cur_debt=0 if pd.isna(cur_debt) else cur_debt
    total_debt=latest_value(bs,['Total Debt']); total_debt=ltd+cur_debt if pd.isna(total_debt) else total_debt
    equity=latest_value(bs,['Stockholders Equity','Total Equity Gross Minority Interest','Common Stock Equity'])
    row['현금및단기투자']=cash+st_inv; row['장기부채']=ltd; row['단기위험부채']=cur_debt; row['총부채']=total_debt; row['주주지분']=equity
    row['주당순현금(린치식)']=(cash+st_inv-ltd)/shares if shares and shares>0 else np.nan
    opcf=latest_value(cf,['Operating Cash Flow','Total Cash From Operating Activities'])
    capex=latest_value(cf,['Capital Expenditure','Capital Expenditures'])
    fcf=latest_value(cf,['Free Cash Flow'])
    if pd.isna(fcf) and not pd.isna(opcf) and not pd.isna(capex): fcf=opcf+capex
    row['주당잉여현금흐름']=fcf/shares if shares and shares>0 and not pd.isna(fcf) else np.nan
    row['잉여현금흐름수익률(%)']=row['주당잉여현금흐름']/price*100 if not pd.isna(row['주당잉여현금흐름']) and price>0 else np.nan
    expe=(price-row['주당순현금(린치식)'])/eps if price>0 and not pd.isna(eps) and eps>0 and not pd.isna(row['주당순현금(린치식)']) else np.nan
    row['순현금차감PER(린치식)']=expe
    g3=safe_float(row['EPS Growth 3Y CAGR(%)']); g1=safe_float(row['EPS Growth 1Y(%)']); gu=g3 if not pd.isna(g3) else g1
    row['사용연성장률(%)']=gu
    row['린치PER배수']=expe/gu if not pd.isna(expe) and not pd.isna(gu) and gu>0 else np.nan
    dy=safe_float(row['배당수익률(%)'])
    row['배당감안점수']=(gu+(0 if pd.isna(dy) else dy))/expe if not pd.isna(expe) and expe>0 and not pd.isna(gu) else np.nan
    row['린치PER판정']=judgement_peg(row['린치PER배수']); row['배당감안점수판정']=judgement_pegy(row['배당감안점수'])
    gg=g3 if not pd.isna(g3) else 0
    fair=max(0,min(60,8.5+2*gg)) if not pd.isna(eps) and eps>0 else np.nan
    intrinsic=eps*fair if not pd.isna(fair) else np.nan
    row['그레이엄적정PER(3년)']=fair; row['그레이엄내재가치(3년)']=intrinsic; row['그레이엄괴리율(3년,%)']=(intrinsic/price-1)*100 if price>0 and not pd.isna(intrinsic) else np.nan
    row['종합판정']=overall(row)
    row['데이터상태']='충분'
    if pd.isna(row['현재가']) or pd.isna(row['EPS(FY)']): row['데이터상태']='핵심부족'
    elif pd.isna(row['린치PER배수']) or pd.isna(row['그레이엄괴리율(3년,%)']): row['데이터상태']='일부부족'
    return row

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--universe',required=True); ap.add_argument('--universe-name',required=True); ap.add_argument('--out',required=True); ap.add_argument('--sleep',type=float,default=0.05)
    args=ap.parse_args(); tickers=read_tickers(args.universe); log(f"Universe={args.universe_name}, tickers={len(tickers)}")
    rows=[]
    for i,t in enumerate(tickers,1):
        try: rows.append(process_ticker(t,args.universe_name))
        except Exception as e: rows.append({'티커':t,'종목코드':t,'종목명':t,'유니버스':args.universe_name,'데이터상태':f'오류:{type(e).__name__}'})
        if i%10==0 or i==len(tickers): log(f"Processed {i}/{len(tickers)}")
        time.sleep(args.sleep)
    df=pd.DataFrame(rows); Path(args.out).parent.mkdir(parents=True,exist_ok=True); df.to_csv(args.out,sep='\t',index=False)
    log(f"Saved -> {args.out} ({len(df)} rows)")
    for c in ['현재가','EPS(FY)','린치PER배수','배당감안점수','그레이엄괴리율(3년,%)','종합판정']:
        if c in df.columns:
            n=df[c].astype(str).str.strip().replace({'nan':'','None':'','-':''}).ne('').sum(); log(f"{c}: {n}/{len(df)}")
if __name__=='__main__': main()
