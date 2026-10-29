"""
CHECK: the 30-day volatility and the stress indicator of sec:stress
(reproduction inventory, row 11)

What this file is for:
    Code/s09_vol_series.py builds, for every trading day, the 30-day at-the-money
    volatility (from the 15:45 snapshot) and the stress threshold: the 80th
    percentile of the 252 previous daily values (def:stress). It stores them in
    Data/06_vol30.csv. This file builds both again with its own code, compares
    them with the stored ones, and also recomputes the stress flag recorded on
    every trade of the reported base-case run at mid (results/trades_base_mid.csv;
    until 2026-10-28 the first base-case run, made before the stock-close rule).

    The 30-day volatility of a day: the ATM volatilities of the expiries around
    30 days are turned into total variance sigma^2 * tau, interpolated in a
    straight line at 30 days, and turned back into a volatility. Where SPX and
    SPXW list the same number of days, their two values are averaged.

    It prints the share of days in stress (sec:stress: 19.7%) and, added on
    2026-10-27, the three example days of sec:stress and CLAUDE.md section 6.

    Rewritten 2026-10-27 in the style of Code/s03_rates.py; same calculations
    and the same printout as before, plus the three example days at the end
    (old version in a folder old_versions/,
    removed on 2026-10-29).

Data: Data/05_atm_vol.csv, Data/06_vol30.csv, results/trades_base_mid.csv.
Read-only: writes nothing. Takes about a minute.
Run it from the main folder:   python checks/check_vol30.py
"""

import numpy as np                           # numpy does maths on lists of numbers
import pandas as pd                          # pandas works with tables


atm = pd.read_csv("Data/05_atm_vol.csv")    # one ATM volatility per snapshot, root and expiry
atm = atm[atm["atm_iv"].notna()]             # keep the slices that have one
atm["date"] = atm["quote_datetime"].str[:10] # "2020-02-24 15:45:00" -> "2020-02-24"


def vol30_of(rows):
    """The 30-day volatility from the ATM volatilities of one snapshot (NaN if 30 days is not bracketed)."""

    # one value per number of days: groupby puts SPX and SPXW with the same
    # days together and .mean() averages them; as_index=False keeps "dte" as a column
    per_dte = rows.groupby("dte", as_index=False)["atm_iv"].mean().sort_values("dte")

    days = per_dte["dte"].values             # .values: the plain numbers
    vols = per_dte["atm_iv"].values

    if len(days) == 0 or days.min() > 30 or days.max() < 30:
        return np.nan                        # no expiry on one side of 30 days

    total_variance = vols ** 2 * days / 365.0                # sigma^2 * tau of each expiry

    # np.interp draws straight lines between the points and reads off the value at 30 days
    at_30 = np.interp(30 / 365.0, days / 365.0, total_variance)

    return float(np.sqrt(at_30 / (30 / 365.0)))              # back to a volatility


# ---- (1) the daily series at 15:45 -------------------------------------------------

at_1545 = atm[atm["quote_datetime"].str[11:] == "15:45:00"]  # the 15:45 snapshot of every day

daily = {}                                   # date -> 30-day volatility
for date, rows in at_1545.groupby("date"):   # one day at a time
    value = vol30_of(rows)
    if not np.isnan(value):                  # skip days where 30 days is not bracketed
        daily[date] = value

dates = sorted(daily)                        # dates as text sort in time order
values = np.array([daily[date] for date in dates])          # the volatilities in that order

# the threshold of each day: the 80th percentile of the 252 days strictly before it
thresholds = [np.nan] * len(values)          # no threshold for the first 252 days
for i in range(252, len(values)):
    thresholds[i] = np.percentile(values[i - 252:i], 80)    # values[i-252:i]: the 252 days before day i

mine = pd.DataFrame({"vol30": values, "threshold": thresholds}, index=dates)
mine["stress"] = mine["vol30"] > mine["threshold"]

# compare with the stored file: join puts the two tables side by side by date;
# rsuffix="_stored" renames the stored columns (vol30 -> vol30_stored, ...)
stored = pd.read_csv("Data/06_vol30.csv").set_index("date")
# how="outer" keeps every date that is in either table (a date missing in
# one of them gets empty values there)
both = mine.join(stored, rsuffix="_stored", how="outer")

