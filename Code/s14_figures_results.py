"""
FIGURE - the annual returns of chapter 4 (review_log T78, T79)

What this file does:
    It READS the daily equity of the base case at mid and crossing the spread
    (results/) and the S&P 500 with dividends (Data/09_total_return/), computes the
    return of every calendar year, and draws one picture. It changes no data file.
    It writes
        Masterarbeit_Tex_file/figures/returns_years.pdf      (sec:results-main)
            the return of every year: S&P 500 with dividends, base case at mid,
            base case crossing the spread, as bars side by side
    (Until 2026-10-30, T79, it also drew two scatter plots of the quarterly
    returns, returns_quarters.pdf and p15_quarters.pdf; Arian removed them from
    the thesis.)

    The returns are made exactly as in checks/quarters_vs_index.py, which prints
    the same numbers for tab:results-years:
      strategy   P&L of the year / average margin held in it (not annualised,
                 so 2026 runs to 14 August)
      index      close of the total return index on the last trading day of the
                 year / close on the last trading day of the year before - 1
    The file prints each year's three returns, so they can be compared with that
    table.

HOW TO RUN IT
    In PowerShell, from the project folder:   python Code/s14_figures_results.py
    It reads three small files and takes a few seconds.
"""

import os
import matplotlib
matplotlib.use("Agg")                   # draw into a file, no window on screen
import matplotlib.pyplot as plt
import pandas as pd


# ----------------------------------------------------------------------
# SETTINGS
# ----------------------------------------------------------------------

RESULTS = "results/"
INDEX_FILE = "Data/09_total_return/SP500TR_daily.csv"
FIGURES = os.path.join("Masterarbeit_Tex_file", "figures")

# colours: the two of fig:smile (s13_figure_smile.py) and a grey for the index
GREY = "#8c8c8c"
BLUE = "#1f5aa6"                        # at mid
RED = "#b8462e"                         # crossing the spread


# ----------------------------------------------------------------------
# Returns
# ----------------------------------------------------------------------

def year_of(date_text):
    """The year of a date: "2012-02-15" -> "2012"."""
    return date_text[:4]                # [:4]: the first four characters


def strategy_returns(run):
    """
    The return of every calendar year of one run: P&L of the year / average margin
    held in it. Returns a dict {year: return}, in date order.
    """
    equity = pd.read_csv(RESULTS + "equity_" + run + ".csv")
    dates = list(equity["date"])
    pnl_day = list(equity["pnl_day"])       # the P&L of each day, interest included
    margin = list(equity["margin"])         # the margin held at the end of each day

    pnl_sum = {}
    margin_sum = {}
    days = {}
    for i in range(len(dates)):
        y = year_of(dates[i])
        if y not in pnl_sum:                # the first day of a new year: start at zero
            pnl_sum[y] = 0.0
            margin_sum[y] = 0.0
            days[y] = 0
        pnl_sum[y] = pnl_sum[y] + pnl_day[i]
        margin_sum[y] = margin_sum[y] + margin[i]
        days[y] = days[y] + 1

    returns = {}
    for y in pnl_sum:                       # a dict keeps the order in which its keys were added
        returns[y] = pnl_sum[y] / (margin_sum[y] / days[y])
    return returns


def index_returns():
    """
    The return of the S&P 500 with dividends in every calendar year: close on the
    last trading day of the year / close on the last trading day of the year before - 1.
    The file starts in December 2011, so 2012 has a starting close.
    """
    index = pd.read_csv(INDEX_FILE)
    dates = list(index["Date"])
    tr_close = list(index["tr_close"])

    last_close = {}
    years = []                              # in date order
    for i in range(len(dates)):
        y = year_of(dates[i])
        if y not in last_close:
            years.append(y)
        last_close[y] = tr_close[i]         # overwritten day by day, so the last day stays

    returns = {}
    for k in range(1, len(years)):          # from the second year on: each needs the one before
        returns[years[k]] = last_close[years[k]] / last_close[years[k - 1]] - 1
    return returns


def as_list(returns, years):
    """The returns of the given years, in that order, in per cent."""
    values = []
    for y in years:
        values.append(100 * returns[y])
    return values


# ----------------------------------------------------------------------
# The figure
# ----------------------------------------------------------------------

def figure_years():
    """Bars: the return of every year, index, base case at mid, base case crossing the spread."""
    mid = strategy_returns("base_mid")
    cross = strategy_returns("base_cross")
    index = index_returns()
    years = list(mid.keys())                # "2012", ..., "2026"

    for y in years:                         # the numbers drawn, to compare with tab:results-years
        print(y, "index %.1f | mid %.1f | cross %.1f" % (100 * index[y], 100 * mid[y], 100 * cross[y]))

    fig, ax = plt.subplots(figsize=(6.3, 3.2))       # width, height in inches
    width = 0.27                                      # width of one bar; three bars per year
    for k, (values, colour, label) in enumerate([
            (as_list(index, years), GREY, "S&P 500 with dividends"),
            (as_list(mid, years), BLUE, "base case at mid"),
            (as_list(cross, years), RED, "base case crossing the spread")]):
        # enumerate gives the position k = 0, 1, 2 with each entry, used to set
        # the three bars of a year side by side: k - 1 = -1, 0, +1 bar widths
        positions = []
        for i in range(len(years)):
            positions.append(i + (k - 1) * width)
        ax.bar(positions, values, width=width, color=colour, label=label)

    labels = []
    for y in years:
        if y == "2026":
            labels.append(y + "*")                    # 2026 runs to 14 August
        else:
            labels.append(y)
    ax.set_xticks(range(len(years)))
    ax.set_xticklabels(labels, rotation=90)
    ax.axhline(0, color="black", lw=0.6)              # the zero line
    ax.set_ylabel("return (%)")
    # the legend in one row above the plot, so it covers no bar:
    # loc="lower center" is the point of the legend that is placed, and
    # bbox_to_anchor=(0.5, 1.0) puts that point at the middle of the top edge of the plot
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, fontsize=8)
    fig.tight_layout()                                # shrink the margins to fit the labels
    out = os.path.join(FIGURES, "returns_years.pdf")
    fig.savefig(out)
    print("saved", out, "|", len(years), "years")


def main():
    # fonts close to the thesis, as in s13_figure_smile.py
    plt.rcParams["font.family"] = "serif"
    plt.rcParams["mathtext.fontset"] = "cm"
    plt.rcParams["font.size"] = 9
    os.makedirs(FIGURES, exist_ok=True)               # make figures/ if missing
    figure_years()


if __name__ == "__main__":
    main()
