"""
Synthetic market, part 1 of 3: make a market whose parameters are known.

What this file is for
---------------------
Method 2 of the validation: quotes are made from a model with known parameters and
run through the whole pipeline (stage 1, stage 2, the ATM fit), which must give the
parameters back (test specification D1-D12). This script writes the made-up raw
data, in the layout of the real Cboe files, into WORK_FOLDER (outside the project),
and a truth file with the answer for every row.

The model (all choices, made so that each statement can fail visibly):
  - three trading days in March 2031, the third an early close (last snapshot
    13:15). Snapshots every 15 minutes from 09:45 to 16:15 (13:15).
  - the index S is constant within a day (4000, 4040, 3980). The recorded index
    quote is S -/+ 0.5, except at the last snapshot, where it is nonsense (S + 100)
    and the official close (S) is in the index close file (D2).
  - T-bill yields: their own values on day 1 and day 3, none on day 2, so day 2
    must forward-fill day 1 (D6).
  - dividend yield q = 1.5% for SPX and SPXQ, 1.0% for SPXW, so a forward that
    mixed the two roots would be visibly wrong (D3).
  - prices: Black-76 with F = S exp((r - q) tau), D = exp(-r tau), r from the yields
    as sec:rates prescribes, tau = calendar days / 365, sigma = the expiry's smile
    a + b x + c x^2 in x = log(K / F) (flat for one expiry). bid and ask lie
    symmetric around the price, so mid = price.
  - traps: expiries 3 and 101 days away (dropped) and 4 and 100 (kept), strikes on
    the K/S limits 0.30, 1.08, 0.97, 1.03 on day 1, a binary root (BSZ), a quote
    with ask = bid, and an SPXQ expiry with only two call-put pairs, which must get
    no forward (D8).

How to run (from the main folder; writes about 60 MB, seconds):
    python validation/automatic/synthetic/make_market.py
Then run_pipeline.py runs the project's code on it, and check.py compares.
"""

import csv              # writes CSV files row by row
import math             # exp, log, sqrt, erf
import os               # folders and paths
import tempfile         # the computer's temporary folder
from datetime import date              # dates, to count calendar days


# ---------------------------------------------------------------------------
# Settings: the known parameters
# ---------------------------------------------------------------------------

WORK_FOLDER = os.path.join(tempfile.gettempdir(), "masterarbeit_synthetic")

# The trading days, the index level S and whether the day closes early.
DAYS = [
    {"day": "2031-03-03", "S": 4000.0, "early_close": False},
    {"day": "2031-03-04", "S": 4040.0, "early_close": False},
    {"day": "2031-03-05", "S": 3980.0, "early_close": True},
]

# T-bill yields in per cent, by date (None = no value that day, to be forward-filled).
# The four maturities in calendar days (choice: 30, 91, 182, 365, as for the real data).
YIELD_SERIES = ["DGS1MO", "DGS3MO", "DGS6MO", "DGS1"]
YIELD_DAYS = [30, 91, 182, 365]
YIELDS = {
    "2031-02-28": [3.90, 4.00, 4.10, 4.20],     # before the sample: must not be used
    "2031-03-03": [4.00, 4.20, 4.40, 4.60],
    "2031-03-04": None,                         # a day without yields (forward-fill)
    "2031-03-05": [4.10, 4.30, 4.50, 4.70],
}

DIVIDEND_YIELD = {"SPX": 0.015, "SPXQ": 0.015, "SPXW": 0.010}   # q, continuous

