"""
THE BACKTEST (stage 3)

What this file is for:
    It runs the strategy through the whole sample, one 15-minute snapshot at a
    time, as one continuous simulation. At every moment we either hold one
    position (two bull put spreads on one expiry) or we open one.

    The rules are those of the thesis, chapter 2. The design, with every choice
    that the thesis leaves open, is in backtest_design.md.

WHAT IS IN THIS VERSION (build steps 1 to 3)
    - opening a position (strikes, credit, entry delta)
    - watching it at every snapshot and the three exits (loss, profit, gamma)
    - closing it and immediately opening the next one
    - the loss deficit L: after a loss it becomes that loss (base case, see
      RECOVERY_MODE below), a profit pays it down, never below 0
    - with L > 0, the maturity rule picks the shortest expiry whose credit covers
      the deficit (thesis, "Maturity selection")
    - the stress flag, recorded on each trade (it does NOT change any decision;
      decided 2026-10-08, see backtest_design.md)

    - cash and the equity curve (build step 4, decided 2026-10-08): the capital
      of each cycle is its MARGIN, the most the position can lose. That margin is
      held in T-bills and earns the 3-month rate. The open position is marked to
      the mid quote at the last snapshot of each day. One row per day goes to
      EQUITY_FILE (equity_<run>.csv). The return of a period (a quarter, a
      year) is its P&L divided by the average margin held in it ("return on
      margin", function period_returns, sec:backtest-design).

    - the end of the day (decided 2026-10-23, review_log.md C8 and C9).
        C9: the snapshot at the stock close (16:00, or 13:00 on early-close days)
            has unreliable option quotes. No decision is taken there: no exit
            test, no new position. The next snapshot takes over. Switch
            SKIP_CLOSE_SNAPSHOT below.
        C8: the snapshot after the close (16:15, or 13:15) has a meaningless
            index quote. Since 2026-10-27 (review_log.md C15) this is fixed in
            the DATA: stage 1 (Code/s01_stage1_extract_simple.py) takes S there
            to be the official daily close, so the stored deltas are right and
            the backtest uses them as they are. (Until then the backtest
            corrected those deltas itself, switch USE_OFFICIAL_CLOSE; that code
            is in commit 4aca3ae, tag thesis-v1.)

    - broken option quotes (decided 2026-10-25, review_log.md C14; developed
      in a separate experiment, removed 2026-10-29). Also a problem of the DATA: some quotes are
      broken for one snapshot, e.g. 12.3 / 52.6 for a put quoted 48.3 / 50.0 a
      snapshot earlier, which gives a meaningless implied vol and delta, and so
      a false exit. A leg's quote counts as broken when its implied vol jumped
      since the previous snapshot used AND its bid/ask became much wider than it
      was then AND it widened more than its mid moved (3 vol points, 3 times).
      Only the past is used, never the next snapshot. A broken quote is treated
      like a missing one: no decision, the next snapshot takes over. Switch
      QUOTE_RULE below; "off" uses every quote as it comes (the comparison
      runs named "..._without_quote_rule").

HOW TO RUN IT
    python Code/s11_backtest.py
"""

import numpy as np
import pandas as pd

from s06_greeks import spread_delta        # reuse the function from s06_greeks.py
from s03_rates import load_rates, rate_for  # reuse the T-bill rates from s03_rates.py


# ---- files ------------------------------------------------------------

ATM_FILE = "Data/05_atm_vol.csv"           # input: ATM volatility per slice
VOL30_FILE = "Data/06_vol30.csv"           # input: daily 30-day vol (from s09_vol_series.py)
GREEKS_FOLDER = "Data/04_greeks"           # input: stage 2 output, one file per month

# ---- the strategy (thesis, table "The complete strategy specification") ---

K1 = 1.0                                   # short put, in standard deviations below F
K2 = 2.3                                   # long put, in standard deviations below F
HOW_MANY_SPREADS = 2                       # n, the number of spreads
TARGET_DAYS = 30                           # target maturity
MAX_DAYS = 90                              # maturity cap
# the delta band: loss exit at delta0 + BAND_LOSS, profit exit at delta0 - BAND_PROFIT.
# BAND_PROFIT = None means "no profit exit": hold until the loss or gamma exit.
# (Base case: both 0.10. Other values are the pre-registered variants.)
BAND_LOSS = 0.10
BAND_PROFIT = 0.10
EXIT_FRACTION = 0.5                        # f in the gamma exit
EXIT_FLOOR_DAYS = 10                       # tau_min in the gamma exit
MULTIPLIER = 100                           # one SPX index point is worth 100 dollars
RECOVERY_FRACTION = 1.0                    # lambda: how much of the deficit to cover

# How the amount to recover (the "deficit") is updated after each trade:
#   "latest"     (base case, decided 2026-10-08): after a loss, the deficit
#                becomes THAT loss, replacing whatever was left; after a profit
#                it shrinks by the profit, never below 0.
#   "cumulative" (sensitivity case, not run; the definition of an early draft): losses
#                add up, profits pay them down, never below 0.
#   "none"       (sensitivity case, not run): no recovery, always the 30-day spread.
RECOVERY_MODE = "latest"

STRESS_WINDOW = 252                        # past days used for the stress percentile
STRESS_PERCENTILE = 0.80                   # the stress level
CASH_RATE_DAYS = 91                        # the cash earns the 3-month T-bill rate

# The stress flag always uses the 30-day vol, whatever the base maturity is.
# Kept separate from TARGET_DAYS on purpose: a variant with a 45-day base
# maturity must not change what counts as stress.
STRESS_VOL_DAYS = 30

# "mid": trade at the mid quote (base case).
# "cross": sell at the bid and buy at the ask (crossing the spread).
EXECUTION = "mid"

# ---- the end of the day (review_log.md C8 and C9, decided 2026-10-23) -------
# True = the fix is on (base case from 2026-10-23); False = the old behaviour.

# C9: take no decision at the snapshot of the stock close (16:00, or 13:00 on
# early-close days), because the option quotes there are unreliable.
SKIP_CLOSE_SNAPSHOT = True

