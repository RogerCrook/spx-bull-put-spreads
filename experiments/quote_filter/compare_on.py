# Step 3 of the README: old (the thesis runs, results/*_c8c9.csv) against new
# (the "on" runs, broken quotes skipped). Read-only: writes nothing.
# Part 1: which trades changed. Part 2: every backtest number of chapter 4, with
# the same formulas as checks/thesis_numbers.py (copied here, since that script
# runs on import).
import numpy as np                  # numpy does maths on lists of numbers
import pandas as pd                 # pandas works with tables

HERE = "C:/Dokumente/Python/Masterarbeit/experiments/quote_filter/"
RESULTS = "C:/Dokumente/Python/Masterarbeit/results/"
RUNS = ["base_mid", "base_cross", "p15_mid", "p15_cross"]
LABELS = {"base_mid": "mid", "base_cross": "cross", "p15_mid": "p15m", "p15_cross": "p15c"}


def load(which, run):
    """The trades and the daily equity of one run; which = "old" (thesis run) or "new" ("on" run)."""
    if which == "old":
        t = pd.read_csv(RESULTS + "trades_" + run + "_c8c9.csv")
        q = pd.read_csv(RESULTS + "equity_" + run + "_c8c9.csv")
    else:
        t = pd.read_csv(HERE + "trades_" + run + "_on_c8c9.csv")
        q = pd.read_csv(HERE + "equity_" + run + "_on_c8c9.csv")
    # .str[:4] takes the first 4 characters of every date: "2012-01-03" -> "2012"
    q["year"] = q["date"].str[:4]
    q["month"] = q["date"].str[:7]            # "2012-01-03" -> "2012-01"
    # the quarter of each day, e.g. "2012-Q1"; .dt.quarter gives 1 to 4
    q["quarter"] = q["year"] + "-Q" + pd.to_datetime(q["date"]).dt.quarter.astype(str)
    t["entry_year"] = t["entry_time"].str[:4]
    # the length of each trade in days (.dt.total_seconds: the time difference in seconds)
    length = pd.to_datetime(t["exit_time"]) - pd.to_datetime(t["entry_time"])
    t["days"] = length.dt.total_seconds() / 86400
    return t, q


# ---------------- Part 1: the trades that changed ----------------
# A trade is "the same" when entry time, exit time, strikes and expiry are equal.
# merge(..., how="outer", indicator=True) puts both tables side by side, matched
# on KEY, keeps the trades of both, and adds a column "_merge": "both",
# "left_only" (only old) or "right_only" (only new).
KEY = ["entry_time", "exit_time", "expiration", "strike_short", "strike_long"]
SHOW = KEY + ["reason", "pnl", "maturity_rule"]

for run in RUNS:
    old_t, old_q = load("old", run)
    new_t, new_q = load("new", run)
    # suffixes: the columns both tables have but that are not in KEY get
    # "_old" and "_new" added to their names (reason_old, reason_new, ...)
    both = old_t[SHOW].merge(new_t[SHOW], on=KEY, how="outer", indicator=True,
                             suffixes=("_old", "_new"))
    only_old = both[both["_merge"] == "left_only"]
    only_new = both[both["_merge"] == "right_only"]
    print("=" * 100)
    print("%s: trades old %d, new %d, only in old %d, only in new %d, skipped (broken) snapshots %d" % (
        run, len(old_t), len(new_t), len(only_old), len(only_new), int(new_t["skipped_broken"].sum())))
    print("  P&L of the changed trades (points): old %+.2f, new %+.2f" % (
        only_old["pnl_old"].sum(), only_new["pnl_new"].sum()))
    print("  only in old:")
    for _, r in only_old.iterrows():           # iterrows: one row at a time
        print("    %s -> %s  %s/%s  %s  %+8.2f" % (r["entry_time"], r["exit_time"], r["strike_short"],
                                                  r["strike_long"], r["reason_old"], r["pnl_old"]))
    print("  only in new:")
    for _, r in only_new.iterrows():
        print("    %s -> %s  %s/%s  %s  %+8.2f" % (r["entry_time"], r["exit_time"], r["strike_short"],
                                                  r["strike_long"], r["reason_new"], r["pnl_new"]))
    # the trades where the rule skipped a snapshot, with how many
    hit = new_t[new_t["skipped_broken"] > 0]
    for _, r in hit.iterrows():
        print("  skipped %d snapshot(s) in the trade opened %s (exit %s, %s)" % (
            r["skipped_broken"], r["entry_time"], r["exit_time"], r["reason"]))
    # .iloc[-1]: the last row, i.e. the last day
    print("  final total P&L $: old %.0f, new %.0f" % (old_q["total_pnl"].iloc[-1], new_q["total_pnl"].iloc[-1]))


