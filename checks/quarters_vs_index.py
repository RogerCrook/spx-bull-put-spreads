"""
CHAPTER 4: the quarterly return of the strategy against the S&P 500 with
dividends (review_log T69)

What this file is for:
    Sections 4.2 (sec:results-main) and 4.4 (sec:robustness) compare, quarter by
    quarter, the return of the strategy with the return of the S&P 500 including
    dividends (the total return index ^SP500TR). This file computes every number
    of that comparison and prints it the way the .tex writes it, next to "yes" if
    it stands in the thesis.

    The two returns of a quarter:
      strategy   P&L of the quarter / average margin held in it, exactly as in
                 checks/chapter4_numbers.py (function periods): the P&L includes
                 the Treasury-bill interest and the change in value of the
                 position still open at the end of the quarter
      index      close of the total return index on the last trading day of the
                 quarter / close on the last trading day of the quarter before - 1
                 (for the first quarter of 2012 the close of 30 December 2011)
    and, as a third reference, the Treasury bills alone:
      T-bills    interest of the quarter / average margin, from the base case at mid
                 (the interest the margin earns, without any option trade)
    The last quarter, 2026 Q3, runs only to 14 August 2026, like the backtest.

    The runs are the four the thesis reports (results/, made 2026-10-28):
      base_mid, base_cross   the base case at mid and crossing the spread (4.2)
      p15_mid, p15_cross     the profit exit at Delta_0 - 0.15 (4.4)

    First the file recomputes three rows of tab:results-base and tab:p15
    (negative quarters, median quarter, worst quarter), to show that its quarters
    are the same as those of checks/chapter4_numbers.py. Then it prints:
      A  the return of every quarter (one line per quarter, for the long tables)
      B  statistics of the quarterly returns, base case and index (4.2)
      C  the same for the four runs, and how often Delta_0 - 0.15 is ahead (4.4)
      D  for information, not planned for the thesis: the index without dividends

    How the "in the thesis" column works: a table row is "yes" when its cells,
    in the order printed, stand in the .tex (the label of the row is not
    checked, it can be worded freely). Short numbers such as "$10$" can also be
    found elsewhere in the thesis, so a "yes" on a single short number is weak.

Data: results/equity_{base_mid,base_cross,p15_mid,p15_cross}.csv and
Data/09_total_return/SP500TR_daily.csv (checks/fetch_sp500tr.py, retrieved
29 October 2026). Read-only: writes nothing. Takes a few seconds.
Run it from the main folder:   python checks/quarters_vs_index.py
"""

import math                                  # math.sqrt, the square root
import os                                    # os.path.exists tells whether a file is there
import pandas as pd                          # pandas works with tables


RESULTS = "results/"
TEX_FILE = "Masterarbeit_Tex_file/Masterarbeit_Tex_file.tex"
INDEX_FILE = "Data/09_total_return/SP500TR_daily.csv"
RUNS = ["base_mid", "base_cross", "p15_mid", "p15_cross"]


# ---- 1. the thesis text, to look the numbers up in ------------------------------------

# The same lookup as in checks/chapter4_numbers.py. The .tex is not in the code
# repository. Without it every number is still computed, but the "in the thesis"
# column shows "?".
if os.path.exists(TEX_FILE):
    tex = open(TEX_FILE, encoding="utf-8").read()
    # the .tex breaks lines anywhere, so a row can be split by a line break.
    # .split() cuts the text at every space and line break, and " ".join glues
    # the pieces back together with single spaces.
    tex_one_line = " ".join(tex.split())
else:
    tex = None                               # None = no thesis text to look in
    print("Thesis .tex not found (" + TEX_FILE + "): the numbers are not looked up.")
    print()


def in_thesis(text):
    """"yes" if this exact text occurs in the thesis, "-" if not, "?" without the thesis."""
    if tex is None:
        return "?"
    if text in tex:                          # as it stands, on one line of the .tex
        return "yes"
    if " ".join(text.split()) in tex_one_line:   # or split over two lines
        return "yes"
    return "-"


