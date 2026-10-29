"""
RUNNING THE STRATEGY VARIANTS

What this file is for:
    s11_backtest.py keeps the base-case settings at its top. To run a variant
    (e.g. a 45-day base maturity) we do NOT edit s11_backtest.py; instead this file
    imports it, changes the settings for one run, and starts it. Every run
    writes its own files, named after the variant, so nothing is overwritten.

    The variants were fixed on 2026-10-08, after the cost result and BEFORE any
    of them was run (see backtest_design.md). They must not be tuned afterwards.

HOW TO RUN IT
    python Code/s12_run_variants.py base_cross              one run
    python Code/s12_run_variants.py p15_mid p15_cross       several runs, one after the other
"""

import sys

import s11_backtest as backtest            # the backtest itself (runs nothing on import)


# Every variant: its name and the settings it changes. Settings not listed keep
# the base-case value from the top of s11_backtest.py.
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

    # Comparison runs (added 2026-10-27, review_log.md C15). They change no rule
    # of the strategy, only switch off one of the two rules for bad DATA, so the
    # thesis can show what that rule changes (sec:monitoring, sec:broken-quotes).
    # without the broken-quote rule (C14)
    "base_mid_without_quote_rule":    {"EXECUTION": "mid",   "QUOTE_RULE": "off"},
    "base_cross_without_quote_rule":  {"EXECUTION": "cross", "QUOTE_RULE": "off"},
    "p15_mid_without_quote_rule":     {"EXECUTION": "mid",   "BAND_PROFIT": 0.15, "QUOTE_RULE": "off"},
    "p15_cross_without_quote_rule":   {"EXECUTION": "cross", "BAND_PROFIT": 0.15, "QUOTE_RULE": "off"},
    # without the broken-quote rule and without the stock-close rule (C9)
    "base_mid_without_close_rule":    {"EXECUTION": "mid",   "QUOTE_RULE": "off", "SKIP_CLOSE_SNAPSHOT": False},
    "base_cross_without_close_rule":  {"EXECUTION": "cross", "QUOTE_RULE": "off", "SKIP_CLOSE_SNAPSHOT": False},
}


def run_one(name):
    """Change s11_backtest.py's settings for this variant and run it."""

    settings = VARIANTS[name]

    # setattr(backtest, "EXECUTION", "cross") does the same as writing
    # EXECUTION = "cross" at the top of s11_backtest.py, but only for this run
    for setting_name in settings:
        setattr(backtest, setting_name, settings[setting_name])

    # The variant's name already says everything that differs from the base
    # case (e.g. "p15_cross", "base_mid_without_quote_rule"), so the output
    # files are named after it alone. Until 2026-10-28 a tag of review_log.md
    # item numbers was added ("_c8c9", "q", "_c15"); those older runs were
    # removed on 2026-10-29.

    # the output files carry the variant's name, e.g. "trades_t45_cross.csv"
    backtest.TRADES_FILE = "trades_" + name + ".csv"
    backtest.EQUITY_FILE = "equity_" + name + ".csv"
    backtest.QUARTERS_FILE = "quarters_" + name + ".csv"
    backtest.QUOTES_FILE = "quotes_" + name + ".csv"       # the quote test (C14)
    backtest.MISSING_FILE = "missing_" + name + ".csv"     # the missing legs (C15)

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

        # each run starts from a fresh copy of s11_backtest.py's base settings,
        # so one variant's changes cannot leak into the next run.
        # importlib.reload reads s11_backtest.py again from the file.
        import importlib
        importlib.reload(backtest)

        run_one(name)


main()
