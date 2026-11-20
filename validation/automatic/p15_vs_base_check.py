"""
Base case against p15 (code validation, step 2, method 5: metamorphic, statement S33).

What this file is for
---------------------
The p15 variant differs from the base case only in the profit exit: Delta0 - 0.15
instead of Delta0 - 0.10 (sec:robustness). Everything else, the entry rule, the
loss and gamma exits, the deficit, is the same. So without knowing what either run
should earn, we know how the two must relate:

  1. Whenever both runs open a position at the same snapshot with the same deficit,
     they must open the same position (same expiry, strikes, credit, Delta0, ...),
     because the entry depends only on the snapshot and the deficit.
  2. That cycle must then end as follows (def:exits, tested in the order loss,
     profit, gamma, G1). The p15 profit level is lower, so it can only hold
     where the base level holds too:
       base exits for loss                       -> p15 the same snapshot, loss
       base exits for gamma                      -> p15 the same snapshot, gamma
       base exits for profit, Delta_exit <= Delta0 - 0.15
                                                 -> p15 the same snapshot, profit
       base exits for profit, Delta_exit >  Delta0 - 0.15
                                                 -> p15 holds on: it exits later, or
                                                    at the same snapshot for gamma
                                                    if the gamma exit holds there
     If p15 exits at the same snapshot, its P&L and deficit after must be the same.
  3. In particular, the two runs agree trade for trade from the start until the
     first cycle of the last kind.

It reads only the trade logs of the four runs (results/trades_<run>.csv) and runs in
seconds. Written from the thesis and the test specification, without reading Code/.

How to run (from the main folder; read-only):
    python validation/automatic/p15_vs_base_check.py

Prints a summary and writes every difference to
validation/automatic/output/p15_vs_base_check.csv. Writes nothing else.
"""

import csv          # reads and writes CSV files row by row
import os           # the output folder


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

RESULTS_FOLDER = "results"
OUTPUT_FOLDER = "validation/automatic/output"

PAIRS = [("base_mid", "p15_mid"), ("base_cross", "p15_cross")]   # same execution, two profit exits

P15_PROFIT_BAND = 0.15          # p15: profit exit at Delta0 - 0.15 (sec:robustness)
TOLERANCE = 1e-9                # two numbers count as equal within this (points, deltas)

# The columns fixed at entry. Both runs must agree on all of them when they open at
# the same snapshot with the same deficit (point 1).
ENTRY_COLUMNS = ["root", "expiration", "dte0", "exit_days", "forward0", "atm_iv0",
                 "target_short", "target_long", "strike_short", "strike_long",
                 "iv_short0", "iv_long0", "delta0", "credit", "credit_mid", "margin",
                 "maturity_rule", "target_credit", "vol30_entry", "stress_threshold", "stress"]

