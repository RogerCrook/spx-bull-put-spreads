"""
Mutation testing, follow-up: do the two new tests catch the five gaps?

What this file is for
---------------------
run_mutants.py found five planted bugs that no test caught (2026-11-19):
    m013  s04_forward.py   the forward from 9 strikes instead of 8
    m036  s08_atm_vol.py   the ATM band 0.055 instead of 0.05
    m038  s08_atm_vol.py   the ATM fit without the out-of-the-money calls
    m039  s08_atm_vol.py   the ATM fit needs 4 points instead of 3
    m054  s11_backtest.py  the 30-day vol at entry computed wrongly
Two tests were added for them on 2026-11-20: the rough made-up market
(synthetic/make_rough_market.py, check_rough.py) and Part E of
invariants_check.py. This script runs the new tests on these five mutants and on
the unchanged copy m000, which must pass:
    m000, m013, m036, m038, m039: the pipeline on the rough market, then check_rough.py
    m000, m054: the backtest on Feb-Mar 2020, then invariants_check.py (with Part E)

Before running: the mutants (make_mutants.py), the data copies
(metamorphic/make_copies.py) and the rough market (synthetic/make_rough_market.py)
must exist in the temp folder.
How to run (from the main folder; a few minutes):
    python validation/automatic/mutation/rerun_gaps.py
Writes validation/automatic/output/mutation_gaps.csv and logs in
<temp>/masterarbeit_mutation/reports_gaps/<mutant>/log.txt.
"""

import csv              # reads and writes CSV files row by row
import os               # folders, paths, environment variables
import shutil           # copying and deleting folders
import subprocess       # running another Python program and waiting for it
import sys              # the path of the Python program itself
import tempfile         # the computer's temporary folder


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

TEMP = tempfile.gettempdir()
MUTATION_FOLDER = os.path.join(TEMP, "masterarbeit_mutation")
COPIES_FOLDER = os.path.join(TEMP, "masterarbeit_metamorphic")
ROUGH_MARKET = os.path.join(TEMP, "masterarbeit_synthetic_rough")
RESULTS_FILE = "validation/automatic/output/mutation_gaps.csv"
TESTS = "validation/automatic"

