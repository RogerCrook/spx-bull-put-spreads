"""
Invariants of the outputs (code validation, step 2, method 4).

What this file is for
---------------------
The one-step check (one_step_check.py) covered every decision and every trade.
This script checks the remaining statements of the test specification that can be
checked on the real output files:

  Part A  the daily equity file of each run (results/equity_<run>.csv), rebuilt
          day by day from the trades, the logged quotes and the T-bill yields:
            - margin of the day = margin of the position open at the day's close
              (S26, S13, G9),
            - realised P&L, unrealised P&L at the mids of the last usable snapshot
              of the day, also in the runs crossing the spread (S28, G13),
            - interest of day t = margin(t-1) * (exp(r(t) * days / 365) - 1), with
              r(t) the 3-month rate of day t (S27, G14, G21),
            - total P&L = realised + unrealised + interest, day P&L = its change,
            - the deficit at the day's close.
  Part B  the returns of a period = its P&L / its average daily margin (S29):
            - against results/quarters_<run>.csv,
            - the yearly returns and the 2012-2026 row of tab:results-years, read
              from the .tex, for the base case (S30), and the index column from
              Data/09_total_return.
  Part C  the data series in Data/05_atm_vol.csv (D2, D5): S is the same for all
          expiries of a snapshot, equals the recorded quote except at the snapshot
          after the close, where it equals the official close; dte = calendar days.
  Part D  the stress indicator (D13, S32): the threshold is the 80th percentile of
          the 252 previous 30-day values, stress = value > threshold, and each
          trade's stress columns agree with that.
  Part E  (added 2026-11-20, after the mutation tests found it unchecked) the
          30-day vol recorded at each entry (vol30_entry), recomputed from the ATM
          vols of the entry snapshot in Data/05_atm_vol.csv (D13). The way of
          interpolating is not in the thesis: taken from checks/check_vol30.py.

Written from the thesis and validation/test_specification.md only, without reading
Code/. Choices that the thesis does not fix are marked "choice".

How to run (from the main folder; read-only, expected under a minute):
    python validation/automatic/invariants_check.py

Prints a summary and writes every difference to
validation/automatic/output/invariants_check.csv. Writes nothing else.
"""

import csv                      # reads and writes CSV files row by row
import math                     # exp, log, floor
import os                       # the output folder
from datetime import date       # to count calendar days between two dates


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# The mutation tests (step 5) point the settings marked "(outside)" elsewhere through
# environment variables: os.environ.get("NAME", default) reads a setting given from
# outside the script, or uses the default. Run normally, nothing changes.
RESULTS_FOLDER = os.environ.get("CHECK_RESULTS_FOLDER", "results")                         # (outside)
ATM_VOL_FILE = os.environ.get("CHECK_ATM_VOL_FILE", "Data/05_atm_vol.csv")   # snapshot times, S, dte (outside)
VOL30_FILE = os.environ.get("CHECK_VOL30_FILE", "Data/06_vol30.csv")         # daily 30-day vol, threshold (outside)
INDEX_CLOSE_FILE = "Data/07_index_close/GSPC_daily.csv"  # official close
TOTAL_RETURN_FILE = "Data/09_total_return/SP500TR_daily.csv"
RATE_FILE = "Data/03_treasury_bills/DGS3MO.csv"          # 3-month T-bill yield, per cent
TEX_FILE = "Masterarbeit_Tex_file/Masterarbeit_Tex_file.tex"
OUTPUT_FOLDER = os.environ.get("CHECK_OUTPUT_FOLDER", "validation/automatic/output")       # (outside)

# the runs (outside: a comma-separated list; .split(",") cuts it at the commas)
RUNS = os.environ.get("CHECK_RUNS", "base_mid,base_cross,p15_mid,p15_cross").split(",")
# "yes" skips the comparison with tab:results-years, which only fits the full sample (outside)
SKIP_YEAR_TABLE = os.environ.get("CHECK_SKIP_YEAR_TABLE", "no") == "yes"
EXECUTION = {"base_mid": "mid", "base_cross": "cross", "p15_mid": "mid", "p15_cross": "cross"}

NUMBER_OF_SPREADS = 2           # two spreads (def:entry)
DOLLARS_PER_POINT = 100         # one SPX option = 100 dollars per index point
RATE_MATURITY_DAYS = 91         # the 3-month yield converted with tau = 91 / 365 (choice:
                                # the thesis says "each series' own maturity", not the days)
