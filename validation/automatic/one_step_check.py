"""
One-step check over all held snapshots (code validation, step 2: automatic tests).

What this file is for
---------------------
The backtest logs
  - every put it holds, at every snapshot it uses     (results/quotes_<run>.csv),
  - every snapshot at which a held put had no quote    (results/missing_<run>.csv),
  - every closed cycle                                 (results/trades_<run>.csv).
This script takes the state the backtest logged just before a snapshot (the open
position, its entry delta, its time to expiry at entry) and works out from the
thesis rules alone what the backtest had to do at that snapshot. Then it compares
with what the backtest did. Each snapshot therefore tests one step, and every held
snapshot of the four reported runs is tested, not a sample.

It was written from the thesis and validation/test_specification.md only, without
reading Code/. The IDs in brackets (S7, G11, ...) are the statements and the Part G
answers of the test specification.

  Part A  the schedule. Every snapshot of the data while a position is open is
          either logged as held or logged as "leg missing" (S13, S22). Nothing
          happens at the stock close, 16:00, or 13:00 on early-close days (S19).
  Part B  the decision at each held snapshot: broken quote or not (S20, S21),
          position delta (S7), and which exit holds, in the order loss, profit,
          gamma (S8-S11, G1, G10).
  Part C  each closed cycle: entry delta, days, credit, margin, target strikes,
          the exit, its cost and P&L, the deficit (S1, S6, S12, S15-S18, S24,
          S26, G15, G17, G19).

What it does NOT test (needs the full quotes of a snapshot, a later test):
  - which expiry and which listed strikes a new position takes (S1 snapping,
    S3-S5), and whether a put about to be opened has a broken quote,
  - whether the logged deltas are the Black-76 sticky-strike deltas of the data,
  - the daily equity file (interest, unrealised P&L, margin per day).

How to run (from the main folder; read-only, about one or two minutes):
    python validation/automatic/one_step_check.py

It prints a summary and writes every difference it finds, one row each, to
validation/automatic/output/one_step_<run>.csv. It writes nothing else.
"""

import csv                      # reads and writes CSV files row by row
import math                     # exp and sqrt for the target strikes
import os                       # to make the output folder
from datetime import date       # to count calendar days between two dates


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# The mutation tests (step 5) point the settings marked "(outside)" elsewhere through
# environment variables: os.environ.get("NAME", default) reads a setting given from
# outside the script, or uses the default. Run normally, nothing changes.
RESULTS_FOLDER = os.environ.get("CHECK_RESULTS_FOLDER", "results")          # the backtest's result files (outside)
ATM_VOL_FILE = os.environ.get("CHECK_ATM_VOL_FILE", "Data/05_atm_vol.csv")    # every snapshot time, F and ATM vol (outside)
OUTPUT_FOLDER = os.environ.get("CHECK_OUTPUT_FOLDER", "validation/automatic/output")   # the list of differences (outside)

# the four reported runs (outside: a comma-separated list; .split(",") cuts it at the commas)
RUNS = os.environ.get("CHECK_RUNS", "base_mid,base_cross,p15_mid,p15_cross").split(",")

# Profit exit at delta0 - band (def:exits). The p15 runs use 0.15 (sec:robustness, S33).
PROFIT_BAND = {"base_mid": 0.10, "base_cross": 0.10, "p15_mid": 0.15, "p15_cross": 0.15}

# How trades are priced (sec:costs, S24): at the midpoint, or crossing the spread.
EXECUTION = {"base_mid": "mid", "base_cross": "cross", "p15_mid": "mid", "p15_cross": "cross"}

LOSS_BAND = 0.10                # loss exit at delta0 + 0.10 (def:exits), the same in every run
GAMMA_FLOOR_DAYS = 10           # tau_exit = max(tau0 / 2, 10 days) (eq:gamma-exit)
SOLD_OFFSET = 1.0               # sold put at K = F * exp(-1 * sigma * sqrt(tau)) (eq:strikes)
BOUGHT_OFFSET = 2.3             # bought put at K = F * exp(-2.3 * sigma * sqrt(tau))
NUMBER_OF_SPREADS = 2           # two spreads (def:entry, S2)
DOLLARS_PER_POINT = 100         # one SPX option = 100 dollars per index point (G15)
MIN_DAYS = 30                   # shortest maturity allowed (def:tau-star, G5)
MAX_DAYS = 90                   # longest maturity when a deficit is recovered (def:tau-star)

BROKEN_VOL_JUMP = 0.03          # condition 1 of def:broken: iv moved by more than 3 vol points
BROKEN_WIDTH_RATIO = 3.0        # condition 2 of def:broken: quote more than 3 times as wide

# Tolerances, fixed before the first run (choice).
TOLERANCE = 1e-6                # two prices, deltas or points count as equal within this
EDGE = 1e-9                     # a value this close to a threshold is "on the edge": listed, not judged

EXIT_ACTIONS = ["loss", "profit", "gamma"]   # the exit reasons, in the order they are tested (G1)
SKIP_ACTION = "skipped (broken)"             # the log's word for a snapshot skipped for a broken quote
HOLD_ACTION = ""                             # the log leaves the action empty when the position is kept

