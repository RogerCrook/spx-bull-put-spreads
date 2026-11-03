"""
CHECK: the entry delta of the backtest's own positions (review_log T63)

What this file is for:
    Every cycle of the backtest records, when it opens, the delta of the whole
    position Delta_0 (column delta0 of the trade log) and the implied
    volatilities of its two puts. The thesis gives, after prop:entry-delta and
    in its footnote, the number of entries, the mean Delta_0 ("averages 0.27",
    0.2679 in the footnote) and the mean implied volatility of the sold and of
    the bought put. This file computes them from the trade log of the base case
    at mid.

    Until 2026-11-03 (review_log T112) it also computed the figures of
    sec:realised-entry-delta, set aside in Masterarbeit_Tex_file/set_aside_ch4.tex
    on 2026-10-30 (statistics, histogram, maturities, strikes against targets,
    yearly means, an absolute band [0.20, 0.40]), for the base case at mid and
    crossing the spread. That code is in commit cf6519a (tag thesis-v4).

Data: results/trades_base_mid.csv.
Read-only: writes nothing. Takes a second.
Run it from the main folder:   python checks/entry_delta_backtest.py
"""

import pandas as pd                          # pandas works with tables


trades = pd.read_csv("results/trades_base_mid.csv")   # one row per cycle

print("entries %d | mean Delta_0 %.4f" % (len(trades), trades["delta0"].mean()))
print("mean implied volatility, sold put %.2f%% | bought put %.2f%%" % (
    100 * trades["iv_short0"].mean(), 100 * trades["iv_long0"].mean()))