# C8 (the index level after the close) is handled in the data since 2026-10-27,
# see the description at the top. Nothing to switch here any more.

# ---- broken option quotes (review_log.md C14, decided 2026-10-25) ----------
# "on":    (base case from 2026-10-25) a leg whose quote is broken is treated
#          like a missing quote: no exit test and no new mark while held, no
#          opening at that snapshot
# "count": the test is measured for every leg we hold or open and written to
#          QUOTES_FILE, but nothing changes: the trades are those of "off"
# "off":   quotes are used as they come (the old behaviour, before 2026-10-25)
QUOTE_RULE = "on"

# A quote is broken when ALL THREE hold, against the same option's quote at the
# previous snapshot used (the stock-close snapshot is never used, C9):
#   its implied vol moved by more than BROKEN_VOL_JUMP (0.03 = 3 vol points)
#   its bid/ask spread is more than BROKEN_WIDTH_RATIO times as wide as then
#   it widened more than its mid moved (a side ran away; in a real move the
#   whole quote shifts)
# Fixed 2026-10-25 (Arian) from the "count" runs only (how often it would fire),
# before any "on" run was made. None = not chosen.
BROKEN_VOL_JUMP = 0.03
BROKEN_WIDTH_RATIO = 3

# ---- output files -------------------------------------------------------
# The file names carry the settings, so runs with different settings do not
# overwrite each other, e.g. "trades_mid_latest.csv", "trades_cross_latest.csv".

RUN_NAME = EXECUTION + "_" + RECOVERY_MODE

# a run with one of the two data rules switched off says so in its name, so
# it never overwrites the results with both rules on
if not SKIP_CLOSE_SNAPSHOT:
    RUN_NAME = RUN_NAME + "_without_close_rule"
# "count" trades like "off", but also writes the quote test to QUOTES_FILE
if QUOTE_RULE == "off":
    RUN_NAME = RUN_NAME + "_without_quote_rule"
if QUOTE_RULE == "count":
    RUN_NAME = RUN_NAME + "_quote_rule_counted"
# (until 2026-10-28 the names carried review_log.md item numbers: "_c8c9",
# "q", "_c15"; those older runs were removed on 2026-10-29)
TRADES_FILE = "trades_" + RUN_NAME + ".csv"        # one row per finished trade
EQUITY_FILE = "equity_" + RUN_NAME + ".csv"        # one row per trading day
QUARTERS_FILE = "quarters_" + RUN_NAME + ".csv"    # one row per quarter
QUOTES_FILE = "quotes_" + RUN_NAME + ".csv"        # the quote test, one row per leg and snapshot
MISSING_FILE = "missing_" + RUN_NAME + ".csv"      # one row per held snapshot with a leg missing

# ---- test settings ----------------------------------------------------

# For a test, list the months to run, e.g. ["2021-06"].
# An empty list means: run every month.
TEST_MONTHS = []


# ======================================================================
#  Prices
# ======================================================================

def price_when_selling(row):
    """The price we receive when we SELL this option."""

    if EXECUTION == "mid":
        return row["mid"]
    else:
        return row["bid"]                  # a buyer only pays the bid


def price_when_buying(row):
    """The price we pay when we BUY this option."""

    if EXECUTION == "mid":
        return row["mid"]
    else:
        return row["ask"]                  # a seller only accepts the ask


# ======================================================================
#  Opening a position
# ======================================================================

def find_put(puts, strike_wanted):
    """
    Find the listed put whose strike is closest to the strike we want.

      puts          : table of puts for ONE slice (one time, root, expiry)
      strike_wanted : the target strike, for example 5437.3

    Returns the one row (as a Series) of the closest put.
    """

    # the strikes that exist in this slice, as a plain array of numbers
    listed_strikes = puts["strike"].values

    # how far each listed strike is from the one we want
    gaps = np.abs(listed_strikes - strike_wanted)

    # the position (0, 1, 2, ...) of the smallest gap
    best_position = np.argmin(gaps)

    # return the row at that position (.iloc means "by position", not by label)
    return puts.iloc[best_position]


def build_spread(expiry_row, puts_now):
    """
    Work out the spread the rule would open on ONE expiry, at this snapshot.

      expiry_row : one row of the ATM table (root, expiration, dte, forward, atm_iv)
      puts_now   : all puts of this snapshot

    Returns a dictionary describing the spread, or None if it cannot be built.
    """

    F = expiry_row["forward"]                  # forward price of this expiry
    sigma = expiry_row["atm_iv"]               # ATM volatility of this expiry
    dte = expiry_row["dte"]                    # days to expiry
    tau = dte / 365.0                          # time to expiry in years

    # ---- the puts of this expiry that we could actually trade ------------

    # True/False columns: same root, same expiry
    same_root = puts_now["root"] == expiry_row["root"]
    same_expiry = puts_now["expiration"] == expiry_row["expiration"]

    # True where there is a delta and a mid price (notna = "not empty")
    has_delta = puts_now["delta"].notna()
    has_price = puts_now["mid"].notna()

    # & means "and": keep the rows where all four are True
    puts = puts_now[same_root & same_expiry & has_delta & has_price]

    if len(puts) < 2:                          # we need at least two strikes
        return None

    # ---- the two target strikes (thesis, equation of the entry rule) -----

    one_sd = sigma * np.sqrt(tau)              # sigma * sqrt(tau)

    target_short = F * np.exp(-K1 * one_sd)
    target_long = F * np.exp(-K2 * one_sd)

    # snap each target to the nearest listed strike
    short_put = find_put(puts, target_short)
    long_put = find_put(puts, target_long)

    # the short strike must be above the long strike, otherwise it is no spread
    if short_put["strike"] <= long_put["strike"]:
        return None

    # ---- credit, entry delta and margin --------------------------------

    # credit of ONE spread: we receive the short put, we pay for the long put
    credit_one = price_when_selling(short_put) - price_when_buying(long_put)

    # credit of all spreads together, in index points
    credit = HOW_MANY_SPREADS * credit_one

    # the delta of the whole position at entry (thesis: Delta_0)
    delta0 = spread_delta(short_put["delta"], long_put["delta"], HOW_MANY_SPREADS)

    # the gamma exit: close when dte falls to max(f * dte0, 10 days)
    exit_days = max(EXIT_FRACTION * dte, EXIT_FLOOR_DAYS)

    # margin = the most we can lose: (width - credit) per spread, in dollars
    width = short_put["strike"] - long_put["strike"]
    margin = (width - credit_one) * MULTIPLIER * HOW_MANY_SPREADS

    # what it would cost to close the position, valued at the MID quote.
    # This is the "mark" used for the daily equity curve. Right after opening
    # at mid it equals the credit, so the position starts at zero profit.
    mark = HOW_MANY_SPREADS * (short_put["mid"] - long_put["mid"])

    return {
        "root": expiry_row["root"],
        "expiration": expiry_row["expiration"],
        "dte0": dte,
        "exit_days": exit_days,
        "forward0": F,
        "atm_iv0": sigma,
        "target_short": target_short,
        "target_long": target_long,
        "strike_short": short_put["strike"],
        "strike_long": long_put["strike"],
        "iv_short0": short_put["iv"],
        "iv_long0": long_put["iv"],
        "delta0": delta0,
        "credit": credit,
        "credit_mid": mark,    # the credit if we had traded at mid (= the mark at entry)
        "margin": margin,
        "mark": mark,
    }


