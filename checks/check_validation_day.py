"""
CHECK: call and put, smile shape and Greek peaks of tab:validation, on two named slices
(reproduction inventory, row 21: call/put, smile shape, Greeks peak)

What this file is for:
    The last two rows of tab:validation give, for the two slices of fig:smile:
      - call and put at the same strike: 12.50% for both at 4,220 on 8 June
        2021, largest difference 0.17 volatility points across 27 strikes
        (0.72 across 30 on 16 March 2020),
      - the smile never rises across the 66 out-of-the-money put strikes of
        8 June 2021 (on 16 March 2020 it rises at 8 of 111 steps),
      - vega peaks at the strike nearest the forward, gamma and theta within
        1.7% of it (8 June 2021).
    Until 2026-10-27 the table gave the methodology report's figures for no
    named day. This file computes all three on the two slices, both at 10:00:
      8 June 2021, SPXW expiring 7 July 2021 (calm), and
      16 March 2020, SPX expiring 17 April 2020 (stress).

    Calls are kept only near the money (K/S from 0.97 to 1.03), so the
    call/put comparison covers those strikes only.

Data: Data/04_greeks/spx_2021-06.csv and spx_2020-03.csv (only the two slices are kept).
Read-only: writes nothing. Takes about a minute.
Run it from the main folder:   python checks/check_validation_day.py
"""

import numpy as np                           # numpy does maths on lists of numbers
import pandas as pd                          # pandas works with tables


SLICES = [
    ("Data/04_greeks/spx_2021-06.csv", "2021-06-08 10:00:00", "SPXW", "2021-07-07"),
    ("Data/04_greeks/spx_2020-03.csv", "2020-03-16 10:00:00", "SPX", "2020-04-17"),
]


for file, time, root, expiry in SLICES:

    # ---- read the slice ----
    pieces = []
    for chunk in pd.read_csv(file, chunksize=2_000_000):     # the month in pieces
        here = (chunk["quote_datetime"] == time) & (chunk["root"] == root) & (chunk["expiration"] == expiry)
        pieces.append(chunk[here])
    one_slice = pd.concat(pieces)

    F = one_slice["forward"].iloc[0]         # the stored forward of the slice
    print("%s  %s  expiry %s   F = %.2f" % (time, root, expiry, F))

    with_vol = one_slice[one_slice["iv"].notna()]            # quotes with a volatility

    # ---- 1. call and put at the same strike ----
    calls = with_vol[with_vol["option_type"] == "C"].set_index("strike")["iv"]   # strike -> call vol
    puts = with_vol[with_vol["option_type"] == "P"].set_index("strike")["iv"]    # strike -> put vol

    both = [K for K in calls.index if K in puts.index]       # strikes with a call and a put
    differences = []                                         # |call vol - put vol| in vol points
    for K in both:
        differences.append(100 * abs(calls[K] - puts[K]))

    nearest = both[0]                        # the paired strike closest to the forward: start with the first ...
    for K in both:                           # ... and replace it by any strike that is closer to F
        if abs(K - F) < abs(nearest - F):
            nearest = K
    print("   call/put: %d strikes with both; at %.0f (nearest F) call %.2f%%, put %.2f%%; largest difference %.2f points" % (
        len(both), nearest, 100 * calls[nearest], 100 * puts[nearest], max(differences)))

    # ---- 2. does the put smile fall with strike? ----
    # out-of-the-money puts (K below F), sorted by strike
    otm_puts = with_vol[(with_vol["option_type"] == "P") & (with_vol["strike"] < F)].sort_values("strike")
    vols = otm_puts["iv"].values             # .values: the volatilities as a plain list of numbers

    rises = 0                                # how often the volatility goes UP from one strike to the next
    for i in range(1, len(vols)):
        if vols[i] > vols[i - 1]:
            rises += 1
    print("   smile: %d out-of-the-money put strikes, from %.0f to %.0f; volatility rises %d times from one strike to the next" % (
        len(vols), otm_puts["strike"].min(), otm_puts["strike"].max(), rises))

    # ---- 3. where do gamma, vega and theta peak? (puts, all strikes) ----
    all_puts = with_vol[with_vol["option_type"] == "P"]
    for greek in ["gamma", "vega", "theta"]:
        # for theta the largest decay is the most negative value, so look at its size
        size = all_puts[greek].abs()
        peak_row = all_puts.loc[size.idxmax()]               # .idxmax(): the row label of the largest; .loc reads that row
        print("   %-5s peaks at strike %.0f, K/F = %.4f" % (greek, peak_row["strike"], peak_row["strike"] / F))
    print()
