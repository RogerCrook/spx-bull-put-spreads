"""
DOWNLOAD: the official daily close of the S&P 500 (Yahoo Finance, symbol ^GSPC)

What this file is for:
    Stage 1 (Code/s01_stage1_extract_simple.py) sets the index level S at the
    snapshot after the stock close (16:15, or 13:15 on early-close days) to the
    official daily close, and checks/check_s_close.py compares the recorded
    index quote with it (sec:data). Both read the file this script writes:
        Data/07_index_close/GSPC_daily.csv
    one row per trading day, with the columns Date, Open, High, Low, Close and
    Volume, from 1 January 2012 to 16 August 2026.

    The thesis uses the file downloaded on 22 October 2026. Running this
    script again OVERWRITES that file with a new download, which may differ.
    Yahoo's chart address is not an official interface and may change.

    Rewritten 2026-10-29 in the style of Code/s03_rates.py: the same download,
    the same file and the same printout as before, in simple steps.

Data: downloads from Yahoo Finance, writes Data/07_index_close/GSPC_daily.csv.
Takes a few seconds.
Run it from the main folder:   python checks/fetch_gspc.py
"""

import json                                  # json reads the text Yahoo sends back into Python lists and dicts
import os                                    # os.makedirs creates a folder
import urllib.request                        # urllib.request downloads a web page (part of Python itself)
from datetime import datetime, timezone, timedelta   # dates and times
import pandas as pd                          # pandas works with tables


# ---- 1. the address to download from -----------------------------------------------

# Yahoo wants the first and the last day as "Unix time": the number of seconds
# since 1 January 1970, midnight, in UTC (the time zone of Greenwich).
# .timestamp() turns a date into that number, int() drops the fractions of a second.
start_seconds = int(datetime(2012, 1, 1, tzinfo=timezone.utc).timestamp())
end_seconds = int(datetime(2026, 8, 16, tzinfo=timezone.utc).timestamp())

# %5E is how a web address writes the character ^ (so %5EGSPC means ^GSPC);
# interval=1d asks for one row per day
url = ("https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC"
       + "?period1=" + str(start_seconds) + "&period2=" + str(end_seconds)
       + "&interval=1d&events=history")


# ---- 2. download ---------------------------------------------------------------------

# Yahoo refuses requests that do not say which browser they come from, so the
# request names one ("User-Agent").
request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

# "with" opens the connection and closes it again at the end of the block;
# timeout=60: give up after 60 seconds without an answer
with urllib.request.urlopen(request, timeout=60) as answer:
    data = json.load(answer)                 # the whole answer as nested lists and dicts


# ---- 3. take the table out of the answer ---------------------------------------------

# The answer is nested: data["chart"]["result"] is a list with one entry per
# symbol, and we asked for one symbol, so we take entry [0].
result = data["chart"]["result"][0]

# The days come as Unix times of the opening, in UTC. To get the trading day in
# New York, add the exchange's offset from UTC in seconds ("gmtoffset", -14400
# = 4 hours behind UTC in summer). .get(..., -14400) uses -14400 if the answer
# has no gmtoffset.
offset_seconds = result["meta"].get("gmtoffset", -14400)

# the open, high, low, close and volume of every day, as five lists
quotes = result["indicators"]["quote"][0]

# turn every Unix time into a date, one at a time
dates = []
for seconds in result["timestamp"]:
    moment = datetime.fromtimestamp(seconds, tz=timezone.utc)    # the moment, in UTC
    moment = moment + timedelta(seconds=offset_seconds)          # moved to New York time
    dates.append(moment.date())                                  # .date() keeps the day only

# the table: one column per list, one row per day
table = pd.DataFrame({"Date": dates,
                      "Open": quotes["open"],
                      "High": quotes["high"],
                      "Low": quotes["low"],
                      "Close": quotes["close"],
                      "Volume": quotes["volume"]})


# ---- 4. save it -----------------------------------------------------------------------

out_folder = "Data/07_index_close"           # relative to the main folder: run it as python checks/fetch_gspc.py
os.makedirs(out_folder, exist_ok=True)       # create the folder; exist_ok=True: no error if it is already there
table.to_csv(out_folder + "/GSPC_daily.csv", index=False)   # index=False: do not write the row numbers


# ---- 5. print what was saved ----------------------------------------------------------

# .isna() is True where a close is missing, .sum() counts the Trues
print("rows", len(table), "| from", table["Date"].min(), "to", table["Date"].max(),
      "| missing closes", int(table["Close"].isna().sum()))
# the first two and the last two rows; .to_string(index=False) prints them without row numbers
print(table.head(2).to_string(index=False))
print(table.tail(2).to_string(index=False))
