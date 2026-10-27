"""
CHECK: the forward of every slice on 17 days, and SPX against SPXW
(reproduction inventory, row 22; review_log C9)

What this file is for:
    Stage 2 (Code/s04_forward.py) computes one forward per slice (snapshot,
    root, expiry) by put-call parity: calls and puts are paired by strike,
    K0 is the strike where |C - P| is smallest, F = K + (C - P)/D is computed
    at the 8 strikes nearest K0, and the median is taken (sec:forward-impl).
    This file does the same with its own code on 17 days (the first trading
    day of every year, 16 March 2020 and 28 July 2026) and compares with the
    stored forwards.

    It also compares the SPX and SPXW forwards of the same expiry date at the
    same snapshot. sec:monitoring cites this: on the 17 days they agree to a
    median of 0.06 index points, and the large differences, up to 7.7 points,
    all occur at 16:00 (the last line of the printout shows at which times).

    Rewritten 2026-10-27 in the style of Code/s03_rates.py; same calculations
    and the same printout as before, plus that last line (old version in
    old_versions/checks_before_style_2026-10-27/).

Data: 17 days of Data/02_clean/ and Data/04_greeks/ (read month by month, only the day kept).
Read-only: writes nothing. Takes several minutes.
Run it from the main folder:   python checks/check_forward.py
"""

import numpy as np                           # numpy does maths on lists of numbers
import pandas as pd                          # pandas works with tables


DAYS = ["2012-01-03", "2013-01-02", "2014-01-02", "2015-01-02", "2016-01-04", "2017-01-03",
        "2018-01-02", "2019-01-02", "2020-01-02", "2020-03-16", "2021-01-04", "2022-01-03",
        "2023-01-03", "2024-01-02", "2025-01-02", "2026-01-02", "2026-07-28"]
SLICE = ["quote_datetime", "root", "expiration"]     # the three columns that name a slice


def day_rows(folder, day, columns):
    """The rows of one day from a monthly file of Data/02_clean or Data/04_greeks."""
    pieces = []
    # read the month 2 million rows at a time; .str.startswith(day) keeps the rows of that day
    for chunk in pd.read_csv(folder + "/spx_" + day[:7] + ".csv", usecols=columns, chunksize=2_000_000):
        pieces.append(chunk[chunk["quote_datetime"].str.startswith(day)])
    return pd.concat(pieces)


def my_forward(one_slice, D):
    """The forward of one slice by sec:forward-impl, and the number of call-put pairs."""

    calls = one_slice[one_slice["option_type"] == "C"][["strike", "mid"]]
    puts = one_slice[one_slice["option_type"] == "P"][["strike", "mid"]]

    # merge pairs each call with the put of the same strike; suffixes name the two
    # mid columns mid_c and mid_p
    pairs = calls.merge(puts, on="strike", suffixes=("_c", "_p"))
    n = len(pairs)
    if n < 3:
        return np.nan, n                     # fewer than three pairs: no forward

    pairs["diff"] = pairs["mid_c"] - pairs["mid_p"]          # C - P at each strike

    # K0: the strike where |C - P| is smallest (.idxmin() gives that row's label, .loc reads it)
    k0 = pairs.loc[pairs["diff"].abs().idxmin(), "strike"]

    # the 8 strikes nearest K0: sort by distance to K0 and keep the first 8 (.head(8))
    pairs["dist"] = (pairs["strike"] - k0).abs()
    pairs = pairs.sort_values("dist").head(8)

    # F = K + (C - P) / D at each of them, and the median
    return float((pairs["strike"] + pairs["diff"] / D).median()), n


# ---- 1. day by day, slice by slice ----------------------------------------------------

rows = []                                    # one entry per slice