# Numbers the thesis gives for the base case at mid (sec:broken-quotes, sec:monitoring,
# CLAUDE.md section 6), printed next to the counts of this script.
THESIS_BASE_MID = {
    "held snapshots": 95122,
    "snapshots skipped (broken)": 5,
    "snapshots with a leg missing": 22,
    "leg quotes meeting condition 1": 46,
    "leg quotes meeting conditions 1 and 2": 14,
    "leg quotes meeting all three": 5,
    "leg quotes that can be compared": 191587,
    "closed cycles": 699,
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def read_table(path):
    """
    Read a CSV file into a list of rows. Each row is a dictionary
    {column name: text}. Nothing is converted to numbers here.

    Example:  read_table("results/trades_base_mid.csv")[0]["credit"]  ->  "19.3"
    """
    rows = []
    with open(path, newline="") as file:            # newline="" is what the csv module asks for
        reader = csv.DictReader(file)               # DictReader uses the first line as column names
        for row in reader:
            rows.append(row)
    return rows


def to_number(text):
    """
    Turn a text field into a number. An empty field becomes None (no value).

    Example:  to_number("12.8") -> 12.8,   to_number("") -> None
    """
    if text == "":
        return None
    return float(text)


def days_to_expiry(time_text, expiration_text):
    """
    Calendar days from the date of a snapshot to the expiry date (def:tau-conv, D5).
    The clock time does not matter: all snapshots of a day have the same days.

    Example:  days_to_expiry("2012-01-03 09:45:00", "2012-02-18")  ->  46
    """
    snapshot_day = date.fromisoformat(time_text[:10])      # the first 10 characters are the date
    expiry_day = date.fromisoformat(expiration_text)
    difference = expiry_day - snapshot_day                 # a "timedelta", a length of time
    return difference.days                                 # its length in whole days


def is_equal(a, b):
    """True if two numbers are equal within TOLERANCE. None only equals None."""
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= TOLERANCE


def is_on_edge(value, threshold):
    """True if a value lies so close to a threshold that rounding could decide the side."""
    return abs(value - threshold) < EDGE


def add_problem(problems, run, part, statement, time, what, expected, found):
    """
    Append one difference to the list of problems. Every difference becomes one
    row of the output file, so nothing is lost even if the printout is short.
    """
    problem = {
        "run": run,
        "part": part,                 # A, B or C
        "statement": statement,       # the test specification's ID, e.g. "S8"
        "time": time,                 # the snapshot or the cycle's entry time
        "what": what,                 # in words
        "expected": expected,         # what the thesis rule gives
        "found": found,               # what the backtest logged
    }
    problems.append(problem)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def read_snapshot_times_and_atm(wanted_keys):
    """
    Read Data/05_atm_vol.csv line by line (about 165 MB, never all at once).
    Returns
      - the sorted list of every snapshot time in the data,
      - a dictionary {(time, root, expiration): (forward, atm_iv)} for the
        expiries in wanted_keys only (the entries of the four runs).

    The file has one line per snapshot and expiry, so a time appears many times.
    """
    all_times = set()                              # a set keeps each time only once
    atm_of_entry = {}

    with open(ATM_VOL_FILE, newline="") as file:
        reader = csv.reader(file)                  # csv.reader gives each line as a list of texts
        header = next(reader)                      # next() takes the first line, the column names
        time_column = header.index("quote_datetime")   # .index finds the position of a name in a list
        root_column = header.index("root")
        expiration_column = header.index("expiration")
        forward_column = header.index("forward")
        atm_column = header.index("atm_iv")

        for line in reader:
            time = line[time_column]
            all_times.add(time)

            key = (time, line[root_column], line[expiration_column])
            if key in wanted_keys:                 # only the expiries some run entered
                forward = float(line[forward_column])
                atm_iv = to_number(line[atm_column])
                atm_of_entry[key] = (forward, atm_iv)

    sorted_times = sorted(all_times)               # "YYYY-MM-DD HH:MM:SS" sorts in time order as text
    return sorted_times, atm_of_entry


def find_stock_close_times(times):
    """
    The stock-close snapshot of each day (sec:monitoring, S19): 16:00 on a normal
    day, 13:00 on an early-close day. A day is an early close when its last
    snapshot is 13:15, a normal day when it is 16:15 (G20).

    Returns (set of stock-close times, list of early-close days, list of days
    whose last snapshot is neither, which are reported and get no stock close).
    """
    last_time_of_day = {}                          # {day: last time}
    for time in times:                             # times are sorted, so the last one written wins
        day = time[:10]
        last_time_of_day[day] = time

    stock_close_times = set()
    early_close_days = []
    odd_days = []
    for day in sorted(last_time_of_day):
        clock = last_time_of_day[day][11:]         # characters 11 on are the clock time
        if clock == "16:15:00":
            stock_close_times.add(day + " 16:00:00")
        elif clock == "13:15:00":
            stock_close_times.add(day + " 13:00:00")
            early_close_days.append(day)
        else:
            odd_days.append(day + " (last snapshot " + clock + ")")

    return stock_close_times, early_close_days, odd_days


def organise_quote_log(run, quote_rows, problems):
    """
    Sort the rows of quotes_<run>.csv by time and kind.
    Returns two dictionaries {time: {"short": row, "long": row}}:
      held_by_time   the held position at that snapshot,
      entry_by_time  a position opened at that snapshot.
    At an exit snapshot a time is in both: the old position (exit) and the new one.
    """
    held_by_time = {}
    entry_by_time = {}

    for row in quote_rows:
        time = row["time"]
        if row["kind"] == "held":
            table = held_by_time
        elif row["kind"] == "entry":
            table = entry_by_time
        else:
            add_problem(problems, run, "A", "S35", time, "unknown kind in the quote log", "held or entry", row["kind"])
            continue

        if time not in table:
            table[time] = {}
        leg = row["leg"]                                       # "short" (sold) or "long" (bought)
        if leg in table[time]:
            add_problem(problems, run, "A", "S13", time, "two " + row["kind"] + " rows for the same leg", "one", "two")
        table[time][leg] = row

    # Every snapshot must have both legs.
    for table in [held_by_time, entry_by_time]:
        for time in table:
            if "short" not in table[time] or "long" not in table[time]:
                add_problem(problems, run, "A", "S2", time, "a leg is not in the quote log", "short and long", str(list(table[time])))

    return held_by_time, entry_by_time


def quote_of(row):
    """
    The numbers of one logged leg at one snapshot, as a dictionary of floats.
    "before" holds the quote the backtest compared it with (None if it did not
    compare, e.g. at an entry).
    """
    quote = {
        "bid": to_number(row["bid"]),
        "ask": to_number(row["ask"]),
        "iv": to_number(row["iv"]),
        "delta": to_number(row["delta"]),
        "strike": to_number(row["strike"]),
    }
    if row["bid_before"] == "":
        quote["before"] = None
    else:
        quote["before"] = {
            "bid": to_number(row["bid_before"]),
            "ask": to_number(row["ask_before"]),
            "iv": to_number(row["iv_before"]),
        }
    return quote


def build_positions(run, entry_by_time, trades, problems):
    """
    One position per entry in the quote log, in time order, each with its
    closed-cycle row from trades_<run>.csv (None for the position still open
    at the end of the sample, G18).
    """
    trade_of_entry = {}                                       # {entry time: trade row}
    for trade in trades:
        trade_of_entry[trade["entry_time"]] = trade

    positions = []
    for entry_time in sorted(entry_by_time):
        legs = entry_by_time[entry_time]
        if "short" not in legs or "long" not in legs:         # already reported
            continue
        position = {
            "entry_time": entry_time,
            "root": legs["short"]["root"],
            "expiration": legs["short"]["expiration"],
            "short_entry": quote_of(legs["short"]),
            "long_entry": quote_of(legs["long"]),
            "trade": trade_of_entry.get(entry_time),          # .get gives None if there is no such key
        }
        positions.append(position)

    # Every trade must have its entry in the quote log, and only the last
    # position may be without a trade (the one open at the end).
    for trade in trades:
        if trade["entry_time"] not in entry_by_time:
            add_problem(problems, run, "C", "S35", trade["entry_time"], "trade without entry rows in the quote log", "entry rows", "none")
    for number in range(len(positions)):
        is_last = number == len(positions) - 1
        if positions[number]["trade"] is None and not is_last:
            add_problem(problems, run, "C", "S35", positions[number]["entry_time"], "entry without a closed trade", "a trade row", "none")

    return positions


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------

def position_delta(short_quote, long_quote):
    """
    Delta of the whole position (eq:posdelta): sold 2 puts, bought 2 puts, so
        Delta_pos = 2 * (Delta_bought - Delta_sold).
    Put deltas are negative, the sold one more so, hence Delta_pos > 0.

    Example:  sold -0.204611, bought -0.065873  ->  2 * 0.138738 = 0.277476
    """
    return NUMBER_OF_SPREADS * (long_quote["delta"] - short_quote["delta"])


def broken_conditions(now, before):
    """
    The three conditions of def:broken for one leg, comparing the quote now with
    the quote "before". Returns (condition 1, condition 2, condition 3, edge),
    edge = True if a value lies on a threshold to rounding.

      1.  |iv_now - iv_before| > 0.03
      2.  w_now > 3 * w_before                    (w = ask - bid, the width)
      3.  w_now - w_before > |m_now - m_before|   (m = (bid + ask) / 2, the midpoint)
    """
    vol_jump = abs(now["iv"] - before["iv"])
    width_now = now["ask"] - now["bid"]
    width_before = before["ask"] - before["bid"]
    mid_now = (now["bid"] + now["ask"]) / 2
    mid_before = (before["bid"] + before["ask"]) / 2
    widening = width_now - width_before
    mid_move = abs(mid_now - mid_before)

    condition_1 = vol_jump > BROKEN_VOL_JUMP
    condition_2 = width_now > BROKEN_WIDTH_RATIO * width_before
    condition_3 = widening > mid_move

    edge = False
    if is_on_edge(vol_jump, BROKEN_VOL_JUMP):
        edge = True
    if is_on_edge(width_now, BROKEN_WIDTH_RATIO * width_before):
        edge = True
    if is_on_edge(widening, mid_move):
        edge = True

    return condition_1, condition_2, condition_3, edge


def is_broken(now, before):
    """True if all three conditions of def:broken hold. No 'before' quote: not broken."""
    if before is None:
        return False
    condition_1, condition_2, condition_3, edge = broken_conditions(now, before)
    return condition_1 and condition_2 and condition_3


def exit_decision(delta_pos, delta0, profit_band, days_left, exit_days):
    """
    The exit rules of def:exits at one snapshot. Tested in the order loss, profit,
    gamma, and the first that holds is the reason (G1). Returns
    (action, number of triggers that hold, edge). action is "" if the position is kept.

      loss:    Delta_pos >= Delta0 + 0.10
      profit:  Delta_pos <= Delta0 - band      (band 0.10, or 0.15 in p15)
      gamma:   days_left <= max(tau0 / 2, 10)  (whole days, G10)

    Example:  exit_decision(0.40, 0.27, 0.10, 20, 23.0)  ->  ("loss", 2, False)
    """
    loss_level = delta0 + LOSS_BAND
    profit_level = delta0 - profit_band

    loss = delta_pos >= loss_level
    profit = delta_pos <= profit_level
    gamma = days_left <= exit_days

    triggers = 0                                  # how many hold at once
    if loss:
        triggers = triggers + 1
    if profit:
        triggers = triggers + 1
    if gamma:
        triggers = triggers + 1

    edge = is_on_edge(delta_pos, loss_level) or is_on_edge(delta_pos, profit_level)

    if loss:
        return "loss", triggers, edge
    if profit:
        return "profit", triggers, edge
    if gamma:
        return "gamma", triggers, edge
    return HOLD_ACTION, triggers, edge


def new_deficit(deficit, pnl):
    """
    The deficit after a cycle (def:deficit), pnl in index points:
      pnl >= L        ->  0
      0 <= pnl < L    ->  L - pnl
      pnl < 0         ->  -pnl   (the old deficit is dropped)

    Example:  new_deficit(9.4, 3.0) -> 6.4,   new_deficit(9.4, -5.0) -> 5.0
    """
    if pnl >= deficit:
        return 0.0
    if pnl >= 0:
        return deficit - pnl
    return -pnl


def spread_price(short_quote, long_quote, how):
    """
    The value of the two spreads in index points, at one snapshot (sec:costs, S24).
      how = "mid":         2 * (mid_sold - mid_bought)
      how = "open_cross":  2 * (bid_sold - ask_bought)    we sell the higher put at its bid
                                                          and buy the lower one at its ask
      how = "close_cross": 2 * (ask_sold - bid_bought)    to close we buy back the higher put
                                                          at its ask and sell the lower at its bid
    """
    if how == "mid":
        short_price = (short_quote["bid"] + short_quote["ask"]) / 2
        long_price = (long_quote["bid"] + long_quote["ask"]) / 2
    elif how == "open_cross":
        short_price = short_quote["bid"]
        long_price = long_quote["ask"]
    elif how == "close_cross":
        short_price = short_quote["ask"]
        long_price = long_quote["bid"]
    else:
        raise ValueError("unknown price: " + how)
    return NUMBER_OF_SPREADS * (short_price - long_price)


# ---------------------------------------------------------------------------
# Parts A and B: walk through every snapshot of every position
# ---------------------------------------------------------------------------

def walk_position(run, position, times, time_index, stock_close_times,
                  held_by_time, missing_by_time, visited, counts, problems):
    """
    Go through every snapshot of the data from just after the position's entry
    to its exit (or to the end of the data for the position still open) and
    check the schedule (Part A) and the decision (Part B) at each one.

    Fills in position["first_exit_time"], position["short_exit"],
    position["long_exit"], and the numbers of skipped and missing snapshots.
    """
    entry_time = position["entry_time"]
    trade = position["trade"]

    if entry_time not in time_index:
        add_problem(problems, run, "A", "S13", entry_time, "entry time is not a snapshot of the data", "a data snapshot", "missing")
        return
    if entry_time in stock_close_times:
        add_problem(problems, run, "A", "S19", entry_time, "position opened at the stock close", "no entry", "entry")

    # Where the position's snapshots start and end in the list of all times.
    first = time_index[entry_time] + 1                 # tested from the next snapshot on (S12)
    if trade is None:
        last = len(times) - 1                          # still open: to the end of the data (G18)
    elif trade["exit_time"] in time_index:
        last = time_index[trade["exit_time"]]
    else:
        add_problem(problems, run, "A", "S13", trade["exit_time"], "exit time is not a snapshot of the data", "a data snapshot", "missing")
        return

    # The state fixed at entry (sec:entry-delta, S6).
    delta0 = position_delta(position["short_entry"], position["long_entry"])
    days0 = days_to_expiry(entry_time, position["expiration"])
    exit_days = max(days0 / 2, GAMMA_FLOOR_DAYS)         # tau_exit = max(tau0 / 2, 10 days)
    profit_band = PROFIT_BAND[run]
    position["delta0"] = delta0
    position["days0"] = days0
    position["exit_days"] = exit_days

    # Three memories per leg while walking (one per reading of t-minus, def:broken):
    #   last_logged    the leg's quote at the previous snapshot the backtest logged
    #                  (what the backtest's own "before" columns should show)
    #   last_good      the leg's last quote that was not broken (G11, Arian's rule)
    #   present_unlogged  True if since the last logged snapshot the leg was quoted at a
    #                  snapshot where the other leg was missing (its quote is not in the log)
    last_logged = {"short": position["short_entry"], "long": position["long_entry"]}
    last_good = {"short": position["short_entry"], "long": position["long_entry"]}
    present_unlogged = {"short": False, "long": False}
    previous_snapshot = None          # None = a logged snapshot (or the entry), else the missing-log row

    position["first_exit_time"] = None
    position["skipped_broken"] = 0
    position["missing"] = 0

    for number in range(first, last + 1):
        time = times[number]

        # ---- Part A: the stock close (S19) ----
        if time in stock_close_times:
            if time in held_by_time or time in missing_by_time:
                add_problem(problems, run, "A", "S19", time, "a row at the stock close", "nothing", "a logged snapshot")
            counts["stock closes passed"] = counts["stock closes passed"] + 1
            continue                                   # never a decision, never t-minus

        held = held_by_time.get(time)
        missing = missing_by_time.get(time)

        # ---- Part A: every snapshot is logged once, as held or as missing (S13, S22) ----
        if held is not None and missing is not None:
            add_problem(problems, run, "A", "S22", time, "logged both as held and as missing", "one of them", "both")
            continue
        if held is None and missing is None:
            add_problem(problems, run, "A", "S13", time, "snapshot of the data not in any log", "held or missing", "nothing")
            continue
        visited.add(time)

        # ---- Part A: a snapshot with a leg missing: no decision (S22) ----
        if missing is not None:
            # The missing-leg row must name this position's two puts
            # (the brackets let one condition run over several lines).
            same_position = (missing["root"] == position["root"]
                             and missing["expiration"] == position["expiration"]
                             and is_equal(to_number(missing["strike_short"]), position["short_entry"]["strike"])
                             and is_equal(to_number(missing["strike_long"]), position["long_entry"]["strike"]))
            if not same_position:
                add_problem(problems, run, "A", "S22", time, "missing-leg row of another position", position["root"] + " " + position["expiration"], missing["root"] + " " + missing["expiration"])
            position["missing"] = position["missing"] + 1
            counts["snapshots with a leg missing"] = counts["snapshots with a leg missing"] + 1
            for leg in ["short", "long"]:
                if missing[leg + "_missing"] != "True":       # this leg was quoted there
                    present_unlogged[leg] = True
            previous_snapshot = missing
            continue

        # ---- Part B: a held snapshot ----
        counts["held snapshots"] = counts["held snapshots"] + 1
        if position["first_exit_time"] is not None:
            add_problem(problems, run, "B", "S12", time, "still held after its exit", "closed at " + position["first_exit_time"], "held")

        quotes = {}
        for leg in ["short", "long"]:
            row = held[leg]
            # The row must be this position's put.
            expected_strike = position[leg + "_entry"]["strike"]
            if (row["root"] != position["root"] or row["expiration"] != position["expiration"]
                    or not is_equal(to_number(row["strike"]), expected_strike)):
                add_problem(problems, run, "B", "S13", time, leg + " leg is another put than the one opened", position["root"] + " " + position["expiration"] + " " + str(expected_strike), row["root"] + " " + row["expiration"] + " " + row["strike"])
            quote = quote_of(row)
            # A usable leg has a delta and a quote (G12).
            if quote["delta"] is None or quote["bid"] is None or quote["ask"] is None or quote["iv"] is None:
                add_problem(problems, run, "B", "S22", time, leg + " leg logged without delta, bid, ask or iv", "all four", "one missing")
            quotes[leg] = quote
        if None in [quotes["short"]["delta"], quotes["long"]["delta"]]:
            continue                                   # cannot test this snapshot, already reported

        # -- Which quote did the backtest compare with? (def:broken, t-minus; for information) --
        for leg in ["short", "long"]:
            before = quotes[leg]["before"]
            if previous_snapshot is None:
                # The previous snapshot was logged: "before" should be that quote.
                expected = last_logged[leg]
                same = (before is not None and is_equal(before["bid"], expected["bid"])
                        and is_equal(before["ask"], expected["ask"]) and is_equal(before["iv"], expected["iv"]))
                if same:
                    counts["t-minus = previous logged snapshot"] = counts["t-minus = previous logged snapshot"] + 1
                else:
                    if before is None:
                        found_text = "no quote"
                    else:
                        found_text = str(before["bid"]) + "/" + str(before["ask"])
                    add_problem(problems, run, "B", "S20", time, leg + ": compared with another quote than the previous logged one", str(expected["bid"]) + "/" + str(expected["ask"]), found_text)
            elif previous_snapshot[leg + "_missing"] == "True":
                # The leg had no quote at the previous snapshot.
                if before is None:
                    counts["t-minus: leg missing there, not compared"] = counts["t-minus: leg missing there, not compared"] + 1
                else:
                    counts["t-minus: leg missing there, compared with an earlier quote"] = counts["t-minus: leg missing there, compared with an earlier quote"] + 1
            else:
                # The leg was quoted at the previous snapshot, but that quote is not
                # in the log (the other leg was missing). Cannot be checked here.
                counts["t-minus: previous quote not in the log"] = counts["t-minus: previous quote not in the log"] + 1

        # -- The broken-quote test with the quote the backtest logged as "before" (S20) --
        broken_as_logged = {}
        for leg in ["short", "long"]:
            now = quotes[leg]
            before = now["before"]
            broken_as_logged[leg] = False
            if before is None:
                continue
            counts["leg quotes that can be compared"] = counts["leg quotes that can be compared"] + 1
            condition_1, condition_2, condition_3, edge = broken_conditions(now, before)
            if condition_1:
                counts["leg quotes meeting condition 1"] = counts["leg quotes meeting condition 1"] + 1
            if condition_1 and condition_2:
                counts["leg quotes meeting conditions 1 and 2"] = counts["leg quotes meeting conditions 1 and 2"] + 1
            if condition_1 and condition_2 and condition_3:
                counts["leg quotes meeting all three"] = counts["leg quotes meeting all three"] + 1
                broken_as_logged[leg] = True
            if edge:
                counts["broken test on the edge"] = counts["broken test on the edge"] + 1
                add_problem(problems, run, "B", "S20 (edge)", time, leg + ": a broken-quote condition lies on its threshold", "", "")

            # The log's own vol_jump and width_ratio columns must be what they say.
            vol_jump = abs(now["iv"] - before["iv"])
            width_ratio = (now["ask"] - now["bid"]) / (before["ask"] - before["bid"])
            logged_jump = to_number(held[leg]["vol_jump"])
            logged_ratio = to_number(held[leg]["width_ratio"])
            if not is_equal(vol_jump, logged_jump) or not is_equal(width_ratio, logged_ratio):
                add_problem(problems, run, "B", "S20", time, leg + ": logged vol_jump / width_ratio", str(vol_jump) + " / " + str(width_ratio), str(logged_jump) + " / " + str(logged_ratio))

        # -- The broken-quote test against the last good quote (G11, Arian's rule) --
        broken_by_g11 = {}
        for leg in ["short", "long"]:
            now = quotes[leg]
            if present_unlogged[leg] and now["before"] is not None:
                # The leg's quote at the missing-leg snapshot is not in the log. The
                # backtest's "before" is taken to be that quote (an assumption).
                # It becomes the last good quote unless it was broken itself.
                candidate = now["before"]
                if not is_broken(candidate, last_good[leg]):
                    last_good[leg] = candidate
            broken_by_g11[leg] = is_broken(now, last_good[leg])

        # -- The decision (S7-S11, S21) --
        delta_pos = position_delta(quotes["short"], quotes["long"])
        days_left = days_to_expiry(time, position["expiration"])
        logged_action = held["short"]["action"]
        if held["long"]["action"] != logged_action:
            add_problem(problems, run, "B", "S35", time, "the two legs have different actions", logged_action, held["long"]["action"])

        if broken_as_logged["short"] or broken_as_logged["long"]:
            expected_action = SKIP_ACTION                     # no mark, no test (S21)
            triggers = 0
            edge = False
        else:
            expected_action, triggers, edge = exit_decision(delta_pos, delta0, profit_band, days_left, exit_days)

        if edge:
            counts["exit test on the edge"] = counts["exit test on the edge"] + 1
            add_problem(problems, run, "B", "S8/S9 (edge)", time, "position delta lies on a band edge", "", str(delta_pos))
        if triggers >= 2:
            counts["two or more triggers at once"] = counts["two or more triggers at once"] + 1

        if expected_action == logged_action:
            counts["decisions the same"] = counts["decisions the same"] + 1
        else:
            add_problem(problems, run, "B", "S8-S11, S21", time, "decision (delta_pos " + str(round(delta_pos, 6)) + ", delta0 " + str(round(delta0, 6)) + ", days " + str(days_left) + ")", expected_action, logged_action)

        # Arian's G11 rule: would the decision differ? (code change pending, information)
        if broken_by_g11["short"] or broken_by_g11["long"]:
            g11_action = SKIP_ACTION
        else:
            g11_action, g11_triggers, g11_edge = exit_decision(delta_pos, delta0, profit_band, days_left, exit_days)
        if g11_action != logged_action:
            counts["decisions that differ under G11"] = counts["decisions that differ under G11"] + 1
            add_problem(problems, run, "B", "G11", time, "decision with the last good quote as t-minus", g11_action, logged_action)

        # Count the actions as the backtest logged them.
        if logged_action == SKIP_ACTION:
            position["skipped_broken"] = position["skipped_broken"] + 1
            counts["snapshots skipped (broken)"] = counts["snapshots skipped (broken)"] + 1
        if logged_action in EXIT_ACTIONS and position["first_exit_time"] is None:
            position["first_exit_time"] = time
            position["exit_reason"] = logged_action
            position["short_exit"] = quotes["short"]
            position["long_exit"] = quotes["long"]

        # Update the memories for the next snapshot.
        for leg in ["short", "long"]:
            last_logged[leg] = quotes[leg]
            present_unlogged[leg] = False
            if not broken_by_g11[leg]:
                last_good[leg] = quotes[leg]
        previous_snapshot = None


# ---------------------------------------------------------------------------
# Part C: each closed cycle
# ---------------------------------------------------------------------------

def check_number(problems, run, statement, time, field, expected, found_text):
    """Compare one number of the trade log with the value worked out here. Returns 1 (a field checked)."""
    found = to_number(found_text)
    if not is_equal(expected, found):
        add_problem(problems, run, "C", statement, time, field, str(expected), found_text)
    return 1


def check_cycles(run, positions, atm_of_entry, first_data_time, stock_close_times, counts, problems):
    """
    Check every closed cycle of trades_<run>.csv against the logged quotes at its
    entry and exit and against the thesis rules. The deficit is carried from one
    cycle to the next by this script itself, starting at 0 (S14).
    """
    deficit = 0.0                                  # L = 0 at the start (def:deficit, S14)
    fields = 0

    # The first position is opened at the first snapshot of the data (G19).
    if len(positions) > 0 and positions[0]["entry_time"] != first_data_time:
        add_problem(problems, run, "C", "G19", positions[0]["entry_time"], "first entry", first_data_time, positions[0]["entry_time"])

    for number in range(len(positions)):
        position = positions[number]
        trade = position["trade"]
        if trade is None:
            continue                               # the position still open at the end (G18)
        if "delta0" not in position:
            continue                               # its walk stopped early, already reported
        time = position["entry_time"]
        short_entry = position["short_entry"]
        long_entry = position["long_entry"]
        counts["closed cycles"] = counts["closed cycles"] + 1

        # -- Entry (S1, S2, S6, S26, G15) --
        if trade["root"] != position["root"] or trade["expiration"] != position["expiration"]:
            add_problem(problems, run, "C", "S35", time, "root / expiration", position["root"] + " " + position["expiration"], trade["root"] + " " + trade["expiration"])
        fields = fields + check_number(problems, run, "S1", time, "strike_short", short_entry["strike"], trade["strike_short"])
        fields = fields + check_number(problems, run, "S1", time, "strike_long", long_entry["strike"], trade["strike_long"])
        fields = fields + check_number(problems, run, "S35", time, "iv_short0", short_entry["iv"], trade["iv_short0"])
        fields = fields + check_number(problems, run, "S35", time, "iv_long0", long_entry["iv"], trade["iv_long0"])
        fields = fields + check_number(problems, run, "S6", time, "delta0", position["delta0"], trade["delta0"])
        fields = fields + check_number(problems, run, "S6", time, "dte0", position["days0"], trade["dte0"])
        fields = fields + check_number(problems, run, "S10", time, "exit_days", position["exit_days"], trade["exit_days"])

        if short_entry["strike"] <= long_entry["strike"]:
            add_problem(problems, run, "C", "G3", time, "sold strike not above bought strike", "above", str(short_entry["strike"]))

        # The credit: at execution prices (G6), and at mid.
        if EXECUTION[run] == "mid":
            credit = spread_price(short_entry, long_entry, "mid")
        else:
            credit = spread_price(short_entry, long_entry, "open_cross")
        credit_mid = spread_price(short_entry, long_entry, "mid")
        fields = fields + check_number(problems, run, "S24", time, "credit", credit, trade["credit"])
        fields = fields + check_number(problems, run, "S24", time, "credit_mid", credit_mid, trade["credit_mid"])

        # Margin = maximum loss at entry = (2 * width - credit) * 100 dollars (G15, S26).
        width = short_entry["strike"] - long_entry["strike"]
        margin = (NUMBER_OF_SPREADS * width - credit) * DOLLARS_PER_POINT
        fields = fields + check_number(problems, run, "S26", time, "margin", margin, trade["margin"])

        # Forward and ATM vol of the expiry traded, from the data (S1).
        key = (time, position["root"], position["expiration"])
        if key in atm_of_entry:
            forward, atm_iv = atm_of_entry[key]
            fields = fields + check_number(problems, run, "S1", time, "forward0", forward, trade["forward0"])
            fields = fields + check_number(problems, run, "S1", time, "atm_iv0", atm_iv, trade["atm_iv0"])
        else:
            add_problem(problems, run, "C", "S1", time, "expiry traded has no row in 05_atm_vol", "a row", "none")

        # Target strikes K = F * exp(-k * sigma * sqrt(tau)), tau = days / 365 (eq:strikes).
        forward0 = to_number(trade["forward0"])
        sigma0 = to_number(trade["atm_iv0"])
        sqrt_tau = math.sqrt(position["days0"] / 365)
        target_short = forward0 * math.exp(-SOLD_OFFSET * sigma0 * sqrt_tau)
        target_long = forward0 * math.exp(-BOUGHT_OFFSET * sigma0 * sqrt_tau)
        fields = fields + check_number(problems, run, "S1", time, "target_short", target_short, trade["target_short"])
        fields = fields + check_number(problems, run, "S1", time, "target_long", target_long, trade["target_long"])

        # Deficit at entry and the maturity rule it implies (S3-S5, partly).
        fields = fields + check_number(problems, run, "S15-S17", time, "deficit_at_entry", deficit, trade["deficit_at_entry"])
        rule = trade["maturity_rule"]
        if deficit <= TOLERANCE:
            if rule != "target":
                add_problem(problems, run, "C", "S3", time, "maturity rule with no deficit", "target", rule)
        else:
            if rule not in ["recovery", "cap"]:
                add_problem(problems, run, "C", "S4/S5", time, "maturity rule with a deficit", "recovery or cap", rule)
            if position["days0"] > MAX_DAYS:
                add_problem(problems, run, "C", "S4/S5", time, "days to expiry with a deficit", "at most 90", str(position["days0"]))
        if position["days0"] < MIN_DAYS:
            add_problem(problems, run, "C", "S3", time, "days to expiry", "at least 30", str(position["days0"]))

        # -- Exit (S8-S12, S18, S24) --
        exit_time = position["first_exit_time"]
        if exit_time is None:
            add_problem(problems, run, "C", "S8-S10", time, "closed trade without an exit in the quote log", trade["exit_time"], "none")
            continue
        if exit_time != trade["exit_time"]:
            add_problem(problems, run, "C", "S8-S10", time, "exit time", exit_time, trade["exit_time"])
        if position["exit_reason"] != trade["reason"]:
            add_problem(problems, run, "C", "S8-S10", time, "exit reason", position["exit_reason"], trade["reason"])
        if exit_time in stock_close_times:
            add_problem(problems, run, "C", "S19", time, "exit at the stock close", "never", exit_time)

        short_exit = position["short_exit"]
        long_exit = position["long_exit"]
        fields = fields + check_number(problems, run, "S35", time, "dte_exit", days_to_expiry(exit_time, position["expiration"]), trade["dte_exit"])
        fields = fields + check_number(problems, run, "S35", time, "iv_short_exit", short_exit["iv"], trade["iv_short_exit"])
        fields = fields + check_number(problems, run, "S35", time, "iv_long_exit", long_exit["iv"], trade["iv_long_exit"])
        fields = fields + check_number(problems, run, "S7", time, "delta_exit", position_delta(short_exit, long_exit), trade["delta_exit"])

        # Cost of closing, at execution prices and at mid (S24).
        if EXECUTION[run] == "mid":
            cost = spread_price(short_exit, long_exit, "mid")
        else:
            cost = spread_price(short_exit, long_exit, "close_cross")
        cost_mid = spread_price(short_exit, long_exit, "mid")
        pnl = credit - cost                        # pi = credit received - cost of closing (S18)
        pnl_mid = credit_mid - cost_mid
        fields = fields + check_number(problems, run, "S24", time, "cost", cost, trade["cost"])
        fields = fields + check_number(problems, run, "S24", time, "cost_mid", cost_mid, trade["cost_mid"])
        fields = fields + check_number(problems, run, "S18", time, "pnl", pnl, trade["pnl"])
        fields = fields + check_number(problems, run, "S18", time, "pnl_mid", pnl_mid, trade["pnl_mid"])
        fields = fields + check_number(problems, run, "S24", time, "spread_cost", pnl_mid - pnl, trade["spread_cost"])
        fields = fields + check_number(problems, run, "S18", time, "pnl_dollars", pnl * DOLLARS_PER_POINT, trade["pnl_dollars"])
        fields = fields + check_number(problems, run, "S29", time, "return_on_margin", pnl * DOLLARS_PER_POINT / margin, trade["return_on_margin"])

        # The deficit after the cycle, with pi at execution prices (def:deficit, G17).
        deficit = new_deficit(deficit, pnl)
        fields = fields + check_number(problems, run, "S15-S17", time, "deficit_after", deficit, trade["deficit_after"])

        # The skip counts of the cycle (column meaning read from their names).
        fields = fields + check_number(problems, run, "S21", time, "skipped_broken", position["skipped_broken"], trade["skipped_broken"])
        fields = fields + check_number(problems, run, "S22", time, "skipped (leg missing)", position["missing"], trade["skipped"])

        # The next position opens at the exit snapshot (S12), so one is always open (S13).
        if number + 1 < len(positions):
            next_entry = positions[number + 1]["entry_time"]
            if next_entry != exit_time:
                add_problem(problems, run, "C", "S12/S13", time, "next entry", exit_time, next_entry)

    counts["trade fields checked"] = fields


# ---------------------------------------------------------------------------
# One run
# ---------------------------------------------------------------------------

def check_run(run, logs, times, time_index, stock_close_times, atm_of_entry):
    """Run Parts A, B and C for one run. Returns (counts, problems)."""
    quote_rows, missing_rows, trades = logs[run]
    problems = []

    # Every counter starts at 0, in the order they are printed.
    counts = {}
    for name in ["held snapshots", "snapshots skipped (broken)", "snapshots with a leg missing",
                 "stock closes passed", "decisions the same", "two or more triggers at once",
                 "exit test on the edge", "leg quotes that can be compared",
                 "leg quotes meeting condition 1", "leg quotes meeting conditions 1 and 2",
                 "leg quotes meeting all three", "broken test on the edge",
                 "t-minus = previous logged snapshot", "t-minus: leg missing there, not compared",
                 "t-minus: leg missing there, compared with an earlier quote",
                 "t-minus: previous quote not in the log", "decisions that differ under G11",
                 "closed cycles", "trade fields checked"]:
        counts[name] = 0

    held_by_time, entry_by_time = organise_quote_log(run, quote_rows, problems)

    missing_by_time = {}
    for row in missing_rows:
        missing_by_time[row["when"]] = row

    positions = build_positions(run, entry_by_time, trades, problems)
    counts["positions (closed + open at the end)"] = len(positions)

    # Parts A and B.
    visited = set()                          # every logged time the walk passed
    for position in positions:
        walk_position(run, position, times, time_index, stock_close_times,
                      held_by_time, missing_by_time, visited, counts, problems)

    # Logged times that belong to no position's snapshots (Part A, S13).
    for time in sorted(held_by_time):
        if time not in visited:
            add_problem(problems, run, "A", "S13", time, "held row outside every position's snapshots", "none", "a held row")
    for time in sorted(missing_by_time):
        if time not in visited:
            add_problem(problems, run, "A", "S22", time, "missing-leg row outside every position's snapshots", "none", "a row")

    # Part C.
    check_cycles(run, positions, atm_of_entry, times[0], stock_close_times, counts, problems)

    return counts, problems


def write_problems(run, problems):
    """Write every difference of one run to OUTPUT_FOLDER/one_step_<run>.csv."""
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)          # make the folder; exist_ok: no error if it exists
    path = OUTPUT_FOLDER + "/one_step_" + run + ".csv"
    columns = ["run", "part", "statement", "time", "what", "expected", "found"]
    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)   # writes dictionaries as CSV rows
        writer.writeheader()
        for problem in problems:
            writer.writerow(problem)
    return path


