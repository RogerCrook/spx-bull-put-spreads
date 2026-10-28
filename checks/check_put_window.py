"""
CHECK: how much data a wider put window in stage 1 would add
(review_log C15, the put window; no thesis number depends on it yet)

What this file is for:
    Stage 1 (Code/s01_stage1_extract_simple.py) keeps puts with
    0.45 <= K/S <= 1.08. After prop:credit-maturity the thesis derives that the
    strategy makes sense for bought puts down to 38% of the forward, so in a
    deep enough crisis the bought put could fall below the data window (the p0
    variant lost its bought put this way from 18 March 2020). Before deciding
    whether the rerun of stage 1 should keep puts down to 0.35 (or 0.40, 0.30),
    this file counts how many rows that would add.

    It applies the stage-1 filters exactly as s01 does (the roots, 4 to 100
    days, bid >= 0.025, ask > bid, the strike windows) and counts, for each
    candidate lower bound, the puts between that bound and 0.45 that pass all
    the other filters. S is the quoted index midpoint, as in the current stage
    1 (the C15 change replaces it by the official close only at the last
    snapshot of the day, which hardly changes a count).

    Sample: the first trading day of every month (176 days, as in
    check_ohlc_zeros.py), plus six stress days, printed separately, because
    deep puts are quoted mostly when volatility is high.

Data: Data/01_raw_options/, 176 + 6 daily files.
Read-only: writes nothing. Takes about 10 to 15 minutes.
Run it from the main folder:   python checks/check_put_window.py
"""

import os                                    # for listing the files in a folder
import pandas as pd                          # pandas works with tables


FOLDER = "Data/01_raw_options"               # the raw Cboe files, one per day

# the stage-1 settings, copied from Code/s01_stage1_extract_simple.py
ROOTS = ["SPX", "SPXW", "SPXQ"]
DTE_MIN = 4
DTE_MAX = 100
PUT_LOW = 0.45
PUT_HIGH = 1.08
CALL_LOW = 0.97
CALL_HIGH = 1.03
MIN_BID = 0.025

# the lower put bounds we are thinking about
NEW_LOWS = [0.40, 0.35, 0.30]

# days of high volatility, printed on their own (not part of the monthly sample)
STRESS_DAYS = ["2020-03-16", "2020-03-18", "2020-03-23",
               "2022-10-13", "2024-08-05", "2025-04-08"]

# the size of today's stage-1 and stage-2 output, measured 2026-10-27, in GB
CLEAN_GB = 32.0
GREEKS_GB = 58.8

# read only the columns we need, which is much faster
COLUMNS = ["quote_datetime", "root", "expiration", "strike", "option_type",
           "bid", "ask", "underlying_bid", "underlying_ask"]


def count_one_day(path):
    """
    Apply the stage-1 filters to one raw file.

    Returns two things:
      kept_now : how many rows stage 1 keeps today
      extra    : a dictionary, lower bound -> how many more puts that bound would keep
    """

    table = pd.read_csv(path, usecols=COLUMNS)

    # the vanilla roots only, as in s01. isin() is True where the root is in the
    # list; .copy() makes our own table instead of a view of the old one
    table = table[table["root"].isin(ROOTS)].copy()

    # days to expiry, as in s01: the expiry date minus the trading day, in whole days.
    # .dt.normalize() sets the time of day to 00:00, so only the date is left
    expiry = pd.to_datetime(table["expiration"])
    trade_day = pd.to_datetime(table["quote_datetime"]).dt.normalize()
    dte = (expiry - trade_day).dt.days

    # Each test below gives one True/False per row. & means "and", | means "or",
    # and they combine the columns row by row.

    right_maturity = (dte >= DTE_MIN) & (dte <= DTE_MAX)
    real_quote = (table["bid"] >= MIN_BID) & (table["ask"] > table["bid"])

    passes = right_maturity & real_quote     # every filter except the strike window

    spot = (table["underlying_bid"] + table["underlying_ask"]) / 2    # S, the middle of the index quote
    moneyness = table["strike"] / spot                                # K/S

    is_put = table["option_type"] == "P"
    is_call = table["option_type"] == "C"

    # the strike windows of today
    put_in_window = is_put & (moneyness >= PUT_LOW) & (moneyness <= PUT_HIGH)
    call_in_window = is_call & (moneyness >= CALL_LOW) & (moneyness <= CALL_HIGH)

    # .sum() counts the Trues; int() turns the result into a plain number
    kept_now = int((passes & (put_in_window | call_in_window)).sum())

    # for each candidate bound: the puts between it and 0.45 that pass the rest
    extra = {}
    for low in NEW_LOWS:
        deeper = is_put & (moneyness >= low) & (moneyness < PUT_LOW)
        extra[low] = int((passes & deeper).sum())

    return kept_now, extra


