"""
Rough synthetic market, part 1 of 2: a made-up market that is less perfect.

What this file is for
---------------------
The mutation tests (step 5) found four rules of stages 2 and 2b that the first
made-up market (make_market.py) cannot see, because there put-call parity holds
exactly at every strike and every smile is exactly quadratic:
    - the forward uses the 8 strikes nearest K0 (D8),
    - the ATM fit uses the band |x| < 0.05 (D11),
    - the fit uses the out-of-the-money calls for x >= 0 as well as the puts (D11),
    - the fit needs at least 3 points (D11).
This market has one slice for each:
    "noisy"   SPX 2031-04-02 (30 days): the call prices carry a parity error that
              differs by strike near the money, so the median of the 8 nearest
              strikes differs from the median of 7 or 9 (here by 0.25 points).
    "cubic"   SPX 2031-04-18 (46 days): the smile has a cubic term, so the fit
              changes with the band and with leaving out the calls (by about
              2e-4 and 9e-4, the check's tolerance is 1e-5).
    "three"   SPX 2031-05-07 (65 days): strikes 100 points apart, so exactly 3
              out-of-the-money quotes lie in the band: it must get an ATM vol.
    "two"     SPX 2031-05-21 (79 days): the same, but the 4100 call costs 10 points
              more than D F, the most any call can be worth, so it has no
              volatility and only 2 quotes are left: it must get none. (A first
              try with 2,500 points failed: at 79 days a vol of about 72% gives
              that price.)
Everything else is as in make_market.py: one ordinary trading day (3 March 2031,
index 4,000), T-bill yields, dividend yield 1.5%, Black-76 prices, bid and ask
symmetric around the price.

The truth file has one row per raw row, with the true F, D and sigma, and the
parity error put into the call. check_rough.py works out the expected forward and
ATM vol from these with the thesis's rules.

How to run (from the main folder; seconds, writes about 10 MB):
    python validation/automatic/synthetic/make_rough_market.py
Then run the pipeline on it with the folder set from outside (PowerShell):
    $env:CHECK_SYNTHETIC_FOLDER = "$env:TEMP" + "/masterarbeit_synthetic_rough"
    python validation/automatic/synthetic/run_pipeline.py
and compare:
    python validation/automatic/synthetic/check_rough.py
"""

import csv              # writes CSV files row by row
import math             # exp, log, sqrt, erf
import os               # folders and paths
import tempfile         # the computer's temporary folder
from datetime import date              # dates, to count calendar days


# ---------------------------------------------------------------------------
# Settings: the known parameters
# ---------------------------------------------------------------------------

WORK_FOLDER = os.path.join(tempfile.gettempdir(), "masterarbeit_synthetic_rough")

DAY = "2031-03-03"
S = 4000.0
DIVIDEND_YIELD = 0.015                          # q, continuous

# T-bill yields in per cent (the day before the sample must not be used).
YIELD_SERIES = ["DGS1MO", "DGS3MO", "DGS6MO", "DGS1"]
YIELD_DAYS = [30, 91, 182, 365]
YIELDS = {
    "2031-02-28": [3.90, 4.00, 4.10, 4.20],
    "2031-03-03": [4.00, 4.20, 4.40, 4.60],
}

# The four slices. smile: sigma(x) = a + b x + c x^2 + d * (x cut to [-0.1, 0.1])^3.
# The cut keeps the cubic term small far from the money (sigma stays below 5).
SLICES = [
    {"name": "noisy", "expiration": "2031-04-02", "a": 0.18, "b": -0.30, "c": 0.50, "d": 0.0, "step": 5.0},
    {"name": "cubic", "expiration": "2031-04-18", "a": 0.20, "b": -0.30, "c": 0.50, "d": 60.0, "step": 5.0},
    {"name": "three", "expiration": "2031-05-07", "a": 0.19, "b": -0.30, "c": 0.50, "d": 0.0, "step": 100.0},
    {"name": "two",   "expiration": "2031-05-21", "a": 0.19, "b": -0.30, "c": 0.50, "d": 0.0, "step": 100.0},
]
ROOT = "SPX"

# The parity errors of the "noisy" slice (index points), on the strikes K0 - 20 ...
# K0 + 20, K0 the strike nearest the forward. Sorted, the 8 nearest give the median
# (0.5 + 1) / 2 = 0.75, whichever of K0 - 20 and K0 + 20 is taken (both +4); all 9
# give 1, the 7 nearest 0.5.
NOISE_OFFSETS = [-20.0, -15.0, -10.0, -5.0, 0.0, 5.0, 10.0, 15.0, 20.0]
NOISE_ERRORS = [4.0, -3.0, -2.0, -1.0, 0.5, 1.0, 2.0, 3.0, 4.0]

