"""
STAGE 1 - clean all the raw CSV files and save them, one file per month.
(As CSV: see FILE_FORMAT below. Parquet is possible but was not used.)

This is the notebook (stage1_simple.ipynb) wrapped in a loop.
The function clean_one_file() below does exactly what cells 4 to 16 do.

HOW TO RUN IT
  1. Run it from the project folder (the one that holds Data/01_raw_options).
  2. Edit RAW_FOLDER and OUT_FOLDER below if your folders are named differently.
  3. In PowerShell:   python Code/s01_stage1_extract_simple.py

It is safe to stop it and run it again - it skips months it already finished.
"""

import os                       # for looking at files and folders
import glob                     # for finding all files matching a pattern
import pandas as pd


# ----------------------------------------------------------------------
# SETTINGS - the only things you should need to change
# ----------------------------------------------------------------------

RAW_FOLDER = "Data/01_raw_options"  # folder holding the raw CSV files
OUT_FOLDER = "Data/02_clean"    # folder where the cleaned files will go

GOOD_ROOTS = ["SPX", "SPXW", "SPXQ"]   # notebook cell 4

DTE_MIN = 4                     # notebook cell 7
DTE_MAX = 100

PUT_LOW = 0.45                  # notebook cell 11
PUT_HIGH = 1.08

CALL_LOW = 0.97                 # notebook cell 12
CALL_HIGH = 1.03

MIN_BID = 0.025                 # notebook cell 14

# Output format: "csv" is easy to open in Excel, "parquet" is ~11x smaller,
# ~6x faster to read, and remembers that dates are dates.
FILE_FORMAT = "csv"


# ----------------------------------------------------------------------
# This function is the whole notebook, for ONE file.
# ----------------------------------------------------------------------

def clean_one_file(path):
    """Read one raw CSV, apply the six filters, return the cleaned table."""

    # --- notebook cell 1: read the file ---------------------------------
    raw = pd.read_csv(path)

    # --- notebook cell 4: keep only the vanilla roots --------------------
    mask = raw["root"].isin(GOOD_ROOTS)         # True where root is one we want
    df = raw[mask].copy()                       # keep those rows, make our own copy

    if len(df) == 0:                            # nothing left? tell the caller
        return None

    # --- notebook cell 5: turn the text dates into real dates ------------
    df["expiration"] = pd.to_datetime(df["expiration"])
    df["quote_datetime"] = pd.to_datetime(df["quote_datetime"])

    # --- notebook cell 6: how many days until expiry ---------------------
    trade_day = df["quote_datetime"].dt.normalize()     # today's date, time removed
    df["dte"] = (df["expiration"] - trade_day).dt.days  # subtract, then take whole days

    # --- notebook cell 7: keep 4 to 100 days -----------------------------
    long_enough = df["dte"] >= DTE_MIN
    short_enough = df["dte"] <= DTE_MAX
    df = df[long_enough & short_enough]         # & = "and": keep rows where both are True

    if len(df) == 0:
        return None

    # --- notebook cells 8 and 9: spot price and moneyness ----------------
    df = df.copy()                                                  # copy again after filtering
    df["spot"] = (df["underlying_bid"] + df["underlying_ask"]) / 2  # middle of the index quote
    df["moneyness"] = df["strike"] / df["spot"]                     # strike as a fraction of spot

    # --- notebook cell 10: split into puts and calls ---------------------
    puts = df[df["option_type"] == "P"]
    calls = df[df["option_type"] == "C"]

    # --- notebook cells 11 and 12: different strike range for each -------
    puts = puts[(puts["moneyness"] >= PUT_LOW) & (puts["moneyness"] <= PUT_HIGH)]
    calls = calls[(calls["moneyness"] >= CALL_LOW) & (calls["moneyness"] <= CALL_HIGH)]

    # --- notebook cell 13: glue them back together -----------------------
    df = pd.concat([puts, calls])

    # --- notebook cell 14: throw away broken quotes ----------------------
    has_bid = df["bid"] >= MIN_BID              # someone is actually buying
    not_crossed = df["ask"] > df["bid"]         # the quote makes sense
    df = df[has_bid & not_crossed].copy()

    if len(df) == 0:
        return None

    # --- notebook cell 15: our price is the middle of bid and ask --------
    df["mid"] = (df["bid"] + df["ask"]) / 2

    # --- notebook cell 16: keep only the columns we need -----------------
    wanted = ["quote_datetime", "root", "expiration", "dte", "strike",
              "option_type", "bid", "ask", "mid", "spot"]
    return df[wanted]


# ----------------------------------------------------------------------
# The loop. This is the only part that is NOT in the notebook.
# ----------------------------------------------------------------------

def main():
    # find every CSV inside the raw folder.
    # os.path.join glues folder names together with the right separator.
    # "**" with recursive=True means "in this folder or any folder inside it".
    pattern = os.path.join(RAW_FOLDER, "**", "*.csv")
    files = sorted(glob.glob(pattern, recursive=True))
    print("found", len(files), "CSV files in", RAW_FOLDER)

    if len(files) == 0:
        print("No files found. Check that RAW_FOLDER is spelled correctly.")
        return

    # make the output folder if it does not exist yet
    os.makedirs(OUT_FOLDER, exist_ok=True)

    # Sort the files into months, so we end up with ~170 output files
    # instead of ~3500. The file names contain a date like 2012-09-28,
    # so we look for that and keep the first 7 characters: "2012-09".
    months = {}                                  # a dictionary: month -> list of files
    for f in files:
        name = os.path.basename(f)               # just the file name, no folders
        # negative positions count from the end: [-14:-4] are the 10 characters
        # that end 4 characters before the end, i.e. just before ".csv"
        date_part = name[-14:-4]                 # the "2012-09-28" bit before ".csv"
        month = date_part[:7]                    # "2012-09"
        if month not in months:
            months[month] = []                   # first file of this month
        months[month].append(f)

    # now process one month at a time
    for month in sorted(months):
        out_path = os.path.join(OUT_FOLDER, "spx_" + month + "." + FILE_FORMAT)

        if os.path.exists(out_path):             # already done on an earlier run
            print(month, "already done, skipping")
            continue

        pieces = []                              # will hold one cleaned table per day
        for f in months[month]:
            # try / except: if one file is broken, print the problem and go on
            try:
                cleaned = clean_one_file(f)
                if cleaned is not None:
                    pieces.append(cleaned)
            except Exception as e:               # a broken file should not stop everything
                print("   PROBLEM with", os.path.basename(f), ":", e)

        if len(pieces) == 0:
            print(month, "no usable rows")
            continue

        table = pd.concat(pieces)                # stack all the days of this month

        if FILE_FORMAT == "csv":                 # save in whichever format was chosen
            table.to_csv(out_path, index=False)
        else:
            table.to_parquet(out_path, index=False)

        size_mb = os.path.getsize(out_path) / 1e6
        print(month, ":", len(table), "rows,", round(size_mb, 1), "MB,",
              len(pieces), "days")

    print("\nDone. Cleaned files are in the", OUT_FOLDER, "folder.")


main()
