"""
CHECK: the numbers of sec:broken-quotes and a few of sec:backtest-design
(reproduction inventory, rows 25, 27, 28)

What this file is for:
    The backtest writes, for each reported run, a "quotes" file with one row
    per leg and snapshot: the quote now (bid, ask, implied volatility), the
    same option's quote at the previous snapshot the backtest used
    (bid_before, ask_before, iv_before), the two measures of def:broken
    (vol_jump and width_ratio) and what the backtest did ("action").

    From these files this file computes:
      1. per run: the snapshots at which a position is held, those skipped
         because a quote was broken, and the entries refused because a quote
         was broken;
         for the base case at mid: how many quotes meet condition 1, 1 and 2,
         and all three conditions of def:broken;
      2. the example quotes of the thesis: the 1990 put of 3 April 2020 at
         10:00 (against 09:45) and at 10:15 (against the broken 10:00 quote:
         the snapshot before is every snapshot except the stock close, also
         one skipped for a broken quote, as in def:broken), and the 5010 put
         of 5 August 2024;
      3. two figures of sec:backtest-design: the average margin of the cycles
         opened in 2012 and 2026, and the forward at the first and the last
         cycle (cost discussion, tab:costs);
      4. the first trade of the base case at mid that differs between the runs
         without and with the rule (added 2026-10-28: the March 2020 skips change
         no trade, the skip of 3 April 2020 does).

    Rewritten 2026-10-27 in the style of Code/s03_rates.py (old version in
    a folder old_versions/,
    removed on 2026-10-29). Changed 2026-10-29: the
    distribution of the two measures over all four runs and the count of
    quarters in which compounding shows a loss were dropped (no longer in the
    thesis since review_log T56 and T61); the 10:15 quote of 3 April 2020 and
    the count of refused entries were added (both are in the thesis).

    All runs are the current ones in results/ (made 2026-10-28 on the rebuilt
    data). Until 2026-10-28 this file read older runs (removed on 2026-10-29).

Data: results/quotes_*.csv (four runs), results/trades_base_mid.csv and
      results/trades_base_mid_without_quote_rule.csv.
Read-only: writes nothing. Takes about a minute.
Run it from the main folder:   python checks/check_broken_quotes_tex.py
"""

import pandas as pd                          # pandas works with tables


RESULTS = "results/"
RUNS = ["base_mid", "base_cross", "p15_mid", "p15_cross"]


# ---- 1. snapshots per run, and how often the conditions hold --------------------

tables = []                                  # the four quote tables, glued together below

for run in RUNS:

    quotes = pd.read_csv(RESULTS + "quotes_" + run + ".csv")
    quotes["run"] = run                      # remember which run each row came from

    # an empty "action" comes back from the CSV as a missing value (NaN);
    # fillna("") turns it into empty text, which means "held, nothing done"
    quotes["action"] = quotes["action"].fillna("")
    tables.append(quotes)

    # one held snapshot = two rows (short and long leg); drop_duplicates keeps
    # the first row of each snapshot time, so every snapshot counts once
    held = quotes[quotes["kind"] == "held"].drop_duplicates(["time"])

    # the backtest writes "skipped (broken)" at a held snapshot it skips and
    # "not opened (broken)" at an entry it refuses (Code/s11_backtest.py);
    # again each snapshot counts once
    skipped = quotes[quotes["action"] == "skipped (broken)"].drop_duplicates(["time"])
    refused = quotes[quotes["action"] == "not opened (broken)"].drop_duplicates(["time"])

    print("%-10s held snapshots %d, skipped (broken) %d: %s" % (
        run, len(held), len(skipped), ", ".join(skipped["time"])))
    print("%-10s entries refused (broken) %d" % (run, len(refused)))

# pd.concat glues the four tables below each other; reset_index(drop=True)
# numbers the rows 0, 1, 2, ... again (otherwise each table's numbers repeat)
everything = pd.concat(tables).reset_index(drop=True)

# the rows that have an earlier quote to compare with (.notna(): True where not empty)
compared = everything[everything["vol_jump"].notna()]

# how often each condition of def:broken holds, base case at mid
print()
base = compared[compared["run"] == "base_mid"]

width_now = base["ask"] - base["bid"]                        # how wide the quote is now
width_before = base["ask_before"] - base["bid_before"]       # and at the previous snapshot used
widened = width_now - width_before                           # how much it widened

mid_now = (base["ask"] + base["bid"]) / 2
mid_before = (base["ask_before"] + base["bid_before"]) / 2
moved = (mid_now - mid_before).abs()                         # how far the mid moved (.abs(): up or down)

