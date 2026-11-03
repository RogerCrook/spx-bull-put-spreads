"""
The backtest numbers outside the chapter-4 tables, computed from the trade logs
(reproduction inventory, rows 24, 26, 27, 28, 31 to 34)

What this file is for:
    The backtest (Code/s11_backtest.py, run by Code/s12_run_variants.py) writes
    two files per run into results/:
      trades_<run>.csv   one row per finished cycle (entry, exit, P&L, ...)
      equity_<run>.csv   one row per trading day (P&L so far, margin, interest)
    This file reads them and computes the backtest numbers the thesis gives
    outside the tables of checks/quarters_vs_index.py:
      tab:costs                  the cost of crossing the spread (base case)
      sec:backtest-design        the snapshots with a leg missing (base case at mid)
      sec:monitoring,            the return per year of the base case with and
      sec:broken-quotes          without the two rules for bad data
      tab:p15-test               the test of p15 against the base case, both
                                 crossing the spread (commented out in the thesis
                                 since T68, 2026-10-29, until Arian has reread it)
    Each number is printed the way the .tex writes it, e.g. 15600 as
    "$15{,}600$", next to "yes" if that exact text is in the .tex (commented
    lines included, so the test shows "yes" too).

    Until 2026-11-03 (review_log T112) this file also computed the tables set
    aside in Masterarbeit_Tex_file/set_aside_ch4.tex (tab:results-base,
    tab:losses-months, tab:losses-rules, tab:p15, the old tab:results-years and
    their text). That code is in commit cf6519a (tag thesis-2026-11-03-unused-code-removed).

    Three sets of runs are read (all in results/, made 2026-10-28):
      thesis                           the four runs the thesis reports
      without the broken-quote rule    the same four with QUOTE_RULE off
      without the stock-close rule     the base case with both data rules off

    The formulas (CLAUDE.md section 6):
      return per year    = P&L of the whole sample / average margin / (trading days / 252)
      cost share         = average over cycles of spread cost / credit at mid
      test               = monthly return of p15 minus base case, both crossing the
                           spread; t-statistic and a moving-block bootstrap
                           (blocks of 12 months, 10,000 resamples, seed 1)

Data: results/trades_*.csv and results/equity_*.csv of the 10 runs named below.
Read-only: writes nothing. Takes about a minute (the bootstrap).
Run it from the main folder:   python checks/chapter4_numbers.py
"""

import os                                    # os.path.exists tells whether a file is there
import numpy as np                           # numpy does maths on lists of numbers
import pandas as pd                          # pandas works with tables


RESULTS = "results/"
TEX_FILE = "Masterarbeit_Tex_file/Masterarbeit_Tex_file.tex"   # folder and file renamed 2026-10-29

# the runs with the test: set name -> {run: file name part}
RUN_SETS = {
    "thesis": {
        "base_mid": "base_mid", "base_cross": "base_cross",
        "p15_cross": "p15_cross"},
    "without the broken-quote rule": {
        "base_mid": "base_mid_without_quote_rule", "base_cross": "base_cross_without_quote_rule",
        "p15_cross": "p15_cross_without_quote_rule"},
}

# the base case without the stock-close rule (only the base case was run): run -> file name part
NO_CLOSE_RUNS = {"base_mid": "base_mid_without_close_rule", "base_cross": "base_cross_without_close_rule"}


# ---- the thesis text, to look the numbers up in -----------------------------

# The .tex is not in the code repository. Without it every number is still
# computed and printed, but the first column shows "?" instead of "yes" or "-".
if os.path.exists(TEX_FILE):
    tex = open(TEX_FILE, encoding="utf-8").read()
else:
    tex = None                               # None = no thesis text to look in
    print("Thesis .tex not found (" + TEX_FILE + "):")
    print("the numbers are computed but not looked up in the thesis.")
    print()

# the .tex breaks sentences over several lines, so a phrase can be split by a
# line break. .split() cuts the text at every space and line break, and
# " ".join glues the pieces back together with single spaces.
if tex is not None:
    tex_one_line = " ".join(tex.split())


