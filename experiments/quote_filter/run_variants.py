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
# EXPERIMENT COPY (experiments/quote_filter, review_log.md C14): only the four
# thesis runs, with the broken-quote test only measured ("count"; the trades
# must equal the thesis runs). The "on" runs (added 2026-10-25, after the
# limits in backtest.py were fixed) skip broken quotes.
VARIANTS = {
    "base_mid_count":   {"EXECUTION": "mid",   "QUOTE_RULE": "count"},
    "base_cross_count": {"EXECUTION": "cross", "QUOTE_RULE": "count"},
    "p15_mid_count":    {"EXECUTION": "mid",   "BAND_PROFIT": 0.15, "QUOTE_RULE": "count"},
    "p15_cross_count":  {"EXECUTION": "cross", "BAND_PROFIT": 0.15, "QUOTE_RULE": "count"},
    "base_mid_on":      {"EXECUTION": "mid",   "QUOTE_RULE": "on"},
    "base_cross_on":    {"EXECUTION": "cross", "QUOTE_RULE": "on"},
    "p15_mid_on":       {"EXECUTION": "mid",   "BAND_PROFIT": 0.15, "QUOTE_RULE": "on"},
    "p15_cross_on":     {"EXECUTION": "cross", "BAND_PROFIT": 0.15, "QUOTE_RULE": "on"},
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
    backtest.QUOTES_FILE = "quotes_" + name + tag + ".csv"       # the quote test (C14)

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
