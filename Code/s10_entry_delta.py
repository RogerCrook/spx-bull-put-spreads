"""
THE ENTRY DELTA

What this file is for:
    When the strategy opens two bull put spreads, what is the delta of the
    whole position at that moment? The thesis shows that if both legs used
    the SAME volatility the answer would be about 0.296, and that using each
    strike's own volatility (the "smile") should give a lower number, around
    0.23. The methodology report quotes 0.2833, which nobody has checked.

    This file measures it on the real data: one entry per day, strikes chosen
    by the strategy's rule, delta read from the Greeks files.

HOW IT WORKS
    For each day:
      1. take the expiry closest to 30 days, at the entry time
      2. compute the two target strikes
             K_short = F * exp(-1.0 * sigma * sqrt(tau))
             K_long  = F * exp(-2.3 * sigma * sqrt(tau))
         where sigma is the at-the-money volatility of that expiry
      3. snap each target to the nearest strike that really exists
      4. look up the delta of those two puts in the Greeks files
      5. combine them into the delta of two spreads

HOW TO RUN IT
    python Code/s10_entry_delta.py
"""

import numpy as np
import pandas as pd
from scipy.stats import norm

from s06_greeks import spread_delta        # reuse the function from s06_greeks.py


ATM_FILE = "Data/05_atm_vol.csv"           # input: ATM volatility per slice
GREEKS_FOLDER = "Data/04_greeks"           # input: stage 2 output, one file per month
OUT_FILE = "entry_delta.csv"               # output: one row per day

ENTRY_TIME = "10:00:00"                    # the snapshot at which we open the trade
TARGET_DAYS = 30                           # the maturity we want
K1 = 1.0                                   # short put, in standard deviations below F
K2 = 2.3                                   # long put, in standard deviations below F
HOW_MANY_SPREADS = 2                       # the strategy trades two spreads

# For a quick test, list the months to run, e.g. ["2021-06", "2012-01"].
# An empty list means: run every month.
TEST_MONTHS = []


def pick_one_expiry_per_day(atm):
    """
    From the ATM table, keep ONE row per day: the slice at the entry time whose
    days-to-expiry is closest to 30.

      atm : table with columns quote_datetime, root, expiration, dte, spot,
            forward, atm_iv

    Returns a smaller table with one row per day.
    """

    # the date as text, for example "2021-06-08" (the first 10 characters)
    atm["date"] = atm["quote_datetime"].str[:10]

    # the time as text, for example "10:00:00" (everything after the space)
    atm["time"] = atm["quote_datetime"].str[11:]

    # keep only the entry time.
    # atm["time"] == ENTRY_TIME gives one True/False per row, and atm[...] keeps
    # the rows that are True. .copy() makes the result a separate table; without it
    # pandas may warn later that we are changing a "slice" of the original table.
    atm = atm[atm["time"] == ENTRY_TIME].copy()

    # drop slices where the ATM volatility could not be fitted
    # (notna() is True where there IS a number, False where it is empty)
    atm = atm[atm["atm_iv"].notna()].copy()

    # how far each expiry is from the 30 days we want (always positive)
    atm["distance_from_30"] = (atm["dte"] - TARGET_DAYS).abs()

    # sort so that, within each day, the closest expiry comes first.
    # sort_values sorts by the first column, then by the second where the first
    # is equal, and so on.
    # The root and dte are added only so that ties are always broken the same way.
    atm = atm.sort_values(["date", "distance_from_30", "root", "dte"])

    # keep the first row of each day, which is the closest expiry.
    # drop_duplicates looks only at the "date" column: of all rows with the same
    # date it keeps the first one and throws the rest away.
    atm = atm.drop_duplicates(subset="date", keep="first")

    return atm


def find_put(puts, strike_wanted):
    """
    Find the listed put whose strike is closest to the strike we want.

      puts          : table of puts for ONE slice (one time, root, expiry)
      strike_wanted : the target strike, for example 5437.3

    Returns the one row (as a Series) of the closest put.
    """

    # the strikes that exist in this slice, as a plain array of numbers
    listed_strikes = puts["strike"].values

    # how far each listed strike is from the one we want
    gaps = np.abs(listed_strikes - strike_wanted)

    # the position (0, 1, 2, ...) of the smallest gap
    best_position = np.argmin(gaps)

    # return the row at that position (.iloc means "by position", not by label)
    return puts.iloc[best_position]