TRADING_DAYS_PER_YEAR = 252     # the 2012-2026 row divides by 3,675 / 252 years (tab:results-years)
STRESS_WINDOW = 252             # trading days with a value (def:stress)
STRESS_PERCENTILE = 0.80        # the 80th percentile (def:stress)

TOLERANCE = 1e-6                # numbers equal within this (dollars, fractions)
CLOSE_TOLERANCE = 0.005         # S against the official close, index points (choice)
SKIP_ACTION = "skipped (broken)"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def read_table(path):
    """Read a CSV file into a list of dictionaries {column: text}."""
    rows = []
    with open(path, newline="") as file:
        reader = csv.DictReader(file)               # the first line gives the column names
        for row in reader:
            rows.append(row)
    return rows


def days_between(first_text, second_text):
    """
    Calendar days from one date "YYYY-MM-DD" to another.

    Example:  days_between("2012-01-06", "2012-01-09")  ->  3
    """
    first = date.fromisoformat(first_text[:10])
    second = date.fromisoformat(second_text[:10])
    difference = second - first                     # a "timedelta", a length of time
    return difference.days


def is_equal(a, b):
    """True if two numbers are equal within TOLERANCE, or within 1e-9 of their size."""
    allowed = TOLERANCE + 1e-9 * max(abs(a), abs(b))
    return abs(a - b) <= allowed


def add_problem(problems, run, part, statement, key, what, expected, found):
    """Keep one difference. Every difference becomes one row of the output file."""
    problems.append({"run": run, "part": part, "statement": statement, "key": key,
                     "what": what, "expected": str(expected), "found": str(found)})


def mid_value(row, leg):
    """The midpoint (bid + ask) / 2 of one leg of a quote-log row pair (eq:mid)."""
    bid = float(row[leg]["bid"])
    ask = float(row[leg]["ask"])
    return (bid + ask) / 2


def percentile_linear(values, fraction):
    """
    The percentile of a list of numbers with linear interpolation between the two
    nearest sorted values (choice: the convention is not in the thesis).
    position = fraction * (n - 1), counted from 0 in the sorted list.

    Example:  percentile_linear([1, 2, 3, 4, 5], 0.80)  ->  4.2
    """
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    below = math.floor(position)                    # the sorted value just below
    weight = position - below                       # how far towards the next one
    if below + 1 >= len(ordered):
        return ordered[below]
    return ordered[below] + weight * (ordered[below + 1] - ordered[below])


# ---------------------------------------------------------------------------
# Reading the data series
# ---------------------------------------------------------------------------

def read_snapshot_data(official_close, problems):
    """
    Read Data/05_atm_vol.csv line by line. Returns the sorted list of trading days
    and {day: time of its last snapshot}. Checks D2 and D5 on the way (Part C)
    and returns their counts.
    """
    last_time_of_day = {}
    spot_of_time = {}                               # the first S seen at each snapshot
    counts = {"rows": 0, "S differs between expiries": 0, "S differs from the quote": 0,
              "S differs from the official close": 0, "days differ": 0, "after-close snapshots": 0}

    # First pass: the last snapshot of each day (the file is sorted by time).
    with open(ATM_VOL_FILE, newline="") as file:
        reader = csv.reader(file)                   # each line as a list of texts
        header = next(reader)                       # next() takes the first line, the column names
        time_column = header.index("quote_datetime")
        for line in reader:
            time = line[time_column]
            last_time_of_day[time[:10]] = time

    after_close_times = set()
    for day in last_time_of_day:
        after_close_times.add(last_time_of_day[day])

    # Second pass: the checks of Part C.
    with open(ATM_VOL_FILE, newline="") as file:
        reader = csv.reader(file)
        header = next(reader)
        time_column = header.index("quote_datetime")
        expiration_column = header.index("expiration")
        dte_column = header.index("dte")
        spot_column = header.index("spot")
        quote_column = header.index("spot_quote")
        for line in reader:
            counts["rows"] = counts["rows"] + 1
            time = line[time_column]
            spot = float(line[spot_column])
            spot_quote = float(line[quote_column])

            # D2: one S per snapshot, the same for every expiry.
            if time not in spot_of_time:
                spot_of_time[time] = spot
            elif spot != spot_of_time[time]:
                counts["S differs between expiries"] = counts["S differs between expiries"] + 1
                add_problem(problems, "data", "C", "D2", time, "S differs between expiries", spot_of_time[time], spot)

            # D2: at the snapshot after the close S is the official close, elsewhere the quote.
            if time in after_close_times:
                day = time[:10]
                if day not in official_close:
                    add_problem(problems, "data", "C", "D2", time, "no official close for the day", "a close", "none")
                elif abs(spot - official_close[day]) > CLOSE_TOLERANCE:
                    counts["S differs from the official close"] = counts["S differs from the official close"] + 1
                    add_problem(problems, "data", "C", "D2", time + " " + line[expiration_column], "S at the after-close snapshot", official_close[day], spot)
            elif spot != spot_quote:
                counts["S differs from the quote"] = counts["S differs from the quote"] + 1
                add_problem(problems, "data", "C", "D2", time + " " + line[expiration_column], "S away from the after-close snapshot", spot_quote, spot)

            # D5: days to expiry = calendar days.
            if days_between(time, line[expiration_column]) != int(line[dte_column]):
                counts["days differ"] = counts["days differ"] + 1
                add_problem(problems, "data", "C", "D5", time + " " + line[expiration_column], "dte", days_between(time, line[expiration_column]), line[dte_column])

    counts["after-close snapshots"] = len(after_close_times)
    trading_days = sorted(last_time_of_day)
    return trading_days, last_time_of_day, counts