# each line gives a column of True/False, one per quote
condition_1 = base["vol_jump"] > 0.03                        # vol jumped by more than 3 points
condition_2 = base["width_ratio"] > 3                        # more than 3 times as wide
condition_3 = widened > moved                                # widened by more than the mid moved

# & means "and", row by row; .sum() counts the Trues
print("base mid, rows: (1) %d, (2) %d, (1)+(2) %d, all three %d, of %d" % (
    condition_1.sum(), condition_2.sum(), (condition_1 & condition_2).sum(),
    (condition_1 & condition_2 & condition_3).sum(), len(base)))


# ---- 2. the two examples in the thesis --------------------------------------------

def show(time, strike):
    """Print the quote of the put with this strike at this snapshot, before and now."""

    rows = everything[(everything["time"] == time) & (everything["strike"] == strike)]
    rows = rows.drop_duplicates(["time", "strike"])         # the same quote appears in several runs

    for _, row in rows.iterrows():           # iterrows: one row at a time
        width_0 = row["ask_before"] - row["bid_before"]
        width_1 = row["ask"] - row["bid"]
        mid_0 = (row["ask_before"] + row["bid_before"]) / 2
        mid_1 = (row["ask"] + row["bid"]) / 2
        print("%s %s %s %.0f: %.2f / %.2f -> %.2f / %.2f, mid %.2f -> %.2f (moved %.2f), "
              "width %.2f -> %.2f (widened %.2f, ratio %.1f), iv %.1f%% -> %.1f%% (jump %.1f), action '%s'" % (
                  time, row["root"], row["expiration"], strike,
                  row["bid_before"], row["ask_before"], row["bid"], row["ask"],
                  mid_0, mid_1, abs(mid_1 - mid_0),
                  width_0, width_1, width_1 - width_0, width_1 / width_0,
                  100 * row["iv_before"], 100 * row["iv"], 100 * abs(row["iv"] - row["iv_before"]),
                  row["action"]))


print()
show("2020-04-03 10:00:00", 1990.0)          # the broken quote of sec:broken-quotes
show("2020-04-03 10:15:00", 1990.0)          # the same put one snapshot later, back to normal
show("2024-08-05 09:45:00", 5010.0)          # the genuine selloff that is not broken


# ---- 3. two figures of sec:backtest-design (base case at mid) -----------------------

trades = pd.read_csv(RESULTS + "trades_base_mid.csv")

# the average margin of the cycles opened in each year: .str[:4] keeps the
# first four characters of the entry time ("2012-..." -> "2012"), groupby
# collects the trades of each year, and .mean() averages their margins
margin_by_year = trades.groupby(trades["entry_time"].str[:4])["margin"].mean()

print()
print("base mid: margin 2012 / 2026 entries %.0f / %.0f; forward first / last trade %.0f / %.0f" % (
    margin_by_year["2012"], margin_by_year["2026"],
    trades["forward0"].iloc[0], trades["forward0"].iloc[-1]))


# ---- 4. which trades the rule changes (base case at mid) ----------------------------
# sec:broken-quotes says the skips of 9 and 16 March 2020 change no trade, while the
# skip of 3 April 2020 prevents a false exit. Both runs are compared trade by trade,
# in order, on when each cycle opened and closed, why it closed and its P&L: the
# first trade that differs shows where the rule starts to change the path.

without_rule = pd.read_csv(RESULTS + "trades_base_mid_without_quote_rule.csv")
with_rule = pd.read_csv(RESULTS + "trades_base_mid.csv")
COLUMNS = ["entry_time", "exit_time", "reason", "pnl"]

print()
print("trades: without the rule %d, with the rule %d" % (len(without_rule), len(with_rule)))

first_difference = None                      # None = no difference found (yet)
for i in range(min(len(without_rule), len(with_rule))):
    same = True
    for column in COLUMNS:
        # .iloc[i]: the i-th row, counted from 0
        if without_rule[column].iloc[i] != with_rule[column].iloc[i]:
            same = False
    if not same:
        first_difference = i
        break                                # stop at the first trade that differs

if first_difference is None:
    print("all trades identical")
else:
    print("identical up to trade %d (counted from 0), the first that differs:" % first_difference)
    for name, table in (("without", without_rule), ("with   ", with_rule)):
        row = table.iloc[first_difference]
        print("  %s the rule: opened %s, closed %s (%s), P&L %.2f" % (
            name, row["entry_time"], row["exit_time"], row["reason"], row["pnl"]))