for day in DAYS:

    clean = day_rows("Data/02_clean", day, ["quote_datetime", "root", "expiration", "dte", "strike",
                                            "option_type", "mid"])

    # the stored forward and D: one row per slice is enough (drop_duplicates);
    # set_index makes the three slice columns the row labels, to look a slice up
    stored_table = day_rows("Data/04_greeks", day, SLICE + ["forward", "D"]).drop_duplicates(SLICE)
    stored_table = stored_table.set_index(SLICE)

    # groupby gives each slice (its three names as a tuple) with its quotes
    for key, one_slice in clean.groupby(SLICE):

        stored = stored_table["forward"].get(key, np.nan)    # .get: NaN if the slice has no stored forward
        D = stored_table["D"].get(key, np.nan)
        if D != D:                           # D is NaN (only NaN is not equal to itself): any D will do,
            D = 1.0                          # only the number of pairs matters then

        forward, pairs = my_forward(one_slice, D)
        rows.append({"day": day, "time": key[0][11:16], "root": key[1], "exp": key[2],
                     "dte": int(one_slice["dte"].iloc[0]), "pairs": pairs, "mine": forward, "stored": stored})

    print("done", day, flush=True)           # flush=True: show the line at once

results = pd.DataFrame(rows)


# ---- 2. mine against stored -------------------------------------------------------------

both = results.dropna(subset=["mine", "stored"])            # slices where both exist
print("\nslices:", len(results), "| with a stored forward:", int(results["stored"].notna().sum()))
print("my F vs stored F: max |difference| %.2e index points over %d slices"
      % ((both["mine"] - both["stored"]).abs().max(), len(both)))
print("slices where I get no F but one is stored, or vice versa:",
      int((results["mine"].isna() != results["stored"].isna()).sum()))


# ---- 3. how many call-put pairs a slice has (10 to 90 days) ----------------------------

window = results[(results["dte"] >= 10) & (results["dte"] <= 90)]
window = window.assign(year=window["day"].str[:4])          # .assign adds a column to a copy

print("\nslices with 10-90 days, by sample day: share with < 3 pairs (no forward) /"
      " 3-4 pairs / 5-7 pairs / 8+ pairs")
for day, group in window.groupby("day"):
    n = group["pairs"]
    print("  %s: %4d slices | <3 %5.1f%% | 3-4 %5.1f%% | 5-7 %5.1f%% | 8+ %5.1f%% | median %d"
          % (day, len(group), 100 * (n < 3).mean(), 100 * ((n >= 3) & (n <= 4)).mean(),
             100 * ((n >= 5) & (n <= 7)).mean(), 100 * (n >= 8).mean(), n.median()))


# ---- 4. SPX against SPXW: same expiry date, same snapshot -------------------------------

with_forward = results.dropna(subset=["stored"])

# pivot_table puts the roots side by side: one row per (day, time, expiry date),
# one column per root (SPX, SPXQ, SPXW), each cell the stored forward
side_by_side = with_forward.pivot_table(index=["day", "time", "exp"], columns="root", values="stored")

if "SPX" in side_by_side and "SPXW" in side_by_side:
    # the difference where both roots exist (.dropna drops the rows where one is missing)
    difference = (side_by_side["SPX"] - side_by_side["SPXW"]).abs().dropna()
    print("\nSPX vs SPXW, same expiry date: %d pairs, |difference| median %.3f, 90%% %.3f, max %.3f points"
          % (len(difference), difference.median(), difference.quantile(0.9), difference.max()))
    # per day: how many pairs, the median and the largest difference
    print(difference.groupby(level="day").agg(["count", "median", "max"]).round(3).to_string())

    # added 2026-10-27: at which times of day the large differences (above 0.5
    # points) occur. difference > 0.5 gives True/False per pair; [...] keeps the
    # large ones; .index.get_level_values("time") reads their snapshot times
    large = difference[difference > 0.5]
    print("\ndifferences above 0.5 points: %d, at the times %s" % (
        len(large), large.index.get_level_values("time").value_counts().to_dict()))

    # how many differences exceed each size, at 16:00 and at all other snapshots
    times = difference.index.get_level_values("time")      # the snapshot time of every pair
    at_1600 = difference[times == "16:00"]
    elsewhere = difference[times != "16:00"]
    for size in [0.5, 1, 2, 3, 5]:
        print("   above %.1f points: %3d at 16:00, %3d at other snapshots" % (
            size, (at_1600 > size).sum(), (elsewhere > size).sum()))
    # the largest difference away from 16:00, and where it is (.idxmax(): its label)
    print("   largest away from 16:00: %.3f points on %s" % (elsewhere.max(), elsewhere.idxmax()))