# The expiries: root, date, and the smile sigma(x) = a + b x + c x^2.
EXPIRIES = [
    {"root": "SPXW", "expiration": "2031-03-06", "a": 0.20, "b": -0.30, "c": 0.50},  # 3 days on day 1: dropped
    {"root": "SPXW", "expiration": "2031-03-07", "a": 0.20, "b": -0.30, "c": 0.50},  # 4 days on day 1: kept
    {"root": "SPX",  "expiration": "2031-04-02", "a": 0.18, "b": 0.00, "c": 0.00},   # flat smile (D12)
    {"root": "SPX",  "expiration": "2031-04-18", "a": 0.20, "b": -0.30, "c": 0.50},  # SPX and SPXW on
    {"root": "SPXW", "expiration": "2031-04-18", "a": 0.21, "b": -0.25, "c": 0.40},  # the same date (D3)
    {"root": "SPXQ", "expiration": "2031-05-07", "a": 0.20, "b": -0.30, "c": 0.50},  # only 2 pairs (D8)
    {"root": "SPX",  "expiration": "2031-06-11", "a": 0.22, "b": -0.35, "c": 0.60},  # 100 days on day 1: kept
    {"root": "SPX",  "expiration": "2031-06-12", "a": 0.22, "b": -0.35, "c": 0.60},  # 101 days on day 1: dropped
    {"root": "BSZ",  "expiration": "2031-04-18", "a": 0.20, "b": -0.30, "c": 0.50},  # binary root: dropped
]
FEW_PAIRS_ROOT = "SPXQ"          # this root lists calls at only two strikes
FEW_PAIRS_STRIKES = [3995.0, 4005.0]

# Strikes (index points): every 25 below 3600, every 5 from 3600 to 4400.
# Puts at all of them, calls only from 3600 to 4400.
WIDE_STRIKES_FROM = 1125.0
NARROW_STRIKES_FROM = 3600.0
STRIKES_TO = 4400.0

# The quote with ask = bid (must be dropped): this put, at this snapshot.
FLAT_QUOTE = {"time": "2031-03-03 10:00:00", "root": "SPX", "expiration": "2031-04-02", "strike": 3500.0}

# Half the bid-ask width: 0.05 + 1% of the price (choice), so mid = price.
HALF_WIDTH_FIXED = 0.05
HALF_WIDTH_SHARE = 0.01

# The filter limits as the thesis states them (sec:cleaning), for the truth file.
GOOD_ROOTS = ["SPX", "SPXW", "SPXQ"]
MIN_DAYS = 4
MAX_DAYS = 100
PUT_LIMITS = (0.30, 1.08)
CALL_LIMITS = (0.97, 1.03)
MIN_BID = 0.025


# ---------------------------------------------------------------------------
# The model
# ---------------------------------------------------------------------------

