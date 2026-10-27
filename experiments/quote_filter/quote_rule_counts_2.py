# Second look at the limits (README, step 2), still without any P&L.
# The first look (quote_rule_counts.py) showed that "vol jump + much wider"
# also fires on real fast markets (March 2020 after the trading halts,
# 2024-08-05 open), where bid AND ask moved the same way. A broken quote looks
# different: it is wider on BOTH sides of the previous quote, the bid at or
# below the previous bid and the ask at or above the previous ask
# ("brackets" the previous quote). This adds that third condition.
# Also fixes the first script's count "at a decision": an empty action is read
# back from the CSV as a missing value (nan), which it had counted as a decision.
import pandas as pd                 # pandas works with tables

HERE = "C:/Dokumente/Python/Masterarbeit/experiments/quote_filter/"
RUNS = ["base_mid", "base_cross", "p15_mid", "p15_cross"]

quotes = {}
for run in RUNS:
    q = pd.read_csv(HERE + "quotes_" + run + "_count_c8c9.csv")
    q["action"] = q["action"].fillna("")       # empty action = held, no decision
    # True where the new quote brackets the previous one (& means "and", row by row)
    q["brackets"] = (q["bid"] <= q["bid_before"]) & (q["ask"] >= q["ask_before"])
    quotes[run] = q


def flagged_rows(q, jump, ratio, need_brackets):
    """The rows the rule would flag with these limits (and brackets, if asked)."""
    rule = (q["vol_jump"] > jump) & (q["width_ratio"] > ratio)    # a column of True/False
    if need_brackets:
        rule = rule & q["brackets"]
    return q[rule]                             # q[...] keeps the rows where rule is True


pd.set_option("display.width", 250)            # print wide tables on one line
print("snapshots flagged per run / of which at a decision (exit or entry)")
names = []
for run in RUNS:
    names.append("%-11s" % run)                # each name padded to 11 characters
print("limits                   " + "   ".join(names))
for need_brackets in (False, True):
    for jump in (0.02, 0.03, 0.05, 0.07):
        for ratio in (2, 3, 5):
            parts = []
            for run in RUNS:
                f = flagged_rows(quotes[run], jump, ratio, need_brackets)
                # both legs can be flagged at one snapshot: count each snapshot once
                snapshots = f.drop_duplicates(["time", "kind"])
                decisions = snapshots[snapshots["action"] != ""]
                parts.append("%3d / %3d  " % (len(snapshots), len(decisions)))
            label = "%2.0f pts, %dx" % (100 * jump, ratio)
            if need_brackets:
                label = label + " + brackets"
            print("%-24s %s" % (label, "  ".join(parts)))
    print()

print("every quote flagged with 2 pts, 2x + brackets (the loosest bracket rule):")
rows = []
for run in RUNS:
    # .copy(): a table of its own, so adding the column "run" does not touch quotes[run]
    f = flagged_rows(quotes[run], 0.02, 2, True).copy()
    f["run"] = run
    rows.append(f)
table = pd.concat(rows)                        # glue the four tables below each other
vol_before = (100 * table["iv_before"]).round(1).astype(str)    # numbers -> text
vol_now = (100 * table["iv"]).round(1).astype(str)
table["vol"] = vol_before + " -> " + vol_now
table["jump"] = (100 * table["vol_jump"]).round(1)
table["ratio"] = table["width_ratio"].round(1)
table = table.sort_values(["time", "run"])     # by time, then by run
print(table[["run", "time", "kind", "leg", "root", "expiration", "strike", "bid_before", "ask_before",
             "bid", "ask", "vol", "jump", "ratio", "action"]].to_string(index=False))