# .dropna(subset=[...]) drops the dates where either value is empty, and
# .shape[0] is the number of rows that are left; .fillna(False) counts an
# empty stress flag as "no stress", so that two empty flags compare as equal
print("days: mine %d | stored %d | in both %d" % (
    len(mine), len(stored), int(both.dropna(subset=["vol30", "vol30_stored"]).shape[0])))
print("max |vol30 difference| %.2e | max |threshold difference| %.2e | stress flags differing: %d"
      % ((both["vol30"] - both["vol30_stored"]).abs().max(),
         (both["threshold"] - both["threshold_stored"]).abs().max(),
         int((both["stress"].fillna(False) != both["stress_stored"].fillna(False)).sum())))

judged = mine[mine["threshold"].notna()]     # the days that have a threshold
print("days with a threshold: %d | share in stress %.1f%%" % (len(judged), 100 * judged["stress"].mean()))

all_dates = sorted(atm["date"].unique())     # every trading day in the data
missing = sorted(set(all_dates) - set(mine.index))          # the days without a 15:45 value
print("trading days without a 15:45 value: %d" % len(missing))

# the last snapshot of each day ("13:15" on early-close days, which have no 15:45)
last_time = atm.groupby("date")["quote_datetime"].max().str[11:16]
print("   their last snapshot:", last_time.reindex(missing).value_counts().to_dict())
print("   examples:", missing[:8])


# ---- (2) the stress flag recorded on the trades (reported base-case run at mid) ----

trades = pd.read_csv("results/trades_base_mid.csv")

# the slices of each snapshot, looked up by the snapshot time
by_time = {}
for time, rows in atm.groupby("quote_datetime"):
    by_time[time] = rows

worst_vol = 0.0                              # largest difference in the 30-day vol at entry
worst_threshold = 0.0                        # largest difference in the threshold
flips = 0                                    # trades whose flag comes out differently
n = 0                                        # trades that could be compared

for _, trade in trades.iterrows():           # one trade at a time

    entry = str(trade["entry_time"])[:19]    # "2020-02-24 10:00:00"

    if entry in by_time:
        vol = vol30_of(by_time[entry])       # the 30-day vol at the entry snapshot
    else:
        vol = np.nan

    # the position of the entry date in the sorted list of dates: the 252
    # dates before it form the window (np.searchsorted finds that position)
    position = np.searchsorted(np.array(dates), entry[:10], side="left")
    if position >= 252:
        threshold = np.percentile(values[position - 252:position], 80)
    else:
        threshold = np.nan

    if not np.isnan(vol) and not np.isnan(trade["vol30_entry"]):
        worst_vol = max(worst_vol, abs(vol - trade["vol30_entry"]))
    if not np.isnan(threshold) and not np.isnan(trade["stress_threshold"]):
        worst_threshold = max(worst_threshold, abs(threshold - trade["stress_threshold"]))

    if not (np.isnan(vol) or np.isnan(threshold)) and str(trade["stress"]) in ("True", "False"):
        mine_flag = vol > threshold
        stored_flag = str(trade["stress"]) == "True"
        if mine_flag != stored_flag:
            flips = flips + 1
        n = n + 1

print("\ntrades (base, mid): %d | max |vol30_entry diff| %.2e | max |threshold diff| %.2e | flag differs on %d of %d"
      % (len(trades), worst_vol, worst_threshold, flips, n))

has_flag = trades["stress"].astype(str).isin(["True", "False"])     # trades with a flag
in_stress = (trades["stress"].astype(str) == "True").sum()
print("stress share at entry: %.1f%% of trades with a flag" % (100 * in_stress / max(1, has_flag.sum())))


# ---- (3) the example days of sec:stress (added 2026-10-27) -------------------------

print()
for date in ["2017-06-01", "2020-02-24", "2020-02-27"]:
    row = mine.loc[date]                     # .loc[date]: the row of that date
    print("%s: threshold %.2f%%, 30-day volatility %.2f%%, stress %s" % (
        date, 100 * row["threshold"], 100 * row["vol30"], row["stress"]))
