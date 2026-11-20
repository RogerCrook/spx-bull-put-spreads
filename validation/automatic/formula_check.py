"""
Formula check by known answers (code validation, step 2, method 1).

What this file is for
---------------------
The pipeline stores, for every kept quote, the forward F, the discount factor D,
the implied volatility and four Greeks (Data/04_greeks/). This script recomputes
them with its own Black-76, written from the thesis (prop:black76, prop:greeks-fwd,
prop:chainrule, rem:scaling), and compares. It does not import or read Code/, so a
wrong formula in the code cannot also be in the check.

  Part 1  the check's own Black-76 on made-up inputs (seconds). It must pass first,
          because Part 2 trusts it:
            - put-call parity (F2), the price rising with sigma and its limits (F3),
            - each Greek against a finite difference with D held fixed (F5),
            - the thesis's illustrative numbers: the flat-vol entry delta 0.296 (F9),
              the credits 31.98 / 44.62 / 54.04 (F10, rem:credit-size), and the
              delta of the 3,900 put in tab:validation,
            - a textbook value (Hull's example of Black's model, see the setting).
  Part 2  the stored outputs of a sample of months, every n-th row:
            - D1  the cleaning filters hold on every stored row,
            - D4  mid = (bid + ask) / 2,
            - D5  dte = calendar days from the quote date to expiry,
            - F4  pricing at the stored iv gives back the mid (the round trip),
                  and a row without iv has a price outside the no-arbitrage bounds
                  or outside what sigma in [0.001, 5] can produce,
            - F5, F6, F7  stored delta, gamma, vega, theta = the formulas with the
                  chain rule to S and the scalings (vega / 100, theta / 365),
            - the signs: put delta in [-D, 0], call delta in [0, D], gamma and vega > 0.

Not tested here: F (the forward, D8), D (the rates, D6, D7), the ATM fit (D11).
These are the inputs of the formulas here, taken as stored.

How to run (from the main folder; read-only). Part 2 reads about 6 GB, line by line,
expected 5 to 15 minutes:
    python validation/automatic/formula_check.py

Prints a summary. Writes every difference (at most MAX_PROBLEM_ROWS) to
validation/automatic/output/formula_check.csv. Writes nothing else.
"""

import csv          # reads and writes CSV files row by row
import math         # exp, log, sqrt, erf
import os           # file existence and the output folder
from datetime import date   # to count calendar days between two dates


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

GREEKS_FOLDER = "Data/04_greeks"                  # one file per month, spx_YYYY-MM.csv
OUTPUT_FOLDER = "validation/automatic/output"

# The sample of months (choice): one per year, a different calendar month each year,
# plus the three stress months 2020-03, 2024-08 and 2025-04.
SAMPLE_MONTHS = ["2012-01", "2013-02", "2014-03", "2015-04", "2016-05", "2017-06",
                 "2018-07", "2019-08", "2020-03", "2020-09", "2021-10", "2022-11",
                 "2023-12", "2024-08", "2025-04", "2026-07"]

EVERY_NTH_ROW = 10              # test every 10th row of a file (choice: keeps the run short)

# The cleaning filters of sec:cleaning (D1).
VANILLA_ROOTS = ["SPX", "SPXW", "SPXQ"]          # the roots of the table in sec:data
MIN_DAYS = 4
MAX_DAYS = 100
PUT_MONEYNESS = (0.30, 1.08)    # K/S for puts
CALL_MONEYNESS = (0.97, 1.03)   # K/S for calls
MIN_BID = 0.025                 # bid >= 0.025 (test specification D1)

# The volatility search interval of sec:iv-impl.
SIGMA_LOW = 0.001
SIGMA_HIGH = 5.0

# Rounding of the stored numbers: 6 decimals (seen in the files). Half a unit:
HALF_UNIT = 0.5e-6

# Tolerances (choice, fixed before the first run).
GREEK_ABSOLUTE = 2e-6           # a Greek may differ by 2 units of the 6th decimal ...
GREEK_RELATIVE = 1e-4           # ... plus 0.01% of its size (the inputs are rounded too)

# Hull, "Options, Futures, and Other Derivatives", example of Black's model for a
# European put on a futures price: F = 20, K = 20, r = 9%, 4 months, sigma = 25%,
# put price 1.12 (to 2 decimals). Quoted from memory, to be checked against the book.
HULL_EXAMPLE = {"F": 20.0, "K": 20.0, "r": 0.09, "tau": 4 / 12, "sigma": 0.25, "put": 1.12}