ROUGH_MARKET_MUTANTS = ["m000", "m013", "m036", "m038", "m039"]
BACKTEST_MUTANTS = ["m000", "m054"]
TIMEOUT = 900                   # seconds for one program


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_program(script, arguments, settings, log_file):
    """
    Run one Python script as a separate program with extra environment settings
    and wait for it. Returns "ok", "crashed" or "timed out".
    """
    environment = dict(os.environ)                 # a copy of this program's settings ...
    for name in settings:
        environment[name] = settings[name]         # ... plus the ones for this run
    command = [sys.executable, script] + arguments # sys.executable: the python that runs this file
    log_file.write("\n$ " + " ".join(command) + "   " + str(settings) + "\n")
    log_file.flush()
    try:
        finished = subprocess.run(command, env=environment, stdout=log_file, stderr=subprocess.STDOUT,
                                  timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return "timed out"
    if finished.returncode != 0:                   # 0 means the program ended normally
        return "crashed"
    return "ok"


def count_rows(path):
    """The number of rows of a check's output file (None if it is missing)."""
    if not os.path.exists(path):
        return None
    rows = 0
    with open(path, newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            rows = rows + 1
    return rows


def test_rough_market(mutant, code_folder, report_folder, log_file):
    """The mutant's stage 1, 2 and ATM fit on the rough market, then check_rough.py."""
    folder = os.path.join(MUTATION_FOLDER, "work", "rough_" + mutant)
    if os.path.exists(folder):
        shutil.rmtree(folder)                      # left over from a stopped run
    for part in ["Data/01_raw_options", "Data/03_treasury_bills", "Data/07_index_close"]:
        shutil.copytree(os.path.join(ROUGH_MARKET, part), os.path.join(folder, part))
    shutil.copy(os.path.join(ROUGH_MARKET, "truth.csv"), folder)

    settings = {"CHECK_SYNTHETIC_FOLDER": folder, "CHECK_CODE_FOLDER": code_folder,
                "CHECK_OUTPUT_FOLDER": report_folder}
    status = run_program(TESTS + "/synthetic/run_pipeline.py", [], settings, log_file)
    if status != "ok":
        shutil.rmtree(folder)
        return status, "pipeline on the rough market", ""
    status = run_program(TESTS + "/synthetic/check_rough.py", [], settings, log_file)
    shutil.rmtree(folder)
    if status != "ok":
        return "crashed", "rough-market check on the mutant's output", ""
    rows = count_rows(os.path.join(report_folder, "synthetic_rough_check.csv"))
    if rows is None or rows > 0:
        return "caught", "rough market", str(rows) + " differences"
    return "survived", "", ""


def test_backtest(mutant, code_folder, report_folder, log_file):
    """The mutant's backtest on Feb-Mar 2020, then the invariants check with Part E."""
    output_root = os.path.join(MUTATION_FOLDER, "work", "gaps_backtest_" + mutant)
    if os.path.exists(output_root):
        shutil.rmtree(output_root)
    settings = {"CHECK_COPIES_FOLDER": COPIES_FOLDER, "CHECK_CODE_FOLDER": code_folder,
                "CHECK_RUNS_OUTPUT": output_root}
    status = run_program(TESTS + "/metamorphic/run_on_copy.py", ["backtest_original", "base_mid", "base_cross"],
                         settings, log_file)
    if status != "ok":
        return status, "backtest run", ""
    original_copy = os.path.join(COPIES_FOLDER, "backtest_original", "Data")
    settings = {"CHECK_RESULTS_FOLDER": os.path.join(output_root, "backtest_original"),
                "CHECK_ATM_VOL_FILE": os.path.join(original_copy, "05_atm_vol.csv"),
                "CHECK_VOL30_FILE": os.path.join(original_copy, "06_vol30.csv"),
                "CHECK_RUNS": "base_mid,base_cross", "CHECK_SKIP_YEAR_TABLE": "yes",
                "CHECK_OUTPUT_FOLDER": report_folder}
    status = run_program(TESTS + "/invariants_check.py", [], settings, log_file)
    if status != "ok":
        return "caught", "invariants check (stopped on the output)", status
    rows = count_rows(os.path.join(report_folder, "invariants_check.csv"))
    if rows is None or rows > 0:
        return "caught", "invariants check", str(rows) + " differences"
    return "survived", "", ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    for folder in [MUTATION_FOLDER, COPIES_FOLDER, ROUGH_MARKET]:
        if not os.path.isdir(folder):
            raise ValueError("missing " + folder + ": run the scripts named at the top first")

    # The manifest gives the file, line and change of each mutant.
    manifest = {}
    with open(os.path.join(MUTATION_FOLDER, "manifest.csv"), newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            manifest[row["mutant"]] = row

    results = []
    for test_name, mutants, test in [("rough market", ROUGH_MARKET_MUTANTS, test_rough_market),
                                     ("backtest + Part E", BACKTEST_MUTANTS, test_backtest)]:
        for mutant in mutants:
            code_folder = os.path.join(MUTATION_FOLDER, "mutants", mutant, "Code")
            report_folder = os.path.join(MUTATION_FOLDER, "reports_gaps", mutant + "_" + test_name.split()[0])
            os.makedirs(report_folder, exist_ok=True)
            with open(os.path.join(report_folder, "log.txt"), "w", encoding="utf-8") as log_file:
                outcome, caught_by, detail = test(mutant, code_folder, report_folder, log_file)
            row = manifest[mutant]
            results.append({"mutant": mutant, "file": row["file"], "line": row["line"], "change": row["change"],
                            "test": test_name, "outcome": outcome, "caught_by": caught_by, "detail": detail})
            print(mutant + " " + row["file"] + " " + row["change"] + " | " + test_name + ": " + outcome
                  + " " + caught_by + " " + detail, flush=True)

    with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["mutant", "file", "line", "change", "test",
                                                  "outcome", "caught_by", "detail"])
        writer.writeheader()
        for row in results:
            writer.writerow(row)
    print("written to " + RESULTS_FILE)


main()
