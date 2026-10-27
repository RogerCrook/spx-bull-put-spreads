"""
RUNNING THE STRATEGY VARIANTS

What this file is for:
    backtest.py keeps the base-case settings at its top. To run a variant
    (e.g. a 45-day base maturity) we do NOT edit backtest.py; instead this file
    imports it, changes the settings for one run, and starts it. Every run
    writes its own files, named after the variant, so nothing is overwritten.

    The variants were fixed on 2026-10-08, after the cost result and BEFORE any
    of them was run (see backtest_design.md). They must not be tuned afterwards.

HOW TO RUN IT
    python run_variants.py base_cross              one run
    python run_variants.py p15_mid p15_cross       several runs, one after the other
"""

import sys

import backtest                            # the backtest itself (runs nothing on import)


# Every variant: its name and the settings it changes. Settings not listed keep
# the base-case value from the top of backtest.py.
VARIANTS = {
    # the base case, at mid and crossing the spread
    "base_mid":   {"EXECUTION": "mid"},
    "base_cross": {"EXECUTION": "cross"},

    # fewer round trips: profit exit at delta0 - 0.15 instead of - 0.10
    "p15_mid":    {"EXECUTION": "mid",   "BAND_PROFIT": 0.15},
    "p15_cross":  {"EXECUTION": "cross", "BAND_PROFIT": 0.15},

    # fewer round trips: no profit exit at all (hold until loss or gamma exit)
    "p0_mid":     {"EXECUTION": "mid",   "BAND_PROFIT": None},
    "p0_cross":   {"EXECUTION": "cross", "BAND_PROFIT": None},

    # longer base maturity: 45 days instead of 30 (the 90-day cap stays)
    "t45_mid":    {"EXECUTION": "mid",   "TARGET_DAYS": 45},
    "t45_cross":  {"EXECUTION": "cross", "TARGET_DAYS": 45},

    # longer base maturity: 60 days instead of 30
    "t60_mid":    {"EXECUTION": "mid",   "TARGET_DAYS": 60},
    "t60_cross":  {"EXECUTION": "cross", "TARGET_DAYS": 60},
}


def run_one(name):
    """Change backtest.py's settings for this variant and run it."""

    settings = VARIANTS[name]

    # setattr(backtest, "EXECUTION", "cross") does the same as writing
    # EXECUTION = "cross" at the top of backtest.py, but only for this run
    for setting_name in settings:
        setattr(backtest, setting_name, settings[setting_name])

    # runs with the end-of-day fix (review_log.md C8, C9) get "_c8c9" in their
    # names, as in backtest.py, so they never overwrite results made without it
    tag = ""
    if backtest.SKIP_CLOSE_SNAPSHOT or backtest.USE_OFFICIAL_CLOSE:
        tag = "_c8c9"

    # the output files carry the variant's name, e.g. "trades_t45_cross_c8c9.csv"
    backtest.TRADES_FILE = "trades_" + name + tag + ".csv"
    backtest.EQUITY_FILE = "equity_" + name + tag + ".csv"
    backtest.QUARTERS_FILE = "quarters_" + name + tag + ".csv"

    print("=" * 70)
    print("VARIANT", name, settings)
    print("=" * 70)

    backtest.main()


def main():

    # sys.argv is the list of words typed after "python": sys.argv[0] is the
    # file name itself, the rest ([1:]) are the variant names
    names = sys.argv[1:]

    if len(names) == 0:
        print("Name at least one variant:", list(VARIANTS.keys()))
        return

    for name in names:

        if name not in VARIANTS:
            print("unknown variant:", name)
            continue

        # each run starts from a fresh copy of backtest.py's base settings,
        # so one variant's changes cannot leak into the next run.
        # importlib.reload reads backtest.py again from the file.
        import importlib
        importlib.reload(backtest)

        run_one(name)


main()
