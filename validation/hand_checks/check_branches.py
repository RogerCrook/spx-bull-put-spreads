"""
CHECK THAT EACH BRANCH SNAPSHOT IS WHAT IT CLAIMS TO BE

What this file is for:
    select_snapshots.sh chose 22 snapshots, each meant to show one rule branch
    (a loss exit, a recovery entry, the stock close, ...). This file tests,
    for each of them, that the branch condition really holds there.

    Where possible the test uses the DATA (the snapshot calendar of
    Data/05_atm_vol.csv, the quotes in the packets), not the backtest's logs,
    so that a wrong definition in the selection shows up. Conditions that only
    the logs can show (the reason of an exit, the deficit) are re-read from the
    trade log with their own code.

    It prints one line per branch: id, condition, yes/no, the numbers behind it.
    It writes nothing.

To run it (from the main folder, after make_packets.py, about 20 seconds):
    python validation/hand_checks/check_branches.py
"""

import pandas as pd                 # pandas works with tables


# ---- settings ----------------------------------------------------------------

KEY_FILE = "validation/hand_checks/key.csv"         # which H number belongs to which branch
PACKETS = "validation/hand_checks/packets"          # the input packets
ATM_FILE = "Data/05_atm_vol.csv"                    # the data's snapshots and expiries
RESULTS = "results"                                 # the backtest's logs

BAND = 0.10                         # the delta band of the base case
BAND_P15 = 0.15                     # the profit band of p15
BROKEN_VOL_JUMP = 0.03              # def:broken, condition 1 (3 vol points)
BROKEN_WIDTH_RATIO = 3              # def:broken, condition 2


# ---- helpers ------------------------------------------------------------------

def trade_exiting_at(trades, when):
    """The trade (one row) that closed at `when`, and the next trade, or None."""

    for position in range(len(trades)):
        trade = trades.iloc[position]               # .iloc[n]: the row at position n
        if trade["exit_time"] == when:
            if position + 1 < len(trades):
                next_trade = trades.iloc[position + 1]
            else:
                next_trade = None
            return trade, next_trade
    return None, None


def expiries_at(atm, when):
    """The days to expiry of all expiries with an ATM vol at `when`, sorted."""

    rows = atm[atm["quote_datetime"] == when]
    has_vol = rows["atm_iv"].notna()                # .notna(): True where the cell is not empty
    rows = rows[has_vol]
    return sorted(rows["dte"].tolist())             # .tolist(): the column as a plain list


def close_time_of(day, last_time_of_day):
    """The stock close of a day: 13:00 if the day ends at 13:15, else 16:00."""

    if last_time_of_day[day] == "13:15:00":
        return "13:00:00"
    return "16:00:00"


def report(key_id, hand_check, condition, holds, numbers):
    """Print one line of the result."""

    if holds:
        answer = "yes"
    else:
        answer = "NO "
    print(key_id.ljust(5), hand_check, answer, "|", condition, "|", numbers)   # ljust(5): pad to 5 characters


# ---- the checks ----------------------------------------------------------------

