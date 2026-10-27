"""
CHAPTER 4: every number of the backtest results, computed from the trade logs
(reproduction inventory, rows 24, 26, 27, 28, 31 to 34)

What this file is for:
    The backtest (Code/s11_backtest.py, run by Code/s12_run_variants.py) writes
    two files per run into results/:
      trades_<run>.csv   one row per finished cycle (entry, exit, P&L, ...)
      equity_<run>.csv   one row per trading day (P&L so far, margin, interest)
    This file reads them and computes every number chapter 4 of the thesis
    reports (and tab:costs in chapter 3): the results tables, the yearly and
    monthly returns, the costs, the losses by rule, and the test of the
    variant. Each number is printed the way the .tex writes it, e.g. 15600 as
    "$15{,}600$", next to "yes" if that exact text is in the thesis.

    Three sets of runs are read, each with the base case and the variant with
    the profit exit at Delta_0 - 0.15 ("p15"), at mid and crossing the spread:
      thesis                          the runs the thesis reports (all three data fixes)
      without the broken-quote rule   sec:broken-quotes quotes their returns and test
      without the stock-close rule    sec:monitoring quotes their returns
    For the two older sets most numbers are of course not in the thesis; only
    the few it quotes should say "yes".

    The formulas (CLAUDE.md section 6):
      return of a period = P&L of the period / average margin held in it
      return per year    = that, for the whole sample, divided by (trading days / 252)
      winning cycle      = P&L > 0
      cost share         = average over cycles of spread cost / credit at mid
      test               = monthly return of p15 minus base case, both crossing the
                           spread; t-statistic and a moving-block bootstrap
                           (blocks of 12 months, 10,000 resamples, seed 1)

    This replaces checks/verify_tex_c14.py and checks/thesis_numbers.py (kept in
    old_versions/checks_before_style_2026-10-27/), with the same formulas.

Data: results/trades_*.csv and results/equity_*.csv of the 12 runs.
Read-only: writes nothing. Takes about a minute (the bootstrap).
Run it from the main folder:   python checks/chapter4_numbers.py
"""

import os                                    # os.path.exists tells whether a file is there
import numpy as np                           # numpy does maths on lists of numbers
import pandas as pd                          # pandas works with tables


RESULTS = "results/"
TEX_FILE = "Masterarbeit Tex File from claude/Masterarbeit von Claude.tex"

# the three sets of runs: set name -> {run: file name part}
RUN_SETS = {
    "thesis": {
        "base_mid": "base_mid_c8c9q", "base_cross": "base_cross_c8c9q",
        "p15_mid": "p15_mid_c8c9q", "p15_cross": "p15_cross_c8c9q"},
    "without the broken-quote rule": {
        "base_mid": "base_mid_c8c9", "base_cross": "base_cross_c8c9",
        "p15_mid": "p15_mid_c8c9", "p15_cross": "p15_cross_c8c9"},
    "without the stock-close rule": {
        "base_mid": "mid_latest", "base_cross": "base_cross",
        "p15_mid": "p15_mid", "p15_cross": "p15_cross"},
}

MONTH_NAMES = {"01": "January", "02": "February", "03": "March", "04": "April",
               "05": "May", "06": "June", "07": "July", "08": "August",
               "09": "September", "10": "October", "11": "November", "12": "December"}


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


# ---- small helpers -------------------------------------------------------------

def big(x):
    """A whole number with LaTeX thousands separators: 15600 -> "15{,}600"."""
    text = "{:,}".format(int(round(x)))      # Python writes "15,600"
    return text.replace(",", "{,}")          # LaTeX wants "15{,}600"