# The columns of the exit. They must agree when both exit at the same snapshot (point 2).
EXIT_COLUMNS = ["exit_time", "reason", "dte_exit", "iv_short_exit", "iv_long_exit",
                "delta_exit", "cost", "pnl", "cost_mid", "pnl_mid", "deficit_after"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_table(path):
    """Read a CSV file into a list of dictionaries {column: text}."""
    rows = []
    with open(path, newline="") as file:
        reader = csv.DictReader(file)               # the first line gives the column names
        for row in reader:
            rows.append(row)
    return rows


def same_value(a_text, b_text):
    """
    True if two fields of the trade log are the same: equal as numbers within
    TOLERANCE when both are numbers, otherwise equal as text (e.g. "SPXW", "profit").
    """
    try:
        a = float(a_text)                           # float() fails on text like "SPXW" ...
        b = float(b_text)
    except ValueError:                              # ... and then we compare the text itself
        return a_text == b_text
    return abs(a - b) <= TOLERANCE


def add_problem(problems, pair, entry_time, what, base_value, p15_value):
    """Keep one difference. Every difference becomes one row of the output file."""
    problems.append({"pair": pair, "entry_time": entry_time, "what": what,
                     "base": str(base_value), "p15": str(p15_value)})


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------

def check_pair(base_run, p15_run, problems):
    """Run points 1 to 3 for one pair of runs. Returns a dictionary of counts."""
    pair = base_run + " / " + p15_run
    base_trades = read_table(RESULTS_FOLDER + "/trades_" + base_run + ".csv")
    p15_trades = read_table(RESULTS_FOLDER + "/trades_" + p15_run + ".csv")

    # The p15 trades by entry time, to find the one opened at the same snapshot.
    p15_by_entry = {}
    for trade in p15_trades:
        p15_by_entry[trade["entry_time"]] = trade

    counts = {
        "base cycles": len(base_trades),
        "p15 cycles": len(p15_trades),
        "same snapshot, same deficit (tested)": 0,
        "same snapshot, other deficit (not tested)": 0,
        "  ended the same (loss)": 0,
        "  ended the same (gamma)": 0,
        "  ended the same (profit below Delta0 - 0.15)": 0,
        "  p15 held on after a base profit exit": 0,
        "  p15 exited for gamma where base took profit": 0,
        "cycles the same from the start": 0,
    }

    still_identical_from_start = True               # point 3

    for number in range(len(base_trades)):
        base = base_trades[number]
        entry_time = base["entry_time"]
        p15 = p15_by_entry.get(entry_time)          # .get gives None if p15 has no entry then

        if p15 is None:
            still_identical_from_start = False
            continue
        if not same_value(base["deficit_at_entry"], p15["deficit_at_entry"]):
            counts["same snapshot, other deficit (not tested)"] = counts["same snapshot, other deficit (not tested)"] + 1
            still_identical_from_start = False
            continue
        counts["same snapshot, same deficit (tested)"] = counts["same snapshot, same deficit (tested)"] + 1

        # Point 1: the same position.
        for column in ENTRY_COLUMNS:
            if not same_value(base[column], p15[column]):
                add_problem(problems, pair, entry_time, "entry column " + column, base[column], p15[column])
                still_identical_from_start = False

        # Point 2: how the cycle ends.
        delta0 = float(base["delta0"])
        base_delta_exit = float(base["delta_exit"])
        p15_level = delta0 - P15_PROFIT_BAND
        base_reason = base["reason"]

        if base_reason in ["loss", "gamma"] or (base_reason == "profit" and base_delta_exit <= p15_level + TOLERANCE):
            # p15 must exit at the same snapshot for the same reason, with the same numbers.
            for column in EXIT_COLUMNS:
                if not same_value(base[column], p15[column]):
                    add_problem(problems, pair, entry_time, "exit column " + column + " (base " + base_reason + ")", base[column], p15[column])
                    still_identical_from_start = False
            if base_reason == "loss":
                counts["  ended the same (loss)"] = counts["  ended the same (loss)"] + 1
            elif base_reason == "gamma":
                counts["  ended the same (gamma)"] = counts["  ended the same (gamma)"] + 1
            else:
                counts["  ended the same (profit below Delta0 - 0.15)"] = counts["  ended the same (profit below Delta0 - 0.15)"] + 1
        elif base_reason == "profit":
            # Base took profit above the p15 level: p15 must not take profit here.
            still_identical_from_start = False
            if p15["exit_time"] > base["exit_time"]:
                counts["  p15 held on after a base profit exit"] = counts["  p15 held on after a base profit exit"] + 1
            elif p15["exit_time"] == base["exit_time"] and p15["reason"] == "gamma":
                # Allowed only if the gamma exit holds at that snapshot: days left <= exit day.
                if int(base["dte_exit"]) <= float(base["exit_days"]):
                    counts["  p15 exited for gamma where base took profit"] = counts["  p15 exited for gamma where base took profit"] + 1
                else:
                    add_problem(problems, pair, entry_time, "p15 gamma exit although days left > exit day", base["exit_days"], p15["dte_exit"])
            else:
                add_problem(problems, pair, entry_time, "p15 exit after a base profit above Delta0 - 0.15",
                            base["exit_time"] + " profit", p15["exit_time"] + " " + p15["reason"])
        else:
            add_problem(problems, pair, entry_time, "unknown exit reason", base_reason, p15["reason"])

        if still_identical_from_start:
            counts["cycles the same from the start"] = counts["cycles the same from the start"] + 1

    return counts


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    problems = []
    for base_run, p15_run in PAIRS:
        counts = check_pair(base_run, p15_run, problems)
        print()
        print(base_run + " against " + p15_run)
        for name in counts:
            print("  " + name.ljust(50) + str(counts[name]).rjust(8))

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)       # make the folder; no error if it exists
    path = OUTPUT_FOLDER + "/p15_vs_base_check.csv"
    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["pair", "entry_time", "what", "base", "p15"])
        writer.writeheader()
        for problem in problems:
            writer.writerow(problem)

    print()
    print("  " + str(len(problems)) + " differences written to " + path)
    shown = 0
    for problem in problems:
        if shown == 15:
            break
        print("    " + problem["pair"] + " " + problem["entry_time"] + " | " + problem["what"]
              + " | base " + problem["base"] + " | p15 " + problem["p15"])
        shown = shown + 1


main()
