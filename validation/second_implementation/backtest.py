"""
Second implementation of the backtest (validation method 3).

Written from the thesis (chapters 2 to 4) and validation/test_specification.md
(Part G) alone, WITHOUT reading Code/ or results/. It runs the strategy of the
thesis in four versions at once, in one pass over the data:

    base_mid     profit exit at entry delta - 0.10, every leg traded at its mid
    base_cross   the same, selling at the bid and buying at the ask
    p15_mid      profit exit at entry delta - 0.15, at mid
    p15_cross    the same, crossing the spread

Both data rules are on: no decision at the stock-close snapshot (16:00, 13:00 on
early-close days), and no decision on a broken quote (def:broken, with Arian's
answer G11: compare with the last quote of the same put that was not broken).

Every place where the thesis and Part G leave a detail open is marked "# CHOICE"
and listed in open_questions.md.

How to run (from the main folder C:\\Dokumente\\Python\\Masterarbeit):

    python validation/second_implementation/backtest.py                    (all months)
    python validation/second_implementation/backtest.py 2012-01 2012-02    (a test)

Output, in validation/second_implementation/output/ (or output_test_<first>_<last>/
for a test):
    trades_<run>.csv    one row per closed cycle
    equity_<run>.csv    one row per trading day, in dollars
    summary.txt         counts and the return of each year, for all four runs
"""

import sys                      # to read the months given on the command line
import os                       # to make the output folder
import math                     # exp, log, sqrt, isnan
import time as clock_time       # only to print how long each month took

import pandas as pd             # to read the large CSV files


# ============================================================================
# Settings
# ============================================================================

GREEKS_FOLDER = "Data/04_greeks"                    # one CSV per month: quotes with forward, iv, delta
ATM_FILE = "Data/05_atm_vol.csv"                    # ATM forward vol and forward per snapshot, root, expiry
VOL30_FILE = "Data/06_vol30.csv"                    # daily 30-day vol and the stress flag
TBILL_FILE = "Data/03_treasury_bills/DGS3MO.csv"    # 3-month T-bill yield, per cent, daily

OUTPUT_FOLDER = "validation/second_implementation/output"   # where the result files go

FIRST_MONTH = "2012-01"         # first month of the sample
LAST_MONTH = "2026-08"          # last month of the sample (data end on 14 Aug 2026)

NUMBER_OF_SPREADS = 2           # def:entry: the position is two spreads
SHORT_DISTANCE = 1.0            # eq:strikes: sold put 1 standard deviation below the forward
LONG_DISTANCE = 2.3             # eq:strikes: bought put 2.3 standard deviations below

BASE_DAYS = 30                  # def:tau-star: shortest expiry with at least 30 days
CAP_DAYS = 90                   # def:tau-star: recovery maturities at most 90 days

LOSS_BAND = 0.10                # def:exits: loss exit at entry delta + 0.10
GAMMA_FLOOR_DAYS = 10           # eq:gamma-exit: tau_exit = max(tau0 / 2, 10 days)

QUOTE_RULE_ON = True            # def:broken: the broken-quote rule is on in every run
BROKEN_VOL_JUMP = 0.03          # def:broken condition 1: iv jumped more than 3 vol points
BROKEN_WIDTH_RATIO = 3.0        # def:broken condition 2: quote more than 3 times as wide

TBILL_DAYS = 91                 # the 3-month series sits at 91 days on the rate curve (sec:rates)
DOLLARS_PER_POINT = 100         # an SPX option is worth 100 dollars per index point

# The four runs. Only the profit band and the execution differ (sec:robustness).
RUNS_TO_DO = [
    {"name": "base_mid",   "profit_band": 0.10, "execution": "mid"},
    {"name": "base_cross", "profit_band": 0.10, "execution": "cross"},
    {"name": "p15_mid",    "profit_band": 0.15, "execution": "mid"},
    {"name": "p15_cross",  "profit_band": 0.15, "execution": "cross"},
]


# ============================================================================
# Part 1: reading the small files (rates, stress flags, ATM table)
# ============================================================================

def read_tbill_rates():
    """
    Read the 3-month T-bill yield and return a dictionary
    date string -> simple yield as a fraction, for EVERY calendar day from the
    first to the last date of the file. Days without a value (holidays, the
    empty rows of the file) get the last value before them (forward fill,
    sec:rates).

    Example:  rates["2012-01-03"]  ->  0.0002   (0.02 per cent)
    """

    table = pd.read_csv(TBILL_FILE)                         # two columns: observation_date, DGS3MO

    known_rates = {}                                        # date -> yield, only days that have a value
    for row_number in range(len(table)):                    # plain loop over the rows
        date = table["observation_date"][row_number]        # e.g. "2012-01-03"
        value = table["DGS3MO"][row_number]                 # per cent, or NaN (an empty number) when missing
        if not math.isnan(value):                           # skip the empty rows
            known_rates[date] = value / 100.0               # per cent -> fraction

    first_day = pd.Timestamp(table["observation_date"][0])              # first calendar day of the file
    last_day = pd.Timestamp(table["observation_date"][len(table) - 1])  # last calendar day

    rates = {}                                              # the answer: every calendar day
    last_value = None                                       # the last yield seen so far
    day = first_day
    while day <= last_day:                                  # walk through every calendar day
        date = day.strftime("%Y-%m-%d")                     # Timestamp -> "YYYY-MM-DD"
        if date in known_rates:
            last_value = known_rates[date]                  # a new value on this day
        rates[date] = last_value                            # else keep the previous one (forward fill)
        day = day + pd.Timedelta(days=1)                    # next calendar day

    return rates


