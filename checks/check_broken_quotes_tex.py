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
      1. per run: the snapshots at which a position is held, and those
         skipped because a quote was broken;
         over all four runs: how large the two measures usually are;
         for the base case at mid: how many quotes meet condition 1, 1 and 2,
         and all three conditions of def:broken;
      2. the two example quotes of the thesis (3 April 2020 and 5 August 2024);
      3. three figures of sec:backtest-design, without and with the rule:
         quarters in which compounding shows a loss although the strategy made
         money, the average margin of the cycles opened in 2012 and 2026, and
         the forward at the first and the last cycle (cost discussion, tab:costs).

    Rewritten 2026-10-27 in the style of Code/s03_rates.py; same calculations
    and the same printout as before (old version in
    old_versions/checks_before_style_2026-10-27/).

Data: results/quotes_*_c8c9q.csv (four runs), results/trades_base_mid*.csv and
      results/equity_base_mid*.csv (without and with the rule).
Read-only: writes nothing. Takes about a minute.
Run it from the main folder:   python checks/check_broken_quotes_tex.py
"""

import pandas as pd                          # pandas works with tables


RESULTS = "results/"
RUNS = ["base_mid", "base_cross", "p15_mid", "p15_cross"]


# ---- 1. snapshots per run, and how large the two measures usually are ----------

tables = []                                  # the four quote tables, glued together below

for run in RUNS:

    quotes = pd.read_csv(RESULTS + "quotes_" + run + "_c8c9q.csv")
    quotes["run"] = run                      # remember which run each row came from

    # an empty "action" comes back from the CSV as a missing value (NaN);
    # fillna("") turns it into empty text, which means "held, nothing done"
    quotes["action"] = quotes["action"].fillna("")
    tables.append(quotes)

    # one held snapshot = two rows (short and long leg); drop_duplicates keeps
    # the first row of each snapshot time, so every snapshot counts once
    held = quotes[quotes["kind"] == "held"].drop_duplicates(["time"])

    # .str.contains("broken"): True where the action text contains "broken"
    skipped = quotes[quotes["action"].str.contains("broken")].drop_duplicates(["time", "kind"])

    print("%-10s held snapshots %d, skipped (broken) %d: %s" % (
        run, len(held), len(skipped), ", ".join(skipped["time"])))

# pd.concat glues the four tables below each other; reset_index(drop=True)
# numbers the rows 0, 1, 2, ... again (otherwise each table's numbers repeat)
everything = pd.concat(tables).reset_index(drop=True)

# the rows that have an earlier quote to compare with (.notna(): True where not empty)
compared = everything[everything["vol_jump"].notna()]
print("\nquotes compared with an earlier one (all four runs): %d of %d rows" % (len(compared), len(everything)))

# .quantile(0.99): the value 99% of the rows lie below; vol_jump is in decimals, * 100 = vol points
print("vol jump (vol points): median %.2f, 99%% %.2f, 99.9%% %.2f" % (
    100 * compared["vol_jump"].median(), 100 * compared["vol_jump"].quantile(0.99),
    100 * compared["vol_jump"].quantile(0.999)))
print("width ratio: median %.2f, 99%% %.2f, 99.9%% %.2f" % (
    compared["width_ratio"].median(), compared["width_ratio"].quantile(0.99),
    compared["width_ratio"].quantile(0.999)))

# how often each condition of def:broken holds, base case at mid
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
show("2024-08-05 09:45:00", 5010.0)          # the genuine selloff that is not broken


# ---- 3. three figures of sec:backtest-design, without and with the rule --------------

def compound(daily_returns):
    """Compound a list of daily returns: (1 + r1) * (1 + r2) * ... - 1."""
    growth = 1.0
    for r in daily_returns:
        growth = growth * (1 + r)
    return growth - 1


for tag in ("_c8c9", "_c8c9q"):              # without the rule, then with it

    trades = pd.read_csv(RESULTS + "trades_base_mid" + tag + ".csv")
    equity = pd.read_csv(RESULTS + "equity_base_mid" + tag + ".csv")

    # the quarter of each day, e.g. "2012-Q1": .str[:4] is the year, .dt.quarter gives 1 to 4
    equity["quarter"] = equity["date"].str[:4] + "-Q" + pd.to_datetime(equity["date"]).dt.quarter.astype(str)

    # Compounding: the daily return is the day's P&L over the margin of the day
    # before. .shift(1) moves the margin column down one row, so each day sees
    # yesterday's margin; the first day has none, so fillna gives it its own
    # margin, and its return is set to 0.
    margin_before = equity["margin"].shift(1).fillna(equity["margin"].iloc[0])
    equity["r"] = equity["pnl_day"] / margin_before
    equity.loc[0, "r"] = 0.0                 # row 0 is the first day

    compounded = {}                          # quarter -> compounded return
    simple = {}                              # quarter -> P&L of the quarter
    for quarter, days in equity.groupby("quarter"):         # each quarter with its days
        compounded[quarter] = compound(days["r"])
        simple[quarter] = days["pnl_day"].sum()

    artefacts = 0                            # quarters that made money but compound to a loss
    for quarter in compounded:
        if compounded[quarter] < 0 and simple[quarter] > 0:
            artefacts = artefacts + 1

    # the average margin of the cycles opened in each year ("2012-..." -> "2012")
    margin_by_year = trades.groupby(trades["entry_time"].str[:4])["margin"].mean()

    print("base mid%s: compounding artefact %d of %d quarters; margin 2012 / 2026 entries %.0f / %.0f; "
          "forward first / last trade %.0f / %.0f" % (
              tag, artefacts, len(compounded), margin_by_year["2012"], margin_by_year["2026"],
              trades["forward0"].iloc[0], trades["forward0"].iloc[-1]))
