"""
CHECK: how much more credit a longer maturity brings (rem:credit-size)
(reproduction inventory, rows 9 and 10; review_log T38)

What this file is for:
    Part 1, ILLUSTRATIVE (no data): the Black-76 credit of two spreads at the
      strategy's strikes K = F exp(-k sigma sqrt(tau)), k = 1 and 2.3, at one
      flat volatility, for the reference inputs F = 4000, sigma = 18%, r = 4%,
      at 30, 60 and 90 days; next to it the first-order rule
      c = 2 D F kappa sigma sqrt(tau), with kappa = the integral of N(-u) from 1 to 2.3.
    Part 2, MEASURED: the credits actually received in the reported base-case
      runs, grouped by the maturity rule at entry (target, recovery, cap).

    Rewritten 2026-10-27 in the style of Code/s03_rates.py; same calculations
    and the same printout as before (old version in
    old_versions/checks_before_style_2026-10-27/).

Data: results/trades_base_mid_c8c9q.csv and results/trades_base_cross_c8c9q.csv.
Read-only: writes nothing. Takes a second.
Run it from the main folder:   python checks/credit_by_maturity.py
"""

import math                                  # plain maths: log, exp, sqrt, erf
import pandas as pd                          # pandas works with tables


# ----------------------------------------------------------------------
# Part 1: illustrative Black-76 numbers
# ----------------------------------------------------------------------

def N(x):
    """The standard normal distribution function, written with math.erf (no scipy needed)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def put(F, K, tau, sigma, D):
    """Black-76 put price, eq:b76-put: D * (K N(-d0) - F N(-d1))."""
    d1 = math.log(F / K) / (sigma * math.sqrt(tau)) + 0.5 * sigma * math.sqrt(tau)
    d0 = d1 - sigma * math.sqrt(tau)
    return D * (K * N(-d0) - F * N(-d1))


def kappa():
    """The integral of N(-u) from 1 to 2.3, by Simpson's rule with 1000 steps."""
    a, b, n = 1.0, 2.3, 1000                 # from a to b in n steps (n must be even for Simpson)
    h = (b - a) / n                          # the width of one step
    total = N(-a) + N(-b)                    # the two end points count once
    for i in range(1, n):
        if i % 2 == 1:                       # % 2 is the remainder after dividing by 2: odd steps ...
            weight = 4                       # ... count 4 times,
        else:
            weight = 2                       # even steps twice
        total = total + weight * N(-(a + i * h))
    return total * h / 3.0


F, SIGMA, R_RATE = 4000.0, 0.18, 0.04        # the reference inputs
KAPPA = kappa()

print("Part 1 (illustrative, F 4000, sigma 18%, r 4%, flat vol)")
print("kappa = %.5f" % KAPPA)

credits = {}                                 # days -> credit of two spreads

for days in (30, 60, 90):
    tau = days / 365.0                       # as a fraction of a year
    D = math.exp(-R_RATE * tau)              # discount factor
    sd = SIGMA * math.sqrt(tau)              # one standard deviation, sigma * sqrt(tau)
    k_short = F * math.exp(-1.0 * sd)        # the sold strike, one standard deviation below F
    k_long = F * math.exp(-2.3 * sd)         # the bought strike, 2.3 below
    credit = 2 * (put(F, k_short, tau, SIGMA, D) - put(F, k_long, tau, SIGMA, D))   # two spreads
    first_order = 2 * D * F * KAPPA * sd     # the first-order rule
    credits[days] = credit
    print("%2d days: strikes %.1f / %.1f, credit %.2f points, first order %.2f"
          % (days, k_short, k_long, credit, first_order))

print("ratio 60/30 = %.3f (sqrt 2 = %.3f), 90/30 = %.3f (sqrt 3 = %.3f)"
      % (credits[60] / credits[30], math.sqrt(2), credits[90] / credits[30], math.sqrt(3)))
print("extra credit 90 vs 30 days: %.2f points" % (credits[90] - credits[30]))


# ----------------------------------------------------------------------
# Part 2: measured credits by maturity rule
# ----------------------------------------------------------------------

print()
print("Part 2 (measured, base case)")

for tag in ("base_mid_c8c9q", "base_cross_c8c9q"):

    trades = pd.read_csv("results/trades_" + tag + ".csv")

    # the credit as a share of the forward at entry, in basis points (1 bp = 0.01%),
    # so that cycles of 2012 (index about 1,300) and 2026 (about 7,800) can be compared
    trades["credit_bp"] = 10000.0 * trades["credit"] / trades["forward0"]

    # one standard deviation of the cycle, sigma * sqrt(tau), with the ATM vol at entry
    trades["sd"] = trades["atm_iv0"] * (trades["dte0"] / 365.0) ** 0.5

    # credit per unit of forward and of sigma * sqrt(tau): by the first-order rule
    # this is about 2 D kappa = 0.159, whatever the maturity and the volatility
    trades["credit_per_sd"] = trades["credit"] / (trades["forward0"] * trades["sd"])

    print(tag, "| cycles:", len(trades))

    for rule in ("target", "recovery", "cap"):
        group = trades[trades["maturity_rule"] == rule]     # True/False per cycle; keep this rule's cycles
        print("  %-8s n %3d | median dte0 %5.1f | mean credit %6.2f points "
              "| mean credit %5.1f bp of F | mean deficit at entry %6.2f points"
              % (rule, len(group), group["dte0"].median(), group["credit"].mean(),
                 group["credit_bp"].mean(), group["deficit_at_entry"].mean()))
        print("  %-8s mean ATM vol at entry %5.2f%% | mean sigma*sqrt(tau) %.4f "
              "| mean credit/(F*sigma*sqrt(tau)) %.4f"
              % ("", 100 * group["atm_iv0"].mean(), group["sd"].mean(), group["credit_per_sd"].mean()))