def print_summary(run, counts, problems, path):
    """Print the counts and the differences by part and statement."""
    print()
    print("=" * 78)
    print("Run " + run)
    print("=" * 78)
    for name in counts:
        line = "  " + name.ljust(58) + str(counts[name]).rjust(10)    # ljust/rjust pad with spaces
        if run == "base_mid" and name in THESIS_BASE_MID:
            line = line + "   (thesis " + str(THESIS_BASE_MID[name]) + ")"
        print(line)

    # Count the differences by (part, statement).
    by_kind = {}
    for problem in problems:
        kind = problem["part"] + "  " + problem["statement"]
        if kind not in by_kind:
            by_kind[kind] = 0
        by_kind[kind] = by_kind[kind] + 1

    print()
    if len(problems) == 0:
        print("  No differences.")
    else:
        print("  Differences and notes by part and statement (all rows in " + path + "):")
        for kind in sorted(by_kind):
            print("    " + kind.ljust(30) + str(by_kind[kind]).rjust(8))
        print("  First rows:")
        shown = 0
        for problem in problems:
            if shown == 10:
                break
            print("    " + problem["part"] + " " + problem["statement"] + " " + problem["time"]
                  + " | " + problem["what"] + " | expected " + problem["expected"] + " | found " + problem["found"])
            shown = shown + 1