def continuous_rate(simple_rate, years):
    """
    Turn a simple-interest yield into a continuous rate, eq:rate-conversion:
        r_cont = log(1 + r_simple * tau) / tau
    with tau the maturity of the series in years (here 91/365 for 3 months).
    """
    return math.log(1.0 + simple_rate * years) / years


def read_stress_flags():
    """
    Read the daily stress flag (def:stress) and return date -> True/False.
    It is only recorded on each trade and changes no decision (G16 is deferred).
    """
    table = pd.read_csv(VOL30_FILE, usecols=["date", "stress"])     # only the two columns needed
    flags = {}
    for row_number in range(len(table)):
        date = table["date"][row_number]
        flags[date] = bool(table["stress"][row_number])            # "True"/"False" -> True/False
    return flags


def read_atm_table():
    """
    Read Data/05_atm_vol.csv and return a dictionary
        snapshot time -> list of (root, expiration, days, forward, atm_vol)
    with one entry for every root and expiry that has an ATM vol at that time.

    Example:  atm["2012-01-03 09:45:00"][0]
              -> ("SPX", "2012-01-21", 18, 1280.425, 0.1843)
    """

    columns = ["quote_datetime", "root", "expiration", "dte", "forward", "atm_iv"]  # only what is needed
    table = pd.read_csv(ATM_FILE, usecols=columns)

    # .to_numpy() turns a column into a plain array, which is much faster to
    # loop over than the column itself.
    times = table["quote_datetime"].to_numpy()
    roots = table["root"].to_numpy()
    expirations = table["expiration"].to_numpy()
    days = table["dte"].to_numpy()
    forwards = table["forward"].to_numpy()
    atm_vols = table["atm_iv"].to_numpy()

    atm = {}                                                # the answer
    for i in range(len(times)):                             # one row = one root and expiry at one snapshot
        forward = float(forwards[i])
        atm_vol = float(atm_vols[i])
        if math.isnan(forward) or math.isnan(atm_vol):      # G7: no forward or no ATM vol -> not a candidate
            continue
        if times[i] not in atm:
            atm[times[i]] = []                              # first expiry seen at this snapshot
        atm[times[i]].append((roots[i], expirations[i], int(days[i]), forward, atm_vol))

    return atm


# ============================================================================
# Part 2: reading one month of put quotes
# ============================================================================

def month_list(first_month, last_month):
    """
    All months from first_month to last_month, as "YYYY-MM" strings.
    Example:  month_list("2012-11", "2013-02") -> ["2012-11", "2012-12", "2013-01", "2013-02"]
    """
    months = []
    year = int(first_month[:4])                             # "2012-11" -> 2012
    month = int(first_month[5:])                            # "2012-11" -> 11
    while True:
        name = str(year) + "-" + str(month).zfill(2)        # zfill(2) pads with a zero: 1 -> "01"
        months.append(name)
        if name == last_month:
            break
        month = month + 1
        if month == 13:                                     # December -> January of the next year
            month = 1
            year = year + 1
    return months