def in_thesis(text):
    """True if this exact text occurs in the thesis, None if there is no thesis text."""
    if tex is None:
        return None
    return (text in tex) or (text in tex_one_line)


def show(passage, what, text):
    """Print one number: "yes" / "-" / "?", where it belongs, what it is, the text."""
    result = in_thesis(text)
    if result is None:
        mark = "?"                           # no .tex to look in
    elif result:
        mark = "yes"
    else:
        mark = "-"
    print("%-3s  %-27s %-42s %s" % (mark, passage, what, text))


# ---- small helpers -------------------------------------------------------------

def big(x):
    """A whole number with LaTeX thousands separators: 15600 -> "15{,}600"."""
    text = "{:,}".format(int(round(x)))      # Python writes "15,600"
    return text.replace(",", "{,}")          # LaTeX wants "15{,}600"


def load(name):
    """Read the trades and the daily equity of one run, e.g. load("base_mid")."""

    trades = pd.read_csv(RESULTS + "trades_" + name + ".csv")
    equity = pd.read_csv(RESULTS + "equity_" + name + ".csv")

    equity["month"] = equity["date"].str[:7]          # "2012-01-03" -> "2012-01"

    # the length of each cycle in days: exit time minus entry time is a time
    # difference; .dt.total_seconds() turns it into seconds, / 86400 into days
    length = pd.to_datetime(trades["exit_time"]) - pd.to_datetime(trades["entry_time"])
    trades["days"] = length.dt.total_seconds() / 86400

    return trades, equity


def monthly_returns(equity):
    """
    The return of each month: the P&L of the month divided by the average
    margin held in it.
    """
    # groupby puts the days of each month together, so that .sum() and .mean()
    # are taken month by month
    groups = equity.groupby("month")
    return groups["pnl_day"].sum() / groups["margin"].mean()


def per_year(equity):
    """Return on margin per year, in per cent: total P&L / average margin / (days / 252)."""
    years = len(equity) / 252.0
    return 100 * equity["pnl_day"].sum() / equity["margin"].mean() / years


# ---- tab:costs and sec:backtest-design (the runs the thesis reports) --------------

print("=" * 100)
print("tab:costs and sec:backtest-design   (files: base_cross, base_mid)")
print("=" * 100)

trades_mid, equity_mid = load("base_mid")
trades_cross, equity_cross = load("base_cross")

p = "tab:costs"
share = trades_cross["spread_cost"] / trades_cross["credit_mid"]     # one share per cycle
# the average share per entry year: "2012-03-05 10:00:00" -> "2012";
# groupby puts the cycles of each year together, .mean() averages them
share_by_year = share.groupby(trades_cross["entry_time"].str[:4]).mean() * 100
early = share_by_year[["2012", "2013", "2014", "2015"]]               # these four years
late_years = []
for year in range(2019, 2027):                                        # 2019 to 2026
    late_years.append(str(year))
late = share_by_year[late_years]
show(p, "trades", "Trades & $%d$" % len(trades_cross))
show(p, "cost mean / median", "$%.2f$ / $%.2f$" % (
    trades_cross["spread_cost"].mean(), trades_cross["spread_cost"].median()))
show(p, "cost share", "$%.1f\\%%$" % (100 * share.mean()))
show(p, "cost share 2012-15", "$%d$--$%d\\%%$" % (round(early.min()), round(early.max())))
show(p, "cost share 2019-26", "$%d$--$%d\\%%$" % (round(late.min()), round(late.max())))
show(p, "total spread cost", "$%s$" % big(trades_cross["spread_cost"].sum()))
for reason in ("profit", "loss"):
    # the spread cost of the cycles that ended at this exit
    cost = trades_cross.loc[trades_cross["reason"] == reason, "spread_cost"]
    show(p, "cost " + reason + " exits", "$%s$, $%.2f$" % (big(cost.sum()), cost.mean()))
