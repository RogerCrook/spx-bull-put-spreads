"""
Rough synthetic market, part 2 of 2: compare the pipeline's outputs with the rules.

What this file is for
---------------------
make_rough_market.py wrote a made-up market with parity errors, a cubic smile and
two slices with few strikes. run_pipeline.py ran stage 1, stage 2 and the ATM fit on
it. This script works out, with its own code and the rules of the test
specification, what the pipeline should give, and compares:

  D8   the forward of every slice and snapshot: pair call and put at each strike
       that stage 1 kept, K0 = the strike with the smallest |C - P|, at the 8
       strikes nearest K0 the estimate K + (C - P) / D, the median of these.
       Where two strikes are equally far from K0 both choices are tried, and they
       must give the same median (otherwise the market is badly made).
  D11  the ATM vol of the slices "cubic", "three" and "two": the out-of-the-money
       quotes (puts for x < 0, calls for x >= 0, x = log(K / F)) with |x| < 0.05
       and a volatility, at least 3 of them, an unweighted fit of a + b x + c x^2,
       the ATM vol = a. With fewer than 3 there must be no ATM vol.
       (The "noisy" slice is left out here: its vols depend on its noisy forward.)

It also prints how far the answer moves under the slips the mutation tests planted
(7 or 9 strikes, a band of 0.055, no calls in the fit), to show the test can see
them. The rows stage 1 keeps are read from its output (stage 1 itself is checked by
the first made-up market, check.py). The true F, D and sigma come from truth.csv.

How to run (from the main folder; reads only, seconds):
    python validation/automatic/synthetic/check_rough.py
Prints a summary and writes every difference to
validation/automatic/output/synthetic_rough_check.csv.
"""

import csv              # reads and writes CSV files row by row
import math             # log, isnan
import os               # folders and paths
import statistics       # median
import tempfile         # the computer's temporary folder

import numpy as np      # only for np.polyfit, the least-squares fit of a curve


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# The mutation tests point the settings marked "(outside)" elsewhere through
# environment variables; os.environ.get("NAME", default) reads one, or uses the default.
WORK_FOLDER = os.environ.get("CHECK_SYNTHETIC_FOLDER",
                             os.path.join(tempfile.gettempdir(), "masterarbeit_synthetic_rough"))   # (outside)
OUTPUT_FOLDER = os.environ.get("CHECK_OUTPUT_FOLDER", "validation/automatic/output")                # (outside)
MONTH = "2031-03"

NEAREST_STRIKES = 8             # D8
MIN_PAIRS = 3                   # D8: fewer pairs, no forward
BAND = 0.05                     # D11: |x| < 0.05
MIN_POINTS = 3                  # D11
FIT_SLICES = ["cubic", "three", "two"]

FORWARD_TOLERANCE = 1e-5        # index points (the pipeline stores 6 decimals)
ATM_TOLERANCE = 1e-5            # the ATM vol, as a fraction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_table(path):
    """Read a CSV file into a list of dictionaries {column: text}. None if it is missing."""
    if not os.path.exists(path):
        return None
    rows = []
    with open(path, newline="") as file:
        for row in csv.DictReader(file):           # the first line gives the column names
            rows.append(row)
    return rows


def is_empty(text):
    """True if a stored number is missing: an empty cell or "nan"."""
    return text == "" or text.lower() == "nan"