def open_position(when, atm_now, puts_now, deficit):
    """
    Open a new position at this snapshot.

      when     : the snapshot time, as text, e.g. "2021-06-08 10:00:00"
      atm_now  : the rows of the ATM table at this snapshot
      puts_now : all puts at this snapshot
      deficit  : L, the loss still to be recovered, in index points (>= 0)

    Returns the position (a dictionary), or None if nothing could be opened.

    The maturity rule (thesis, "Maturity selection"):
      - the "target" spread is the one on the SHORTEST expiry with at least
        30 days (closest to the target from above);
      - with no deficit, we open the target spread;
      - with a deficit, we open the spread on the SHORTEST expiry (up to 90 days)
        whose credit is at least  target credit + lambda * deficit;
      - if no expiry is long enough for that, we open the LONGEST one up to 90
        days, and the rest of the deficit is carried forward.
    """

    # the expiries we are allowed to use: 30 to 90 days, with a fitted ATM vol
    long_enough = atm_now["dte"] >= TARGET_DAYS
    short_enough = atm_now["dte"] <= MAX_DAYS
    has_vol = atm_now["atm_iv"].notna()

    candidates = atm_now[long_enough & short_enough & has_vol]

    # shortest first; if SPX and SPXW have the same dte, "SPX" sorts first,
    # so SPX is preferred (a choice, see backtest_design.md)
    candidates = candidates.sort_values(["dte", "root"])

    # ---- build the spread on every candidate expiry ---------------------
    # (only the ones that can actually be built go into the list)

    spreads = []                               # one dictionary per usable expiry

    for _, expiry_row in candidates.iterrows():

        spread = build_spread(expiry_row, puts_now)

        if spread is not None:                 # "is not None" = we got a spread
            spreads.append(spread)

        # with no deficit the first one that works is all we need,
        # so stop here and save the time of building the others
        if deficit == 0 and len(spreads) == 1:
            break

    if len(spreads) == 0:
        return None                            # no expiry worked at this snapshot

    # ---- choose the maturity --------------------------------------------

    target = spreads[0]                        # shortest expiry: the target spread

    if deficit == 0:
        chosen = target
        rule = "target"
    else:
        credit_needed = target["credit"] + RECOVERY_FRACTION * deficit

        chosen = None

        # spreads is sorted shortest first, so the first one that is enough
        # is the shortest one that is enough
        for spread in spreads:
            if spread["credit"] >= credit_needed:
                chosen = spread
                rule = "recovery"
                break                          # stop at the first one that is enough

        if chosen is None:
            # none is enough: take the longest one. [-1] is the last in the list,
            # i.e. the longest dte.
            longest_dte = spreads[-1]["dte0"]

            # if SPX and SPXW both list that dte, the list has SPX first, so take
            # the FIRST spread with that dte to keep preferring SPX
            for spread in spreads:
                if spread["dte0"] == longest_dte:
                    chosen = spread
                    break

            rule = "cap"

    chosen["entry_time"] = when
    chosen["maturity_rule"] = rule             # "target", "recovery" or "cap"
    chosen["target_credit"] = target["credit"] # credit of the 30-day spread, for the record
    chosen["deficit_at_entry"] = deficit
    chosen["skipped"] = 0                      # snapshots where a leg was missing
    chosen["skipped_broken"] = 0               # snapshots skipped for a broken quote (C14)

    return chosen


# ======================================================================
#  The stress flag (recorded only, it does not change any decision)
# ======================================================================

def thirty_day_vol(atm_now):
    """
    The 30-day ATM volatility at this snapshot, interpolated in total variance
    between the two expiries that bracket 30 days. Same method as s09_vol_series.py.

    Returns a number, or nan if 30 days is not bracketed.
    """

    rows = atm_now[atm_now["atm_iv"].notna()]

    if len(rows) == 0:
        return np.nan

    # if both SPX and SPXW offer the same dte, average them:
    # group by dte, take the mean of atm_iv within each group.
    # as_index=False keeps dte as an ordinary column.
    rows = rows.groupby("dte", as_index=False)["atm_iv"].mean()

    rows = rows.sort_values("dte")             # shortest first, np.interp needs it

    expiries = rows["dte"].values              # .values = plain array of numbers
    vols = rows["atm_iv"].values

    # we cannot interpolate if everything is on one side of 30 days
    if expiries.min() > STRESS_VOL_DAYS or expiries.max() < STRESS_VOL_DAYS:
        return np.nan

    taus = expiries / 365.0
    total_variance = (vols ** 2) * taus        # variance = sigma^2 * tau

    target_tau = STRESS_VOL_DAYS / 365.0

    # straight lines between the points, read off at 30 days
    variance_at_30 = np.interp(target_tau, taus, total_variance)

    return float(np.sqrt(variance_at_30 / target_tau))


