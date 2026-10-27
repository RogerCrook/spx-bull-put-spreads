"""
CHECK: how far parity at a single strike misses the forward, by distance from the money
(reproduction inventory, row 17)

What this file is for:
    sec:forward-impl says that far from the money the parity estimate
    F = K + (C - P) / D is biased: "on one snapshot the median error was 0.002
    index points for strikes within 1% of the forward, 0.274 at 3 to 6% and
    0.416 beyond 12%". The report did not record which snapshot. This file
    recomputes the figures on two named snapshots, the two of Figure fig:smile.

    For every strike where both the call and the put are quoted, it computes
    the single-strike estimate K + (C - P)/D from the raw quotes (C and P are
    mid quotes) and compares it with the forward the pipeline stored for that
    slice (median over the 8 strikes nearest the money, sec:forward-impl).
    The raw quotes are used, not the cleaned ones, because cleaning keeps
    calls only near the money (K/S from 0.97 to 1.03).

Data: Data/01_raw_options/ (two daily files) for the quotes, and
      Data/04_greeks/ (two monthly files) for the stored forward F and the discount factor D.
Read-only: writes nothing. Takes about a minute.
Run it from the main folder:   python checks/check_forward_error.py
"""

import numpy as np                           # numpy does maths on lists of numbers
import pandas as pd                          # pandas works with tables


# the two snapshots of fig:smile: (time, root, expiry, raw file, Greeks file)
SNAPSHOTS = [
    ("2021-06-08 10:00:00", "SPXW", "2021-07-07",
     "Data/01_raw_options/UnderlyingOptionsIntervals_900sec_2021-06-08.csv", "Data/04_greeks/spx_2021-06.csv"),
    ("2020-03-16 10:00:00", "SPX", "2020-04-17",
     "Data/01_raw_options/UnderlyingOptionsIntervals_900sec_2020-03-16.csv", "Data/04_greeks/spx_2020-03.csv"),
]

# distance bands, as |K/F - 1| in per cent: (lower edge, upper edge, label)
BANDS = [(0, 1, "within 1%"), (1, 3, "1 to 3%"), (3, 6, "3 to 6%"), (6, 12, "6 to 12%"), (12, 1000, "beyond 12%")]


for time, root, expiry, raw_file, greeks_file in SNAPSHOTS:

    # ---- 1. the stored forward and discount factor of this slice ----
    F = None                                 # not found yet
    D = None
    for chunk in pd.read_csv(greeks_file, usecols=["quote_datetime", "root", "expiration", "forward", "D"],
                             chunksize=2_000_000):            # read the month in pieces
        # True on the rows of our slice: same time, root and expiry
        here = (chunk["quote_datetime"] == time) & (chunk["root"] == root) & (chunk["expiration"] == expiry)
        if here.any():                       # .any(): is at least one row True?
            first = chunk[here].iloc[0]      # .iloc[0]: the first of those rows (all carry the same F and D)
            F = first["forward"]
            D = first["D"]
            break                            # found it, stop reading

    # ---- 2. the raw quotes of the slice, calls and puts paired by strike ----
    raw = pd.read_csv(raw_file, usecols=["quote_datetime", "root", "expiration", "strike", "option_type", "bid", "ask"])

    here = (raw["quote_datetime"] == time) & (raw["root"] == root) & (raw["expiration"] == expiry)
    quotes = raw[here].copy()                # .copy(): a separate table we can add columns to

    quotes = quotes[(quotes["bid"] > 0) & (quotes["ask"] > quotes["bid"])]   # both sides quoted, not crossed
    quotes["mid"] = (quotes["bid"] + quotes["ask"]) / 2                       # mid quote

    calls = {}                               # strike -> call mid
    puts = {}                                # strike -> put mid
    for _, row in quotes.iterrows():         # one quote at a time
        if row["option_type"] == "C":
            calls[row["strike"]] = row["mid"]
        else:
            puts[row["strike"]] = row["mid"]

    # ---- 3. single-strike estimate and its error at every paired strike ----
    rows = []
    for K in calls:                          # every strike with a call ...
        if K in puts:                        # ... and a put
            estimate = K + (calls[K] - puts[K]) / D          # parity at this one strike
            rows.append({
                "strike": K,
                "distance": 100 * abs(K / F - 1),            # how far from the forward, in per cent
                "error": estimate - F,                       # signed error, in index points
            })
    paired = pd.DataFrame(rows)

    print("%s  %s  expiry %s   stored F = %.2f, D = %.6f, paired strikes: %d" % (time, root, expiry, F, D, len(paired)))

    for low, high, label in BANDS:
        in_band = paired[(paired["distance"] >= low) & (paired["distance"] < high)]   # strikes in this band
        if len(in_band) == 0:
            print("   %-11s  no strikes" % label)
            continue
        print("   %-11s  %3d strikes   median error %+8.3f points   median absolute error %7.3f points" % (
            label, len(in_band), in_band["error"].median(), in_band["error"].abs().median()))
    print()
