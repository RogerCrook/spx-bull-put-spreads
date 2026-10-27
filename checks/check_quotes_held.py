"""
CHECK: suspicious quotes of the option legs actually held (review_log C14, part A)
(reproduction inventory, row 25: the claim that quotes widen around 10:00 and 14:00)

What this file is for:
    On 7 April 2025 at 10:30 a put was quoted 19.4 / 551.7 while it was worth
    about 71. Stage 2 turned that mid into an implied volatility of 80% and a
    delta of 0.21, which forced a false exit in an experiment run. This file
    looks for anything like that in the four reported runs, in both
    directions (a quote too high gives a fake loss, too low a fake gain).

    For every snapshot at which a leg of a reported trade is held, two tests:
      width:  (ask - bid) / mid, the bid-ask spread as a share of the price.
              A normal quote is a few per cent wide; the broken one was 186%.
      spike:  the leg's implied volatility jumps at one snapshot and comes back
              at the next (45% -> 80% -> 47% on 7 April 2025). The volatility
              is tested, not the price, because the price moves with the index
              anyway, while the volatility of one contract changes slowly.
              The test looks at the NEXT snapshot, so it is a diagnosis only,
              never a trading rule (that would use the future).
    A flagged quote matters most at a decision (the entry or exit of a trade).

    The runs read are the four "_c8c9" runs, made BEFORE the broken-quote rule
    (def:broken) existed: this check is how the broken quotes were found.

    Control: the run "ks125_kl230_mid" of a deleted experiment contains the
    known broken quote of 7 April 2025; the test must flag it.

    sec:broken-quotes cites the printout at the end: the flagged quotes by time
    of day, where 10:00 (data releases) and 14:00 (Federal Reserve
    announcements) stand out.

    Rewritten 2026-10-27 in the style of Code/s03_rates.py; same calculations
    and the same printout as before, except at the end: the full list of flags
    is no longer written to a temporary file, and the flags are counted by time
    of day instead (old version in old_versions/checks_before_style_2026-10-27/).

Data: results/trades_*_c8c9.csv, checks/data/trades_ks125_kl230_mid_c8c9.csv, and the
      puts of all of Data/04_greeks/ (read month by month).
Read-only: writes nothing. Takes about 15 to 20 minutes.
Run it from the main folder:   python checks/check_quotes_held.py
"""

import os                                    # for listing the files in a folder
import numpy as np                           # numpy does maths on lists of numbers
import pandas as pd                          # pandas works with tables


RUN_FILES = {
    "base_mid": "results/trades_base_mid_c8c9.csv",
    "base_cross": "results/trades_base_cross_c8c9.csv",
    "p15_mid": "results/trades_p15_mid_c8c9.csv",
    "p15_cross": "results/trades_p15_cross_c8c9.csv",
    # the control run's trades, kept in checks/data/ when the experiment was deleted (2026-10-26)
    "CONTROL_ks125_kl230_mid": "checks/data/trades_ks125_kl230_mid_c8c9.csv",
}

WIDE = 1.0                                   # flag a quote whose spread is wider than its mid
SPIKE = 0.05                                 # flag a vol jump of more than 5 vol points ...
COMES_BACK = 0.5                             # ... that comes back: before and after differ by less than half the jump


# ---- 1. the legs held: one row per (run, trade, leg) -----------------------------------

legs = []
for run in RUN_FILES:
    trades = pd.read_csv(RUN_FILES[run])
    for i in range(len(trades)):
        trade = trades.iloc[i]               # .iloc[i]: the i-th row
        for leg, strike in (("short", trade["strike_short"]), ("long", trade["strike_long"])):
            legs.append({"run": run, "trade": i, "leg": leg, "root": trade["root"],
                         "expiration": trade["expiration"], "strike": strike,
                         "entry": trade["entry_time"], "exit": trade["exit_time"]})
legs = pd.DataFrame(legs)
print("legs held:", len(legs))

# each contract once, with the first entry and the last exit over all runs
contracts = {}                               # (root, expiration, strike) -> [first entry, last exit]
for i in range(len(legs)):
    leg = legs.iloc[i]
    key = (leg["root"], leg["expiration"], leg["strike"])
    if key not in contracts:
        contracts[key] = [leg["entry"], leg["exit"]]
    else:
        contracts[key][0] = min(contracts[key][0], leg["entry"])     # times as text compare in time order
        contracts[key][1] = max(contracts[key][1], leg["exit"])