def read_month(month):
    """
    Read the put quotes of one month from Data/04_greeks and prepare them for
    fast lookup. The rows at the stock-close snapshot are dropped here, since no
    decision, no valuation and no broken-quote comparison ever uses them
    (sec:monitoring, def:broken, G13).

    Returns a dictionary with:
        "times"         sorted list of the snapshot times kept
        "early_close"   list of the early-close dates of the month
        "slice_rows"    (time, root, expiration) -> row positions of the puts of that slice
        "contract_rows" (root, expiration, strike) -> row positions of that put, all month
        and one array per column ("time", "strike", "bid", "ask", "mid", "iv", "delta", "dte").
    """

    path = GREEKS_FOLDER + "/spx_" + month + ".csv"
    columns = ["quote_datetime", "root", "expiration", "dte", "strike", "option_type",
               "bid", "ask", "mid", "iv", "delta"]          # only the columns the backtest needs
    table = pd.read_csv(path, usecols=columns)

    # Keep the puts only. table["option_type"] == "P" is a True/False column
    # (a "mask"); table[mask] keeps the rows where it is True.
    is_put = table["option_type"] == "P"
    table = table[is_put]

    # .str[:10] takes the first 10 characters of every text in the column:
    # "2012-01-03 09:45:00" -> "2012-01-03" (the date) and .str[11:16] -> "09:45".
    date_part = table["quote_datetime"].str[:10]
    clock_part = table["quote_datetime"].str[11:16]

    # The last snapshot of each day. groupby(date_part) collects the rows of
    # each date, and .max() takes the latest clock time within each date.
    last_clock_of_day = clock_part.groupby(date_part).max()

    # CHOICE (G20): a day is an early-close day when its last snapshot is
    # 13:15 or earlier. Its stock close is then 13:00, otherwise 16:00.
    early_close = []
    for date, last_clock in last_clock_of_day.items():     # .items() gives (date, value) pairs
        if last_clock <= "13:15":                           # text comparison works for "HH:MM"
            early_close.append(date)

    # Mark the rows at the stock-close snapshot.
    # .isin(list) is True where the value is one of the list.  & means "and",
    # | means "or", ~ means "not" (for True/False columns).
    on_early_day = date_part.isin(early_close)
    at_stock_close = ((clock_part == "16:00") & ~on_early_day) | ((clock_part == "13:00") & on_early_day)
    table = table[~at_stock_close]                          # drop them

    # Number the rows 0, 1, 2, ... again after the rows were dropped.
    # (reset_index(drop=True) throws the old row labels away.)
    table = table.reset_index(drop=True)

    # groupby(...).indices gives a dictionary: group -> row positions of its rows.
    # A slice = all puts of one root and expiry at one snapshot (sec:forward-impl).
    slice_rows = table.groupby(["quote_datetime", "root", "expiration"]).indices
    # A contract = one put (root, expiration, strike), over the whole month.
    contract_rows = table.groupby(["root", "expiration", "strike"]).indices

    month_data = {
        "name": month,
        "times": sorted(table["quote_datetime"].unique()),   # .unique() = each time once
        "early_close": early_close,
        "slice_rows": slice_rows,
        "contract_rows": contract_rows,
        "time": table["quote_datetime"].to_numpy(),
        "strike": table["strike"].to_numpy(),
        "dte": table["dte"].to_numpy(),
        "bid": table["bid"].to_numpy(),
        "ask": table["ask"].to_numpy(),
        "mid": table["mid"].to_numpy(),
        "iv": table["iv"].to_numpy(),
        "delta": table["delta"].to_numpy(),
    }
    return month_data


def quote_at_row(month_data, row):
    """
    Collect the numbers of one quote (one row) into a small dictionary.
    """
    bid = float(month_data["bid"][row])
    ask = float(month_data["ask"][row])
    quote = {
        "time": month_data["time"][row],
        "strike": float(month_data["strike"][row]),
        "dte": int(month_data["dte"][row]),                 # calendar days to expiry (def:tau-conv)
        "bid": bid,
        "ask": ask,
        "mid": float(month_data["mid"][row]),               # (bid + ask) / 2, eq:mid
        "width": ask - bid,                                 # w_t of def:broken, index points
        "iv": float(month_data["iv"][row]),                 # NaN when no volatility was found
        "delta": float(month_data["delta"][row]),           # spot delta Delta_S, NaN when no volatility
    }
    return quote


def is_usable(quote):
    """
    G12: a leg counts as quoted only if it has a row AND a delta.
    """
    if quote is None:
        return False                                        # no row at all
    if math.isnan(quote["delta"]) or math.isnan(quote["iv"]):
        return False                                        # a row without volatility or delta
    return True


def rows_by_time_of_contract(month_data, root, expiration, strike):
    """
    All quotes of one put in this month, as a dictionary time -> row position.
    Used for the legs of an open position, so that each snapshot needs only a
    dictionary lookup.
    """
    key = (root, expiration, strike)
    rows = month_data["contract_rows"].get(key)             # .get gives None if the put is not there
    answer = {}
    if rows is None:
        return answer                                       # the put has no quote at all this month
    for row in rows:
        answer[month_data["time"][row]] = row
    return answer


# ============================================================================
# Part 3: the broken-quote rule (def:broken, G11)
# ============================================================================

def is_broken(quote_now, reference):
    """
    def:broken. The quote at t is broken if all three hold, against the
    reference quote (the last good quote of the same put, G11):
        1. |iv_t - iv_ref| > 0.03
        2. w_t > 3 * w_ref
        3. w_t - w_ref > |m_t - m_ref|
    With no reference quote there is nothing to compare, so it is not broken.
    """
    if not QUOTE_RULE_ON:
        return False
    if reference is None:
        return False                                        # CHOICE: a put never quoted before cannot be tested

    iv_jumped = abs(quote_now["iv"] - reference["iv"]) > BROKEN_VOL_JUMP
    much_wider = quote_now["width"] > BROKEN_WIDTH_RATIO * reference["width"]
    widened_more_than_moved = (quote_now["width"] - reference["width"]) > abs(quote_now["mid"] - reference["mid"])

    if iv_jumped and much_wider and widened_more_than_moved:
        return True
    return False


