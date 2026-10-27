"""
STAGE 2 - add the forward, the implied volatility and the greeks.

This reads every file in the Clean folder and writes a new file for each
one into the Greeks folder, with these extra columns:

    forward   what the market expects the index to be worth at expiry
    D         the discount factor
    iv        implied volatility
    delta     how much the option moves when the index moves 1 point
    gamma     how much delta moves when the index moves 1 point
    vega      how much the option moves when volatility rises 1 point
    theta     how much the option loses per day from time passing

HOW TO RUN IT
    python Code/s07_stage2_greeks.py

It skips files it has already done, so you can stop it and start it again.
"""

import os
import glob
import time

import numpy as np
import pandas as pd

import s03_rates as rates                      # our own s03_rates.py
import s04_forward as forward                  # our own s04_forward.py
import s05_volatility as volatility            # our own s05_volatility.py
import s06_greeks as greeks                    # our own s06_greeks.py


# ----------------------------------------------------------------------
# SETTINGS
# ----------------------------------------------------------------------

CLEAN_FOLDER = "Data/02_clean"                 # where stage 1 put its files
OUT_FOLDER = "Data/04_greeks"                  # where this file will put its files

DECIMALS = 6                                   # round the new numbers, to keep files smaller


def process_one_month(path, rates_table):
    """Read one cleaned month, add the new columns, return the table."""

    # parse_dates: turn these two text columns into real dates while reading
    data = pd.read_csv(path, parse_dates=["quote_datetime", "expiration"])

    # ---- step 1: the forward price for every slice --------------------
    # A "slice" is one moment in time, one root, one expiry.

    forwards = forward.all_forwards(data, rates_table, rates.discount_factor)

    # keep only the columns we need to attach back
    # (a list of names inside [ ] picks those columns)
    forwards = forwards[["quote_datetime", "root", "expiration", "forward", "D"]]

    # ---- step 2: attach the forward to every row ----------------------
    # Every option in a slice shares that slice's forward and discount factor.
    #
    # merge works like a lookup (VLOOKUP in Excel): for every row of data it
    # finds the row of forwards with the same time, root and expiry, and copies
    # that row's "forward" and "D" into it.
    # how="left" keeps EVERY row of data, even if no forward was found for it;
    # those rows get an empty value (nan), which we remove just below.

    data = data.merge(forwards, on=["quote_datetime", "root", "expiration"], how="left")

    # throw away rows where the forward could not be worked out
    # (notna() is True where there IS a number)
    data = data[data["forward"].notna()]

    if len(data) == 0:
        return None

    # ---- step 3: time to expiry, as a fraction of a year --------------

    # .values turns the column into a plain numpy array of numbers, which the
    # formulas in s05_volatility.py and s06_greeks.py work on all at once
    tau = data["dte"].values / 365.0

    # np.maximum compares element by element and keeps the larger of the two,
    # so every tau below one day is raised to one day
    tau = np.maximum(tau, 1.0 / 365.0)          # never let tau be zero

    # ---- step 4: implied volatility for every option ------------------

    # one True/False per row: True for a call, False for a put
    is_call = (data["option_type"] == "C").values

    data["iv"] = volatility.implied_volatility(
        data["mid"].values,
        data["forward"].values,
        data["strike"].values,
        tau,
        data["D"].values,
        is_call,
    )

    # ---- step 5: the greeks -------------------------------------------

    g = greeks.all_greeks(
        data["forward"].values,
        data["strike"].values,
        tau,
        data["iv"].values,
        data["D"].values,
        is_call,
        data["spot"].values,
    )

    # g is a dictionary (see greeks.all_greeks); put each greek in its own column
    data["delta"] = g["delta"]
    data["gamma"] = g["gamma"]
    data["vega"] = g["vega"]
    data["theta"] = g["theta"]

    # ---- step 6: tidy up ----------------------------------------------

    for column in ["forward", "D", "iv", "delta", "gamma", "vega", "theta"]:
        data[column] = data[column].round(DECIMALS)     # round to 6 decimals

    return data


def main():

    print("loading the rate curve...")
    rates_table = rates.load_rates()

    # glob finds all file names matching a pattern; * means "anything".
    # sorted() puts them in order, i.e. oldest month first.
    files = sorted(glob.glob(CLEAN_FOLDER + "/*.csv"))
    print("found", len(files), "cleaned files")

    if len(files) == 0:
        print("Nothing found. Check CLEAN_FOLDER is spelled correctly.")
        return

    # make the output folder; exist_ok=True means "no error if it already exists"
    os.makedirs(OUT_FOLDER, exist_ok=True)

    started = time.time()                        # the clock time now, in seconds

    # enumerate gives a counter alongside each file: (1, first file), (2, second
    # file), ... The 1 means "start counting at 1" (the default would be 0).
    for number, path in enumerate(files, 1):

        name = os.path.basename(path)                    # e.g. "spx_2024-08.csv"
        out_path = OUT_FOLDER + "/" + name

        if os.path.exists(out_path):                     # already done earlier
            print(number, "/", len(files), name, "already done, skipping")
            continue

        # try / except: if anything goes wrong inside process_one_month, do not
        # stop the whole run. Print the error and carry on with the next month.
        try:
            result = process_one_month(path, rates_table)
        except Exception as problem:
            print(number, "/", len(files), name, "FAILED:", problem)
            continue                                     # go to the next file

        if result is None:
            print(number, "/", len(files), name, "no usable rows")
            continue

        # index=False: do not write pandas' row numbers into the file
        result.to_csv(out_path, index=False)

        # how many options we could not find a volatility for.
        # isna() is True where the value is empty; .sum() counts the Trues
        # (True counts as 1, False as 0).
        failed = int(result["iv"].isna().sum())
        share_failed = 100.0 * failed / len(result)

        minutes_so_far = (time.time() - started) / 60.0

        print(number, "/", len(files), name,
              "|", len(result), "rows",
              "| iv failed on", round(share_failed, 2), "%",
              "|", round(minutes_so_far, 1), "min so far")

    print()
    print("Done. Files are in the", OUT_FOLDER, "folder.")


# runs as soon as the file is started. (Note: this also runs if another file
# imports s07_stage2_greeks, so do not import it; start it with python Code/s07_stage2_greeks.py)
main()