def stress_threshold(date, vol_dates, vol_values):
    """
    The stress threshold for one day: the 80th percentile of the daily 30-day
    vols of the 252 days strictly BEFORE this date (thesis, "Stress indicator").

      date       : text like "2020-03-12"
      vol_dates  : all dates of Data/06_vol30.csv, as a sorted array of text
      vol_values : the 30-day vol of each of those dates

    Returns a number, or nan if there are fewer than 252 days before the date.
    """

    # searchsorted finds where this date would go in the sorted list of dates:
    # everything before that position is strictly earlier than the date.
    # (Dates as text "YYYY-MM-DD" sort in the same order as in time.)
    position = np.searchsorted(vol_dates, date, side="left")

    if position < STRESS_WINDOW:               # not enough history yet
        return np.nan

    # the 252 days before the date (the slice stops one short of position)
    past = vol_values[position - STRESS_WINDOW: position]

    # np.percentile wants the level in percent (80), not as a fraction (0.80)
    return float(np.percentile(past, STRESS_PERCENTILE * 100))


# ======================================================================
#  Watching a position
# ======================================================================

def find_leg(puts_now, position, strike):
    """
    Find one leg of the open position at this snapshot.

    Returns the row, or None if the option is not quoted at this snapshot
    or has no delta or price.
    """

    same_root = puts_now["root"] == position["root"]
    same_expiry = puts_now["expiration"] == position["expiration"]
    same_strike = puts_now["strike"] == strike

    rows = puts_now[same_root & same_expiry & same_strike]

    if len(rows) == 0:                         # not in the data at this snapshot
        return None

    row = rows.iloc[0]                         # the first (and only) matching row

    # np.isnan is True for an empty number
    if np.isnan(row["delta"]) or np.isnan(row["mid"]):
        return None

    return row


def test_quote(leg_now, leg_before):
    """
    The broken-quote test for one leg (QUOTE_RULE, review_log.md C14).

      leg_now    : the leg's row at this snapshot
      leg_before : the same option's row at the previous snapshot used, or None

    Returns (broken, vol_jump, width_ratio). With no earlier quote, or with the
    limits not chosen yet (None), the quote is never called broken.
    """

    # nothing to compare with (first snapshot, or the option was not quoted
    # then): not broken. np.nan is numpy's "empty number", written as an empty
    # cell in the CSV, so the two measures are left blank.
    if leg_before is None:
        return False, np.nan, np.nan

    # how far the implied vol moved, in vol points as a fraction (0.05 = 5 points)
    vol_jump = abs(leg_now["iv"] - leg_before["iv"])

    # how many times wider the bid/ask spread is now. ask > bid in every row
    # (a stage 1 filter), so the width before is never 0.
    width_now = leg_now["ask"] - leg_now["bid"]
    width_before = leg_before["ask"] - leg_before["bid"]
    width_ratio = width_now / width_before

    if BROKEN_VOL_JUMP is None or BROKEN_WIDTH_RATIO is None:
        return False, vol_jump, width_ratio

    # how much wider the quote got, and how far its mid moved (abs: up or down)
    widened = width_now - width_before
    mid_now = (leg_now["bid"] + leg_now["ask"]) / 2
    mid_before = (leg_before["bid"] + leg_before["ask"]) / 2
    moved = abs(mid_now - mid_before)

    broken = (vol_jump > BROKEN_VOL_JUMP
              and width_ratio > BROKEN_WIDTH_RATIO
              and widened > moved)

    return broken, vol_jump, width_ratio


def quote_record(when, kind, leg_name, leg_now, leg_before, vol_jump, width_ratio, action):
    """
    One row of QUOTES_FILE: the quote test for one leg at one snapshot.

      when        : the snapshot, e.g. "2020-04-03 10:00:00"
      kind        : "held" (a leg of the open position) or "entry" (a leg we
                    are about to open)
      leg_name    : "short" or "long"
      leg_now     : the leg's row at this snapshot
      leg_before  : the same option's row at the previous snapshot used, or None
      vol_jump, width_ratio : the two measures from test_quote
      action      : what the backtest did here (see the main loop)

    The rows are only for checking afterwards; nothing in the backtest reads them.
    """

    record = {
        "time": when,
        "kind": kind,                          # "held" or "entry"
        "leg": leg_name,                       # "short" or "long"
        "root": leg_now["root"],               # the contract: root, expiry, strike
        "expiration": leg_now["expiration"],
        "strike": leg_now["strike"],
        "bid": leg_now["bid"],                 # the quote now
        "ask": leg_now["ask"],
        "iv": leg_now["iv"],                   # its implied vol (stage 2)
        "delta": leg_now["delta"],
        "bid_before": np.nan,                  # the quote before: empty for now,
        "ask_before": np.nan,                  # filled in below if there was one
        "iv_before": np.nan,                   # (np.nan = numpy's "empty number")
        "vol_jump": vol_jump,
        "width_ratio": width_ratio,
        "action": action,                      # what the backtest did at this snapshot
    }

    if leg_before is not None:                 # there was an earlier quote
        record["bid_before"] = leg_before["bid"]
        record["ask_before"] = leg_before["ask"]
        record["iv_before"] = leg_before["iv"]

    return record


def check_exit(position, short_leg, long_leg):
    """
    Test the three exit triggers (thesis, "The three exit rules").

    Returns "loss", "profit", "gamma", or None if the position stays open.
    The order only decides the label when two fire at the same snapshot.
    """

    delta_now = spread_delta(short_leg["delta"], long_leg["delta"], HOW_MANY_SPREADS)

    # Delta_pos rises when the index falls, so a HIGH delta is the bad side
    if delta_now >= position["delta0"] + BAND_LOSS:
        return "loss"

    # the profit exit only exists if BAND_PROFIT is a number (not None)
    if BAND_PROFIT is not None:
        if delta_now <= position["delta0"] - BAND_PROFIT:
            return "profit"

    # dte is whole calendar days, the same for every snapshot of one day
    if short_leg["dte"] <= position["exit_days"]:
        return "gamma"

    return None