def main():

    key = pd.read_csv(KEY_FILE)

    print("loading", ATM_FILE, "...")
    atm = pd.read_csv(ATM_FILE, usecols=["quote_datetime", "dte", "atm_iv"])

    # the data's calendar: every snapshot time, sorted, and each day's last time
    all_times = sorted(atm["quote_datetime"].unique())
    last_time_of_day = {}
    for when in all_times:
        last_time_of_day[when[:10]] = when[11:]

    trades = {}
    for run in ["base_mid", "base_cross", "p15_mid"]:
        trades[run] = pd.read_csv(RESULTS + "/trades_" + run + ".csv")

    # go through the branch snapshots in key order (B01, B02, ...)
    key = key.sort_values("key_id")

    for _, row in key.iterrows():

        key_id = row["key_id"]
        if not key_id.startswith("B"):              # the random ones claim no branch
            continue

        h = row["hand_check"]
        when = row["snapshot"]
        run = row["run"]
        trade, next_trade = trade_exiting_at(trades[run], when)

        if key_id == "B01":
            first = all_times[0]
            report(key_id, h, "the first snapshot in the data", when == first, "first = " + first)

        elif key_id in ["B02", "B03", "B04", "B08"] and trade is None:
            report(key_id, h, "an exit at this snapshot", False, "no trade closes here")

        elif key_id == "B02":
            listed = expiries_at(atm, when)
            at_least_30 = []
            for days in listed:
                if days >= 30:
                    at_least_30.append(days)
            holds = (trade["reason"] == "profit" and trade["deficit_at_entry"] == 0
                     and next_trade["dte0"] == at_least_30[0])
            report(key_id, h, "profit exit, deficit 0, new expiry = shortest >= 30 days in the data", holds,
                   "reason " + trade["reason"] + ", deficit " + str(trade["deficit_at_entry"])
                   + ", new dte " + str(next_trade["dte0"]) + ", shortest >= 30: " + str(at_least_30[0]))

        elif key_id == "B03":
            listed = expiries_at(atm, when)
            at_least_30 = []
            for days in listed:
                if days >= 30:
                    at_least_30.append(days)
            holds = (trade["reason"] == "loss" and next_trade["dte0"] > at_least_30[0]
                     and next_trade["dte0"] <= 90)
            report(key_id, h, "loss exit, new expiry longer than the shortest >= 30 days, at most 90", holds,
                   "reason " + trade["reason"] + ", new dte " + str(next_trade["dte0"])
                   + ", shortest >= 30: " + str(at_least_30[0]))

        elif key_id == "B04":
            listed = expiries_at(atm, when)
            at_most_90 = []
            for days in listed:
                if days >= 30 and days <= 90:
                    at_most_90.append(days)
            holds = trade["reason"] == "loss" and next_trade["dte0"] == at_most_90[-1]   # [-1]: the last = longest
            report(key_id, h, "loss exit, new expiry = longest <= 90 days in the data", holds,
                   "reason " + trade["reason"] + ", new dte " + str(next_trade["dte0"])
                   + ", expiries 30-90: " + str(at_most_90))

        elif key_id == "B05":
            holds = trade["reason"] == "gamma" and trade["dte_exit"] <= trade["dte0"] / 2
            report(key_id, h, "gamma exit, days left <= dte0 / 2", holds,
                   "days left " + str(trade["dte_exit"]) + ", dte0 " + str(trade["dte0"]))

        elif key_id in ["B06", "B07", "B08"]:
            before = trade["deficit_at_entry"]
            pnl = trade["pnl"]
            after = trade["deficit_after"]
            if key_id == "B06":
                condition = "deficit > 0, loss, new deficit = that loss"
                holds = before > 0 and pnl < 0 and abs(after + pnl) < 1e-9
            elif key_id == "B07":
                condition = "deficit > 0, 0 <= profit < deficit, new deficit = deficit - profit"
                holds = before > 0 and pnl >= 0 and pnl < before and abs(after - (before - pnl)) < 1e-9
            else:
                condition = "deficit > 0, profit >= deficit, new deficit 0"
                holds = before > 0 and pnl >= before and after == 0
            report(key_id, h, condition, holds,
                   "deficit " + str(round(before, 2)) + ", pnl " + str(round(pnl, 2)) + ", after " + str(round(after, 2)))

        elif key_id == "B09":
            holds = trade["reason"] in ["loss", "profit"] and trade["dte_exit"] <= trade["dte0"] / 2
            report(key_id, h, "delta exit while days left <= dte0 / 2", holds,
                   "reason " + trade["reason"] + ", days left " + str(trade["dte_exit"]) + ", dte0 " + str(trade["dte0"]))

        elif key_id in ["B10", "B11"]:
            holds, numbers = broken_from_packet(h, when)
            if key_id == "B10":
                report(key_id, h, "a leg broken against the snapshot before (quotes of the packet)", holds, numbers)
            else:
                # the snapshot after B10 must be the next snapshot in the data
                b10_time = key[key["key_id"] == "B10"]["snapshot"].iloc[0]
                position = all_times.index(b10_time)
                report(key_id, h, "the next snapshot after B10 in the data", when == all_times[position + 1],
                       "B10 " + b10_time + ", next " + all_times[position + 1])

        elif key_id == "B12":
            legs = pd.read_csv(PACKETS + "/" + h + "/legs.csv")
            rows_now = legs[legs["quote_datetime"] == when]
            report(key_id, h, "a leg has no row at this snapshot (packet)", len(rows_now) < 2,
                   str(len(rows_now)) + " leg rows at the snapshot")

        elif key_id in ["B13", "B14"]:
            day = when[:10]
            close_time = close_time_of(day, last_time_of_day)
            report(key_id, h, "the stock-close snapshot of its day (data calendar)", when[11:] == close_time,
                   "day ends " + last_time_of_day[day] + ", close " + close_time)

        elif key_id in ["B13b", "B14b", "B15"]:
            day = when[:10]
            report(key_id, h, "the last snapshot of its day (data calendar)", when[11:] == last_time_of_day[day],
                   "day ends " + last_time_of_day[day])

        elif key_id in ["B16", "B17"]:
            if key_id == "B16":
                wanted = "loss"
            else:
                wanted = "profit"
            position = all_times.index(when)
            # the next snapshot used: the next one in the data, unless it is
            # the stock close of its day, then the one after it
            next_time = all_times[position + 1]
            if next_time[11:] == close_time_of(next_time[:10], last_time_of_day):
                next_time = all_times[position + 2]
            exiting, _ = trade_exiting_at(trades[run], next_time)
            holds = exiting is not None and exiting["reason"] == wanted
            report(key_id, h, "the next snapshot used is a " + wanted + " exit", holds, "next " + next_time)

        elif key_id == "B18":
            report(key_id, h, "a trade of the run crossing the spread closes here", trade is not None, run)

        elif key_id == "B19":
            holds = (trade["reason"] == "profit"
                     and trade["delta_exit"] <= trade["delta0"] - BAND_P15 + 1e-12)
            report(key_id, h, "p15 profit exit, delta <= delta0 - 0.15", holds,
                   "delta0 " + str(round(trade["delta0"], 4)) + ", delta at exit " + str(round(trade["delta_exit"], 4)))

        elif key_id == "B20":
            date = when[:10]
            days = sorted(last_time_of_day.keys())  # all trading days, in order
            day_before = days[days.index(date) - 1] # the trading day before
            gap = (pd.Timestamp(date) - pd.Timestamp(day_before)).days     # .days: the length in days
            report(key_id, h, "the trading day before is 3 calendar days earlier (a weekend)", gap == 3,
                   "day before " + day_before)

        else:
            report(key_id, h, "no check written", False, "")


