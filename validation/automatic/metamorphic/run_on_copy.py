"""
Metamorphic tests, part 2 of 3: run the project's code inside one copy.

What this file is for
---------------------
The pipeline scripts read "Data/..." relative to the folder they are started from
and write their outputs there (Code/README.md). So this script changes into a copy
made by make_copies.py and runs the project's own code there, unchanged. Nothing is
read from or written to the project's Data/ or results/.

Only the interface of the code is used, as documented in Code/README.md and in the
settings block at the top of each script: s11_backtest's settings EXECUTION,
TEST_MONTHS and the output file names, then its main(), as Code/s12_run_variants.py
does it; and the main() of s07_stage2_greeks and s08_atm_vol.

How to run (from the main folder):
    python validation/automatic/metamorphic/run_on_copy.py backtest_original base_mid base_cross
    python validation/automatic/metamorphic/run_on_copy.py stage2_original stage2

The first word is the copy (a folder in WORK_FOLDER), the others what to run in it:
base_mid, base_cross (the backtest on BACKTEST_MONTHS), or stage2 (stage 2 and the
ATM fit on the copy's cleaned month).
"""

import importlib        # to load the backtest afresh for each run
import os               # folders and paths
import sys              # the words typed after "python", and where Python finds modules
import tempfile         # the computer's temporary folder


# ---------------------------------------------------------------------------
# Settings (the same as in make_copies.py)
# ---------------------------------------------------------------------------

# The mutation tests (step 5) point the settings marked "(outside)" elsewhere through
# environment variables: os.environ.get("NAME", default) reads a setting given from
# outside the script, or uses the default. Run normally, nothing changes.
WORK_FOLDER = os.environ.get("CHECK_COPIES_FOLDER", os.path.join(tempfile.gettempdir(), "masterarbeit_metamorphic"))   # (outside)
BACKTEST_MONTHS = ["2020-02", "2020-03"]
# the code to run: the project's, found before changing folder, or a mutant's (outside)
CODE_FOLDER = os.environ.get("CHECK_CODE_FOLDER", os.path.abspath("Code"))
PROJECT_FOLDER = os.path.abspath(".")     # the main folder, where this script is started
# where the outputs go: "" = into the copy itself, else into <this folder>/<copy name> (outside)
OUTPUT_ROOT = os.environ.get("CHECK_RUNS_OUTPUT", "")

# The two runs, with the settings they change (as in Code/s12_run_variants.py).
RUNS = {
    "base_mid": {"EXECUTION": "mid"},
    "base_cross": {"EXECUTION": "cross"},
}


def run_backtest(run_name, output_folder):
    """
    Run the backtest with one run's settings on BACKTEST_MONTHS, in the current folder.
    The output files go into output_folder ("" = the current folder).
    """
    import s11_backtest as backtest            # the project's backtest (runs nothing on import)
    importlib.reload(backtest)                 # fresh base-case settings for every run

    for setting in RUNS[run_name]:
        setattr(backtest, setting, RUNS[run_name][setting])   # setattr(m, "X", v) is m.X = v
    backtest.TEST_MONTHS = BACKTEST_MONTHS
    # os.path.join("", name) is just name, so with no output folder the files go here
    backtest.TRADES_FILE = os.path.join(output_folder, "trades_" + run_name + ".csv")
    backtest.EQUITY_FILE = os.path.join(output_folder, "equity_" + run_name + ".csv")
    backtest.QUARTERS_FILE = os.path.join(output_folder, "quarters_" + run_name + ".csv")
    backtest.QUOTES_FILE = os.path.join(output_folder, "quotes_" + run_name + ".csv")
    backtest.MISSING_FILE = os.path.join(output_folder, "missing_" + run_name + ".csv")

    print("running " + run_name + " in " + os.getcwd())
    backtest.main()


def run_stage2():
    """Run stage 2 (forward, iv, Greeks) and the ATM fit on the cleaned month of the current folder."""
    import s07_stage2_greeks as stage2
    import s08_atm_vol as atm_vol
    print("running stage 2 in " + os.getcwd())
    stage2.main()
    print("running the ATM fit in " + os.getcwd())
    atm_vol.main()


def main():
    words = sys.argv[1:]                       # the words after the file name
    if len(words) < 2:
        print(__doc__)
        return
    copy_name = words[0]
    to_run = words[1:]

    folder = os.path.join(WORK_FOLDER, copy_name)
    if not os.path.isdir(folder):
        raise ValueError("no copy " + folder + ": run make_copies.py first")

    output_folder = ""
    if OUTPUT_ROOT != "":
        output_folder = os.path.join(OUTPUT_ROOT, copy_name)
        os.makedirs(output_folder, exist_ok=True)       # no error if it exists
    sys.path.insert(0, CODE_FOLDER)            # so "import s11_backtest" finds the code to run
    os.chdir(folder)                           # from here on "Data/..." means the copy's Data
    if os.getcwd().startswith(PROJECT_FOLDER):
        raise ValueError("refusing to run inside the project")

    for name in to_run:
        if name == "stage2":
            run_stage2()
        elif name in RUNS:
            run_backtest(name, output_folder)
        else:
            print("unknown run: " + name)


main()
