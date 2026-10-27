"""
CHECK: how much the one-sided fitting window moves the ATM volatility (rem:atm-band)
(reproduction inventory, row 20)

What this file is for:
    rem:atm-band says the fitting window |x| < 0.05 is cut on the call side at
    about x = +0.03 (calls were cleaned only up to K/S = 1.03), and that "in a
    simulation against an assumed smile shape the bias is about 0.01
    volatility points, against about 0.03 from quote noise". The simulation
    behind those numbers was lost and its inputs were not recorded. This file
    redoes it with every input stated and taken from one real slice:
    8 June 2021, 10:00, SPXW expiring 7 July 2021 (the calm smile of fig:smile).

    The steps:
      1. The "true" smile: a cubic sigma(x) = a + b x + c x^2 + d x^3, fitted
         to that slice's out-of-the-money quotes over a wider range, |x| < 0.15.
         Its value at x = 0, a, is the true ATM volatility. (A pure parabola
         would give no bias at all, so the cubic term is what matters.)
      2. Two sets of strikes: the quotes the fit of def:atm really uses in
         that slice (from x = -0.05 up to the highest call, about +0.03), and
         a symmetric set, the same plus the put strikes mirrored to the call
         side where the data has no calls (up to +0.05).
      3. Bias: fit the parabola of def:atm to the true smile on each set of
         strikes, without noise, and compare its value at 0 with a.
      4. Noise: add a random error to every volatility, as large as half the
         bid-ask spread of that slice turned into volatility points (median of
         half spread / vega), refit, 10,000 times. The spread of the results
         is the noise.

Data: Data/04_greeks/spx_2021-06.csv (only the one slice is kept).
Read-only: writes nothing. Takes under a minute.
Run it from the main folder:   python checks/check_atm_bias.py
"""

import numpy as np                           # numpy does maths on lists of numbers
import pandas as pd                          # pandas works with tables


FILE = "Data/04_greeks/spx_2021-06.csv"
TIME, ROOT, EXPIRY = "2021-06-08 10:00:00", "SPXW", "2021-07-07"
BAND = 0.05                                  # the window of def:atm
WIDE = 0.15                                  # the wider range used for the "true" smile
DRAWS = 10_000                               # how many noisy repetitions


# ---- 1. read the slice ----------------------------------------------------

pieces = []
for chunk in pd.read_csv(FILE, chunksize=2_000_000):         # the month, 2 million rows at a time
    here = (chunk["quote_datetime"] == TIME) & (chunk["root"] == ROOT) & (chunk["expiration"] == EXPIRY)
    pieces.append(chunk[here])               # keep only our slice
one_slice = pd.concat(pieces)                # glue the kept rows together

F = one_slice["forward"].iloc[0]             # the stored forward (same on every row)
one_slice = one_slice[one_slice["iv"].notna()].copy()        # quotes with a volatility; .copy(): a separate table
one_slice["x"] = np.log(one_slice["strike"] / F)             # log-moneyness x = log(K/F)

# out-of-the-money quotes: puts below the forward, calls at or above it
otm = one_slice[((one_slice["option_type"] == "P") & (one_slice["x"] < 0)) |
                ((one_slice["option_type"] == "C") & (one_slice["x"] >= 0))]


# ---- 2. the "true" smile: a cubic over |x| < 0.15 ------------------------

wide = otm[otm["x"].abs() < WIDE]            # .abs(): without the sign

# np.polyfit(x, y, 3) finds the cubic that fits the points best (least squares);
# it returns the coefficients from the highest power down: [d, c, b, a]
true_coefficients = np.polyfit(wide["x"], wide["iv"], 3)
true_atm = np.polyval(true_coefficients, 0.0)                # the true smile at x = 0, i.e. a

print("slice %s %s %s: F = %.2f, %d out-of-the-money quotes with |x| < %.2f" % (TIME, ROOT, EXPIRY, F, len(wide), WIDE))
print("true smile (cubic): a = %.4f, b = %.4f, c = %.4f, d = %.4f" % (
    true_coefficients[3], true_coefficients[2], true_coefficients[1], true_coefficients[0]))
print("true ATM volatility: %.4f%%" % (100 * true_atm))
print()


# ---- 3. the two sets of strikes ------------------------------------------

in_window = otm[otm["x"].abs() < BAND]       # the quotes def:atm uses in this slice
right_edge = in_window["x"].max()            # how far the call side really reaches

x_real = np.sort(in_window["x"].values)      # the x of those quotes, smallest first (.values: plain numbers)

# the symmetric set: add, on the call side, the mirror image (-x) of every put
# strike whose mirror lies beyond the last real call and inside the window
mirrored = []
for x in x_real:
    if x < 0 and right_edge < -x < BAND:     # a put whose mirror falls in the empty part
        mirrored.append(-x)
x_symmetric = np.sort(np.concatenate([x_real, np.array(mirrored)]))   # np.concatenate glues two lists of numbers

print("real window: x from %.3f to %.3f (%d strikes); symmetric: %.3f to %.3f (%d strikes)" % (
    x_real.min(), x_real.max(), len(x_real), x_symmetric.min(), x_symmetric.max(), len(x_symmetric)))


# ---- 4. the noise level: half the bid-ask spread, in volatility ----------

# vega is stored per volatility point (divided by 100), so half spread / vega
# is the volatility change, in points, that moves the price by half the spread
half_spread_points = ((in_window["ask"] - in_window["bid"]) / 2) / in_window["vega"]
noise = half_spread_points.median() / 100    # back to decimals (0.01 = 1 point)
print("noise per quote (median half spread over vega): %.3f volatility points" % (100 * noise))
print()


# ---- 5. bias without noise, and spread with noise -------------------------

generator = np.random.default_rng(1)         # random numbers, seed 1, so the run can be repeated

for label, x in [("real window", x_real), ("symmetric window", x_symmetric)]:

    true_vols = np.polyval(true_coefficients, x)             # the true smile at these strikes

    fitted = np.polyfit(x, true_vols, 2)                     # the parabola of def:atm, no noise
    bias = np.polyval(fitted, 0.0) - true_atm                # its value at 0 minus the truth

    estimates = []                                           # one ATM estimate per noisy repetition
    for _ in range(DRAWS):
        noisy = true_vols + generator.normal(0.0, noise, len(x))   # add an error to every volatility
        estimates.append(np.polyval(np.polyfit(x, noisy, 2), 0.0))
    estimates = np.array(estimates)

    print("%-17s bias without noise %+.4f points | with noise: mean error %+.4f points, standard deviation %.4f points" % (
        label, 100 * bias, 100 * (estimates.mean() - true_atm), 100 * estimates.std()))