def read_official_close():
    """{day: official close} from Data/07_index_close (the Close column)."""
    closes = {}
    for row in read_table(INDEX_CLOSE_FILE):
        closes[row["Date"]] = float(row["Close"])
    return closes


def read_rates(trading_days):
    """
    {trading day: continuous 3-month rate} (sec:rates):
      y = yield / 100, forward-filled over days without a value,
      r = log(1 + y * tau) / tau with tau = 91 / 365   (eq:rate-conversion)
    """
    yield_of_day = {}
    for row in read_table(RATE_FILE):
        text = row["DGS3MO"]
        if text != "" and text != ".":              # FRED leaves holidays empty (or ".")
            yield_of_day[row["observation_date"]] = float(text) / 100

    known_days = sorted(yield_of_day)
    rates = {}
    position = 0
    last_yield = None
    tau = RATE_MATURITY_DAYS / 365
    for day in trading_days:
        # Move along the known days up to this day; the last one seen is the forward-fill.
        while position < len(known_days) and known_days[position] <= day:
            last_yield = yield_of_day[known_days[position]]
            position = position + 1
        if last_yield is None:
            raise ValueError("no T-bill yield on or before " + day)
        rates[day] = math.log(1 + last_yield * tau) / tau
    return rates


# ---------------------------------------------------------------------------
# Part A: the daily equity of one run
# ---------------------------------------------------------------------------

def build_positions(run, quote_rows, trades):
    """
    The positions of a run from the quote log, in time order. Each position has its
    entry time, its credit at execution, its margin (G15), its deficit at entry, and
    a list of usable marks (time, value of the two spreads at mid): the entry and
    every held snapshot not skipped for a broken quote (G13).
    """
    entry_rows = {}                                 # {time: {"short": row, "long": row}}
    held_rows = {}
    for row in quote_rows:
        if row["kind"] == "entry":
            table = entry_rows
        else:
            table = held_rows
        if row["time"] not in table:
            table[row["time"]] = {}
        table[row["time"]][row["leg"]] = row

    trade_of_entry = {}
    for trade in trades:
        trade_of_entry[trade["entry_time"]] = trade

    positions = []
    for entry_time in sorted(entry_rows):
        legs = entry_rows[entry_time]
        short_strike = float(legs["short"]["strike"])
        long_strike = float(legs["long"]["strike"])
        if EXECUTION[run] == "mid":
            credit = NUMBER_OF_SPREADS * (mid_value(legs, "short") - mid_value(legs, "long"))
        else:
            # Sell the higher put at its bid, buy the lower at its ask (sec:costs).
            credit = NUMBER_OF_SPREADS * (float(legs["short"]["bid"]) - float(legs["long"]["ask"]))
        margin = (NUMBER_OF_SPREADS * (short_strike - long_strike) - credit) * DOLLARS_PER_POINT
        mark_at_entry = NUMBER_OF_SPREADS * (mid_value(legs, "short") - mid_value(legs, "long"))
        position = {
            "entry_time": entry_time,
            "credit": credit,
            "margin": margin,
            "trade": trade_of_entry.get(entry_time),          # None for the position open at the end
            "marks": [(entry_time, mark_at_entry)],
        }
        positions.append(position)

    # Each held row belongs to the last position opened strictly before it.
    entry_times = []
    for position in positions:
        entry_times.append(position["entry_time"])
    owner = 0
    for time in sorted(held_rows):
        while owner + 1 < len(positions) and entry_times[owner + 1] < time:
            owner = owner + 1
        legs = held_rows[time]
        if legs["short"]["action"] == SKIP_ACTION:
            continue                                          # no mark at a broken quote (S21)
        mark = NUMBER_OF_SPREADS * (mid_value(legs, "short") - mid_value(legs, "long"))
        positions[owner]["marks"].append((time, mark))
    return positions


