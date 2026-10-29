"""
CHECK: exits and trading cost at the stock-close snapshot, in the runs made
without the rule "no decision at the stock close" (sec:monitoring, "Decision
times"; reproduction inventory, row 23; review_log C9, "check C")

What this file is for:
    sec:monitoring says that in runs of the backtest with decisions at every
    snapshot, 16:00 has more exits than its neighbouring snapshots (15:45 and
    16:15), split about evenly between profit and loss exits, and that
    crossing the spread costs about twice as much there. This file counts the
    exits at those three snapshots and computes the cost of crossing the
    spread there, from the trade logs.

    The cost of crossing the spread, per trade:
      at entry:  credit at mid  minus  credit received   (credit_mid - credit)
      at exit:   cost paid      minus  cost at mid       (cost - cost_mid)

    Since 2026-10-29 it reads the two current runs of the base case with the
    rule switched off (made 2026-10-28 by Code/s11_backtest.py through
    Code/s12_run_variants.py, SKIP_CLOSE_SNAPSHOT = False, and QUOTE_RULE =
    "off" as well). Until then it read the four first runs of 2026-10-08
    (made by an earlier version of the code, both removed on 2026-10-29),
    which gave the figures 29 / 18 / 17 and 4.54 / 3.78 of the thesis then.

Data: results/trades_base_mid_without_close_rule.csv,
      results/trades_base_cross_without_close_rule.csv.
Read-only: writes nothing. Takes a second.
Run it from the main folder:   python checks/check_close_snapshot.py
"""

import pandas as pd                          # pandas works with tables


# the two runs without the rule: name in the thesis -> trade log
RUNS = {
    "base, mid":      "results/trades_base_mid_without_close_rule.csv",
    "base, cross":    "results/trades_base_cross_without_close_rule.csv",
}

CLOSE_AND_NEIGHBOURS = ["15:45", "16:00", "16:15"]   # the stock close and the snapshots around it


for name in RUNS:                            # one run at a time

    trades = pd.read_csv(RUNS[name])         # one row per finished trade

    # the time of day of each exit and entry: characters 11 to 15 of "2020-03-16 16:00:00"
    trades["exit_clock"] = trades["exit_time"].str[11:16]
    trades["entry_clock"] = trades["entry_time"].str[11:16]

    print(name, "(", len(trades), "trades )")

    # ---- exits per snapshot ----
    # value_counts counts how many trades share each exit time of day
    exits_per_clock = trades["exit_clock"].value_counts()

    # the average over the intraday snapshots, leaving out 09:45, where
    # the overnight gap piles up exits (and the gamma exits all happen)
    intraday = exits_per_clock.drop("09:45", errors="ignore")    # errors="ignore": fine if 09:45 is missing
    print("   exits: 15:45 %d | 16:00 %d | 16:15 %d | average intraday snapshot (without 09:45) %.1f" % (
        exits_per_clock.get("15:45", 0), exits_per_clock.get("16:00", 0),
        exits_per_clock.get("16:15", 0), intraday.mean()))

    # the 16:00 exits by reason (profit, loss, gamma)
    at_1600 = trades[trades["exit_clock"] == "16:00"]
    print("   16:00 exits by reason:", dict(at_1600["reason"].value_counts()))

    # ---- cost of crossing the spread (only in the runs that cross it) ----
    if "cross" in name:

        trades["entry_cost"] = trades["credit_mid"] - trades["credit"]     # given up when selling
        trades["exit_cost"] = trades["cost"] - trades["cost_mid"]          # paid extra when buying back

        for clock in CLOSE_AND_NEIGHBOURS:

            entries_here = trades[trades["entry_clock"] == clock]        # trades opened at this time
            exits_here = trades[trades["exit_clock"] == clock]           # trades closed at this time

            print("   at %s: entry cost %.2f points (%d entries) | exit cost %.2f points (%d exits)" % (
                clock, entries_here["entry_cost"].mean(), len(entries_here),
                exits_here["exit_cost"].mean(), len(exits_here)))

        # the two parts must add up to the stored total spread cost
        print("   check: entry + exit cost %.1f points, stored spread_cost %.1f points" % (
            trades["entry_cost"].sum() + trades["exit_cost"].sum(), trades["spread_cost"].sum()))

    print()