# ---------------- Part 2: the chapter-4 numbers, old and new ----------------
def period_table(q, column):
    """
    One row per period (month, quarter or year, named by `column`): its P&L,
    its average margin, and its return = P&L / average margin.
    """
    # groupby puts the days of each period together, so that .sum() and
    # .mean() are taken per period
    groups = q.groupby(column)
    table = pd.DataFrame({"pnl": groups["pnl_day"].sum(), "margin": groups["margin"].mean()})
    table["ret"] = table["pnl"] / table["margin"]
    return table


def annual(q):
    """Return on margin per year in per cent: total P&L / average margin, per 252 days."""
    return 100 * q["pnl_day"].sum() / q["margin"].mean() / (len(q) / 252.0)


def block_bootstrap(x, block=12, n_boot=10000, seed=1):
    """
    Moving-block bootstrap of the mean: draw blocks of 12 consecutive months at
    random start positions, glue them together, cut to the original length,
    take the mean; n_boot times. Returns the share of means below 0 (per cent)
    and the 2.5% and 97.5% points of the means.
    """
    rng = np.random.default_rng(seed)          # random numbers with a fixed seed
    n = len(x)
    n_blocks = int(np.ceil(n / block))         # np.ceil rounds up: 176/12 -> 15
    means = np.empty(n_boot)                   # room for n_boot numbers
    for b in range(n_boot):
        starts = rng.integers(0, n - block + 1, size=n_blocks)
        pieces = []
        for s in starts:
            pieces.append(x[s:s + block])      # the 12 months from position s
        sample = np.concatenate(pieces)[:n]    # glue them, keep the first n
        means[b] = sample.mean()
    # (means < 0).mean(): the share of means below 0;
    # np.percentile(means, 2.5): the value 2.5% of the means are below
    return 100 * (means < 0).mean(), np.percentile(means, 2.5), np.percentile(means, 97.5)


def count_text(t, column, values):
    """How many trades have each of `values` in `column`, as "415/275/9"."""
    parts = []
    for value in values:
        parts.append(str((t[column] == value).sum()))
    return "/".join(parts)


