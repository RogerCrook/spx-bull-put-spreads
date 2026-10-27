# Download the daily S&P 500 (^GSPC) from Yahoo's chart endpoint, 2012-01-01 .. 2026-08-16,
# and save it as Data/07_index_close/GSPC_daily.csv. Standard library only (plus pandas for the CSV).
import json, os, urllib.request
from datetime import datetime, timezone, timedelta
import pandas as pd

p1 = int(datetime(2012, 1, 1, tzinfo=timezone.utc).timestamp())
p2 = int(datetime(2026, 8, 16, tzinfo=timezone.utc).timestamp())
url = ("https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC"
       + "?period1=" + str(p1) + "&period2=" + str(p2) + "&interval=1d&events=history")
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=60) as resp:
    data = json.load(resp)

res = data["chart"]["result"][0]
off = res["meta"].get("gmtoffset", -14400)
q = res["indicators"]["quote"][0]
dates = [(datetime.fromtimestamp(t, tz=timezone.utc) + timedelta(seconds=off)).date()
         for t in res["timestamp"]]
df = pd.DataFrame({"Date": dates, "Open": q["open"], "High": q["high"], "Low": q["low"],
                   "Close": q["close"], "Volume": q["volume"]})
out_dir = "Data/07_index_close"   # relative to the main folder: run it as python checks/fetch_gspc.py
os.makedirs(out_dir, exist_ok=True)
df.to_csv(out_dir + "/GSPC_daily.csv", index=False)
print("rows", len(df), "| from", df["Date"].min(), "to", df["Date"].max(),
      "| missing closes", int(df["Close"].isna().sum()))
print(df.head(2).to_string(index=False)); print(df.tail(2).to_string(index=False))