def last_good_quote_before(run, month_data, previous_month_data, root, expiration, strike, time):
    """
    G11 for a put about to be opened: its last quote before `time` that was not
    judged broken in this run, at a snapshot that is not the stock close (those
    rows were dropped when reading), with a volatility. The search goes back
    through this month and the previous one.

    Returns the quote dictionary, or None if there is none.
    """
    for data in [month_data, previous_month_data]:          # this month first, then the month before
        if data is None:
            continue                                        # the first month has no month before it
        rows = data["contract_rows"].get((root, expiration, strike))
        if rows is None:
            continue                                        # the put has no quote in that month
        best_row = None
        best_time = None
        for row in rows:                                    # plain loop over all quotes of this put
            row_time = data["time"][row]
            if row_time >= time:
                continue                                    # only quotes strictly before t
            if math.isnan(data["iv"][row]):
                continue                                    # CHOICE: a quote without volatility cannot be a reference
            if (root, expiration, strike, row_time) in run["broken_quotes"]:
                continue                                    # judged broken earlier: not a good quote
            if best_time is None or row_time > best_time:
                best_row = row
                best_time = row_time
        if best_row is not None:
            return quote_at_row(data, best_row)
    return None


# ============================================================================
# Part 4: opening a position (def:entry, def:tau-star)
# ============================================================================

def nearest_put(month_data, rows, target):
    """
    def:entry and G2: the listed put nearest in strike to the target, among the
    puts of the slice that are quoted with a delta (G12).
    Returns (row position, True if there was a tie) or (None, False).
    """
    best_row = None
    best_distance = None
    best_strike = None
    tie = False
    for row in rows:
        if math.isnan(month_data["delta"][row]) or math.isnan(month_data["iv"][row]):
            continue                                        # not usable (G12)
        strike = float(month_data["strike"][row])
        distance = abs(strike - target)                     # distance in index points
        if best_row is None or distance < best_distance:
            best_row = row
            best_distance = distance
            best_strike = strike
            tie = False
        elif distance == best_distance:
            tie = True                                      # G2: should practically never happen; counted
            if strike < best_strike:                        # CHOICE: on an exact tie take the lower strike
                best_row = row
                best_strike = strike
    return best_row, tie


def build_spread(run, month_data, time, candidate):
    """
    Build the two spreads of eq:strikes for one candidate expiry at time t.

    candidate = (root, expiration, days, forward, atm_vol) from the ATM table.
    Returns a dictionary with the strikes, quotes and the credit, or None if
    the expiry cannot be used (G3, G7).
    """
    root, expiration, days, forward, atm_vol = candidate

    rows = month_data["slice_rows"].get((time, root, expiration))
    if rows is None:
        return None                                         # no puts of this expiry at t (G7: skipped)

    tau = max(days, 1) / 365.0                              # def:tau-conv: calendar days / 365, floored at 1/365
    spread_of_vol = atm_vol * math.sqrt(tau)                # sigma * sqrt(tau)

    target_short = forward * math.exp(-SHORT_DISTANCE * spread_of_vol)   # K_short = F exp(-sigma sqrt(tau))
    target_long = forward * math.exp(-LONG_DISTANCE * spread_of_vol)     # K_long  = F exp(-2.3 sigma sqrt(tau))

    short_row, short_tie = nearest_put(month_data, rows, target_short)
    long_row, long_tie = nearest_put(month_data, rows, target_long)
    if short_tie or long_tie:
        run["counts"]["strike_ties"] += 1

    if short_row is None or long_row is None:
        return None                                         # G7: a strike cannot be snapped -> skipped

    short_quote = quote_at_row(month_data, short_row)
    long_quote = quote_at_row(month_data, long_row)

    if short_quote["strike"] <= long_quote["strike"]:
        return None                                         # G3: the strikes must differ -> skipped

    # The credit for two spreads, in index points (G6: at the execution price).
    credit_mid = NUMBER_OF_SPREADS * (short_quote["mid"] - long_quote["mid"])
    if run["execution"] == "mid":
        credit = credit_mid                                 # sec:costs: every leg at its mid
    else:
        credit = NUMBER_OF_SPREADS * (short_quote["bid"] - long_quote["ask"])   # sell at the bid, buy at the ask

    spread = {
        "root": root,
        "expiration": expiration,
        "days": days,
        "forward": forward,
        "atm_vol": atm_vol,
        "target_short": target_short,
        "target_long": target_long,
        "short": short_quote,
        "long": long_quote,
        "credit": credit,
        "credit_mid": credit_mid,
    }
    return spread