show(p, "median length of a cycle", "$%d$ days" % round(trades_cross["days"].median()))
cycles_a_year = len(trades_cross) / (len(equity_cross) / 252.0)
show(p, "cycles a year", "$\\approx %d$ cycles a year" % round(cycles_a_year))

show("sec:backtest-design", "snapshots with a leg missing",
     "at $%d$ snapshots in the base-case" % trades_mid["skipped"].sum())
print()


# ---- the return per year and the test, with and without the broken-quote rule -----

for set_name in RUN_SETS:

    files = RUN_SETS[set_name]
    print("=" * 100)
    print("RUNS:", set_name, "  (files:", ", ".join(files.values()), ")")
    print("=" * 100)

    _, equity_mid = load(files["base_mid"])      # "_": the trades are not needed here
    _, equity_cross = load(files["base_cross"])
    _, equity_p15c = load(files["p15_cross"])

    # sec:monitoring and sec:broken-quotes quote these
    show("sec:monitoring / broken", "base_mid return per year", "$%.1f\\%%$" % per_year(equity_mid))
    show("sec:monitoring / broken", "base_cross return per year", "$%.1f\\%%$" % per_year(equity_cross))

    # ---- tab:p15-test: monthly return, p15 crossing minus base crossing ----
    p = "tab:p15-test"
    # the difference month by month, in percentage points; .values: plain numbers
    difference = (100 * (monthly_returns(equity_p15c) - monthly_returns(equity_cross))).values
    n = len(difference)
    mean = difference.mean()
    sd = difference.std(ddof=1)              # ddof=1: the sample standard deviation (divides by n - 1)
    t_stat = mean / (sd / np.sqrt(n))

    # moving-block bootstrap: glue together 15 blocks of 12 consecutive months,
    # each starting at a random month where a whole block fits, cut to n months,
    # and take the mean; repeat 10,000 times
    generator = np.random.default_rng(1)                 # random numbers with seed 1, as reported
    blocks_needed = int(np.ceil(n / 12))                 # np.ceil rounds up: 176 / 12 -> 15
    means = np.empty(10000)                              # room for 10,000 numbers
    for b in range(10000):
        starts = generator.integers(0, n - 12 + 1, size=blocks_needed)   # 15 random start months
        pieces = []
        for start in starts:
            pieces.append(difference[start:start + 12])  # the 12 months from that start
        resample = np.concatenate(pieces)[:n]            # glue them together, keep the first n
        means[b] = resample.mean()

    show(p, "months", "Months & $%d$" % n)
    show(p, "mean difference", "$%+.2f$ percentage points" % mean)
    show(p, "standard deviation", "$%.2f$ percentage points" % sd)
    show(p, "t-statistic (table)", "$t$-statistic & $%.2f$" % t_stat)
    show(p, "t-statistic (text)", "$t$-statistic is $%.2f$" % t_stat)
    show(p, "months the variant is ahead", "variant is ahead & $%d$" % (difference > 0).sum())
    # (means < 0).mean(): the share of the 10,000 means below zero
    show(p, "bootstrap: share behind", "variant behind & $%.1f\\%%$" % (100 * (means < 0).mean()))
    # np.percentile(means, 2.5): the value 2.5% of the 10,000 means lie below
    show(p, "bootstrap: 95% interval", "$%+.2f$ to $%+.2f$ percentage points" % (
        np.percentile(means, 2.5), np.percentile(means, 97.5)))
    print()


# ---- the base case without the stock-close rule (sec:monitoring) ----------------------

print("=" * 100)
print("RUNS: without the stock-close rule, base case only   (files:", ", ".join(NO_CLOSE_RUNS.values()), ")")
print("=" * 100)

for run in NO_CLOSE_RUNS:
    _, equity = load(NO_CLOSE_RUNS[run])     # "_": the trades are not needed here
    show("sec:monitoring", run + " return per year", "$%.1f\\%%$" % per_year(equity))
print()