def process_one_month(month, days):
    """
    Work out the entry delta for every day of one month.

      month : text like "2021-06"
      days  : the rows of the ATM table (one per day) that belong to this month

    Returns a list of dictionaries, one per day.
    """

    path = GREEKS_FOLDER + "/spx_" + month + ".csv"    # e.g. "Data/04_greeks/spx_2021-06.csv"

    print("reading", path)

    # read only the columns we need, which saves a lot of memory
    # quote_datetime and expiration stay as text, which is faster than dates
    columns = ["quote_datetime", "root", "expiration", "strike",
               "option_type", "iv", "delta"]
    greeks = pd.read_csv(path, usecols=columns)    # usecols = read only these columns

    # keep only puts, we never need calls here
    greeks = greeks[greeks["option_type"] == "P"]

    # keep only the entry time. quote_datetime is text like "2021-06-08 10:00:00";
    # .str[11:] cuts off the first 11 characters (date and space), leaving the time
    greeks = greeks[greeks["quote_datetime"].str[11:] == ENTRY_TIME]

    # drop options whose volatility could not be computed (their delta is empty too),
    # otherwise we might pick one as the nearest strike and get no delta
    greeks = greeks[greeks["delta"].notna()]

    results = []                               # empty list, one dictionary per day goes in

    # iterrows() goes through the table one row at a time. Each step gives two
    # things: the row's label (which we do not need, so we call it _) and the row
    # itself (which we call day; day["forward"] is then that row's forward).
    for _, day in days.iterrows():

        # ---- step 1: the target strikes ----------------------------------

        F = day["forward"]                     # forward price of this slice
        sigma = day["atm_iv"]                  # ATM volatility of this slice
        tau = day["dte"] / 365.0               # time to expiry in years

        spread_of_one_sd = sigma * np.sqrt(tau)           # sigma * sqrt(tau)

        target_short = F * np.exp(-K1 * spread_of_one_sd)
        target_long = F * np.exp(-K2 * spread_of_one_sd)

        # ---- step 2: find this day's slice in the Greeks table -----------

        # three True/False columns, one per condition
        same_time = greeks["quote_datetime"] == day["quote_datetime"]
        same_root = greeks["root"] == day["root"]
        same_expiry = greeks["expiration"] == day["expiration"]

        # & means "and": keep only the rows where all three are True
        puts = greeks[same_time & same_root & same_expiry]

        if len(puts) == 0:                     # len() is the number of rows
            print("  no puts found for", day["date"], "- skipped")
            continue

        # ---- step 3: snap to the nearest listed strike -------------------

        short_put = find_put(puts, target_short)
        long_put = find_put(puts, target_long)

        # the short strike must be above the long strike, otherwise it is no spread
        if short_put["strike"] <= long_put["strike"]:
            print("  strikes collapsed on", day["date"], "- skipped")
            continue

        # ---- step 4: the delta of the position ---------------------------

        # s06_greeks.py expects the delta of each put as a negative number,
        # which is what our Greeks files contain
        entry_delta = spread_delta(short_put["delta"],
                                   long_put["delta"],
                                   HOW_MANY_SPREADS)

        # store this day's numbers as a dictionary: name -> value.
        # Each name becomes a column of the output file.
        results.append({
            "date": day["date"],
            "root": day["root"],
            "dte": day["dte"],
            "forward": F,
            "atm_iv": sigma,
            "target_short": target_short,
            "target_long": target_long,
            "strike_short": short_put["strike"],
            "strike_long": long_put["strike"],
            "iv_short": short_put["iv"],
            "iv_long": long_put["iv"],
            "delta_short": short_put["delta"],
            "delta_long": long_put["delta"],
            "entry_delta": entry_delta,
        })

    return results


def main():

    print("loading", ATM_FILE, "...")

    # quote_datetime and expiration are kept as text on purpose (no parse_dates)
    atm = pd.read_csv(ATM_FILE)

    print(len(atm), "rows")

    one_per_day = pick_one_expiry_per_day(atm)

    print(len(one_per_day), "days with an entry at", ENTRY_TIME)

    # the month as text, for example "2021-06" (the first 7 characters of the date)
    one_per_day["month"] = one_per_day["date"].str[:7]

    # decide which months to run
    if len(TEST_MONTHS) > 0:
        months = TEST_MONTHS
    else:
        # unique() lists each month once, sorted() puts them in time order
        months = sorted(one_per_day["month"].unique())

    all_results = []                           # will collect the days of all months

    for month in months:

        # the rows (days) that belong to this month
        days = one_per_day[one_per_day["month"] == month]

        if len(days) == 0:
            print("no days found for", month)
            continue                           # skip to the next month

        month_results = process_one_month(month, days)

        # + on two lists glues them together into one longer list
        all_results = all_results + month_results

    # a list of dictionaries becomes a table: one row per dictionary,
    # one column per name
    table = pd.DataFrame(all_results)

    # index=False: do not write pandas' row numbers into the file
    table.to_csv(OUT_FILE, index=False)

    print()
    print("saved", len(table), "days to", OUT_FILE)
    print()

    # ---- the summary ------------------------------------------------------

    d = table["entry_delta"]                   # a short name for the column

    print("entry delta of the two spreads:")
    print("  lowest  ", round(d.min(), 4))
    print("  mean    ", round(d.mean(), 4))
    print("  median  ", round(d.median(), 4))
    print("  highest ", round(d.max(), 4))
    print()

    print("quantiles:")
    for level in [0.05, 0.25, 0.50, 0.75, 0.95]:
        # quantile(0.05) is the value below which 5% of the days lie
        print("  ", int(level * 100), "%  ", round(d.quantile(level), 4))
    print()

    # the value if both legs used the same volatility (from the thesis):
    # N(2.3) - N(1) per spread, where norm.cdf is N, the normal distribution
    flat_one_spread = norm.cdf(K2) - norm.cdf(K1)
    flat_value = HOW_MANY_SPREADS * flat_one_spread

    print("for comparison:")
    print("  flat-volatility value    ", round(flat_value, 4))
    print("  methodology report       ", 0.2833)
    print()

    # how far the snapped strikes are from the targets, in index points
    # (one column minus another works row by row; .abs() removes the sign)
    snap_short = (table["strike_short"] - table["target_short"]).abs()
    snap_long = (table["strike_long"] - table["target_long"]).abs()

    print("distance between target strike and listed strike (index points):")
    print("  short leg, largest ", round(snap_short.max(), 2))
    print("  long leg,  largest ", round(snap_long.max(), 2))
    print()

    print("average volatility of the legs:")
    print("  ATM      ", round(table["atm_iv"].mean(), 4))
    print("  short put", round(table["iv_short"].mean(), 4))
    print("  long put ", round(table["iv_long"].mean(), 4))


main()
