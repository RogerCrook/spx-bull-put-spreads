"""
IMPLIED VOLATILITY

What this file is for:
    The market gives us a PRICE for each option. Your strategy is written in
    terms of VOLATILITY and DELTA. So we have to go backwards: find the
    volatility that would make the pricing formula produce the price we see.

    That number is called the implied volatility.

The pricing formula (Black-76, written on the forward F):

    call = D * ( F * N(d1) - K * N(d2) )
    put  = D * ( K * N(-d2) - F * N(-d1) )

    where   d1 = ( log(F/K) + 0.5 * sigma^2 * tau ) / ( sigma * sqrt(tau) )
            d2 = d1 - sigma * sqrt(tau)
            N() is the normal distribution function

    F     the forward price          (from forward.py)
    K     the strike
    tau   time to expiry, in years
    sigma the volatility             <-- this is what we want to find
    D     the discount factor        (from rates.py)

To check it works, run:   python volatility.py
"""

import numpy as np
from scipy.stats import norm                # norm.cdf is the N() in the formula


def black76_price(F, K, tau, sigma, D, is_call):
    """
    Work out what an option SHOULD cost, given a volatility.

    All the inputs can be single numbers or whole columns of numbers.
    """

    # sigma * sqrt(tau) appears several times, so work it out once
    v = sigma * np.sqrt(tau)

    # if v is zero we would divide by zero, so nudge it to a tiny number.
    # np.where(condition, a, b) goes element by element: where the condition is
    # True it takes a, where it is False it takes b. Here: where v is tiny, use
    # 1e-12, otherwise keep v.
    v = np.where(v < 0.000000000001, 0.000000000001, v)

    d1 = (np.log(F / K) + 0.5 * v * v) / v      # the first term in the formula

    d2 = d1 - v                                  # the second term

    call_price = D * (F * norm.cdf(d1) - K * norm.cdf(d2))

    put_price = D * (K * norm.cdf(-d2) - F * norm.cdf(-d1))

    # pick the call price where is_call is True, the put price where it is False
    return np.where(is_call, call_price, put_price)


def implied_volatility(market_price, F, K, tau, D, is_call, steps=60):
    """
    Find the volatility that makes black76_price match the market price.

    HOW IT WORKS - "bisection", or squeezing in on the answer:

      The key fact is that a higher volatility ALWAYS means a higher option
      price. So the price only ever goes up as sigma goes up.

      That lets us play a guessing game:
        - we know the answer is somewhere between 0.1% and 500%
        - try the middle
        - if the price we get is too LOW, the true sigma must be HIGHER,
          so throw away the bottom half
        - if too HIGH, throw away the top half
        - repeat

      Each round halves the range. After 60 rounds the range is tiny.

    Returns nan where no answer exists (a bad quote).
    """

    # make sure everything is a numpy array of the same shape, so that
    # single numbers work alongside whole columns
    market_price, F, K, tau, D, is_call = np.broadcast_arrays(
        market_price, F, K, tau, D, is_call)

    # a copy of the prices as decimal numbers (dtype=float), so that later
    # calculations never treat them as whole numbers
    market_price = np.array(market_price, dtype=float)

    # np.full(shape, value) makes an array of that shape filled with one value:
    # one "low" and one "high" guess for every option at once.
    # .shape is the size of the array, e.g. (26805,) for 26,805 options.
    low = np.full(market_price.shape, 0.001)        # 0.1% volatility, the bottom guess

    high = np.full(market_price.shape, 5.0)         # 500% volatility, the top guess

    # ---- check the price is even possible ----------------------------
    # An option can never be worth less than its intrinsic value, and never
    # more than the forward (for a call) or the strike (for a put).
    # Prices outside that range mean a broken quote.

    intrinsic = D * np.where(is_call,
                             np.maximum(F - K, 0.0),
                             np.maximum(K - F, 0.0))

    most_it_can_be = D * np.where(is_call, F, K)

    # & means "and", element by element: True only where BOTH are True
    is_sensible = (market_price > intrinsic) & (market_price < most_it_can_be)

    # ---- the squeezing loop -------------------------------------------

    # Every line in this loop works on ALL options at once (whole arrays), so
    # 60 rounds of the loop do the squeezing for every option in the file.
    for step in range(steps):

        middle = (low + high) / 2.0                 # try the middle of the range

        price_here = black76_price(F, K, tau, middle, D, is_call)

        too_cheap = price_here < market_price       # our guess gave too low a price

        # where our guess was too cheap, the real sigma is higher,
        # so move the bottom of the range up to the middle
        low = np.where(too_cheap, middle, low)

        # otherwise move the top of the range down to the middle
        high = np.where(too_cheap, high, middle)

    answer = (low + high) / 2.0                     # the middle of the final tiny range

    # put nan wherever the price was not sensible
    answer = np.where(is_sensible, answer, np.nan)

    return answer


# ----------------------------------------------------------------------
# Only runs if you type:  python volatility.py
# ----------------------------------------------------------------------

if __name__ == "__main__":

    print("TEST 1 - price an option, then work backwards and see if we get")
    print("         the same volatility we started with.")
    print()

    F = 5525.0                  # forward price
    K = 5400.0                  # strike
    tau = 29 / 365.0            # 29 days, as a fraction of a year
    D = 0.9956                  # discount factor
    true_sigma = 0.18           # the volatility we will try to recover

    price = black76_price(F, K, tau, true_sigma, D, False)      # False = it is a put

    print("   we started with sigma =", true_sigma)
    print("   that gives a put price of", round(float(price), 4))

    found = implied_volatility(price, F, K, tau, D, False)

    print("   working backwards we get  ", round(float(found), 8))
    print("   error:", abs(float(found) - true_sigma))
    print()

    print("TEST 2 - does it work across many different strikes?")
    print()

    strikes = np.array([4500.0, 5000.0, 5400.0, 5525.0, 5700.0])

    for K in strikes:
        price = black76_price(F, K, tau, 0.18, D, False)
        found = implied_volatility(price, F, K, tau, D, False)
        print("   K =", K, "  price =", round(float(price), 3),
              "  sigma found =", round(float(found), 6))
