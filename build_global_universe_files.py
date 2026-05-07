from pathlib import Path

UNIVERSES = {
    "taiwan50_tickers.txt": [
        "2330.TW","2317.TW","2454.TW","2308.TW","2382.TW","2303.TW","2412.TW","2882.TW","2891.TW","2881.TW",
        "2886.TW","2884.TW","2885.TW","2880.TW","1101.TW","1301.TW","1303.TW","2002.TW","1216.TW","2207.TW",
        "1326.TW","3008.TW","5871.TW","3711.TW","6669.TW","3034.TW","2357.TW","4938.TW","2892.TW","5880.TW",
        "2912.TW","6505.TW","2603.TW","2615.TW","2327.TW","3037.TW","3045.TW","6415.TW","2395.TW","2379.TW",
        "2474.TW","4904.TW","2408.TW","1590.TW","9910.TW","5876.TW","3529.TW","3443.TW","3661.TW","2376.TW",
    ],
    "japan_nikkei225_tickers.txt": [
        "7203.T","6758.T","9984.T","6861.T","8035.T","6954.T","6857.T","6594.T","9432.T","9433.T","9434.T",
        "8306.T","8316.T","8411.T","7267.T","6902.T","7974.T","6098.T","4519.T","4568.T","4502.T","4503.T",
        "9983.T","4063.T","6981.T","6762.T","6976.T","2802.T","2914.T","4452.T","6501.T","6503.T","6506.T",
        "6752.T","7751.T","7752.T","8058.T","8001.T","8031.T","8766.T","8750.T","8801.T","8802.T","9020.T",
        "9021.T","9022.T","7201.T","7269.T","7270.T","4901.T","5108.T","6301.T","6326.T","6367.T","6273.T",
        "6146.T","7735.T","7741.T","7733.T","6971.T","6963.T","6723.T","6702.T","6701.T","5802.T","5713.T",
        "5401.T","5411.T","4188.T","4005.T","3407.T","3382.T","3092.T","1925.T","1928.T","4755.T","4689.T",
        "9201.T","9202.T","9101.T","9104.T","9107.T","4911.T","2502.T","2503.T","4507.T","4523.T","4543.T",
    ],
    "china_hk_tickers.txt": [
        "0700.HK","9988.HK","3690.HK","9618.HK","9999.HK","1810.HK","9888.HK","1024.HK","1211.HK","2318.HK",
        "0939.HK","1398.HK","3988.HK","0941.HK","0883.HK","0857.HK","0386.HK","0005.HK","1299.HK","0388.HK",
        "2382.HK","9868.HK","2015.HK","9866.HK","0981.HK","1347.HK","1876.HK","0020.HK","2269.HK","2388.HK",
        "600519.SS","601318.SS","600036.SS","601012.SS","300750.SZ","000858.SZ","002594.SZ","300760.SZ","603501.SS","688981.SS",
        "600183.SS","000725.SZ","002916.SZ","601888.SS","601899.SS","600276.SS","600309.SS","000333.SZ","000651.SZ","002475.SZ",
    ],
    "india_nifty50_tickers.txt": [
        "RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","BHARTIARTL.NS","SBIN.NS","ITC.NS","LT.NS","HINDUNILVR.NS",
        "BAJFINANCE.NS","KOTAKBANK.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS","TITAN.NS","ULTRACEMCO.NS","WIPRO.NS","ONGC.NS",
        "NTPC.NS","POWERGRID.NS","M&M.NS","TATASTEEL.NS","HCLTECH.NS","TECHM.NS","COALINDIA.NS","NESTLEIND.NS","ADANIENT.NS","ADANIPORTS.NS",
        "JSWSTEEL.NS","CIPLA.NS","DRREDDY.NS","GRASIM.NS","HINDALCO.NS","HEROMOTOCO.NS","BPCL.NS","EICHERMOT.NS","APOLLOHOSP.NS","BRITANNIA.NS",
        "BAJAJ-AUTO.NS","TATACONSUM.NS","DIVISLAB.NS","INDUSINDBK.NS","SHRIRAMFIN.NS","HDFCLIFE.NS","SBILIFE.NS","BAJAJFINSV.NS","UPL.NS","LTIM.NS",
    ],
    "global_semicon_pcb_memory_osat_tickers.txt": [
        "TSM","ASML","ARM","NVDA","AMD","AVGO","MU","MRVL","AMAT","LRCX","KLAC","TER","ON","NXPI","QCOM","TXN","INTC","MCHP","MPWR","QRVO","SWKS","COHR","AMKR","GFS","UMC",
        "2330.TW","2454.TW","2303.TW","3711.TW","3037.TW","8046.TW","4958.TW","3044.TW","2327.TW","2408.TW","2344.TW","2337.TW","6239.TW","2449.TW","8150.TW","2368.TW","3189.TW","2313.TW","2316.TW",
        "6981.T","6762.T","6976.T","4062.T","6861.T","8035.T","6857.T","6146.T","7735.T","6723.T","6758.T","3407.T","5201.T","3110.T",
        "600183.SS","002916.SZ","688981.SS","603501.SS","1888.HK","0981.HK","2382.HK","TTMI","005930.KS","000660.KS","042700.KS","009150.KS","011070.KS","222800.KS","272210.KS","353200.KQ",
    ],
}

def write_unique(path: Path, tickers):
    seen=[]
    for t in tickers:
        t=t.strip()
        if t and t not in seen:
            seen.append(t)
    path.write_text("\n".join(seen)+"\n", encoding="utf-8")
    return len(seen)

def main():
    for name,tickers in UNIVERSES.items():
        n=write_unique(Path(name), tickers)
        print(f"{name}: {n}")

if __name__ == "__main__":
    main()
