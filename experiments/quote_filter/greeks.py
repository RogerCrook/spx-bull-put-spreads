"""
THE GREEKS

What this file is for:
    Your strategy is steered by DELTA: the delta of the whole position is
    watched against a band around its value at entry (about 0.27 in the data;
    exits at entry delta - 0.10 and + 0.10, thesis section 2.3).
    So we need delta for every option.

    We also work out gamma, vega and theta. They cost almost nothing extra
    (they all reuse the same d1) and you need them later to explain WHERE
    your profit and loss came from.

What each one means:

    DELTA  how much the option price moves when the index moves 1 point.
           A put has negative delta: the index goes up, the put loses value.

    GAMMA  how much DELTA moves when the index moves 1 point.
           High gamma means your delta changes fast, which is the risk
           your 15-day rule is there to control.

    VEGA   how much the option price moves when volatility rises 1 point.
           In a crash, most of your loss is vega, not delta.

    THETA  how much the option price changes per day just from time passing.
           For an option you SOLD, theta is your profit engine.

To check it works, run:   python greeks.py
"""

import numpy as np
from scipy.stats import norm


def all_greeks(F, K, tau, sigma, D, is_call, S):
    """
    Work out delta, gamma, vega and theta.

      F       forward price
      K       strike
      tau     time to expiry in years
      sigma   implied volatility (from volatility.py)
      D       discount factor
      is_call True for a call, False for a put
      S       the spot index level

    Returns a dictionary with one entry per greek.
    """

    # ---- the two standard terms, same as in the pricing formula --------

    v = sigma * np.sqrt(tau)                     # sigma * sqrt(tau)

    # avoid dividing by zero. np.where(condition, a, b): element by element,
    # take a where the condition is True and b where it is False.
    v = np.where(v < 0.000000000001, 0.000000000001, v)

    d1 = (np.log(F / K) + 0.5 * v * v) / v

    d2 = d1 - v

    # the bell curve height at d1, which several greeks need
    # (the normal density phi(d1) = exp(-d1^2 / 2) / sqrt(2 pi); np.pi is 3.14159...)
    bell = np.exp(-0.5 * d1 * d1) / np.sqrt(2.0 * np.pi)

    # ---- delta ----------------------------------------------------------
    # First with respect to the FORWARD. For a call this is N(d1),
    # for a put it is N(d1) - 1, which is always negative.

    # norm.cdf is N(), the normal distribution function, from scipy.
    # np.where picks N(d1) for the calls and N(d1) - 1 for the puts.
    delta_vs_forward = D * np.where(is_call, norm.cdf(d1), norm.cdf(d1) - 1.0)

    # But we want delta with respect to SPOT, because that is what moves.
    # The forward and the spot move together: F = S * (something fixed),
    # so a 1 point move in S moves F by F/S points. Chain rule:

    delta = delta_vs_forward * (F / S)

    # ---- gamma ----------------------------------------------------------
    # How fast delta changes. Same chain rule, applied twice.

    gamma_vs_forward = D * bell / (F * v)

    gamma = gamma_vs_forward * (F / S) * (F / S)

    # ---- vega -----------------------------------------------------------
    # Sensitivity to volatility. Divided by 100 so it reads
    # "price change per 1 percentage point of volatility".

    vega = D * F * bell * np.sqrt(tau) / 100.0

    # ---- theta ----------------------------------------------------------
    # Sensitivity to time. Negative, because an option loses value as
    # expiry approaches. Divided by 365 so it reads "per calendar day".

    theta = -D * F * bell * sigma / (2.0 * np.sqrt(tau)) / 365.0

    return {
        "delta": delta,
        "gamma": gamma,
        "vega": vega,
        "theta": theta,
    }


def spread_delta(short_leg_delta, long_leg_delta, how_many_spreads=2):
    """
    The delta of your whole position.

    You SELL the higher strike put and BUY the lower strike put.
    Selling flips the sign, so a sold put contributes POSITIVE delta.

      short_leg_delta : delta of the put you sold   (a negative number)
      long_leg_delta  : delta of the put you bought (a negative number)

    Example: sold put delta -0.21, bought put delta -0.07
             one spread  = -(-0.21) + (-0.07) = +0.14
             two spreads = +0.28
    """

    one_spread = -short_leg_delta + long_leg_delta

    return how_many_spreads * one_spread


# ----------------------------------------------------------------------
# Only runs if you type:  python greeks.py
# ----------------------------------------------------------------------

if __name__ == "__main__":

    print("TEST 1 - check delta against a simple experiment.")
    print()
    print("  Delta should equal: how much the price moves when spot moves")
    print("  1 point. So let us just move spot by a tiny amount and see.")
    print()

    from volatility import black76_price

    S = 5500.0
    F = 5525.0
    K = 5400.0
    tau = 29 / 365.0
    sigma = 0.18
    D = 0.9956

    g = all_greeks(F, K, tau, sigma, D, False, S)       # False = a put

    # now nudge spot up by a small amount and reprice
    nudge = 0.01
    F_up = F * (S + nudge) / S                          # forward moves in proportion

    price_now = black76_price(F, K, tau, sigma, D, False)
    price_up = black76_price(F_up, K, tau, sigma, D, False)

    delta_by_experiment = (price_up - price_now) / nudge

    print("   delta from the formula    ", round(float(g["delta"]), 6))
    print("   delta from the experiment ", round(float(delta_by_experiment), 6))
    print()

    print("TEST 2 - a put spread like the one your strategy trades.")
    print()

    K_short = 5400.0                                    # the put you sell
    K_long = 5100.0                                     # the put you buy

    short = all_greeks(F, K_short, tau, 0.175, D, False, S)
    long = all_greeks(F, K_long, tau, 0.230, D, False, S)

    print("   sold   put at", K_short, " delta =", round(float(short["delta"]), 4))
    print("   bought put at", K_long, "  delta =", round(float(long["delta"]), 4))
    print()

    one = spread_delta(short["delta"], long["delta"], 1)
    two = spread_delta(short["delta"], long["delta"], 2)

    print("   one spread  delta =", round(float(one), 4))
    print("   two spreads delta =", round(float(two), 4), " <- your starting position")