def expected_equity(run, positions, trades, trading_days, last_time_of_day, rates):
    """
    Rebuild the daily equity of one run. Returns {day: dictionary of the columns}.

    For each trading day t:
      open position  = the last one opened at or before the day's last snapshot
      margin(t)      = its margin                                         (S26)
      realised(t)    = 100 * sum of the P&L of the cycles closed on or before t
      unrealised(t)  = 100 * (credit - mark at mid of its last usable snapshot)   (S28, G13)
      interest(t)    = margin(t-1) * (exp(r(t) * days / 365) - 1), 0 on the first day (G21)
      total(t)       = realised + unrealised + interest so far
      day P&L(t)     = total(t) - total(t-1)
      deficit(t)     = deficit at entry of the open position, or after the last cycle
    """
    closed = []                                     # (exit time, P&L in dollars, deficit after)
    for trade in trades:
        closed.append((trade["exit_time"], float(trade["pnl_dollars"]), float(trade["deficit_after"])))
    closed.sort()                                   # sort by exit time (the first item)

    equity = {}
    open_index = -1                                 # index of the open position, -1 = none yet
    closed_index = 0
    realised = 0.0
    interest_total = 0.0
    previous_total = 0.0
    previous_margin = None
    previous_day = None
    last_mark = {}                                  # {position index: latest usable mark so far}
    mark_index = []                                 # how far each position's marks are read
    for position in positions:
        mark_index.append(0)

    for day in trading_days:
        day_end = last_time_of_day[day]

        # The open position at the close: move on while the next one opened by day_end.
        while open_index + 1 < len(positions) and positions[open_index + 1]["entry_time"] <= day_end:
            open_index = open_index + 1

        # Read the marks of every position up to day_end (only the open one matters).
        if open_index >= 0:
            marks = positions[open_index]["marks"]
            while mark_index[open_index] < len(marks) and marks[mark_index[open_index]][0] <= day_end:
                last_mark[open_index] = marks[mark_index[open_index]][1]
                mark_index[open_index] = mark_index[open_index] + 1

        # Cycles closed on or before this day add their P&L to the realised P&L.
        while closed_index < len(closed) and closed[closed_index][0] <= day_end:
            realised = realised + closed[closed_index][1]
            closed_index = closed_index + 1

        if open_index >= 0:
            position = positions[open_index]
            margin = position["margin"]
            unrealised = (position["credit"] - last_mark[open_index]) * DOLLARS_PER_POINT
            if position["trade"] is not None:
                deficit = float(position["trade"]["deficit_at_entry"])
            else:
                deficit = None                      # the last position: deficit of the last cycle
        else:
            margin = 0.0                            # before the first entry (does not happen)
            unrealised = 0.0
            deficit = 0.0

        if previous_day is None:
            interest_today = 0.0                    # the first trading day earns nothing (G21)
        else:
            days = days_between(previous_day, day)
            interest_today = previous_margin * (math.exp(rates[day] * days / 365) - 1)
        interest_total = interest_total + interest_today

        total = realised + unrealised + interest_total
        equity[day] = {
            "realised": realised,
            "unrealised": unrealised,
            "interest_today": interest_today,
            "interest_total": interest_total,
            "total_pnl": total,
            "margin": margin,
            "rate": rates[day],
            "deficit": deficit,
            "pnl_day": total - previous_total,
            "position open": open_index >= 0,
        }
        previous_total = total
        previous_margin = margin
        previous_day = day

    # The deficit of the last open position is the deficit after the last cycle.
    for day in equity:
        if equity[day]["deficit"] is None:
            equity[day]["deficit"] = closed[-1][2]
    return equity


