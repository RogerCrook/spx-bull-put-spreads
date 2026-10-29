"""
CHECK: how many quotes get no implied volatility, over the whole sample
(reproduction inventory, row 15; review_log T8, D2)

What this file is for:
    sec:iv-impl says that quotes outside the no-arbitrage bounds get no
    volatility, and that these are 0.90% of the 448 million stored quotes
    (0.3 to 2.9% by year), 99.6% of them in-the-money puts and the rest
    in-the-money calls, with a single one among the 273 million
    out-of-the-money puts the strategy trades. (Until 2026-10-27 the thesis
    gave the methodology report's 0.6 to 0.8%.) This file counts them on every
    row of the stage-2 output.

    Stage 2 stores every cleaned quote with its implied volatility in the
    column "iv"; where the bisection found no answer, iv is empty (NaN).

    In or out of the money is judged against the forward F of the quote's slice:
      a put is in the money when its strike is above F (K > F),
      a call is in the money when its strike is below F (K < F).

Data: all 176 files of Data/04_greeks/ (about 68 GB), read in pieces, four columns only.
Read-only: writes nothing. Takes about 10 minutes (9 minutes on 2026-10-27).
Run it from the main folder:   python checks/check_iv_failures.py
"""

import os                                    # for listing the files in a folder
import pandas as pd                          # pandas works with tables


FOLDER = "Data/04_greeks"                    # stage-2 output, one file per month
COLUMNS = ["option_type", "strike", "forward", "iv"]

# the four groups we count, each with [number of quotes, number without a volatility]
GROUPS = ["out-of-the-money puts", "in-the-money puts", "out-of-the-money calls", "in-the-money calls"]

totals = {}                                  # group -> [quotes, failures], whole sample
by_year = {}                                 # year -> [quotes, failures]

for group in GROUPS:                         # start every counter at zero
    totals[group] = [0, 0]


files = sorted(name for name in os.listdir(FOLDER) if name.endswith(".csv"))   # "spx_2012-01.csv", ...

for number, name in enumerate(files, 1):     # enumerate counts along: 1, 2, 3, ...

    year = name[4:8]                         # "spx_2012-01.csv" -> "2012"
    if year not in by_year:
        by_year[year] = [0, 0]

    # read the month 2 million rows at a time (chunksize), so memory is not filled
    for chunk in pd.read_csv(FOLDER + "/" + name, usecols=COLUMNS, chunksize=2_000_000):

        failed = chunk["iv"].isna()          # True where there is no volatility

        is_put = chunk["option_type"] == "P"                 # True for puts
        above_forward = chunk["strike"] > chunk["forward"]   # True where K > F
        below_forward = chunk["strike"] < chunk["forward"]   # True where K < F

        # the four groups as True/False columns; ~ means "not"
        masks = {
            "out-of-the-money puts":  is_put & ~above_forward,
            "in-the-money puts":      is_put & above_forward,
            "out-of-the-money calls": ~is_put & ~below_forward,
            "in-the-money calls":     ~is_put & below_forward,
        }

        for group in GROUPS:
            in_group = masks[group]
            totals[group][0] += int(in_group.sum())               # quotes in the group
            totals[group][1] += int((in_group & failed).sum())    # of those, without a volatility

        by_year[year][0] += len(chunk)       # all quotes of the year
        by_year[year][1] += int(failed.sum())

    print("read", number, "of", len(files), name)    # progress, so you can see it is running


all_quotes = sum(totals[group][0] for group in GROUPS)       # add the four groups up
all_failed = sum(totals[group][1] for group in GROUPS)

print()
print("all quotes: %d, without a volatility: %d = %.2f%%" % (all_quotes, all_failed, 100 * all_failed / all_quotes))
print()
for group in GROUPS:
    n, f = totals[group]
    print("   %-24s %11d quotes, %9d without a volatility (%.3f%% of the group, %.1f%% of all failures)" % (
        group, n, f, 100 * f / n if n > 0 else 0, 100 * f / all_failed if all_failed > 0 else 0))
print()
print("by year:")
for year in sorted(by_year):
    n, f = by_year[year]
    print("   %s   %.2f%%" % (year, 100 * f / n))