MAX_PROBLEM_ROWS = 10000        # at most this many rows in the output file


# ---------------------------------------------------------------------------
# The check's own Black-76 (from the thesis)
# ---------------------------------------------------------------------------

def normal_cdf(x):
    """N(x), the standard normal distribution function, through the error function erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def normal_density(x):
    """phi(x) = exp(-x^2 / 2) / sqrt(2 pi), the standard normal density."""
    return math.exp(-x * x / 2.0) / math.sqrt(2.0 * math.pi)


def d1_d0(F, K, tau, sigma):
    """
    d1 = log(F / K) / (sigma sqrt(tau)) + (sigma / 2) sqrt(tau),   d0 = d1 - sigma sqrt(tau)
    (eq:d1d0).
    """
    root_tau = math.sqrt(tau)
    d1 = math.log(F / K) / (sigma * root_tau) + sigma * root_tau / 2.0
    d0 = d1 - sigma * root_tau
    return d1, d0


def black76_price(F, K, tau, sigma, D, is_put):
    """
    Black-76 price (eq:b76-call, eq:b76-put):
        call = D [F N(d1) - K N(d0)]
        put  = D [K N(-d0) - F N(-d1)]
    tau in years, sigma as a fraction (0.18 = 18%), D the discount factor.
    """
    d1, d0 = d1_d0(F, K, tau, sigma)
    if is_put:
        return D * (K * normal_cdf(-d0) - F * normal_cdf(-d1))
    return D * (F * normal_cdf(d1) - K * normal_cdf(d0))


def black76_greeks(F, K, tau, sigma, D, is_put):
    """
    The Greeks of prop:greeks-fwd, partial derivatives with D held fixed:
        Delta_F = D [N(d1) - 1 if put]
        Gamma_F = D phi(d1) / (F sigma sqrt(tau))
        Vega    = D F phi(d1) sqrt(tau)                    (per 1.00 of sigma)
        Theta   = -D F phi(d1) sigma / (2 sqrt(tau))       (= -dC/dtau, per year)
    Theta is the same for a put: P = C - D (F - K), and with D fixed the last
    term does not depend on tau.
    Returns a dictionary, unscaled.
    """
    d1, d0 = d1_d0(F, K, tau, sigma)
    root_tau = math.sqrt(tau)
    density = normal_density(d1)
    delta_F = D * normal_cdf(d1)
    if is_put:
        delta_F = delta_F - D
    gamma_F = D * density / (F * sigma * root_tau)
    vega = D * F * density * root_tau
    theta = -D * F * density * sigma / (2.0 * root_tau)
    return {"delta_F": delta_F, "gamma_F": gamma_F, "vega": vega, "theta": theta}


def stored_greeks(F, S, K, tau, sigma, D, is_put):
    """
    The Greeks as the pipeline should store them (prop:chainrule, rem:scaling):
        delta = Delta_F * F / S          gamma = Gamma_F * (F / S)^2
        vega  = Vega / 100               theta = Theta / 365
    """
    greeks = black76_greeks(F, K, tau, sigma, D, is_put)
    ratio = F / S
    return {
        "delta": greeks["delta_F"] * ratio,
        "gamma": greeks["gamma_F"] * ratio * ratio,
        "vega": greeks["vega"] / 100.0,
        "theta": greeks["theta"] / 365.0,
    }


# ---------------------------------------------------------------------------
# Part 1: the check's own formulas on made-up inputs
# ---------------------------------------------------------------------------

def report(results, name, passed, detail):
    """Store one Part 1 result and print it at once."""
    results.append((name, passed))
    if passed:
        word = "ok  "
    else:
        word = "FAIL"
    print("  " + word + "  " + name + "   " + detail)


def part_1():
    """Run the Part 1 tests. Returns True if all pass."""
    print("Part 1: the check's own Black-76 on made-up inputs")
    results = []

    # A grid of made-up inputs (choice): strikes from deep in to deep out of the money.
    F = 4000.0
    D = math.exp(-0.04 * 30 / 365)                     # D = exp(-r tau), r = 4%, 30 days
    strikes = [2000.0, 3000.0, 3600.0, 3900.0, 4000.0, 4100.0, 4400.0, 5000.0]
    taus = [4 / 365, 30 / 365, 100 / 365]
    sigmas = [0.05, 0.18, 0.60, 2.0]

    # F2: call - put = D (F - K).
    worst = 0.0
    for K in strikes:
        for tau in taus:
            for sigma in sigmas:
                call = black76_price(F, K, tau, sigma, D, False)
                put = black76_price(F, K, tau, sigma, D, True)
                error = abs(call - put - D * (F - K))
                if error > worst:
                    worst = error
    report(results, "F2 put-call parity", worst < 1e-9, "largest error " + str(worst))

    # F3: the price rises with sigma, and stays inside its limits
    #     D (F - K)+ <= call <= D F,   D (K - F)+ <= put <= D K.
    # "Rises strictly" can only be seen away from the limits: very close to a limit
    # two prices are equal in floating point, or one is lower in its last digit
    # (seen in the first run, 2026-11-17: a call worth exactly its lower limit "fell"
    # by 4e-13, a worthless call went from 0 to -5.5e-14). So a step counts as a
    # failure if the price falls by more than 1e-9, or if it stays equal while more
    # than 1e-9 away from both limits.
    rises = True
    inside = True
    for K in strikes:
        for tau in taus:
            for is_put in [False, True]:
                if is_put:
                    lower = D * max(K - F, 0.0)
                    upper = D * K
                else:
                    lower = D * max(F - K, 0.0)
                    upper = D * F
                previous = None
                for step in range(1, 101):             # sigma = 0.05, 0.10, ..., 5.00
                    sigma = step * 0.05
                    price = black76_price(F, K, tau, sigma, D, is_put)
                    if previous is not None:
                        if price < previous - 1e-9:
                            rises = False
                        away_from_limits = price > lower + 1e-9 and price < upper - 1e-9
                        if price == previous and away_from_limits:
                            rises = False
                    previous = price
                    if price < lower - 1e-9 or price > upper + 1e-9:
                        inside = False
    report(results, "F3 price rises with sigma", rises, "")
    report(results, "F3 price inside its no-arbitrage limits", inside, "")

    # F5: each Greek against a central finite difference, D held fixed.
    worst_relative = 0.0
    for K in strikes:
        for tau in taus:
            for sigma in [0.18, 0.60]:
                for is_put in [False, True]:
                    greeks = black76_greeks(F, K, tau, sigma, D, is_put)
                    h = 0.01                                                  # step in F (points)
                    up = black76_price(F + h, K, tau, sigma, D, is_put)
                    down = black76_price(F - h, K, tau, sigma, D, is_put)
                    middle = black76_price(F, K, tau, sigma, D, is_put)
                    numeric = {
                        "delta_F": (up - down) / (2 * h),
                        "gamma_F": (up - 2 * middle + down) / (h * h),
                    }
                    s = 1e-5                                                  # step in sigma
                    numeric["vega"] = (black76_price(F, K, tau, sigma + s, D, is_put)
                                       - black76_price(F, K, tau, sigma - s, D, is_put)) / (2 * s)
                    t = 1e-6                                                  # step in tau (years)
                    numeric["theta"] = -(black76_price(F, K, tau + t, sigma, D, is_put)
                                         - black76_price(F, K, tau - t, sigma, D, is_put)) / (2 * t)
                    # A Greek passes if it is within 0.1% of the finite difference, or
                    # within 1e-6 in absolute terms. The second is for Greeks that are
                    # practically 0, where the finite difference is only rounding noise
                    # (seen in the first run, 2026-11-17: theta of a deep in-the-money
                    # call, -3.4e-10, against a finite difference of 2.3e-7). The stored
                    # Greeks have 6 decimals, so 1e-6 is below what they can show.
                    for name in numeric:
                        difference = abs(numeric[name] - greeks[name])
                        size = max(abs(greeks[name]), 1e-4)                   # avoid dividing by ~0
                        relative = difference / size
                        if difference <= 1e-6:
                            continue                                          # passes on the absolute rule
                        if relative > worst_relative:
                            worst_relative = relative
    report(results, "F5 Greeks = finite differences (D fixed)", worst_relative < 1e-3,
           "largest relative difference above 1e-6 absolute: " + str(worst_relative))

    # F9: the flat-vol entry delta (prop:entry-delta). The position delta of two spreads,
    # Delta_pos = 2 (Delta_S bought - Delta_S sold) (eq:posdelta), with both puts at one
    # sigma and the unsnapped strikes F exp(-sigma sqrt(tau)) and F exp(-2.3 sigma sqrt(tau)),
    # must equal eq:entry-delta:
    #   2 D (F / S) [N(2.3 + s/2) - N(1 + s/2)],   s = sigma sqrt(tau)
    # and the thesis rounds it to 2 (N(2.3) - N(1)) = 0.296.
    worst = 0.0
    for S in [3900.0, 3990.0, 4000.0]:                 # made-up spot levels around F = 4000
        for tau in taus:
            for sigma in [0.10, 0.18, 0.60]:
                s = sigma * math.sqrt(tau)
                sold = stored_greeks(F, S, F * math.exp(-1.0 * s), tau, sigma, D, True)["delta"]
                bought = stored_greeks(F, S, F * math.exp(-2.3 * s), tau, sigma, D, True)["delta"]
                position = 2 * (bought - sold)
                formula = 2 * D * (F / S) * (normal_cdf(2.3 + s / 2) - normal_cdf(1.0 + s / 2))
                error = abs(position - formula)
                if error > worst:
                    worst = error
    report(results, "F9 position delta = eq:entry-delta", worst < 1e-12, "largest error " + str(worst))
    closed_form = 2 * (normal_cdf(2.3) - normal_cdf(1.0))
    report(results, "F9 2(N(2.3) - N(1)) = 0.296", round(closed_form, 3) == 0.296,
           "computed " + str(round(closed_form, 6)))

    # F10: credits of two spreads at 30, 60, 90 days (rem:credit-size):
    # F = 4000, sigma = 18%, r = 4%, strikes F exp(-sigma sqrt(tau)) and F exp(-2.3 sigma sqrt(tau)).
    expected_credits = {30: 31.98, 60: 44.62, 90: 54.04}
    all_equal = True
    detail = ""
    for days in [30, 60, 90]:
        tau = days / 365
        D_here = math.exp(-0.04 * tau)
        sold_strike = 4000.0 * math.exp(-1.0 * 0.18 * math.sqrt(tau))
        bought_strike = 4000.0 * math.exp(-2.3 * 0.18 * math.sqrt(tau))
        credit = 2 * (black76_price(4000.0, sold_strike, tau, 0.18, D_here, True)
                      - black76_price(4000.0, bought_strike, tau, 0.18, D_here, True))
        if round(credit, 2) != expected_credits[days]:
            all_equal = False
        detail = detail + str(days) + " days " + str(round(credit, 4)) + "  "
    report(results, "F10 credits 31.98 / 44.62 / 54.04", all_equal, detail)

    # tab:validation: put K = 3,900, S = 3,990, F = 4,000, 30 days, sigma 18%, r 4%.
    # Delta_S from the formula -0.302545, finite difference in S (by 0.01) -0.302536.
    tau = 30 / 365
    D_here = math.exp(-0.04 * tau)
    formula_delta = stored_greeks(4000.0, 3990.0, 3900.0, tau, 0.18, D_here, True)["delta"]
    ratio = 4000.0 / 3990.0                                     # F moves by F/S per point of S
    up = black76_price(4000.0 + 0.01 * ratio, 3900.0, tau, 0.18, D_here, True)
    down = black76_price(4000.0, 3900.0, tau, 0.18, D_here, True)
    numeric_delta = (up - down) / 0.01                          # one-sided, as "spot moved by 0.01"
    passed = round(formula_delta, 6) == -0.302545 and abs(numeric_delta - (-0.302536)) < 2e-6
    report(results, "tab:validation delta -0.302545 / -0.302536", passed,
           "formula " + str(round(formula_delta, 6)) + ", finite difference " + str(round(numeric_delta, 6)))

    # A textbook value (Hull, Black's model).
    example = HULL_EXAMPLE
    hull_put = black76_price(example["F"], example["K"], example["tau"], example["sigma"],
                             math.exp(-example["r"] * example["tau"]), True)
    report(results, "F1 textbook put 1.12 (Hull, from memory)", round(hull_put, 2) == example["put"],
           "computed " + str(round(hull_put, 4)))

    all_passed = True
    for name, passed in results:
        if not passed:
            all_passed = False
    return all_passed


# ---------------------------------------------------------------------------
# Part 2: the stored outputs
# ---------------------------------------------------------------------------

def days_between(date_text, expiration_text):
    """
    Calendar days from a date "YYYY-MM-DD" to another.

    Example:  days_between("2012-01-03", "2012-02-18")  ->  46
    """
    first = date.fromisoformat(date_text)
    second = date.fromisoformat(expiration_text)
    difference = second - first                                # a "timedelta", a length of time
    return difference.days                                     # its length in whole days


def check_row(values, counts, problems, month):
    """
    Check one stored row. values is a dictionary of texts {column: text}.
    Adds to counts and problems. Returns nothing.
    """
    time = values["quote_datetime"]
    root = values["root"]
    is_put = values["option_type"] == "P"
    K = float(values["strike"])
    bid = float(values["bid"])
    ask = float(values["ask"])
    mid = float(values["mid"])
    S = float(values["spot"])
    F = float(values["forward"])
    D = float(values["D"])
    dte = int(values["dte"])
    label = time + " " + root + " " + values["expiration"] + " " + values["strike"] + " " + values["option_type"]

    counts["rows tested"] = counts["rows tested"] + 1

    # D1: the cleaning filters.
    moneyness = K / S
    if is_put:
        low, high = PUT_MONEYNESS
    else:
        low, high = CALL_MONEYNESS
    filter_fails = []
    if root not in VANILLA_ROOTS:
        filter_fails.append("root")
    if dte < MIN_DAYS or dte > MAX_DAYS:
        filter_fails.append("days")
    if moneyness < low or moneyness > high:
        filter_fails.append("K/S " + str(round(moneyness, 4)))
    if bid < MIN_BID:
        filter_fails.append("bid")
    if not ask > bid:
        filter_fails.append("ask not above bid")
    if len(filter_fails) > 0:
        counts["D1 filter fails"] = counts["D1 filter fails"] + 1
        add_problem(problems, month, "D1", label, ", ".join(filter_fails), "")   # join puts ", " between the words

    # D4: the midpoint.
    if abs(mid - (bid + ask) / 2) > 1e-9:
        counts["D4 mid fails"] = counts["D4 mid fails"] + 1
        add_problem(problems, month, "D4", label, str((bid + ask) / 2), str(mid))

    # D5: days to expiry.
    calendar_days = days_between(time[:10], values["expiration"])
    if calendar_days != dte:
        counts["D5 days fails"] = counts["D5 days fails"] + 1
        add_problem(problems, month, "D5", label, str(calendar_days), str(dte))
    tau = max(dte, 1) / 365                                    # tau = days / 365, at least 1/365 (def:tau-conv)

    # F4: no-arbitrage bounds and the range sigma in [0.001, 5] can reach.
    if is_put:
        lower = D * max(K - F, 0.0)
        upper = D * K
    else:
        lower = D * max(F - K, 0.0)
        upper = D * F
    inside_bounds = lower < mid < upper
    lowest_price = black76_price(F, K, tau, SIGMA_LOW, D, is_put)
    highest_price = black76_price(F, K, tau, SIGMA_HIGH, D, is_put)
    reachable = lowest_price <= mid <= highest_price

    if values["iv"] == "":
        counts["rows without iv"] = counts["rows without iv"] + 1
        if inside_bounds and reachable:
            # A price a sigma in [0.001, 5] could produce, yet no volatility stored.
            margin = min(mid - lowest_price, highest_price - mid)
            if margin > HALF_UNIT * 10:                        # not just rounding at the edge
                counts["F4 no iv although solvable"] = counts["F4 no iv although solvable"] + 1
                add_problem(problems, month, "F4 no iv", label, "an iv in [0.001, 5]", "none (mid " + str(mid) + ")")
        return                                                 # nothing more to test without iv

    sigma = float(values["iv"])
    if not inside_bounds:
        counts["F4 iv although outside bounds"] = counts["F4 iv although outside bounds"] + 1
        add_problem(problems, month, "F4 bounds", label, "no iv", values["iv"])

    # F4 round trip: the price at the stored iv must give back the mid. The stored
    # iv, F and D are rounded to 6 decimals, so allow what that rounding can move:
    #   vega * 0.5e-6  +  |Delta_F| * 0.5e-6  +  price * 0.5e-6 / D  (+ a little)
    greeks = black76_greeks(F, K, tau, sigma, D, is_put)
    price = black76_price(F, K, tau, sigma, D, is_put)
    allowed = (greeks["vega"] + abs(greeks["delta_F"]) + price / D) * HALF_UNIT + 1e-9
    if abs(price - mid) > allowed:
        counts["F4 round trip fails"] = counts["F4 round trip fails"] + 1
        add_problem(problems, month, "F4 round trip", label, str(mid), str(price))

    # F5, F6, F7: the stored Greeks.
    expected = stored_greeks(F, S, K, tau, sigma, D, is_put)
    any_missing = False
    for name in ["delta", "gamma", "vega", "theta"]:
        if values[name] == "":
            any_missing = True
            counts["Greek missing although iv"] = counts["Greek missing although iv"] + 1
            add_problem(problems, month, "F5 missing", label, name, "")
            continue
        stored = float(values[name])
        allowed = GREEK_ABSOLUTE + GREEK_RELATIVE * abs(expected[name])
        if abs(stored - expected[name]) > allowed:
            counts["F5-F7 " + name + " fails"] = counts["F5-F7 " + name + " fails"] + 1
            add_problem(problems, month, "F5-F7 " + name, label, str(expected[name]), values[name])

    # Signs (F5): Delta_F of a put in [-D, 0], of a call in [0, D], gamma and vega
    # not negative. The stored delta is Delta_S, so the chain rule is undone first.
    if any_missing:
        return                                                    # already reported
    delta_F_stored = float(values["delta"]) * S / F               # undo the chain rule
    if is_put:
        sign_ok = -D - HALF_UNIT * 2 <= delta_F_stored <= HALF_UNIT * 2
    else:
        sign_ok = -HALF_UNIT * 2 <= delta_F_stored <= D + HALF_UNIT * 2
    if not sign_ok or float(values["gamma"]) < 0 or float(values["vega"]) < 0:
        counts["F5 sign fails"] = counts["F5 sign fails"] + 1
        add_problem(problems, month, "F5 sign", label, "delta in range, gamma and vega >= 0", values["delta"] + " " + values["gamma"] + " " + values["vega"])


def add_problem(problems, month, check, row_label, expected, found):
    """Keep one difference (at most MAX_PROBLEM_ROWS in all)."""
    if len(problems) < MAX_PROBLEM_ROWS:
        problems.append({"month": month, "check": check, "row": row_label, "expected": expected, "found": found})


def check_month(month, counts, problems):
    """Read one month file line by line and test every EVERY_NTH_ROW-th row."""
    path = GREEKS_FOLDER + "/spx_" + month + ".csv"
    if not os.path.exists(path):
        print("  " + month + ": file not found, skipped")
        return
    rows_in_file = 0
    with open(path, newline="") as file:
        reader = csv.reader(file)                  # each line as a list of texts
        header = next(reader)                      # the column names
        for line in reader:
            rows_in_file = rows_in_file + 1
            if rows_in_file % EVERY_NTH_ROW != 0:  # % is the remainder: keep rows 10, 20, 30, ...
                continue
            values = {}
            for position in range(len(header)):
                values[header[position]] = line[position]
            check_row(values, counts, problems, month)
    print("  " + month + ": " + str(rows_in_file) + " rows in the file")


def part_2():
    """Run Part 2 over the sample months. Returns (counts, problems)."""
    print()
    print("Part 2: the stored outputs, every " + str(EVERY_NTH_ROW) + "th row of " + str(len(SAMPLE_MONTHS)) + " months")
    counts = {}
    for name in ["rows tested", "rows without iv", "D1 filter fails", "D4 mid fails", "D5 days fails",
                 "F4 no iv although solvable", "F4 iv although outside bounds", "F4 round trip fails",
                 "Greek missing although iv", "F5-F7 delta fails", "F5-F7 gamma fails",
                 "F5-F7 vega fails", "F5-F7 theta fails", "F5 sign fails"]:
        counts[name] = 0
    problems = []
    for month in SAMPLE_MONTHS:
        check_month(month, counts, problems)
    return counts, problems


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    part_1_passed = part_1()
    if not part_1_passed:
        print()
        print("Part 1 failed: the check's own formulas are not trusted, Part 2 not run.")
        return

    counts, problems = part_2()

    print()
    for name in counts:
        print("  " + name.ljust(36) + str(counts[name]).rjust(12))

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)              # make the folder; no error if it exists
    path = OUTPUT_FOLDER + "/formula_check.csv"
    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["month", "check", "row", "expected", "found"])
        writer.writeheader()
        for problem in problems:
            writer.writerow(problem)
    print()
    print("  " + str(len(problems)) + " differences written to " + path)
    shown = 0
    for problem in problems:
        if shown == 15:
            break
        print("    " + problem["check"] + " | " + problem["row"] + " | expected " + problem["expected"] + " | found " + problem["found"])
        shown = shown + 1


main()