def check_equity(run, expected, equity_rows, problems, counts):
    """Compare the rebuilt equity with results/equity_<run>.csv, column by column."""
    logged_days = []
    for row in equity_rows:
        logged_days.append(row["date"])
    if logged_days != sorted(expected):
        add_problem(problems, run, "A", "S13", "", "trading days of the equity file", str(len(expected)) + " data days", str(len(logged_days)) + " rows")

    for row in equity_rows:
        day = row["date"]
        if day not in expected:
            continue
        mine = expected[day]
        counts["equity days"] = counts["equity days"] + 1
        if not mine["position open"]:
            counts["days without a position"] = counts["days without a position"] + 1
        for column in ["realised", "unrealised", "interest_today", "interest_total",
                       "total_pnl", "margin", "rate", "deficit", "pnl_day"]:
            found = float(row[column])
            if not is_equal(mine[column], found):
                counts["equity fields that differ"] = counts["equity fields that differ"] + 1
                add_problem(problems, run, "A", "S26-S28", day, column, mine[column], found)
            counts["equity fields checked"] = counts["equity fields checked"] + 1


# ---------------------------------------------------------------------------
# Part B: returns of periods
# ---------------------------------------------------------------------------

def period_returns(expected, period_of_day):
    """
    Sum the day P&L and average the margin over the days of each period (S29).
    period_of_day turns a day into its period, e.g. "2012-Q1" or "2012".
    Returns {period: (days, P&L, average margin, return)}.
    """
    sums = {}
    for day in sorted(expected):
        period = period_of_day(day)
        if period not in sums:
            sums[period] = [0, 0.0, 0.0]            # days, P&L, sum of margins
        sums[period][0] = sums[period][0] + 1
        sums[period][1] = sums[period][1] + expected[day]["pnl_day"]
        sums[period][2] = sums[period][2] + expected[day]["margin"]
    result = {}
    for period in sums:
        days, pnl, margin_sum = sums[period]
        average_margin = margin_sum / days
        result[period] = (days, pnl, average_margin, pnl / average_margin)
    return result


def quarter_of(day):
    """ "2012-05-14" -> "2012-Q2" """
    month = int(day[5:7])
    quarter = (month - 1) // 3 + 1                  # // divides and drops the remainder
    return day[:4] + "-Q" + str(quarter)


def year_of(day):
    """ "2012-05-14" -> "2012" """
    return day[:4]


def whole_sample(day):
    """Every day belongs to the same period, for the 2012-2026 row."""
    return "all"


def check_quarters(run, expected, quarter_rows, problems, counts):
    """Compare the quarters with results/quarters_<run>.csv."""
    mine = period_returns(expected, quarter_of)
    for row in quarter_rows:
        period = row["period"]
        counts["quarters checked"] = counts["quarters checked"] + 1
        if period not in mine:
            add_problem(problems, run, "B", "S29", period, "quarter not in the rebuilt equity", "", "")
            continue
        days, pnl, average_margin, period_return = mine[period]
        same_days = int(row["days"]) == days
        same_pnl = is_equal(pnl, float(row["pnl"]))
        same_margin = is_equal(average_margin, float(row["mean_margin"]))
        same_return = is_equal(period_return, float(row["return"]))
        if not (same_days and same_pnl and same_margin and same_return):
            counts["quarters that differ"] = counts["quarters that differ"] + 1
            add_problem(problems, run, "B", "S29", period, "days / pnl / mean margin / return",
                        str(days) + " / " + str(pnl) + " / " + str(average_margin) + " / " + str(period_return),
                        row["days"] + " / " + row["pnl"] + " / " + row["mean_margin"] + " / " + row["return"])


def read_year_table():
    """
    Read tab:results-years from the .tex: {year or "all": (index, mid, cross)} in per
    cent as written. The rows sit between the header line and \\bottomrule.
    """
    table = {}
    inside = False
    with open(TEX_FILE, encoding="utf-8") as file:
        for line in file:
            if "\\textbf{Year} & \\textbf{S\\&P~500} & \\textbf{Mid} & \\textbf{Cross}" in line:
                inside = True
                continue
            if inside and "\\bottomrule" in line:
                break
            if not inside or "&" not in line:
                continue
            cells = line.split("&")                 # the four columns of the row
            label = cells[0].strip()
            numbers = []
            for cell in cells[1:]:
                text = cell.replace("$", "").replace("\\\\", "").strip()
                numbers.append(float(text))
            if "--" in label:
                table["all"] = numbers              # the 2012--2026 row
            else:
                year = label.replace("$", "").replace("^\\ast", "").strip()
                table[year] = numbers
    return table


