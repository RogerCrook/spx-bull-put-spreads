"""
calculator.py  -  the blind calculator of the hand checks (method 7 of the validation)

What it is for
--------------
For each of the 32 hand checks (H01 ... H32 in list.csv) this script works out what
the strategy must do at the snapshot of the check, from the thesis
(Masterarbeit_Tex_file.tex) and validation/test_specification.md (Part G) alone,
using only the inputs in the packet folder packets/H.. .

It was written without looking at the backtest code, its logs or the answer key,
so that its answers can be compared with the backtest independently. Every point
where the thesis and Part G leave a choice open is marked "CHOICE" in a comment and
listed in calc_output/open_questions.md.

Every step is printed as
    rule     -> which rule of the thesis (LaTeX label) or of Part G applies
    formula  -> the formula
    numbers  -> the numbers put into it
    result   -> what comes out
so that each step can be judged without reading this code.

The order of the steps for one snapshot (the working order of README.md):
    1. Is a decision allowed (not the stock close)?
    2. Are both legs usable (a row with a delta) and not broken (def:broken, G11)?
    3. Position delta now (eq:posdelta) and which exit holds (def:exits, G1).
    4. If it exits: cost to close, P&L, new deficit (def:deficit).
    5. If it exits, or no position is open: the new position (def:entry, def:tau-star).
    6. The equity day (only the check whose snapshot ends in "(day)").
    7. Deep checks: cleaning, forward, implied vol, delta and ATM vol redone from raw.csv.

How to run (from the main folder of the project, or from anywhere):
    python validation/hand_checks/calculator.py

It reads only the small packet files (a few seconds) and writes
    validation/hand_checks/calc_output/H01.txt ... H32.txt   (one per check)
    validation/hand_checks/calc_output/answers.csv           (one row per check)

Only the Python standard library is used (csv, math, os, datetime): no pandas,
no numpy.
"""

import csv        # reads and writes comma-separated text files
import math       # exp, log, sqrt, erf (for the normal distribution)
import os         # file paths and folders
import datetime   # calendar dates: days between two dates, day of the week


# ======================================================================
# Settings
# ======================================================================

# --- Where the files are -------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))     # the folder of this script (validation/hand_checks)
PACKET_FOLDER = os.path.join(HERE, "packets")          # packets/H01 ... packets/H32 (inputs)
LIST_FILE = os.path.join(HERE, "list.csv")             # the 32 checks: hand_check, run, snapshot, deep
OUTPUT_FOLDER = os.path.join(HERE, "calc_output")      # where the answers are written

# --- The strategy (chapter 2 of the thesis, tab:spec) --------------------
SHORT_OFFSET = 1.0          # sold put at K = F * exp(-1.0 * sigma * sqrt(tau))    (eq:strikes)
LONG_OFFSET = 2.3           # bought put at K = F * exp(-2.3 * sigma * sqrt(tau))  (eq:strikes)
NUMBER_OF_SPREADS = 2       # the position is two spreads (def:entry)
TARGET_DAYS = 30            # shortest expiry with at least 30 days (def:entry, def:tau-star, G5)
CAP_DAYS = 90               # recovery maturities only up to 90 days (def:tau-star, G5)
GAMMA_FLOOR_DAYS = 10       # gamma exit at tau <= max(tau0 / 2, 10 days) (eq:gamma-exit)
LOSS_BAND = 0.10            # loss exit at delta_pos >= delta0 + 0.10, in both runs (def:exits, sec:robustness)
PROFIT_BAND = {             # profit exit at delta_pos <= delta0 - band
    "base": 0.10,           # base case (def:exits)
    "p15": 0.15,            # the p15 variant: profit exit at delta0 - 0.15 (sec:robustness)
}
EXIT_ORDER = ["loss", "profit", "gamma"]   # G1: tested in this order, the first that holds is recorded
ROOT_ORDER = {"SPX": 0, "SPXQ": 1, "SPXW": 2}   # G4: on the same date SPX first, then SPXQ, then SPXW
DOLLARS_PER_POINT = 100     # one index point of an SPX option is worth 100 dollars (G15)

# --- The broken-quote rule (def:broken) ----------------------------------
BROKEN_VOL_JUMP = 0.03      # condition 1: |iv_t - iv_before| > 0.03 (three volatility points)
BROKEN_WIDTH_RATIO = 3.0    # condition 2: w_t > 3 * w_before

# --- The data pipeline, for the deep checks (chapter 3) ------------------
VANILLA_ROOTS = ["SPX", "SPXW", "SPXQ"]   # sec:cleaning "vanilla roots only"; the roots of the table in sec:data (CHOICE: the list itself)
MIN_DAYS = 4                # sec:cleaning: time to expiry 4-100 days (CHOICE: both ends included)
MAX_DAYS = 100
PUT_MONEYNESS = (0.30, 1.08)    # sec:cleaning: puts K/S in [0.30, 1.08] (CHOICE: both ends included)
CALL_MONEYNESS = (0.97, 1.03)   # sec:cleaning: calls K/S in [0.97, 1.03] (CHOICE: both ends included)
MIN_BID = 0.025             # sec:cleaning: bid >= 0.025
PARITY_STRIKES = 8          # sec:forward-impl: parity at the 8 strikes nearest K0
MIN_PAIRS = 3               # sec:forward-impl: fewer than 3 pairs -> no forward
IV_LOW = 0.001              # sec:iv-impl: bisection on [0.001, 5]
IV_HIGH = 5.0
IV_HALVINGS = 60            # sec:iv-impl: 60 halvings
ATM_BAND = 0.05             # def:atm: |x| < 0.05 with x = log(K/F)
ATM_MIN_QUOTES = 3          # def:atm: at least three quotes
RATE_DAYS = [30, 91, 182, 365]   # sec:rates: maturities of the 1, 3, 6, 12 month yields in days (CHOICE: 30/91/182/365)
RATE_COLUMNS = ["DGS1MO", "DGS3MO", "DGS6MO", "DGS1"]   # the four FRED series, in the same order

# The columns of answers.csv, in this order.
ANSWER_COLUMNS = [
    "hand_check", "run", "snapshot",
    "decision_allowed", "legs_usable", "broken_leg",
    "position_delta", "delta0", "exit_reason",
    "exit_cost", "pnl", "deficit_before", "new_deficit",
    "new_root", "new_expiry", "new_dte", "maturity_rule",
    "target_short", "target_long", "strike_short", "strike_long",
    "credit", "entry_delta", "gamma_exit_days", "gamma_exit_day", "margin",
    "day_unrealised_points", "day_pnl_dollars", "day_interest_dollars", "day_margin",
    "deep_spot_calc", "deep_spot_packet",
    "deep_forward_calc", "deep_forward_packet",
    "deep_iv_short_calc", "deep_iv_short_packet",
    "deep_iv_long_calc", "deep_iv_long_packet",
    "deep_delta_short_calc", "deep_delta_short_packet",
    "deep_delta_long_calc", "deep_delta_long_packet",
    "deep_atm_calc", "deep_atm_packet",
]


# ======================================================================
# 1. Small helpers: reading files, numbers, times, printing
# ======================================================================

def read_table(path):
    """
    Read a CSV file into a list of rows. Each row is a dictionary
    {column name: text}, e.g. row["strike"] -> "1780.0".
    """
    rows = []
    with open(path, newline="") as file:              # 'with' closes the file again at the end
        reader = csv.DictReader(file)                  # DictReader takes the first line as the column names
        for row in reader:                             # one dictionary per line of the file
            rows.append(row)
    return rows


def number_or_none(text):
    """Turn the text of a cell into a number: '1.25' -> 1.25, and an empty cell -> None (no value)."""
    if text is None:                                   # the column does not exist in this row
        return None
    text = text.strip()                                # remove spaces around the text
    if text == "":                                     # an empty cell means: no value
        return None
    return float(text)


def show(value, digits):
    """Write a number with a fixed number of decimals: show(3.14159, 2) -> '3.14'. None -> 'none'."""
    if value is None:
        return "none"
    pattern = "." + str(digits) + "f"                  # e.g. ".2f" = two decimals
    return format(value, pattern)                      # format() writes the number with that pattern


def date_of(timestamp):
    """'2014-01-13 09:45:00' -> '2014-01-13' (the first 10 characters)."""
    return timestamp[0:10]


def clock_of(timestamp):
    """'2014-01-13 09:45:00' -> '09:45:00' (characters 12 to 19)."""
    return timestamp[11:19]


def to_date(text):
    """'2014-01-13' -> a date object, so that dates can be subtracted."""
    return datetime.date.fromisoformat(text[0:10])     # fromisoformat reads the form YYYY-MM-DD


def calendar_days_between(first_date_text, second_date_text):
    """Number of calendar days from the first date to the second: ('2014-01-10', '2014-01-13') -> 3."""
    difference = to_date(second_date_text) - to_date(first_date_text)   # a 'timedelta' (a length of time)
    return difference.days                                            # .days = the length in whole days


def add_step(lines, title, rule, formula, numbers, result):
    """
    Append one step to the printout, as
        title
          rule:    ...
          formula: ...
          numbers: ...      (numbers is a list of lines)
          result:  ...
    """
    lines.append("")
    lines.append(title)
    lines.append("  rule:    " + rule)
    lines.append("  formula: " + formula)
    first = True
    for line in numbers:                               # the first line after 'numbers:', the others indented below it
        if first:
            lines.append("  numbers: " + line)
            first = False
        else:
            lines.append("           " + line)
    if first:                                          # the list was empty
        lines.append("  numbers: -")
    lines.append("  result:  " + result)


# ======================================================================
# 2. Reading one packet
# ======================================================================

def read_calendar(folder):
    """
    Read calendar.txt: the time of the last snapshot of the day before and of the day.
    Returns a dictionary {date: last snapshot time}, e.g. {'2014-01-10': '16:15:00', ...}.
    A line looks like:  last snapshot of 2014-01-10: 16:15:00
    """
    calendar = {}
    path = os.path.join(folder, "calendar.txt")
    with open(path) as file:
        for line in file:
            line = line.strip()
            if not line.startswith("last snapshot of "):   # skip empty or other lines
                continue
            rest = line[len("last snapshot of "):]           # '2014-01-10: 16:15:00'
            day = rest[0:10]                                 # '2014-01-10'
            last_time = rest[12:20]                          # '16:15:00' (after the date and ': ')
            calendar[day] = last_time
    return calendar


def stock_close_clock(last_snapshot_clock):
    """
    sec:monitoring: the stock close is 16:00, or 13:00 on an early-close day.
    An early-close day is one whose last snapshot is 13:15 (README, calendar.txt).
    """
    if last_snapshot_clock == "13:15:00":
        return "13:00:00"
    if last_snapshot_clock == "16:15:00":
        return "16:00:00"
    raise ValueError("unexpected last snapshot of a day: " + last_snapshot_clock)


def is_stock_close(timestamp, calendar):
    """True if this snapshot is the stock close of its day (16:00, or 13:00 on an early-close day)."""
    day = date_of(timestamp)
    if day not in calendar:                            # we only know the two days of the packet
        raise ValueError("day not in calendar.txt: " + day)
    return clock_of(timestamp) == stock_close_clock(calendar[day])


