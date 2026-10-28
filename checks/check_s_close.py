"""
CHECK: how far the quoted index level is from the official close
(reproduction inventory, row 12; review_log C8)

What this file is for:
    sec:data says the index level S is the midpoint of the index bid and ask
    in the option data, and that at the last snapshot of the day (16:15, or
    13:15 on early-close days), after the stocks have stopped trading, this
    midpoint is no longer a price: it differs from the official close by more
    than 1% on 118 of the 3,675 days, up to 31.5%, and on 16 March 2020 it was
    2,583 against a close of 2,386. At the stock-close snapshot (16:00, or
    13:00) it differs by a median of 0.009% and at most 0.35%.

    This file compares, day by day, the quoted midpoint at those two
    snapshots with the official daily close.

    Rewritten 2026-10-27 in the style of Code/s03_rates.py; same calculations
    and the same printout as before (old version in
    old_versions/checks_before_style_2026-10-27/).

    Since 2026-10-27 (review_log.md C15) stage 1 itself uses the official close
    as S at the last snapshot, and keeps the recorded quote in its own column,
    spot_quote. This file reads spot_quote, so it still compares the recorded
    quote (before, it read spot, which was the recorded quote then).

Data: Data/05_atm_vol.csv (the recorded index quote at every snapshot, column
      spot_quote) and Data/07_index_close/GSPC_daily.csv (the official close,
      from checks/fetch_gspc.py).
Read-only: writes nothing. Takes about half a minute.
Run it from the main folder:   python checks/check_s_close.py
"""

import pandas as pd                          # pandas works with tables


# ---- 1. the quoted spot, one value per snapshot -----------------------------------

atm = pd.read_csv("Data/05_atm_vol.csv", usecols=["quote_datetime", "spot_quote"])

# from here on the recorded quote is called "spot", as in the rest of this file
atm = atm.rename(columns={"spot_quote": "spot"})

# every slice of one snapshot carries the same spot; groupby puts the slices of
# each snapshot together and .median() keeps one value; reset_index turns the
# snapshot labels back into an ordinary column
spot = atm.groupby("quote_datetime")["spot"].median().reset_index()

spot["date"] = spot["quote_datetime"].str[:10]       # "2020-03-16 16:15:00" -> "2020-03-16"
spot["time"] = spot["quote_datetime"].str[11:16]     # -> "16:15"


# ---- 2. the official close ----------------------------------------------------------

close = pd.read_csv("Data/07_index_close/GSPC_daily.csv", usecols=["Date", "Close"])
close = close.rename(columns={"Date": "date"})       # same column name as in the spot table


# ---- 3. day by day: the spot at the last snapshot and at the stock close -------------

rows = []                                    # one entry per day

# groupby gives each date with the snapshots of that day
for date, day in spot.groupby("date"):

    times = sorted(day["time"])              # the snapshot times of the day, in order
    last = times[-1]                         # the last one: "16:15", or "13:15" on an early close

    if last == "13:15":                      # early close: the stocks stop at 13:00
        stock_close = "13:00"
    else:
        stock_close = "16:00"

    # day["time"] == last gives True/False per snapshot; .loc[..., "spot"] picks
    # the spot of the True row, and .iloc[0] takes that single value
    spot_last = day.loc[day["time"] == last, "spot"].iloc[0]

    if stock_close in times:
        spot_at_close = day.loc[day["time"] == stock_close, "spot"].iloc[0]
    else:
        spot_at_close = None                 # the day has no stock-close snapshot

    rows.append({"date": date, "last": last, "S_last": spot_last, "S_close_snap": spot_at_close})

# merge adds the official close of each date (like VLOOKUP in Excel)
days = pd.DataFrame(rows).merge(close, on="date")

# the difference in per cent: quoted / official - 1
days["err_last"] = 100 * (days["S_last"] / days["Close"] - 1)
days["err_close_snap"] = 100 * (days["S_close_snap"] / days["Close"] - 1)


# ---- 4. print ------------------------------------------------------------------------

# value_counts counts how many days end at each last snapshot time
print("days:", len(days), " last snapshot:", days["last"].value_counts().to_dict())

gap = days["err_last"].abs()                 # .abs(): above or below, without the sign
# gap.idxmax(): the row label of the largest gap; .loc reads that row's date
print("last snapshot |S/close-1| %%: median %.3f, 90%% %.3f, >0.5%%: %d, >1%%: %d, >3%%: %d, max %.1f on %s"
      % (gap.median(), gap.quantile(0.9), (gap > 0.5).sum(), (gap > 1).sum(), (gap > 3).sum(),
         gap.max(), days.loc[gap.idxmax(), "date"]))

# the days off by more than 1%, counted by year ("2020-03-16" -> "2020")
print("days > 1% by year:", days.loc[gap > 1, "date"].str[:4].value_counts().sort_index().to_dict())

print("2020-03-16:", days.loc[days["date"] == "2020-03-16", ["S_last", "Close", "err_last"]].to_dict("records"))

gap_close = days["err_close_snap"].abs()
# .notna().sum(): the number of days that have a stock-close snapshot
print("stock-close snapshot |S/close-1| %%: n %d, median %.3f, 99%% %.3f, max %.3f"
      % (gap_close.notna().sum(), gap_close.median(), gap_close.quantile(0.99), gap_close.max()))