def index_returns(trading_days):
    """
    The S&P 500 total return index (Data/09_total_return): each year's return =
    close on its last trading day / close on the last trading day before - 1, and
    the whole sample compounded per year over 3,675 / 252 years. In per cent.
    """
    close_of_day = {}
    for row in read_table(TOTAL_RETURN_FILE):
        close_of_day[row["Date"]] = float(row["tr_close"])
    days = sorted(close_of_day)

    # The close at the end of each year, and the one before the first trading day.
    end_of_year = {}
    start_close = None
    for day in days:
        if day < trading_days[0]:
            start_close = close_of_day[day]         # the last day before the sample
        elif day <= trading_days[-1]:
            end_of_year[day[:4]] = close_of_day[day]
    result = {}
    previous = start_close
    for year in sorted(end_of_year):
        result[year] = 100 * (end_of_year[year] / previous - 1)
        previous = end_of_year[year]
    years = len(trading_days) / TRADING_DAYS_PER_YEAR
    growth = end_of_year[sorted(end_of_year)[-1]] / start_close
    result["all"] = 100 * (growth ** (1 / years) - 1)           # ** is "to the power of"
    return result


def check_year_table(expected_by_run, trading_days, problems, counts):
    """Compare tab:results-years with the rebuilt base-case equity and the index file (S29, S30)."""
    table = read_year_table()
    index = index_returns(trading_days)
    years_in_sample = len(trading_days) / TRADING_DAYS_PER_YEAR
    columns = [("index", None), ("mid", "base_mid"), ("cross", "base_cross")]
    for column_number in range(3):
        name, run = columns[column_number]
        if run is None:
            mine = index
        else:
            by_year = period_returns(expected_by_run[run], year_of)
            mine = {}
            for year in by_year:
                mine[year] = 100 * by_year[year][3]
            whole = period_returns(expected_by_run[run], whole_sample)["all"]
            mine["all"] = 100 * whole[3] / years_in_sample        # not compounded (tab:results-years)
        for key in table:
            counts["table cells checked"] = counts["table cells checked"] + 1
            written = table[key][column_number]
            if key not in mine:
                add_problem(problems, name, "B", "S29/S30", key, "tab:results-years", "a value", "none")
                continue
            if round(mine[key], 1) != written:
                counts["table cells that differ"] = counts["table cells that differ"] + 1
                add_problem(problems, name, "B", "S29/S30", key, "tab:results-years (per cent)", round(mine[key], 3), written)


# ---------------------------------------------------------------------------
# Part D: the stress indicator
# ---------------------------------------------------------------------------

def check_stress(trades_by_run, problems, counts):
    """
    D13: recompute the threshold of each day from Data/06_vol30.csv as the 80th
    percentile of the 252 previous days that have a 30-day value, and the flag
    stress = value > threshold. S32: each trade's stress columns agree.
    """
    rows = read_table(VOL30_FILE)
    threshold_of_day = {}
    history = []                                    # the 30-day values before the day, in order
    stress_days = 0
    full_window_days = 0
    for row in rows:
        day = row["date"]
        counts["vol30 days"] = counts["vol30 days"] + 1
        if len(history) >= STRESS_WINDOW:
            window = history[len(history) - STRESS_WINDOW:]       # the last 252 values
            threshold = percentile_linear(window, STRESS_PERCENTILE)
        else:
            threshold = None                        # not enough history yet
        threshold_of_day[day] = threshold

        logged = row["threshold"]
        if threshold is None:
            if logged != "":
                add_problem(problems, "data", "D", "D13", day, "threshold before a full window", "none", logged)
        elif logged == "" or not is_equal(threshold, float(logged)):
            counts["thresholds that differ"] = counts["thresholds that differ"] + 1
            add_problem(problems, "data", "D", "D13", day, "threshold", threshold, logged)

        if row["vol30"] != "":
            value = float(row["vol30"])
            if threshold is not None:
                full_window_days = full_window_days + 1
                stress = value > threshold
                if stress:
                    stress_days = stress_days + 1
                if str(stress) != row["stress"]:
                    counts["stress flags that differ"] = counts["stress flags that differ"] + 1
                    add_problem(problems, "data", "D", "D13", day, "stress flag", stress, row["stress"])
            history.append(value)                   # today's value joins the window of tomorrow
        else:
            counts["days without a 30-day value"] = counts["days without a 30-day value"] + 1

    counts["share of stress days (per cent, thesis 19.7)"] = round(100 * stress_days / full_window_days, 2)

    # S32: each trade's stress columns.
    for run in RUNS:
        for trade in trades_by_run[run]:
            counts["trades checked for stress"] = counts["trades checked for stress"] + 1
            day = trade["entry_time"][:10]
            if trade["stress_threshold"] == "":
                continue                            # no full window yet
            threshold = float(trade["stress_threshold"])
            if threshold_of_day.get(day) is None or not is_equal(threshold, threshold_of_day[day]):
                counts["trade thresholds that differ"] = counts["trade thresholds that differ"] + 1
                add_problem(problems, run, "D", "S32", trade["entry_time"], "stress_threshold of the entry day", threshold_of_day.get(day), trade["stress_threshold"])
            stress = float(trade["vol30_entry"]) > threshold
            if str(stress) != trade["stress"]:
                counts["trade stress flags that differ"] = counts["trade stress flags that differ"] + 1
                add_problem(problems, run, "D", "S32", trade["entry_time"], "stress = vol30_entry > threshold", stress, trade["stress"])


