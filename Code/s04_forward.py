"""
THE FORWARD PRICE

What this file is for:
    To price an option we need to know what the market thinks the S&P 500
    will be worth at expiry. That number is called the FORWARD price, F.

    F is not the same as today's index level, because the index pays
    dividends between now and expiry.

    We could try F = spot * exp((r - q) * tau), but we do not know q, the
    dividend yield, and it is not in our data.

    Instead we use PUT-CALL PARITY, which gives F straight from the option
    prices themselves:

        C - P = D * (F - K)          so         F = K + (C - P) / D

    where C and P are a call and a put with the SAME strike K and the SAME
    expiry, and D is the discount factor from s03_rates.py.

    This needs no dividend estimate at all.

To check it works, run:   python Code/s04_forward.py
"""

import numpy as np
import pandas as pd


def forward_from_slice(slice_table, D, how_many_strikes=8):
    """
    Work out the forward price F for ONE moment in time and ONE expiry.

      slice_table      : rows for a single quote_datetime, root and expiration
      D                : the discount factor for that expiry
      how_many_strikes : how many strikes near the money to average over

    Returns one number, or nan if there is not enough data.
    """

    # Split the slice into calls and puts.
    # slice_table["option_type"] == "C" gives one True/False per row, and
    # slice_table[...] keeps the rows that are True.
    calls = slice_table[slice_table["option_type"] == "C"]
    puts = slice_table[slice_table["option_type"] == "P"]

    # We only want the strike and the price from each
    calls = calls[["strike", "mid"]]
    puts = puts[["strike", "mid"]]

    # Join them on strike, so each row has a call AND a put at the same strike.
    # "inner" means keep only strikes that have both.
    # Both tables have a column called "mid"; suffixes renames them to
    # "mid_call" and "mid_put" in the result, so they can be told apart.
    pairs = calls.merge(puts, on="strike", how="inner", suffixes=("_call", "_put"))

    if len(pairs) < 3:                          # too few pairs to trust
        return np.nan

    # The difference between the call and the put at each strike
    pairs["difference"] = pairs["mid_call"] - pairs["mid_put"]

    # At the money, a call and a put cost almost the same, so the difference
    # is closest to zero there. That strike is called K0.
    # .abs() removes the sign; .idxmin() gives the LABEL of the row with the
    # smallest value (not its value)
    row_of_K0 = pairs["difference"].abs().idxmin()      # which row has the smallest |difference|

    # .loc[row label, column name] reads one cell by its labels
    K0 = pairs.loc[row_of_K0, "strike"]                 # the strike in that row

    # How far each strike is from K0
    pairs["distance"] = (pairs["strike"] - K0).abs()

    # Keep only the strikes closest to K0. Strikes far from the money give a
    # much noisier answer, so we do not use them.
    pairs = pairs.sort_values("distance")               # closest to K0 first
    pairs = pairs.head(how_many_strikes)                # .head(8) keeps the first 8 rows

    # Apply the formula to each of those strikes separately
    forwards = pairs["strike"] + pairs["difference"] / D

    # Each strike gives a slightly different answer because of bid-ask noise.
    # The median is the middle value, which ignores any odd ones.
    return float(forwards.median())


def all_forwards(day_table, rates_table, discount_factor_function):
    """
    Work out F for every (time, root, expiry) slice in one day of data.

      day_table                : cleaned option data for one or more days
      rates_table              : the table from rates.load_rates()
      discount_factor_function : rates.discount_factor

    Returns a small table with one row per slice.
    """

    results = []                                    # empty list to collect the answers

    # Group the data into slices. Each slice is one moment in time, one root,
    # one expiry. We must NOT mix roots: an SPX option and an SPXW option
    # expiring the same week settle differently, so they are not a parity pair.
    # groupby splits the table into one small table per combination of
    # (time, root, expiry). Looping over it gives, each time, the three values
    # of the combination (group_name) and that slice's rows (slice_table).
    grouped = day_table.groupby(["quote_datetime", "root", "expiration"])

    for group_name, slice_table in grouped:

        when, root, expiry = group_name             # unpack the three grouping values

        # .iloc[0] is the first row by position; every row of a slice has the
        # same dte, so the first one will do
        days = slice_table["dte"].iloc[0]           # days to expiry for this slice

        the_date = when.normalize()                 # the date, with the time removed

        D = discount_factor_function(rates_table, the_date, days)

        F = forward_from_slice(slice_table, D)

        spot = slice_table["spot"].iloc[0]          # the index level, for comparison

        results.append({                            # store one row of answers
            "quote_datetime": when,
            "root": root,
            "expiration": expiry,
            "dte": days,
            "spot": spot,
            "D": D,
            "forward": F,
        })

    return pd.DataFrame(results)                    # turn the list of rows into a table


# ----------------------------------------------------------------------
# Only runs if you type:  python Code/s04_forward.py
# ----------------------------------------------------------------------

if __name__ == "__main__":

    import s03_rates as rates                       # our own s03_rates.py

    CLEAN_FILE = "Data/02_clean/spx_2024-08.csv"    # <-- change to a file you have

    print("loading rates...")
    rates_table = rates.load_rates()

    print("loading option data...")
    data = pd.read_csv(CLEAN_FILE, parse_dates=["quote_datetime", "expiration"])

    # Just one moment in time, to keep the test small
    one_moment = data["quote_datetime"].unique()[20]
    data = data[data["quote_datetime"] == one_moment]

    print("using", one_moment)
    print()

    answers = all_forwards(data, rates_table, rates.discount_factor)

    answers = answers.sort_values("dte")            # shortest expiry first

    # How far the forward is from spot, as a percentage
    answers["percent_above_spot"] = (answers["forward"] / answers["spot"] - 1) * 100

    # print only the columns we care about, rounded to 4 decimals
    shown = answers[["root", "expiration", "dte", "spot", "forward", "percent_above_spot"]]
    shown = shown.copy()
    shown["expiration"] = shown["expiration"].dt.date        # drop the time from the date
    shown["forward"] = shown["forward"].round(2)
    shown["percent_above_spot"] = shown["percent_above_spot"].round(4)
    print(shown.to_string(index=False))

    # ---- a check: some expiries have BOTH an SPX and an SPXW contract -----
    # They are different products, priced separately by the market, but they
    # expire on the same day. So they should give the same forward.
    print()
    print("Same expiry, different root - do they agree?")

    for expiry in answers["expiration"].unique():

        both = answers[answers["expiration"] == expiry]

        if len(both) < 2:                           # only one root for this expiry
            continue

        biggest = both["forward"].max()
        smallest = both["forward"].min()

        print("  ", pd.Timestamp(expiry).date(),
              " difference =", round(biggest - smallest, 3), "index points")