# The call of the "two" slice with an impossible price: D F + 10 points, above the
# no-arbitrage upper bound D F of a call (eq:noarb-call, prop:impvol), so it has no volatility.
IMPOSSIBLE_CALL = {"name": "two", "strike": 4100.0, "above_bound": 10.0}

# Strikes: puts from 1,200 (the "step" apart near the money, 25 apart below 3,600
# for the 5-point slices), calls only from 3,600 to 4,400 (stage 1 keeps
# K/S 0.97 to 1.03 of them).
LOWEST_STRIKE = 1200.0
NARROW_FROM = 3600.0
HIGHEST_STRIKE = 4400.0

HALF_WIDTH_FIXED = 0.05             # half the bid-ask width: 0.05 + 1% of the price
HALF_WIDTH_SHARE = 0.01


# ---------------------------------------------------------------------------
# The model (as in make_market.py)
# ---------------------------------------------------------------------------

def normal_cdf(x):
    """N(x), the standard normal distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black76_price(F, K, tau, sigma, D, is_put):
    """Black-76: call = D [F N(d1) - K N(d0)], put = D [K N(-d0) - F N(-d1)]."""
    root_tau = math.sqrt(tau)
    d1 = math.log(F / K) / (sigma * root_tau) + sigma * root_tau / 2.0
    d0 = d1 - sigma * root_tau
    if is_put:
        return D * (K * normal_cdf(-d0) - F * normal_cdf(-d1))
    return D * (F * normal_cdf(d1) - K * normal_cdf(d0))


def rate_for(days_to_expiry):
    """
    The continuous rate for one maturity (sec:rates): each yield converted with
    its own maturity, r = log(1 + y tau) / tau, then a straight line between 30,
    91, 182 and 365 days (all maturities here lie between 30 and 91 days).
    """
    continuous = []
    for number in range(4):
        tau = YIELD_DAYS[number] / 365
        simple = YIELDS[DAY][number] / 100                 # per cent -> fraction
        continuous.append(math.log(1 + simple * tau) / tau)
    if days_to_expiry <= YIELD_DAYS[0]:
        return continuous[0]
    for number in range(3):
        low_days = YIELD_DAYS[number]
        high_days = YIELD_DAYS[number + 1]
        if low_days <= days_to_expiry <= high_days:
            weight = (days_to_expiry - low_days) / (high_days - low_days)
            return continuous[number] + weight * (continuous[number + 1] - continuous[number])
    raise ValueError("no rate for " + str(days_to_expiry) + " days")


def smile(slice_info, x):
    """sigma(x) = a + b x + c x^2 + d * (x cut to [-0.1, 0.1])^3."""
    cut = x
    if cut < -0.1:
        cut = -0.1
    if cut > 0.1:
        cut = 0.1
    return (slice_info["a"] + slice_info["b"] * x + slice_info["c"] * x * x
            + slice_info["d"] * cut * cut * cut)


def snapshot_times():
    """Every snapshot of the day: 09:45 to 16:15, every 15 minutes."""
    times = []
    minutes = 9 * 60 + 45
    while minutes <= 16 * 60 + 15:
        hours = minutes // 60                      # // divides and drops the remainder
        rest = minutes % 60                        # % is the remainder
        times.append(DAY + " " + str(hours).zfill(2) + ":" + str(rest).zfill(2) + ":00")
        minutes = minutes + 15
    return times


def strike_list(step):
    """The strikes of one slice: 25 apart below 3,600 (if step < 25), then step apart."""
    strikes = []
    strike = LOWEST_STRIKE
    while strike <= HIGHEST_STRIKE:
        strikes.append(strike)
        if strike < NARROW_FROM and step < 25.0:
            strike = strike + 25.0
        else:
            strike = strike + step
    return strikes


def parity_errors(F, strikes):
    """
    The parity error of each strike of the "noisy" slice: NOISE_ERRORS on the
    strikes K0 - 20 ... K0 + 20, zero elsewhere. K0 = the strike nearest F.
    """
    nearest = strikes[0]
    for strike in strikes:
        if abs(strike - F) < abs(nearest - F):
            nearest = strike
    errors = {}
    for strike in strikes:
        errors[strike] = 0.0
    for number in range(len(NOISE_OFFSETS)):
        errors[nearest + NOISE_OFFSETS[number]] = NOISE_ERRORS[number]
    return errors


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

RAW_COLUMNS = ["underlying_symbol", "quote_datetime", "root", "expiration", "strike", "option_type",
               "open", "high", "low", "close", "trade_volume", "bid_size", "bid", "ask_size", "ask",
               "underlying_bid", "underlying_ask"]
TRUTH_COLUMNS = ["quote_datetime", "slice", "root", "expiration", "strike", "option_type", "days",
                 "F", "D", "sigma", "parity_error", "price", "has_volatility"]


def main():
    if os.path.exists(WORK_FOLDER):
        raise ValueError(WORK_FOLDER + " exists already: delete it first")

    # The official close and the four yield files, laid out like the real ones.
    folder = os.path.join(WORK_FOLDER, "Data", "07_index_close")
    os.makedirs(folder)
    with open(os.path.join(folder, "GSPC_daily.csv"), "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Date", "Open", "High", "Low", "Close", "Volume"])
        writer.writerow([DAY, repr(S), repr(S), repr(S), repr(S), "0"])
    folder = os.path.join(WORK_FOLDER, "Data", "03_treasury_bills")
    os.makedirs(folder)
    for number in range(4):
        series = YIELD_SERIES[number]
        with open(os.path.join(folder, series + ".csv"), "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["observation_date", series])
            for day in sorted(YIELDS):
                writer.writerow([day, repr(YIELDS[day][number])])

    # The raw quotes of the day and the truth file.
    folder = os.path.join(WORK_FOLDER, "Data", "01_raw_options")
    os.makedirs(folder)
    raw_path = os.path.join(folder, "UnderlyingOptionsIntervals_900sec_" + DAY + ".csv")
    rows = 0
    with open(raw_path, "w", newline="") as raw_file, \
            open(os.path.join(WORK_FOLDER, "truth.csv"), "w", newline="") as truth_file:
        raw = csv.writer(raw_file)
        truth = csv.writer(truth_file)
        raw.writerow(RAW_COLUMNS)
        truth.writerow(TRUTH_COLUMNS)
        for time in snapshot_times():
            for slice_info in SLICES:
                days = (date.fromisoformat(slice_info["expiration"]) - date.fromisoformat(DAY)).days
                tau = days / 365
                rate = rate_for(days)
                F = S * math.exp((rate - DIVIDEND_YIELD) * tau)        # prop:forward
                D = math.exp(-rate * tau)                              # def:discount
                strikes = strike_list(slice_info["step"])
                errors = {}
                if slice_info["name"] == "noisy":
                    errors = parity_errors(F, strikes)

                for strike in strikes:
                    x = math.log(strike / F)
                    sigma = smile(slice_info, x)
                    put_price = black76_price(F, strike, tau, sigma, D, True)
                    for option_type in ["P", "C"]:
                        if option_type == "C" and strike < NARROW_FROM:
                            continue                               # calls only near the money
                        error = 0.0
                        has_volatility = True
                        if option_type == "P":
                            price = put_price
                        else:
                            # call = put + D (F + error - K): parity with the error added
                            error = errors.get(strike, 0.0)        # .get: 0 if the strike has none
                            price = put_price + D * (F + error - strike)
                            if (slice_info["name"] == IMPOSSIBLE_CALL["name"]
                                    and strike == IMPOSSIBLE_CALL["strike"]):
                                price = D * F + IMPOSSIBLE_CALL["above_bound"]
                                has_volatility = False
                        half_width = HALF_WIDTH_FIXED + HALF_WIDTH_SHARE * price
                        bid = price - half_width
                        ask = price + half_width
                        if bid < 0:
                            bid = 0.0                              # no negative bids
                        raw.writerow(["^SPX", time, ROOT, slice_info["expiration"], repr(strike), option_type,
                                      "0.0000", "0.0000", "0.0000", "0.0000", "0", "100", repr(bid),
                                      "100", repr(ask), repr(S - 0.5), repr(S + 0.5)])
                        truth.writerow([time, slice_info["name"], ROOT, slice_info["expiration"], repr(strike),
                                        option_type, days, repr(F), repr(D), repr(sigma), repr(error),
                                        repr((bid + ask) / 2), has_volatility])
                        rows = rows + 1
    print("wrote " + str(rows) + " raw rows to " + WORK_FOLDER)


main()