def read_positions(folder):
    """
    Read position.txt. Returns (positions, deficit_without_position, header_lines):
      positions: a list of dictionaries, one per 'Position' block (usually one,
                 two on the equity day, none on the very first snapshot)
      deficit_without_position: the deficit stated when no position is open, else None
    """
    positions = []
    deficit_without_position = None
    header_lines = []
    current = None                                     # the position block being read
    path = os.path.join(folder, "position.txt")
    with open(path) as file:
        for raw_line in file:
            line = raw_line.rstrip("\n")
            if line.startswith("Position"):            # a new block begins
                current = {}
                positions.append(current)
                continue
            if line.startswith("  ") and ": " in line and current is not None:
                parts = line.strip().split(": ", 1)    # split at the first ': ' only -> [key, value]
                key = parts[0]
                value = parts[1]
                current[key] = value
                continue
            if "Deficit:" in line:                     # '... Deficit: 0.' when no position is open
                start = line.index("Deficit:") + len("Deficit:")   # .index = where the text 'Deficit:' begins
                text = line[start:].strip()            # '0.'
                text = text.rstrip(".")                # remove the full stop at the end -> '0'
                deficit_without_position = float(text)
            if line.strip() != "":
                header_lines.append(line.strip())
    # turn the numbers of each block from text into numbers
    number_keys = ["strike_short", "strike_long", "dte0", "delta0", "credit", "margin", "deficit_at_entry"]
    for position in positions:
        for key in number_keys:
            position[key] = float(position[key])
    return positions, deficit_without_position, header_lines


def make_quote(row):
    """Turn one row of legs.csv or puts.csv (all text) into a dictionary with numbers."""
    quote = {}
    quote["time"] = row["quote_datetime"]              # e.g. '2014-01-13 09:45:00'
    quote["root"] = row["root"]                        # SPX, SPXW or SPXQ
    quote["expiration"] = row["expiration"]            # e.g. '2014-01-31'
    quote["dte"] = int(row["dte"])                     # whole calendar days to expiry
    quote["strike"] = float(row["strike"])             # index points
    quote["bid"] = number_or_none(row["bid"])          # index points
    quote["ask"] = number_or_none(row["ask"])
    quote["mid"] = number_or_none(row["mid"])          # (bid + ask) / 2  (eq:mid)
    quote["spot"] = number_or_none(row["spot"])        # S at this snapshot
    quote["forward"] = number_or_none(row["forward"])  # F of this root and expiry at this snapshot
    quote["D"] = number_or_none(row["D"])              # discount factor to expiry
    quote["iv"] = number_or_none(row["iv"])            # implied vol, a fraction (0.18 = 18%)
    quote["delta"] = number_or_none(row["delta"])      # spot delta of one put (negative)
    return quote


def put_key(root, expiration, strike):
    """The contract key of a put (sec:data): root, expiry and strike (the type is always P here)."""
    return (root, expiration, strike)


def read_leg_quotes(folder):
    """
    Read legs.csv (the puts of the position over the day before and the day).
    Returns a dictionary {put key: list of quotes in time order}.
    If the file does not exist (no position open), the dictionary is empty.
    """
    quotes_by_put = {}
    path = os.path.join(folder, "legs.csv")
    if not os.path.exists(path):                       # no position open -> no legs file
        return quotes_by_put
    for row in read_table(path):
        quote = make_quote(row)
        key = put_key(quote["root"], quote["expiration"], quote["strike"])
        if key not in quotes_by_put:
            quotes_by_put[key] = []
        quotes_by_put[key].append(quote)
    # The quotes must be in time order: check it rather than assume it.
    # (Timestamps 'YYYY-MM-DD HH:MM:SS' sort correctly as text.)
    for key in quotes_by_put:
        quotes = quotes_by_put[key]
        for position in range(1, len(quotes)):
            if quotes[position]["time"] <= quotes[position - 1]["time"]:
                raise ValueError("legs.csv is not in time order for " + str(key))
    return quotes_by_put


def quote_at(quotes_by_put, key, timestamp):
    """The quote of one put at one snapshot, or None if the put has no row there."""
    if key not in quotes_by_put:
        return None
    for quote in quotes_by_put[key]:
        if quote["time"] == timestamp:
            return quote
    return None


def read_expiries(folder):
    """Read expiries.csv: every expiry at the snapshot with its forward and ATM vol."""
    expiries = []
    for row in read_table(os.path.join(folder, "expiries.csv")):
        expiry = {}
        expiry["root"] = row["root"]
        expiry["expiration"] = row["expiration"]
        expiry["dte"] = int(row["dte"])                # whole calendar days
        expiry["spot"] = number_or_none(row["spot"])
        expiry["forward"] = number_or_none(row["forward"])
        expiry["atm"] = number_or_none(row["atm_iv"])  # sigma_atm of def:atm, a fraction
        expiries.append(expiry)
    return expiries


def read_puts_by_slice(folder):
    """
    Read puts.csv (every put at the snapshot) and group the puts by slice.
    Returns a dictionary {(root, expiration): list of quotes}.
    """
    puts_by_slice = {}
    for row in read_table(os.path.join(folder, "puts.csv")):
        quote = make_quote(row)
        slice_key = (quote["root"], quote["expiration"])
        if slice_key not in puts_by_slice:
            puts_by_slice[slice_key] = []
        puts_by_slice[slice_key].append(quote)
    return puts_by_slice


# ======================================================================
# 3. Black-76 (chapter 1): normal distribution, prices, delta
# ======================================================================

