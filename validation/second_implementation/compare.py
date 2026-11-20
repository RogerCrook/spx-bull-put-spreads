"""
Compare the second implementation of the backtest with the project's backtest,
cycle by cycle and day by day (validation method 3).

Reads only:
    validation/second_implementation/output/trades_<run>.csv, equity_<run>.csv   (ours)
    results/trades_<run>.csv, results/equity_<run>.csv                            (the project's)
for the runs base_mid, base_cross, p15_mid, p15_cross. It writes nothing into
results/. The report is printed and saved as
validation/second_implementation/comparison.txt.

How to run (from the main folder):
    python validation/second_implementation/compare.py
"""

import math                     # isnan, fabs
import pandas as pd             # to read the CSV files


# ============================================================================
# Settings
# ============================================================================

OURS_FOLDER = "validation/second_implementation/output"        # our result files
PROJECT_FOLDER = "results"                                     # the project's result files
REPORT_FILE = "validation/second_implementation/comparison.txt"

RUNS = ["base_mid", "base_cross", "p15_mid", "p15_cross"]

# Two numbers count as equal if they differ by at most this much. The files
# store about 6 to 15 significant digits, so 1e-6 (absolute) is far below any
# difference that could change a decision (deltas are compared with bands of
# 0.10, prices are quoted in steps of 0.05 points).
TOLERANCE = 1e-6

# The fields of a cycle: our column name -> the project's column name.
TRADE_FIELDS = [
    ("exit_time", "exit_time"),
    ("root", "root"),
    ("expiration", "expiration"),
    ("days_at_entry", "dte0"),
    ("days_at_exit", "dte_exit"),
    ("maturity_rule", "maturity_rule"),
    ("forward", "forward0"),
    ("atm_vol", "atm_iv0"),
    ("target_short", "target_short"),
    ("target_long", "target_long"),
    ("short_strike", "strike_short"),
    ("long_strike", "strike_long"),
    ("short_iv_entry", "iv_short0"),
    ("long_iv_entry", "iv_long0"),
    ("credit", "credit"),
    ("credit_mid", "credit_mid"),
    ("entry_delta", "delta0"),
    ("exit_reason", "reason"),
    ("exit_delta", "delta_exit"),
    ("short_iv_exit", "iv_short_exit"),
    ("long_iv_exit", "iv_long_exit"),
    ("cost_to_close", "cost"),
    ("cost_to_close_mid", "cost_mid"),
    ("pnl_points", "pnl"),
    ("deficit_before", "deficit_at_entry"),
    ("deficit_after", "deficit_after"),
    ("margin", "margin"),
]

# Our name of the maturity rule "shortest expiry with at least 30 days" is
# "base", the project's is "target". The other two names are the same.
RULE_NAMES = {"base": "target", "recovery": "recovery", "cap": "cap"}


# ============================================================================
# Helpers
# ============================================================================

def same_value(ours, theirs):
    """
    True if two cells hold the same value: numbers within TOLERANCE, text
    exactly. Two empty cells (NaN) count as equal.
    """
    ours_is_number = isinstance(ours, (int, float))             # isinstance asks "is this a number?"
    theirs_is_number = isinstance(theirs, (int, float))
    if ours_is_number and theirs_is_number:
        if math.isnan(ours) and math.isnan(theirs):
            return True                                         # both empty
        if math.isnan(ours) or math.isnan(theirs):
            return False                                        # only one empty
        return math.fabs(ours - theirs) <= TOLERANCE
    return str(ours) == str(theirs)                             # text: compare as written


def table_rows(table):
    """
    Turn a table into a list of dictionaries, one per row (column -> value),
    so the rest of the script can use plain loops.
    .to_dict("records") does exactly that.
    """
    return table.to_dict("records")


# ============================================================================
# Cycles
# ============================================================================

def compare_trades(run, lines):
    """
    Line up the cycles of both backtests by entry time and report every field
    that differs. Returns the number of identical cycles and the totals.
    """
    ours = table_rows(pd.read_csv(OURS_FOLDER + "/trades_" + run + ".csv"))
    theirs = table_rows(pd.read_csv(PROJECT_FOLDER + "/trades_" + run + ".csv"))

    # Dictionaries entry time -> cycle, for each side.
    ours_by_entry = {}
    for cycle in ours:
        ours_by_entry[cycle["entry_time"]] = cycle
    theirs_by_entry = {}
    for cycle in theirs:
        theirs_by_entry[cycle["entry_time"]] = cycle

    # Every entry time that occurs on either side, in time order.
    all_entries = sorted(set(ours_by_entry) | set(theirs_by_entry))   # | joins two sets

    identical = 0
    first_divergence = None
    differences = []                                            # (entry time, text) for each difference
    for entry_time in all_entries:
        our_cycle = ours_by_entry.get(entry_time)
        their_cycle = theirs_by_entry.get(entry_time)
        if our_cycle is None:
            differences.append((entry_time, "cycle only in the project's backtest"))
            if first_divergence is None:
                first_divergence = entry_time
            continue
        if their_cycle is None:
            differences.append((entry_time, "cycle only in the second implementation"))
            if first_divergence is None:
                first_divergence = entry_time
            continue

        fields_that_differ = []
        for our_name, their_name in TRADE_FIELDS:
            our_value = our_cycle[our_name]
            their_value = their_cycle[their_name]
            if our_name == "maturity_rule":
                our_value = RULE_NAMES.get(our_value, our_value)   # translate our rule name
            if not same_value(our_value, their_value):
                fields_that_differ.append(our_name + ": ours " + str(our_value) + ", project " + str(their_value))

        if len(fields_that_differ) == 0:
            identical = identical + 1
        else:
            if first_divergence is None:
                first_divergence = entry_time
            for text in fields_that_differ:
                differences.append((entry_time, text))

    lines.append("Run " + run)
    lines.append("  cycles: ours " + str(len(ours)) + ", project " + str(len(theirs))
                 + ", entry times on either side " + str(len(all_entries)))
    share = 100.0 * identical / len(all_entries)
    lines.append("  identical cycles (all " + str(len(TRADE_FIELDS)) + " fields): " + str(identical)
                 + " (" + format(share, ".1f") + " %)")
    lines.append("  first divergence: " + str(first_divergence))
    for entry_time, text in differences:
        lines.append("    " + entry_time + "  " + text)

    # The largest difference of each numeric field, over the cycles on both sides.
    lines.append("  largest absolute difference per numeric field (cycles on both sides):")
    for our_name, their_name in TRADE_FIELDS:
        largest = 0.0
        is_numeric = True
        for entry_time in all_entries:
            our_cycle = ours_by_entry.get(entry_time)
            their_cycle = theirs_by_entry.get(entry_time)
            if our_cycle is None or their_cycle is None:
                continue
            our_value = our_cycle[our_name]
            their_value = their_cycle[their_name]
            if not isinstance(our_value, (int, float)) or not isinstance(their_value, (int, float)):
                is_numeric = False
                break
            if math.isnan(our_value) or math.isnan(their_value):
                continue
            largest = max(largest, math.fabs(our_value - their_value))
        if is_numeric:
            lines.append("    " + our_name + ": " + format(largest, ".2e"))

    return identical, len(all_entries)