def forward_by_rule(pairs, D, how_many):
    """
    The forward of one slice by the rule of D8, with how_many nearest strikes.
      pairs : {strike: (call mid, put mid)}
    Returns a list of the medians for every way of breaking a tie in distance
    (normally one value), or [] with fewer than MIN_PAIRS pairs.
    """
    if len(pairs) < MIN_PAIRS:
        return []
    strikes = sorted(pairs)
    k0 = strikes[0]
    for strike in strikes:                          # K0: the smallest |C - P|
        call, put = pairs[strike]
        best_call, best_put = pairs[k0]
        if abs(call - put) < abs(best_call - best_put):
            k0 = strike
    # Sort the strikes by distance to K0, once with the lower strike first in a tie,
    # once with the higher one first. sorted(..., key=...) sorts by the number the
    # small function after "key=" gives for each strike.
    lower_first = sorted(strikes, key=lambda strike: (abs(strike - k0), strike))
    higher_first = sorted(strikes, key=lambda strike: (abs(strike - k0), -strike))
    medians = []
    for order in [lower_first, higher_first]:
        estimates = []
        for strike in order[:how_many]:             # [:how_many]: the first how_many of the list
            call, put = pairs[strike]
            estimates.append(strike + (call - put) / D)     # parity: C - P = D (F - K)
        medians.append(statistics.median(estimates))
    if abs(medians[0] - medians[1]) < 1e-12:
        return [medians[0]]
    return medians


def atm_by_rule(points, band, use_calls):
    """
    The ATM vol of one slice by the rule of D11.
      points : list of (x, is_call, sigma or None)
    Returns the fitted value at x = 0, or None with fewer than MIN_POINTS points.
    """
    xs = []
    vols = []
    for x, is_call, sigma in points:
        if sigma is None:
            continue                                # no volatility for this quote
        if abs(x) >= band:
            continue
        out_of_the_money = (is_call and x >= 0) or (not is_call and x < 0)
        if not out_of_the_money:
            continue
        if is_call and not use_calls:
            continue
        xs.append(x)
        vols.append(sigma)
    if len(xs) < MIN_POINTS:
        return None
    # np.polyfit(xs, vols, 2) finds c, b, a of the parabola c x^2 + b x + a closest to
    # the points (least squares, every point weighted the same). [-1] is a, the value at 0.
    coefficients = np.polyfit(xs, vols, 2)
    return float(coefficients[-1])


