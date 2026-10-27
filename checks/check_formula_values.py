"""
CHECK: the thesis numbers that come from the formulas alone, not from the data
(reproduction inventory, rows 1 and 21)

What this file is for:
    Three results in the thesis use only the Black-76 formulas with chosen
    example inputs. No option data is read.

      (a) rem:atm-otm: below the forward, an in-the-money call reacts more to
          an error in the forward than the out-of-the-money put at the same
          strike, by the factor N(d1) / N(-d1). The thesis gives it at
          x = -0.03 and x = -0.05 (tau = 30/365, sigma = 18%).

      (b) tab:validation, "round-trip inversion": price an option with
          sigma = 0.18, then let our bisection find sigma back from that
          price. The difference should be tiny.

      (c) tab:validation, "delta against a finite difference": move the spot
          by 0.01, price the option again, and compare the price change per
          point with our delta formula. This tests the factor F/S.

    (b) and (c) call the project's own functions in Code/, so they test the
    code that made the thesis numbers. Their example inputs are chosen here,
    because the methodology report did not record its inputs, so the numbers
    printed can differ from the ones now in the thesis.

Read-only: reads no data and writes nothing. Takes about a second.
Run it from the main folder:   python checks/check_formula_values.py
"""

import sys                                   # sys holds Python's list of folders it imports from
sys.path.insert(0, "Code")                   # add Code/ to that list, so the imports below find our files

import numpy as np                           # numpy does maths on lists of numbers
from scipy.stats import norm                 # norm.cdf(x) is N(x), the normal distribution function

import s05_volatility as volatility          # our Black-76 price and our implied volatility
import s06_greeks as greeks                  # our delta formula


# ----------------------------------------------------------------------
# (a) rem:atm-otm: the factor N(d1) / N(-d1)
# ----------------------------------------------------------------------

tau = 30 / 365                               # 30 days, as a fraction of a year
sigma = 0.18                                 # 18% volatility

one_sd = sigma * np.sqrt(tau)                # sigma * sqrt(tau): one standard deviation in log terms

print("(a) rem:atm-otm   tau = 30/365, sigma = 18%")

for x in [-0.03, -0.05]:                     # the two log-moneyness values the remark uses

    # x = log(K/F), so log(F/K) = -x. Then d1 as in the thesis:
    # d1 = log(F/K) / (sigma sqrt(tau)) + (sigma sqrt(tau)) / 2
    d1 = -x / one_sd + 0.5 * one_sd

    call_exposure = norm.cdf(d1)             # |dC/dF| / D for the call = N(d1)
    put_exposure = norm.cdf(-d1)             # |dP/dF| / D for the put  = N(-d1)

    factor = call_exposure / put_exposure    # how many times more the call is exposed

    print("   x = %.2f   d1 = %.4f   factor = %.3f" % (x, d1, factor))

print()


# ----------------------------------------------------------------------
# Example inputs for (b) and (c), chosen here
# ----------------------------------------------------------------------

S = 3990.0                                   # spot index level
F = 4000.0                                   # forward, a little above spot (as with r > q)
r = 0.04                                     # 4% interest rate
D = np.exp(-r * tau)                         # discount factor D = exp(-r tau)

print("example inputs for (b) and (c): S = %.0f, F = %.0f, tau = 30/365, r = 4%%, D = %.6f" % (S, F, D))
print()


# ----------------------------------------------------------------------
# (b) round trip: price with sigma = 0.18, then invert
# ----------------------------------------------------------------------

print("(b) round trip: price at sigma = 0.18, then find sigma back by bisection")

largest_error = 0.0                          # we keep the biggest error we see

for K in [3600.0, 3800.0, 3900.0, 4000.0, 4100.0, 4200.0]:     # a few strikes around the forward

    for is_call in [False, True]:            # first the put, then the call

        # the price our own Black-76 function gives at sigma = 0.18
        price = volatility.black76_price(F, K, tau, 0.18, D, is_call)

        # our own bisection, asked which sigma gives back that price
        found = volatility.implied_volatility(price, F, K, tau, D, is_call)

        # float() turns numpy's answer into a plain Python number
        error = abs(float(found) - 0.18)

        if error > largest_error:            # remember it if it is the biggest so far
            largest_error = error

        kind = "call" if is_call else "put "   # text for the printout
        print("   K = %.0f %s   price %9.4f   sigma found %.15f   error %.1e" % (K, kind, float(price), float(found), error))

print("   largest error: %.1e" % largest_error)
print()


# ----------------------------------------------------------------------
# (c) delta against a finite difference
# ----------------------------------------------------------------------
# The forward moves with the spot: F = S * (F/S), and F/S stays fixed when
# only the spot moves. So moving the spot by 0.01 moves the forward by
# 0.01 * F/S. We reprice the option there and divide the price change by 0.01.

print("(c) delta of a put: our formula against a finite difference (spot moved by 0.01)")

step = 0.01                                  # the spot move, in index points

for K in [3800.0, 3900.0, 4000.0]:           # three put strikes

    # delta from our formula (Code/s06_greeks.py); it returns a dictionary,
    # and ["delta"] takes the delta out of it
    formula = float(greeks.all_greeks(F, K, tau, sigma, D, False, S)["delta"])

    price_now = float(volatility.black76_price(F, K, tau, sigma, D, False))   # put price now

    S_up = S + step                          # the spot one step higher
    F_up = F * S_up / S                      # the forward moves in proportion

    price_up = float(volatility.black76_price(F_up, K, tau, sigma, D, False))  # put price after the move

    one_sided = (price_up - price_now) / step    # price change per point: the finite-difference delta

    # a two-sided difference (one step down as well) is more accurate;
    # printed to show how much of the gap is just the one-sided method
    S_down = S - step
    F_down = F * S_down / S
    price_down = float(volatility.black76_price(F_down, K, tau, sigma, D, False))
    two_sided = (price_up - price_down) / (2 * step)

    print("   K = %.0f   formula %.6f   one-sided %.6f (diff %.1e)   two-sided %.6f (diff %.1e)" % (
        K, formula, one_sided, abs(one_sided - formula), two_sided, abs(two_sided - formula)))

    # with the factor 1 instead of F/S the formula would be off by this much:
    without_factor = formula * S / F
    print("              without the factor F/S the formula would give %.6f" % without_factor)
