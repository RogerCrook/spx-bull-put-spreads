"""
CHECK: SPX against SPXW forwards on 1 and 5 August 2024 (tab:validation)
(reproduction inventory, row 21)

What this file is for:
    tab:validation says that the forwards from SPX and from SPXW options with
    the same expiry date, at every snapshot except the stock close, differ by
    a median of 0.08 index points on 1 August 2024 (a calm day) and 0.39 on
    5 August 2024, at single snapshots by up to 3.3 and 7.4 points (0.06% and
    0.14% of spot). Until 2026-10-27 it gave the methodology report's ranges
    (0.048 to 0.100 and 0.135 to 0.601 points). This file computes the figures
    from the stored stage-2 output.

    Stage 2 stores one forward per (snapshot, root, expiry) on every row of
    that slice. For each snapshot and each expiry date that both SPX and SPXW
    list, we take the two forwards and their difference.

    The report did not say over which snapshots its ranges run, so the ranges
    are printed over all snapshots, without the 16:00 snapshot (unreliable,
    sec:monitoring), and expiry by expiry.

Data: Data/04_greeks/spx_2024-08.csv (one month, read in pieces; only the two days are kept).
Read-only: writes nothing. Takes about a minute.
Run it from the main folder:   python checks/check_root_forwards.py
"""

import pandas as pd                          # pandas works with tables


FILE = "Data/04_greeks/spx_2024-08.csv"      # stage-2 output for August 2024
DAYS = ["2024-08-01", "2024-08-05"]          # the two days in tab:validation
COLUMNS = ["quote_datetime", "root", "expiration", "forward", "spot"]


# ---- 1. read the month in pieces and keep the two days ------------------

pieces = []                                  # rows of the two days, collected piece by piece

# chunksize: read 2 million rows at a time, so the memory is not filled
for chunk in pd.read_csv(FILE, usecols=COLUMNS, chunksize=2_000_000):

    date = chunk["quote_datetime"].str[:10]  # .str[:10]: the first 10 characters, i.e. the date
    keep = date.isin(DAYS)                   # True where the date is one of the two days
    chunk = chunk[keep]                      # keep only those rows

    # every row of a slice carries the same forward, so one row per slice is
    # enough: drop_duplicates keeps the first row of each (time, root, expiry)
    chunk = chunk.drop_duplicates(subset=["quote_datetime", "root", "expiration"])

    pieces.append(chunk)

slices = pd.concat(pieces)                   # glue the pieces into one table
slices = slices.drop_duplicates(subset=["quote_datetime", "root", "expiration"])   # a slice could span two pieces


# ---- 2. put the SPX and SPXW forward of the same time and expiry side by side

forwards = {}                                # (time, expiry) -> {"SPX": F, "SPXW": F, "spot": S}

for _, row in slices.iterrows():             # one slice at a time

    key = (row["quote_datetime"], row["expiration"])    # same time, same expiry date

    if key not in forwards:                  # first time we see this pair: start an empty entry
        forwards[key] = {}

    forwards[key][row["root"]] = row["forward"]          # the forward of this root
    forwards[key]["spot"] = row["spot"]                  # the spot at that time (same for all roots)


# ---- 3. the differences, day by day -------------------------------------

rows = []                                    # one entry per (time, expiry) with both roots

for key in forwards:                         # go through every (time, expiry)

    entry = forwards[key]

    if "SPX" not in entry or "SPXW" not in entry:        # need both roots
        continue

    time, expiry = key                       # unpack the pair

    difference = abs(entry["SPX"] - entry["SPXW"])       # in index points

    rows.append({
        "day": time[:10],                    # the date part of the time
        "clock": time[11:16],                # the time of day, e.g. "10:00"
        "expiry": expiry,
        "difference": difference,
        "percent_of_spot": 100 * difference / entry["spot"],
    })

table = pd.DataFrame(rows)                   # one row per comparison

for day in DAYS:

    one_day = table[table["day"] == day]                 # comparisons of this day
    not_1600 = one_day[one_day["clock"] != "16:00"]      # the same without the 16:00 snapshot

    print(day, "  shared expiry dates:", sorted(one_day["expiry"].unique()))
    print("   all snapshots:     %d comparisons, difference %.3f to %.3f points (median %.3f), at most %.4f%% of spot" % (
        len(one_day), one_day["difference"].min(), one_day["difference"].max(),
        one_day["difference"].median(), one_day["percent_of_spot"].max()))
    print("   without 16:00:     %d comparisons, difference %.3f to %.3f points (median %.3f), at most %.4f%% of spot" % (
        len(not_1600), not_1600["difference"].min(), not_1600["difference"].max(),
        not_1600["difference"].median(), not_1600["percent_of_spot"].max()))

    # expiry by expiry: groupby gives one small table per expiry date
    for expiry, rows_of_expiry in not_1600.groupby("expiry"):
        print("      expiry %s: %.3f to %.3f points, median %.3f" % (
            expiry, rows_of_expiry["difference"].min(), rows_of_expiry["difference"].max(),
            rows_of_expiry["difference"].median()))

    # the five largest differences of the day and when they happened:
    # sort_values(..., ascending=False) puts the largest first, head(5) keeps five
    largest = one_day.sort_values("difference", ascending=False).head(5)
    print("   largest differences:")
    for _, row in largest.iterrows():
        print("      %s  expiry %s  %.3f points" % (row["clock"], row["expiry"], row["difference"]))

    # how many comparisons differ by more than half a point, and at which times
    big = one_day[one_day["difference"] > 0.5]
    print("   differences above 0.5 points:", len(big), "of", len(one_day), "at", sorted(big["clock"].unique()))
    print()
