# Check of the "count" runs: with the broken-quote test only measured, every
# trade and every day of the equity curve must equal the thesis run
# (results/*_c8c9.csv). Read-only.
import pandas as pd

HERE = "C:/Dokumente/Python/Masterarbeit/experiments/quote_filter/"
RESULTS = "C:/Dokumente/Python/Masterarbeit/results/"

for run in ["base_mid", "base_cross", "p15_mid", "p15_cross"]:
    new_trades = pd.read_csv(HERE + "trades_" + run + "_count_c8c9.csv")
    old_trades = pd.read_csv(RESULTS + "trades_" + run + "_c8c9.csv")
    new_equity = pd.read_csv(HERE + "equity_" + run + "_count_c8c9.csv")
    old_equity = pd.read_csv(RESULTS + "equity_" + run + "_c8c9.csv")

    # the copy adds one column (skipped_broken); compare the columns both have
    extra = []
    for column in new_trades.columns:
        if column not in old_trades.columns:
            extra.append(column)
    same_shape = len(new_trades) == len(old_trades)
    differing = 0
    if same_shape:
        for column in old_trades.columns:
            a = old_trades[column]
            b = new_trades[column]
            # equal, or both empty (nan == nan is False, so test that separately)
            equal = (a == b) | (a.isna() & b.isna())
            differing = differing + int((~equal).sum())     # ~ means "not"
    # the daily total P&L, rounded to 6 decimals; .equals is True only if the
    # two columns are equal on every day
    equity_same = old_equity["total_pnl"].round(6).equals(new_equity["total_pnl"].round(6))
    print("%-10s trades %d vs %d, differing cells %d, extra columns %s, equity identical: %s" % (
        run, len(new_trades), len(old_trades), differing, extra, equity_same))
