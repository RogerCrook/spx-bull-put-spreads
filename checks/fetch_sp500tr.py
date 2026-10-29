"""
DOWNLOAD: the daily close of the S&P 500 total return index (Yahoo Finance,
symbol ^SP500TR), with the price index ^GSPC beside it

What this file is for:
    Sections 4.2 and 4.4 of the thesis compare the quarterly return of the
    strategy with the return of the S&P 500 including dividends (review_log T69).
    The price index in Data/07_index_close/GSPC_daily.csv leaves the dividends
    out. The total return index ^SP500TR reinvests them: on the day a share goes
    ex-dividend its price drops, and the index adds the dividend back.

    This script downloads both indices over the same days and writes
        Data/09_total_return/SP500TR_daily.csv
    one row per trading day from 1 December 2011 (the quarter of January to
    March 2012 needs the close of 30 December 2011 as its starting value) to
    14 August 2026, with the columns
        Date          the trading day in New York, e.g. 2012-01-03
        tr_close      close of the total return index ^SP500TR
        price_close   close of the price index ^GSPC
    and a short note Data/09_total_return/retrieved.txt with the day of the
    download and the two addresses (for the list of sources in the thesis).

    The price index is downloaded again only to check the download: on every
    day it should equal Data/07_index_close/GSPC_daily.csv (downloaded on
    22 October 2026), and the gap between the daily returns of the two indices
    should be small, because it is only the dividends of one day.

    If the file already exists the script stops and changes nothing, so that the
    download the thesis uses is never overwritten by accident. To download again,
    delete the folder Data/09_total_return/ first. Yahoo's chart address is not
    an official interface and may change.

Data: downloads from Yahoo Finance, reads Data/07_index_close/GSPC_daily.csv,
writes Data/09_total_return/SP500TR_daily.csv and retrieved.txt.
Takes a few seconds.
Run it from the main folder:   python checks/fetch_sp500tr.py
"""

import json                                  # json reads the text Yahoo sends back into Python lists and dicts
import os                                    # os.path.exists checks for a file, os.makedirs creates a folder
import sys                                   # sys.exit stops the script
import urllib.request                        # urllib.request downloads a web page (part of Python itself)
from datetime import datetime, timezone, timedelta   # dates and times
import pandas as pd                          # pandas works with tables


out_folder = "Data/09_total_return"          # relative to the main folder: run it as python checks/fetch_sp500tr.py
out_file = out_folder + "/SP500TR_daily.csv"


# ---- 0. never overwrite an earlier download --------------------------------------------

if os.path.exists(out_file):
    print(out_file, "exists already, nothing downloaded.")
    print("To download again, delete the folder", out_folder, "first.")
    sys.exit()                               # stop here


# ---- 1. the first and the last day --------------------------------------------------------

# Yahoo wants the first and the last day as "Unix time": the number of seconds
# since 1 January 1970, midnight, in UTC (the time zone of Greenwich).
# .timestamp() turns a date into that number, int() drops the fractions of a second.
# The last day asked for is 16 August 2026 (a Sunday), so that Friday 14 August,
# the last day of the backtest, is the last trading day in the answer.
start_seconds = int(datetime(2011, 12, 1, tzinfo=timezone.utc).timestamp())
end_seconds = int(datetime(2026, 8, 16, tzinfo=timezone.utc).timestamp())


# ---- 2. a function that downloads one index -----------------------------------------------

def address(symbol):
    """The chart address of one symbol, e.g. "%5ESP500TR" for ^SP500TR."""
    # %5E is how a web address writes the character ^ ;
    # interval=1d asks for one row per day
    return ("https://query1.finance.yahoo.com/v8/finance/chart/" + symbol
            + "?period1=" + str(start_seconds) + "&period2=" + str(end_seconds)
            + "&interval=1d&events=history")