def normal_cdf(x):
    """N(x), the standard normal distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black76_price(F, K, tau, sigma, D, is_put):
    """Black-76: call = D [F N(d1) - K N(d0)], put = D [K N(-d0) - F N(-d1)] (eq:b76-call, eq:b76-put)."""
    root_tau = math.sqrt(tau)
    d1 = math.log(F / K) / (sigma * root_tau) + sigma * root_tau / 2.0
    d0 = d1 - sigma * root_tau
    if is_put:
        return D * (K * normal_cdf(-d0) - F * normal_cdf(-d1))
    return D * (F * normal_cdf(d1) - K * normal_cdf(d0))


def yields_on(day):
    """
    The four yields (fractions) that apply on a day: that day's, or the last day's
    before it with values (forward-fill, sec:rates).
    """
    known = None
    for listed_day in sorted(YIELDS):
        if listed_day <= day and YIELDS[listed_day] is not None:
            known = YIELDS[listed_day]
    if known is None:
        raise ValueError("no yields on or before " + day)
    fractions = []
    for value in known:
        fractions.append(value / 100)              # per cent -> fraction
    return fractions


def rate_for(day, days_to_expiry):
    """
    The continuous rate for one maturity (sec:rates):
      each yield converted with its own maturity:  r = log(1 + y tau) / tau   (eq:rate-conversion)
      linear interpolation in calendar days between 30, 91, 182, 365 days,
      the 1-month rate below 30 days, the 1-year rate above 365 (choice, not reached).
    """
    simple = yields_on(day)
    continuous = []
    for number in range(4):
        tau = YIELD_DAYS[number] / 365
        continuous.append(math.log(1 + simple[number] * tau) / tau)
    if days_to_expiry <= YIELD_DAYS[0]:
        return continuous[0]
    if days_to_expiry >= YIELD_DAYS[-1]:
        return continuous[-1]
    for number in range(3):
        low_days = YIELD_DAYS[number]
        high_days = YIELD_DAYS[number + 1]
        if low_days <= days_to_expiry <= high_days:
            weight = (days_to_expiry - low_days) / (high_days - low_days)
            return continuous[number] + weight * (continuous[number + 1] - continuous[number])
    raise ValueError("no rate for " + str(days_to_expiry) + " days")


def snapshot_times(day_info):
    """Every snapshot of a day: 09:45 to 16:15, or to 13:15 on an early close, every 15 minutes."""
    times = []
    if day_info["early_close"]:
        last_minutes = 13 * 60 + 15
    else:
        last_minutes = 16 * 60 + 15
    minutes = 9 * 60 + 45
    while minutes <= last_minutes:
        hours = minutes // 60                      # // divides and drops the remainder
        rest = minutes % 60                        # % is the remainder
        times.append(day_info["day"] + " " + str(hours).zfill(2) + ":" + str(rest).zfill(2) + ":00")
        minutes = minutes + 15
    return times


def strike_list():
    """Every strike: every 25 points up to 3600, then every 5 points up to 4400."""
    strikes = []
    strike = WIDE_STRIKES_FROM
    while strike < NARROW_STRIKES_FROM:
        strikes.append(strike)
        strike = strike + 25.0
    strike = NARROW_STRIKES_FROM
    while strike <= STRIKES_TO:
        strikes.append(strike)
        strike = strike + 5.0
    return strikes


def expected_kept(root, days, is_put, strike, S, bid, ask):
    """
    Whether the thesis's filters (sec:cleaning, D1) keep a row: vanilla root,
    4 to 100 days, K/S in the put or call limits, bid >= 0.025, ask > bid.
    Limits inclusive (the test specification writes them as closed intervals).
    """
    if root not in GOOD_ROOTS:
        return False
    if days < MIN_DAYS or days > MAX_DAYS:
        return False
    moneyness = strike / S
    if is_put:
        low, high = PUT_LIMITS
    else:
        low, high = CALL_LIMITS
    if moneyness < low or moneyness > high:
        return False
    if bid < MIN_BID:
        return False
    if not ask > bid:
        return False
    return True


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

RAW_COLUMNS = ["underlying_symbol", "quote_datetime", "root", "expiration", "strike", "option_type",
               "open", "high", "low", "close", "trade_volume", "bid_size", "bid", "ask_size", "ask",
               "underlying_bid", "underlying_ask"]
TRUTH_COLUMNS = ["quote_datetime", "root", "expiration", "strike", "option_type", "days", "S",
                 "spot_quote", "rate", "q", "F", "D", "sigma", "price", "bid", "ask", "kept_by_stage1"]


def write_raw_day(day_info, strikes, truth_writer):
    """Write one raw file for one day, and one truth row per raw row."""
    folder = os.path.join(WORK_FOLDER, "Data", "01_raw_options")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "UnderlyingOptionsIntervals_900sec_" + day_info["day"] + ".csv")
    S = day_info["S"]
    times = snapshot_times(day_info)
    rows_written = 0

    with open(path, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(RAW_COLUMNS)
        for time in times:
            is_last_snapshot = time == times[-1]
            # The recorded index quote: S -/+ 0.5, nonsense at the last snapshot (D2).
            if is_last_snapshot:
                index_bid = S + 100.0 - 0.5
                index_ask = S + 100.0 + 0.5
            else:
                index_bid = S - 0.5
                index_ask = S + 0.5
            spot_quote = (index_bid + index_ask) / 2

            for expiry in EXPIRIES:
                root = expiry["root"]
                days = (date.fromisoformat(expiry["expiration"]) - date.fromisoformat(day_info["day"])).days
                tau = days / 365                                   # all days here are >= 3
                rate = rate_for(day_info["day"], days)
                q = DIVIDEND_YIELD.get(root, 0.015)                # BSZ: any value, it is dropped
                F = S * math.exp((rate - q) * tau)                 # prop:forward
                D = math.exp(-rate * tau)                          # def:discount

                for strike in strikes:
                    for option_type in ["P", "C"]:
                        is_put = option_type == "P"
                        if not is_put and strike < NARROW_STRIKES_FROM:
                            continue                               # calls only near the money
                        if root == FEW_PAIRS_ROOT and not is_put and strike not in FEW_PAIRS_STRIKES:
                            continue                               # the few-pairs expiry
                        x = math.log(strike / F)
                        sigma = expiry["a"] + expiry["b"] * x + expiry["c"] * x * x
                        price = black76_price(F, strike, tau, sigma, D, is_put)
                        half_width = HALF_WIDTH_FIXED + HALF_WIDTH_SHARE * price
                        bid = price - half_width
                        ask = price + half_width
                        if (time == FLAT_QUOTE["time"] and root == FLAT_QUOTE["root"] and is_put
                                and expiry["expiration"] == FLAT_QUOTE["expiration"]
                                and strike == FLAT_QUOTE["strike"]):
                            bid = price                            # the trap: ask = bid
                            ask = price
                        if bid < 0:
                            bid = 0.0                              # no negative bids, as in real data

                        writer.writerow(["^SPX", time, root, expiry["expiration"], repr(strike), option_type,
                                         "0.0000", "0.0000", "0.0000", "0.0000", "0", "100", repr(bid),
                                         "100", repr(ask), repr(index_bid), repr(index_ask)])
                        kept = expected_kept(root, days, is_put, strike, S, bid, ask)
                        truth_writer.writerow([time, root, expiry["expiration"], repr(strike), option_type,
                                               days, repr(S), repr(spot_quote), repr(rate), repr(q), repr(F),
                                               repr(D), repr(sigma), repr(price), repr(bid), repr(ask), kept])
                        rows_written = rows_written + 1
    return rows_written


def write_index_close():
    """The official close file, laid out like Data/07_index_close/GSPC_daily.csv."""
    folder = os.path.join(WORK_FOLDER, "Data", "07_index_close")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "GSPC_daily.csv"), "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Date", "Open", "High", "Low", "Close", "Volume"])
        for day_info in DAYS:
            S = repr(day_info["S"])
            writer.writerow([day_info["day"], S, S, S, S, "0"])


def write_yields():
    """The four T-bill files, laid out like the FRED files in Data/03_treasury_bills."""
    folder = os.path.join(WORK_FOLDER, "Data", "03_treasury_bills")
    os.makedirs(folder, exist_ok=True)
    for number in range(4):
        series = YIELD_SERIES[number]
        with open(os.path.join(folder, series + ".csv"), "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["observation_date", series])
            for day in sorted(YIELDS):
                if YIELDS[day] is None:
                    writer.writerow([day, ""])                     # FRED leaves such days empty
                else:
                    writer.writerow([day, repr(YIELDS[day][number])])


def main():
    if os.path.exists(WORK_FOLDER):
        raise ValueError(WORK_FOLDER + " exists already: delete it first")
    os.makedirs(WORK_FOLDER)
    write_index_close()
    write_yields()
    strikes = strike_list()
    total = 0
    with open(os.path.join(WORK_FOLDER, "truth.csv"), "w", newline="") as truth_file:
        truth_writer = csv.writer(truth_file)
        truth_writer.writerow(TRUTH_COLUMNS)
        for day_info in DAYS:
            total = total + write_raw_day(day_info, strikes, truth_writer)
    print("wrote " + str(total) + " raw rows for " + str(len(DAYS)) + " days to " + WORK_FOLDER)


main()
