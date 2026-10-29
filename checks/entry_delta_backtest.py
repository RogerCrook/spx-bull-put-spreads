"""
CHECK: the entry delta of the backtest's own positions (sec:realised-entry-delta)
(review_log T63)

What this file is for:
    Every cycle of the backtest records, when it opens, the delta of the whole
    position Delta_0 (column delta0 of the trade log), the implied volatilities
    of its two puts and the at-the-money volatility of its expiry. This file
    computes from the trade log every number of sec:realised-entry-delta:
    the statistics of tab:entry-delta-stats, the histogram of
    tab:entry-delta-hist, the mean per year of entry, how far the listed
    strikes are from their targets, and the distances to an absolute band
    [0.20, 0.40] (no longer in the thesis: the paragraph "Consequence for the
    band" was removed on 2026-10-28, T65).

    Until 2026-10-28 that subsection reported a separate study instead: one
    position built on paper every trading day at 10:00
    (Code/s10_entry_delta.py; its check script, checks/check_entry.py, was
    removed on 2026-10-29). Arian replaced it with the positions the backtest
    actually opened (review_log T63).

    The base case at mid is the run the subsection reports; the base case
    crossing the spread is printed after it for comparison.

Data: results/trades_base_mid.csv and results/trades_base_cross.csv.
Read-only: writes nothing. Takes a second.
Run it from the main folder:   python checks/entry_delta_backtest.py
"""

import pandas as pd                          # pandas works with tables
from scipy.stats import norm                 # norm.cdf(x) is N(x), the normal distribution function


for run in ("base_mid", "base_cross"):

    trades = pd.read_csv("results/trades_" + run + ".csv")   # one row per cycle
    delta0 = trades["delta0"]                # the entry delta of two spreads

    print("=" * 80)
    print(run)
    print("=" * 80)

    # ---- tab:entry-delta-stats ----
    print("entries %d | mean %.4f | sd %.4f | min %.4f | max %.4f" % (
        len(delta0), delta0.mean(), delta0.std(), delta0.min(), delta0.max()))

    # .quantile(q): the value a share q of the entries lie below
    print("quantiles 1/5/25/50/75/95/99%%: %s" % [round(delta0.quantile(q), 4) for q in [.01, .05, .25, .5, .75, .95, .99]])

    print("mean iv ATM / sold / bought: %.2f%% / %.2f%% / %.2f%%" % (
        100 * trades["atm_iv0"].mean(), 100 * trades["iv_short0"].mean(), 100 * trades["iv_long0"].mean()))
    print("mean vol gap bought - sold: %.1f points" % (100 * (trades["iv_long0"] - trades["iv_short0"]).mean()))

    print("flat-vol value 2*(N(2.3)-N(1)) = %.4f" % (2 * (norm.cdf(2.3) - norm.cdf(1))))

    # ---- tab:entry-delta-hist ----
    # pd.cut puts each entry into one of the bins [0.20, 0.22), [0.22, 0.24), ...
    # (right=False: the left edge belongs to the bin, the right edge does not);
    # value_counts counts the entries per bin, sort_index puts the bins in order
    bins = [0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.32, 0.34]
    histogram = pd.cut(delta0, bins, right=False).value_counts().sort_index()
    print("histogram (bin: entries, share):")
    for interval in histogram.index:
        count = histogram[interval]
        print("   [%.2f, %.2f): %4d  %5.1f%%" % (interval.left, interval.right, count, 100 * count / len(delta0)))
    print("   outside the bins: %d" % (len(delta0) - histogram.sum()))

    # ---- the maturities and the roots ----
    print("dte at entry: min %d | median %.0f | max %d" % (
        trades["dte0"].min(), trades["dte0"].median(), trades["dte0"].max()))
    # groupby puts the cycles of each maturity rule together
    for rule, cycles in trades.groupby("maturity_rule"):
        print("   %-8s %3d entries, median dte %.0f, median Delta_0 %.4f" % (
            rule, len(cycles), cycles["dte0"].median(), cycles["delta0"].median()))
    print("roots:", trades["root"].value_counts().to_dict())

    # how far each listed strike is from its target, in per cent (.abs(): either side)
    short_gap = (trades["strike_short"] / trades["target_short"] - 1).abs() * 100
    long_gap = (trades["strike_long"] / trades["target_long"] - 1).abs() * 100
    # long_gap > 2 gives True/False per cycle; .loc[..., "entry_time"] lists where it is True
    print("strike vs target: sold max %.2f%% | bought max %.2f%%, > 2%% on %d entries: %s" % (
        short_gap.max(), long_gap.max(), int((long_gap > 2).sum()),
        list(trades.loc[long_gap > 2, "entry_time"])))

    # the mean entry delta of each year of entry ("2012-01-03 10:00:00" -> "2012")
    yearly = trades.groupby(trades["entry_time"].str[:4])["delta0"].mean()
    print("annual means %.3f - %.3f" % (yearly.min(), yearly.max()))

    # ---- an absolute band [0.20, 0.40] (no longer in the thesis, T65) ----
    to_profit = delta0 - 0.20                # room down to the profit edge
    to_loss = 0.40 - delta0                  # room up to the loss edge
    print("absolute band: to 0.20 median %.3f range %.3f-%.3f, < 0.05 on %.1f%% | to 0.40 median %.3f range %.3f-%.3f" % (
        to_profit.median(), to_profit.min(), to_profit.max(), 100 * (to_profit < 0.05).mean(),
        to_loss.median(), to_loss.min(), to_loss.max()))
    print()
