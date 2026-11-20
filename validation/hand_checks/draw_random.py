"""
THE RANDOM SNAPSHOTS AND THE WORK LIST OF THE HAND CHECKS

What this file is for:
    The hand checks (method 7 of the validation) look at 32 snapshots.
    22 were chosen by rule branch from the backtest's logs, by
    select_snapshots.sh, and are in key_branches.csv.

    This file adds the other 10, drawn at random. They are drawn from the
    snapshot times in the DATA (Data/05_atm_vol.csv), not from the backtest's
    logs, so that a snapshot the backtest wrongly left out could still be drawn.

    It also:
      - checks that the data's snapshot times and the backtest's held
        snapshots are the same list (they should be: a position is always open),
      - picks 4 of the 32 for the deep check from the raw data (Part B),
        one in each period 2012-14, 2015-19, 2020, 2021-26,
      - shuffles the 32 and numbers them H01 to H32.

    It only reads. It writes two files next to itself:
      key.csv  : the ANSWER KEY (why each snapshot was chosen, what the
                 backtest did there). Arian does not open it before his
                 hand checks.
      list.csv : the work list for Arian: H number, run, snapshot, deep check.

To run it (from the main folder, takes about a minute):
    python validation/hand_checks/draw_random.py
"""

import random                       # Python's own random numbers (no numpy needed)
import pandas as pd                 # pandas works with tables


# ---- settings ----------------------------------------------------------------

SEED = 20261116                     # fixed seed: running again gives the same draw
HOW_MANY_RANDOM = 10                # how many random snapshots

FOLDER = "validation/hand_checks"                   # where this file and its outputs are
BRANCH_KEY_FILE = FOLDER + "/key_branches.csv"      # the 22 chosen by rule branch
KEY_FILE = FOLDER + "/key.csv"                      # output: the answer key
LIST_FILE = FOLDER + "/list.csv"                    # output: Arian's work list

ATM_FILE = "Data/05_atm_vol.csv"                    # the data's snapshot times are read from here
QUOTES_LOG = "results/quotes_base_mid.csv"          # the backtest's held snapshots (base case, mid)
MISSING_LOG = "results/missing_base_mid.csv"        # held snapshots where a leg was missing

# the four periods for the deep checks: (name, first year, last year)
PERIODS = [
    ("2012-14", 2012, 2014),
    ("2015-19", 2015, 2019),
    ("2020", 2020, 2020),
    ("2021-26", 2021, 2026),
]


# ---- step 1: the snapshot times in the data -----------------------------------

def data_snapshot_times():
    """
    All snapshot times in the data at which the backtest may take a decision,
    i.e. every snapshot except the stock close (16:00, or 13:00 on a day whose
    last snapshot is 13:15). Returns a sorted list of text like "2021-06-08 10:00:00".
    """

    print("reading the snapshot times of", ATM_FILE, "...")

    # usecols: read only this one column, which is much faster than the whole file
    atm = pd.read_csv(ATM_FILE, usecols=["quote_datetime"])

    # .unique() lists each time once (the file has one row per expiry and time).
    # sorted() puts them in time order; text "YYYY-MM-DD HH:MM:SS" sorts like time.
    all_times = sorted(atm["quote_datetime"].unique())

    # the last snapshot of each day. The list is sorted, so the last time we
    # see for a date is that day's last snapshot.
    last_time_of_day = {}                           # date -> "16:15:00" or "13:15:00"
    for when in all_times:
        date = when[:10]                            # the first 10 characters: "2021-06-08"
        last_time_of_day[date] = when[11:]          # the characters after the space: "16:15:00"

    # keep every time that is not the stock close of its day
    times = []
    for when in all_times:
        date = when[:10]
        time_of_day = when[11:]

        if last_time_of_day[date] == "13:15:00":    # an early-close day
            close_time = "13:00:00"
        else:                                       # a normal day
            close_time = "16:00:00"

        if time_of_day != close_time:               # not the stock close: keep it
            times.append(when)

    print("  snapshots in the data:", len(all_times), "| without the stock close:", len(times))
    return times


# ---- step 2: the same list from the backtest's logs, and the comparison --------

def backtest_actions():
    """
    What the backtest did at each snapshot of the base case at mid, from its logs.
    Returns a dictionary: time -> "held", "loss", "profit", "gamma",
    "skipped (broken)" or "leg missing".
    """

    quotes = pd.read_csv(QUOTES_LOG)

    actions = {}
    # iterrows() goes through the table one row at a time;
    # each row comes as (row number, row). The "_" means we ignore the number.
    for _, row in quotes.iterrows():

        # one row per leg: use the short leg's row of a HELD position only
        if row["kind"] != "held" or row["leg"] != "short":
            continue

        action = row["action"]
        if pd.isna(action):                         # an empty cell: nothing happened
            action = "held"
        actions[row["time"]] = action

    missing = pd.read_csv(MISSING_LOG)
    for _, row in missing.iterrows():
        actions[row["when"]] = "leg missing"

    return actions