# ---------------------------------------------------------------------------
# Main: read, check, write
# ---------------------------------------------------------------------------

def main():
    # 1. Read the three logs of each run (a few tens of MB each, read whole).
    logs = {}
    wanted_keys = set()                                  # (time, root, expiration) of every entry
    for run in RUNS:
        quote_rows = read_table(RESULTS_FOLDER + "/quotes_" + run + ".csv")
        missing_rows = read_table(RESULTS_FOLDER + "/missing_" + run + ".csv")
        trades = read_table(RESULTS_FOLDER + "/trades_" + run + ".csv")
        logs[run] = (quote_rows, missing_rows, trades)
        for trade in trades:
            wanted_keys.add((trade["entry_time"], trade["root"], trade["expiration"]))
        print("read " + run + ": " + str(len(quote_rows)) + " quote rows, "
              + str(len(missing_rows)) + " missing-leg rows, " + str(len(trades)) + " trades")

    # 2. Read every snapshot time of the data, and F and the ATM vol at each entry.
    times, atm_of_entry = read_snapshot_times_and_atm(wanted_keys)
    time_index = {}                                      # {time: its position in the sorted list}
    for number in range(len(times)):
        time_index[times[number]] = number

    stock_close_times, early_close_days, odd_days = find_stock_close_times(times)
    print("data: " + str(len(times)) + " snapshot times, " + str(len(early_close_days))
          + " early-close days, " + str(len(odd_days)) + " days ending neither at 16:15 nor at 13:15")
    for day in odd_days:
        print("  odd day: " + day)

    # 3. Check each run and write its differences.
    for run in RUNS:
        counts, problems = check_run(run, logs, times, time_index, stock_close_times, atm_of_entry)
        path = write_problems(run, problems)
        print_summary(run, counts, problems, path)


main()
