"""
CHECK: how many expiries were listed on the first and the last day the thesis names
(reproduction inventory, row 13)

What this file is for:
    sec:data says the expiry grid became much denser, from 8 expiry dates
    between 4 and 100 days away on 28 September 2012 to 30 on 28 July 2026.
    (Until 2026-10-27 it said "8 ... to 60", from the methodology report, whose
    60 counted SPX and SPXW separately.) This file counts the expiries straight
    from the raw Cboe files of those two days.

    "Listed" can mean two things, so both are printed:
      - every expiry date quoted that day (also LEAPS years away), and
      - only the expiries 4 to 100 days away, the range that stage 1 keeps.
    Only the vanilla roots SPX, SPXW and SPXQ count (stage 1 drops the rest).

Data: Data/01_raw_options/, the two daily files (about 50 and 95 MB).
Read-only: writes nothing. Takes a few seconds.
Run it from the main folder:   python checks/check_expiry_count.py
"""

import pandas as pd                          # pandas works with tables


FOLDER = "Data/01_raw_options"               # the raw Cboe files, one per day
DAYS = ["2012-09-28", "2026-07-28"]          # the two days the thesis names
ROOTS = ["SPX", "SPXW", "SPXQ"]              # the vanilla roots stage 1 keeps


for day in DAYS:                             # do the same for each of the two days

    # the file name of that day, e.g. ".../UnderlyingOptionsIntervals_900sec_2012-09-28.csv"
    path = FOLDER + "/UnderlyingOptionsIntervals_900sec_" + day + ".csv"

    # read only the two columns we need (usecols), which is much faster
    table = pd.read_csv(path, usecols=["root", "expiration"])

    trade_day = pd.Timestamp(day)            # the day as a real date, so we can subtract dates

    all_expiries = set()                     # every expiry date seen (a set keeps each value once)
    near_expiries = set()                    # only those 4 to 100 days away
    by_root = {}                             # root -> set of its expiry dates

    for root in ROOTS:                       # start an empty set for each root
        by_root[root] = set()

    # drop_duplicates keeps each (root, expiration) pair once, so the loop
    # below runs over a few hundred pairs instead of hundreds of thousands of rows
    pairs = table.drop_duplicates()

    # iterrows goes through the table one row at a time;
    # each step gives the row label (not needed, so "_") and the row itself
    for _, row in pairs.iterrows():

        root = row["root"]                   # e.g. "SPXW"

        if root not in ROOTS:                # skip binary and other non-vanilla roots
            continue

        expiry = row["expiration"]           # the expiry date, as text like "2012-10-19"

        days_left = (pd.Timestamp(expiry) - trade_day).days     # calendar days to expiry

        all_expiries.add(expiry)             # count it among all expiries
        by_root[root].add(expiry)            # and under its root

        if 4 <= days_left <= 100:            # the range stage 1 keeps
            near_expiries.add(expiry)

    print(day)
    print("   all expiry dates (SPX, SPXW, SPXQ together):  ", len(all_expiries))
    print("   expiry dates 4 to 100 days away:              ", len(near_expiries))
    for root in ROOTS:
        print("   %-5s %d expiry dates" % (root, len(by_root[root])))
    print()
