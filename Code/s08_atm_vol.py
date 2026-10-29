"""
AT-THE-MONEY VOLATILITY

What this file is for:
    Your strategy picks strikes with

        K = S * exp( -k * sigma * sqrt(tau) )

    where sigma is the AT-THE-MONEY volatility. "At the money" means the
    strike equals the forward, K = F.

    There is almost never a listed strike exactly at F, so we cannot just
    look one up. Instead we fit a smooth curve through the volatilities of
    the strikes near the money, and read off the value at K = F.

    The result is one number per (moment in time, root, expiry). We save
    them all into one small file, which is also what we will use to decide
    what counts as a "stress phase".

HOW TO RUN IT
    python Code/s08_atm_vol.py

CHANGED 2026-10-27 (review_log.md C3 and C15; the version before is the one
in commit 4aca3ae, tag thesis-v1):
  - each month's result is first saved on its own in PARTS_FOLDER. A month
    already saved there is not done again, and a month that fails is reported
    and the run carries on. So the run can be stopped and started again, and a
    crash after hours costs only the month it happened in. At the end the
    months are put together into OUT_FILE exactly as before.
    WARNING: a month already in PARTS_FOLDER is never recomputed. Before a
    rerun on changed Greeks files, delete PARTS_FOLDER, or the old months are
    used again without any message. (The folder of the C15 run was deleted
    on 2026-10-29, after OUT_FILE was written.)
  - the recorded index quote spot_quote is saved next to spot.
  - main() only runs when this file is started directly (review_log.md C4).
"""

import os
import glob

import numpy as np
import pandas as pd


GREEKS_FOLDER = "Data/04_greeks"           # where stage 2 put its files
OUT_FILE = "Data/05_atm_vol.csv"           # the one file this produces
PARTS_FOLDER = "Data/05_atm_vol_parts"     # one file per month, put together at the end

WIDTH = 0.05                               # use strikes within 5% of the forward


def atm_vol_for_slice(strikes, ivs, option_types, F):
    """
    Work out the volatility at K = F for one slice.

      strikes      : the strikes in this slice
      ivs          : their implied volatilities
      option_types : "C" or "P" for each one
      F            : the forward price

    Returns one number, or nan if there is not enough data.
    """

    # Measure each strike as a distance from the forward, on a log scale.
    # log_moneyness is 0 exactly at the money, negative below, positive above.
    log_moneyness = np.log(strikes / F)

    # Use only out-of-the-money options: puts below the forward, calls above.
    # Those are the ones that are actively quoted, so their prices are best.
    # np.where(condition, a, b), element by element: for a call take the test
    # "log_moneyness >= 0" (above the forward), for a put "log_moneyness < 0"
    is_call = option_types == "C"
    use_this_one = np.where(is_call, log_moneyness >= 0, log_moneyness < 0)

    # Only keep the ones near the money, and only ones with a real volatility
    near_the_money = np.abs(log_moneyness) < WIDTH
    has_a_volatility = np.isfinite(ivs)    # isfinite is False for nan (and infinity)

    # & = "and": keep the options that pass all three tests
    keep = use_this_one & near_the_money & has_a_volatility

    # keep.sum() counts the Trues (True counts as 1)
    if keep.sum() < 3:                     # not enough points to fit a curve
        return np.nan

    # array[keep] keeps only the elements where keep is True
    x = log_moneyness[keep]                # the distances from the money
    y = ivs[keep]                          # the volatilities

    # Fit a parabola (a curve of the form a*x^2 + b*x + c) through the points.
    # A parabola, rather than a straight line, because the smile is curved.
    # np.polyfit(x, y, 2) finds the a, b, c of the best-fitting parabola
    # (least squares) and returns them as [a, b, c].
    coefficients = np.polyfit(x, y, 2)

    # Read the fitted curve off at x = 0, which is exactly at the money.
    # np.polyval(coefficients, 0) evaluates a*0^2 + b*0 + c, which is just c.
    return float(np.polyval(coefficients, 0.0))


