"""
CHAPTER 4: the quarterly and annual returns of the strategy against the S&P 500
with dividends (review_log T69, T78)

What this file is for:
    Sections sec:results-main and sec:robustness compare, quarter by quarter and
    year by year, the return of the strategy with the return of the S&P 500
    including dividends (the total return index ^SP500TR). This file computes
    every number of their tables and prints it the way the .tex writes it, next
    to "yes" if it stands in the thesis.

    The two returns of a quarter:
      strategy   P&L of the quarter / average margin held in it: the P&L
                 includes the Treasury-bill interest and the change in value of
                 the position still open at the end of the quarter
      index      close of the total return index on the last trading day of the
                 quarter / close on the last trading day of the quarter before - 1
                 (for the first quarter of 2012 the close of 30 December 2011)
    The last quarter, 2026 Q3, runs only to 14 August 2026, like the backtest.

    The runs are the four the thesis reports (results/, made 2026-10-28):
      base_mid, base_cross   the base case at mid and crossing the spread (sec:results-main)
      p15_mid, p15_cross     the profit exit at Delta_0 - 0.15 (sec:robustness)

    It prints:
      A  the return of every quarter (tab:quarters-base, tab:quarters-p15)
      B  statistics of the quarterly returns, base case and index (tab:quarters-index)
      C  the same for the four runs (tab:p15-quarters)
      E  the return of every calendar year, the whole sample per year
         (tab:results-years, tab:p15-years), and the negative and worst years
         (tab:p15-quarters)

    The return of a year is made like that of a quarter: the strategy's P&L of
    the year / average margin held in it (not annualised, so 2026 is the return to
    14 August), the index's close on the last trading day of the year / close on
    the last trading day of the year before - 1. The whole sample per year is, for
    the strategy, total P&L / average margin / number of years (a year = 252
    trading days), which is not compounded. For the index it is the compounded
    return per year over the same trading days.

    Until 2026-11-03 (review_log T112) the file also printed figures no longer in
    the thesis (the T-bills alone, a check of the set-aside tab:results-base and
    tab:p15, the best quarters, how often p15 is ahead, the index without
    dividends, the mean of the index's full years). That code is in commit
    cf6519a (tag thesis-v4).

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


def year_of(date_text):
    """The year of a date: "2012-02-15" -> "2012"."""
    return date_text[:4]                     # [:4]: the first four characters


def per_cent(x):
    """A share as a per cent figure with one decimal, as the .tex writes it in a table cell: 0.141 -> "$14.1$"."""
    return "$%.1f$" % (100 * x)


def per_cent_sign(x):
    """The same with a per cent sign, as in tab:quarters-index: 0.141 -> "$14.1\\%$"."""
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


# ---- 3. the strategy: return of each quarter and each year, for each run --------------------

strategy = {}                                # run -> {quarter: return}
strategy_year = {}                           # run -> {year: return}
whole_sample = {}                            # run -> return per year over the whole sample
last_day = {}                                # quarter -> last day of the quarter in the equity file
quarters = []                                # the quarters in date order: "2012-Q1", ..., "2026-Q3"
years = []                                   # the years in order: "2012", ..., "2026"
backtest_days = 0                            # number of trading days in the backtest


def returns_by(dates, pnl_day, margin, label_of):
    """
    The return of every period (quarter or year, named by the function label_of):
    the P&L of the period / the average margin held in it. Returns a dict
    {period: return}, in date order.
    """
    # add up, period by period, the P&L and the margin, and count the days
    pnl_sum = {}
    margin_sum = {}
    days = {}
    for i in range(len(dates)):
        period = label_of(dates[i])
        if period not in pnl_sum:            # the first day of a new period: start at zero
            pnl_sum[period] = 0.0
            margin_sum[period] = 0.0
            days[period] = 0
        pnl_sum[period] = pnl_sum[period] + pnl_day[i]
        margin_sum[period] = margin_sum[period] + margin[i]
        days[period] = days[period] + 1

    # return of a period = its P&L / its average margin (average = sum / number of days)
    returns = {}
    for period in pnl_sum:
        returns[period] = pnl_sum[period] / (margin_sum[period] / days[period])
    return returns


for run in RUNS:
    equity = pd.read_csv(RESULTS + "equity_" + run + ".csv")

    # the columns as plain Python lists, so that the loops can go through them
    # with simple positions 0, 1, 2, ...
    dates = list(equity["date"])
    pnl_day = list(equity["pnl_day"])        # the P&L of each day, interest included
    margin = list(equity["margin"])          # the margin held at the end of each day

    for i in range(len(dates)):
        if quarter_of(dates[i]) != equity["quarter"][i]:     # the file's own quarter column must agree
            print("quarter mismatch on", dates[i], quarter_of(dates[i]), equity["quarter"][i])
        last_day[quarter_of(dates[i])] = dates[i]   # the rows are in date order, so the last one seen is the last day

    strategy[run] = returns_by(dates, pnl_day, margin, quarter_of)
    strategy_year[run] = returns_by(dates, pnl_day, margin, year_of)

    # the whole sample: total P&L / average margin of all days / number of years
    number_of_years = len(dates) / 252.0
    whole_sample[run] = sum(pnl_day) / (sum(margin) / len(margin)) / number_of_years

    if run == "base_mid":
        quarters = list(strategy[run].keys())       # a dict keeps the order in which its keys were added
        years = list(strategy_year[run].keys())
        backtest_days = len(dates)


# ---- 4. the index: return of each quarter and each year --------------------------------------

index = pd.read_csv(INDEX_FILE)
index_dates = list(index["Date"])
tr_close = list(index["tr_close"])           # with dividends reinvested


def index_returns_by(label_of):
    """
    The return of the index in every period (quarter or year, named by the
    function label_of): close on its last trading day / close on the last
    trading day of the period before - 1. Also gives back the last trading day
    of every period. The file starts in December 2011, so 2011 (2011-Q4) is
    there as the starting point and has no return of its own.
    """
    last_close = {}
    last_date = {}
    periods = []                             # in date order
    for i in range(len(index_dates)):
        period = label_of(index_dates[i])
        if period not in last_close:
            periods.append(period)
        last_close[period] = tr_close[i]     # overwritten day by day, so the last day of the period stays
        last_date[period] = index_dates[i]
    returns = {}
    for k in range(1, len(periods)):         # from the second period on: each needs the one before
        returns[periods[k]] = last_close[periods[k]] / last_close[periods[k - 1]] - 1
    return returns, last_date, last_close, periods


index_tr, index_last_day, _, index_quarters = index_returns_by(quarter_of)
index_year, _, last_tr_year, index_years = index_returns_by(year_of)

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

# the index over the whole sample: from the close of 30 December 2011 to the close
# of 14 August 2026, compounded per year over the backtest's trading days
growth = last_tr_year[index_years[-1]] / last_tr_year[index_years[0]]
index_whole = growth ** (252.0 / backtest_days) - 1     # ** : to the power of


# lists in quarter order, used by every statistic below
x_index = []
for q in quarters:
    x_index.append(index_tr[q])
x_run = {}
for run in RUNS:
    x_run[run] = []
    for q in quarters:
        x_run[run].append(strategy[run][q])


# ---- 5. A: the return of every quarter ----------------------------------------------------------

print("=" * 100)
print("A  RETURN OF EVERY QUARTER, per cent (2026 Q3 to 14 August)")
print("   sec:results-main  tab:quarters-base: S&P 500 with dividends & base mid & base cross")
print("   sec:robustness    tab:quarters-p15:  S&P 500 with dividends & base cross & Delta_0 - 0.15 cross")
print("=" * 100)
print("  sec:results-main")
for i in range(len(quarters)):
    label = quarters[i].replace("-", " ")    # "2012-Q1" -> "2012 Q1"
    show(label, [per_cent(x_index[i]), per_cent(x_run["base_mid"][i]), per_cent(x_run["base_cross"][i])])
print("  sec:robustness")
for i in range(len(quarters)):
    label = quarters[i].replace("-", " ")
    show(label, [per_cent(x_index[i]), per_cent(x_run["base_cross"][i]), per_cent(x_run["p15_cross"][i])])
print()


# ---- 6. the statistics of a list of columns of quarterly returns ---------------------------------

def statistics_rows(columns):
    """Print the statistics rows for a list of (name, returns) columns, one cell per column."""
    mean_cells = []
    median_cells = []
    sd_cells = []
    negative_cells = []
    for name, returns in columns:
        mean_cells.append(per_cent_sign(mean(returns)))
        median_cells.append(per_cent_sign(median(returns)))
        sd_cells.append(per_cent_sign(standard_deviation(returns)))
        negative = 0
        for r in returns:
            if r < 0:
                negative = negative + 1
        negative_cells.append("$%d$" % negative)
    show("Mean quarter", mean_cells)
    show("Median quarter", median_cells)
    show("Standard deviation", sd_cells)
    show("Negative quarters (of %d)" % len(quarters), negative_cells)

    # correlation and slope against the index; "---" for the index itself
    # (the thesis writes "---" there too)
    correlation_cells = []
    slope_cells = []
    for name, returns in columns:
        if name == "index":
            correlation_cells.append("---")
            slope_cells.append("---")
        else:
            c, b = correlation_and_slope(x_index, returns)
            correlation_cells.append("$%.2f$" % c)
            slope_cells.append("$%.2f$" % b)
    show("Correlation with the index", correlation_cells)
    show("Least-squares slope against the index", slope_cells)

    # the mean return in the quarters in which the index fell, and in those in
    # which it rose (a quarter with an index return of exactly zero would count
    # as "rose")
    down_cells = []
    up_cells = []
    for name, returns in columns:
        down = []
        up = []
        for i in range(len(quarters)):
            if x_index[i] < 0:
                down.append(returns[i])
            else:
                up.append(returns[i])
        down_cells.append(per_cent_sign(mean(down)))
        up_cells.append(per_cent_sign(mean(up)))
    show("Mean in the %d quarters the index fell" % len(down), down_cells)
    show("Mean in the %d quarters the index rose" % len(up), up_cells)


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


# ---- 7. B: sec:results-main ----------------------------------------------------------------------

columns_base = [("index", x_index),
                ("base_mid", x_run["base_mid"]), ("base_cross", x_run["base_cross"])]

print("=" * 100)
print("B  sec:results-main  tab:quarters-index: columns S&P 500 with dividends & base mid & base cross")
print("=" * 100)
statistics_rows(columns_base)
print("  The five worst quarters of the index:")
worst_index_quarters(columns_base, 5)
print()


# ---- 8. C: sec:robustness ------------------------------------------------------------------------

columns_p15 = [("index", x_index),
               ("base_mid", x_run["base_mid"]), ("p15_mid", x_run["p15_mid"]),
               ("base_cross", x_run["base_cross"]), ("p15_cross", x_run["p15_cross"])]

print("=" * 100)
print("C  sec:robustness  tab:p15-quarters: columns S&P 500 with dividends & base mid & p15 mid & base cross & p15 cross")
print("=" * 100)
statistics_rows(columns_p15)
print("  The five worst quarters of the index:")
worst_index_quarters(columns_p15, 5)
print()


# ---- 9. E: the return of every calendar year (review_log T78) -------------------------------------

print("=" * 100)
print("E  RETURN OF EVERY CALENDAR YEAR, per cent (2026 to 14 August, not annualised)")
print("   sec:results-main  tab:results-years: S&P 500 with dividends & base mid & base cross")
print("   sec:robustness    tab:p15-years: S&P 500 with dividends & base mid & p15 mid & base cross & p15 cross")
print("=" * 100)
print("  sec:results-main")
for y in years:
    show(y, [per_cent(index_year[y]),
             per_cent(strategy_year["base_mid"][y]), per_cent(strategy_year["base_cross"][y])])
show("2012-2026, per year", [per_cent(index_whole),
                             per_cent(whole_sample["base_mid"]), per_cent(whole_sample["base_cross"])])
print("  sec:robustness")
for y in years:
    show(y, [per_cent(index_year[y]),
             per_cent(strategy_year["base_mid"][y]), per_cent(strategy_year["p15_mid"][y]),
             per_cent(strategy_year["base_cross"][y]), per_cent(strategy_year["p15_cross"][y])])
show("2012-2026, per year", [per_cent(index_whole),
                             per_cent(whole_sample["base_mid"]), per_cent(whole_sample["p15_mid"]),
                             per_cent(whole_sample["base_cross"]), per_cent(whole_sample["p15_cross"])])

# the negative years and the worst year, the last two rows of tab:p15-quarters
# (2026 counted as a year)
year_returns = {"index": index_year}         # column name -> {year: return}
for run in RUNS:
    year_returns[run] = strategy_year[run]
negative_cells = []
worst_cells = []
worst_years = []
# in the column order of tab:p15-quarters
for name in ["index", "base_mid", "p15_mid", "base_cross", "p15_cross"]:
    returns = year_returns[name]
    negative = 0
    worst_year = years[0]
    for y in years:
        if returns[y] < 0:
            negative = negative + 1
        if returns[y] < returns[worst_year]:
            worst_year = y
    negative_cells.append("$%d$" % negative)
    worst_cells.append(per_cent_sign(returns[worst_year]))
    worst_years.append(worst_year)
print("  tab:p15-quarters")
show("Negative years (of %d)" % len(years), negative_cells)
show("Worst year %s" % worst_years, worst_cells)
