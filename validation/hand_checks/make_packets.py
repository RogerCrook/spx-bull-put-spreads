"""
THE INPUT PACKETS OF THE HAND CHECKS

What this file is for:
    For each of the 32 snapshots in list.csv (made by draw_random.py) it
    writes one folder, packets/H01 ... packets/H32, with everything Arian needs
    to work out by hand what the strategy must do there, and nothing that
    says what the backtest did.

    Each folder holds calendar.txt: the time of the last snapshot of this day
    and of the day before (16:15, or 13:15 on an early-close day).

    Each snapshot folder also holds:
      position.txt  : the position open just before the snapshot and the deficit
                      (from the backtest's trade log: each check tests ONE step)
      legs.csv      : the quotes of the position's two puts at every snapshot of
                      the day before and of this day, up to the snapshot
                      (for the broken-quote test against the last good quote)
      expiries.csv  : every expiry at the snapshot with its forward and ATM vol
      puts.csv      : every put at the snapshot (for a possible new position)
    The equity day (the one line of list.csv that ends in "(day)") gets instead:
      position.txt  : every position open on that day or at the end of the day before
      legs.csv      : their puts at every snapshot of the day before and of the day
      rates.csv     : the 3-month T-bill rate (FRED, in percent) around that day
    The deep checks (deep = yes in list.csv) also get, from the raw data:
      raw.csv          : every raw row of that snapshot (calls and puts, all roots)
      index_close.csv  : the official close of that day
      rates.csv        : the four T-bill rates (FRED, in percent) around that day

    It only reads Data/ and results/. It writes only into
    validation/hand_checks/packets/.

To run it (from the main folder; it reads about 30 monthly files of
Data/04_greeks, roughly 20 to 30 minutes):
    python validation/hand_checks/make_packets.py
"""

import os                           # for making folders
import pandas as pd                 # pandas works with tables


# ---- settings ----------------------------------------------------------------

LIST_FILE = "validation/hand_checks/list.csv"       # the work list (H01 ... H32)
OUT_FOLDER = "validation/hand_checks/packets"       # one folder per hand check goes in here

GREEKS_FOLDER = "Data/04_greeks"                    # quotes with forward, iv and delta, one file per month
RAW_FOLDER = "Data/01_raw_options"                  # raw quotes, one file per day
ATM_FILE = "Data/05_atm_vol.csv"                    # forward and ATM vol per snapshot and expiry
RATES_FOLDER = "Data/03_treasury_bills"             # the four FRED rate files
INDEX_CLOSE_FILE = "Data/07_index_close/GSPC_daily.csv"   # the official daily close
RESULTS_FOLDER = "results"                          # the backtest's logs

# the columns of Data/04_greeks we need (usecols makes reading much faster)
GREEKS_COLUMNS = ["quote_datetime", "root", "expiration", "dte", "strike",
                  "option_type", "bid", "ask", "mid", "spot", "forward", "D", "iv", "delta"]

# the columns of the trade log Arian gets in position.txt
POSITION_FIELDS = ["root", "expiration", "strike_short", "strike_long", "entry_time",
                   "dte0", "delta0", "credit", "margin", "deficit_at_entry"]

RATE_DAYS_AROUND = 7                # how many calendar days of rates before the day to include


# ---- reading the data ----------------------------------------------------------

def read_month_puts(month, cache):
    """
    Read the puts of one month of Data/04_greeks, e.g. month = "2021-06".
    cache is a dictionary month -> table, so a month is read only once.
    Only the last two months are kept, to save memory.
    """

    if month in cache:                              # already read: use it again
        return cache[month]

    path = GREEKS_FOLDER + "/spx_" + month + ".csv"
    print("  reading", path)

    table = pd.read_csv(path, usecols=GREEKS_COLUMNS)

    # keep only the puts: the strategy never trades calls.
    # table["option_type"] == "P" is a column of True/False ("a mask");
    # table[mask] keeps the rows where it is True.
    is_put = table["option_type"] == "P"
    table = table[is_put]

    # keep at most one month besides the new one: if two are kept already,
    # forget the older of them. (A month of puts takes a lot of memory.)
    if len(cache) >= 2:
        oldest = min(cache.keys())                  # month text sorts like time, so min = oldest
        del cache[oldest]

    cache[month] = table
    return table


def previous_month(month):
    """The month before, as text: "2021-06" -> "2021-05", "2021-01" -> "2020-12"."""

    year = int(month[:4])
    month_number = int(month[5:7])

    if month_number == 1:
        return str(year - 1) + "-12"
    else:
        return str(year) + "-" + str(month_number - 1).zfill(2)    # zfill(2): "5" -> "05"


