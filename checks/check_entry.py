"""
CHECK: the realised entry delta of sec:realised-entry-delta
(reproduction inventory, rows 6 and 29)

What this file is for:
    Code/s10_entry_delta.py opens, on every trading day at 10:00, the
    two-spread position of def:entry on the expiry closest to 30 days and
    stores its entry delta Delta_0 in results/entry_delta.csv.

    Part (1) computes from that file every number the thesis prints in
    sec:realised-entry-delta: the statistics of tab:entry-delta-stats, the
    histogram of tab:entry-delta-hist, the days to expiry, how far the
    snapped strikes are from their targets, the annual means, the distances
    to an absolute band [0.20, 0.40], and the volatility gap between the legs.

    Part (2) rebuilds the entry of 12 random days from scratch with its own
    code (choose the expiry, compute the target strikes, snap to the nearest
    listed put, read the two deltas) and compares with the stored Delta_0.

    Rewritten 2026-10-27 in the style of Code/s03_rates.py; same calculations
    and the same printout as before (old version in
    old_versions/checks_before_style_2026-10-27/).

Data: results/entry_delta.csv; for part (2) Data/05_atm_vol.csv and 12 months of Data/04_greeks/.
Read-only: writes nothing. Takes a few minutes (part 2 reads 12 Greeks months).
Run it from the main folder:   python checks/check_entry.py
"""

import numpy as np                           # numpy does maths on lists of numbers
import pandas as pd                          # pandas works with tables
from scipy.stats import norm                 # norm.cdf(x) is N(x), the normal distribution function


entries = pd.read_csv("results/entry_delta.csv")     # one row per trading day
delta0 = entries["entry_delta"]                      # the entry delta of two spreads


# ---- (1) the published figures ----------------------------------------------------

print("(1) published figures")

print("days %d | mean %.4f | sd %.4f | min %.4f | max %.4f" % (
    len(delta0), delta0.mean(), delta0.std(), delta0.min(), delta0.max()))

# .quantile(q): the value a share q of the days lie below
print("quantiles 1/5/25/50/75/95/99%%: %s" % [round(delta0.quantile(q), 4) for q in [.01, .05, .25, .5, .75, .95, .99]])

# the stored put deltas are negative; the minus sign shows them as positive numbers
print("mean delta sold %.4f | bought (abs) %.4f" % (-entries["delta_short"].mean(), -entries["delta_long"].mean()))

print("mean iv ATM / sold / bought: %.2f%% / %.2f%% / %.2f%%" % (
    100 * entries["atm_iv"].mean(), 100 * entries["iv_short"].mean(), 100 * entries["iv_long"].mean()))

print("flat-vol value 2*(N(2.3)-N(1)) = %.4f" % (2 * (norm.cdf(2.3) - norm.cdf(1))))

# the histogram: pd.cut puts each day into one of the bins [0.20, 0.22), [0.22, 0.24), ...
# (right=False: the left edge belongs to the bin, the right edge does not);
# value_counts counts the days per bin, sort_index puts the bins in order
bins = [0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.32, 0.34]
histogram = pd.cut(delta0, bins, right=False).value_counts().sort_index()
print("histogram:", histogram.to_dict())

print("dte range %d-%d | exactly 30 on %.1f%% | roots %s" % (
    entries["dte"].min(), entries["dte"].max(), 100 * (entries["dte"] == 30).mean(),
    entries["root"].value_counts().to_dict()))

# how far each snapped strike is from its target, in per cent (.abs(): either side)
short_gap = (entries["strike_short"] / entries["target_short"] - 1).abs() * 100
long_gap = (entries["strike_long"] / entries["target_long"] - 1).abs() * 100
# long_gap > 2 gives True/False per day; .loc[..., "date"] lists the dates where it is True
print("snap short max %.2f%% | long > 2%% on %d days: %s" % (
    short_gap.max(), int((long_gap > 2).sum()), list(entries.loc[long_gap > 2, "date"])))

