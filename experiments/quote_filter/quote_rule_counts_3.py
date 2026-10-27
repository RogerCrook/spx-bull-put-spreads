# Third look at the rule (README, step 2), still without any P&L.
# quote_rule_counts_2.py: "the new quote brackets the previous one" removes the
# real fast markets, but misses the known case 2012-06-14 15:30 (put 1050:
# bid 0.10 -> 0.90, ask 2.5 -> 9.8, so the bid rose a little). A wider form of
# the same idea: the quote WIDENED more than its middle MOVED,
#     (width now - width before)  >  |mid now - mid before|
# i.e. the mid moved because the quote blew up, not because the market moved.
# (A quote that brackets the previous one always passes this.)
import pandas as pd                 # pandas works with tables

HERE = "C:/Dokumente/Python/Masterarbeit/experiments/quote_filter/"
RUNS = ["base_mid", "base_cross", "p15_mid", "p15_cross"]

quotes = {}
for run in RUNS:
    q = pd.read_csv(HERE + "quotes_" + run + "_count_c8c9.csv")
    # an empty action (held, no decision) is read back as a missing value;
    # fillna("") turns it into empty text
    q["action"] = q["action"].fillna("")
    # each line works on whole columns at once: one value per row
    widened = (q["ask"] - q["bid"]) - (q["ask_before"] - q["bid_before"])
    mid_now = (q["ask"] + q["bid"]) / 2
    mid_before = (q["ask_before"] + q["bid_before"]) / 2
    moved = (mid_now - mid_before).abs()       # .abs(): up or down, without the sign
    q["blew_up"] = widened > moved             # a column of True/False
    quotes[run] = q


def flagged(q, jump, ratio):
    """The rows where all three conditions hold (& means "and", row by row)."""
    rule = (q["vol_jump"] > jump) & (q["width_ratio"] > ratio) & q["blew_up"]
    return q[rule]                             # q[...] keeps the rows where rule is True


pd.set_option("display.width", 250)            # print wide tables on one line
print("snapshots flagged per run / of which at a decision (exit or entry), with 'widened more than moved'")
names = []
for run in RUNS:
    names.append("%-11s" % run)                # each name padded to 11 characters
print("limits          " + "   ".join(names))  # joined with 3 spaces between them
for jump in (0.02, 0.03, 0.05):
    for ratio in (2, 3, 5):
        parts = []
        for run in RUNS:
            f = flagged(quotes[run], jump, ratio)
            # both legs can be flagged at one snapshot: drop_duplicates keeps
            # one row per snapshot, so each snapshot is counted once
            snapshots = f.drop_duplicates(["time", "kind"])
            decisions = snapshots[snapshots["action"] != ""]
            parts.append("%3d / %3d  " % (len(snapshots), len(decisions)))
        print("%2.0f pts, %dx      %s" % (100 * jump, ratio, "  ".join(parts)))

print("\nevery quote flagged with 3 pts, 3x + widened more than moved:")
rows = []
for run in RUNS:
    # .copy(): a table of its own, so adding the column "run" does not touch quotes[run]
    f = flagged(quotes[run], 0.03, 3).copy()
    f["run"] = run
    rows.append(f)
table = pd.concat(rows)                        # glue the four tables below each other
vol_before = (100 * table["iv_before"]).round(1).astype(str)    # numbers -> text
vol_now = (100 * table["iv"]).round(1).astype(str)
table["vol"] = vol_before + " -> " + vol_now
table["ratio"] = table["width_ratio"].round(1)
table = table.sort_values(["time", "run"])     # by time, then by run
print(table[["run", "time", "kind", "leg", "root", "expiration", "strike", "bid_before", "ask_before",
             "bid", "ask", "vol", "ratio", "action"]].to_string(index=False))