def puts_between(first_time, last_time, cache):
    """
    All puts with a snapshot time from first_time to last_time (both included).
    The two times are at most two days apart, so at most two months are read.
    """

    months = [first_time[:7]]                       # the month of the first time, e.g. "2021-06"
    if last_time[:7] != first_time[:7]:
        months.append(last_time[:7])

    pieces = []
    for month in months:
        table = read_month_puts(month, cache)

        # True/False masks again; & means "and": both must hold
        after_first = table["quote_datetime"] >= first_time
        before_last = table["quote_datetime"] <= last_time
        pieces.append(table[after_first & before_last])

    # pd.concat glues the pieces under each other into one table
    return pd.concat(pieces)


# ---- the open position --------------------------------------------------------------

def open_position_before(trades, when):
    """
    The trade that was open just before the snapshot `when`: the one entered
    before it and closed at it or later. Returns one row, or None if none was
    open (before the first entry, or the last position, which never closed and
    so is not in the trade log).
    """

    for _, trade in trades.iterrows():              # iterrows(): one row at a time
        if trade["entry_time"] < when and trade["exit_time"] >= when:
            return trade

    return None


def positions_open_on_day(trades, day_start, day_end):
    """
    Every trade open at some time between day_start and day_end (text times).
    Returns a list of rows.
    """

    found = []
    for _, trade in trades.iterrows():
        if trade["entry_time"] <= day_end and trade["exit_time"] >= day_start:
            found.append(trade)
    return found


def position_text(trade):
    """The lines of position.txt for one trade."""

    lines = []
    for field in POSITION_FIELDS:
        lines.append("  " + field + ": " + str(trade[field]))
    return lines


def leg_quotes(puts, trade):
    """The rows of `puts` that belong to the two legs of `trade`."""

    same_root = puts["root"] == trade["root"]
    same_expiry = puts["expiration"] == trade["expiration"]

    # .isin(...) is True where the strike is one of the two in the list
    is_leg = puts["strike"].isin([trade["strike_short"], trade["strike_long"]])

    legs = puts[same_root & same_expiry & is_leg]

    # sort by time, then strike, so the file reads in order
    return legs.sort_values(["quote_datetime", "strike"])


# ---- the rates and the raw data ---------------------------------------------------

def rates_around(date, file_names):
    """
    The FRED rates (in percent, as downloaded) from RATE_DAYS_AROUND days before
    `date` up to `date`, one column per file. Returns a table.
    """

    # the first date, RATE_DAYS_AROUND calendar days before `date`:
    day = pd.Timestamp(date)                        # the text "2016-10-24" as a real date
    first_day = day - pd.Timedelta(days=RATE_DAYS_AROUND)   # Timedelta = a length of time; subtract 7 days
    first_date = str(first_day)[:10]                # back to text, first 10 characters: "2016-10-17"

    table = None
    for name in file_names:
        one = pd.read_csv(RATES_FOLDER + "/" + name + ".csv")   # columns observation_date, name

        # keep the rows from first_date to date (dates as text sort like time)
        not_too_early = one["observation_date"] >= first_date
        not_too_late = one["observation_date"] <= date
        one = one[not_too_early & not_too_late]

        if table is None:                           # the first file: start the table with it
            table = one
        else:
            # merge puts the columns side by side, matching rows on the date.
            # how="outer" keeps a date even if only one of the files has it.
            table = table.merge(one, on="observation_date", how="outer")

    return table


def write_raw_files(folder, when):
    """For a deep check: the raw rows of the snapshot, the official close and the rates."""

    date = when[:10]

    raw_path = RAW_FOLDER + "/UnderlyingOptionsIntervals_900sec_" + date + ".csv"
    print("  reading", raw_path)
    raw = pd.read_csv(raw_path)
    raw = raw[raw["quote_datetime"] == when]        # only this snapshot
    raw.to_csv(folder + "/raw.csv", index=False)    # index=False: no pandas row numbers

    close = pd.read_csv(INDEX_CLOSE_FILE)
    close = close[close["Date"] == date]
    close.to_csv(folder + "/index_close.csv", index=False)

    rates = rates_around(date, ["DGS1MO", "DGS3MO", "DGS6MO", "DGS1"])
    rates.to_csv(folder + "/rates.csv", index=False)


# ---- one packet ------------------------------------------------------------------------

