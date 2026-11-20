"""
COMPARE THE BLIND CALCULATOR WITH THE BACKTEST

What this file is for:
    The blind calculator (calculator.py, written from the thesis only) worked
    out what the strategy must do at the 32 hand-check snapshots and saved its
    answers in calc_output/answers.csv. This file looks up what the backtest
    did at the same snapshots, in its logs in results/, and prints both side
    by side, field by field, with "same" or "DIFFERENT".

    What the backtest did is read from:
      trades_<run>.csv  : an exit at the snapshot (reason, cost, P&L, new
                          deficit) and the position opened there
      quotes_<run>.csv  : a held snapshot ("held", or "skipped (broken)")
      missing_<run>.csv : a held snapshot with a leg missing
      equity_<run>.csv  : the equity day (unrealised, interest, margin, day P&L)
    A snapshot found in none of them is the stock close (no decision).

    It only reads. It writes calc_output/comparison.csv (one row per field).

To run it (from the main folder, a few seconds):
    python validation/hand_checks/compare.py
"""

import pandas as pd                 # pandas works with tables


# ---- settings ----------------------------------------------------------------

ANSWERS_FILE = "validation/hand_checks/calc_output/answers.csv"     # the calculator's answers
OUT_FILE = "validation/hand_checks/calc_output/comparison.csv"      # the result of this file
RESULTS = "results"                                                 # the backtest's logs

TOLERANCE = 0.0005                  # two numbers count as the same if they differ by less
                                    # (the logs and the packets round to 4-6 decimals)

# the fields compared when the backtest exits at the snapshot:
# (name in answers.csv, name in the trade log, which trade: the one closed or the one opened)
EXIT_FIELDS = [
    ("exit_cost", "cost", "closed"),
    ("pnl", "pnl", "closed"),
    ("new_deficit", "deficit_after", "closed"),
    ("position_delta", "delta_exit", "closed"),
]
ENTRY_FIELDS = [
    ("new_root", "root", "opened"),
    ("new_expiry", "expiration", "opened"),
    ("new_dte", "dte0", "opened"),
    ("maturity_rule", "maturity_rule", "opened"),
    ("target_short", "target_short", "opened"),
    ("target_long", "target_long", "opened"),
    ("strike_short", "strike_short", "opened"),
    ("strike_long", "strike_long", "opened"),
    ("credit", "credit", "opened"),
    ("entry_delta", "delta0", "opened"),
    ("gamma_exit_days", "exit_days", "opened"),
    ("margin", "margin", "opened"),
]


# ---- helpers --------------------------------------------------------------------

def same(a, b):
    """
    True if the two values agree: numbers within TOLERANCE, anything else as text.
    Both empty also counts as the same.
    """

    a_empty = pd.isna(a) or str(a) == ""            # pd.isna: True for an empty cell
    b_empty = pd.isna(b) or str(b) == ""
    if a_empty and b_empty:
        return True
    if a_empty or b_empty:
        return False

    # try to read both as numbers; float() raises ValueError for text like "SPXW"
    try:
        number_a = float(a)
        number_b = float(b)
        return abs(number_a - number_b) < TOLERANCE
    except ValueError:
        return str(a) == str(b)


def calculator_outcome(answer):
    """What the calculator says happens at the snapshot, as one word."""

    if answer["decision_allowed"] == "no":
        return "no decision (stock close)"
    if pd.isna(answer["exit_reason"]) and pd.isna(answer["legs_usable"]):
        return "no position, open one"                  # the first snapshot
    if not pd.isna(answer["broken_leg"]) and answer["broken_leg"] != "none":
        return "skipped (broken)"
    if answer["legs_usable"] == "no":
        return "skipped (leg missing)"
    if answer["exit_reason"] == "none":
        return "held"
    return answer["exit_reason"]                         # "loss", "profit" or "gamma"