# ---------------------------------------------------------------------------
# Part E: the 30-day vol recorded at each entry (added 2026-11-20)
# ---------------------------------------------------------------------------

def thirty_day_vol(slices):
    """
    The 30-day ATM vol of one snapshot (def:stress), or None if 30 days is not
    bracketed by the listed expiries.

      slices : a list of (days to expiry, ATM vol) of that snapshot, all roots

    The thesis says only "interpolated between the two listed expiries around it".
    How (choice, as in checks/check_vol30.py and sec:stress's footnote script): the
    vols of SPX and SPXW with the same days are averaged, each vol is turned into
    total variance sigma^2 * tau, a straight line is drawn between the expiry just
    below and the one just above 30 days, and the value at 30 days is turned back
    into a vol: sqrt(variance / tau_30).

    Example: 20 days at 0.20 and 40 days at 0.30 give the variances
      0.04 * 20/365 = 0.8/365 and 0.09 * 40/365 = 3.6/365. Halfway between them
      is 2.2/365, divided by tau_30 = 30/365 that is 0.07333, so the vol is 0.2708.
    """
    # Average the vols that share a number of days: add them up and count them.
    total = {}                                      # days -> sum of the vols
    number = {}                                     # days -> how many vols
    for days, vol in slices:
        if days not in total:
            total[days] = 0.0
            number[days] = 0
        total[days] = total[days] + vol
        number[days] = number[days] + 1
    if len(total) == 0:
        return None

    target_days = 30
    if target_days in total:                        # an expiry exactly 30 days away
        return total[target_days] / number[target_days]

    # The expiry just below 30 days and the one just above.
    below = None
    above = None
    for days in total:
        if days < target_days and (below is None or days > below):
            below = days
        if days > target_days and (above is None or days < above):
            above = days
    if below is None or above is None:              # 30 days not bracketed
        return None

    vol_below = total[below] / number[below]
    vol_above = total[above] / number[above]
    variance_below = vol_below * vol_below * below / 365.0       # sigma^2 * tau
    variance_above = vol_above * vol_above * above / 365.0
    weight = (target_days - below) / (above - below)             # how far towards "above"
    variance = variance_below + weight * (variance_above - variance_below)
    return math.sqrt(variance / (target_days / 365.0))