def normal_cdf(x):
    """N(x), the standard normal distribution function: N(x) = (1 + erf(x / sqrt(2))) / 2."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def d1_d0(F, K, tau, sigma):
    """eq:d1d0: d1 = log(F/K) / (sigma sqrt(tau)) + sigma sqrt(tau) / 2,  d0 = d1 - sigma sqrt(tau)."""
    sigma_sqrt_tau = sigma * math.sqrt(tau)
    d1 = math.log(F / K) / sigma_sqrt_tau + 0.5 * sigma_sqrt_tau
    d0 = d1 - sigma_sqrt_tau
    return d1, d0


def black76_put(F, K, tau, sigma, D):
    """eq:b76-put: P = D [K N(-d0) - F N(-d1)]."""
    d1, d0 = d1_d0(F, K, tau, sigma)
    return D * (K * normal_cdf(-d0) - F * normal_cdf(-d1))


def black76_call(F, K, tau, sigma, D):
    """eq:b76-call: C = D [F N(d1) - K N(d0)]."""
    d1, d0 = d1_d0(F, K, tau, sigma)
    return D * (F * normal_cdf(d1) - K * normal_cdf(d0))


def put_delta_spot(F, K, tau, sigma, D, S):
    """
    Spot delta of a put, sticky strike (prop:greeks-fwd, prop:chainrule, rem:sticky):
        Delta_F = D (N(d1) - 1),   Delta_S = Delta_F * F / S.
    """
    d1, d0 = d1_d0(F, K, tau, sigma)
    delta_forward = D * (normal_cdf(d1) - 1.0)
    return delta_forward * F / S


def tau_in_years(days):
    """def:tau-conv: tau = calendar days / 365, floored at 1/365."""
    if days < 1:
        days = 1
    return days / 365.0


# ======================================================================
# 4. The broken-quote rule (def:broken, G11, G12)
# ======================================================================

def compare_quotes(now, before):
    """
    def:broken: compare a quote at t with the last good quote of the same put.
    Returns a dictionary with the three conditions and the numbers behind them.
    """
    width_now = now["ask"] - now["bid"]                # w_t
    width_before = before["ask"] - before["bid"]       # w_t-
    comparison = {}
    comparison["before_time"] = before["time"]
    comparison["iv_now"] = now["iv"]
    comparison["iv_before"] = before["iv"]
    comparison["iv_jump"] = abs(now["iv"] - before["iv"])               # |iv_t - iv_t-|
    comparison["width_now"] = width_now
    comparison["width_before"] = width_before
    comparison["width_growth"] = width_now - width_before               # w_t - w_t-
    comparison["mid_move"] = abs(now["mid"] - before["mid"])            # |m_t - m_t-|
    comparison["condition1"] = comparison["iv_jump"] > BROKEN_VOL_JUMP
    comparison["condition2"] = width_now > BROKEN_WIDTH_RATIO * width_before
    comparison["condition3"] = comparison["width_growth"] > comparison["mid_move"]
    # broken only if all three hold
    all_three = comparison["condition1"] and comparison["condition2"] and comparison["condition3"]
    comparison["broken"] = all_three
    return comparison


def classify_put_quotes(quotes, calendar):
    """
    Go through the quotes of one put in time order and give each one a status:
        "stock close"  16:00 (13:00 on an early-close day): never a decision, never t-  (sec:monitoring)
        "no delta"     a row without a delta or a mid: not usable (G12)
        "first"        the first usable quote in the packet: nothing earlier to compare with
        "good"         compared with the last good quote and not broken (def:broken, G11)
        "broken"       all three conditions of def:broken hold
    G11: the comparison is always with the last quote of the same put that was not
    broken (CHOICE: a quote counts as good even at a snapshot where the other leg
    was missing or broken, because the quote itself was not broken).
    Returns a dictionary {time: (status, comparison or None)}.
    """
    statuses = {}
    last_good = None                                   # the last good quote seen so far
    for quote in quotes:
        if is_stock_close(quote["time"], calendar):
            statuses[quote["time"]] = ("stock close", None)
            continue
        if quote["delta"] is None or quote["iv"] is None or quote["mid"] is None:
            statuses[quote["time"]] = ("no delta", None)
            continue
        if last_good is None:                          # CHOICE: the first quote of the packet counts as good
            statuses[quote["time"]] = ("first", None)
            last_good = quote
            continue
        comparison = compare_quotes(quote, last_good)
        if comparison["broken"]:
            statuses[quote["time"]] = ("broken", comparison)   # last_good stays as it was
        else:
            statuses[quote["time"]] = ("good", comparison)
            last_good = quote
    return statuses


def describe_comparison(comparison):
    """The numbers of a def:broken comparison as lines of text."""
    lines = []
    lines.append("compared with the last good quote, at " + comparison["before_time"])
    lines.append("1. |iv_t - iv_t-| = |" + show(comparison["iv_now"], 6) + " - " + show(comparison["iv_before"], 6)
                 + "| = " + show(comparison["iv_jump"], 6) + "  > 0.03 ? " + str(comparison["condition1"]))
    lines.append("2. w_t = " + show(comparison["width_now"], 2) + ",  3 w_t- = 3 x " + show(comparison["width_before"], 2)
                 + " = " + show(BROKEN_WIDTH_RATIO * comparison["width_before"], 2) + "  w_t > 3 w_t- ? " + str(comparison["condition2"]))
    lines.append("3. w_t - w_t- = " + show(comparison["width_growth"], 2) + ",  |m_t - m_t-| = " + show(comparison["mid_move"], 2)
                 + "  w_t - w_t- > |m_t - m_t-| ? " + str(comparison["condition3"]))
    return lines


# ======================================================================
# 5. Strategy rules: position delta, exits, prices, deficit
# ======================================================================

def position_delta(long_delta, short_delta):
    """eq:posdelta: delta_pos = 2 (Delta_S long - Delta_S short)."""
    return NUMBER_OF_SPREADS * (long_delta - short_delta)


def exit_tests(delta_now, delta0, dte_now, dte0, profit_band):
    """
    def:exits and eq:gamma-exit, tested in the order loss, profit, gamma (G1):
        loss:   delta_pos >= delta0 + 0.10
        profit: delta_pos <= delta0 - band (0.10 base, 0.15 p15)
        gamma:  tau <= max(tau0 / 2, 10 days), in whole days (G10)
    Returns a dictionary with the levels, the three tests and the recorded reason.
    """
    result = {}
    result["loss_level"] = delta0 + LOSS_BAND
    result["profit_level"] = delta0 - profit_band
    result["gamma_days"] = max(dte0 / 2.0, GAMMA_FLOOR_DAYS)
    result["loss"] = delta_now >= result["loss_level"]
    result["profit"] = delta_now <= result["profit_level"]
    # dte is a whole number, so dte <= 23.5 is the same as dte <= 23 (G10: rounding down)
    result["gamma"] = dte_now <= result["gamma_days"]
    result["reason"] = "none"
    for name in EXIT_ORDER:                            # the first that holds is recorded (G1)
        if result[name]:
            result["reason"] = name
            break
    return result


def price_to_close(short_quote, long_quote, execution):
    """
    sec:costs: closing buys back the sold put and sells the bought put, two of each.
        mid:   cost = 2 (mid_short - mid_long)
        cross: cost = 2 (ask_short - bid_long)   (buy at the ask, sell at the bid)
    In index points.
    """
    if execution == "mid":
        return NUMBER_OF_SPREADS * (short_quote["mid"] - long_quote["mid"])
    return NUMBER_OF_SPREADS * (short_quote["ask"] - long_quote["bid"])


def credit_to_open(short_quote, long_quote, execution):
    """
    sec:costs, G6: opening sells the higher put and buys the lower one, two of each.
        mid:   credit = 2 (mid_short - mid_long)
        cross: credit = 2 (bid_short - ask_long)
    In index points.
    """
    if execution == "mid":
        return NUMBER_OF_SPREADS * (short_quote["mid"] - long_quote["mid"])
    return NUMBER_OF_SPREADS * (short_quote["bid"] - long_quote["ask"])


def value_at_mid(short_quote, long_quote):
    """S28: the open position valued at the midpoints, 2 (mid_short - mid_long), also in the runs crossing the spread."""
    return NUMBER_OF_SPREADS * (short_quote["mid"] - long_quote["mid"])


def update_deficit(deficit, pnl):
    """
    def:deficit, with pi the P&L of the cycle in index points (G17: at execution):
        pi >= L        -> L = 0
        0 <= pi < L    -> L = L - pi
        pi < 0         -> L = -pi  (any earlier deficit dropped)
    Returns (new deficit, which case applied as text).
    """
    if pnl < 0:
        return -pnl, "pi < 0, so L = -pi (the earlier deficit is dropped)"
    if pnl >= deficit:
        return 0.0, "pi >= L, so L = 0"
    return deficit - pnl, "0 <= pi < L, so L = L - pi"


def gamma_exit_day(expiration, dte0):
    """
    eq:gamma-exit: the first day with dte <= max(dte0 / 2, 10). Since dte counts
    calendar days to expiry, that is the calendar date expiry - floor(max(dte0/2, 10)).
    If it falls on a Saturday or Sunday, the first test is on the Monday after.
    (Holidays are not known here: if the date is a market holiday, the next trading day.)
    Returns (gamma days, calendar date text, first weekday text).
    """
    gamma_days = max(dte0 / 2.0, GAMMA_FLOOR_DAYS)
    whole_days = math.floor(gamma_days)                 # G10: whole days, rounding down
    exit_date = to_date(expiration) - datetime.timedelta(days=whole_days)   # timedelta = a number of days
    first_weekday = exit_date
    while first_weekday.weekday() >= 5:                  # weekday(): Monday = 0 ... Saturday = 5, Sunday = 6
        first_weekday = first_weekday + datetime.timedelta(days=1)
    return gamma_days, exit_date.isoformat(), first_weekday.isoformat()


# ======================================================================
# 6. Opening a position (def:entry, def:tau-star, G2-G8, G15)
# ======================================================================

def nearest_put(puts_of_slice, target):
    """
    def:entry, G2: the listed put nearest in strike to the target. Only puts with a
    delta and a mid count (G12: a put without a delta is not usable).
    CHOICE on a tie (two strikes equally near): the lower strike, and the tie is reported.
    Returns (quote or None, tie True/False).
    """
    best = None
    best_distance = None
    tie = False
    for quote in puts_of_slice:
        if quote["delta"] is None or quote["mid"] is None:
            continue                                     # not usable
        distance = abs(quote["strike"] - target)
        if best is None or distance < best_distance:
            best = quote
            best_distance = distance
            tie = False
        elif distance == best_distance:                  # equally near: keep the lower strike, note the tie
            tie = True
            if quote["strike"] < best["strike"]:
                best = quote
    return best, tie


def build_spread(expiry, puts_by_slice, execution):
    """
    For one listed expiry: the target strikes (eq:strikes), the snapped strikes, the
    credit c(tau) at execution (G6), the entry delta and the margin (G15).
    Returns a dictionary; 'problem' is None when the expiry can be used, else the
    reason why it is skipped (G7, G3).
    """
    spread = {}
    spread["root"] = expiry["root"]
    spread["expiration"] = expiry["expiration"]
    spread["dte"] = expiry["dte"]
    spread["forward"] = expiry["forward"]
    spread["atm"] = expiry["atm"]
    spread["problem"] = None
    if expiry["forward"] is None or expiry["atm"] is None:          # G7: skipped
        spread["problem"] = "no forward or no ATM vol (G7)"
        return spread
    tau = tau_in_years(expiry["dte"])                               # def:tau-conv
    sigma_sqrt_tau = expiry["atm"] * math.sqrt(tau)                  # sigma sqrt(tau)
    spread["tau"] = tau
    spread["sigma_sqrt_tau"] = sigma_sqrt_tau
    spread["target_short"] = expiry["forward"] * math.exp(-SHORT_OFFSET * sigma_sqrt_tau)   # F e^{-sigma sqrt tau}
    spread["target_long"] = expiry["forward"] * math.exp(-LONG_OFFSET * sigma_sqrt_tau)     # F e^{-2.3 sigma sqrt tau}
    slice_key = (expiry["root"], expiry["expiration"])
    puts_of_slice = []
    if slice_key in puts_by_slice:
        puts_of_slice = puts_by_slice[slice_key]
    short_quote, short_tie = nearest_put(puts_of_slice, spread["target_short"])
    long_quote, long_tie = nearest_put(puts_of_slice, spread["target_long"])
    spread["short_tie"] = short_tie
    spread["long_tie"] = long_tie
    if short_quote is None or long_quote is None:                   # G7: a strike cannot be snapped
        spread["problem"] = "no usable put to snap to (G7)"
        return spread
    spread["short"] = short_quote
    spread["long"] = long_quote
    if short_quote["strike"] <= long_quote["strike"]:               # G3: the snapped strikes must differ
        spread["problem"] = "snapped strikes coincide or are reversed (G3)"
        return spread
    spread["credit"] = credit_to_open(short_quote, long_quote, execution)
    spread["entry_delta"] = position_delta(long_quote["delta"], short_quote["delta"])
    spread["width"] = short_quote["strike"] - long_quote["strike"]   # one spread, index points
    # G15: margin = (2 x width - credit) x 100 dollars
    spread["margin"] = (NUMBER_OF_SPREADS * spread["width"] - spread["credit"]) * DOLLARS_PER_POINT
    return spread


def expiry_order(expiry):
    """Sort key for expiries: by days to expiry, and on the same date SPX, SPXQ, SPXW (G4)."""
    rank = 9                                           # any other root after these three
    if expiry["root"] in ROOT_ORDER:
        rank = ROOT_ORDER[expiry["root"]]
    return (expiry["dte"], rank, expiry["root"])


def spread_line(spread):
    """One line of the table of candidate expiries."""
    text = spread["root"] + " " + spread["expiration"] + "  dte " + str(spread["dte"])
    text = text + "  F " + show(spread["forward"], 3) + "  sigma_atm " + show(spread["atm"], 6)
    if "target_short" in spread:
        text = text + "  targets " + show(spread["target_short"], 2) + " / " + show(spread["target_long"], 2)
    if "short" in spread:
        text = text + "  snapped " + show(spread["short"]["strike"], 1) + " / " + show(spread["long"]["strike"], 1)
    if "credit" in spread:
        text = text + "  credit " + show(spread["credit"], 4)
    if spread["problem"] is not None:
        text = text + "  SKIPPED: " + spread["problem"]
    return text


def choose_new_position(expiries, puts_by_slice, deficit, execution, lines):
    """
    def:entry and def:tau-star:
      L = 0: the shortest listed expiry with at least 30 days (tau30)      -> rule 'target'
      L > 0: the shortest expiry with 30 <= dte <= 90 and c >= c(tau30) + L -> rule 'recovery'
             if none qualifies, the longest listed expiry of at most 90 days -> rule 'cap'
    Expiries that cannot be used are skipped (G7). With no expiry of 30 days or more,
    no position is opened (G8). Prints the steps into 'lines'.
    Returns (chosen spread or None, rule text).
    """
    ordered = sorted(expiries, key=expiry_order)       # sorted(..., key=f) sorts by the value f gives each item

    # Build the spread of every expiry with at least 30 days, up to 90 days
    # (and beyond 90 only until tau30 is found, in case it lies beyond 90).
    spreads = []
    tau30 = None
    for expiry in ordered:
        if expiry["dte"] < TARGET_DAYS:
            continue                                   # below 30 days: never a candidate
        if expiry["dte"] > CAP_DAYS and tau30 is not None:
            break                                      # beyond the cap and tau30 known: nothing more needed
        spread = build_spread(expiry, puts_by_slice, execution)
        spreads.append(spread)
        if tau30 is None and spread["problem"] is None:
            tau30 = spread                             # the first usable expiry with >= 30 days

    table = []
    for spread in spreads:
        table.append(spread_line(spread))
    add_step(lines, "5a. Candidate expiries (30 days or more), in the order of G4",
             "def:entry, def:tau-star, G4 (same date: SPX, SPXQ, SPXW), G5 (whole days), G6 (credit at execution), G7 (skip)",
             "K_short = F exp(-1.0 sigma sqrt(tau)),  K_long = F exp(-2.3 sigma sqrt(tau)),  tau = dte/365;  "
             + "snapped to the nearest listed put with a delta;  c(tau) = 2 (price short - price long)",
             table, str(len(spreads)) + " candidate expiries built")

    if tau30 is None:                                  # G8: no expiry with 30 days or more that can be used
        add_step(lines, "5b. Maturity", "G8", "tau30 = shortest listed expiry with dte >= 30",
                 ["no usable expiry with 30 days or more"], "NO POSITION OPENED (next attempt at the next snapshot)")
        return None, "none"

    if deficit <= 0:
        add_step(lines, "5b. Maturity (no deficit)", "def:entry, def:tau-star (L = 0)",
                 "tau* = tau30 = the shortest listed expiry with at least 30 days",
                 ["L = " + show(deficit, 4), "tau30 = " + tau30["root"] + " " + tau30["expiration"] + " (" + str(tau30["dte"]) + " days)"],
                 "rule 'target': " + tau30["root"] + " " + tau30["expiration"])
        return tau30, "target"

    needed = tau30["credit"] + deficit                 # c(tau30) + L
    checks = []
    chosen = None
    for spread in spreads:
        if spread["problem"] is not None:
            continue
        if spread["dte"] < TARGET_DAYS or spread["dte"] > CAP_DAYS:
            continue
        qualifies = spread["credit"] >= needed
        checks.append(spread["root"] + " " + spread["expiration"] + " (" + str(spread["dte"]) + " d): c = "
                      + show(spread["credit"], 4) + " >= " + show(needed, 4) + " ? " + str(qualifies))
        if qualifies:
            chosen = spread
            break                                      # the shortest that qualifies
    if chosen is not None:
        add_step(lines, "5b. Maturity (deficit to recover)", "def:tau-star (L > 0), eq:tau-star",
                 "tau* = min{ tau : 30 <= dte <= 90, c(tau) >= c(tau30) + L }",
                 ["L = " + show(deficit, 4) + ",  c(tau30) = " + show(tau30["credit"], 4) + " (" + tau30["root"] + " " + tau30["expiration"] + ")",
                  "c(tau30) + L = " + show(needed, 4)] + checks,
                 "rule 'recovery': " + chosen["root"] + " " + chosen["expiration"])
        return chosen, "recovery"

    # The cap: the longest listed expiry of at most 90 days (on a tie of dates, the first root of G4).
    longest = None
    for spread in spreads:
        if spread["problem"] is not None or spread["dte"] > CAP_DAYS:
            continue
        if longest is None or spread["dte"] > longest["dte"]:
            longest = spread                           # strictly longer replaces; same date keeps the earlier root
    if longest is None:
        add_step(lines, "5b. Maturity (deficit, cap)", "def:tau-star", "longest listed expiry <= 90 days",
                 ["no usable expiry of at most 90 days"], "NO POSITION OPENED")
        return None, "none"
    add_step(lines, "5b. Maturity (deficit to recover, none qualifies)", "def:tau-star (L > 0): the cap of 90 days",
             "no tau with c(tau) >= c(tau30) + L, so tau* = the longest listed expiry of at most 90 days",
             ["L = " + show(deficit, 4) + ",  c(tau30) = " + show(tau30["credit"], 4) + " (" + tau30["root"] + " " + tau30["expiration"] + ")",
              "c(tau30) + L = " + show(needed, 4)] + checks,
             "rule 'cap': " + longest["root"] + " " + longest["expiration"])
    return longest, "cap"


def print_new_position(spread, rule, deficit, run_name, check_time, quotes_by_put, leg_statuses, lines, answers):
    """Print the details of the new position (strikes, credit, entry delta, gamma exit, margin) and store the answers."""
    short_quote = spread["short"]
    long_quote = spread["long"]
    execution = run_name.split("_")[1]                 # 'base_mid' -> ['base', 'mid'] -> 'mid'

    add_step(lines, "5c. Target strikes", "def:entry, eq:strikes",
             "K_short = F exp(-1.0 sigma sqrt(tau)),  K_long = F exp(-2.3 sigma sqrt(tau))",
             ["F = " + show(spread["forward"], 6) + ",  sigma = sigma_atm = " + show(spread["atm"], 6)
              + ",  tau = " + str(spread["dte"]) + "/365 = " + show(spread["tau"], 6),
              "sigma sqrt(tau) = " + show(spread["sigma_sqrt_tau"], 6),
              "K_short = " + show(spread["forward"], 6) + " x exp(-" + show(spread["sigma_sqrt_tau"], 6) + ") = " + show(spread["target_short"], 4),
              "K_long  = " + show(spread["forward"], 6) + " x exp(-2.3 x " + show(spread["sigma_sqrt_tau"], 6) + ") = " + show(spread["target_long"], 4)],
             "targets " + show(spread["target_short"], 4) + " (sold) and " + show(spread["target_long"], 4) + " (bought)")

    tie_text = ""
    if spread["short_tie"] or spread["long_tie"]:
        tie_text = "  TIE: two strikes equally near (lower strike taken)"
    add_step(lines, "5d. Snapped strikes", "def:entry, G2 (nearest in strike, among puts with a delta)",
             "nearest listed put to each target",
             ["sold:   " + show(short_quote["strike"], 1) + " (distance " + show(abs(short_quote["strike"] - spread["target_short"]), 4) + ")",
              "bought: " + show(long_quote["strike"], 1) + " (distance " + show(abs(long_quote["strike"] - spread["target_long"]), 4) + ")"],
             "sell 2 x " + show(short_quote["strike"], 1) + " put, buy 2 x " + show(long_quote["strike"], 1) + " put, "
             + spread["root"] + " " + spread["expiration"] + tie_text)

    # The broken test of the new legs (G11: against each put's own last good quote).
    broken_lines = []
    # The loop runs twice: first leg_name = "sold" and quote = the sold put, then the bought put.
    for leg_name, quote in [("sold", short_quote), ("bought", long_quote)]:
        key = put_key(quote["root"], quote["expiration"], quote["strike"])
        if key in leg_statuses and check_time in leg_statuses[key]:
            status, comparison = leg_statuses[key][check_time]
            broken_lines.append(leg_name + " put: status '" + status + "' (its history is in legs.csv)")
        else:
            broken_lines.append(leg_name + " put: not testable here, the packet has no earlier quote of this put")
    add_step(lines, "5e. Broken test of the new legs", "sec:broken-quotes, G11 (a put about to be opened: against its own last good quote)",
             "def:broken", broken_lines, "see numbers (an open question if not testable)")

    if execution == "mid":
        credit_formula = "c = 2 (mid_short - mid_long)"
        credit_numbers = "2 x (" + show(short_quote["mid"], 4) + " - " + show(long_quote["mid"], 4) + ")"
    else:
        credit_formula = "c = 2 (bid_short - ask_long)  (sold at the bid, bought at the ask)"
        credit_numbers = "2 x (" + show(short_quote["bid"], 4) + " - " + show(long_quote["ask"], 4) + ")"
    add_step(lines, "5f. Credit", "sec:costs, G6 (at the execution price of the run: " + execution + ")",
             credit_formula,
             ["sold put   bid " + show(short_quote["bid"], 2) + "  ask " + show(short_quote["ask"], 2) + "  mid " + show(short_quote["mid"], 4),
              "bought put bid " + show(long_quote["bid"], 2) + "  ask " + show(long_quote["ask"], 2) + "  mid " + show(long_quote["mid"], 4),
              credit_numbers],
             "credit = " + show(spread["credit"], 4) + " index points")

    add_step(lines, "5g. Entry delta", "sec:entry-delta, eq:posdelta (packet deltas, sticky strike)",
             "Delta0 = 2 (Delta_S long - Delta_S short)",
             ["2 x (" + show(long_quote["delta"], 6) + " - (" + show(short_quote["delta"], 6) + "))"],
             "Delta0 = " + show(spread["entry_delta"], 6))

    gamma_days, exit_date, first_weekday = gamma_exit_day(spread["expiration"], spread["dte"])
    add_step(lines, "5h. Gamma exit day", "eq:gamma-exit, G10 (whole days)",
             "tau_exit = max(tau0 / 2, 10 days); first day with dte <= tau_exit = expiry - floor(tau_exit)",
             ["tau0 = " + str(spread["dte"]) + " days,  tau0/2 = " + show(spread["dte"] / 2.0, 1) + ",  tau_exit = " + show(gamma_days, 1) + " days",
              spread["expiration"] + " - " + str(math.floor(gamma_days)) + " days = " + exit_date],
             "gamma exit at the first snapshot (not the stock close) of " + first_weekday
             + " (or the next trading day if that is a holiday)")

    add_step(lines, "5i. Margin", "sec:cash, G15",
             "margin = (2 x width - credit) x 100 dollars, width = K_short - K_long",
             ["width = " + show(short_quote["strike"], 1) + " - " + show(long_quote["strike"], 1) + " = " + show(spread["width"], 1),
              "(2 x " + show(spread["width"], 1) + " - " + show(spread["credit"], 4) + ") x 100"],
             "margin = " + show(spread["margin"], 2) + " dollars")

    answers["new_root"] = spread["root"]
    answers["new_expiry"] = spread["expiration"]
    answers["new_dte"] = str(spread["dte"])
    answers["maturity_rule"] = rule
    answers["target_short"] = show(spread["target_short"], 4)
    answers["target_long"] = show(spread["target_long"], 4)
    answers["strike_short"] = show(short_quote["strike"], 1)
    answers["strike_long"] = show(long_quote["strike"], 1)
    answers["credit"] = show(spread["credit"], 4)
    answers["entry_delta"] = show(spread["entry_delta"], 6)
    answers["gamma_exit_days"] = show(gamma_days, 1)
    answers["gamma_exit_day"] = first_weekday
    answers["margin"] = show(spread["margin"], 2)


# ======================================================================
# 7. The rates (sec:rates) and the interest (sec:cash, G14)
# ======================================================================

def simple_to_continuous(simple_rate, days):
    """eq:rate-conversion: r_cont = log(1 + r_simple tau) / tau, tau = days / 365."""
    tau = days / 365.0
    return math.log(1.0 + simple_rate * tau) / tau


def latest_rate(rate_rows, column, day):
    """
    The value of one FRED series on a day, as a fraction (per cent / 100).
    Holidays are forward-filled (sec:rates): the last value on or before the day.
    Returns (rate, date of the value used).
    """
    found_value = None
    found_date = None
    for row in rate_rows:                              # the rows are in date order
        if row["observation_date"] > day:              # dates 'YYYY-MM-DD' compare correctly as text
            break
        value = number_or_none(row[column])
        if value is not None:
            found_value = value
            found_date = row["observation_date"]
    if found_value is None:
        raise ValueError("no " + column + " rate on or before " + day)
    return found_value / 100.0, found_date


def rate_for_days(rate_rows, day, days):
    """
    sec:rates: the continuous rate for an option with 'days' to expiry, on one day.
    Each of the four yields is converted with its own maturity (eq:rate-conversion),
    then interpolated linearly in days; below 30 days the 1-month rate.
    CHOICE: convert first, then interpolate; maturities 30 / 91 / 182 / 365 days.
    Returns (rate, list of text lines describing the steps).
    """
    continuous = []
    notes = []
    for position in range(len(RATE_COLUMNS)):
        simple, used_date = latest_rate(rate_rows, RATE_COLUMNS[position], day)
        rate = simple_to_continuous(simple, RATE_DAYS[position])
        continuous.append(rate)
        notes.append(RATE_COLUMNS[position] + " of " + used_date + ": " + show(simple * 100, 2) + "% simple -> "
                     + show(rate * 100, 5) + "% continuous (" + str(RATE_DAYS[position]) + " days)")
    if days <= RATE_DAYS[0]:                           # below (or at) 1 month: the 1-month rate
        notes.append(str(days) + " days <= 30: the 1-month rate")
        return continuous[0], notes
    if days >= RATE_DAYS[-1]:                          # [-1] = the last element
        notes.append(str(days) + " days >= 365: the 12-month rate")
        return continuous[-1], notes
    for position in range(len(RATE_DAYS) - 1):
        left_days = RATE_DAYS[position]
        right_days = RATE_DAYS[position + 1]
        if left_days <= days <= right_days:            # days lies between the two maturities (both ends included)
            weight = (days - left_days) / (right_days - left_days)   # 0 at the left point, 1 at the right
            rate = continuous[position] + weight * (continuous[position + 1] - continuous[position])
            notes.append(str(days) + " days: linear between " + str(left_days) + " and " + str(right_days)
                         + " days, weight " + show(weight, 4) + " -> " + show(rate * 100, 5) + "%")
            return rate, notes
    raise ValueError("rate interpolation failed")


# ======================================================================
# 8. Steps 1-5 for one snapshot
# ======================================================================

def check_one_snapshot(hand_check, run_name, snapshot, deep, folder, lines, answers):
    """Steps 1 to 5 (and 7 for deep checks) for one hand check at one snapshot."""
    variant = run_name.split("_")[0]                   # 'p15_mid' -> 'p15'
    execution = run_name.split("_")[1]                 # 'p15_mid' -> 'mid'
    profit_band = PROFIT_BAND[variant]

    calendar = read_calendar(folder)
    positions, deficit_without_position, header_lines = read_positions(folder)
    quotes_by_put = read_leg_quotes(folder)

    # The state before the snapshot (from the backtest's logs, README "What is in a packet").
    lines.append("")
    lines.append("STATE BEFORE THE SNAPSHOT (given by the packet)")
    for line in header_lines:
        lines.append("  " + line)
    position = None
    if len(positions) > 0:
        position = positions[0]
        for key in position:
            lines.append("  " + key + ": " + str(position[key]))
        deficit = position["deficit_at_entry"]         # README: the deficit changes only when a position closes
    else:
        deficit = deficit_without_position
    answers["deficit_before"] = show(deficit, 4)
    lines.append("  run: " + run_name + "  (profit band " + show(profit_band, 2) + ", loss band " + show(LOSS_BAND, 2)
                 + ", execution at " + execution + ")")

    # ---- Step 1: is a decision allowed? ----------------------------------
    day = date_of(snapshot)
    last_clock = calendar[day]
    close_clock = stock_close_clock(last_clock)
    decision_allowed = clock_of(snapshot) != close_clock
    early = ""
    if last_clock == "13:15:00":
        early = " (early-close day: last snapshot 13:15)"
    if decision_allowed:
        result = "decision allowed: YES"
        answers["decision_allowed"] = "yes"
    else:
        result = "decision allowed: NO (the stock close: no exit, no entry)"
        answers["decision_allowed"] = "no"
    add_step(lines, "1. Is a decision allowed?", "sec:monitoring (no position opened or closed at the stock close), S19",
             "decision allowed unless the snapshot is 16:00, or 13:00 on an early-close day",
             ["snapshot " + clock_of(snapshot) + " on " + day + ", last snapshot of the day " + last_clock + early,
              "stock close of the day: " + close_clock],
             result)

    exit_reason = "none"
    legs_ok = True
    leg_statuses = {}

    if position is not None:
        short_key = put_key(position["root"], position["expiration"], position["strike_short"])
        long_key = put_key(position["root"], position["expiration"], position["strike_long"])
        for key in quotes_by_put:
            leg_statuses[key] = classify_put_quotes(quotes_by_put[key], calendar)
        short_quote = quote_at(quotes_by_put, short_key, snapshot)
        long_quote = quote_at(quotes_by_put, long_key, snapshot)

        # ---- Step 2: are both legs usable and not broken? -----------------
        step_numbers = []
        broken_names = []
        usable_names = []
        # The loop runs twice: once with the three names set to the sold put's values,
        # once with the bought put's (each (...) is one group of three values).
        for leg_name, key, quote in [("sold", short_key, short_quote), ("bought", long_key, long_quote)]:
            label = leg_name + " put " + key[0] + " " + key[1] + " " + show(key[2], 1)
            if quote is None:
                step_numbers.append(label + ": NO ROW at this snapshot (not quoted, G12)")
                continue
            step_numbers.append(label + ": bid " + show(quote["bid"], 2) + " ask " + show(quote["ask"], 2) + " mid " + show(quote["mid"], 4)
                                + " iv " + show(quote["iv"], 6) + " delta " + show(quote["delta"], 6))
            status, comparison = leg_statuses[key][snapshot]
            if status == "no delta":
                step_numbers.append("  -> row without a delta: not usable (G12)")
                continue
            if status == "stock close":
                step_numbers.append("  -> stock-close snapshot: the broken test is not made (no decision here)")
                usable_names.append(leg_name)
                continue
            if status == "first":
                step_numbers.append("  -> no earlier quote in the packet to compare with: taken as good")
                usable_names.append(leg_name)
                continue
            for line in describe_comparison(comparison):
                step_numbers.append("  " + line)
            if status == "broken":
                step_numbers.append("  -> all three hold: BROKEN")
                broken_names.append(leg_name)
            else:
                step_numbers.append("  -> not all three hold: good")
                usable_names.append(leg_name)
        legs_ok = len(usable_names) == 2
        if legs_ok:
            result = "both legs usable and not broken"
        else:
            result = "NOT both legs usable: the position is neither marked nor tested here (sec:backtest-design, sec:broken-quotes), no entry"
        add_step(lines, "2. Are both legs usable and not broken?",
                 "sec:backtest-design, G12 (a row with a delta), def:broken with G11 (against the last good quote, never the stock close)",
                 "broken if |iv_t - iv_t-| > 0.03 and w_t > 3 w_t- and w_t - w_t- > |m_t - m_t-|, w = ask - bid, m = mid",
                 step_numbers, result)
        if legs_ok:
            answers["legs_usable"] = "yes"
        else:
            answers["legs_usable"] = "no"
        if len(broken_names) > 0:
            answers["broken_leg"] = "+".join(broken_names)   # e.g. 'bought' or 'sold+bought'
        else:
            answers["broken_leg"] = "none"

        # ---- Step 3: position delta and exit tests ------------------------
        if short_quote is not None and long_quote is not None and short_quote["delta"] is not None and long_quote["delta"] is not None:
            delta_now = position_delta(long_quote["delta"], short_quote["delta"])
            tests = exit_tests(delta_now, position["delta0"], short_quote["dte"], position["dte0"], profit_band)
            numbers = ["Delta_pos = 2 x (" + show(long_quote["delta"], 6) + " - (" + show(short_quote["delta"], 6) + ")) = " + show(delta_now, 6),
                       "Delta0 = " + show(position["delta0"], 6) + ",  tau0 = " + show(position["dte0"], 0) + " days,  tau now = " + str(short_quote["dte"]) + " days",
                       "loss:   Delta_pos >= Delta0 + 0.10 = " + show(tests["loss_level"], 6) + " ? " + str(tests["loss"]),
                       "profit: Delta_pos <= Delta0 - " + show(profit_band, 2) + " = " + show(tests["profit_level"], 6) + " ? " + str(tests["profit"]),
                       "gamma:  tau <= max(tau0/2, 10) = " + show(tests["gamma_days"], 1) + " days ? " + str(tests["gamma"])]
            # A side check: the packet's deltas recomputed from its iv, F, D, S (Black-76, sticky strike).
            for leg_name, quote in [("sold", short_quote), ("bought", long_quote)]:
                recomputed = put_delta_spot(quote["forward"], quote["strike"], tau_in_years(quote["dte"]), quote["iv"], quote["D"], quote["spot"])
                numbers.append("(side check) " + leg_name + " put delta from its iv: D (N(d1) - 1) F/S = " + show(recomputed, 6)
                               + " vs packet " + show(quote["delta"], 6))
            if decision_allowed and legs_ok:
                exit_reason = tests["reason"]
                if exit_reason != "none":
                    result = "exit: " + exit_reason.upper()     # .upper() writes the word in capitals
                else:
                    result = "no trigger holds: the position is kept"
            else:
                result = ("not tested here (no decision at this snapshot); the trigger that would hold: " + tests["reason"])
            add_step(lines, "3. Position delta and exits",
                     "eq:posdelta, def:exits, eq:gamma-exit, G1 (order loss, profit, gamma), G10, sec:robustness (p15)",
                     "Delta_pos = 2 (Delta_S long - Delta_S short); loss Delta_pos >= Delta0 + 0.10; profit Delta_pos <= Delta0 - band; gamma tau <= max(tau0/2, 10)",
                     numbers, result)
            answers["position_delta"] = show(delta_now, 6)
        else:
            add_step(lines, "3. Position delta and exits", "eq:posdelta", "Delta_pos = 2 (Delta_S long - Delta_S short)",
                     ["a leg has no delta at this snapshot"], "cannot be computed: no test")
        answers["delta0"] = show(position["delta0"], 6)
        if decision_allowed and legs_ok:
            answers["exit_reason"] = exit_reason
        else:
            answers["exit_reason"] = "not tested"

        # ---- Step 4: closing ----------------------------------------------
        if exit_reason != "none":
            cost = price_to_close(short_quote, long_quote, execution)
            pnl = position["credit"] - cost
            new_deficit, case_text = update_deficit(deficit, pnl)
            if execution == "mid":
                cost_formula = "cost = 2 (mid_short - mid_long)"
                cost_numbers = "2 x (" + show(short_quote["mid"], 4) + " - " + show(long_quote["mid"], 4) + ")"
            else:
                cost_formula = "cost = 2 (ask_short - bid_long)  (buy back at the ask, sell at the bid)"
                cost_numbers = "2 x (" + show(short_quote["ask"], 4) + " - " + show(long_quote["bid"], 4) + ")"
            add_step(lines, "4a. Cost to close", "sec:costs (execution: " + execution + ")", cost_formula,
                     [cost_numbers], "cost = " + show(cost, 4) + " index points")
            add_step(lines, "4b. P&L of the cycle", "def:deficit (pi = credit received - cost of closing, index points), G17",
                     "pi = credit - cost", [show(position["credit"], 4) + " - " + show(cost, 4)],
                     "pi = " + show(pnl, 4) + " points = " + show(pnl * DOLLARS_PER_POINT, 2) + " dollars")
            add_step(lines, "4c. New deficit", "def:deficit", "pi >= L: L = 0;  0 <= pi < L: L = L - pi;  pi < 0: L = -pi",
                     ["L before = " + show(deficit, 4) + ",  pi = " + show(pnl, 4), case_text],
                     "new L = " + show(new_deficit, 4))
            answers["exit_cost"] = show(cost, 4)
            answers["pnl"] = show(pnl, 4)
            answers["new_deficit"] = show(new_deficit, 4)
            deficit = new_deficit

    # ---- Step 5: a new position? -------------------------------------------
    open_new = decision_allowed and (position is None or (legs_ok and exit_reason != "none"))
    if open_new:
        lines.append("")
        lines.append("5. NEW POSITION at the same snapshot (sec:strategy, S12), deficit L = " + show(deficit, 4))
        expiries = read_expiries(folder)
        puts_by_slice = read_puts_by_slice(folder)
        spread, rule = choose_new_position(expiries, puts_by_slice, deficit, execution, lines)
        if spread is not None:
            print_new_position(spread, rule, deficit, run_name, snapshot, quotes_by_put, leg_statuses, lines, answers)
            answers["_new_spread"] = spread            # kept for the deep check (not written to the CSV)
        else:
            answers["maturity_rule"] = "none"
    else:
        lines.append("")
        if not decision_allowed:
            lines.append("5. No new position: no decision at the stock close.")
        elif position is not None and not legs_ok:
            lines.append("5. No new position: a leg is missing or broken, nothing is decided at this snapshot.")
        else:
            lines.append("5. No new position: the position open before is kept.")

    # ---- Context: the position at every packet snapshot since its entry ------
    if position is not None:
        print_context(position, quotes_by_put, leg_statuses, calendar, snapshot, profit_band, lines)

    # ---- Step 7: deep check --------------------------------------------------
    if deep == "yes":
        deep_check(folder, snapshot, calendar, position, quotes_by_put, answers, lines)


def print_context(position, quotes_by_put, leg_statuses, calendar, snapshot, profit_band, lines):
    """
    Context only (not a step of the check): the position delta and the trigger that
    would hold at every snapshot of the packet from the entry up to the check.
    """
    short_key = put_key(position["root"], position["expiration"], position["strike_short"])
    long_key = put_key(position["root"], position["expiration"], position["strike_long"])
    times = []
    if short_key in quotes_by_put:
        for quote in quotes_by_put[short_key]:
            times.append(quote["time"])
    if long_key in quotes_by_put:
        for quote in quotes_by_put[long_key]:
            if quote["time"] not in times:
                times.append(quote["time"])
    times.sort()                                        # time order (text sorts correctly)
    lines.append("")
    lines.append("CONTEXT (not part of the check): the position at each snapshot of the packet from its entry ("
                 + position["entry_time"] + ") up to the check")
    lines.append("  time                 short status   long status    Delta_pos   trigger that holds")
    for time in times:
        if time < position["entry_time"] or time > snapshot:
            continue
        short_quote = quote_at(quotes_by_put, short_key, time)
        long_quote = quote_at(quotes_by_put, long_key, time)
        short_status = "missing"
        long_status = "missing"
        if short_quote is not None:
            short_status = leg_statuses[short_key][time][0]
        if long_quote is not None:
            long_status = leg_statuses[long_key][time][0]
        delta_text = "-"
        trigger = "-"
        if short_quote is not None and long_quote is not None and short_quote["delta"] is not None and long_quote["delta"] is not None:
            delta_now = position_delta(long_quote["delta"], short_quote["delta"])
            delta_text = show(delta_now, 6)
            if time > position["entry_time"]:          # no test at the entry snapshot itself (S12)
                tests = exit_tests(delta_now, position["delta0"], short_quote["dte"], position["dte0"], profit_band)
                trigger = tests["reason"]
            else:
                trigger = "(entry)"
        lines.append("  " + time + "  " + short_status.ljust(13) + "  " + long_status.ljust(13) + "  "
                     + delta_text.rjust(9) + "   " + trigger)   # ljust / rjust pad the text with spaces to a width


# ======================================================================
# 9. Step 6: the equity day
# ======================================================================

def last_usable_snapshot(position, quotes_by_put, leg_statuses, day, until_time):
    """
    G13: the last snapshot of a day, up to 'until_time', where both legs have a row
    with a delta and neither is broken, never the stock close.
    Returns (time, short quote, long quote) or (None, None, None).
    """
    short_key = put_key(position["root"], position["expiration"], position["strike_short"])
    long_key = put_key(position["root"], position["expiration"], position["strike_long"])
    best = (None, None, None)
    if short_key not in quotes_by_put:
        return best
    for short_quote in quotes_by_put[short_key]:       # in time order
        time = short_quote["time"]
        if date_of(time) != day or time > until_time:
            continue
        long_quote = quote_at(quotes_by_put, long_key, time)
        if long_quote is None:
            continue
        short_status = leg_statuses[short_key][time][0]
        long_status = leg_statuses[long_key][time][0]
        good = ["good", "first"]
        if short_status in good and long_status in good:
            best = (time, short_quote, long_quote)     # later ones overwrite earlier ones
    return best


def equity_day(hand_check, run_name, folder, lines, answers):
    """
    Step 6 (S28, sec:results-main, sec:cash, G13, G14): the P&L of one trading day.
      day P&L = realised P&L + change in value of the open position + interest
    The open position is valued at the midpoints of its puts at the last usable
    snapshot of the day (G13), also in the runs crossing the spread.
    """
    variant = run_name.split("_")[0]
    execution = run_name.split("_")[1]
    profit_band = PROFIT_BAND[variant]
    calendar = read_calendar(folder)
    positions, deficit_without_position, header_lines = read_positions(folder)
    quotes_by_put = read_leg_quotes(folder)
    leg_statuses = {}
    for key in quotes_by_put:
        leg_statuses[key] = classify_put_quotes(quotes_by_put[key], calendar)

    day = None
    previous_day = None
    for line in header_lines:
        if line.startswith("Hand check of the day "):
            day = line[len("Hand check of the day "):len("Hand check of the day ") + 10]
        if line.startswith("The trading day before: "):
            previous_day = line[len("The trading day before: "):].strip()
    lines.append("")
    lines.append("THE EQUITY DAY " + day + " (trading day before: " + previous_day + "), run " + run_name)
    for position in positions:
        lines.append("  position " + position["root"] + " " + position["expiration"] + " " + show(position["strike_short"], 1)
                     + "/" + show(position["strike_long"], 1) + ": entry " + position["entry_time"] + ", exit " + position["exit_time"]
                     + ", credit " + show(position["credit"], 2) + ", margin " + show(position["margin"], 2)
                     + ", Delta0 " + show(position["delta0"], 6) + ", tau0 " + show(position["dte0"], 0))

    start_of_day = day + " 00:00:00"
    end_of_day = day + " 23:59:59"
    total_points = 0.0                                  # the day's P&L of the positions, in index points
    end_position = None                                 # the position open at the end of the day
    end_unrealised = None

    for position in positions:
        name = position["root"] + " " + position["expiration"] + " " + show(position["strike_short"], 1) + "/" + show(position["strike_long"], 1)
        short_key = put_key(position["root"], position["expiration"], position["strike_short"])
        long_key = put_key(position["root"], position["expiration"], position["strike_long"])
        opened_today = date_of(position["entry_time"]) == day
        closed_today = date_of(position["exit_time"]) == day
        numbers = []

        # The value at the start of the day (the previous day's mark), or the credit if opened today.
        if opened_today:
            entry_short = quote_at(quotes_by_put, short_key, position["entry_time"])
            entry_long = quote_at(quotes_by_put, long_key, position["entry_time"])
            recomputed_credit = credit_to_open(entry_short, entry_long, execution)
            start_value = position["credit"]            # the credit received (the position starts at value 0 for us)
            numbers.append("opened today at " + position["entry_time"] + ": credit received " + show(position["credit"], 4)
                           + " (recomputed from the quotes at " + execution + ": " + show(recomputed_credit, 4) + ")")
            start_text = "credit " + show(position["credit"], 4)
        else:
            mark_time, mark_short, mark_long = last_usable_snapshot(position, quotes_by_put, leg_statuses, previous_day, previous_day + " 23:59:59")
            previous_mark = value_at_mid(mark_short, mark_long)
            numbers.append("held at the start of the day: previous mark at " + mark_time + " (G13, last usable snapshot)")
            numbers.append("  value = 2 (mid_short - mid_long) = 2 x (" + show(mark_short["mid"], 4) + " - " + show(mark_long["mid"], 4)
                           + ") = " + show(previous_mark, 4))
            start_value = previous_mark
            start_text = "previous mark " + show(previous_mark, 4)

        if closed_today:
            # Check the exit: the trigger at each decision snapshot of the day up to the exit.
            numbers.append("exit trigger at each decision snapshot of the day up to the exit:")
            for short_quote in quotes_by_put[short_key]:
                time = short_quote["time"]
                if time < start_of_day or time > position["exit_time"] or time <= position["entry_time"]:
                    continue
                if is_stock_close(time, calendar):
                    continue
                long_quote = quote_at(quotes_by_put, long_key, time)
                if long_quote is None or short_quote["delta"] is None or long_quote["delta"] is None:
                    numbers.append("  " + time + "  a leg missing: no test")
                    continue
                if leg_statuses[short_key][time][0] == "broken" or leg_statuses[long_key][time][0] == "broken":
                    numbers.append("  " + time + "  a leg broken: no test")
                    continue
                delta_now = position_delta(long_quote["delta"], short_quote["delta"])
                tests = exit_tests(delta_now, position["delta0"], short_quote["dte"], position["dte0"], profit_band)
                numbers.append("  " + time + "  Delta_pos " + show(delta_now, 6) + "  (loss level " + show(tests["loss_level"], 6)
                               + ", profit level " + show(tests["profit_level"], 6) + ", gamma " + show(tests["gamma_days"], 1)
                               + " d, tau " + str(short_quote["dte"]) + " d) -> " + tests["reason"])
            exit_short = quote_at(quotes_by_put, short_key, position["exit_time"])
            exit_long = quote_at(quotes_by_put, long_key, position["exit_time"])
            cost = price_to_close(exit_short, exit_long, execution)
            pnl_cycle = position["credit"] - cost
            numbers.append("closed at " + position["exit_time"] + ": cost to close at " + execution + " = " + show(cost, 4)
                           + ", realised P&L of the cycle = " + show(position["credit"], 4) + " - " + show(cost, 4) + " = " + show(pnl_cycle, 4))
            end_value = cost
            end_text = "cost to close " + show(cost, 4)
        else:
            mark_time, mark_short, mark_long = last_usable_snapshot(position, quotes_by_put, leg_statuses, day, end_of_day)
            end_mark = value_at_mid(mark_short, mark_long)
            numbers.append("open at the end of the day: mark at " + mark_time + " (G13, last usable snapshot, at mid, S28)")
            numbers.append("  value = 2 (mid_short - mid_long) = 2 x (" + show(mark_short["mid"], 4) + " - " + show(mark_long["mid"], 4)
                           + ") = " + show(end_mark, 4))
            end_value = end_mark
            end_text = "end mark " + show(end_mark, 4)
            end_position = position
            end_unrealised = position["credit"] - end_mark
            numbers.append("  unrealised P&L of the cycle = credit - value = " + show(position["credit"], 4) + " - "
                           + show(end_mark, 4) + " = " + show(end_unrealised, 4) + " points")

        # The day's contribution: what the position was worth to us at the start minus at the end.
        # A short position is worth -value; so the P&L = start value - end value
        # (for a position opened today the start 'value' is the credit received).
        contribution = start_value - end_value
        numbers.append("P&L of this position on the day = " + start_text + " - " + end_text + " = " + show(contribution, 4) + " points")
        add_step(lines, "6. Position " + name, "S28, sec:results-main, G13",
                 "day P&L = value at the start of the day (or the credit) - value at the end (or the cost to close)",
                 numbers, show(contribution, 4) + " index points = " + show(contribution * DOLLARS_PER_POINT, 2) + " dollars")
        total_points = total_points + contribution

    # The interest of the day (sec:cash, G14).
    rate_rows = read_table(os.path.join(folder, "rates.csv"))
    simple, used_date = latest_rate(rate_rows, "DGS3MO", day)
    continuous = simple_to_continuous(simple, RATE_DAYS[1])
    days = calendar_days_between(previous_day, day)
    margin_end = end_position["margin"]
    growth = math.exp(continuous * days / 365.0) - 1.0   # continuous compounding over the calendar days
    interest = margin_end * growth
    alternative_margin = None
    for position in positions:                           # the margin held at the end of the day before
        if date_of(position["entry_time"]) < day:
            alternative_margin = position["margin"]
    numbers = ["3-month rate of the day of payment (" + day + ", value of " + used_date + "): " + show(simple * 100, 2) + "% simple",
               "continuous (eq:rate-conversion, 91 days): log(1 + " + show(simple, 6) + " x 91/365) / (91/365) = " + show(continuous * 100, 5) + "%",
               "calendar days from " + previous_day + " to " + day + ": " + str(days),
               "margin of the cycle open at the end of the day: " + show(margin_end, 2) + " dollars (CHOICE, see open questions)",
               "interest = " + show(margin_end, 2) + " x (exp(" + show(continuous, 7) + " x " + str(days) + "/365) - 1)"]
    if alternative_margin is not None and alternative_margin != margin_end:
        alternative_interest = alternative_margin * growth
        numbers.append("(alternative: on the margin held at the end of the day before, " + show(alternative_margin, 2)
                       + " dollars, it would be " + show(alternative_interest, 4) + " dollars)")
    add_step(lines, "6. Interest of the day", "sec:cash, G14 (rate of the day of payment, calendar days, continuous)",
             "interest = margin x (exp(r_cont x days / 365) - 1)", numbers, show(interest, 4) + " dollars")

    day_pnl = total_points * DOLLARS_PER_POINT + interest
    add_step(lines, "6. P&L and margin of the day", "S28, sec:results-main",
             "day P&L = (realised + change in value) x 100 + interest; margin of the day = margin of the cycle open at the end",
             [show(total_points, 4) + " points x 100 + " + show(interest, 4)],
             "day P&L = " + show(day_pnl, 2) + " dollars, margin of the day = " + show(margin_end, 2)
             + " dollars, unrealised P&L of the open cycle = " + show(end_unrealised, 4) + " points")
    answers["day_unrealised_points"] = show(end_unrealised, 4)
    answers["day_pnl_dollars"] = show(day_pnl, 2)
    answers["day_interest_dollars"] = show(interest, 4)
    answers["day_margin"] = show(margin_end, 2)


# ======================================================================
# 10. Step 7: the deep check (chapter 3 redone from raw.csv)
# ======================================================================

def implied_vol(price, F, K, tau, D, option_type):
    """
    sec:iv-impl, rem:bisection: bisection on [0.001, 5] with 60 halvings. A price
    outside eq:noarb-call / eq:noarb-put gets no volatility (None).
    CHOICE: the answer is the midpoint of the last interval.
    """
    if option_type == "P":
        lower = D * max(K - F, 0.0)                    # eq:noarb-put: D (K - F)+ < P < D K
        upper = D * K
    else:
        lower = D * max(F - K, 0.0)                    # eq:noarb-call: D (F - K)+ < C < D F
        upper = D * F
    if not (lower < price < upper):                    # 'lower < price < upper' means both lower < price and price < upper
        return None
    low = IV_LOW
    high = IV_HIGH
    for step in range(IV_HALVINGS):
        middle = 0.5 * (low + high)
        if option_type == "P":
            model = black76_put(F, K, tau, middle, D)
        else:
            model = black76_call(F, K, tau, middle, D)
        if model > price:                              # the price rises with sigma (prop:impvol): too high -> go lower
            high = middle
        else:
            low = middle
    return 0.5 * (low + high)


def determinant3(m):
    """Determinant of a 3x3 matrix given as a list of three rows (rule of Sarrus)."""
    return (m[0][0] * m[1][1] * m[2][2] + m[0][1] * m[1][2] * m[2][0] + m[0][2] * m[1][0] * m[2][1]
            - m[0][2] * m[1][1] * m[2][0] - m[0][0] * m[1][2] * m[2][1] - m[0][1] * m[1][0] * m[2][2])


def quadratic_fit(xs, ys):
    """
    def:atm, eq:atm-fit: unweighted least squares of y = a + b x + c x^2.
    Solves the normal equations
        [n    Sx   Sx2] [a]   [Sy  ]
        [Sx   Sx2  Sx3] [b] = [Sxy ]
        [Sx2  Sx3  Sx4] [c]   [Sx2y]
    by Cramer's rule (each unknown = a determinant ratio). Returns (a, b, c).
    """
    n = len(xs)
    sx = 0.0
    sx2 = 0.0
    sx3 = 0.0
    sx4 = 0.0
    sy = 0.0
    sxy = 0.0
    sx2y = 0.0
    for position in range(n):
        x = xs[position]
        y = ys[position]
        sx = sx + x
        sx2 = sx2 + x * x
        sx3 = sx3 + x * x * x
        sx4 = sx4 + x * x * x * x
        sy = sy + y
        sxy = sxy + x * y
        sx2y = sx2y + x * x * y
    matrix = [[n, sx, sx2], [sx, sx2, sx3], [sx2, sx3, sx4]]
    right = [sy, sxy, sx2y]
    whole = determinant3(matrix)
    answers = []
    for column in range(3):                            # replace one column by the right-hand side
        replaced = []
        for row in range(3):
            new_row = list(matrix[row])                # list(...) makes a copy, so the original stays unchanged
            new_row[column] = right[row]
            replaced.append(new_row)
        answers.append(determinant3(replaced) / whole)
    return answers[0], answers[1], answers[2]


def median(values):
    """The middle value of a list (the mean of the two middle values if the list has an even length)."""
    ordered = sorted(values)
    count = len(ordered)
    if count % 2 == 1:                                 # % = remainder: odd length
        return ordered[count // 2]                     # // = whole-number division
    return 0.5 * (ordered[count // 2 - 1] + ordered[count // 2])


def deep_check(folder, snapshot, calendar, position, quotes_by_put, answers, lines):
    """
    Step 7: redo from raw.csv the cleaning (sec:cleaning), the forward
    (sec:forward-impl), the discount factor (sec:rates), the implied vol and delta
    of both legs (sec:iv-impl, prop:greeks-fwd, prop:chainrule) and the ATM vol
    (def:atm, sec:atm-impl) of the relevant expiries, next to the packet's values.
    """
    lines.append("")
    lines.append("7. DEEP CHECK: the stage-1 and stage-2 values redone from raw.csv")
    day = date_of(snapshot)
    raw_rows = read_table(os.path.join(folder, "raw.csv"))
    rate_rows = read_table(os.path.join(folder, "rates.csv"))
    close_rows = read_table(os.path.join(folder, "index_close.csv"))
    expiries = read_expiries(folder)

    # ---- 7a. The index level S --------------------------------------------
    pairs_seen = []
    for row in raw_rows:
        pair = (row["underlying_bid"], row["underlying_ask"])
        if pair not in pairs_seen:
            pairs_seen.append(pair)
    underlying_bid = float(pairs_seen[0][0])
    underlying_ask = float(pairs_seen[0][1])
    spot_mid = 0.5 * (underlying_bid + underlying_ask)
    is_last = clock_of(snapshot) == calendar[day]
    official_close = None
    for row in close_rows:
        if row["Date"] == day:
            official_close = float(row["Close"])
    if is_last:
        spot = official_close                          # sec:data: at 16:15 (13:15) S is the official close
        spot_rule = "last snapshot of the day: S = the official close " + show(official_close, 4)
    else:
        spot = spot_mid
        spot_rule = "S = (underlying bid + ask) / 2 = (" + show(underlying_bid, 2) + " + " + show(underlying_ask, 2) + ") / 2"
    packet_spot = None
    if len(expiries) > 0:
        packet_spot = expiries[0]["spot"]
    add_step(lines, "7a. Index level S", "sec:data, D2", "S = mid of the underlying; at 16:15 (13:15) the official close",
             [str(len(pairs_seen)) + " different underlying bid/ask pair(s) in raw.csv", spot_rule],
             "S = " + show(spot, 4) + "   packet: " + show(packet_spot, 4))
    answers["deep_spot_calc"] = show(spot, 4)
    answers["deep_spot_packet"] = show(packet_spot, 4)

    # ---- The slices to redo: the held position's expiry and the new one's ----
    slices = []                                        # list of (root, expiration, sold strike, bought strike, label)
    if position is not None:
        slices.append((position["root"], position["expiration"], position["strike_short"], position["strike_long"], "held position"))
    if "_new_spread" in answers:
        new = answers["_new_spread"]
        slices.append((new["root"], new["expiration"], new["short"]["strike"], new["long"]["strike"], "new position"))

    first_slice = True
    for root, expiration, strike_short, strike_long, label in slices:
        lines.append("")
        lines.append("  --- slice " + root + " " + expiration + " (" + label + ") ---")
        days = calendar_days_between(day, expiration)
        tau = tau_in_years(days)

        # ---- 7b. Cleaning of the rows of this slice ------------------------
        counts = {"raw rows": 0, "not a vanilla root": 0, "dte outside 4-100": 0, "put K/S outside [0.30, 1.08]": 0,
                  "call K/S outside [0.97, 1.03]": 0, "bid < 0.025": 0, "ask <= bid": 0, "kept": 0}
        kept_calls = {}                                # strike -> (bid, ask, mid)
        kept_puts = {}
        for row in raw_rows:
            if row["root"] != root or row["expiration"] != expiration:
                continue
            counts["raw rows"] = counts["raw rows"] + 1
            strike = float(row["strike"])
            bid = float(row["bid"])
            ask = float(row["ask"])
            option_type = row["option_type"]
            moneyness = strike / spot                  # K / S
            if root not in VANILLA_ROOTS:
                counts["not a vanilla root"] += 1      # += 1 adds one
                continue
            if days < MIN_DAYS or days > MAX_DAYS:
                counts["dte outside 4-100"] += 1
                continue
            if option_type == "P" and (moneyness < PUT_MONEYNESS[0] or moneyness > PUT_MONEYNESS[1]):
                counts["put K/S outside [0.30, 1.08]"] += 1
                continue
            if option_type == "C" and (moneyness < CALL_MONEYNESS[0] or moneyness > CALL_MONEYNESS[1]):
                counts["call K/S outside [0.97, 1.03]"] += 1
                continue
            if bid < MIN_BID:
                counts["bid < 0.025"] += 1
                continue
            if not ask > bid:
                counts["ask <= bid"] += 1
                continue
            counts["kept"] += 1
            mid = 0.5 * (bid + ask)                    # eq:mid
            if option_type == "C":
                kept_calls[strike] = (bid, ask, mid)
            else:
                kept_puts[strike] = (bid, ask, mid)
        count_lines = []
        for name in counts:
            count_lines.append(name + ": " + str(counts[name]))
        # Compare the kept puts with the puts of this slice in puts.csv.
        packet_strikes = []
        puts_by_slice = read_puts_by_slice(folder)
        if (root, expiration) in puts_by_slice:
            for quote in puts_by_slice[(root, expiration)]:
                packet_strikes.append(quote["strike"])
        only_mine = []
        for strike in kept_puts:
            if strike not in packet_strikes:
                only_mine.append(strike)
        only_packet = []
        for strike in packet_strikes:
            if strike not in kept_puts:
                only_packet.append(strike)
        count_lines.append("kept puts: " + str(len(kept_puts)) + ",  puts of this slice in puts.csv: " + str(len(packet_strikes)))
        count_lines.append("strikes kept here but not in puts.csv: " + str(sorted(only_mine)))
        count_lines.append("strikes in puts.csv but not kept here: " + str(sorted(only_packet)))
        add_step(lines, "7b. Cleaning (" + root + " " + expiration + ", dte " + str(days) + ")", "sec:cleaning, D1",
                 "vanilla root; 4 <= dte <= 100; puts 0.30 <= K/S <= 1.08; calls 0.97 <= K/S <= 1.03; bid >= 0.025; ask > bid",
                 count_lines, "same put strikes as the packet: " + str(len(only_mine) == 0 and len(only_packet) == 0))

        # ---- 7c. Discount factor ---------------------------------------------
        rate, rate_notes = rate_for_days(rate_rows, day, days)
        D = math.exp(-rate * tau)                       # def:discount: D = exp(-r tau)
        packet_D = None
        leg_short = quote_at(quotes_by_put, put_key(root, expiration, strike_short), snapshot)
        leg_long = quote_at(quotes_by_put, put_key(root, expiration, strike_long), snapshot)
        if label == "new position":                     # the new legs are in puts.csv, not in legs.csv
            leg_short = None
            leg_long = None
            for quote in puts_by_slice[(root, expiration)]:
                if quote["strike"] == strike_short:
                    leg_short = quote
                if quote["strike"] == strike_long:
                    leg_long = quote
        if leg_short is not None:
            packet_D = leg_short["D"]
        add_step(lines, "7c. Rate and discount factor", "sec:rates, eq:rate-conversion, def:discount, D6, D7",
                 "r = interpolated continuous rate at dte days, D = exp(-r tau), tau = dte/365",
                 rate_notes + ["tau = " + str(days) + "/365 = " + show(tau, 6)],
                 "r = " + show(rate * 100, 5) + "%,  D = " + show(D, 6) + "   packet D: " + show(packet_D, 6))

        # ---- 7d. Forward ------------------------------------------------------
        pair_strikes = []
        for strike in kept_calls:
            if strike in kept_puts:
                pair_strikes.append(strike)
        pair_strikes.sort()
        forward = None
        forward_lines = [str(len(pair_strikes)) + " strikes with both a call and a put"]
        if len(pair_strikes) >= MIN_PAIRS:
            k0 = None
            smallest = None
            for strike in pair_strikes:
                difference = abs(kept_calls[strike][2] - kept_puts[strike][2])   # |C - P| at mid
                if smallest is None or difference < smallest:
                    smallest = difference
                    k0 = strike
            # the 8 strikes nearest K0 (K0 itself included). CHOICE on equal distance: the lower strike first.
            by_distance = []
            for strike in pair_strikes:
                by_distance.append((abs(strike - k0), strike))    # a pair (distance, strike): sorts by distance, then strike
            by_distance.sort()
            chosen = []
            for position_in_list in range(min(PARITY_STRIKES, len(by_distance))):
                chosen.append(by_distance[position_in_list][1])
            chosen.sort()
            estimates = []
            for strike in chosen:
                call_mid = kept_calls[strike][2]
                put_mid = kept_puts[strike][2]
                estimate = strike + (call_mid - put_mid) / D       # F = K + (C - P) / D
                estimates.append(estimate)
                forward_lines.append("K " + show(strike, 1) + ": C " + show(call_mid, 4) + ", P " + show(put_mid, 4)
                                     + ", F = K + (C - P)/D = " + show(estimate, 4))
            forward = median(estimates)
            forward_lines.insert(1, "K0 = " + show(k0, 1) + " (smallest |C - P| = " + show(smallest, 4) + ")")   # insert at position 1
        packet_forward = None
        for expiry in expiries:
            if expiry["root"] == root and expiry["expiration"] == expiration:
                packet_forward = expiry["forward"]
        add_step(lines, "7d. Forward", "sec:forward-impl, D8",
                 "K0 = argmin |C - P|; F = median of K + (C - P)/D over the 8 strikes nearest K0; fewer than 3 pairs -> none",
                 forward_lines, "F = " + show(forward, 6) + "   packet: " + show(packet_forward, 6))

        # ---- 7e. Implied vol and delta of both legs ---------------------------
        leg_answers = {}
        for leg_name, strike, packet_quote in [("short", strike_short, leg_short), ("long", strike_long, leg_long)]:
            numbers = []
            iv = None
            delta = None
            if strike in kept_puts and forward is not None:
                bid, ask, mid = kept_puts[strike]      # the three values stored for this strike
                iv = implied_vol(mid, forward, strike, tau, D, "P")
                packet_mid_text = "none"
                if packet_quote is not None:
                    packet_mid_text = show(packet_quote["mid"], 4)
                numbers.append("put " + show(strike, 1) + ": bid " + show(bid, 2) + " ask " + show(ask, 2) + " mid " + show(mid, 4)
                               + "   packet mid " + packet_mid_text)
                if iv is not None:
                    delta = put_delta_spot(forward, strike, tau, iv, D, spot)
                    numbers.append("iv by bisection on [0.001, 5], 60 halvings = " + show(iv, 6))
                    numbers.append("Delta_S = D (N(d1) - 1) F / S = " + show(delta, 6))
            else:
                numbers.append("put " + show(strike, 1) + " not kept by the cleaning, or no forward")
            packet_iv = None
            packet_delta = None
            if packet_quote is not None:
                packet_iv = packet_quote["iv"]
                packet_delta = packet_quote["delta"]
            leg_word = "bought"
            if leg_name == "short":
                leg_word = "sold"
            add_step(lines, "7e. Implied vol and delta of the " + leg_word + " put",
                     "sec:iv-impl, rem:bisection, prop:greeks-fwd, prop:chainrule, rem:sticky",
                     "P(sigma) = D [K N(-d0) - F N(-d1)] = mid;  Delta_S = D (N(d1) - 1) F/S",
                     numbers, "iv " + show(iv, 6) + " (packet " + show(packet_iv, 6) + "),  delta " + show(delta, 6)
                     + " (packet " + show(packet_delta, 6) + ")")
            leg_answers[leg_name] = (iv, packet_iv, delta, packet_delta)

        # ---- 7f. ATM vol --------------------------------------------------------
        atm = None
        atm_lines = []
        if forward is not None:
            xs = []
            ys = []
            all_strikes = []
            for strike in kept_puts:
                all_strikes.append(strike)
            for strike in kept_calls:
                if strike not in all_strikes:
                    all_strikes.append(strike)
            all_strikes.sort()
            for strike in all_strikes:
                x = math.log(strike / forward)          # x = log(K / F)
                if x < 0 and x > -ATM_BAND and strike in kept_puts:       # OTM puts: -0.05 < x < 0
                    iv = implied_vol(kept_puts[strike][2], forward, strike, tau, D, "P")
                    kind = "put"
                elif x >= 0 and x < ATM_BAND and strike in kept_calls:    # OTM calls: 0 <= x < 0.05
                    iv = implied_vol(kept_calls[strike][2], forward, strike, tau, D, "C")
                    kind = "call"
                else:
                    continue
                if iv is None:
                    atm_lines.append(kind + " " + show(strike, 1) + ": no volatility, dropped")
                    continue
                xs.append(x)
                ys.append(iv)
            window_text = "-"
            if len(xs) > 0:
                window_text = show(min(xs), 4) + " to " + show(max(xs), 4)   # the window of the fit (sec:atm-impl)
            # .insert(0, ...) puts this line at the top of the list
            atm_lines.insert(0, str(len(xs)) + " out-of-the-money quotes in the band, x from " + window_text)
            if len(xs) >= ATM_MIN_QUOTES:
                a, b, c = quadratic_fit(xs, ys)
                atm = a
                atm_lines.append("fit sigma(x) = a + b x + c x^2:  a = " + show(a, 6) + ", b = " + show(b, 6) + ", c = " + show(c, 6))
        packet_atm = None
        for expiry in expiries:
            if expiry["root"] == root and expiry["expiration"] == expiration:
                packet_atm = expiry["atm"]
        add_step(lines, "7f. ATM vol", "def:atm, sec:atm-impl, D11",
                 "OTM puts -0.05 < x < 0, OTM calls 0 <= x < 0.05, x = log(K/F), at least 3; unweighted fit; sigma_atm = a",
                 atm_lines, "sigma_atm = " + show(atm, 6) + "   packet: " + show(packet_atm, 6))

        if first_slice:                                # the CSV holds the first slice (the held position, if any)
            answers["deep_forward_calc"] = show(forward, 6)
            answers["deep_forward_packet"] = show(packet_forward, 6)
            answers["deep_iv_short_calc"] = show(leg_answers["short"][0], 6)
            answers["deep_iv_short_packet"] = show(leg_answers["short"][1], 6)
            answers["deep_iv_long_calc"] = show(leg_answers["long"][0], 6)
            answers["deep_iv_long_packet"] = show(leg_answers["long"][1], 6)
            answers["deep_delta_short_calc"] = show(leg_answers["short"][2], 6)
            answers["deep_delta_short_packet"] = show(leg_answers["short"][3], 6)
            answers["deep_delta_long_calc"] = show(leg_answers["long"][2], 6)
            answers["deep_delta_long_packet"] = show(leg_answers["long"][3], 6)
            answers["deep_atm_calc"] = show(atm, 6)
            answers["deep_atm_packet"] = show(packet_atm, 6)
            first_slice = False


# ======================================================================
# 11. Main: all 32 checks
# ======================================================================

def main():
    """Run every check of list.csv, write one text file per check and answers.csv."""
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)                     # create the output folder the first time

    all_answers = []
    for item in read_table(LIST_FILE):
        hand_check = item["hand_check"]
        run_name = item["run"]
        snapshot = item["snapshot"]
        deep = item["deep"]
        folder = os.path.join(PACKET_FOLDER, hand_check)

        answers = {}
        for column in ANSWER_COLUMNS:                  # every column starts empty
            answers[column] = ""
        answers["hand_check"] = hand_check
        answers["run"] = run_name
        answers["snapshot"] = snapshot

        lines = []
        lines.append("HAND CHECK " + hand_check + "   run " + run_name + "   snapshot " + snapshot + "   deep check: " + deep)
        lines.append("Worked out from the thesis and Part G of validation/test_specification.md by calculator.py.")
        lines.append("Each step: rule -> formula -> numbers -> result. Prices in index points, 1 point = 100 dollars.")

        if snapshot.endswith("(day)"):
            equity_day(hand_check, run_name, folder, lines, answers)
        else:
            check_one_snapshot(hand_check, run_name, snapshot, deep, folder, lines, answers)

        output_path = os.path.join(OUTPUT_FOLDER, hand_check + ".txt")
        with open(output_path, "w") as file:
            for line in lines:
                file.write(line + "\n")
        all_answers.append(answers)
        # a one-line summary on the screen
        summary = answers["exit_reason"]
        if summary == "":                              # the equity day has no exit reason: show its P&L instead
            summary = "day P&L " + answers["day_pnl_dollars"]
        print(hand_check, run_name, snapshot, "->", summary, answers["new_expiry"], answers["maturity_rule"])

    answers_path = os.path.join(OUTPUT_FOLDER, "answers.csv")
    with open(answers_path, "w", newline="") as file:
        # DictWriter writes dictionaries as rows; extrasaction="ignore" skips keys not in the
        # column list (here the '_new_spread' kept for the deep check).
        writer = csv.DictWriter(file, fieldnames=ANSWER_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for answers in all_answers:
            writer.writerow(answers)
    print("written:", OUTPUT_FOLDER)


main()