# ---- 2. small helpers ---------------------------------------------------------------------

def quarter_of(date_text):
    """The quarter of a date, written as in the equity files: "2012-02-15" -> "2012-Q1"."""
    year = date_text[:4]                     # [:4]: the first four characters, the year
    month = int(date_text[5:7])              # [5:7]: the 6th and 7th characters, the month
    return year + "-Q" + str((month - 1) // 3 + 1)   # // divides and drops the remainder: months 1-3 -> 1, 4-6 -> 2, ...


def per_cent(x):
    """A share as a per cent figure with one decimal, as the .tex writes it in a table cell: 0.141 -> "$14.1$"."""
    return "$%.1f$" % (100 * x)


def per_cent_sign(x):
    """The same with a per cent sign, as in tab:results-base: 0.141 -> "$14.1\\%$"."""
    return "$%.1f\\%%$" % (100 * x)


def mean(values):
    """The average of a list of numbers."""
    return sum(values) / len(values)


def median(values):
    """The middle value of a list of numbers (the average of the two middle ones if the count is even)."""
    ordered = sorted(values)                 # sorted gives a new list, smallest first
    n = len(ordered)
    if n % 2 == 1:                           # % gives the remainder: 1 means n is odd
        return ordered[n // 2]
    return (ordered[n // 2 - 1] + ordered[n // 2]) / 2


def standard_deviation(values):
    """The sample standard deviation: the sum of squared distances from the mean, over n - 1, square root."""
    m = mean(values)
    total = 0.0
    for v in values:
        total = total + (v - m) ** 2         # ** 2: squared
    return math.sqrt(total / (len(values) - 1))


def correlation_and_slope(x, y):
    """
    The correlation of two lists of the same length, and the slope of the
    straight line that fits y against x best (least squares): how many per cent
    y moves, on average, when x moves by one per cent.
    """
    mx = mean(x)
    my = mean(y)
    sxy = 0.0                                # sum of (x - mean x) * (y - mean y)
    sxx = 0.0                                # sum of (x - mean x) squared
    syy = 0.0                                # sum of (y - mean y) squared
    for i in range(len(x)):
        sxy = sxy + (x[i] - mx) * (y[i] - my)
        sxx = sxx + (x[i] - mx) ** 2
        syy = syy + (y[i] - my) ** 2
    return sxy / math.sqrt(sxx * syy), sxy / sxx


def show(label, cells):
    """Print one table row: the cells joined by " & ", and whether they stand in the thesis."""
    row = " & ".join(cells)
    print("  %-4s %-46s %s" % (in_thesis(row), label, row))


# ---- 3. the strategy: return of each quarter, for each run ----------------------------------

strategy = {}                                # run -> {quarter: return}
tbills = {}                                  # quarter -> T-bill interest / average margin (base case at mid)
last_day = {}                                # quarter -> last day of the quarter in the equity file
quarters = []                                # the quarters in date order: "2012-Q1", ..., "2026-Q3"

for run in RUNS:
    equity = pd.read_csv(RESULTS + "equity_" + run + ".csv")

    # the columns as plain Python lists, so that the loop below can go through
    # them with simple positions 0, 1, 2, ...
    dates = list(equity["date"])
    pnl_day = list(equity["pnl_day"])        # the P&L of each day, interest included
    margin = list(equity["margin"])          # the margin held at the end of each day
    interest = list(equity["interest_today"])   # the T-bill interest of each day

    # add up, quarter by quarter, the P&L, the margin and the interest, and count the days
    pnl_sum = {}
    margin_sum = {}
    interest_sum = {}
    days = {}
    for i in range(len(dates)):
        q = quarter_of(dates[i])
        if q != equity["quarter"][i]:        # the file's own quarter column must agree
            print("quarter mismatch on", dates[i], q, equity["quarter"][i])
        if q not in pnl_sum:                 # the first day of a new quarter: start at zero
            pnl_sum[q] = 0.0
            margin_sum[q] = 0.0
            interest_sum[q] = 0.0
            days[q] = 0
        pnl_sum[q] = pnl_sum[q] + pnl_day[i]
        margin_sum[q] = margin_sum[q] + margin[i]
        interest_sum[q] = interest_sum[q] + interest[i]
        days[q] = days[q] + 1
        last_day[q] = dates[i]               # the rows are in date order, so the last one seen is the last day

    # return of a quarter = its P&L / its average margin (average = sum / number of days)
    strategy[run] = {}
    for q in pnl_sum:
        average_margin = margin_sum[q] / days[q]
        strategy[run][q] = pnl_sum[q] / average_margin
        if run == "base_mid":
            tbills[q] = interest_sum[q] / average_margin

    if run == "base_mid":
        quarters = list(pnl_sum.keys())      # a dict keeps the order in which its keys were added


# ---- 4. the index: return of each quarter ------------------------------------------------------

index = pd.read_csv(INDEX_FILE)
index_dates = list(index["Date"])
tr_close = list(index["tr_close"])           # with dividends reinvested
price_close = list(index["price_close"])     # the price index, without dividends

# the close and the date of the last trading day of every quarter in the file
# (it starts in December 2011, so 2011-Q4 is there as the starting point)
last_tr = {}
last_price = {}
index_last_day = {}
index_quarters = []                          # in date order: "2011-Q4", "2012-Q1", ...
for i in range(len(index_dates)):
    q = quarter_of(index_dates[i])
    if q not in last_tr:
        index_quarters.append(q)
    last_tr[q] = tr_close[i]                 # overwritten day by day, so the last day of the quarter stays
    last_price[q] = price_close[i]
    index_last_day[q] = index_dates[i]

index_tr = {}                                # quarter -> return with dividends
index_price = {}                             # quarter -> return without dividends
for k in range(1, len(index_quarters)):      # from the second quarter on: each needs the one before
    q = index_quarters[k]
    before = index_quarters[k - 1]
    index_tr[q] = last_tr[q] / last_tr[before] - 1
    index_price[q] = last_price[q] / last_price[before] - 1

# both must end each quarter on the same day (the same trading calendar)
different_end = []
for q in quarters:
    if index_last_day[q] != last_day[q]:
        different_end.append(q)
print("Quarters:", len(quarters), "from", quarters[0], "to", quarters[-1],
      "| last day of the backtest", last_day[quarters[-1]],
      "| last day of the index file", index_dates[-1])
print("Quarters in which the index file and the backtest end on different days:", different_end)
print("Start of the first quarter of the index: close of", index_last_day[index_quarters[0]])
print()


# lists in quarter order, used by every statistic below
x_index = []
for q in quarters:
    x_index.append(index_tr[q])
x_tbills = []
for q in quarters:
    x_tbills.append(tbills[q])
x_run = {}
for run in RUNS:
    x_run[run] = []
    for q in quarters:
        x_run[run].append(strategy[run][q])


# ---- 5. the same quarters as checks/chapter4_numbers.py ----------------------------------------

print("=" * 100)
print("CHECK: rows of tab:results-base and tab:p15 recomputed from these quarters")
print("=" * 100)
for run in RUNS:
    returns = x_run[run]
    negative = 0
    for r in returns:
        if r < 0:
            negative = negative + 1
    worst = min(returns)
    print("  %-11s negative quarters %s (%s)   median %s (%s)   worst %s (%s)" % (
        run, "$%d$" % negative, in_thesis("$%d$" % negative),
        per_cent_sign(median(returns)), in_thesis(per_cent_sign(median(returns))),
        per_cent_sign(worst), in_thesis(per_cent_sign(worst))))
print("  (the medians of p15 are not in tab:p15, but they are in tab:p15-quarters)")
print()


# ---- 6. A: the return of every quarter ----------------------------------------------------------

print("=" * 100)
print("A  RETURN OF EVERY QUARTER, per cent (2026 Q3 to 14 August)")
print("   4.2  tab:quarters-base: S&P 500 with dividends & base mid & base cross")
print("   4.4  tab:quarters-p15:  S&P 500 with dividends & base cross & Delta_0 - 0.15 cross")
print("=" * 100)
print("  4.2")
for i in range(len(quarters)):
    label = quarters[i].replace("-", " ")    # "2012-Q1" -> "2012 Q1"
    show(label, [per_cent(x_index[i]), per_cent(x_run["base_mid"][i]), per_cent(x_run["base_cross"][i])])
print("  4.4")
for i in range(len(quarters)):
    label = quarters[i].replace("-", " ")
    show(label, [per_cent(x_index[i]), per_cent(x_run["base_cross"][i]), per_cent(x_run["p15_cross"][i])])
print()


# ---- 7. the statistics of one list of quarterly returns ----------------------------------------

def statistics(returns):
    """Mean, median, standard deviation, best and worst quarter, number of negative quarters."""
    best = max(returns)
    worst = min(returns)
    negative = 0
    for r in returns:
        if r < 0:
            negative = negative + 1
    return {"mean": mean(returns), "median": median(returns),
            "sd": standard_deviation(returns),
            "best": best, "best quarter": quarters[returns.index(best)],      # .index(v): the position of v in the list
            "worst": worst, "worst quarter": quarters[returns.index(worst)],
            "negative": negative}


def by_index_direction(returns):
    """
    The mean return in the quarters in which the index fell, and in those in which
    it rose, and how many of each (a quarter with an index return of exactly zero
    would count as "rose").
    """
    down = []
    up = []
    for i in range(len(quarters)):
        if x_index[i] < 0:
            down.append(returns[i])
        else:
            up.append(returns[i])
    return mean(down), len(down), mean(up), len(up)


def cells(stats, key):
    """One cell per column: the statistic `key` of each column, as a per cent figure."""
    result = []
    for s in stats:
        result.append(per_cent_sign(s[key]))
    return result


def statistics_rows(columns):
    """Print the statistics rows for a list of (name, returns) columns, one cell per column."""
    stats = []
    for name, returns in columns:
        stats.append(statistics(returns))

    show("Mean quarter", cells(stats, "mean"))
    show("Median quarter", cells(stats, "median"))
    show("Standard deviation", cells(stats, "sd"))
    # best and worst quarter: printed for information, not in the thesis tables
    # (the worst is 2020 Q1 for all but the T-bills, the first of the five worst
    # quarters of the index printed below, and in tab:results-base already)
    show("Best quarter", cells(stats, "best"))
    best_quarters = []
    worst_quarters = []
    negative_cells = []
    for s in stats:
        best_quarters.append(s["best quarter"])
        worst_quarters.append(s["worst quarter"])
        negative_cells.append("$%d$" % s["negative"])
    print("       its quarter:", best_quarters)
    show("Worst quarter", cells(stats, "worst"))
    print("       its quarter:", worst_quarters)
    show("Negative quarters (of %d)" % len(quarters), negative_cells)

    # correlation and slope against the index; "---" for the index itself, and
    # for the T-bills, whose return hardly changes from quarter to quarter, so that
    # a correlation with it means nothing (the thesis writes "---" there too)
    correlation_cells = []
    slope_cells = []
    for name, returns in columns:
        if name == "index" or name == "T-bills":
            correlation_cells.append("---")
            slope_cells.append("---")
        else:
            c, b = correlation_and_slope(x_index, returns)
            correlation_cells.append("$%.2f$" % c)
            slope_cells.append("$%.2f$" % b)
    show("Correlation with the index", correlation_cells)
    show("Slope against the index", slope_cells)

    down_cells = []
    up_cells = []
    for name, returns in columns:
        mean_down, n_down, mean_up, n_up = by_index_direction(returns)
        down_cells.append(per_cent_sign(mean_down))
        up_cells.append(per_cent_sign(mean_up))
    show("Mean in the %d quarters the index fell" % n_down, down_cells)
    show("Mean in the %d quarters the index rose" % n_up, up_cells)


def worst_index_quarters(columns, how_many):
    """Print the quarters in which the index did worst, with the return of every column in them."""
    # the positions 0, 1, ... of the quarters, sorted by the index return, lowest first;
    # key=... says what to sort by: "lambda i: x_index[i]" is a one-line function
    # that gives back the index return of quarter i
    order = sorted(range(len(quarters)), key=lambda i: x_index[i])
    for i in order[:how_many]:               # [:how_many]: the first how_many of them
        cells = []
        for name, returns in columns:
            cells.append(per_cent_sign(returns[i]))
        show("  " + quarters[i].replace("-", " "), cells)


# ---- 8. B: section 4.2 ---------------------------------------------------------------------------

columns_42 = [("index", x_index), ("T-bills", x_tbills),
              ("base_mid", x_run["base_mid"]), ("base_cross", x_run["base_cross"])]

print("=" * 100)
print("B  4.2  tab:quarters-index: columns S&P 500 with dividends & T-bills & base mid & base cross")
print("=" * 100)
statistics_rows(columns_42)
print("  The five worst quarters of the index:")
worst_index_quarters(columns_42, 5)
print()


# ---- 9. C: section 4.4 ---------------------------------------------------------------------------

columns_44 = [("index", x_index),
              ("base_mid", x_run["base_mid"]), ("p15_mid", x_run["p15_mid"]),
              ("base_cross", x_run["base_cross"]), ("p15_cross", x_run["p15_cross"])]

print("=" * 100)
print("C  4.4  tab:p15-quarters: columns S&P 500 with dividends & base mid & p15 mid & base cross & p15 cross")
print("=" * 100)
statistics_rows(columns_44)
print("  The five worst quarters of the index:")
worst_index_quarters(columns_44, 5)

# how often Delta_0 - 0.15 does better than the base case, in all quarters and in
# the quarters in which the index fell; and the mean difference in each group
print("  Delta_0 - 0.15 against the base case:")
for setting in ["mid", "cross"]:
    base = x_run["base_" + setting]
    p15 = x_run["p15_" + setting]
    ahead = 0                                # quarters in which p15 is ahead
    ahead_down = 0                           # of them, quarters in which the index fell
    n_down = 0
    differences_down = []
    differences_up = []
    for i in range(len(quarters)):
        difference = p15[i] - base[i]
        if difference > 0:
            ahead = ahead + 1
        if x_index[i] < 0:
            n_down = n_down + 1
            differences_down.append(difference)
            if difference > 0:
                ahead_down = ahead_down + 1
        else:
            differences_up.append(difference)
    show("%-5s quarters ahead (of %d)" % (setting, len(quarters)), ["$%d$" % ahead])
    show("%-5s ahead in the %d quarters the index fell" % (setting, n_down), ["$%d$" % ahead_down])
    show("%-5s mean difference, index fell / rose (points)" % setting,
         [per_cent(mean(differences_down)), per_cent(mean(differences_up))])
print()


# ---- 10. D: for information, the index without dividends -----------------------------------------

print("=" * 100)
print("D  For information (not planned for the thesis): the index without dividends")
print("=" * 100)
x_price = []
for q in quarters:
    x_price.append(index_price[q])
dividend_part = []
for i in range(len(quarters)):
    dividend_part.append(x_index[i] - x_price[i])
print("  mean quarter with dividends %.2f%%, without %.2f%%, difference %.2f%% (smallest %.2f%%, largest %.2f%%)" % (
    100 * mean(x_index), 100 * mean(x_price), 100 * mean(dividend_part),
    100 * min(dividend_part), 100 * max(dividend_part)))
print("  mean T-bill quarter %.2f%% (smallest %.2f%%, largest %.2f%%)" % (
    100 * mean(x_tbills), 100 * min(x_tbills), 100 * max(x_tbills)))