# ---- 1. find the files: the first trading day of every month, and the stress days ----

# The file names end in "_900sec_2021-06-08.csv". Two spellings exist (the days
# from June 2023 to August 2024 start with "hanweck."), so we only look at the
# date at the end: the 10 characters before ".csv".
files_by_date = {}                           # date (text) -> file name

for name in os.listdir(FOLDER):              # every file in the folder
    if name.endswith(".csv"):                # only the data files
        date = name[-14:-4]                  # e.g. "2021-06-08": characters 14 to 5 from the end
        files_by_date[date] = name

first_day_of_month = {}                      # month (e.g. "2021-06") -> its first trading day

for date in sorted(files_by_date):           # dates as text sort in time order
    month = date[:7]                         # the first 7 characters, e.g. "2021-06"
    if month not in first_day_of_month:      # the first date we meet in a month is its first trading day
        first_day_of_month[month] = date

print("sample:", len(first_day_of_month), "days, one per month")
print()


# ---- 2. the monthly sample ------------------------------------------------------------

total_now = 0                                # rows stage 1 keeps today, over the sample
total_extra = {}                             # lower bound -> extra rows over the sample
for low in NEW_LOWS:
    total_extra[low] = 0

by_year = {}                                 # year -> [rows kept now, extra rows at 0.35]

for month in sorted(first_day_of_month):     # one sample day at a time

    date = first_day_of_month[month]
    kept_now, extra = count_one_day(FOLDER + "/" + files_by_date[date])

    total_now += kept_now
    for low in NEW_LOWS:
        total_extra[low] += extra[low]

    year = date[:4]                          # e.g. "2021"
    if year not in by_year:                  # first day of this year: start the counters
        by_year[year] = [0, 0]
    by_year[year][0] += kept_now
    by_year[year][1] += extra[0.35]

print("rows stage 1 keeps today on the sample days:", total_now)
print()
print("lower put bound   extra rows   extra share   about this many GB more (clean + Greeks)")
for low in NEW_LOWS:
    share = total_extra[low] / total_now     # extra rows as a fraction of today's rows
    print("   %.2f        %10d       %5.2f%%         %.1f"
          % (low, total_extra[low], 100 * share, share * (CLEAN_GB + GREEKS_GB)))
print()

print("by year, lower bound 0.35:")
for year in sorted(by_year):
    n_now, n_extra = by_year[year]
    print("   %s   %5.2f%%   (%d extra rows of %d)" % (year, 100 * n_extra / n_now, n_extra, n_now))
print()


# ---- 3. the stress days ------------------------------------------------------------------

print("stress days (not in the sample above):")
for date in STRESS_DAYS:

    if date not in files_by_date:            # the day is not in the data
        print("   %s   no file" % date)
        continue

    kept_now, extra = count_one_day(FOLDER + "/" + files_by_date[date])

    text = "   %s   kept today %d" % (date, kept_now)
    for low in NEW_LOWS:
        text += " | %.2f: +%d (%.1f%%)" % (low, extra[low], 100 * extra[low] / kept_now)
    print(text)