def choose_spread(run, month_data, time, atm_entries):
    """
    def:tau-star with G4 to G8. Returns (spread, maturity rule) or (None, reason).

    The candidates are the expiries of the ATM table at t with at least 30 days,
    sorted by days and, for the same date, by root name (G4: SPX, SPXQ, SPXW).
    """

    candidates = []
    for entry in atm_entries:
        days = entry[2]
        if days >= BASE_DAYS:                               # G5: whole calendar days, at least 30
            candidates.append(entry)

    # Sort by days first, then by root name (G4). The "key" tells sort what to
    # compare: here the pair (days, root) of each entry.
    def sort_key(entry):
        return (entry[2], entry[0])
    candidates.sort(key=sort_key)

    deficit = run["deficit"]

    # tau_30: the shortest usable expiry with at least 30 days (G7: unusable ones are skipped).
    base_spread = None
    base_position = None
    for i in range(len(candidates)):
        spread = build_spread(run, month_data, time, candidates[i])
        if spread is not None:
            base_spread = spread
            base_position = i
            break

    if base_spread is None:
        return None, "no_candidate"                         # G8: no position, try again at the next snapshot

    if deficit <= 0.0:
        return base_spread, "base"                          # def:tau-star: L = 0 -> tau_30

    # L > 0: the shortest expiry of 30 to 90 days whose credit covers c(tau_30) + L.
    needed_credit = base_spread["credit"] + deficit
    longest_spread = None                                   # the longest usable one of at most 90 days
    for i in range(base_position, len(candidates)):
        days = candidates[i][2]
        if days > CAP_DAYS:
            break                                           # sorted by days: the rest is above 90 days too
        if i == base_position:
            spread = base_spread                            # already built
        else:
            spread = build_spread(run, month_data, time, candidates[i])
        if spread is None:
            continue                                        # G7: skipped
        if spread["credit"] >= needed_credit:
            return spread, "recovery"                       # the first (shortest) that qualifies
        # Keep the longest one; for the same date the first root in name order (CHOICE, as G4).
        if longest_spread is None or spread["days"] > longest_spread["days"]:
            longest_spread = spread

    if longest_spread is not None:
        return longest_spread, "cap"                        # no maturity qualifies: the longest of at most 90 days

    # CHOICE: tau_30 itself is above 90 days, so no expiry of 30 to 90 days exists.
    # Not covered by the thesis; take tau_30 and count it.
    run["counts"]["cap_without_expiry"] += 1
    return base_spread, "cap_none_below_90"


def try_to_open(run, month_data, previous_month_data, time, atm_table, stress_flags):
    """
    Open a new position at snapshot `time` if possible (def:entry). If no
    expiry can be used, or a leg's quote is broken (sec:broken-quotes), no
    position is opened and the next attempt is at the next snapshot (G9).
    """
    atm_entries = atm_table.get(time, [])                   # all expiries with an ATM vol at t
    spread, rule = choose_spread(run, month_data, time, atm_entries)
    if spread is None:
        run["counts"]["entry_no_candidate"] += 1
        return

    # The broken-quote rule on the two legs about to be opened (only the chosen
    # expiry is tested, as sec:broken-quotes says).
    any_broken = False
    for leg_name in ["short", "long"]:
        quote = spread[leg_name]
        reference = last_good_quote_before(run, month_data, previous_month_data,
                                           spread["root"], spread["expiration"], quote["strike"], time)
        if is_broken(quote, reference):
            run["broken_quotes"].add((spread["root"], spread["expiration"], quote["strike"], time))
            any_broken = True
    if any_broken:
        run["counts"]["entry_refused_broken"] += 1
        return

    short_quote = spread["short"]
    long_quote = spread["long"]

    # eq:posdelta: Delta_pos = 2 (Delta_S long - Delta_S short), at each put's own iv.
    entry_delta = NUMBER_OF_SPREADS * (long_quote["delta"] - short_quote["delta"])

    width = short_quote["strike"] - long_quote["strike"]    # strike distance of one spread, points
    # G15: margin = maximum loss at entry = (2 * width - credit) * 100 dollars,
    # with the credit at the execution price.
    margin = (NUMBER_OF_SPREADS * width - spread["credit"]) * DOLLARS_PER_POINT

    position = {
        "entry_time": time,
        "root": spread["root"],
        "expiration": spread["expiration"],
        "days_at_entry": spread["days"],
        # eq:gamma-exit: tau_exit = max(tau0 / 2, 10 days). Compared with whole days (G10).
        "gamma_exit_days": max(spread["days"] / 2.0, GAMMA_FLOOR_DAYS),
        "forward": spread["forward"],
        "atm_vol": spread["atm_vol"],
        "target_short": spread["target_short"],
        "target_long": spread["target_long"],
        "short_strike": short_quote["strike"],
        "long_strike": long_quote["strike"],
        "short_iv_entry": short_quote["iv"],
        "long_iv_entry": long_quote["iv"],
        "credit": spread["credit"],
        "credit_mid": spread["credit_mid"],
        "entry_delta": entry_delta,
        "maturity_rule": rule,
        "deficit_before": run["deficit"],
        "margin": margin,
        "stress": stress_flags.get(time[:10]),              # CHOICE: the day's flag of 06_vol30.csv (G16 deferred)
        # The last good quote of each leg, for the broken-quote rule (G11).
        "reference_short": short_quote,
        "reference_long": long_quote,
        # Value of the two spreads at mid at the last usable snapshot, points (S28).
        "mark_mid": spread["credit_mid"],
        # The quotes of each leg over the current month, time -> row (filled below).
        "rows_month": None,
        "short_rows": None,
        "long_rows": None,
    }
    run["position"] = position
    run["counts"]["entries"] += 1