def backtest_outcome(run, when, logs):
    """
    What the backtest did at the snapshot, as one word, and the trade it closed
    and the trade it opened there (None if none).
    """

    trades = logs[run]["trades"]

    closed = None
    opened = None
    # go through the trades one at a time (iterrows: one row at a time)
    for _, trade in trades.iterrows():
        if trade["exit_time"] == when:
            closed = trade
        if trade["entry_time"] == when:
            opened = trade

    if closed is not None:
        return closed["reason"], closed, opened

    if opened is not None:
        return "no position, open one", closed, opened

    # no trade starts or ends here: look in the quote log (short leg of a held position)
    quotes = logs[run]["quotes"]
    is_here = (quotes["time"] == when) & (quotes["kind"] == "held") & (quotes["leg"] == "short")
    rows = quotes[is_here]
    if len(rows) > 0:
        action = rows.iloc[0]["action"]                  # .iloc[0]: the first row
        if pd.isna(action):
            return "held", None, None
        return action, None, None

    missing = logs[run]["missing"]
    if when in missing["when"].tolist():                 # .tolist(): the column as a plain list
        return "skipped (leg missing)", None, None

    return "no decision (stock close)", None, None


# ---- main -------------------------------------------------------------------------

def main():

    answers = pd.read_csv(ANSWERS_FILE)

    # the logs of each run that occurs in the list, read once
    logs = {}
    for run in answers["run"].unique():                  # .unique(): each run once
        logs[run] = {
            "trades": pd.read_csv(RESULTS + "/trades_" + run + ".csv"),
            "quotes": pd.read_csv(RESULTS + "/quotes_" + run + ".csv"),
            "missing": pd.read_csv(RESULTS + "/missing_" + run + ".csv"),
            "equity": pd.read_csv(RESULTS + "/equity_" + run + ".csv"),
        }

    rows = []                                            # one dictionary per compared field

    # in time order, so the printout reads like the history
    answers = answers.sort_values("snapshot")

    for _, answer in answers.iterrows():

        h = answer["hand_check"]
        run = answer["run"]
        when = answer["snapshot"]

        # ---- the equity day ----------------------------------------------
        if when.endswith("(day)"):
            date = when[:10]
            equity = logs[run]["equity"]
            day = equity[equity["date"] == date].iloc[0]
            pairs = [
                ("day unrealised (dollars)", answer["day_unrealised_points"] * 100, day["unrealised"]),
                ("day interest (dollars)", answer["day_interest_dollars"], day["interest_today"]),
                ("day margin (dollars)", answer["day_margin"], day["margin"]),
                ("day P&L (dollars)", answer["day_pnl_dollars"], day["pnl_day"]),
            ]
            for name, calc_value, backtest_value in pairs:
                rows.append({"hand_check": h, "run": run, "snapshot": when, "field": name,
                             "calculator": calc_value, "backtest": backtest_value,
                             "same": same(calc_value, backtest_value)})
            continue

        # ---- what happened -----------------------------------------------
        calc_what = calculator_outcome(answer)
        backtest_what, closed, opened = backtest_outcome(run, when, logs)
        rows.append({"hand_check": h, "run": run, "snapshot": when, "field": "outcome",
                     "calculator": calc_what, "backtest": backtest_what,
                     "same": calc_what == backtest_what})

        # ---- the numbers of an exit and of the new position ----------------
        fields = []
        if closed is not None:
            fields = fields + EXIT_FIELDS
        if opened is not None:
            fields = fields + ENTRY_FIELDS

        for calc_name, log_name, which in fields:
            calc_value = answer[calc_name]
            if which == "closed":
                backtest_value = closed[log_name]
            else:
                backtest_value = opened[log_name]
            rows.append({"hand_check": h, "run": run, "snapshot": when, "field": calc_name,
                         "calculator": calc_value, "backtest": backtest_value,
                         "same": same(calc_value, backtest_value)})

    table = pd.DataFrame(rows)                           # list of dictionaries -> table
    table.to_csv(OUT_FILE, index=False)                  # index=False: no pandas row numbers

    # ---- the summary ------------------------------------------------------------
    print("fields compared:", len(table))
    print("the same:       ", int(table["same"].sum()))  # True counts as 1, so the sum counts them
    print()
    print("outcome at each snapshot:")
    for row in rows:
        if row["field"] == "outcome" or row["field"].startswith("day"):
            if row["same"]:
                mark = "same     "
            else:
                mark = "DIFFERENT"
            print(" ", row["hand_check"], row["snapshot"], mark, "| calculator:", row["calculator"],
                  "| backtest:", row["backtest"])
    print()
    print("fields that differ:")
    for row in rows:
        if not row["same"]:
            print(" ", row["hand_check"], row["snapshot"], row["field"],
                  "| calculator:", row["calculator"], "| backtest:", row["backtest"])
    print("written:", OUT_FILE)


# Only run main() when this file is started directly, not when another file imports it.
if __name__ == "__main__":
    main()