def add_problem(problems, statement, key, what, expected, found):
    problems.append({"statement": statement, "key": str(key), "what": what,
                     "expected": str(expected), "found": str(found)})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    truth = read_table(os.path.join(WORK_FOLDER, "truth.csv"))
    clean = read_table(os.path.join(WORK_FOLDER, "Data", "02_clean", "spx_" + MONTH + ".csv"))
    greeks = read_table(os.path.join(WORK_FOLDER, "Data", "04_greeks", "spx_" + MONTH + ".csv"))
    atm = read_table(os.path.join(WORK_FOLDER, "Data", "05_atm_vol.csv"))
    problems = []
    if truth is None:
        raise ValueError("no truth.csv: run make_rough_market.py first")
    for name, table in [("stage 1 output", clean), ("stage 2 output", greeks), ("ATM output", atm)]:
        if table is None:
            add_problem(problems, "D8", "", name, "a file", "missing")

    counts = {"forwards checked": 0, "forwards that differ": 0,
              "ATM vols checked": 0, "ATM vols that differ": 0}
    separation = {}                                 # how far the slips move the answer (smallest seen)

    if len(problems) == 0:
        # The truth of each row, by (time, expiry, strike, type), and of each slice.
        truth_of = {}
        slice_truth = {}
        for row in truth:
            key = (row["quote_datetime"], row["expiration"], float(row["strike"]), row["option_type"])
            truth_of[key] = row
            slice_truth[(row["quote_datetime"], row["expiration"])] = row

        # The kept rows of each slice: {(time, expiry): {strike: {"C": mid, "P": mid}}}.
        kept = {}
        for row in clean:
            slice_key = (row["quote_datetime"], row["expiration"])
            if slice_key not in kept:
                kept[slice_key] = {}
            strike = float(row["strike"])
            if strike not in kept[slice_key]:
                kept[slice_key][strike] = {}
            kept[slice_key][strike][row["option_type"]] = float(row["mid"])

        # The pipeline's forward of each slice (stage 2, every row of a slice has the same).
        forward_stage2 = {}
        for row in greeks:
            forward_stage2[(row["quote_datetime"], row["expiration"])] = row["forward"]
        atm_of = {}
        for row in atm:
            atm_of[(row["quote_datetime"], row["expiration"])] = row

        for slice_key in sorted(kept):
            info = slice_truth[slice_key]
            name = info["slice"]
            D = float(info["D"])
            F = float(info["F"])

            # D8: the forward.
            pairs = {}
            for strike in kept[slice_key]:
                both = kept[slice_key][strike]
                if "C" in both and "P" in both:
                    pairs[strike] = (both["C"], both["P"])
            expected = forward_by_rule(pairs, D, NEAREST_STRIKES)
            if len(expected) != 1:
                add_problem(problems, "D8", slice_key, "forward (market badly made: the tie matters)", expected, "")
                continue
            for other in [NEAREST_STRIKES - 1, NEAREST_STRIKES + 1]:
                moved = forward_by_rule(pairs, D, other)
                gap = abs(moved[0] - expected[0])
                label = name + ": forward with " + str(other) + " strikes"
                if label not in separation or gap < separation[label]:
                    separation[label] = gap
            for where, stored in [("stage 2", forward_stage2.get(slice_key)),
                                  ("ATM file", atm_of.get(slice_key, {}).get("forward"))]:
                counts["forwards checked"] = counts["forwards checked"] + 1
                if stored is None or is_empty(stored) or abs(float(stored) - expected[0]) > FORWARD_TOLERANCE:
                    counts["forwards that differ"] = counts["forwards that differ"] + 1
                    add_problem(problems, "D8", slice_key, "forward in " + where, expected[0], stored)

            # D11: the ATM vol.
            if name not in FIT_SLICES:
                continue
            points = []
            for strike in kept[slice_key]:
                for option_type in kept[slice_key][strike]:
                    row = truth_of[(slice_key[0], slice_key[1], strike, option_type)]
                    sigma = None
                    if row["has_volatility"] == "True":
                        sigma = float(row["sigma"])
                    points.append((math.log(strike / F), option_type == "C", sigma))
            expected_atm = atm_by_rule(points, BAND, True)
            if expected_atm is not None:
                for label, moved in [(name + ": ATM with band 0.055", atm_by_rule(points, 0.055, True)),
                                     (name + ": ATM without the calls", atm_by_rule(points, BAND, False))]:
                    if moved is None:
                        gap = float("inf")                  # no value at all: certainly seen
                    else:
                        gap = abs(moved - expected_atm)
                    if label not in separation or gap < separation[label]:
                        separation[label] = gap
            counts["ATM vols checked"] = counts["ATM vols checked"] + 1
            stored = None
            if slice_key in atm_of and not is_empty(atm_of[slice_key]["atm_iv"]):
                stored = float(atm_of[slice_key]["atm_iv"])
            if expected_atm is None:
                if stored is not None:
                    counts["ATM vols that differ"] = counts["ATM vols that differ"] + 1
                    add_problem(problems, "D11", slice_key, "ATM vol (fewer than 3 points)", "none", stored)
            elif stored is None or abs(stored - expected_atm) > ATM_TOLERANCE:
                counts["ATM vols that differ"] = counts["ATM vols that differ"] + 1
                add_problem(problems, "D11", slice_key, "ATM vol", expected_atm, stored)

    for name in counts:
        print("  " + name.ljust(40) + str(counts[name]).rjust(8))
    print()
    print("  how far each slip would move the answer (smallest over the snapshots; tolerance 1e-5):")
    for label in sorted(separation):
        print("    " + label.ljust(45) + "%.2e" % separation[label])

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    path = OUTPUT_FOLDER + "/synthetic_rough_check.csv"
    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["statement", "key", "what", "expected", "found"])
        writer.writeheader()
        for problem in problems:
            writer.writerow(problem)
    print()
    print(str(len(problems)) + " differences written to " + path)
    shown = 0
    for problem in problems:
        if shown == 15:
            break
        print("  " + problem["statement"] + " | " + problem["key"] + " | " + problem["what"]
              + " | expected " + problem["expected"] + " | found " + problem["found"])
        shown = shown + 1


main()
