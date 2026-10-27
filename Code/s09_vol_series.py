"""
THE 30-DAY VOLATILITY SERIES AND THE STRESS INDICATOR

What this file is for:
    We need one number per day: "how volatile does the market expect the next
    30 days to be?" That is essentially what VIX measures, and we build it
    from our own data.

    We use it for two things:
      1. the sigma in the strike formula  K = F * exp(-k * sigma * sqrt(tau))
      2. deciding what counts as a "stress phase"

HOW IT WORKS
    On any given day there is rarely an expiry at exactly 30 days. So we take
    the two expiries that bracket 30 days and interpolate between them.

    We interpolate TOTAL VARIANCE (sigma^2 * tau), not volatility itself,
    because variance adds up over time while volatility does not.

THE STRESS INDICATOR (thesis, Definition "Stress indicator")
    A day is a stress day if its 30-day volatility is ABOVE the 80th percentile
    of the 30-day volatilities of the 252 days BEFORE it. The day itself is
    not part of its own window, so on day t we only use information that was
    already known. We call that percentile the "threshold" of day t.

    Because the threshold only uses the past, the first 252 days of the
    sample have no threshold (nothing to compare with yet).

    As a named alternative (thesis, "Why a trailing quantile") we also mark
    days above a fixed level, FIXED_LEVEL. It is only for the sensitivity
    analysis.

HOW TO RUN IT
    python Code/s09_vol_series.py
"""

import numpy as np
import pandas as pd


IN_FILE = "Data/05_atm_vol.csv"
OUT_FILE = "Data/06_vol30.csv"

SNAPSHOT = "15:45:00"          # one snapshot per day, near the close
TARGET_DAYS = 30               # the maturity we want

WINDOW = 252                   # number of past days used for the percentile
PERCENTILE = 0.80              # the stress level
FIXED_LEVEL = 0.25             # the alternative: a fixed volatility level


def interpolate_one_day(expiries, vols):
    """
    Given the expiries available on one day and their ATM volatilities,
    work out the 30-day volatility.

      expiries : days to expiry, e.g. [7, 14, 28, 35, 60]
      vols     : the ATM volatility for each, e.g. [0.21, 0.19, 0.18, 0.18, 0.17]
    """

    # we cannot interpolate if everything is on one side of 30 days
    if expiries.min() > TARGET_DAYS or expiries.max() < TARGET_DAYS:
        return np.nan

    # turn volatility into total variance:  variance = sigma^2 * tau
    taus = expiries / 365.0
    total_variance = (vols ** 2) * taus

    # interpolate the total variance at 30 days.
    # np.interp draws straight lines between the points (taus, total_variance)
    # and reads off the value at target_tau, i.e. between the two expiries
    # that bracket 30 days. taus must be sorted, which the caller makes sure of.
    target_tau = TARGET_DAYS / 365.0
    variance_at_30 = np.interp(target_tau, taus, total_variance)

    # turn it back into a volatility
    return float(np.sqrt(variance_at_30 / target_tau))


def add_stress_indicator(series):
    """
    Add three columns to the daily table:

      threshold    : the 80th percentile of the 252 days BEFORE this day
      stress       : True if vol30 is above the threshold
      stress_fixed : True if vol30 is above the fixed level (the alternative)

    The table must be sorted by date, oldest first.
    """

    values = series["vol30"].values          # the 30-day vols as a plain array

    thresholds = []                          # one threshold per day goes in here
    stress = []                              # one True/False per day goes in here

    # i counts the days: 0, 1, 2, ... up to the last one. values[i] is day i.
    # This only works because the table was sorted by date and renumbered first.
    for i in range(len(values)):

        # the first WINDOW days have fewer than 252 days before them
        if i < WINDOW:
            thresholds.append(np.nan)        # nan = "no number"
            stress.append(False)
            continue                         # go straight to the next day

        # the 252 days before day i. values[i - 252 : i] stops one short of i,
        # so day i itself is NOT included
        past = values[i - WINDOW: i]

        # np.percentile wants the level in percent (80), not as a fraction (0.80),
        # hence the * 100. Between two data points it interpolates linearly.
        threshold = np.percentile(past, PERCENTILE * 100)

        thresholds.append(threshold)

        # bool(...) turns numpy's True/False into Python's plain True/False
        stress.append(bool(values[i] > threshold))

    # turn the two lists into new columns of the table (same order as the rows)
    series["threshold"] = thresholds
    series["stress"] = stress

    # the fixed-level alternative: True on every day with vol30 above 25%
    series["stress_fixed"] = series["vol30"] > FIXED_LEVEL

    return series