def load(name):
    """Read the trades and the daily equity of one run, e.g. load("base_mid_c8c9q")."""

    trades = pd.read_csv(RESULTS + "trades_" + name + ".csv")
    equity = pd.read_csv(RESULTS + "equity_" + name + ".csv")

    # The first base-case run (mid_latest) was written before the equity file
    # had the columns pnl_day, year and quarter, so they are made here when missing.
    if "pnl_day" not in equity:
        # the P&L of each day = today's total minus yesterday's total;
        # .diff() does exactly that, and gives nothing (NaN) on the first day,
        # where the day's P&L is simply the total so far
        equity["pnl_day"] = equity["total_pnl"].diff()
        equity.loc[0, "pnl_day"] = equity.loc[0, "total_pnl"]

    if "year" not in equity:
        # .str[:4] cuts the first 4 characters of every date: "2012-01-03" -> "2012";
        # .astype(int) turns that text into a whole number
        equity["year"] = equity["date"].str[:4].astype(int)

    if "quarter" not in equity:
        # the quarter, e.g. "2012-Q1"; .dt.quarter gives 1 to 4 for a real date
        quarter_number = pd.to_datetime(equity["date"]).dt.quarter.astype(str)
        equity["quarter"] = equity["date"].str[:4] + "-Q" + quarter_number

    equity["month"] = equity["date"].str[:7]          # "2012-01-03" -> "2012-01"

    # the length of each cycle in days: exit time minus entry time is a time
    # difference; .dt.total_seconds() turns it into seconds, / 86400 into days
    length = pd.to_datetime(trades["exit_time"]) - pd.to_datetime(trades["entry_time"])
    trades["days"] = length.dt.total_seconds() / 86400

    return trades, equity


def periods(equity, column):
    """
    The return of each period (each month, quarter or year, named by `column`):
    the P&L of the period divided by the average margin held in it.
    Gives back two lists, both labelled by the period: the returns and the P&L.
    """
    # groupby puts the days of each period together, so that .sum() and .mean()
    # are taken period by period
    groups = equity.groupby(column)
    pnl = groups["pnl_day"].sum()
    margin = groups["margin"].mean()
    return pnl / margin, pnl


def per_year(equity):
    """Return on margin per year, in per cent: total P&L / average margin / (days / 252)."""
    years = len(equity) / 252.0
    return 100 * equity["pnl_day"].sum() / equity["margin"].mean() / years


def count(table, column, value):
    """How many rows of the table have this value in this column."""
    # table[column] == value gives True/False per row; .sum() counts the Trues
    return int((table[column] == value).sum())


# ---- all numbers of one set of runs ---------------------------------------------