def process_one_file(path):
    """Read one month of greeks, return one row per slice."""

    # parse_dates: turn these two text columns into real dates while reading
    data = pd.read_csv(path, parse_dates=["quote_datetime", "expiration"])

    results = []                                    # one dictionary per slice goes in

    # groupby splits the month into one small table per (time, root, expiry);
    # each step of the loop gives the three values and that slice's rows
    grouped = data.groupby(["quote_datetime", "root", "expiration"])

    for group_name, slice_table in grouped:

        when, root, expiry = group_name             # unpack the three values

        # .iloc[0] = the first row by position
        F = slice_table["forward"].iloc[0]          # same for every row in the slice

        # .values turns each column into a plain numpy array
        sigma = atm_vol_for_slice(
            slice_table["strike"].values,
            slice_table["iv"].values,
            slice_table["option_type"].values,
            F,
        )

        results.append({
            "quote_datetime": when,
            "root": root,
            "expiration": expiry,
            "dte": slice_table["dte"].iloc[0],
            "spot": slice_table["spot"].iloc[0],
            "spot_quote": slice_table["spot_quote"].iloc[0],    # the recorded index quote (C15)
            "forward": F,
            "atm_iv": sigma,
        })

    # a list of dictionaries becomes a table: one row per slice
    return pd.DataFrame(results)


def main():

    # glob finds all file names matching the pattern (* = anything), sorted by name
    files = sorted(glob.glob(GREEKS_FOLDER + "/*.csv"))
    print("found", len(files), "files")

    if len(files) == 0:
        print("Nothing found. Check GREEKS_FOLDER is spelled correctly.")
        return

    # make the folder for the monthly parts; exist_ok=True: no error if it exists
    os.makedirs(PARTS_FOLDER, exist_ok=True)

    failed_months = []                     # the months that went wrong, if any

    # enumerate gives a counter (starting at 1) alongside each file
    for number, path in enumerate(files, 1):

        name = os.path.basename(path)      # the file name without the folder
        part_path = PARTS_FOLDER + "/" + name

        if os.path.exists(part_path):      # done on an earlier run
            print(number, "/", len(files), name, "already done, skipping")
            continue

        # try / except: if anything goes wrong with one month, report it and
        # carry on with the next one instead of losing the whole run
        try:
            result = process_one_file(path)
        except Exception as problem:
            print(number, "/", len(files), name, "FAILED:", problem)
            failed_months.append(name)
            continue

        # save the month: first under a temporary name, then rename it, so a
        # half-written file can never look finished
        result.to_csv(part_path + ".part", index=False)
        os.replace(part_path + ".part", part_path)

        # isna() is True where no volatility could be fitted; .sum() counts them
        missing = int(result["atm_iv"].isna().sum())

        print(number, "/", len(files), name,
              "|", len(result), "slices",
              "| could not fit", missing)

    if len(failed_months) > 0:
        print()
        print("These months FAILED, so", OUT_FILE, "is not written:", failed_months)
        print("Fix the problem and start the file again; finished months are skipped.")
        return

    # read the monthly parts back, one per month, in the order of the months
    pieces = []                            # one table per month goes in
    for path in files:
        part_path = PARTS_FOLDER + "/" + os.path.basename(path)
        # the time and expiry are read as dates, as process_one_file made them
        pieces.append(pd.read_csv(part_path, parse_dates=["quote_datetime", "expiration"]))

    # pd.concat stacks the monthly tables on top of each other into one table
    everything = pd.concat(pieces)

    everything = everything.sort_values("quote_datetime")      # oldest first

    everything["atm_iv"] = everything["atm_iv"].round(6)        # 6 decimals

    # index=False: do not write pandas' row numbers into the file
    everything.to_csv(OUT_FILE, index=False)

    # os.path.getsize gives the file size in bytes; / 1e6 turns it into MB
    size_mb = os.path.getsize(OUT_FILE) / 1e6

    print()
    print("Saved", len(everything), "rows to", OUT_FILE,
          "(", round(size_mb, 1), "MB )")


# Run main() only when this file is started directly (python Code/s08_atm_vol.py),
# not when another file imports it (review_log.md C4, changed 2026-10-27)
if __name__ == "__main__":
    main()