# ============================================================================
# Part 5: holding and closing (def:exits, def:deficit)
# ============================================================================

def leg_quote_now(position, month_data, leg_name, time):
    """
    The quote of one leg of the open position at `time`, or None if the put has
    no row then. The rows of the leg are looked up once per month.
    """
    if position["rows_month"] != month_data["name"]:        # new month (or new position): look the rows up
        position["short_rows"] = rows_by_time_of_contract(month_data, position["root"],
                                                          position["expiration"], position["short_strike"])
        position["long_rows"] = rows_by_time_of_contract(month_data, position["root"],
                                                         position["expiration"], position["long_strike"])
        position["rows_month"] = month_data["name"]
    rows = position[leg_name + "_rows"]
    row = rows.get(time)
    if row is None:
        return None
    return quote_at_row(month_data, row)


def update_deficit(deficit, pnl):
    """
    def:deficit, with pi the P&L of the cycle in index points (at execution, G17):
        pi >= L       -> L = 0
        0 <= pi < L   -> L = L - pi
        pi < 0        -> L = -pi  (any earlier deficit is dropped)
    """
    if pnl < 0.0:
        return -pnl
    if pnl >= deficit:
        return 0.0
    return deficit - pnl


def close_position(run, time, short_quote, long_quote, delta_now, reason):
    """
    Close the open position at `time` and write one trade row.
    """
    position = run["position"]

    # Cost of buying back the two spreads, index points.
    cost_mid = NUMBER_OF_SPREADS * (short_quote["mid"] - long_quote["mid"])
    if run["execution"] == "mid":
        cost = cost_mid
    else:
        cost = NUMBER_OF_SPREADS * (short_quote["ask"] - long_quote["bid"])  # buy the sold put at the ask, sell the bought at the bid

    pnl = position["credit"] - cost                         # def:deficit: pi = credit - cost of closing
    deficit_before = run["deficit"]
    deficit_after = update_deficit(deficit_before, pnl)
    run["deficit"] = deficit_after

    trade = {
        "entry_time": position["entry_time"],
        "exit_time": time,
        "root": position["root"],
        "expiration": position["expiration"],
        "days_at_entry": position["days_at_entry"],
        "days_at_exit": short_quote["dte"],
        "maturity_rule": position["maturity_rule"],
        "forward": position["forward"],
        "atm_vol": position["atm_vol"],
        "target_short": position["target_short"],
        "target_long": position["target_long"],
        "short_strike": position["short_strike"],
        "long_strike": position["long_strike"],
        "short_iv_entry": position["short_iv_entry"],
        "long_iv_entry": position["long_iv_entry"],
        "credit": position["credit"],
        "credit_mid": position["credit_mid"],
        "entry_delta": position["entry_delta"],
        "exit_reason": reason,
        "exit_delta": delta_now,
        "short_iv_exit": short_quote["iv"],
        "long_iv_exit": long_quote["iv"],
        "cost_to_close": cost,
        "cost_to_close_mid": cost_mid,
        "pnl_points": pnl,
        "pnl_dollars": pnl * DOLLARS_PER_POINT,
        "deficit_before": deficit_before,
        "deficit_after": deficit_after,
        "margin": position["margin"],
        "stress": position["stress"],
    }
    run["trades"].append(trade)
    run["realised_today"] = run["realised_today"] + pnl * DOLLARS_PER_POINT   # dollars
    run["last_margin"] = position["margin"]                 # G9: kept for a day that ends without a position
    run["position"] = None