def check_vol30_at_entry(trades_by_run, problems, counts):
    """
    D13: recompute the 30-day vol at the entry snapshot of every trade from
    ATM_VOL_FILE and compare it with the trade's vol30_entry column.
    """
    # The entry snapshots of all runs, so only their rows are kept from the large file.
    entry_times = set()
    for run in RUNS:
        for trade in trades_by_run[run]:
            entry_times.add(trade["entry_time"][:19])

    # Read the file line by line and keep (days, ATM vol) of those snapshots.
    slices_at = {}                                  # time -> list of (days, vol)
    with open(ATM_VOL_FILE, newline="") as file:
        for row in csv.DictReader(file):
            time = row["quote_datetime"][:19]
            if time not in entry_times:
                continue
            if row["atm_iv"] == "" or row["atm_iv"].lower() == "nan":
                continue                            # this slice has no ATM vol
            if time not in slices_at:
                slices_at[time] = []
            slices_at[time].append((int(float(row["dte"])), float(row["atm_iv"])))

    for run in RUNS:
        for trade in trades_by_run[run]:
            counts["entry vol30 checked"] = counts["entry vol30 checked"] + 1
            time = trade["entry_time"][:19]
            mine = thirty_day_vol(slices_at.get(time, []))       # .get: an empty list if the time is absent
            stored = trade["vol30_entry"]
            if mine is None and (stored == "" or stored.lower() == "nan"):
                continue                            # both say: no value
            if mine is None or stored == "" or stored.lower() == "nan" or not is_equal(mine, float(stored)):
                counts["entry vol30 that differ"] = counts["entry vol30 that differ"] + 1
                add_problem(problems, run, "E", "D13", trade["entry_time"], "vol30_entry", mine, stored)


# ---------------------------------------------------------------------------
# Main: read, check, write
# ---------------------------------------------------------------------------

def main():
    problems = []
    counts = {}
    for name in ["equity days", "days without a position", "equity fields checked",
                 "equity fields that differ", "quarters checked", "quarters that differ",
                 "table cells checked", "table cells that differ", "vol30 days",
                 "days without a 30-day value", "thresholds that differ", "stress flags that differ",
                 "trades checked for stress", "trade thresholds that differ", "trade stress flags that differ",
                 "entry vol30 checked", "entry vol30 that differ"]:
        counts[name] = 0

    # Part C (and the calendar for the other parts).
    official_close = read_official_close()
    trading_days, last_time_of_day, data_counts = read_snapshot_data(official_close, problems)
    print("Part C: Data/05_atm_vol.csv")
    for name in data_counts:
        print("  " + name.ljust(48) + str(data_counts[name]).rjust(12))
    print("  trading days".ljust(50) + str(len(trading_days)).rjust(12))

    rates = read_rates(trading_days)

    # Part A, per run.
    expected_by_run = {}
    trades_by_run = {}
    for run in RUNS:
        quote_rows = read_table(RESULTS_FOLDER + "/quotes_" + run + ".csv")
        trades = read_table(RESULTS_FOLDER + "/trades_" + run + ".csv")
        equity_rows = read_table(RESULTS_FOLDER + "/equity_" + run + ".csv")
        quarter_rows = read_table(RESULTS_FOLDER + "/quarters_" + run + ".csv")
        trades_by_run[run] = trades

        positions = build_positions(run, quote_rows, trades)
        expected = expected_equity(run, positions, trades, trading_days, last_time_of_day, rates)
        expected_by_run[run] = expected
        check_equity(run, expected, equity_rows, problems, counts)
        check_quarters(run, expected, quarter_rows, problems, counts)

    # Part B: the year table, and Part D.
    if not SKIP_YEAR_TABLE:
        check_year_table(expected_by_run, trading_days, problems, counts)
    check_stress(trades_by_run, problems, counts)
    check_vol30_at_entry(trades_by_run, problems, counts)          # Part E

    print()
    print("Parts A, B, D, E (all four runs together)")
    for name in counts:
        print("  " + name.ljust(48) + str(counts[name]).rjust(12))

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)                    # no error if it exists
    path = OUTPUT_FOLDER + "/invariants_check.csv"
    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["run", "part", "statement", "key", "what", "expected", "found"])
        writer.writeheader()
        for problem in problems:
            writer.writerow(problem)

    # Count the differences by part and statement, and show the first rows.
    by_kind = {}
    for problem in problems:
        kind = problem["part"] + "  " + problem["statement"] + "  " + problem["what"]
        if kind not in by_kind:
            by_kind[kind] = 0
        by_kind[kind] = by_kind[kind] + 1
    print()
    print("  " + str(len(problems)) + " differences written to " + path)
    for kind in sorted(by_kind):
        print("    " + kind.ljust(60) + str(by_kind[kind]).rjust(8))
    shown = 0
    for problem in problems:
        if shown == 15:
            break
        print("    " + problem["run"] + " " + problem["part"] + " " + problem["statement"] + " " + problem["key"]
              + " | " + problem["what"] + " | expected " + problem["expected"] + " | found " + problem["found"])
        shown = shown + 1


main()