def numbers(which):
    """Every chapter-4 number for the old or the new runs, as {name: value}."""
    out = {}
    d = {}
    for run in RUNS:
        d[LABELS[run]] = load(which, run)

    # tab:results-base and tab:p15
    for k in d:
        t, q = d[k]
        win = t["pnl"] > 0                     # True for every winning trade
        last = q.iloc[-1]                      # the last day
        qr = period_table(q, "quarter")["ret"]
        out[k + " cycles"] = len(t)
        out[k + " profit/loss/gamma"] = count_text(t, "reason", ["profit", "loss", "gamma"])
        out[k + " target/recovery/cap"] = count_text(t, "maturity_rule", ["target", "recovery", "cap"])
        out[k + " median length"] = round(t["days"].median(), 1)
        out[k + " mean P&L/cycle"] = round(t["pnl"].mean(), 2)
        # the mean of True/False is the share of Trues; .loc[win, "pnl"]: winners' pnl
        out[k + " win share, mean"] = "%.0f%%, %+.2f" % (100 * win.mean(), t.loc[win, "pnl"].mean())
        out[k + " losing mean"] = round(t.loc[~win, "pnl"].mean(), 2)    # ~win: "not win"
        if k in ("cross", "p15c"):
            out[k + " spread cost"] = round(t["spread_cost"].sum())
        out[k + " total $"] = round(last["total_pnl"])
        out[k + " closed / open / interest $"] = "%.0f / %.0f / %.0f" % (last["realised"], last["unrealised"], last["interest_total"])
        out[k + " avg margin $"] = round(q["margin"].mean())
        out[k + " ret/yr all"] = round(annual(q), 1)
        out[k + " ret/yr 2012-18"] = round(annual(q[q["year"] <= "2018"]), 1)
        out[k + " ret/yr 2019-26"] = round(annual(q[q["year"] >= "2019"]), 1)
        out[k + " neg quarters"] = "%d of %d" % ((qr < 0).sum(), len(qr))
        out[k + " median quarter"] = round(100 * qr.median(), 1)
        # .idxmin(): the label (the quarter) of the smallest value
        out[k + " worst quarter"] = "%.1f (%s)" % (100 * qr.min(), qr.idxmin())

    # tab:results-years
    for k in ("mid", "cross"):
        yr = period_table(d[k][1], "year")["ret"]
        parts = []
        for year, value in yr.items():         # .items(): (label, value) pairs
            parts.append("%s:%d" % (year[2:], round(100 * value)))     # "2012" -> "12"
        out[k + " years"] = " ".join(parts)
        out[k + " years positive"] = "%d of %d" % ((yr > 0).sum(), len(yr))
    for k in ("p15m", "p15c"):
        yr = period_table(d[k][1], "year")["ret"]
        out[k + " years positive"] = "%d of %d" % ((yr > 0).sum(), len(yr))

    tm, qm = d["mid"]
    tc, qc = d["cross"]
    tpc, qpc = d["p15c"]

    gap = tm["pnl"].sum() - tc["pnl"].sum()
    out["gap mid-cross closed (pts)"] = round(gap)
    out["path effect = gap - spread cost"] = round(gap - tc["spread_cost"].sum())

    # tab:costs
    out["costs: mean / median per trade"] = "%.2f / %.2f" % (tc["spread_cost"].mean(), tc["spread_cost"].median())
    out["costs: share of mid credit (mean ratio)"] = round(100 * (tc["spread_cost"] / tc["credit_mid"]).mean(), 1)
    for r in ("profit", "loss", "gamma"):
        s = tc.loc[tc["reason"] == r, "spread_cost"]      # the cost of these trades only
        out["costs: %s exits total, per trade" % r] = "%.0f, %.2f" % (s.sum(), s.mean())
    out["skipped snapshots mid / cross"] = "%d / %d" % (tm["skipped"].sum(), tc["skipped"].sum())
    dl = tm["delta0"]
    # .quantile(0.05): the value 5% of the entries are below
    out["mid delta0 median, 5%-95%, min, max"] = "%.3f, %.3f-%.3f, %.3f, %.3f" % (
        dl.median(), dl.quantile(0.05), dl.quantile(0.95), dl.min(), dl.max())

    # tab:losses-months
    mo = period_table(qc, "month")
    w = mo[mo["pnl"] > 0]                      # winning months
    l = mo[mo["pnl"] <= 0]                     # losing months
    out["months profitable"] = "%d of %d" % (len(w), len(mo))
    out["mean winning month $, % (mean ret)"] = "%.0f, %.1f" % (w["pnl"].mean(), 100 * w["ret"].mean())
    out["mean losing month $, % (mean ret)"] = "%.0f, %.1f" % (l["pnl"].mean(), 100 * l["ret"].mean())
    worst = l["pnl"].sort_values()             # the worst month first
    # .iloc[:10]: the first 10, i.e. the 10 worst months
    out["share of losses in 10 / 20 worst"] = "%.0f / %.0f" % (100 * worst.iloc[:10].sum() / worst.sum(), 100 * worst.iloc[:20].sum() / worst.sum())
    parts = []
    for month, value in worst.iloc[:6].items():
        parts.append("%s:%.0f" % (month, value))
    out["worst 6 months"] = "  ".join(parts)

    # tab:losses-rules
    for r in ("target", "recovery", "cap"):
        s = tc[tc["maturity_rule"] == r]
        out["rules cross %s: n, P&L pts, cost/cycle" % r] = "%d, %+.0f, %.2f" % (len(s), s["pnl"].sum(), s["spread_cost"].mean())
    for r in ("profit", "loss"):
        s = tc[tc["reason"] == r]
        out["rules cross %s exit: n, P&L pts" % r] = "%d, %+.0f" % (len(s), s["pnl"].sum())

    # sec:robustness and tab:p15-test
    out["p15 vs base: fewer cycles mid / cross (%)"] = "%.0f / %.0f" % (
        100 * (1 - len(d["p15m"][0]) / len(tm)), 100 * (1 - len(tpc) / len(tc)))
    out["spread cost saved (pts)"] = round(tc["spread_cost"].sum() - tpc["spread_cost"].sum())
    diff = 100 * (period_table(qpc, "month")["ret"] - mo["ret"])
    x = diff.values                            # a plain numpy array of the 176 differences
    out["test: months"] = len(x)
    # x.std(ddof=1): the standard deviation of a sample (divides by n - 1)
    out["test: mean, sd (pp)"] = "%+.2f, %.2f" % (x.mean(), x.std(ddof=1))
    out["test: t"] = round(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))), 2)
    out["test: months variant ahead"] = int((x > 0).sum())
    share, lo, hi = block_bootstrap(x, seed=1)
    out["test: bootstrap seed 1: share behind, 95% interval"] = "%.1f%%, %+.2f to %+.2f" % (share, lo, hi)
    return out


old = numbers("old")
new = numbers("new")
# a table with one row per number: old, new, and a * where they differ.
# dtype=object lets a column hold numbers and text together
table = pd.DataFrame({"old": pd.Series(old, dtype=object), "new": pd.Series(new, dtype=object)})
table["changed"] = ""
for name in table.index:                       # .index: the row labels (the names)
    if str(table.loc[name, "old"]) != str(table.loc[name, "new"]):
        table.loc[name, "changed"] = "*"
pd.set_option("display.width", 250)            # print wide tables on one line
pd.set_option("display.max_colwidth", 120)
print("\n" + table.to_string())
