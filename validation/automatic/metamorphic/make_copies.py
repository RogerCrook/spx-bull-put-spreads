"""
Metamorphic tests, part 1 of 3: build the changed copies of the data.

What this file is for
---------------------
A metamorphic test runs the code twice, on an input and on a copy changed in a known
way, and checks that the output changes in the known way (test specification,
method 5). This script builds the copies. It only READS the project's Data/ folder
and WRITES only into WORK_FOLDER, a folder outside the project (about 4 GB).

The copies (each a folder with its own Data/ inside, laid out like the project's,
because the pipeline scripts read "Data/..." relative to where they are started):

  stage2_original        one cleaned month (02_clean), unchanged          for F8
  stage2_times2          the same month, every price, strike and S x 2    for F8
  backtest_original      two months of 04_greeks, their 05_atm_vol rows,
                         all of 06_vol30, unchanged                       reference
  backtest_times2        prices, strikes, S, F x 2, gamma / 2, vega and
                         theta x 2 (iv and delta unchanged)               S34
  backtest_bid_equals_ask  bid = ask = mid on every quote                 S25
  backtest_cut           every row after CUT_DAY removed                  S31, S23, D14
  backtest_random_stress the 30-day vol, threshold and flag replaced by
                         random numbers                                   S32

Every copy also gets the T-bill yields (Data/03_treasury_bills), unchanged.

How to run (from the main folder; reads about 1 GB, writes about 4 GB, a few minutes):
    python validation/automatic/metamorphic/make_copies.py

Then run_on_copy.py runs the code inside each copy, and compare.py compares.
Delete WORK_FOLDER afterwards to free the space.
"""

import csv              # reads and writes CSV files row by row
import os               # folders and paths
import random           # random numbers for the stress copy
import shutil           # copying whole files
import tempfile         # the computer's temporary folder


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# Where the copies go: a folder in the computer's temporary folder, outside the
# project (so the iCloud backup never copies 4 GB of test data).
WORK_FOLDER = os.path.join(tempfile.gettempdir(), "masterarbeit_metamorphic")

STAGE2_MONTH = "2012-01"                 # smallest cleaned month (21 MB), for the F8 test
BACKTEST_MONTHS = ["2020-02", "2020-03"] # choice: a calm month and the crash (broken
                                         # quotes on 9 and 16 March, legs missing 20 March)
CUT_DAY = "2020-03-10"                   # the cut copy keeps the days up to and including this
SCALE = 2.0                              # choice: x 2 is exact in binary floating point,
                                         # so the doubled numbers carry no new rounding
RANDOM_SEED = 20261118                   # fixed, so a rerun builds the same random copy