def all_numbers(files):
    """
    Every number of chapter 4 for one set of runs, as a list of
    (passage, what, text as the .tex writes it).
    """
    numbers = []                             # filled step by step below

    runs = {}                                # run -> (trades, equity)
    for run in files:
        runs[run] = load(files[run])

    # ---- tab:results-base and tab:p15: the rows every run has ----
    for run in runs:
        trades, equity = runs[run]
        win = trades["pnl"] > 0              # True for every winning cycle
        last_day = equity.iloc[-1]           # .iloc[-1]: the last row, i.e. the last day
        quarter_returns, _ = periods(equity, "quarter")      # "_": the second answer is not needed here

        # equity["year"] <= 2018 gives True/False per day; equity[...] keeps the True days
        first_half = equity[equity["year"] <= 2018]
        second_half = equity[equity["year"] >= 2019]

        p = "tab:results-base / tab:p15"
        numbers.append((p, run + " cycles", "$%d$" % len(trades)))
        numbers.append((p, run + " exits", "$%d/%d/%d$" % (
            count(trades, "reason", "profit"), count(trades, "reason", "loss"), count(trades, "reason", "gamma"))))
        numbers.append((p, run + " median length", "$%.1f$" % trades["days"].median()))
        numbers.append((p, run + " mean P&L", "$%+.2f$" % trades["pnl"].mean()))
        numbers.append((p, run + " win share", "$%.0f\\%%$" % (100 * win.mean())))     # mean of True/False = share of True
        # .loc[win, "pnl"]: the P&L of the winning cycles only; ~win means "not win"
        numbers.append((p, run + " win mean", "$%+.2f$" % trades.loc[win, "pnl"].mean()))
        numbers.append((p, run + " losing mean", "$%.2f$" % trades.loc[~win, "pnl"].mean()))
        numbers.append((p, run + " total $", "$%s$" % big(last_day["total_pnl"])))
        numbers.append((p, run + " return per year", "$%.1f\\%%$" % per_year(equity)))
        numbers.append((p, run + " 2012-18", "$%.1f\\%%$" % per_year(first_half)))
        numbers.append((p, run + " 2019-26", "$%.1f\\%%$" % per_year(second_half)))
        numbers.append((p, run + " worst quarter", "$%.1f\\%%$" % (100 * quarter_returns.min())))
        if run in ("base_cross", "p15_cross"):
            numbers.append((p, run + " spread cost", "$%s$" % big(trades["spread_cost"].sum())))

    trades_mid, equity_mid = runs["base_mid"]
    trades_cross, equity_cross = runs["base_cross"]
    trades_p15c, equity_p15c = runs["p15_cross"]

    # ---- tab:results-base: the rows only the base case has ----
    for label, run in (("mid", "base_mid"), ("cross", "base_cross")):
        trades, equity = runs[run]
        last_day = equity.iloc[-1]
        quarter_returns, _ = periods(equity, "quarter")

        p = "tab:results-base"
        numbers.append((p, label + " exits", "$%d\\,/\\,%d\\,/\\,%d$" % (
            count(trades, "reason", "profit"), count(trades, "reason", "loss"), count(trades, "reason", "gamma"))))
        numbers.append((p, label + " maturity rules", "$%d\\,/\\,%d\\,/\\,%d$" % (
            count(trades, "maturity_rule", "target"), count(trades, "maturity_rule", "recovery"),
            count(trades, "maturity_rule", "cap"))))
        numbers.append((p, label + " closed cycles $", "$%s$" % big(last_day["realised"])))
        numbers.append((p, label + " open at the end $", "$%d$" % round(last_day["unrealised"])))
        numbers.append((p, label + " interest $", "$%s$" % big(last_day["interest_total"])))
        numbers.append((p, label + " average margin $", "$%s$" % big(equity["margin"].mean())))
        numbers.append((p, label + " negative quarters", "$%d$" % (quarter_returns < 0).sum()))
        numbers.append((p, label + " median quarter", "$%.1f\\%%$" % (100 * quarter_returns.median())))

    # ---- tab:results-years: "year & mid & cross" (two years per line in the table) ----
    year_mid, _ = periods(equity_mid, "year")
    year_cross, _ = periods(equity_cross, "year")
    for year in year_mid.index:              # .index: the period labels, here the years
        mid = 100 * year_mid[year]
        cross = 100 * year_cross[year]
        if str(year) == "2026":
            label = "$%s^\\ast$" % year      # 2026 carries a star: "to 14 August"
        else:
            label = "$%s$" % year
        numbers.append(("tab:results-years", "year %s (mid %.2f, cross %.2f)" % (year, mid, cross),
                        "%s & $%d$ & $%d$" % (label, round(mid), round(cross))))
    positive_years = (year_cross > 0).sum()
    numbers.append(("sec:results-main", "cross positive years",
                    "only $%d$ of the $15$ years are positive" % positive_years))

    # ---- sec:results-main text: the gap between mid and crossing the spread ----
    gap = trades_mid["pnl"].sum() - trades_cross["pnl"].sum()
    numbers.append(("sec:results-main", "gap mid - cross (points)", "$%s$ index points" % big(gap)))
    numbers.append(("sec:results-main", "path effect (points)",
                    "plus $%d$ points" % round(gap - trades_cross["spread_cost"].sum())))
    numbers.append(("sec:results-main", "closed cycles cross $", "$+\\$%s$" % big(equity_cross.iloc[-1]["realised"])))

    # ---- tab:costs (base case crossing the spread) ----
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
    numbers.append((p, "trades", "Trades & $%d$" % len(trades_cross)))
    numbers.append((p, "cost mean / median", "$%.2f$ / $%.2f$" % (
        trades_cross["spread_cost"].mean(), trades_cross["spread_cost"].median())))
    numbers.append((p, "cost share", "$%.1f\\%%$" % (100 * share.mean())))
    numbers.append((p, "cost share 2012-15", "$%d$--$%d\\%%$" % (round(early.min()), round(early.max()))))
    numbers.append((p, "cost share 2019-26", "$%d$--$%d\\%%$" % (round(late.min()), round(late.max()))))
    for reason in ("profit", "loss"):
        # the spread cost of the cycles that ended at this exit
        cost = trades_cross.loc[trades_cross["reason"] == reason, "spread_cost"]
        numbers.append((p, "cost " + reason + " exits", "$%s$, $%.2f$" % (big(cost.sum()), cost.mean())))
    cycles_a_year = len(trades_cross) / (len(equity_cross) / 252.0)
    numbers.append((p, "cycles a year", "$\\approx %d$ cycles a year" % round(cycles_a_year)))

    # ---- sec:backtest-design and sec:realised-entry-delta (base case at mid) ----
    numbers.append(("sec:backtest-design", "snapshots with a leg missing",
                    "at $%d$ snapshots in the base-case" % trades_mid["skipped"].sum()))
    p = "sec:realised-entry-delta"
    numbers.append((p, "entries", "The $%d$ entries" % len(trades_mid)))
    dte_recovery = trades_mid.loc[trades_mid["maturity_rule"] == "recovery", "dte0"].median()
    dte_cap = trades_mid.loc[trades_mid["maturity_rule"] == "cap", "dte0"].median()
    dte_target = trades_mid.loc[trades_mid["maturity_rule"] == "target", "dte0"].median()
    # a median of an even number of values can end in .5 (67.5): round half up, as written
    numbers.append((p, "median days under recovery", "median $%d$ days under recovery" % np.floor(dte_recovery + 0.5)))
    numbers.append((p, "median days cap / target", "$%d$ at the cap, against $%d$ at the target" % (dte_cap, dte_target)))
    delta0 = trades_mid["delta0"]
    # .quantile(0.05): the value 5% of the entries lie below
    numbers.append((p, "entry delta", "median of $%.3f$, a $5$--$95\\%%$ range of $%.3f$--$%.3f$ and extremes $%.3f$ and $%.3f$" % (
        delta0.median(), delta0.quantile(0.05), delta0.quantile(0.95), delta0.min(), delta0.max())))
    numbers.append(("sec:robustness", "profit exits at mid", "($%d$ of $%d$ at mid)" % (
        count(trades_mid, "reason", "profit"), len(trades_mid))))

    # ---- tab:losses-months (base case crossing the spread) ----
    p = "tab:losses-months"
    month_returns, month_pnl = periods(equity_cross, "month")
    winning = month_pnl[month_pnl > 0]       # the winning months only
    losing = month_pnl[month_pnl <= 0]       # the losing months
    worst = losing.sort_values()             # the worst month first
    numbers.append((p, "profitable months", "$%d$ of $%d$" % (len(winning), len(month_pnl))))
    # month_returns[winning.index]: the returns of the winning months
    numbers.append((p, "mean winning month", "$+\\$%s$ ($%.1f\\%%$ of margin)" % (
        big(winning.mean()), 100 * month_returns[winning.index].mean())))
    numbers.append((p, "mean losing month", "$-\\$%s$ ($%.1f\\%%$ of margin)" % (
        big(-losing.mean()), -100 * month_returns[losing.index].mean())))
    numbers.append((p, "all winning months", "$+\\$%s$" % big(winning.sum())))
    numbers.append((p, "all losing months", "$-\\$%s$" % big(-losing.sum())))
    # .iloc[:10]: the first 10 rows, i.e. the 10 worst months
    numbers.append((p, "share of the losses in the 10 / 20 worst", "$%.0f\\%%$ / $%.0f\\%%$" % (
        100 * worst.iloc[:10].sum() / losing.sum(), 100 * worst.iloc[:20].sum() / losing.sum())))
    numbers.append(("sec:results-main", "losing months take back", "take back $%.0f\\%%$ of the gains" % (
        100 * -losing.sum() / winning.sum())))
    # the six worst months: .iloc[:6] keeps the first six; .items() gives (label, value) pairs
    for month, pnl in worst.iloc[:6].items():
        name = MONTH_NAMES[month[5:]]        # "2025-04" -> "04" -> "April"
        numbers.append((p, "worst month " + month, "%s $%s$ & $-\\$%s$" % (name, month[:4], big(-pnl))))

    # ---- tab:losses-rules (base case crossing the spread) ----
    p = "tab:losses-rules"
    for rule, label in (("target", "Opened at the target maturity"),
                        ("recovery", "Opened under recovery"),
                        ("cap", "Opened at the cap")):
        group = trades_cross[trades_cross["maturity_rule"] == rule]        # the cycles opened under this rule
        numbers.append((p, "rule " + rule, "%s & $%d$ & $%+d$ & $%.2f$" % (
            label, len(group), round(group["pnl"].sum()), group["spread_cost"].mean())))
    for reason, label in (("profit", "Closed at the profit trigger"), ("loss", "Closed at the loss trigger")):
        group = trades_cross[trades_cross["reason"] == reason]
        if group["pnl"].sum() > 0:
            sign = "+"
        else:
            sign = "-"
        numbers.append((p, "exit " + reason, "%s & $%d$ & $%s%s$" % (
            label, len(group), sign, big(abs(group["pnl"].sum())))))

    # the text says that at mid all three groups are profitable: check it
    all_profitable = True
    for rule in ("target", "recovery", "cap"):
        if trades_mid.loc[trades_mid["maturity_rule"] == rule, "pnl"].sum() <= 0:
            all_profitable = False
    if all_profitable:
        # (the thesis starts a sentence with it: "At mid all three groups are profitable")
        numbers.append(("sec:results-main", "mid: all three groups profitable", "mid all three groups are profitable"))
    else:
        numbers.append(("sec:results-main", "mid: all three groups profitable", "(NOT TRUE for this set)"))

    # ---- sec:robustness text ----
    p = "sec:robustness"
    numbers.append((p, "spread cost saved (points)", "$%d$ points less spread cost" % round(
        trades_cross["spread_cost"].sum() - trades_p15c["spread_cost"].sum())))
    numbers.append((p, "p15 mid against base mid", "($%.1f\\%%$ against $%.1f\\%%$ a year)" % (
        per_year(runs["p15_mid"][1]), per_year(equity_mid))))
    numbers.append((p, "p15 cross against base cross", "($%.1f\\%%$ against $%.1f\\%%$)" % (
        per_year(equity_p15c), per_year(equity_cross))))

    # the text says the variant's three worst months are those of the base case
    _, p15_month_pnl = periods(equity_p15c, "month")
    p15_worst_three = set(p15_month_pnl.sort_values().index[:3])   # a set: the order does not matter
    base_worst_three = set(worst.index[:3])
    if p15_worst_three == base_worst_three:
        numbers.append((p, "three worst months shared", "three worst months are those"))
    else:
        numbers.append((p, "three worst months shared", "(NOT TRUE for this set)"))

    # ---- tab:p15-test: monthly return, p15 crossing minus base crossing ----
    p = "tab:p15-test"
    p15_month_returns, _ = periods(equity_p15c, "month")
    # the difference month by month, in percentage points; .values: plain numbers
    difference = (100 * (p15_month_returns - month_returns)).values
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

    numbers.append((p, "months", "Months & $%d$" % n))
    numbers.append((p, "mean difference", "$%+.2f$ percentage points" % mean))
    numbers.append((p, "standard deviation", "$%.2f$ percentage points" % sd))
    numbers.append((p, "t-statistic (table)", "$t$-statistic & $%.2f$" % t_stat))
    numbers.append((p, "t-statistic (text)", "$t$-statistic is $%.2f$" % t_stat))
    numbers.append((p, "months the variant is ahead", "variant is ahead & $%d$" % (difference > 0).sum()))
    # (means < 0).mean(): the share of the 10,000 means below zero
    numbers.append((p, "bootstrap: share behind", "variant behind & $%.1f\\%%$" % (100 * (means < 0).mean())))
    # np.percentile(means, 2.5): the value 2.5% of the 10,000 means lie below
    numbers.append((p, "bootstrap: 95% interval", "$%+.2f$ to $%+.2f$ percentage points" % (
        np.percentile(means, 2.5), np.percentile(means, 97.5))))

    return numbers


# ---- print every set ----------------------------------------------------------------

for set_name in RUN_SETS:

    numbers = all_numbers(RUN_SETS[set_name])

    print("=" * 100)
    print("RUNS:", set_name, "  (files:", ", ".join(RUN_SETS[set_name].values()), ")")
    print("=" * 100)

    found = 0
    for passage, what, text in numbers:
        result = in_thesis(text)
        if result is None:
            mark = "?"                       # no .tex to look in
        elif result:
            mark = "yes"
            found += 1
        else:
            mark = "-"
        print("%-3s  %-27s %-42s %s" % (mark, passage, what, text))

    print()
    if tex is None:
        print("%d numbers (thesis .tex not found, not looked up)" % len(numbers))
    else:
        print("%d numbers, %d of them in the thesis as written" % (len(numbers), found))
    print()