def make_snapshot_packet(folder, run, when, trades, atm, day_before, cache):
    """The packet of one snapshot (see the top of this file)."""

    lines = ["Hand check at " + when + ", run " + run, ""]

    trade = open_position_before(trades, when)

    if trade is None:
        # .min() of a text column is the earliest time, i.e. the first entry
        if when <= trades["entry_time"].min():      # at or before the first entry
            lines.append("No position is open before this snapshot. Deficit: 0.")
        else:
            lines.append("NOT FOUND: the open position is not in the trade log "
                         "(the last position of the sample never closed).")
        legs = None
    else:
        lines.append("Position open before this snapshot (deficit = deficit_at_entry, "
                     "it changes only when a position closes):")
        lines = lines + position_text(trade)

        # the legs from the first snapshot of the day before up to this snapshot
        puts = puts_between(day_before + " 00:00:00", when, cache)
        legs = leg_quotes(puts, trade)

    # every put at this snapshot
    puts_now = puts_between(when, when, cache)
    puts_now = puts_now.sort_values(["expiration", "root", "strike"])

    # every expiry at this snapshot, with its forward and ATM vol
    expiries = atm[atm["quote_datetime"] == when]
    expiries = expiries.sort_values(["dte", "root"])

    with open(folder + "/position.txt", "w") as f:  # "with" closes the file by itself
        f.write("\n".join(lines) + "\n")            # "\n".join(...): one line per item

    if legs is not None:
        legs.to_csv(folder + "/legs.csv", index=False)
    puts_now.to_csv(folder + "/puts.csv", index=False)
    expiries.to_csv(folder + "/expiries.csv", index=False)


def make_day_packet(folder, run, date, trades, day_before, cache):
    """The packet of the equity day (see the top of this file)."""

    lines = ["Hand check of the day " + date + " (equity curve), run " + run,
             "The trading day before: " + day_before, ""]

    # every position open at the end of the day before or during the day
    open_trades = positions_open_on_day(trades, day_before + " 16:15:00", date + " 23:59:59")

    puts = puts_between(day_before + " 00:00:00", date + " 23:59:59", cache)

    all_legs = []
    for trade in open_trades:
        lines.append("Position:")
        lines = lines + position_text(trade)
        lines.append("  exit_time: " + str(trade["exit_time"]))
        lines.append("")
        all_legs.append(leg_quotes(puts, trade))

    with open(folder + "/position.txt", "w") as f:
        f.write("\n".join(lines) + "\n")

    if len(all_legs) > 0:
        pd.concat(all_legs).to_csv(folder + "/legs.csv", index=False)

    rates_around(date, ["DGS3MO"]).to_csv(folder + "/rates.csv", index=False)


# ---- main ---------------------------------------------------------------------------------

def main():

    work = pd.read_csv(LIST_FILE)                   # columns hand_check, run, snapshot, deep

    print("loading", ATM_FILE, "...")
    atm = pd.read_csv(ATM_FILE)

    # the trading days in the data, sorted: to find "the day before"
    trading_days = sorted(atm["quote_datetime"].str[:10].unique())   # .str[:10]: first 10 characters of each

    # the last snapshot of each day (16:15, or 13:15 on an early-close day),
    # written into each packet as calendar.txt. The times are sorted, so the
    # last time we see for a date is that day's last snapshot.
    last_time_of_day = {}
    for when in sorted(atm["quote_datetime"].unique()):
        last_time_of_day[when[:10]] = when[11:]

    # the trade logs, one per run, read when first needed
    trade_logs = {}

    # work in time order, so each month file is read only once
    work = work.sort_values("snapshot")

    cache = {}                                      # month -> table of puts

    for _, item in work.iterrows():

        name = item["hand_check"]                   # "H07"
        run = item["run"]                           # "base_mid"
        snapshot = item["snapshot"]                 # "2020-03-09 10:00:00" or "2016-10-24 (day)"

        print(name, run, snapshot)

        folder = OUT_FOLDER + "/" + name
        os.makedirs(folder, exist_ok=True)          # make the folder (no error if it exists)

        if run not in trade_logs:
            trade_logs[run] = pd.read_csv(RESULTS_FOLDER + "/trades_" + run + ".csv")
        trades = trade_logs[run]

        date = snapshot[:10]
        position_in_list = trading_days.index(date)          # where the date is in the list

        # the trading day before it. The first day of the data has none: then we
        # use the day itself (fixed 2026-11-17; before, position -1 wrapped round
        # to the LAST day of the data). It only matters for the very first
        # snapshot, where no position is open yet.
        if position_in_list > 0:
            day_before = trading_days[position_in_list - 1]
        else:
            day_before = date

        # calendar.txt: when the day before and this day end (calendar knowledge,
        # not prices), so the stock close of an early-close day can be told apart
        with open(folder + "/calendar.txt", "w") as f:
            if day_before != date:
                f.write("last snapshot of " + day_before + ": " + last_time_of_day[day_before] + "\n")
            else:
                f.write("no trading day before " + date + " in the data\n")
            f.write("last snapshot of " + date + ": " + last_time_of_day[date] + "\n")

        if snapshot.endswith("(day)"):
            make_day_packet(folder, run, date, trades, day_before, cache)
        else:
            make_snapshot_packet(folder, run, snapshot, trades, atm, day_before, cache)
            if item["deep"] == "yes":
                write_raw_files(folder, snapshot)

    print("written:", len(work), "packets into", OUT_FOLDER)


# Only run main() when this file is started directly
# (python validation/hand_checks/make_packets.py), not when another file imports it.
if __name__ == "__main__":
    main()
