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

CHANGED 2026-10-27 (review_log.md C15; the version before is in
old_versions/s01_stage1_extract_simple_2026-10-27_before_c15.py):
  - the index level S at the snapshot after the stock close (16:15, or 13:15 on
    early-close days) is the official daily close of the index, because the
    index quote there is no longer a price. At every other snapshot S is the
    middle of the index quote, as before. The recorded quote is kept in its
    own column, spot_quote.
  - puts are kept down to K/S = 0.30 (was 0.45), so that the data cover every
    bought put the strategy can choose (thesis, after prop:credit-maturity: down
    to 38% of the forward) with room for a rally while it is held.
  - each month is written under a temporary name first (".part") and renamed
    when complete, so a crash while writing cannot leave half a month behind
    that a later run would skip (review_log.md C7).
  - main() only runs when this file is started directly, not when another
    file imports it (review_log.md C4), so its functions can be tested.
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

PUT_LOW = 0.30                  # notebook cell 11 (0.45 there; widened 2026-10-27, see above)
PUT_HIGH = 1.08

CALL_LOW = 0.97                 # notebook cell 12
CALL_HIGH = 1.03

MIN_BID = 0.025                 # notebook cell 14

# the official daily close of the S&P 500 (Yahoo, symbol ^GSPC, one row per day,
# made by checks/fetch_gspc.py). Used as S at the snapshot after the stock close.
INDEX_CLOSE_FILE = "Data/07_index_close/GSPC_daily.csv"

# Output format: "csv" is easy to open in Excel, "parquet" is ~11x smaller,
# ~6x faster to read, and remembers that dates are dates.
FILE_FORMAT = "csv"


# ----------------------------------------------------------------------
# The official close, read once at the start.
# ----------------------------------------------------------------------

def load_official_closes():
    """
    Read the official daily close of the S&P 500 (INDEX_CLOSE_FILE).

    Returns a dictionary: date as text, e.g. "2020-03-16" -> close, e.g. 2386.13.
    """

    table = pd.read_csv(INDEX_CLOSE_FILE)

    closes = {}                                # empty dictionary, filled below

    # iterrows() goes through the table one row at a time; _ is the row label,
    # which we do not need, and row is the row itself
    for _, row in table.iterrows():
        date = str(row["Date"])[:10]           # the first 10 characters: "2020-03-16"
        closes[date] = float(row["Close"])

    return closes


# ----------------------------------------------------------------------
# This function is the whole notebook, for ONE file.
# ----------------------------------------------------------------------

def clean_one_file(path, close):
    """
    Read one raw CSV (one trading day), apply the six filters, return the
    cleaned table. close is the official close of the index on that day.
    """

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
    df["spot_quote"] = (df["underlying_bid"] + df["underlying_ask"]) / 2  # middle of the index quote, as recorded
    df["spot"] = df["spot_quote"]                                   # S, the index level used from here on

    # --- the snapshot after the stock close (review_log.md C8, C15) ------
    # The stocks stop at 16:00 (13:00 on early-close days), the options are
    # quoted until 16:15 (13:15). At that last snapshot the index quote is no
    # longer a price, so S there is the official close of the day.
    # The time of each row as a number: 16:15 -> 16 * 100 + 15 = 1615.
    # .dt.hour and .dt.minute take the hour and the minute out of a date-time.
    hhmm = df["quote_datetime"].dt.hour * 100 + df["quote_datetime"].dt.minute
    if hhmm.max() == 1315:                     # the day ends at 13:15: an early close
        after_close = 1315
    else:                                      # a normal day, ending at 16:15
        after_close = 1615
    is_after_close = hhmm == after_close       # True for the rows of that snapshot
    # .loc[rows, column] = value changes only the rows where is_after_close is True
    df.loc[is_after_close, "spot"] = close

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
    # (spot_quote added 2026-10-27: the recorded index quote, which differs from
    # spot only at the snapshot after the close)
    wanted = ["quote_datetime", "root", "expiration", "dte", "strike",
              "option_type", "bid", "ask", "mid", "spot", "spot_quote"]
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

    # the official close of every day, read once
    closes = load_official_closes()
    print("official closes:", len(closes), "days")

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
            # the day's date from the file name, as above, e.g. "2012-09-28"
            date = os.path.basename(f)[-14:-4]
            # Without an official close the day cannot be cleaned correctly.
            # Stop the whole run (rather than silently dropping the day): this
            # is outside the try below on purpose.
            if date not in closes:
                raise SystemExit("no official close for " + date + " in " + INDEX_CLOSE_FILE + " - stopping")
            # try / except: if one file is broken, print the problem and go on
            try:
                cleaned = clean_one_file(f, closes[date])
                if cleaned is not None:
                    pieces.append(cleaned)
            except Exception as e:               # a broken file should not stop everything
                print("   PROBLEM with", os.path.basename(f), ":", e)

        if len(pieces) == 0:
            print(month, "no usable rows")
            continue

        table = pd.concat(pieces)                # stack all the days of this month

        # Write under a temporary name first and rename when complete (C7): if
        # the program is stopped while writing, only the ".part" file is
        # incomplete, and the month is done again on the next run.
        part_path = out_path + ".part"
        if FILE_FORMAT == "csv":                 # save in whichever format was chosen
            table.to_csv(part_path, index=False)
        else:
            table.to_parquet(part_path, index=False)
        os.replace(part_path, out_path)          # rename: the month file only appears once complete

        size_mb = os.path.getsize(out_path) / 1e6
        print(month, ":", len(table), "rows,", round(size_mb, 1), "MB,",
              len(pieces), "days")

    print("\nDone. Cleaned files are in the", OUT_FOLDER, "folder.")


# Run main() only when this file is started directly (python Code/s01_...py),
# not when another file imports it to use clean_one_file (review_log.md C4).
# Python sets __name__ to "__main__" only for the file that was started.
if __name__ == "__main__":
    main()