# ============================================================================
# Days
# ============================================================================

def compare_days(run, lines):
    """
    Compare the daily rows: margin, interest, P&L of the day and the open P&L
    of the position still held, and the return of each year from both files
    (P&L of the year / average daily margin, sec:results-main).
    """
    ours = table_rows(pd.read_csv(OURS_FOLDER + "/equity_" + run + ".csv"))
    theirs = table_rows(pd.read_csv(PROJECT_FOLDER + "/equity_" + run + ".csv"))

    theirs_by_date = {}
    for day in theirs:
        theirs_by_date[day["date"]] = day

    # Our column -> the project's column. The project's "unrealised" is the
    # open P&L of the position held (a level, not a change), "pnl_day" the
    # total P&L of the day.
    day_fields = [("margin", "margin"), ("interest", "interest_today"),
                  ("total_pnl", "pnl_day"), ("open_pnl", "unrealised")]

    largest = {}
    days_differing = {}
    for our_name, their_name in day_fields:
        largest[our_name] = 0.0
        days_differing[our_name] = 0
    missing_days = 0
    for day in ours:
        their_day = theirs_by_date.get(day["date"])
        if their_day is None:
            missing_days = missing_days + 1
            continue
        for our_name, their_name in day_fields:
            difference = math.fabs(day[our_name] - their_day[their_name])
            if difference > largest[our_name]:
                largest[our_name] = difference
            if difference > 0.01:                               # more than one cent
                days_differing[our_name] = days_differing[our_name] + 1

    lines.append("  days: ours " + str(len(ours)) + ", project " + str(len(theirs))
                 + ", our days missing in the project's file " + str(missing_days))
    for our_name, their_name in day_fields:
        lines.append("    " + our_name + ": days differing by more than one cent "
                     + str(days_differing[our_name]) + ", largest difference "
                     + format(largest[our_name], ".2e") + " dollars")

    # Return of each year from both daily files, the same formula for both.
    our_returns = returns_by_year(ours, "total_pnl", "margin")
    their_returns = returns_by_year(theirs, "pnl_day", "margin")
    lines.append("  return of each year in per cent (ours / project):")
    for year in sorted(our_returns):
        their_value = their_returns.get(year, float("nan"))
        lines.append("    " + year + ": " + format(our_returns[year], ".2f") + " / " + format(their_value, ".2f"))
    lines.append("    per year over the sample: " + format(whole_sample_return(ours, "total_pnl", "margin"), ".2f")
                 + " / " + format(whole_sample_return(theirs, "pnl_day", "margin"), ".2f"))


def returns_by_year(days, pnl_column, margin_column):
    """
    Return of each year in per cent: P&L of the year / average daily margin.
    """
    pnl = {}
    margin_sum = {}
    count = {}
    for day in days:
        year = str(day["date"])[:4]
        if year not in pnl:
            pnl[year] = 0.0
            margin_sum[year] = 0.0
            count[year] = 0
        pnl[year] = pnl[year] + day[pnl_column]
        margin_sum[year] = margin_sum[year] + day[margin_column]
        count[year] = count[year] + 1
    answer = {}
    for year in pnl:
        answer[year] = 100.0 * pnl[year] / (margin_sum[year] / count[year])
    return answer


def whole_sample_return(days, pnl_column, margin_column):
    """
    tab:results-years, last row: total P&L / average daily margin / (days / 252).
    """
    total = 0.0
    margin_sum = 0.0
    for day in days:
        total = total + day[pnl_column]
        margin_sum = margin_sum + day[margin_column]
    return 100.0 * total / (margin_sum / len(days)) / (len(days) / 252.0)


# ============================================================================
# Main
# ============================================================================

def main():
    lines = []
    lines.append("Second implementation against the project's backtest")
    lines.append("Tolerance for numbers: " + str(TOLERANCE))
    lines.append("")
    for run in RUNS:
        compare_trades(run, lines)
        compare_days(run, lines)
        lines.append("")
    with open(REPORT_FILE, "w") as report:
        report.write("\n".join(lines) + "\n")
    print("\n".join(lines))


main()
