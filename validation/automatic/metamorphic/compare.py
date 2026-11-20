"""
Metamorphic tests, part 3 of 3: compare the outputs of the runs on the copies.

What this file is for
---------------------
make_copies.py built changed copies of the data, run_on_copy.py ran the project's
code in each. This script checks that every output changed exactly as the thesis
says it must. Each test names the statements of validation/test_specification.md.

  T1  F8   stage 2 and the ATM fit on a month with every price, strike and S x 2:
           forward x 2, D, iv, delta and ATM vol unchanged, gamma / 2, vega and
           theta x 2 (prop:black76).
  T2  --   stage 2 and the ATM fit rerun on the unchanged month give the project's
           own Data/04_greeks and Data/05_atm_vol.csv rows (reproducibility).
  T3  S34  the backtest on the doubled copy: the same trades at the same times,
           every amount in points or dollars x 2, every return unchanged.
  T4  S25  with bid = ask on every quote, the run crossing the spread equals the
           run at mid in every file.
  T5  S31, S23, D14  with every row after CUT_DAY removed, every trade closed by
           then, every logged quote and every equity day up to then is unchanged
           (nothing before a date depends on data after it).
  T6  S32  with the 30-day vol and the stress threshold replaced by random
           numbers, everything is unchanged except the stress columns of the trades.

How to run (from the main folder; reads only, seconds):
    python validation/automatic/metamorphic/compare.py

Prints a summary and writes every difference to
validation/automatic/output/metamorphic_check.csv.
"""

import csv              # reads and writes CSV files row by row
import os               # folders and paths
import tempfile         # the computer's temporary folder


# ---------------------------------------------------------------------------
# Settings (the copies' settings are those of make_copies.py)
# ---------------------------------------------------------------------------

# The mutation tests (step 5) point the settings marked "(outside)" elsewhere through
# environment variables: os.environ.get("NAME", default) reads a setting given from
# outside the script, or uses the default. Run normally, nothing changes.
WORK_FOLDER = os.environ.get("CHECK_COPIES_FOLDER", os.path.join(tempfile.gettempdir(), "masterarbeit_metamorphic"))   # (outside)
# where the runs' outputs are: in the copies themselves, or <this folder>/<copy name> (outside)
RUNS_ROOT = os.environ.get("CHECK_RUNS_OUTPUT", WORK_FOLDER)
# "yes" skips T1 and T2, the stage 2 tests (outside)
SKIP_STAGE2 = os.environ.get("CHECK_SKIP_STAGE2", "no") == "yes"
STAGE2_MONTH = "2012-01"
CUT_DAY = "2020-03-10"
SCALE = 2.0
OUTPUT_FOLDER = os.environ.get("CHECK_OUTPUT_FOLDER", "validation/automatic/output")   # (outside)
RUN_NAMES = ["base_mid", "base_cross"]

EXACT = 1e-9            # numbers that must agree to floating-point accuracy
ROUNDED = 2e-6          # numbers stored rounded to 6 decimals: round(2x) and 2 round(x)
                        # may differ by 1.5 units of the 6th decimal
ATM_TOLERANCE = 1e-5    # choice: the ATM fit uses log(K / F) with F rounded, so the
                        # doubled run sees x shifted by up to 1e-9