def close_position(position, when, short_leg, long_leg, reason):
    """
    Close the position and return one finished-trade record (a dictionary).
    """

    # to close we BUY BACK the short put and SELL the long put
    cost_one = price_when_buying(short_leg) - price_when_selling(long_leg)

    cost = HOW_MANY_SPREADS * cost_one         # all spreads, in index points

    pnl = position["credit"] - cost            # profit (+) or loss (-), index points

    delta_exit = spread_delta(short_leg["delta"], long_leg["delta"], HOW_MANY_SPREADS)

    # start from a copy of the position's own fields, then add the exit fields.
    # dict(position) makes a new dictionary, so the original is not changed.
    trade = dict(position)

    trade["exit_time"] = when
    trade["reason"] = reason
    trade["dte_exit"] = short_leg["dte"]
    trade["iv_short_exit"] = short_leg["iv"]
    trade["iv_long_exit"] = long_leg["iv"]
    trade["delta_exit"] = delta_exit
    trade["cost"] = cost
    trade["pnl"] = pnl

    # The same trade valued at MID, to measure the cost of the bid/ask spread.
    # With EXECUTION = "mid" these equal credit, cost and pnl, and spread_cost is 0.
    cost_mid = HOW_MANY_SPREADS * (short_leg["mid"] - long_leg["mid"])
    pnl_mid = position["credit_mid"] - cost_mid

    trade["cost_mid"] = cost_mid
    trade["pnl_mid"] = pnl_mid
    trade["spread_cost"] = pnl_mid - pnl      # what crossing cost on this trade (points)
    trade["pnl_dollars"] = pnl * MULTIPLIER
    trade["return_on_margin"] = pnl * MULTIPLIER / position["margin"]

    return trade


def interest_for_day(rates, date, previous_date, margin):
    """
    The T-bill interest earned on the margin since the previous trading day.

      rates         : the rate table from rates.load_rates()
      date          : today, text like "2020-03-12"
      previous_date : the previous trading day, or None on the very first day
      margin        : the margin (dollars) that was held since the previous day

    Returns (interest in dollars, the rate used).
    """

    # pd.Timestamp turns the text into a real date, which rate_for() needs.
    # The 3-month rate, already converted to continuous compounding by s03_rates.py.
    rate = rate_for(rates, pd.Timestamp(date), CASH_RATE_DAYS)

    if previous_date is None:
        return 0.0, rate                       # nothing held before the first day

    # calendar days since the previous trading day (3 over a normal weekend).
    # Subtracting two dates gives a time span; .days is its length in days.
    days = (pd.Timestamp(date) - pd.Timestamp(previous_date)).days

    # continuous compounding: 1 dollar grows to exp(rate * years) dollars
    interest = margin * (np.exp(rate * days / 365.0) - 1.0)

    return interest, rate


def finish_day(date, previous_date, position, realised, interest_total,
               margin_held, deficit, rates):
    """
    Make the equity-curve row for one finished trading day.

      date           : the day that just finished
      previous_date  : the trading day before it (None on the first day)
      position       : the position open at the end of the day, or None
      realised       : P&L of all trades closed so far (dollars)
      interest_total : all interest up to the PREVIOUS day (dollars)
      margin_held    : the margin held since the previous day (dollars)
      deficit        : the current deficit (index points)

    Returns a dictionary, one row of equity.csv.
    """

    # interest earned since the previous day, on the margin held overnight
    interest, rate = interest_for_day(rates, date, previous_date, margin_held)

    interest_total = interest_total + interest

    if position is None:
        unrealised = 0.0
        margin = 0.0
    else:
        # profit so far on the open position, if we closed it at mid now:
        # what we received minus what it would cost to buy back
        unrealised = (position["credit"] - position["mark"]) * MULTIPLIER
        margin = position["margin"]

    total = realised + unrealised + interest_total

    return {
        "date": date,
        "realised": realised,
        "unrealised": unrealised,
        "interest_today": interest,
        "interest_total": interest_total,
        "total_pnl": total,
        "margin": margin,
        "rate": rate,
        "deficit": deficit,
    }


def period_returns(equity, column):
    """
    Return on margin per period (quarter or year).

      equity : the daily table, with columns pnl_day, margin and the label column
      column : "quarter" or "year", the label to group the days by

    For each period: return = (P&L of the period) / (average margin held in it).

    Returns a table with one row per period.
    """

    rows = []                                  # one dictionary per period goes in

    # groupby(column) gives one small table per quarter (or year), in order
    for period, one_period in equity.groupby(column):

        pnl = one_period["pnl_day"].sum()      # all the P&L made in this period
        mean_margin = one_period["margin"].mean()

        rows.append({
            "period": period,
            "days": len(one_period),
            "pnl": pnl,
            "mean_margin": mean_margin,
            "return": pnl / mean_margin,
        })

    return pd.DataFrame(rows)


def update_deficit(deficit, pnl):
    """
    The new deficit after a trade with profit-and-loss pnl (index points,
    negative for a loss). See RECOVERY_MODE at the top for the three rules.

    Example with RECOVERY_MODE = "latest":
        deficit 0,   pnl -100  ->  100   (recover this loss)
        deficit 100, pnl -50   ->   50   (the new loss replaces the old one)
        deficit 50,  pnl +30   ->   20   (paid down by the profit)
        deficit 20,  pnl +30   ->    0   (never below 0)
    """

    if RECOVERY_MODE == "none":
        return 0.0                             # never anything to recover

    if RECOVERY_MODE == "cumulative":
        # losses add up (minus a negative pnl is a plus), profits pay down
        return max(deficit - pnl, 0.0)

    # RECOVERY_MODE == "latest"
    if pnl < 0:
        return -pnl                            # the loss itself, as a positive number
    else:
        return max(deficit - pnl, 0.0)         # paid down by the profit


# ======================================================================
#  The main loop
# ======================================================================