# as a table, with a window from 3 days before the first entry (so that the
# entry snapshot has a snapshot before it) to the end of the day of the last exit
rows = []
for key in contracts:
    first_entry, last_exit = contracts[key]
    start = (pd.Timestamp(first_entry) - pd.Timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    end = last_exit[:10] + " 23:59:59"
    rows.append({"root": key[0], "expiration": key[1], "strike": key[2], "start": start, "end": end})
contracts = pd.DataFrame(rows)
print("different contracts:", len(contracts))


# ---- 2. read their quotes, month by month ---------------------------------------------

COLUMNS = ["quote_datetime", "root", "expiration", "strike", "option_type",
           "bid", "ask", "mid", "iv", "delta"]

# the months of the Greeks folder: "spx_2021-06.csv" -> "2021-06"
months = sorted(f[4:11] for f in os.listdir("Data/04_greeks") if f.startswith("spx_") and f.endswith(".csv"))

pieces = []
for month in months:

    greeks = pd.read_csv("Data/04_greeks/spx_" + month + ".csv", usecols=COLUMNS)
    greeks = greeks[greeks["option_type"] == "P"]            # puts only

    # the stock-close snapshot of each day (16:00, or 13:00 on early-close days,
    # as end_of_day_times in Code/s11_backtest.py): no decision is taken there (C9)
    last_time = {}                           # date -> time of its last snapshot
    for when in sorted(greeks["quote_datetime"].unique()):
        last_time[when[:10]] = when[11:]
    close_snapshots = set()
    for date in last_time:
        if last_time[date] == "13:15:00":    # early close
            close_snapshots.add(date + " 13:00:00")
        else:
            close_snapshots.add(date + " 16:00:00")

    # keep only the held contracts: merge with how="inner" keeps the rows whose
    # (root, expiration, strike) is in both tables, and adds their start and end
    held = greeks.merge(contracts, on=["root", "expiration", "strike"], how="inner")
    in_window = (held["quote_datetime"] >= held["start"]) & (held["quote_datetime"] <= held["end"])
    held = held[in_window]
    held = held[~held["quote_datetime"].isin(close_snapshots)]      # ~ means "not": drop the stock close
    pieces.append(held)
    print(month, "rows kept:", len(held))

quotes = pd.concat(pieces)
quotes = quotes.sort_values(["root", "expiration", "strike", "quote_datetime"])
quotes = quotes.drop_duplicates(["root", "expiration", "strike", "quote_datetime"])
# reset_index(drop=True) numbers the rows 0, 1, 2, ... again: after concat the
# monthly pieces each started at 0, and step 3 needs every row label to be unique
quotes = quotes.reset_index(drop=True)
print("quotes of held contracts:", len(quotes))


# ---- 3. the two tests, contract by contract --------------------------------------------

quotes["width"] = (quotes["ask"] - quotes["bid"]) / quotes["mid"]
quotes["spike"] = False
quotes["iv_before"] = np.nan
quotes["iv_after"] = np.nan

# groupby gives each contract with its quotes in time order; each quote is
# compared with the one before and the one after
for key, one in quotes.groupby(["root", "expiration", "strike"]):
    iv = one["iv"].values                    # .values: the plain numbers
    for j in range(1, len(iv) - 1):
        if np.isnan(iv[j - 1]) or np.isnan(iv[j]) or np.isnan(iv[j + 1]):
            continue                         # a missing volatility: nothing to test
        up = iv[j] - iv[j - 1]               # jump from the snapshot before
        down = iv[j] - iv[j + 1]             # jump back to the snapshot after
        same_direction = up * down > 0       # it went out and came back
        big = min(abs(up), abs(down)) > SPIKE
        back = abs(iv[j + 1] - iv[j - 1]) < COMES_BACK * min(abs(up), abs(down))
        if same_direction and big and back:
            row_label = one.index[j]         # this quote's row label in the big table
            quotes.loc[row_label, "spike"] = True
            quotes.loc[row_label, "iv_before"] = iv[j - 1]
            quotes.loc[row_label, "iv_after"] = iv[j + 1]


# ---- 4. the snapshots at which each leg was held ---------------------------------------

held_rows = legs.merge(quotes, on=["root", "expiration", "strike"], how="inner")
while_held = (held_rows["quote_datetime"] >= held_rows["entry"]) & (held_rows["quote_datetime"] <= held_rows["exit"])
held_rows = held_rows[while_held].copy()     # .copy(): our own table, safe to add columns
held_rows["decision"] = ((held_rows["quote_datetime"] == held_rows["entry"])
                         | (held_rows["quote_datetime"] == held_rows["exit"]))     # | means "or"
held_rows["wide"] = held_rows["width"] > WIDE
held_rows["flagged"] = held_rows["wide"] | held_rows["spike"]

pd.set_option("display.width", 250)          # print wide tables on one line
print("\nper run and leg: held snapshots, width median / 99th pct, share > 0.5, wide (> %.1f), spikes" % WIDE)
for run in RUN_FILES:
    for leg in ("short", "long"):
        part = held_rows[(held_rows["run"] == run) & (held_rows["leg"] == leg)]
        print("%-25s %-5s %7d  %.3f / %.3f  %.4f%%  wide %4d  spikes %4d" % (
            run, leg, len(part), part["width"].median(), part["width"].quantile(0.99),
            100 * (part["width"] > 0.5).mean(), part["wide"].sum(), part["spike"].sum()))

show = ["run", "trade", "leg", "strike", "expiration", "quote_datetime", "entry", "exit",
        "bid", "ask", "mid", "width", "iv_before", "iv", "iv_after", "delta", "spike"]

print("\nflagged quotes AT A DECISION (entry or exit of the trade holding them):")
at_decision = held_rows[held_rows["flagged"] & held_rows["decision"]]
if len(at_decision) > 0:
    print(at_decision[show].to_string(index=False))
else:
    print("none")

print("\nflagged quotes while held, not at a decision (largest vol jumps first, at most 40):")
others = held_rows[held_rows["flagged"] & ~held_rows["decision"]].copy()
others["jump"] = (others["iv"] - others["iv_before"]).abs()
print(len(others), "in total")
print(others.sort_values("jump", ascending=False)[show].head(40).to_string(index=False))


# ---- 5. the flags by time of day (cited in sec:broken-quotes) --------------------------

# the four reported runs only, without the control run; each flagged quote of
# a contract counted once, even if several runs held it
flagged = held_rows[held_rows["flagged"] & (held_rows["run"] != "CONTROL_ks125_kl230_mid")]
flagged = flagged.drop_duplicates(["root", "expiration", "strike", "quote_datetime"])

clock = flagged["quote_datetime"].str[11:16]                 # the time of day, e.g. "10:00"
print("\nflagged quotes of the four reported runs (each quote once): %d" % len(flagged))
print("by time of day:")
# value_counts counts the flags per time; sort_index puts the times in order
counts = clock.value_counts().sort_index()
for time in counts.index:
    print("   %s  %4d" % (time, counts[time]))