def download(symbol):
    """
    Download the daily closes of one index. Gives back a table with two columns:
    Date (text such as "2012-01-03") and Close.
    The steps are the same as in checks/fetch_gspc.py.
    """
    # Yahoo refuses requests that do not say which browser they come from, so the
    # request names one ("User-Agent").
    request = urllib.request.Request(address(symbol), headers={"User-Agent": "Mozilla/5.0"})

    # "with" opens the connection and closes it again at the end of the block;
    # timeout=60: give up after 60 seconds without an answer
    with urllib.request.urlopen(request, timeout=60) as answer:
        data = json.load(answer)             # the whole answer as nested lists and dicts

    # The answer is nested: data["chart"]["result"] is a list with one entry per
    # symbol, and we asked for one symbol, so we take entry [0].
    result = data["chart"]["result"][0]

    # The days come as Unix times of the opening, in UTC. To get the trading day in
    # New York, add the exchange's offset from UTC in seconds ("gmtoffset", -14400
    # = 4 hours behind UTC in summer). .get(..., -14400) uses -14400 if the answer
    # has no gmtoffset.
    offset_seconds = result["meta"].get("gmtoffset", -14400)

    # the closes of all days, as one list (None where Yahoo has no close)
    closes = result["indicators"]["quote"][0]["close"]

    # turn every Unix time into a date, one at a time, and keep it as text
    # ("2012-01-03"), so that it can be compared with the dates in GSPC_daily.csv
    dates = []
    for seconds in result["timestamp"]:
        moment = datetime.fromtimestamp(seconds, tz=timezone.utc)    # the moment, in UTC
        moment = moment + timedelta(seconds=offset_seconds)          # moved to New York time
        dates.append(str(moment.date()))                             # .date() keeps the day only

    return pd.DataFrame({"Date": dates, "Close": closes})


# ---- 3. download both indices ----------------------------------------------------------------

total_return = download("%5ESP500TR")        # ^SP500TR, dividends reinvested
price = download("%5EGSPC")                  # ^GSPC, the price index

# One table with one row per day. merge puts the two tables side by side, matching
# the rows by Date; how="outer" keeps a day even if only one of the two indices has
# it (its other close is then empty, NaN), so that no day is lost silently.
# The columns are renamed first so that the two "Close" columns get their own names.
total_return = total_return.rename(columns={"Close": "tr_close"})
price = price.rename(columns={"Close": "price_close"})
table = pd.merge(total_return, price, on="Date", how="outer")

# merge may change the order of the rows: sort them by date again
# (the dates are text like "2012-01-03", which sorts in the right order);
# reset_index(drop=True) renumbers the rows 0, 1, 2, ... after the sort
table = table.sort_values("Date").reset_index(drop=True)


# ---- 4. save it ---------------------------------------------------------------------------------

os.makedirs(out_folder, exist_ok=True)       # create the folder; exist_ok=True: no error if it is already there
table.to_csv(out_file, index=False)          # index=False: do not write the row numbers

# the note with the day of the download, for the list of sources in the thesis
today = datetime.now().date()                # the day the script runs, on this computer's clock
with open(out_folder + "/retrieved.txt", "w") as note:     # "w": write a new file
    note.write("Retrieved on " + str(today) + " by checks/fetch_sp500tr.py\n")
    note.write(address("%5ESP500TR") + "\n")
    note.write(address("%5EGSPC") + "\n")


# ---- 5. what was saved ---------------------------------------------------------------------------

print("Retrieved on", today)
# .isna() is True where a close is missing, .sum() counts the Trues
print("rows", len(table), "| from", table["Date"].iloc[0], "to", table["Date"].iloc[-1],
      "| missing tr_close", int(table["tr_close"].isna().sum()),
      "| missing price_close", int(table["price_close"].isna().sum()))
# the first two and the last two rows; .to_string(index=False) prints them without row numbers
print(table.head(2).to_string(index=False))
print(table.tail(2).to_string(index=False))
print()


# ---- 6. check 1: the same trading days and the same price closes as GSPC_daily.csv --------------

old = pd.read_csv("Data/07_index_close/GSPC_daily.csv")   # the download of 22 October 2026