def read_month(month):
    """Read the puts of one month from the Greeks folder."""

    path = GREEKS_FOLDER + "/spx_" + month + ".csv"    # e.g. "Data/04_greeks/spx_2021-06.csv"

    print("reading", path)

    # read only the columns we need (usecols), which saves a lot of memory.
    # quote_datetime and expiration stay as text, which is faster than dates.
    columns = ["quote_datetime", "root", "expiration", "dte", "strike",
               "option_type", "bid", "ask", "mid", "iv", "delta"]
    greeks = pd.read_csv(path, usecols=columns)

    # keep only puts, the strategy never trades calls
    greeks = greeks[greeks["option_type"] == "P"]

    return greeks


# ======================================================================
#  The end of the day (review_log.md C9)
# ======================================================================

def end_of_day_times(greeks):
    """
    For every day of one month: the time of the snapshot at the stock close,
    and the time of the snapshot after it.

    Normal days end at 16:15, so the close is 16:00 and the one after it 16:15.
    Early-close days (e.g. the day after Thanksgiving) end at 13:15, so the
    close is 13:00 and the one after it 13:15.

    Returns a dictionary: date -> (close time, after-close time), as text.
    """

    # the last snapshot of each day. The times are sorted (oldest first), so
    # for each date the last time we see is the last snapshot of that day.
    # unique() lists each snapshot time once.
    last_time = {}
    for when in sorted(greeks["quote_datetime"].unique()):
        date = when[:10]                       # "2020-03-16"
        last_time[date] = when[11:]            # "16:15:00" (overwritten until the last one)

    times = {}
    for date in last_time:
        if last_time[date] == "13:15:00":      # an early-close day
            times[date] = ("13:00:00", "13:15:00")
        else:                                  # a normal day
            times[date] = ("16:00:00", "16:15:00")

    return times


