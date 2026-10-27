"""
CHECK: the figures of the sample day 8 June 2021 in sec:iv-impl and rem:atm-band
(reproduction inventory, rows 18 and 19)

What this file is for:
    The thesis gives, for 8 June 2021:
      sec:iv-impl:   none of the 26,805 near-money volatilities lay outside
                     the no-arbitrage bounds or at either end of the bisection
                     bracket [0.001, 5], and they ranged from 7.97% to 21.70%;
      rem:atm-band:  the median fitting window was x in [-0.049, +0.029], and
                     the fit used a median of 41 quotes per slice, never fewer
                     than 33.
    The script that first produced these was lost. This file computes them
    again from the stored stage-2 output, following Definition def:atm.

    A "slice" is one snapshot time, one root and one expiry. x = log(K/F) is
    the log-moneyness. The ATM fit of a slice uses the out-of-the-money quotes
    with |x| < 0.05 that have a volatility: puts with -0.05 < x < 0 and calls
    with 0 <= x < 0.05.

    "Near-money" is not defined in the thesis, so two counts are printed:
    every quote with |x| < 0.05, and only the out-of-the-money ones in the fit.

    This file does not import Code/s08_atm_vol.py, because that file starts its
    whole run as soon as it is imported. It repeats the few steps it needs.

Data: Data/04_greeks/spx_2021-06.csv (one month, read in pieces; only 8 June is kept).
Read-only: writes nothing. Takes about a minute.
Run it from the main folder:   python checks/check_sample_day.py
"""

import numpy as np                           # numpy does maths on lists of numbers
import pandas as pd                          # pandas works with tables


FILE = "Data/04_greeks/spx_2021-06.csv"      # stage-2 output for June 2021
DAY = "2021-06-08"                           # the sample day
BAND = 0.05                                  # the half-width of the fitting window, w in def:atm
COLUMNS = ["quote_datetime", "root", "expiration", "strike", "option_type", "forward", "iv"]


# ---- 1. read the month in pieces and keep only the sample day -----------

pieces = []                                  # the rows of 8 June, collected piece by piece

# chunksize=2_000_000 makes read_csv hand the file over 2 million rows at a
# time instead of all at once, so the computer does not run out of memory
for chunk in pd.read_csv(FILE, usecols=COLUMNS, chunksize=2_000_000):

    # .str[:10] cuts the first 10 characters of every timestamp, i.e. the date;
    # == DAY gives True/False per row, and chunk[...] keeps the True rows
    keep = chunk["quote_datetime"].str[:10] == DAY
    pieces.append(chunk[keep])

# pd.concat glues the pieces below each other into one table
day = pd.concat(pieces)

print("rows on", DAY, ":", len(day))

# the log-moneyness of every quote: x = log(K / F)
day["x"] = np.log(day["strike"] / day["forward"])


# ---- 2. the near-money volatilities (sec:iv-impl) -----------------------

# .abs() removes the sign, so this is True where -0.05 < x < 0.05
near = day[day["x"].abs() < BAND]

# out-of-the-money in the band: puts below the forward, calls at or above it
is_otm_put = (near["option_type"] == "P") & (near["x"] < 0)      # & means "and", row by row
is_otm_call = (near["option_type"] == "C") & (near["x"] >= 0)
near_otm = near[is_otm_put | is_otm_call]                         # | means "or", row by row

for label, quotes in [("all quotes with |x| < 0.05", near), ("out-of-the-money only", near_otm)]:

    no_vol = quotes["iv"].isna().sum()       # .isna() is True where the volatility is missing; .sum() counts them
    with_vol = quotes["iv"].dropna()         # the volatilities that exist

    at_low_end = (with_vol <= 0.0011).sum()  # pinned at the bottom of the bracket [0.001, 5]
    at_high_end = (with_vol >= 4.999).sum()  # pinned at the top

    print()
    print(label)
    print("   quotes:", len(quotes), "| without a volatility (outside the bounds):", no_vol)
    print("   at the bracket ends: low", at_low_end, "| high", at_high_end)
    print("   range: %.2f%% to %.2f%%" % (100 * with_vol.min(), 100 * with_vol.max()))


# ---- 3. the fitting window and the points per fit (rem:atm-band) --------

rows = []                                    # one entry per slice, collected in the loop

# groupby splits the day into one small table per (time, root, expiry);
# the loop gets the three values (a tuple) and the rows of that slice
for (time, root, expiry), one_slice in day.groupby(["quote_datetime", "root", "expiration"]):

    x = one_slice["x"]                       # log-moneyness of each quote in the slice
    kind = one_slice["option_type"]          # "P" or "C"
    has_vol = one_slice["iv"].notna()        # True where a volatility exists

    puts_in = (kind == "P") & (x > -BAND) & (x < 0) & has_vol       # OTM puts in the window
    calls_in = (kind == "C") & (x >= 0) & (x < BAND) & has_vol      # OTM calls in the window
    used = puts_in | calls_in                                       # the quotes the fit uses

    n = int(used.sum())                      # how many quotes the fit uses

    if n > 0:                                # the window actually covered by those quotes
        left = x[used].min()
        right = x[used].max()
    else:
        left = np.nan                        # no quotes: no window
        right = np.nan

    rows.append({
        "n": n,
        "left": left,
        "right": right,
        "one_sided": (puts_in.sum() == 0) or (calls_in.sum() == 0),   # only puts or only calls
    })

slices = pd.DataFrame(rows)                  # one row per slice

fitted = slices[slices["n"] >= 3]            # def:atm needs at least three quotes

print()
print("slices on the day:", len(slices), "| with at least 3 quotes (fitted):", len(fitted),
      "| with fewer than 3:", int((slices["n"] < 3).sum()))
print("one-sided fits (only puts or only calls):", int(fitted["one_sided"].sum()))
print("quotes per fit: median %d, minimum %d" % (fitted["n"].median(), fitted["n"].min()))
print("window: median left edge %.3f, median right edge %.3f" % (fitted["left"].median(), fitted["right"].median()))
