"""
CHECK: why a leg of the held position was missing (review_log.md C15, T26)

What this file is for:
    At every snapshot the backtest looks up both legs of the position it holds
    (the sold and the bought put: same root, expiry and strike) in the Greeks
    files. If a leg has no row there, or a row without a delta, the exits are
    not tested at that snapshot (sec:backtest-design). Since 2026-10-27 the
    backtest writes down every such snapshot (the file missing_<run>.csv).
    This file finds out, for each missing leg, at which step it was lost:

      not recorded     the raw Cboe file has no quote for it at that snapshot
      bid below 0.025  stage 1 drops it: nobody bids for the option
      crossed quote    stage 1 drops it: the ask is not above the bid
      strike window    stage 1 drops it: K/S outside the put window
      no forward       stage 2 drops it: no forward for its expiry at that snapshot
      no implied vol   it is in the Greeks file, but without an implied
                       volatility (so no delta), e.g. a price below intrinsic value

    It follows the leg through the data in the opposite order: Greeks file,
    then cleaned file, then raw file, and applies the stage-1 filters to the
    raw quote with the settings of Code/s01_stage1_extract_simple.py.

Data: results/missing_<run>.csv (the run is chosen below), Data/04_greeks/,
      Data/02_clean/, Data/01_raw_options/ (only the days and months that occur),
      Data/07_index_close/GSPC_daily.csv.
Read-only: writes nothing. Takes a few minutes (it reads one Greeks month and
one cleaned month for every month with a missing leg).
Run it from the main folder:   python checks/check_missing_legs.py
"""

import os
import pandas as pd                          # pandas works with tables


RUN = "base_mid_c8c9q_c15"                   # the run whose missing legs we look at
MISSING_FILE = "results/missing_" + RUN + ".csv"
RAW_FOLDER = "Data/01_raw_options"

# the stage-1 settings, copied from Code/s01_stage1_extract_simple.py
PUT_LOW = 0.30
PUT_HIGH = 1.08
MIN_BID = 0.025


# ---- 1. the missing legs, one row per leg -------------------------------------------

missing = pd.read_csv(MISSING_FILE)
print("held snapshots with a leg missing:", len(missing), "(run " + RUN + ")")

legs = []                                    # one dictionary per missing leg
for _, row in missing.iterrows():            # iterrows(): one row at a time
    # the column short_missing is read as text "True"/"False" or as True/False;
    # str(...) == "True" works for both
    if str(row["short_missing"]) == "True":
        legs.append({"when": row["when"], "root": row["root"], "expiration": row["expiration"],
                     "strike": row["strike_short"], "leg": "sold"})
    if str(row["long_missing"]) == "True":
        legs.append({"when": row["when"], "root": row["root"], "expiration": row["expiration"],
                     "strike": row["strike_long"], "leg": "bought"})
print("missing legs:", len(legs))
print()


# ---- 2. the official close, the raw files ---------------------------------------------

close_table = pd.read_csv("Data/07_index_close/GSPC_daily.csv")
closes = {}
for _, row in close_table.iterrows():
    closes[str(row["Date"])[:10]] = float(row["Close"])

raw_files = {}                               # date -> raw file
for name in os.listdir(RAW_FOLDER):
    if name.endswith(".csv"):
        raw_files[name[-14:-4]] = RAW_FOLDER + "/" + name


def find_rows(table, leg):
    """The rows of one table for this leg's contract at this leg's snapshot."""
    same = (table["quote_datetime"] == leg["when"]) & (table["root"] == leg["root"]) \
        & (table["expiration"] == leg["expiration"]) & (table["strike"] == leg["strike"]) \
        & (table["option_type"] == "P")
    return table[same]


# ---- 3. follow each leg back through the data -------------------------------------

# group the legs by month, so each month's files are read only once
months = {}
for leg in legs:
    month = leg["when"][:7]                  # "2022-11"
    if month not in months:
        months[month] = []
    months[month].append(leg)

columns = ["quote_datetime", "root", "expiration", "strike", "option_type"]

for month in sorted(months):

    # the Greeks and cleaned rows of this month for the strikes we need only
    strikes = set(leg["strike"] for leg in months[month])
    pieces_g = []
    for chunk in pd.read_csv("Data/04_greeks/spx_" + month + ".csv",
                             usecols=columns + ["iv", "delta"], chunksize=1000000):
        pieces_g.append(chunk[chunk["strike"].isin(strikes)])     # isin: True where the strike is one we need
    greeks = pd.concat(pieces_g)
    pieces_c = []
    for chunk in pd.read_csv("Data/02_clean/spx_" + month + ".csv",
                             usecols=columns, chunksize=1000000):
        pieces_c.append(chunk[chunk["strike"].isin(strikes)])
    clean = pd.concat(pieces_c)

    for leg in months[month]:

        rows = find_rows(greeks, leg)
        if len(rows) > 0:
            if pd.isna(rows["delta"].iloc[0]):          # in the file, but no delta
                leg["cause"] = "no implied vol"
            else:
                leg["cause"] = "present (?)"            # should not happen
            continue

        if len(find_rows(clean, leg)) > 0:              # stage 1 kept it, stage 2 dropped it
            leg["cause"] = "no forward"
            continue

        # not in the cleaned data: look at the raw quote
        date = leg["when"][:10]
        raw = pd.read_csv(raw_files[date],
                          usecols=columns + ["bid", "ask", "underlying_bid", "underlying_ask"])
        rows = find_rows(raw, leg)
        if len(rows) == 0:
            leg["cause"] = "not recorded"
            continue
        quote = rows.iloc[0]                            # the first (and only) matching row
        # S as stage 1 uses it: the official close at the last snapshot, else the quote
        last_time = raw["quote_datetime"].max()[11:]
        spot = (quote["underlying_bid"] + quote["underlying_ask"]) / 2
        if leg["when"][11:] == last_time and last_time in ("16:15:00", "13:15:00"):
            spot = closes[date]
        k_over_s = leg["strike"] / spot
        leg["k_over_s"] = round(k_over_s, 4)
        leg["bid"] = quote["bid"]
        leg["ask"] = quote["ask"]
        if quote["bid"] < MIN_BID:
            leg["cause"] = "bid below 0.025"
        elif not quote["ask"] > quote["bid"]:
            leg["cause"] = "crossed quote"
        elif k_over_s < PUT_LOW or k_over_s > PUT_HIGH:
            leg["cause"] = "strike window"
        else:
            leg["cause"] = "passes stage 1 (?)"         # should not happen


# ---- 4. print ------------------------------------------------------------------------

table = pd.DataFrame(legs)
print(table.to_string(index=False))
print()
# value_counts(): how many legs per cause
print("by cause:", table["cause"].value_counts().to_dict())
print("by time of day:", table["when"].str[11:16].value_counts().sort_index().to_dict())
print("by leg:", table["leg"].value_counts().to_dict())