# the mean entry delta of each year: groupby puts the days of each year
# ("2012-01-03" -> "2012") together, .mean() averages them
yearly = entries.groupby(entries["date"].str[:4])["entry_delta"].mean()
print("annual means %.3f - %.3f" % (yearly.min(), yearly.max()))

# an absolute band [0.20, 0.40]: the distance from the entry delta to each edge
to_profit = delta0 - 0.20
to_loss = 0.40 - delta0
print("absolute band: to 0.20 median %.3f range %.3f-%.3f, < 0.05 on %.1f%% | to 0.40 median %.3f range %.3f-%.3f"
      % (to_profit.median(), to_profit.min(), to_profit.max(), 100 * (to_profit < 0.05).mean(),
         to_loss.median(), to_loss.min(), to_loss.max()))

print("vol gap bought - sold: %.1f points" % (100 * (entries["iv_long"] - entries["iv_short"]).mean()))


# ---- (2) 12 random days rebuilt from scratch ----------------------------------------

print("\n(2) 12 random days rebuilt from scratch")

atm = pd.read_csv("Data/05_atm_vol.csv")

# the 10:00 snapshot of every day, slices with an ATM volatility only
at_10 = (atm["quote_datetime"].str[11:] == "10:00:00") & atm["atm_iv"].notna()
atm = atm[at_10].copy()                      # .copy(): our own table, safe to add columns
atm["date"] = atm["quote_datetime"].str[:10]
atm["dist"] = (atm["dte"] - 30).abs()        # how far from 30 days

# per day the expiry closest to 30 days: sort so that the best one comes first
# (closest, then root name, then days), and keep the first row of each date
atm = atm.sort_values(["date", "dist", "root", "dte"]).drop_duplicates("date")

# 12 random days; random_state=7 fixes the random choice, so the run can be repeated
days = entries.sample(12, random_state=7)["date"].tolist()

worst = 0.0                                  # largest difference to the stored Delta_0

for day in sorted(days):

    chosen = atm[atm["date"] == day].iloc[0]     # the expiry chosen that day

    # one standard deviation as a factor: exp(-sigma * sqrt(tau))
    one_sd = np.exp(-chosen["atm_iv"] * np.sqrt(chosen["dte"] / 365.0))
    target_short = chosen["forward"] * one_sd            # K = F exp(-1 sigma sqrt(tau))
    target_long = chosen["forward"] * one_sd ** 2.3      # K = F exp(-2.3 sigma sqrt(tau))

    # the puts of that slice with a delta, read from the Greeks month in pieces
    pieces = []
    for chunk in pd.read_csv("Data/04_greeks/spx_" + day[:7] + ".csv",
                             usecols=["quote_datetime", "root", "expiration", "strike", "option_type", "delta"],
                             chunksize=2_000_000):
        here = ((chunk["quote_datetime"] == chosen["quote_datetime"]) & (chunk["root"] == chosen["root"])
                & (chunk["expiration"] == chosen["expiration"]) & (chunk["option_type"] == "P")
                & chunk["delta"].notna())
        pieces.append(chunk[here])
    puts = pd.concat(pieces)

    # the listed put nearest each target: np.argmin gives the position of the
    # smallest distance, .iloc reads the row at that position
    short_leg = puts.iloc[np.argmin(np.abs(puts["strike"].values - target_short))]
    long_leg = puts.iloc[np.argmin(np.abs(puts["strike"].values - target_long))]

    mine = 2 * (-short_leg["delta"] + long_leg["delta"])          # two spreads, eq:posdelta
    stored = entries.loc[entries["date"] == day, "entry_delta"].iloc[0]
    worst = max(worst, abs(mine - stored))

    print("  %s %s dte %d: mine %.6f | stored %.6f" % (day, chosen["root"], chosen["dte"], mine, stored))

print("max |difference| %.2e" % worst)
