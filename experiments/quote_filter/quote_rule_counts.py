# For choosing the two limits of the broken-quote rule (README, step 2): how often
# would each pair of limits fire in the four "count" runs, and does it catch the
# known broken quotes? Uses only the quote measurements, no P&L. Read-only.
# (Known error, fixed in quote_rule_counts_2.py: an empty action is read back as
# a missing value, which this script counts as a decision, so its "at a
# decision" numbers are too high.)
import pandas as pd                 # pandas works with tables

HERE = "C:/Dokumente/Python/Masterarbeit/experiments/quote_filter/"
RUNS = ["base_mid", "base_cross", "p15_mid", "p15_cross"]
VOL_JUMPS = [0.03, 0.05, 0.07, 0.10]       # 3, 5, 7, 10 vol points
WIDTH_RATIOS = [2, 3, 5, 10]

# the known broken quotes in these runs (review_log C14): time, strike, expiry
KNOWN = [("2020-04-03 10:00:00", 1990.0, "2020-06-19"),
         ("2012-06-14 15:30:00", 1050.0, "2012-07-21")]

quotes = {}
for run in RUNS:
    quotes[run] = pd.read_csv(HERE + "quotes_" + run + "_count_c8c9.csv")

print("rows per run (one per leg and snapshot):")
for run in RUNS:
    q = quotes[run]
    # (q["kind"] == "held") is a column of True/False; .sum() counts the Trues;
    # .isna() is True where a value is missing (no earlier quote)
    print("  %-11s %7d  held %7d  entry %5d  no earlier quote %d" % (
        run, len(q), (q["kind"] == "held").sum(), (q["kind"] == "entry").sum(), q["vol_jump"].isna().sum()))

# how big the two numbers usually are (all four runs together; pd.concat glues
# the four tables below each other)
all_tables = []
for run in RUNS:
    all_tables.append(quotes[run])
everything = pd.concat(all_tables)
# .quantile(0.99): the value 99% of the rows are below (missing values are skipped)
print("\nvol jump (vol points): median %.2f, 99th pct %.2f, 99.9th %.2f" % (
    100 * everything["vol_jump"].median(), 100 * everything["vol_jump"].quantile(0.99),
    100 * everything["vol_jump"].quantile(0.999)))
print("width ratio: median %.2f, 99th pct %.2f, 99.9th %.2f" % (
    everything["width_ratio"].median(), everything["width_ratio"].quantile(0.99),
    everything["width_ratio"].quantile(0.999)))

# the two numbers of the known cases
print("\nthe known broken quotes:")
for run in RUNS:
    q = quotes[run]
    for when, strike, expiry in KNOWN:
        # the rows of this option at this time (& means "and", row by row)
        hit = q[(q["time"] == when) & (q["strike"] == strike) & (q["expiration"] == expiry)]
        for _, row in hit.iterrows():          # iterrows: one row at a time
            print("  %-11s %s %s %.0f: vol %.1f%% -> %.1f%% (jump %.1f), width %.2f -> %.2f (ratio %.1f), action '%s'" % (
                run, when, row["root"], strike, 100 * row["iv_before"], 100 * row["iv"], 100 * row["vol_jump"],
                row["ask_before"] - row["bid_before"], row["ask"] - row["bid"], row["width_ratio"], row["action"]))

# every pair of limits: how many snapshots it would flag (a snapshot counts once
# even if both legs are flagged), how many of them at a decision, known cases caught
print("\nlimits (vol jump, width ratio): snapshots flagged per run, of which at a decision (exit or entry), known caught")
for jump in VOL_JUMPS:
    for ratio in WIDTH_RATIOS:
        parts = []
        caught = 0
        for run in RUNS:
            q = quotes[run]
            flagged = q[(q["vol_jump"] > jump) & (q["width_ratio"] > ratio)]
            snapshots = flagged.drop_duplicates(["time", "kind"])          # one per snapshot
            at_decision = snapshots[snapshots["action"] != ""]
            parts.append("%4d/%3d" % (len(snapshots), len(at_decision)))
            for when, strike, expiry in KNOWN:
                is_known = (flagged["time"] == when) & (flagged["strike"] == strike) & (flagged["expiration"] == expiry)
                if is_known.any():             # .any(): True if at least one row is True
                    caught = caught + 1
        print("  %4.0f pts, %3dx:  %s   known caught %d of 3" % (100 * jump, ratio, "  ".join(parts), caught))
print("(columns: " + ", ".join(RUNS) + "; 'known' = the 1990 put in base mid and base cross, the 1050 put in p15 cross)")