def process_snapshot(run, month_data, previous_month_data, time, atm_table, stress_flags):
    """
    Everything one run does at one snapshot (never the stock close, those rows
    are gone): test the open position, close it if a trigger holds, and open
    the next one at the same snapshot.
    """
    position = run["position"]

    if position is None:
        try_to_open(run, month_data, previous_month_data, time, atm_table, stress_flags)
        return

    if position["entry_time"] == time:
        return                                              # opened at this very snapshot (cannot happen here, kept for safety)

    short_quote = leg_quote_now(position, month_data, "short", time)
    long_quote = leg_quote_now(position, month_data, "long", time)

    short_ok = is_usable(short_quote)                       # G12
    long_ok = is_usable(long_quote)

    # Broken-quote test of each quoted leg against its last good quote (G11).
    short_broken = False
    long_broken = False
    if short_ok:
        short_broken = is_broken(short_quote, position["reference_short"])
        if short_broken:
            run["broken_quotes"].add((position["root"], position["expiration"], position["short_strike"], time))
        else:
            position["reference_short"] = short_quote       # a good quote: the new reference
    if long_ok:
        long_broken = is_broken(long_quote, position["reference_long"])
        if long_broken:
            run["broken_quotes"].add((position["root"], position["expiration"], position["long_strike"], time))
        else:
            position["reference_long"] = long_quote

    if not short_ok or not long_ok:
        run["counts"]["snapshots_leg_missing"] += 1          # sec:backtest-design: triggers not tested
        return
    if short_broken or long_broken:
        run["counts"]["snapshots_broken"] += 1               # sec:broken-quotes: not marked, not tested
        return

    run["counts"]["snapshots_tested"] += 1

    # Mark at mid (S28), points: value of the two spreads.
    position["mark_mid"] = NUMBER_OF_SPREADS * (short_quote["mid"] - long_quote["mid"])

    delta_now = NUMBER_OF_SPREADS * (long_quote["delta"] - short_quote["delta"])   # eq:posdelta
    days_now = short_quote["dte"]                           # whole calendar days to expiry (G10)

    # def:exits, tested in the order loss, profit, gamma (G1).
    reason = None
    if delta_now >= position["entry_delta"] + LOSS_BAND:
        reason = "loss"
    elif delta_now <= position["entry_delta"] - run["profit_band"]:
        reason = "profit"
    elif days_now <= position["gamma_exit_days"]:
        reason = "gamma"

    if reason is None:
        return                                              # S11: kept

    close_position(run, time, short_quote, long_quote, delta_now, reason)
    # S12: the next position is opened at the same snapshot.
    try_to_open(run, month_data, previous_month_data, time, atm_table, stress_flags)


# ============================================================================
# Part 6: the end of each trading day (sec:results-main, sec:cash, G13, G21)
# ============================================================================

def finish_day(run, date, previous_date, rates):
    """
    Write the row of one trading day, in dollars:
        realised    = P&L of the cycles closed today
        unrealised  = change of the open position's value at mid since yesterday
        interest    = M(t-1) * (exp(r(t) * days / 365) - 1)        (G14, G21)
        total       = realised + unrealised + interest
    """
    position = run["position"]

    # Open P&L of the position still open, valued at mid at its last usable
    # snapshot (G13): credit received - value of the two spreads, dollars.
    if position is not None:
        open_pnl = (position["credit"] - position["mark_mid"]) * DOLLARS_PER_POINT
        margin_now = position["margin"]
    else:
        open_pnl = 0.0
        margin_now = run["last_margin"]                      # G9: the margin of the last position
        run["counts"]["days_without_position"] += 1

    unrealised = open_pnl - run["open_pnl_yesterday"]

    # Interest on the margin held at yesterday's close (G21). The first trading
    # day earns nothing.
    interest = 0.0
    if previous_date is not None:
        days = (pd.Timestamp(date) - pd.Timestamp(previous_date)).days   # calendar days since the last trading day
        simple_rate = rates[date]                            # G14: the 3-month yield of the day of payment
        rate = continuous_rate(simple_rate, TBILL_DAYS / 365.0)
        interest = run["margin_yesterday"] * (math.exp(rate * days / 365.0) - 1.0)

    total = run["realised_today"] + unrealised + interest

    run["days"].append({
        "date": date,
        "margin": margin_now,
        "realised_pnl": run["realised_today"],
        "unrealised_pnl": unrealised,
        "interest": interest,
        "total_pnl": total,
        "open_pnl": open_pnl,
        "position_open": position is not None,
    })

    run["realised_today"] = 0.0                              # start the next day at zero
    run["open_pnl_yesterday"] = open_pnl
    run["margin_yesterday"] = margin_now


# ============================================================================
# Part 7: returns and output
# ============================================================================

def yearly_returns(days):
    """
    sec:results-main: return of a period = its P&L / average daily margin over
    its trading days. Returns a list of (year, return in per cent), and the
    whole-sample figure of tab:results-years: total P&L / average margin /
    (number of days / 252), in per cent.
    """
    pnl_by_year = {}
    margin_sum_by_year = {}
    day_count_by_year = {}
    for day in days:
        year = day["date"][:4]
        if year not in pnl_by_year:
            pnl_by_year[year] = 0.0
            margin_sum_by_year[year] = 0.0
            day_count_by_year[year] = 0
        pnl_by_year[year] = pnl_by_year[year] + day["total_pnl"]
        margin_sum_by_year[year] = margin_sum_by_year[year] + day["margin"]
        day_count_by_year[year] = day_count_by_year[year] + 1

    answer = []
    for year in sorted(pnl_by_year):
        average_margin = margin_sum_by_year[year] / day_count_by_year[year]
        answer.append((year, 100.0 * pnl_by_year[year] / average_margin))

    total_pnl = 0.0
    margin_sum = 0.0
    for day in days:
        total_pnl = total_pnl + day["total_pnl"]
        margin_sum = margin_sum + day["margin"]
    whole = 0.0
    if len(days) > 0:
        whole = 100.0 * total_pnl / (margin_sum / len(days)) / (len(days) / 252.0)
    return answer, whole