# The columns that are prices or index levels, so they scale with SCALE.
CLEAN_PRICE_COLUMNS = ["strike", "bid", "ask", "mid", "spot", "spot_quote"]
GREEKS_PRICE_COLUMNS = ["strike", "bid", "ask", "mid", "spot", "spot_quote", "forward"]
ATM_PRICE_COLUMNS = ["spot", "spot_quote", "forward"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_folder(path):
    """Make a folder and any missing folders above it (no error if it exists)."""
    os.makedirs(path, exist_ok=True)


def scaled_text(text, factor):
    """
    Multiply a number written as text by a factor and write it back as text.
    An empty field stays empty.

    Example:  scaled_text("12.8", 2.0) -> "25.6",   scaled_text("", 2.0) -> ""
    """
    if text == "":
        return ""
    value = float(text) * factor
    return repr(value)          # repr writes the number so it reads back exactly the same


def copy_rates(copy_folder):
    """Copy the four T-bill yield files into the copy's Data/03_treasury_bills."""
    target = os.path.join(copy_folder, "Data", "03_treasury_bills")
    make_folder(target)
    for name in os.listdir("Data/03_treasury_bills"):          # every file in the folder
        shutil.copy(os.path.join("Data/03_treasury_bills", name), target)


def rewrite_csv(source, target, change_row):
    """
    Read a CSV file line by line and write it to target, passing every row through
    change_row(header, row). change_row returns the changed row (a list of texts),
    or None to leave the row out.
    """
    make_folder(os.path.dirname(target))
    with open(source, newline="") as file_in, open(target, "w", newline="") as file_out:
        reader = csv.reader(file_in)               # each line as a list of texts
        writer = csv.writer(file_out)
        header = next(reader)                      # the column names
        writer.writerow(header)
        for row in reader:
            new_row = change_row(header, row)
            if new_row is not None:
                writer.writerow(new_row)


# ---------------------------------------------------------------------------
# The changes, one function per kind
# ---------------------------------------------------------------------------

def unchanged(header, row):
    """Keep the row as it is."""
    return row


def clean_times2(header, row):
    """A cleaned row with every price, strike and S multiplied by SCALE."""
    for column in CLEAN_PRICE_COLUMNS:
        position = header.index(column)            # where the column is in the row
        row[position] = scaled_text(row[position], SCALE)
    return row


def greeks_times2(header, row):
    """
    A row of 04_greeks with prices, strikes, S and F multiplied by SCALE. The
    Greeks change as Black-76 says they must (prop:black76 homogeneity, F8):
    iv and delta unchanged, gamma / SCALE, vega and theta x SCALE.
    """
    for column in GREEKS_PRICE_COLUMNS:
        position = header.index(column)
        row[position] = scaled_text(row[position], SCALE)
    gamma = header.index("gamma")
    row[gamma] = scaled_text(row[gamma], 1 / SCALE)
    for column in ["vega", "theta"]:
        position = header.index(column)
        row[position] = scaled_text(row[position], SCALE)
    return row


def greeks_bid_equals_ask(header, row):
    """A row of 04_greeks with bid and ask both set to the mid."""
    mid = row[header.index("mid")]
    row[header.index("bid")] = mid
    row[header.index("ask")] = mid
    return row


def keep_until_cut(header, row):
    """Keep a row only if its date is on or before CUT_DAY (the first column holds the time or date)."""
    if row[0][:10] > CUT_DAY:                      # dates as "YYYY-MM-DD" compare in time order as text
        return None
    return row


def atm_in_months(header, row):
    """Keep a row of 05_atm_vol only if it lies in one of BACKTEST_MONTHS."""
    if row[0][:7] in BACKTEST_MONTHS:
        return row
    return None


def atm_times2(header, row):
    """A row of 05_atm_vol in BACKTEST_MONTHS with S and F multiplied by SCALE (atm_iv unchanged)."""
    if row[0][:7] not in BACKTEST_MONTHS:
        return None
    for column in ATM_PRICE_COLUMNS:
        position = header.index(column)
        row[position] = scaled_text(row[position], SCALE)
    return row


def atm_until_cut(header, row):
    """A row of 05_atm_vol in BACKTEST_MONTHS and on or before CUT_DAY."""
    if row[0][:7] not in BACKTEST_MONTHS:
        return None
    return keep_until_cut(header, row)


def make_random_vol30(generator):
    """
    Returns a change function for 06_vol30 that replaces the 30-day vol and the
    threshold by random numbers between 5% and 80%, and the flags by random
    True/False. generator is a random.Random with a fixed seed.
    """
    def change(header, row):
        row[header.index("vol30")] = repr(generator.uniform(0.05, 0.80))
        if row[header.index("threshold")] != "":
            row[header.index("threshold")] = repr(generator.uniform(0.05, 0.80))
        for column in ["stress", "stress_fixed"]:
            if column in header:
                row[header.index(column)] = str(generator.random() < 0.5)
        return row
    return change                                  # a function made here and used by rewrite_csv


# ---------------------------------------------------------------------------
# Building the copies
# ---------------------------------------------------------------------------

def build_stage2_copy(name, change_row):
    """One cleaned month and the yields, for the stage 2 test."""
    folder = os.path.join(WORK_FOLDER, name)
    source = "Data/02_clean/spx_" + STAGE2_MONTH + ".csv"
    target = os.path.join(folder, "Data", "02_clean", "spx_" + STAGE2_MONTH + ".csv")
    rewrite_csv(source, target, change_row)
    copy_rates(folder)
    print("  built " + name)


def build_backtest_copy(name, greeks_change, atm_change, vol30_change):
    """The backtest months of 04_greeks, their 05_atm_vol rows, 06_vol30 and the yields."""
    folder = os.path.join(WORK_FOLDER, name)
    for month in BACKTEST_MONTHS:
        source = "Data/04_greeks/spx_" + month + ".csv"
        target = os.path.join(folder, "Data", "04_greeks", "spx_" + month + ".csv")
        rewrite_csv(source, target, greeks_change)
    rewrite_csv("Data/05_atm_vol.csv", os.path.join(folder, "Data", "05_atm_vol.csv"), atm_change)
    rewrite_csv("Data/06_vol30.csv", os.path.join(folder, "Data", "06_vol30.csv"), vol30_change)
    copy_rates(folder)
    print("  built " + name)


def main():
    # Refuse to write anywhere inside the project.
    project = os.path.abspath(".")
    if os.path.abspath(WORK_FOLDER).startswith(project):
        raise ValueError("WORK_FOLDER must lie outside the project")
    if os.path.exists(WORK_FOLDER):
        raise ValueError(WORK_FOLDER + " exists already: delete it first, so no old copy is mixed in")
    print("Building the copies in " + WORK_FOLDER)

    build_stage2_copy("stage2_original", unchanged)
    build_stage2_copy("stage2_times2", clean_times2)

    build_backtest_copy("backtest_original", unchanged, atm_in_months, unchanged)
    build_backtest_copy("backtest_times2", greeks_times2, atm_times2, unchanged)
    build_backtest_copy("backtest_bid_equals_ask", greeks_bid_equals_ask, atm_in_months, unchanged)
    build_backtest_copy("backtest_cut", keep_until_cut, atm_until_cut, keep_until_cut)
    generator = random.Random(RANDOM_SEED)         # its own random numbers, fixed by the seed
    build_backtest_copy("backtest_random_stress", unchanged, atm_in_months, make_random_vol30(generator))
    print("Done.")


main()