def main():

    print("loading", ATM_FILE, "...")

    # quote_datetime and expiration are kept as text on purpose (no parse_dates)
    atm = pd.read_csv(ATM_FILE)

    # the month as text, e.g. "2021-06" (the first 7 characters)
    atm["month"] = atm["quote_datetime"].str[:7]

    # the daily 30-day vols, for the stress threshold. Sorted by date, oldest
    # first, because stress_threshold() relies on the order.
    vol30 = pd.read_csv(VOL30_FILE)
    vol30 = vol30.sort_values("date")
    vol_dates = vol30["date"].values           # plain arrays, see stress_threshold()
    vol_values = vol30["vol30"].values

    # the T-bill rates (same function stage 2 used)
    rates = load_rates()

    # counter for the end-of-day handling, printed in the summary
    close_snapshots_skipped = 0                # C9: snapshots at the close not used

    # one row per held snapshot where a leg was missing, saved to MISSING_FILE
    missing_rows = []

    # the broken-quote test (QUOTE_RULE, C14)
    if QUOTE_RULE == "on" and (BROKEN_VOL_JUMP is None or BROKEN_WIDTH_RATIO is None):
        raise ValueError("QUOTE_RULE = 'on' needs BROKEN_VOL_JUMP and BROKEN_WIDTH_RATIO")
    quote_rows = []                            # rows of QUOTES_FILE go in here
    puts_before = None                         # the puts of the previous snapshot used
    held_broken = 0                            # snapshots skipped while holding (rule "on")
    entries_refused = 0                        # entries not made at a snapshot (rule "on")

    # decide which months to run
    if len(TEST_MONTHS) > 0:
        months = TEST_MONTHS
    else:
        # unique() lists each month once, sorted() puts them in time order
        months = sorted(atm["month"].unique())

    # ---- the state: what we remember from one snapshot to the next -------
    # It lives OUTSIDE the month loop, so a position open at the end of one
    # month is simply carried into the next.

    position = None                            # None = no open position
    deficit = 0.0                              # L, the loss still to recover (index points)
    trades = []                                # finished trades go in here
    flat_snapshots = 0                         # snapshots where nothing could be opened

    # for the daily equity curve (all in dollars)
    days = []                                  # one dictionary per trading day goes in
    current_date = None                        # the day we are in, text like "2020-03-12"
    previous_date = None                       # the last day that was finished
    realised = 0.0                             # P&L of all closed trades so far
    interest_total = 0.0                       # all T-bill interest so far
    margin_held = 0.0                          # margin at the end of the previous day

    for month in months:

        greeks = read_month(month)

        # for every day of this month: the close time and the time after it
        day_times = end_of_day_times(greeks)

        # this month's rows of the ATM table
        atm_month = atm[atm["month"] == month]

        # Put the ATM rows into a dictionary: snapshot time -> its rows.
        # groupby splits the table into one small table per snapshot.
        atm_by_time = {}
        for when, rows in atm_month.groupby("quote_datetime"):
            atm_by_time[when] = rows

        # Go through the month one snapshot at a time. groupby sorts the times,
        # and because they are text like "2021-06-08 10:00:00" the sorted order
        # is also the order in time.
        for when, puts_now in greeks.groupby("quote_datetime"):

            # ---- 0. a new day? then first finish the previous one ---------

            today = when[:10]                  # the date part of the snapshot time

            if current_date is not None and today != current_date:

                # the snapshots of current_date are all done: write its row
                row = finish_day(current_date, previous_date, position,
                                 realised, interest_total, margin_held,
                                 deficit, rates)
                days.append(row)

                # carry the numbers over to the next day
                interest_total = row["interest_total"]
                margin_held = row["margin"]
                previous_date = current_date

            current_date = today

            # ---- 0b. the end of the day (review_log.md C9) ---------------

            time_now = when[11:]               # the time part, e.g. "16:00:00"

            # the two special times of today, e.g. ("16:00:00", "16:15:00").
            # Only the first is used here (the second was needed for the C8
            # correction, which is now done in the data)
            close_time, after_close_time = day_times[today]

            # C9: at the stock close no decision is taken. "continue" jumps
            # straight to the next snapshot: no exit test, no new position.
            if SKIP_CLOSE_SNAPSHOT and time_now == close_time:
                close_snapshots_skipped = close_snapshots_skipped + 1
                continue

            # ---- 1. if we hold a position, test the exits ----------------

            if position is not None:

                short_leg = find_leg(puts_now, position, position["strike_short"])
                long_leg = find_leg(puts_now, position, position["strike_long"])

                if short_leg is None or long_leg is None:
                    # a leg is not quoted here: skip the tests, try next snapshot
                    position["skipped"] = position["skipped"] + 1
                    # write down when and which leg (the file MISSING_FILE), so
                    # that the cause can be looked up later (review_log C15, T26;
                    # the script that did it was removed on 2026-10-29)
                    missing_rows.append({"when": when,
                                         "root": position["root"],
                                         "expiration": position["expiration"],
                                         "strike_short": position["strike_short"],
                                         "strike_long": position["strike_long"],
                                         "short_missing": short_leg is None,
                                         "long_missing": long_leg is None})
                else:
                    # ---- 1a. the broken-quote test (QUOTE_RULE, C14) ------
                    reason = None
                    broken_now = False
                    if QUOTE_RULE != "off":
                        # the same two options at the previous snapshot used
                        short_before = None
                        long_before = None
                        if puts_before is not None:
                            short_before = find_leg(puts_before, position, position["strike_short"])
                            long_before = find_leg(puts_before, position, position["strike_long"])

                        broken_s, jump_s, ratio_s = test_quote(short_leg, short_before)
                        broken_l, jump_l, ratio_l = test_quote(long_leg, long_before)
                        broken_now = broken_s or broken_l

                    if QUOTE_RULE == "on" and broken_now:
                        # treated like a missing quote: no new mark, no exit test
                        position["skipped_broken"] = position["skipped_broken"] + 1
                        held_broken = held_broken + 1
                    else:
                        # remember what it would cost to close at mid right now,
                        # for the daily equity curve
                        position["mark"] = HOW_MANY_SPREADS * (short_leg["mid"] - long_leg["mid"])

                        reason = check_exit(position, short_leg, long_leg)

                    if QUOTE_RULE != "off":
                        # what happened here: "skipped (broken)", an exit reason, or "" (held)
                        action = ""
                        if QUOTE_RULE == "on" and broken_now:
                            action = "skipped (broken)"
                        elif reason is not None:
                            action = reason
                        quote_rows.append(quote_record(when, "held", "short", short_leg, short_before,
                                                       jump_s, ratio_s, action))
                        quote_rows.append(quote_record(when, "held", "long", long_leg, long_before,
                                                       jump_l, ratio_l, action))

                    if reason is not None:
                        trade = close_position(position, when, short_leg,
                                               long_leg, reason)

                        # update the deficit, depending on RECOVERY_MODE
                        deficit = update_deficit(deficit, trade["pnl"])

                        trade["deficit_after"] = deficit

                        # the trade's P&L is now realised (dollars)
                        realised = realised + trade["pnl_dollars"]

                        trades.append(trade)
                        position = None        # now flat, so we roll below

            # ---- 2. if we hold nothing, open a position ------------------
            # This also runs right after a close, so the roll happens at the
            # SAME snapshot (a choice, see backtest_design.md). The new position
            # is first tested at the NEXT snapshot.

            if position is None:

                if when in atm_by_time:        # is there ATM data at this time?

                    atm_now = atm_by_time[when]

                    position = open_position(when, atm_now, puts_now, deficit)

                    # the broken-quote test on the two legs we would open (C14)
                    if position is not None and QUOTE_RULE != "off":
                        short_leg = find_leg(puts_now, position, position["strike_short"])
                        long_leg = find_leg(puts_now, position, position["strike_long"])
                        short_before = None
                        long_before = None
                        if puts_before is not None:
                            short_before = find_leg(puts_before, position, position["strike_short"])
                            long_before = find_leg(puts_before, position, position["strike_long"])

                        broken_s, jump_s, ratio_s = test_quote(short_leg, short_before)
                        broken_l, jump_l, ratio_l = test_quote(long_leg, long_before)
                        broken_now = broken_s or broken_l

                        action = "opened"
                        if QUOTE_RULE == "on" and broken_now:
                            action = "not opened (broken)"
                        quote_rows.append(quote_record(when, "entry", "short", short_leg, short_before,
                                                       jump_s, ratio_s, action))
                        quote_rows.append(quote_record(when, "entry", "long", long_leg, long_before,
                                                       jump_l, ratio_l, action))

                        if QUOTE_RULE == "on" and broken_now:
                            # do not open on a broken quote: try again at the next snapshot
                            position = None
                            entries_refused = entries_refused + 1

                    if position is not None:
                        # record the stress flag at entry. It is only reported,
                        # it does not change the trade (decided 2026-10-08).
                        vol_now = thirty_day_vol(atm_now)
                        threshold = stress_threshold(when[:10], vol_dates, vol_values)

                        position["vol30_entry"] = vol_now
                        position["stress_threshold"] = threshold

                        # if either number is missing we cannot judge: leave it empty
                        if np.isnan(vol_now) or np.isnan(threshold):
                            position["stress"] = None
                        else:
                            position["stress"] = bool(vol_now > threshold)

                if position is None:
                    flat_snapshots = flat_snapshots + 1

            # this snapshot was used: it is the "previous snapshot" for the next
            # one (the stock-close snapshot never gets here, see C9 above)
            puts_before = puts_now

    # the very last day has no "next day" to trigger its row, so finish it here
    if current_date is not None:
        row = finish_day(current_date, previous_date, position, realised,
                         interest_total, margin_held, deficit, rates)
        days.append(row)

    # ---- the equity curve --------------------------------------------------

    equity = pd.DataFrame(days)                # one row per trading day

    # The P&L made on each day: today's total minus yesterday's.
    # .shift(1) moves a column down one row, so each row sees yesterday's value.
    equity["pnl_day"] = equity["total_pnl"] - equity["total_pnl"].shift(1)

    # the first day has no yesterday (nan): its P&L is simply its total
    equity["pnl_day"] = equity["pnl_day"].fillna(equity["total_pnl"].iloc[0])

    # labels to group by: the year (2020) and the quarter ("2020-Q1").
    # pd.to_datetime turns the date text into real dates; .dt.year and
    # .dt.quarter then read off the year and the quarter (1 to 4).
    dates = pd.to_datetime(equity["date"])
    equity["year"] = dates.dt.year.astype(str)                 # astype(str) = as text
    equity["quarter"] = equity["year"] + "-Q" + dates.dt.quarter.astype(str)

    equity.to_csv(EQUITY_FILE, index=False)

    # return on margin per quarter and per year (see period_returns)
    quarters = period_returns(equity, "quarter")
    years_table = period_returns(equity, "year")

    quarters.to_csv(QUARTERS_FILE, index=False)

    # ---- the trades --------------------------------------------------------

    # a list of dictionaries becomes a table: one row per trade
    table = pd.DataFrame(trades)

    # index=False: do not write pandas' row numbers into the file
    table.to_csv(TRADES_FILE, index=False)

    print()
    print("saved", len(equity), "days to", EQUITY_FILE)

    last = equity.iloc[-1]                     # the last row (-1 = last)

    print()
    print("total P&L (dollars):     ", round(last["total_pnl"], 2))
    print("  of which closed trades:", round(last["realised"], 2))
    print("  open position at end:  ", round(last["unrealised"], 2))
    print("  T-bill interest:       ", round(last["interest_total"], 2))

    # ---- return on margin ------------------------------------------------
    # Main measure: P&L of a period divided by the average margin held in it.
    # (Not compounded day by day: with a margin that changes from trade to
    # trade, compounding can give a negative % in a period that made money.)

    print()
    print("saved", len(quarters), "quarters to", QUARTERS_FILE)
    print()
    print("return on margin per year (P&L / average margin):")
    for _, y in years_table.iterrows():
        print("  ", y["period"], " ", round(y["return"] * 100, 1), "%   P&L",
              round(y["pnl"]), "$   average margin", round(y["mean_margin"]), "$")

    # whole sample: total P&L / average margin / number of years.
    # A year has about 252 trading days.
    number_of_years = len(equity) / 252.0
    per_year = last["total_pnl"] / equity["margin"].mean() / number_of_years

    q = quarters["return"]                     # a short name for the column

    print()
    print("whole sample, per year:", round(per_year * 100, 2), "%")
    print("quarters:", len(q), "  negative:", int((q < 0).sum()),
          "  median:", round(q.median() * 100, 1), "%",
          "  worst:", round(q.min() * 100, 1), "%",
          "  best:", round(q.max() * 100, 1), "%")

    # volatility per year from the quarterly returns: there are 4 quarters in a
    # year, so multiply the quarterly standard deviation by sqrt(4) = 2
    print("volatility per year (from quarters):", round(q.std() * 2 * 100, 1), "%")

    # ---- largest drawdown, in dollars -------------------------------------
    # cummax() is the highest total P&L reached so far, row by row. The
    # drawdown is how far below that peak we are on each day.
    peak = equity["total_pnl"].cummax()
    drawdown = equity["total_pnl"] - peak

    trough_row = drawdown.idxmin()             # the row of the deepest point
    # the row of the peak before it: the first row where the peak value was reached
    peak_value = peak[trough_row]
    peak_row = equity.index[equity["total_pnl"] == peak_value][0]

    # the drawdown as a share of the average margin held during it
    margin_during = equity.loc[peak_row:trough_row, "margin"].mean()

    print("largest drawdown:", round(drawdown.min()), "$  from",
          equity.loc[peak_row, "date"], "to", equity.loc[trough_row, "date"],
          " =", round(drawdown.min() / margin_during * 100, 1),
          "% of the average margin in that period")

    # ---- worst day ---------------------------------------------------------
    # one day's P&L divided by the margin held since the day before
    day_return = equity["pnl_day"] / equity["margin"].shift(1)
    worst_row = day_return.idxmin()
    print("worst day:", equity.loc[worst_row, "date"], round(day_return.min() * 100, 1),
          "% of the margin held")

    print()
    print("saved", len(table), "trades to", TRADES_FILE)
    print("snapshots without a position:", flat_snapshots)
    print("close snapshots skipped (C9):", close_snapshots_skipped)

    # the held snapshots with a missing leg (one dictionary per snapshot)
    missing_table = pd.DataFrame(missing_rows)
    missing_table.to_csv(MISSING_FILE, index=False)
    print("held snapshots with a leg missing:", len(missing_rows), "| saved to", MISSING_FILE)

    if QUOTE_RULE != "off":
        # quote_rows is a list of dictionaries (one per leg and snapshot);
        # pd.DataFrame turns it into a table, one dictionary per row
        quote_table = pd.DataFrame(quote_rows)
        # index=False: do not write pandas' row numbers into the file
        quote_table.to_csv(QUOTES_FILE, index=False)
        print("quote rule", QUOTE_RULE, "| limits:", BROKEN_VOL_JUMP, BROKEN_WIDTH_RATIO,
              "| rows saved to", QUOTES_FILE, ":", len(quote_rows),
              "| held snapshots skipped:", held_broken, "| entries refused:", entries_refused)

    if position is not None:
        print("still open at the end: entered", position["entry_time"],
              "expiry", position["expiration"])

    if len(table) == 0:
        return

    print()
    print("trades by exit reason:")
    # value_counts() counts how often each reason appears
    counts = table["reason"].value_counts()
    for reason in counts.index:
        print("  ", reason, counts[reason])

    print()
    print("every trade (index points):")
    for _, t in table.iterrows():
        print("  ", t["entry_time"], "->", t["exit_time"],
              "|", t["root"], t["expiration"], "dte", t["dte0"], "->", t["dte_exit"],
              "| strikes", t["strike_short"], "/", t["strike_long"],
              "| delta", round(t["delta0"], 3), "->", round(t["delta_exit"], 3),
              "| credit", round(t["credit"], 2), "pnl", round(t["pnl"], 2),
              "|", t["reason"], "| skipped", t["skipped"],
              "| L", round(t["deficit_at_entry"], 2), "->", round(t["deficit_after"], 2),
              "|", t["maturity_rule"], "| stress", t["stress"])

    print()
    print("total pnl (index points):", round(table["pnl"].sum(), 2))
    print("deficit at the end (index points):", round(deficit, 2))


# Only run main() when this file is started directly (python Code/s11_backtest.py).
# When another file imports it, e.g. a test script, nothing runs by itself.
if __name__ == "__main__":
    main()