def new_run(settings):
    """
    The state of one run at the start of the backtest (G19: no deficit, no position).
    """
    return {
        "name": settings["name"],
        "profit_band": settings["profit_band"],
        "execution": settings["execution"],
        "deficit": 0.0,
        "position": None,
        "last_margin": 0.0,
        "trades": [],
        "days": [],
        "broken_quotes": set(),                              # (root, expiration, strike, time) judged broken
        "realised_today": 0.0,
        "open_pnl_yesterday": 0.0,
        "margin_yesterday": 0.0,
        "counts": {
            "entries": 0,
            "entry_no_candidate": 0,
            "entry_refused_broken": 0,
            "snapshots_tested": 0,
            "snapshots_leg_missing": 0,
            "snapshots_broken": 0,
            "days_without_position": 0,
            "strike_ties": 0,
            "cap_without_expiry": 0,
        },
    }


def write_outputs(runs, output_folder, early_close_days, open_positions):
    """
    Write the trade and the daily files of each run, and the summary.
    """
    os.makedirs(output_folder, exist_ok=True)                # make the folder if it is not there yet

    lines = []
    lines.append("Second implementation of the backtest, summary")
    lines.append("Early-close days found in the data: " + str(len(early_close_days)))
    lines.append("  " + ", ".join(early_close_days))
    for run in runs:
        trades = pd.DataFrame(run["trades"])                 # list of dictionaries -> table
        trades.to_csv(output_folder + "/trades_" + run["name"] + ".csv", index=False)
        days = pd.DataFrame(run["days"])
        days.to_csv(output_folder + "/equity_" + run["name"] + ".csv", index=False)

        lines.append("")
        lines.append("Run " + run["name"] + ": " + str(len(run["trades"])) + " closed cycles")
        for name in run["counts"]:
            lines.append("  " + name + ": " + str(run["counts"][name]))
        lines.append("  broken quotes found: " + str(len(run["broken_quotes"])))
        for item in sorted(run["broken_quotes"], key=lambda q: q[3]):   # lambda: a one-line function giving the time
            lines.append("    " + str(item))
        lines.append("  position still open at the end (only valued, G18): " + str(open_positions[run["name"]]))
        returns, whole = yearly_returns(run["days"])
        for year, value in returns:
            lines.append("  " + year + ": " + format(value, ".1f") + " %")
        lines.append("  per year over the sample (not compounded): " + format(whole, ".1f") + " %")

    with open(output_folder + "/summary.txt", "w") as summary_file:
        summary_file.write("\n".join(lines) + "\n")
    print("\n".join(lines))


# ============================================================================
# Part 8: the main loop
# ============================================================================

def main():
    first_month = FIRST_MONTH
    last_month = LAST_MONTH
    output_folder = OUTPUT_FOLDER
    if len(sys.argv) == 3:                                   # a test on a few months
        first_month = sys.argv[1]
        last_month = sys.argv[2]
        output_folder = OUTPUT_FOLDER + "_test_" + first_month + "_" + last_month

    print("reading rates, stress flags and the ATM table ...", flush=True)
    rates = read_tbill_rates()
    stress_flags = read_stress_flags()
    atm_table = read_atm_table()

    runs = []
    for settings in RUNS_TO_DO:
        runs.append(new_run(settings))

    previous_month_data = None
    previous_date = None
    early_close_days = []

    for month in month_list(first_month, last_month):
        start = clock_time.time()
        month_data = read_month(month)
        early_close_days = early_close_days + month_data["early_close"]

        current_date = None
        for time in month_data["times"]:                     # every snapshot in time order
            date = time[:10]
            if date != current_date:                         # a new trading day begins
                if current_date is not None:
                    for run in runs:
                        finish_day(run, current_date, previous_date, rates)
                    previous_date = current_date
                current_date = date
            for run in runs:
                process_snapshot(run, month_data, previous_month_data, time, atm_table, stress_flags)

        if current_date is not None:                         # close the last day of the month
            for run in runs:
                finish_day(run, current_date, previous_date, rates)
            previous_date = current_date

        previous_month_data = month_data
        seconds = clock_time.time() - start
        text = month + " done in " + format(seconds, ".0f") + " s;"
        for run in runs:
            text = text + " " + run["name"] + " " + str(len(run["trades"]))
        print(text, flush=True)

    # G18: the position still open at the end is only valued, not closed.
    open_positions = {}
    for run in runs:
        position = run["position"]
        if position is None:
            open_positions[run["name"]] = None
        else:
            open_positions[run["name"]] = (position["entry_time"], position["root"], position["expiration"],
                                           position["short_strike"], position["long_strike"])

    write_outputs(runs, output_folder, early_close_days, open_positions)


main()
