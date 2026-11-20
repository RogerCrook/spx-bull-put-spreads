"""
Synthetic market, part 3 of 3: compare the pipeline's outputs with the known truth.

What this file is for
---------------------
make_market.py wrote a made-up market and truth.csv, the known answer for every raw
row. run_pipeline.py ran stage 1, stage 2 and the ATM fit on it. This script checks
the outputs against the truth, statement by statement (validation/test_specification.md):

  Part A  stage 1 (Data/02_clean)
            D1  exactly the rows the thesis's filters keep are kept,
            D2  S = the official close at the last snapshot of a day, the mid of
                the index quote elsewhere, the recorded quote kept as spot_quote,
            D5  dte = calendar days to expiry,
            D4  mid = (bid + ask) / 2.
  Part B  stage 2 (Data/04_greeks)
            D8  a slice with fewer than 3 call-put pairs gets no forward and is dropped,
            D9  the forward = S exp((r - q) tau), for SPX and SPXW separately (D3),
            D6, D7  D = exp(-r tau) with r from the yields as sec:rates says,
                incl. the forward-filled day and the 1-month rate below 30 days,
            D10 the implied vol = the sigma used to make the price,
            F5-F7 the Greeks = the Black-76 Greeks at the true values.
  Part C  the ATM fit (Data/05_atm_vol.csv)
            D11, D12 the ATM vol = a, the smile's value at x = 0 (exact for a
                quadratic smile, and sigma for the flat one).

How to run (from the main folder; reads only, seconds):
    python validation/automatic/synthetic/check.py
Prints a summary and writes every difference to
validation/automatic/output/synthetic_check.csv.
"""

import csv              # reads and writes CSV files row by row
import math             # exp, log, sqrt, erf
import os               # folders and paths
import tempfile         # the computer's temporary folder


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# The mutation tests (step 5) point the settings marked "(outside)" elsewhere through
# environment variables: os.environ.get("NAME", default) reads a setting given from
# outside the script, or uses the default. Run normally, nothing changes.
WORK_FOLDER = os.environ.get("CHECK_SYNTHETIC_FOLDER", os.path.join(tempfile.gettempdir(), "masterarbeit_synthetic"))   # (outside)
MONTH = "2031-03"
OUTPUT_FOLDER = os.environ.get("CHECK_OUTPUT_FOLDER", "validation/automatic/output")   # (outside)

# The smile of each expiry: its value at x = 0 is a (as in make_market.py).
ATM_OF_EXPIRY = {("SPXW", "2031-03-06"): 0.20, ("SPXW", "2031-03-07"): 0.20,
                 ("SPX", "2031-04-02"): 0.18, ("SPX", "2031-04-18"): 0.20,
                 ("SPXW", "2031-04-18"): 0.21, ("SPXQ", "2031-05-07"): 0.20,
                 ("SPX", "2031-06-11"): 0.22, ("SPX", "2031-06-12"): 0.22}
FEW_PAIRS = ("SPXQ", "2031-05-07")       # this slice must get no forward (D8)

# Tolerances (choice, fixed before the first run). The pipeline stores 6 decimals.
EXACT = 1e-9            # numbers copied or computed exactly
ROUNDED = 2e-6          # numbers rounded to 6 decimals, plus a little
FORWARD_TOLERANCE = 1e-5          # the forward, index points (6 decimals, about 4,000)
GREEK_RELATIVE = 1e-4             # Greeks: 2e-6 plus 0.01% of their size
ATM_TOLERANCE = 1e-5              # the ATM vol, as a fraction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_table(path):
    """Read a CSV file into a list of dictionaries {column: text}. None if it is missing."""
    if not os.path.exists(path):
        return None
    rows = []
    with open(path, newline="") as file:
        reader = csv.DictReader(file)              # the first line gives the column names
        for row in reader:
            rows.append(row)
    return rows


def key_of(row):
    """The contract-and-time key of a row (D3: root, expiry, strike, type), with the time."""
    return (row["quote_datetime"], row["root"], row["expiration"], float(row["strike"]), row["option_type"])


