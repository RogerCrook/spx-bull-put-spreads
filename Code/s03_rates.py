"""
THE RISK-FREE RATE CURVE

What this file is for:
    Your options need an interest rate r, so we can work out how much a
    payment at expiry is worth today.

    We have four files from FRED with rates at 1 month, 3 months, 6 months
    and 1 year. Your options expire anywhere from 4 to 100 days, so we have
    to fill in the gaps between those four points.

To check it works, run:   python Code/s03_rates.py
"""

import numpy as np                  # numpy does maths on lists of numbers
import pandas as pd                 # pandas works with tables


# Where the four downloaded files live
FOLDER = "Data/03_treasury_bills"

# Each FRED file, and how many days that rate is for
FILES = {
    "DGS1MO": 30,                   # 1 month  = 30 days
    "DGS3MO": 91,                   # 3 months = 91 days
    "DGS6MO": 182,                  # 6 months = 182 days
    "DGS1": 365,                    # 1 year   = 365 days
}


def load_rates():
    """Read the four files and put them into one table."""

    all_columns = {}                                # empty box to collect the four columns

    for file_name in FILES:                         # go through the four files one at a time

        days = FILES[file_name]                     # how many days this file is for (30, 91, ...)

        path = FOLDER + "/" + file_name + ".csv"    # e.g. "Data/03_treasury_bills/DGS3MO.csv"

        # na_values="." tells pandas that a dot means "no data"
        # (FRED writes a dot on days the market was closed)
        table = pd.read_csv(path, na_values=".")

        # the dates are text, turn them into real dates
        table["observation_date"] = pd.to_datetime(table["observation_date"])

        # make the date the row label, so we can look rows up by date later
        table = table.set_index("observation_date")

        # FRED writes 4.24 when it means 4.24 percent, so divide by 100
        rate = table[file_name] / 100.0

        # ---- convert to the kind of interest Black-Scholes expects -------
        # FRED's number means:  1 dollar grows to  1 * (1 + r * tau)
        # Black-Scholes wants:  1 dollar grows to  1 * exp(r * tau)
        # so we solve  exp(x * tau) = 1 + r * tau  for x
        tau = days / 365.0                          # the maturity, as a fraction of a year
        rate = np.log(1.0 + rate * tau) / tau       # the converted rate

        all_columns[days] = rate                    # store it under its number of days

    rates = pd.DataFrame(all_columns)               # glue the four columns into one table

    rates = rates.sort_index()                      # put the oldest date first

    # A closed market means "no new number today", not "the rate disappeared",
    # so copy the previous day's value into the gap. ffill = forward fill.
    rates = rates.ffill()

    rates = rates.dropna()                          # drop rows still empty at the very start

    return rates                                    # hand the finished table back


def rate_for(rates, date, days):
    """
    Look up the interest rate for one date and one number of days.

    Example:  rate_for(rates, pd.Timestamp("2024-08-01"), 28)  ->  0.0523
    """

    # Find the last row whose date is on or before our date.
    # (If our date is a holiday, this gives us the day before.)
    position = rates.index.searchsorted(date, side="right") - 1

    if position < 0:                                # our date is before the table starts
        raise ValueError("no rate data for " + str(date))

    row = rates.iloc[position]                      # the four rates on that day

    known_days = np.array([30, 91, 182, 365])       # the maturities we have rates for

    known_rates = row.values                        # the four rates themselves

    # np.interp draws a straight line between the points we know
    # and reads off the value at the number of days we want.
    answer = np.interp(days, known_days, known_rates)

    return float(answer)                            # turn it into a plain number


def discount_factor(rates, date, days):
    """
    How much a payment at expiry is worth today.

    Example: 0.9968 means a dollar paid in 28 days is worth 99.68 cents now.
    """

    r = rate_for(rates, date, days)                 # get the interest rate

    tau = days / 365.0                              # the time, as a fraction of a year

    return float(np.exp(-r * tau))                  # D = exp(-r * tau)


# ----------------------------------------------------------------------
# Everything below only runs if you type:  python Code/s03_rates.py
# It does not run when another file imports this one.
# ----------------------------------------------------------------------

if __name__ == "__main__":

    rates = load_rates()                            # load the four files

    print("loaded", len(rates), "days")             # how many rows we got
    print("from", rates.index[0].date(), "to", rates.index[-1].date())
    print()

    print("What the table looks like (first 3 rows):")
    print(rates.head(3))
    print()

    print("Rates for a 28-day option on a few dates:")

    for text_date in ["2012-09-28", "2020-03-16", "2024-08-01"]:

        date = pd.Timestamp(text_date)              # turn the text into a real date

        if date < rates.index[0]:                   # skip dates we have no data for
            continue
        if date > rates.index[-1]:
            continue

        r = rate_for(rates, date, 28)               # the interest rate
        D = discount_factor(rates, date, 28)        # the discount factor

        print("  ", date.date(), "  r =", round(r * 100, 3), "%   D =", round(D, 6))