# the closes of the old file, looked up by date: {"2012-01-03": 1277.06..., ...}
old_close = {}
for i in range(len(old)):
    old_close[old["Date"][i]] = old["Close"][i]

# the closes of the new download from 2012 on (the old file starts on 3 January 2012)
new_close = {}
for i in range(len(table)):
    day = table["Date"][i]
    if day >= "2012-01-01":                  # dates as text compare in calendar order
        new_close[day] = table["price_close"][i]

# days that are in one file but not in the other
only_new = []
for day in new_close:
    if day not in old_close:
        only_new.append(day)
only_old = []
for day in old_close:
    if day not in new_close:
        only_old.append(day)
print("Check 1: price index against Data/07_index_close/GSPC_daily.csv")
print("  days only in the new download:", len(only_new), only_new[:10])
print("  days only in GSPC_daily.csv:  ", len(only_old), only_old[:10])

# the largest difference in the close on the days both files have
largest = 0.0
largest_day = None
for day in new_close:
    if day in old_close:
        difference = abs(new_close[day] - old_close[day])
        if difference > largest:             # a NaN never counts as larger, so missing closes are skipped here
            largest = difference
            largest_day = day
print("  largest difference in the close (index points):", largest, "on", largest_day)
print()


# ---- 7. check 2: the daily gap between the two returns (the dividends of one day) ------------------

# Only days on which both indices have a close, and the day before as well.
# .notna() is True where a value is present; & means "and" for two such columns.
complete = table[table["tr_close"].notna() & table["price_close"].notna()]
complete = complete.reset_index(drop=True)   # renumber the rows 0, 1, 2, ... so that row i-1 is the day before

gaps = []                                    # (gap, day, return with dividends, return without), one per day
for i in range(1, len(complete)):
    tr_return = complete["tr_close"][i] / complete["tr_close"][i - 1] - 1
    price_return = complete["price_close"][i] / complete["price_close"][i - 1] - 1
    gaps.append((tr_return - price_return, complete["Date"][i], tr_return, price_return))

# sorted by the size of the gap, largest first. key=... says what to sort by:
# "lambda entry: abs(entry[0])" is a one-line function that takes one entry and
# gives back the absolute value of its first part, the gap; reverse=True: largest first
gaps.sort(key=lambda entry: abs(entry[0]), reverse=True)
print("Check 2: daily return with dividends minus without, the 5 largest gaps (per cent)")
for gap, day, tr_return, price_return in gaps[:5]:
    print("  %s  gap %+.3f  (with %+.3f, without %+.3f)" % (day, 100 * gap, 100 * tr_return, 100 * price_return))
negative = 0
for entry in gaps:
    if entry[0] < -1e-6:                     # a gap below zero: dividends cannot make the return smaller
        negative = negative + 1
print("  days with a negative gap (below -0.0001 per cent):", negative, "of", len(gaps))
print()


# ---- 8. check 3: the return of each calendar year, to compare with S&P DJI's published figures -----

# the last close of every year: the rows are in date order, so for each year the
# last row that is seen is the last trading day of that year
last_tr = {}
last_price = {}
last_day = {}
for i in range(len(complete)):
    year = int(complete["Date"][i][:4])      # [:4]: the first four characters of the date, the year
    last_tr[year] = complete["tr_close"][i]
    last_price[year] = complete["price_close"][i]
    last_day[year] = complete["Date"][i]

print("Check 3: return of each calendar year (per cent), close of the year's last trading day")
print("         against the close of the year before; compare 'with dividends' with the")
print("         annual total returns published by S&P Dow Jones Indices")
print("  year  last day     with dividends  without  dividends (difference)")
for year in range(2012, 2027):
    tr_return = last_tr[year] / last_tr[year - 1] - 1
    price_return = last_price[year] / last_price[year - 1] - 1
    print("  %d  %s   %+8.2f      %+8.2f   %5.2f" % (
        year, last_day[year], 100 * tr_return, 100 * price_return, 100 * (tr_return - price_return)))
print("  (2026 only to", last_day[2026] + ")")
