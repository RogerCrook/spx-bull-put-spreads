"""
CHECK: how often the open-high-low-close columns of the raw data are zero
(reproduction inventory, row 14)

What this file is for:
    sec:cleaning says the open-high-low-close (OHLC) columns are discarded,
    because when nothing trades in a 15-minute interval the file writes zero
    instead of leaving the field empty, "which is the case for 94.5% of rows".
    That figure comes from the methodology report. This file counts it again.

    OHLC are the first, highest, lowest and last TRADE price in the interval.
    A row counts as "OHLC zero" when all four are 0.

    Reading all 3,675 raw files would take about an hour, so this file uses a
    sample: the first trading day of every month, 176 days spread evenly over
    the whole sample. The share is printed for all rows and for the vanilla
    roots only (SPX, SPXW, SPXQ, the ones stage 1 keeps).

Data: Data/01_raw_options/, 176 daily files (first trading day of each month).
Read-only: writes nothing. Takes about 5 to 10 minutes.
Run it from the main folder:   python checks/check_ohlc_zeros.py
"""

import os                                    # for listing the files in a folder
import pandas as pd                          # pandas works with tables


FOLDER = "Data/01_raw_options"               # the raw Cboe files, one per day
ROOTS = ["SPX", "SPXW", "SPXQ"]              # the vanilla roots stage 1 keeps
COLUMNS = ["root", "open", "high", "low", "close"]


# ---- 1. find the first trading day of every month -----------------------

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


# ---- 2. count the rows with all four OHLC values zero -------------------

rows_all = 0                                 # all rows of the sample days
zero_all = 0                                 # of those, rows with OHLC all zero
rows_vanilla = 0                             # rows of the vanilla roots only
zero_vanilla = 0                             # of those, rows with OHLC all zero
by_year = {}                                 # year -> [vanilla rows, vanilla zero rows]

for month in sorted(first_day_of_month):     # one sample day at a time

    date = first_day_of_month[month]
    path = FOLDER + "/" + files_by_date[date]

    table = pd.read_csv(path, usecols=COLUMNS)    # read only the five columns we need

    # True where all four prices are 0. Each comparison gives a True/False
    # column; & combines them row by row ("and").
    all_zero = (table["open"] == 0) & (table["high"] == 0) & (table["low"] == 0) & (table["close"] == 0)

    is_vanilla = table["root"].isin(ROOTS)   # True where the root is SPX, SPXW or SPXQ

    rows_all += len(table)                   # count every row
    zero_all += int(all_zero.sum())          # .sum() counts the Trues

    n_vanilla = int(is_vanilla.sum())                         # vanilla rows of this day
    n_vanilla_zero = int((all_zero & is_vanilla).sum())       # vanilla rows with OHLC zero
    rows_vanilla += n_vanilla
    zero_vanilla += n_vanilla_zero

    year = date[:4]                          # e.g. "2021"
    if year not in by_year:                  # first day of this year: start the counters
        by_year[year] = [0, 0]
    by_year[year][0] += n_vanilla
    by_year[year][1] += n_vanilla_zero

print("all rows:        %d of %d have OHLC all zero: %.1f%%" % (zero_all, rows_all, 100 * zero_all / rows_all))
print("vanilla roots:   %d of %d have OHLC all zero: %.1f%%" % (zero_vanilla, rows_vanilla, 100 * zero_vanilla / rows_vanilla))
print()
print("by year (vanilla roots):")
for year in sorted(by_year):
    n, z = by_year[year]
    print("   %s   %.1f%%   (%d rows)" % (year, 100 * z / n, n))
