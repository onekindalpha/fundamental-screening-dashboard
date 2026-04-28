import yfinance as yf

tickers = [
    "005930.KS",
    "000660.KS",
    "000270.KS",
    "035420.KS",
    "091990.KQ",
    "196170.KQ",
]

for t in tickers:
    print("=" * 60)
    print("ticker:", t)
    try:
        hist = yf.Ticker(t).history(period="5d")
        print(hist.tail())
        if len(hist) > 0:
            print("last close:", hist["Close"].dropna().iloc[-1])
        else:
            print("NO DATA")
    except Exception as e:
        print("ERROR:", repr(e))