def compare_lists(data_times, actions):
    """
    Print how the data's snapshot times and the backtest's held snapshots differ.
    Before the first entry nothing is held, so the very first snapshot is
    expected in the data only.
    """

    data_set = set(data_times)                      # a set makes "is it in there?" fast
    log_set = set(actions.keys())

    only_in_data = sorted(data_set - log_set)       # "-" on sets: in the first, not the second
    only_in_log = sorted(log_set - data_set)

    print("  held snapshots in the backtest's log:", len(log_set))
    print("  in the data but not in the log:", len(only_in_data), only_in_data[:5])
    print("  in the log but not in the data:", len(only_in_log), only_in_log[:5])


# ---- step 3: draw the random snapshots -----------------------------------------

def draw_random(data_times, branch_times, actions, generator):
    """
    Draw HOW_MANY_RANDOM snapshots from the data's times, leaving out the ones
    already chosen by branch. Returns a list of key rows (dictionaries).
    """

    candidates = []
    for when in data_times:
        if when not in branch_times:
            candidates.append(when)

    # sample() draws without putting back, so no snapshot comes twice
    drawn = generator.sample(candidates, HOW_MANY_RANDOM)
    drawn = sorted(drawn)                           # in time order, for the key

    rows = []
    number = 0
    for when in drawn:
        number = number + 1

        if when in actions:
            what = "action: " + actions[when]
        else:
            what = "not in the backtest's log"

        rows.append({
            "key_id": "R" + str(number).zfill(2),   # zfill(2): "1" -> "01"
            "branch": "random snapshot from the data",
            "run": "base_mid",
            "snapshot": when,
            "what the backtest did": what + " (drawn from " + str(len(candidates)) + " snapshots)",
        })

    return rows


# ---- step 4: the deep checks ------------------------------------------------------

def pick_deep_checks(key_rows, generator):
    """
    Pick one snapshot in each period for the deep check from the raw data.
    The equity day (snapshot ending in "(day)") has no single snapshot, so it is
    left out. Returns the set of key ids picked.
    """

    picked = set()

    for period in PERIODS:

        # each period is a group of three, e.g. ("2015-19", 2015, 2019);
        # [0], [1], [2] take its first, second and third part
        name = period[0]
        first_year = period[1]
        last_year = period[2]

        candidates = []
        for row in key_rows:
            if row["snapshot"].endswith("(day)"):   # the equity day: no single snapshot
                continue
            year = int(row["snapshot"][:4])         # the first 4 characters: "2020"
            if year >= first_year and year <= last_year:
                candidates.append(row["key_id"])

        candidates = sorted(candidates)             # a fixed order, so the draw repeats
        choice = generator.choice(candidates)       # one at random
        picked.add(choice)
        print("  deep check", name, ":", choice, "of", len(candidates))

    return picked


# ---- main ---------------------------------------------------------------------------

def main():

    generator = random.Random(SEED)                 # our own random generator with the fixed seed

    # the 22 chosen by branch
    branch_table = pd.read_csv(BRANCH_KEY_FILE)

    key_rows = []
    branch_times = set()
    for _, row in branch_table.iterrows():
        key_rows.append({
            "key_id": row["id"],
            "branch": row["branch"],
            "run": row["run"],
            "snapshot": row["snapshot"],
            "what the backtest did": row["what the backtest did"],
        })
        branch_times.add(row["snapshot"])

    # the data's times, compared with the backtest's log
    data_times = data_snapshot_times()
    actions = backtest_actions()
    compare_lists(data_times, actions)

    # the 10 random ones
    random_rows = draw_random(data_times, branch_times, actions, generator)
    for row in random_rows:
        key_rows.append(row)

    # the 4 deep checks
    deep = pick_deep_checks(key_rows, generator)

    # shuffle, so that the H number gives nothing away. shuffle() changes the
    # list in place (it returns nothing).
    generator.shuffle(key_rows)

    number = 0
    for row in key_rows:
        number = number + 1
        row["hand_check"] = "H" + str(number).zfill(2)
        if row["key_id"] in deep:
            row["deep"] = "yes"
        else:
            row["deep"] = "no"

    # the answer key: all columns
    key = pd.DataFrame(key_rows)                    # a list of dictionaries -> a table
    # table[[list of names]] (two brackets) keeps these columns, in this order
    key = key[["hand_check", "key_id", "branch", "run", "snapshot", "deep", "what the backtest did"]]
    key.to_csv(KEY_FILE, index=False)               # index=False: no pandas row numbers in the file

    # Arian's work list: no key id, no branch, no answer
    work_list = key[["hand_check", "run", "snapshot", "deep"]]
    work_list.to_csv(LIST_FILE, index=False)

    print("written:", KEY_FILE, "and", LIST_FILE, "with", len(key), "snapshots")


# Only run main() when this file is started directly
# (python validation/hand_checks/draw_random.py), not when another file imports it.
if __name__ == "__main__":
    main()