def normal_cdf(x):
    """N(x), the standard normal distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def normal_density(x):
    """phi(x) = exp(-x^2 / 2) / sqrt(2 pi)."""
    return math.exp(-x * x / 2.0) / math.sqrt(2.0 * math.pi)


def stored_greeks(F, S, K, tau, sigma, D, is_put):
    """
    The Greeks as stored (prop:greeks-fwd, prop:chainrule, rem:scaling):
      delta = D [N(d1) - 1 if put] * F / S,    gamma = D phi(d1) / (F sigma sqrt(tau)) * (F / S)^2,
      vega  = D F phi(d1) sqrt(tau) / 100,     theta = -D F phi(d1) sigma / (2 sqrt(tau)) / 365.
    """
    root_tau = math.sqrt(tau)
    d1 = math.log(F / K) / (sigma * root_tau) + sigma * root_tau / 2.0
    density = normal_density(d1)
    delta_F = D * normal_cdf(d1)
    if is_put:
        delta_F = delta_F - D
    ratio = F / S
    return {
        "delta": delta_F * ratio,
        "gamma": D * density / (F * sigma * root_tau) * ratio * ratio,
        "vega": D * F * density * root_tau / 100.0,
        "theta": -D * F * density * sigma / (2.0 * root_tau) / 365.0,
    }


def add_problem(problems, part, statement, key, what, expected, found):
    """Keep one difference (at most 5,000, to keep the file readable)."""
    if len(problems) < 5000:
        problems.append({"part": part, "statement": statement, "key": str(key), "what": what,
                         "expected": str(expected), "found": str(found)})


def check_number(problems, counts, part, statement, key, what, expected, found_text, tolerance):
    """Compare one number with its known value; count it, and keep it if it differs."""
    counts[statement + " fields"] = counts.get(statement + " fields", 0) + 1     # .get: 0 if not there yet
    if found_text == "":
        counts[statement + " differences"] = counts.get(statement + " differences", 0) + 1
        add_problem(problems, part, statement, key, what, expected, "empty")
        return
    found = float(found_text)
    if abs(found - expected) > tolerance:
        counts[statement + " differences"] = counts.get(statement + " differences", 0) + 1
        add_problem(problems, part, statement, key, what, expected, found)


# ---------------------------------------------------------------------------
# The parts
# ---------------------------------------------------------------------------

def part_a(truth, problems, counts):
    """Stage 1: which rows are kept (D1), and S, spot_quote, dte, mid (D2, D5, D4)."""
    clean = read_table(os.path.join(WORK_FOLDER, "Data", "02_clean", "spx_" + MONTH + ".csv"))
    if clean is None:
        add_problem(problems, "A", "D1", "", "stage 1 output", "a file", "missing")
        return {}
    clean_by_key = {}
    for row in clean:
        clean_by_key[key_of(row)] = row

    kept_keys = {}
    for truth_row in truth:
        key = key_of(truth_row)
        should_keep = truth_row["kept_by_stage1"] == "True"
        is_kept = key in clean_by_key
        counts["D1 raw rows"] = counts.get("D1 raw rows", 0) + 1
        if should_keep != is_kept:
            counts["D1 differences"] = counts.get("D1 differences", 0) + 1
            moneyness = float(truth_row["strike"]) / float(truth_row["S"])
            detail = ("days " + truth_row["days"] + ", K/S " + repr(moneyness) + ", bid " + truth_row["bid"]
                      + ", ask " + truth_row["ask"])
            add_problem(problems, "A", "D1", key, "kept by stage 1 (" + detail + ")", should_keep, is_kept)
        if not is_kept:
            continue
        kept_keys[key] = truth_row
        row = clean_by_key[key]
        check_number(problems, counts, "A", "D2", key, "spot", float(truth_row["S"]), row["spot"], EXACT)
        check_number(problems, counts, "A", "D2", key, "spot_quote", float(truth_row["spot_quote"]), row["spot_quote"], EXACT)
        check_number(problems, counts, "A", "D5", key, "dte", float(truth_row["days"]), row["dte"], EXACT)
        mid = (float(truth_row["bid"]) + float(truth_row["ask"])) / 2
        check_number(problems, counts, "A", "D4", key, "mid", mid, row["mid"], EXACT)
    if len(clean_by_key) != len(kept_keys):
        add_problem(problems, "A", "D1", "", "rows in stage 1 output not in the raw data", len(kept_keys), len(clean_by_key))
    return kept_keys


def part_b(kept_keys, problems, counts):
    """Stage 2: dropped slice (D8), forward (D9, D3), D (D6, D7), iv (D10), Greeks (F5-F7)."""
    greeks = read_table(os.path.join(WORK_FOLDER, "Data", "04_greeks", "spx_" + MONTH + ".csv"))
    if greeks is None:
        add_problem(problems, "B", "D8", "", "stage 2 output", "a file", "missing")
        return
    greeks_by_key = {}
    for row in greeks:
        greeks_by_key[key_of(row)] = row

    for key in kept_keys:
        truth_row = kept_keys[key]
        slice_name = (truth_row["root"], truth_row["expiration"])
        is_there = key in greeks_by_key
        should_be_there = slice_name != FEW_PAIRS
        counts["D8 rows"] = counts.get("D8 rows", 0) + 1
        if is_there != should_be_there:
            counts["D8 differences"] = counts.get("D8 differences", 0) + 1
            add_problem(problems, "B", "D8", key, "row in stage 2 output", should_be_there, is_there)
        if not is_there:
            continue
        row = greeks_by_key[key]
        F = float(truth_row["F"])
        S = float(truth_row["S"])
        D = float(truth_row["D"])
        sigma = float(truth_row["sigma"])
        K = float(truth_row["strike"])
        tau = float(truth_row["days"]) / 365
        is_put = truth_row["option_type"] == "P"
        check_number(problems, counts, "B", "D9", key, "forward", F, row["forward"], FORWARD_TOLERANCE)
        check_number(problems, counts, "B", "D7", key, "D", D, row["D"], ROUNDED)
        check_number(problems, counts, "B", "D10", key, "iv", sigma, row["iv"], ROUNDED)
        expected = stored_greeks(F, S, K, tau, sigma, D, is_put)
        for name in ["delta", "gamma", "vega", "theta"]:
            tolerance = ROUNDED + GREEK_RELATIVE * abs(expected[name])
            check_number(problems, counts, "B", "F5-F7", key, name, expected[name], row[name], tolerance)
    for key in greeks_by_key:
        if key not in kept_keys:
            add_problem(problems, "B", "D8", key, "row in stage 2 that stage 1 did not keep", "absent", "present")


def part_c(truth, problems, counts):
    """The ATM fit: one row per slice with a forward, ATM vol = a (D11, D12)."""
    atm = read_table(os.path.join(WORK_FOLDER, "Data", "05_atm_vol.csv"))
    if atm is None:
        add_problem(problems, "C", "D11", "", "ATM output", "a file", "missing")
        return
    # The forward and S of each slice, from the truth (the same for every strike of it).
    slice_truth = {}
    for truth_row in truth:
        if truth_row["kept_by_stage1"] != "True":
            continue
        slice_key = (truth_row["quote_datetime"], truth_row["root"], truth_row["expiration"])
        slice_truth[slice_key] = truth_row
    found_slices = set()
    for row in atm:
        slice_key = (row["quote_datetime"], row["root"], row["expiration"])
        found_slices.add(slice_key)
        if slice_key not in slice_truth:
            add_problem(problems, "C", "D11", slice_key, "slice in the ATM file without kept quotes", "absent", "present")
            continue
        truth_row = slice_truth[slice_key]
        a = ATM_OF_EXPIRY[(row["root"], row["expiration"])]
        statement = "D11"                                  # the quadratic smiles
        if (row["root"], row["expiration"]) == ("SPX", "2031-04-02"):
            statement = "D12"                              # the flat smile
        check_number(problems, counts, "C", statement, slice_key, "atm_iv", a, row["atm_iv"], ATM_TOLERANCE)
        check_number(problems, counts, "C", "D9", slice_key, "forward in the ATM file", float(truth_row["F"]), row["forward"], FORWARD_TOLERANCE)
        check_number(problems, counts, "C", "D2", slice_key, "spot in the ATM file", float(truth_row["S"]), row["spot"], EXACT)
    for slice_key in slice_truth:
        expected_present = (slice_key[1], slice_key[2]) != FEW_PAIRS
        if expected_present and slice_key not in found_slices:
            add_problem(problems, "C", "D11", slice_key, "slice missing in the ATM file", "present", "absent")
        if not expected_present and slice_key in found_slices:
            add_problem(problems, "C", "D8", slice_key, "slice without forward in the ATM file", "absent", "present")
    counts["C slices in the ATM file"] = len(found_slices)


def main():
    truth = read_table(os.path.join(WORK_FOLDER, "truth.csv"))
    if truth is None:
        raise ValueError("no truth.csv: run make_market.py and run_pipeline.py first")
    problems = []
    counts = {}
    kept_keys = part_a(truth, problems, counts)
    part_b(kept_keys, problems, counts)
    part_c(truth, problems, counts)

    for name in sorted(counts):
        print("  " + name.ljust(40) + str(counts[name]).rjust(10))

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    path = OUTPUT_FOLDER + "/synthetic_check.csv"
    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["part", "statement", "key", "what", "expected", "found"])
        writer.writeheader()
        for problem in problems:
            writer.writerow(problem)
    print()
    print(str(len(problems)) + " differences written to " + path)
    shown = 0
    for problem in problems:
        if shown == 25:
            break
        print("  " + problem["part"] + " " + problem["statement"] + " | " + problem["key"] + " | " + problem["what"]
              + " | expected " + problem["expected"] + " | found " + problem["found"])
        shown = shown + 1


main()