# How each column of the backtest's files scales when prices x 2 (T3). A column
# not listed must stay the same.
SCALED_COLUMNS = {
    "trades": ["forward0", "target_short", "target_long", "strike_short", "strike_long",
               "credit", "credit_mid", "margin", "mark", "target_credit", "deficit_at_entry",
               "cost", "pnl", "cost_mid", "pnl_mid", "spread_cost", "pnl_dollars", "deficit_after"],
    "equity": ["realised", "unrealised", "interest_today", "interest_total", "total_pnl",
               "margin", "deficit", "pnl_day"],
    "quarters": ["pnl", "mean_margin"],
    "quotes": ["strike", "bid", "ask", "bid_before", "ask_before"],
    "missing": ["strike_short", "strike_long"],
}
FILE_KINDS = ["trades", "equity", "quarters", "quotes", "missing"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_table(path):
    """Read a CSV file into a list of dictionaries {column: text}. A missing file gives None."""
    if not os.path.exists(path):
        return None
    rows = []
    with open(path, newline="") as file:
        reader = csv.DictReader(file)              # the first line gives the column names
        for row in reader:
            rows.append(row)
    return rows


def to_number(text):
    """A field as a number, or None if it is empty or not a number (e.g. "SPXW", "True")."""
    try:
        return float(text)
    except ValueError:                             # float() fails on text that is no number
        return None


def same_field(text_a, text_b, factor, tolerance):
    """
    True if field b equals factor times field a: as numbers within tolerance (plus
    1e-9 of their size) when both are numbers, otherwise as text.

    Example:  same_field("12.8", "25.6", 2.0, 1e-9)  ->  True
    """
    a = to_number(text_a)
    b = to_number(text_b)
    if a is None or b is None:
        return text_a == text_b
    allowed = tolerance + 1e-9 * abs(b)
    return abs(b - factor * a) <= allowed


def new_results():
    """
    An empty collection for the results of all tests, a dictionary with two lists:
    "lines" (one summary line per comparison) and "problems" (one row per difference).
    """
    return {"lines": [], "problems": []}


def compare_rows(results, test, label, rows_a, rows_b, factors, ignore, tolerance):
    """
    Compare two lists of rows, row by row and column by column. factors maps a
    column to its factor (default 1), ignore lists columns not compared.
    Adds a summary line and the differences to results. Returns the number of
    differences.
    """
    differences = 0
    fields = 0
    if rows_a is None or rows_b is None:
        results["problems"].append({"test": test, "file": label, "row": "", "column": "",
                                 "expected": "a file", "found": "missing"})
        results["lines"].append(test + "  " + label.ljust(40) + "file missing")
        return 1
    if len(rows_a) != len(rows_b):
        differences = differences + 1
        results["problems"].append({"test": test, "file": label, "row": "", "column": "number of rows",
                                 "expected": str(len(rows_a)), "found": str(len(rows_b))})
    for number in range(min(len(rows_a), len(rows_b))):
        row_a = rows_a[number]
        row_b = rows_b[number]
        for column in row_a:
            if column in ignore:
                continue
            fields = fields + 1
            factor = factors.get(column, 1.0)      # .get: the factor, or 1 if the column is not listed
            if not same_field(row_a[column], row_b.get(column, ""), factor, tolerance):
                differences = differences + 1
                if differences <= 2000:            # keep the output file a readable size
                    results["problems"].append({"test": test, "file": label, "row": str(number),
                                             "column": column, "expected": row_a[column] + " x " + str(factor),
                                             "found": row_b.get(column, "")})
    results["lines"].append(test + "  " + label.ljust(40) + str(len(rows_a)).rjust(7) + " rows "
                         + str(fields).rjust(9) + " fields " + str(differences).rjust(6) + " differences")
    return differences


def factor_map(columns, factor):
    """{column: factor} for a list of columns."""
    result = {}
    for column in columns:
        result[column] = factor
    return result


def output_path(copy_name, kind, run_name):
    """The path of one output file of one run in one copy."""
    return os.path.join(RUNS_ROOT, copy_name, kind + "_" + run_name + ".csv")


def rows_by_key(rows, key_columns, strike_divisor):
    """
    Sort rows of a stage 2 or ATM file by their key (time, root, expiry, strike,
    type), so two files can be compared row by row whatever their order.
    strike_divisor turns doubled strikes back for the key.
    """
    keyed = []
    for row in rows:
        key = []
        for column in key_columns:
            if column == "strike":
                key.append(float(row[column]) / strike_divisor)
            else:
                key.append(row[column])
        keyed.append((tuple(key), row))            # tuple: a fixed list that can be sorted
    keyed.sort(key=first_item)
    result = []
    for key, row in keyed:
        result.append(row)
    return result


def first_item(pair):
    """The first item of a pair, used as the sort key above."""
    return pair[0]


# ---------------------------------------------------------------------------
# The tests
# ---------------------------------------------------------------------------

def test_stage2(results):
    """T1 (doubled month against the original) and T2 (original against the project's files)."""
    greeks_name = "Data/04_greeks/spx_" + STAGE2_MONTH + ".csv"
    keys = ["quote_datetime", "root", "expiration", "strike", "option_type"]

    original = read_table(os.path.join(WORK_FOLDER, "stage2_original", greeks_name))
    doubled = read_table(os.path.join(WORK_FOLDER, "stage2_times2", greeks_name))
    project = read_table(greeks_name)
    if original is None or doubled is None:
        compare_rows(results, "T1 F8", "04_greeks (stage 2 output)", original, doubled, {}, [], ROUNDED)
        return
    original = rows_by_key(original, keys, 1.0)
    doubled = rows_by_key(doubled, keys, SCALE)
    factors = factor_map(["strike", "bid", "ask", "mid", "spot", "spot_quote", "forward", "vega", "theta"], SCALE)
    factors["gamma"] = 1 / SCALE
    compare_rows(results, "T1 F8", "04_greeks x 2 against original", original, doubled, factors, [], ROUNDED)
    compare_rows(results, "T2", "04_greeks rerun against project", rows_by_key(project, keys, 1.0), original, {}, [], EXACT)

    # The ATM fit.
    atm_keys = ["quote_datetime", "root", "expiration"]
    atm_original = read_table(os.path.join(WORK_FOLDER, "stage2_original", "Data/05_atm_vol.csv"))
    atm_doubled = read_table(os.path.join(WORK_FOLDER, "stage2_times2", "Data/05_atm_vol.csv"))
    if atm_original is None or atm_doubled is None:
        compare_rows(results, "T1 F8", "05_atm_vol", atm_original, atm_doubled, {}, [], ATM_TOLERANCE)
        return
    atm_factors = factor_map(["spot", "spot_quote", "forward"], SCALE)
    compare_rows(results, "T1 F8", "05_atm_vol x 2 against original",
                 rows_by_key(atm_original, atm_keys, 1.0), rows_by_key(atm_doubled, atm_keys, 1.0),
                 atm_factors, [], ATM_TOLERANCE)

    # The project's ATM rows of the same month.
    project_atm = []
    with open("Data/05_atm_vol.csv", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row["quote_datetime"][:7] == STAGE2_MONTH:
                project_atm.append(row)
    compare_rows(results, "T2", "05_atm_vol rerun against project",
                 rows_by_key(project_atm, atm_keys, 1.0), rows_by_key(atm_original, atm_keys, 1.0),
                 {}, [], EXACT)


def test_times2(results):
    """T3: the backtest on the doubled copy against the original copy."""
    for run_name in RUN_NAMES:
        for kind in FILE_KINDS:
            original = read_table(output_path("backtest_original", kind, run_name))
            doubled = read_table(output_path("backtest_times2", kind, run_name))
            factors = factor_map(SCALED_COLUMNS[kind], SCALE)
            compare_rows(results, "T3 S34", kind + "_" + run_name, original, doubled, factors, [], EXACT)


def test_bid_equals_ask(results):
    """T4: with bid = ask, the run crossing the spread equals the run at mid."""
    for kind in FILE_KINDS:
        mid_run = read_table(output_path("backtest_bid_equals_ask", kind, "base_mid"))
        cross_run = read_table(output_path("backtest_bid_equals_ask", kind, "base_cross"))
        compare_rows(results, "T4 S25", kind + " cross against mid", mid_run, cross_run, {}, [], EXACT)


def rows_until_cut(rows, time_column):
    """The rows whose time (or date) column is on or before the end of CUT_DAY."""
    kept = []
    if rows is None:
        return None
    for row in rows:
        if row[time_column] != "" and row[time_column][:10] <= CUT_DAY:
            kept.append(row)
    return kept


def test_cut(results):
    """T5: nothing up to CUT_DAY changes when the data after it are removed."""
    time_column_of = {"trades": "exit_time", "equity": "date", "quotes": "time", "missing": "when"}
    for run_name in RUN_NAMES:
        for kind in ["trades", "equity", "quotes", "missing"]:
            original = read_table(output_path("backtest_original", kind, run_name))
            cut = read_table(output_path("backtest_cut", kind, run_name))
            column = time_column_of[kind]
            compare_rows(results, "T5 S31", kind + "_" + run_name + " up to " + CUT_DAY,
                         rows_until_cut(original, column), rows_until_cut(cut, column), {}, [], EXACT)


def test_random_stress(results):
    """T6: random stress inputs change only the stress columns of the trades."""
    for run_name in RUN_NAMES:
        for kind in FILE_KINDS:
            original = read_table(output_path("backtest_original", kind, run_name))
            changed = read_table(output_path("backtest_random_stress", kind, run_name))
            ignore = []
            if kind == "trades":
                ignore = ["stress_threshold", "stress"]
            compare_rows(results, "T6 S32", kind + "_" + run_name, original, changed, {}, ignore, EXACT)

        # The change must bite: the stress columns themselves should differ somewhere.
        original = read_table(output_path("backtest_original", "trades", run_name))
        changed = read_table(output_path("backtest_random_stress", "trades", run_name))
        if original is not None and changed is not None:
            changed_flags = 0
            for number in range(min(len(original), len(changed))):
                if original[number]["stress_threshold"] != changed[number]["stress_threshold"]:
                    changed_flags = changed_flags + 1
            results["lines"].append("T6 S32  (check that the change bites) " + run_name + ": stress threshold differs in "
                                 + str(changed_flags) + " of " + str(len(original)) + " trades")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    results = new_results()
    if not SKIP_STAGE2:
        test_stage2(results)
    test_times2(results)
    test_bid_equals_ask(results)
    test_cut(results)
    test_random_stress(results)

    for line in results["lines"]:
        print(line)

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)      # no error if the folder exists
    path = OUTPUT_FOLDER + "/metamorphic_check.csv"
    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["test", "file", "row", "column", "expected", "found"])
        writer.writeheader()
        for problem in results["problems"]:
            writer.writerow(problem)
    print()
    print(str(len(results["problems"])) + " differences written to " + path)
    shown = 0
    for problem in results["problems"]:
        if shown == 20:
            break
        print("  " + problem["test"] + " | " + problem["file"] + " | row " + problem["row"] + " | "
              + problem["column"] + " | expected " + problem["expected"] + " | found " + problem["found"])
        shown = shown + 1


main()