def main():

    print("loading", IN_FILE, "...")

    data = pd.read_csv(IN_FILE)

    print(len(data), "rows")

    # keep one snapshot per day. quote_datetime is text like "2021-06-08 15:45:00";
    # .str[11:] cuts off the first 11 characters (date and space), leaving the time.
    # .copy() makes a separate table, so pandas does not warn when we add columns.
    times = data["quote_datetime"].str[11:]
    data = data[times == SNAPSHOT].copy()

    print(len(data), "rows at", SNAPSHOT)

    # drop slices where the volatility could not be fitted
    data = data[data["atm_iv"].notna()].copy()

    # add a plain date column to group by (the first 10 characters)
    data["date"] = data["quote_datetime"].str[:10]

    results = []                             # one dictionary per day goes in here
    days_without_30 = 0                      # counts days where 30 days is not bracketed

    # groupby("date") splits the table into one small table per date. Each step of
    # the loop gives the date and that day's rows (which we call one_day).
    for date, one_day in data.groupby("date"):

        # if both SPX and SPXW offer the same dte, average them:
        # group that day's rows by dte, take the mean of atm_iv within each group.
        # as_index=False keeps dte as an ordinary column, so we can read it below.
        one_day = one_day.groupby("dte", as_index=False)["atm_iv"].mean()

        one_day = one_day.sort_values("dte")     # shortest expiry first

        # .values turns a column into a plain numpy array of numbers

        vol30 = interpolate_one_day(one_day["dte"].values,
                                    one_day["atm_iv"].values)

        if np.isnan(vol30):
            days_without_30 = days_without_30 + 1

        results.append({"date": date, "vol30": vol30})

    # a list of dictionaries becomes a table: one row per day
    series = pd.DataFrame(results)

    # remove days where 30 days could not be bracketed (dropna drops rows with nan)
    series = series.dropna().copy()

    # the percentile needs the days in order, oldest first.
    # reset_index(drop=True) renumbers the rows 0, 1, 2, ... after sorting and
    # dropping, so that row number i really is the i-th day (the loop relies on it).
    series = series.sort_values("date").reset_index(drop=True)

    series = add_stress_indicator(series)

    # index=False: do not write pandas' row numbers into the file
    series.to_csv(OUT_FILE, index=False)

    print()
    print("saved", len(series), "days to", OUT_FILE)
    print("from", series["date"].min(), "to", series["date"].max())
    print("days dropped because 30 days could not be bracketed:", days_without_30)
    print()

    v = series["vol30"]

    print("summary:")
    print("  lowest  ", round(v.min(), 4))
    print("  median  ", round(v.median(), 4))
    print("  highest ", round(v.max(), 4))
    print()

    print("the 10 most volatile days:")

    # sort highest first (ascending=False) and keep the first 10 rows
    top = series.sort_values("vol30", ascending=False).head(10)

    # iterrows() gives one row at a time; _ is the row label, which we do not need
    for _, row in top.iterrows():
        print("  ", row["date"], round(row["vol30"], 4))
    print()

    # only days that HAVE a threshold can be judged (not the first 252)
    judged = series[series["threshold"].notna()].copy()

    print("days with a threshold:", len(judged))
    # the mean of a True/False column is the share of True (True counts as 1)
    print("share of those days in stress (should be near 20%):",
          round(judged["stress"].mean() * 100, 1), "%")
    print()

    # the same share for each year; with a trailing percentile it should stay
    # near 20% in every year, unlike the fixed level
    judged["year"] = judged["date"].str[:4]

    print("share of days in stress, per year:")
    print("   year   trailing 80th pct   fixed", FIXED_LEVEL)

    # one small table per year; mean() of a True/False column is the share of True
    for year, one_year in judged.groupby("year"):
        trailing = one_year["stress"].mean() * 100
        fixed = one_year["stress_fixed"].mean() * 100
        print("  ", year, "   ", round(trailing, 1), "%        ", round(fixed, 1), "%")


main()
