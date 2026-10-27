"""
CHECK: the stored Greeks, recomputed, and the Greek formulas against finite differences
(reproduction inventory, row 30; review_log T18)

What this file is for:
    (1) Stage 2 (Code/s07_stage2_greeks.py, using Code/s06_greeks.py) stores,
        for every quote, its delta, gamma, vega and theta. This file computes
        them again from the stored inputs (forward, strike, days, implied
        volatility, discount factor, spot) with its own code, on every quote
        of five days from 2012 to 2026, and prints the largest difference.
        sec:realised-entry-delta cites the delta result.
    (2) It checks each Greek formula against a finite difference of the
        Black-76 price, on 2,000 random puts (illustrative inputs).

    It does not import Code/s06_greeks.py: the formulas are written again
    here (propositions prop:greeks-fwd and prop:chainrule, with vega per
    volatility point and theta per calendar day as in rem:scaling), so that
    a mistake in that file would show up as a difference.

    Rewritten 2026-10-27 in the style of Code/s03_rates.py; same calculations
    and the same printout as before (old version in
    old_versions/checks_before_style_2026-10-27/).

Data: five months of Data/04_greeks/ (only the five days are kept).
Read-only: writes nothing. Takes a few minutes.
Run it from the main folder:   python checks/check_greeks.py
"""

import numpy as np                           # numpy does maths on lists of numbers
import pandas as pd                          # pandas works with tables
from scipy.stats import norm                 # norm.cdf is N(x), norm.pdf the normal density


DAYS = ["2012-01-03", "2016-01-04", "2020-03-16", "2021-06-08", "2026-07-28"]


def price(F, K, tau, sigma, D, is_call):
    """Black-76 price (eq:b76-call, eq:b76-put), for whole arrays at once."""
    v = sigma * np.sqrt(tau)                 # sigma * sqrt(tau)
    d1 = np.log(F / K) / v + 0.5 * v
    d0 = d1 - v
    call_price = D * (F * norm.cdf(d1) - K * norm.cdf(d0))
    put_price = D * (K * norm.cdf(-d0) - F * norm.cdf(-d1))
    return np.where(is_call, call_price, put_price)          # np.where: call price where is_call, else put price


def greeks(F, K, tau, sigma, D, is_call, S):
    """Delta and gamma with respect to spot, vega per vol point, theta per calendar day."""
    v = sigma * np.sqrt(tau)
    d1 = np.log(F / K) / v + 0.5 * v
    density = norm.pdf(d1)                   # phi(d1)

    # delta with respect to the forward: D N(d1) for a call, D (N(d1) - 1) for a put
    delta_forward = D * (norm.cdf(d1) - np.where(is_call, 0.0, 1.0))
    gamma_forward = D * density / (F * v)

    return {
        "delta": delta_forward * F / S,                              # chain rule: times F/S
        "gamma": gamma_forward * (F / S) ** 2,                       # chain rule twice
        "vega": D * F * density * np.sqrt(tau) / 100,                # per volatility point
        "theta": -D * F * density * sigma / (2 * np.sqrt(tau)) / 365,  # per calendar day, D held fixed
    }


# ---- (1) stored against recomputed --------------------------------------------------

GREEKS = ["delta", "gamma", "vega", "theta"]
worst = {}                                   # greek -> largest absolute difference
worst_relative = {}                          # greek -> largest relative difference
for greek in GREEKS:
    worst[greek] = 0.0
    worst_relative[greek] = 0.0
n = 0                                        # quotes compared

for day in DAYS:

    pieces = []
    # read the month in pieces of 2 million rows and keep the rows of this day
    for chunk in pd.read_csv("Data/04_greeks/spx_" + day[:7] + ".csv", chunksize=2_000_000):
        pieces.append(chunk[chunk["quote_datetime"].str.startswith(day)])   # .str.startswith: the date part matches

    stored = pd.concat(pieces).dropna(subset=["iv"])        # only the quotes with a volatility

    is_call = (stored["option_type"] == "C").values
    tau = np.maximum(stored["dte"].values / 365.0, 1 / 365.0)   # days / 365, at least one day (def:tau-conv)

    mine = greeks(stored["forward"].values, stored["strike"].values, tau, stored["iv"].values,
                  stored["D"].values, is_call, stored["spot"].values)

    for greek in GREEKS:
        difference = np.abs(mine[greek] - stored[greek].values)
        worst[greek] = max(worst[greek], difference.max())

        # relative difference, only where the value is not tiny (above 0.001)
        large = np.abs(stored[greek].values) > 1e-3
        if large.any():
            relative = difference[large] / np.abs(stored[greek].values[large])
            worst_relative[greek] = max(worst_relative[greek], relative.max())

    n += len(stored)
    print("done", day, len(stored), flush=True)  # flush=True: show the line at once

print("\nrows with an iv:", n)
for greek in GREEKS:
    print("  %-5s max |stored - recomputed| %.2e | max relative (where |value| > 1e-3) %.2e"
          % (greek, worst[greek], worst_relative[greek]))


# ---- (2) finite differences on 2,000 random puts -----------------------------------

generator = np.random.default_rng(0)         # random numbers, seed 0, so the run can be repeated
m = 2000

# random inputs over the range the strategy meets (illustrative)
F = generator.uniform(1300, 7800, m)                         # forward between 1,300 and 7,800
S = F / generator.uniform(0.997, 1.004, m)                   # spot close to the forward
K = F * np.exp(-generator.uniform(0, 2.5, m) * 0.2 * np.sqrt(30 / 365))   # puts from ATM to 2.5 SD out
tau = generator.uniform(10, 90, m) / 365                     # 10 to 90 days
sigma = generator.uniform(0.10, 0.60, m)                     # 10% to 60% volatility
D = np.exp(-0.04 * tau)                                      # 4% interest
is_call = np.zeros(m, bool)                                  # all puts

formula = greeks(F, K, tau, sigma, D, is_call, S)

step_S = S * 1e-4                            # a small move of the spot


def price_at_spot(new_S):
    """The put price after the spot moves to new_S, the forward moving in proportion."""
    return price(F * new_S / S, K, tau, sigma, D, is_call)


# two-sided differences: (price up - price down) / (2 * step), and the second difference for gamma
fd_delta = (price_at_spot(S + step_S) - price_at_spot(S - step_S)) / (2 * step_S)
fd_gamma = (price_at_spot(S + step_S) - 2 * price_at_spot(S) + price_at_spot(S - step_S)) / step_S ** 2
fd_vega = (price(F, K, tau, sigma + 1e-5, D, is_call) - price(F, K, tau, sigma - 1e-5, D, is_call)) / 2e-5 / 100
step_tau = 1e-5                              # theta = -dP/dtau with D held fixed, per calendar day
fd_theta = -(price(F, K, tau + step_tau, sigma, D, is_call) - price(F, K, tau - step_tau, sigma, D, is_call)) / (2 * step_tau) / 365

print("\nfinite-difference check, %d random puts (10-90 d, vol 10-60%%, ATM to 2.5 SD out):" % m)
for greek, fd in [("delta", fd_delta), ("gamma", fd_gamma), ("vega", fd_vega), ("theta", fd_theta)]:
    relative = np.abs(fd - formula[greek]) / np.maximum(np.abs(formula[greek]), 1e-12)
    print("  %-5s max relative difference %.1e" % (greek, relative.max()))