def broken_from_packet(h, when):
    """
    Test def:broken on the packet's quotes: for each leg, compare its quote at
    `when` with its quote at the snapshot before (in the packet). Returns
    (True if a leg is broken, a text with the numbers).
    """

    legs = pd.read_csv(PACKETS + "/" + h + "/legs.csv")
    times = sorted(legs["quote_datetime"].unique())
    before = times[times.index(when) - 1]           # the snapshot before, in the packet
    # (B10 is in the morning, so the snapshot before is never a stock close)

    any_broken = False
    text = ""
    for strike in sorted(legs["strike"].unique()):

        same_strike = legs["strike"] == strike
        rows_now = legs[same_strike & (legs["quote_datetime"] == when)]
        rows_before = legs[same_strike & (legs["quote_datetime"] == before)]
        now_row = rows_now.iloc[0]                  # the one row (.iloc[0] = the first by position)
        old_row = rows_before.iloc[0]

        jump = abs(now_row["iv"] - old_row["iv"])               # condition 1: vol jump
        width_now = now_row["ask"] - now_row["bid"]
        width_old = old_row["ask"] - old_row["bid"]
        ratio = width_now / width_old                           # condition 2: width ratio
        moved = abs(now_row["mid"] - old_row["mid"])            # condition 3: widened more than mid moved

        broken = jump > BROKEN_VOL_JUMP and ratio > BROKEN_WIDTH_RATIO and (width_now - width_old) > moved
        if broken:
            any_broken = True
        text = text + "K " + str(strike) + ": jump " + str(round(jump, 3)) + ", ratio " + str(round(ratio, 1)) \
               + ", widened " + str(round(width_now - width_old, 2)) + " vs moved " + str(round(moved, 2)) + "; "

    return any_broken, text + "before = " + before


# Only run main() when this file is started directly, not when imported.
if __name__ == "__main__":
    main()
