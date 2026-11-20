"""
Mutation testing, part 2 of 2: run the tests on every mutant and count the catches.

What this file is for
---------------------
make_mutants.py wrote copies of Code/ with one planted bug each. For every mutant
this script runs the tests that fit the file it changed, cheapest first, and stops
at the first test that catches it:

  pipeline files (s01, s03, s04, s05, s06, s07, s08):
      the synthetic market: stage 1, stage 2 and the ATM fit on the made-up market,
      compared with the truth (validation/automatic/synthetic/)
  the backtest (s11), and s03 and s06, which the backtest also uses:
      the backtest on Feb-Mar 2020, at mid and crossing the spread, then
      the one-step check (one_step_check.py), the equity rebuild
      (invariants_check.py), and the metamorphic tests (metamorphic/compare.py,
      prices x 2, bid = ask, data cut, random stress)

A mutant is "caught" when a test reports a difference, "crashed" when the code
stops with an error (also a catch: a run that fails is noticed), "timed out" when it
runs too long, and "survived" when every test passes. m000, the unchanged code, must
survive every test: otherwise the harness itself is wrong and the run stops.

Everything runs in the temp folder. The tests are the project's own scripts, run as
separate programs (the module subprocess) with their folders set from outside.

Before running:
    python validation/automatic/metamorphic/make_copies.py    (the data copies)
    python validation/automatic/synthetic/make_market.py      (the made-up market)
    python validation/automatic/mutation/make_mutants.py      (the mutants)
How to run (from the main folder; one to three hours, best in the background):
    python validation/automatic/mutation/run_mutants.py
Results, one row per mutant, in validation/automatic/output/mutation_results.csv
(written after each mutant, so a stopped run can be continued: finished mutants are
skipped).
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
MUTATION_FOLDER = os.path.join(TEMP, "masterarbeit_mutation")       # mutants, work, reports
COPIES_FOLDER = os.path.join(TEMP, "masterarbeit_metamorphic")      # from make_copies.py
SYNTHETIC_BASE = os.path.join(TEMP, "masterarbeit_synthetic")       # from make_market.py
RESULTS_FILE = "validation/automatic/output/mutation_results.csv"
TESTS = "validation/automatic"                                      # the test scripts

PIPELINE_FILES = ["s01_stage1_extract_simple.py", "s03_rates.py", "s04_forward.py",
                  "s05_volatility.py", "s06_greeks.py", "s07_stage2_greeks.py", "s08_atm_vol.py"]
BACKTEST_FILES = ["s11_backtest.py", "s03_rates.py", "s06_greeks.py"]

PIPELINE_TIMEOUT = 600          # seconds for the pipeline on the made-up market (normally 31 s)
BACKTEST_TIMEOUT = 900          # seconds for two backtest runs (normally about 140 s)
CHECK_TIMEOUT = 600             # seconds for one check script

RESULT_COLUMNS = ["mutant", "file", "line", "kind", "change", "code", "outcome", "caught_by", "detail"]


# ---------------------------------------------------------------------------
# Running one program
# ---------------------------------------------------------------------------

def run_program(script, arguments, settings, timeout, log_file):
    """
    Run one Python script as a separate program, with extra environment settings
    (the "(outside)" settings of the test scripts), and wait for it.
    Returns "ok", "crashed" or "timed out". Its printout goes to log_file.
    """
    environment = dict(os.environ)                 # a copy of this program's settings ...
    for name in settings:
        environment[name] = settings[name]         # ... plus the ones for this run
    command = [sys.executable, script] + arguments # sys.executable: the python that runs this file
    log_file.write("\n$ " + " ".join(command) + "   " + str(settings) + "\n")
    log_file.flush()
    try:
        finished = subprocess.run(command, env=environment, stdout=log_file, stderr=subprocess.STDOUT,
                                  timeout=timeout)
    except subprocess.TimeoutExpired:              # the program ran longer than allowed
        return "timed out"
    if finished.returncode != 0:                   # 0 means the program ended normally
        return "crashed"
    return "ok"


def differences_written(log_path):
    """
    Read the last "<N> differences written to ..." line of a log (printed by
    synthetic/check.py and metamorphic/compare.py) and return N, or None if absent.
    """
    found = None
    with open(log_path, encoding="utf-8", errors="replace") as file:
        for line in file:
            words = line.split()
            if "differences written to" in line and len(words) > 0 and words[0].isdigit():
                found = int(words[0])
    return found


def count_rows(path, leave_out_statements):
    """
    The number of rows of a check's output file, leaving out rows that are notes
    rather than differences: one-step "(edge)" rows and the G11 comparison.
    """
    if not os.path.exists(path):
        return None
    rows = 0
    with open(path, newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            statement = row.get("statement", "")
            is_note = False
            for note in leave_out_statements:
                if note in statement:
                    is_note = True
            if not is_note:
                rows = rows + 1
    return rows


# ---------------------------------------------------------------------------
# The two test groups
# ---------------------------------------------------------------------------

def test_with_synthetic_market(mutant, code_folder, report_folder, log_file):
    """Stage 1, 2 and the ATM fit of the mutant on the made-up market. Returns (outcome, by, detail)."""
    folder = os.path.join(MUTATION_FOLDER, "work", "synthetic_" + mutant)
    if os.path.exists(folder):
        shutil.rmtree(folder)                      # left over from a stopped run
    # Only the inputs of the made-up market (not the outputs of an earlier run).
    for part in ["Data/01_raw_options", "Data/03_treasury_bills", "Data/07_index_close"]:
        shutil.copytree(os.path.join(SYNTHETIC_BASE, part), os.path.join(folder, part))
    shutil.copy(os.path.join(SYNTHETIC_BASE, "truth.csv"), folder)

    settings = {"CHECK_SYNTHETIC_FOLDER": folder, "CHECK_CODE_FOLDER": code_folder,
                "CHECK_OUTPUT_FOLDER": report_folder}
    status = run_program(TESTS + "/synthetic/run_pipeline.py", [], settings, PIPELINE_TIMEOUT, log_file)
    if status != "ok":
        shutil.rmtree(folder)
        return status, "pipeline on the made-up market", ""
    status = run_program(TESTS + "/synthetic/check.py", [], settings, CHECK_TIMEOUT, log_file)
    shutil.rmtree(folder)                          # about 100 MB, not kept
    if status != "ok":
        return "crashed", "synthetic check on the mutant's output", ""
    log_file.flush()
    count = differences_written(log_file.name)
    if count is None or count > 0:
        return "caught", "synthetic market", str(count) + " differences"
    return "survived", "", ""


def run_backtest_on(copy_name, code_folder, output_root, log_file):
    """Run the mutant's backtest (mid and cross) on one data copy. Returns "ok", "crashed" or "timed out"."""
    settings = {"CHECK_COPIES_FOLDER": COPIES_FOLDER, "CHECK_CODE_FOLDER": code_folder,
                "CHECK_RUNS_OUTPUT": output_root}
    return run_program(TESTS + "/metamorphic/run_on_copy.py", [copy_name, "base_mid", "base_cross"],
                       settings, BACKTEST_TIMEOUT, log_file)


def test_with_backtest(mutant, code_folder, report_folder, log_file):
    """The backtest of the mutant on Feb-Mar 2020 and the checks on it. Returns (outcome, by, detail)."""
    output_root = os.path.join(MUTATION_FOLDER, "work", "backtest_" + mutant)
    if os.path.exists(output_root):
        shutil.rmtree(output_root)
    status = run_backtest_on("backtest_original", code_folder, output_root, log_file)
    if status != "ok":
        return status, "backtest run", ""

    original_copy = os.path.join(COPIES_FOLDER, "backtest_original", "Data")
    settings = {"CHECK_RESULTS_FOLDER": os.path.join(output_root, "backtest_original"),
                "CHECK_ATM_VOL_FILE": os.path.join(original_copy, "05_atm_vol.csv"),
                "CHECK_VOL30_FILE": os.path.join(original_copy, "06_vol30.csv"),
                "CHECK_RUNS": "base_mid,base_cross", "CHECK_SKIP_YEAR_TABLE": "yes",
                "CHECK_OUTPUT_FOLDER": report_folder}

    # 1. The one-step check.
    status = run_program(TESTS + "/one_step_check.py", [], settings, CHECK_TIMEOUT, log_file)
    if status != "ok":
        return "caught", "one-step check (stopped on the output)", status
    total = 0
    for run_name in ["base_mid", "base_cross"]:
        rows = count_rows(os.path.join(report_folder, "one_step_" + run_name + ".csv"), ["(edge)", "G11"])
        if rows is None:
            return "caught", "one-step check (no output)", run_name
        total = total + rows
    if total > 0:
        return "caught", "one-step check", str(total) + " differences"

    # 2. The equity rebuild.
    status = run_program(TESTS + "/invariants_check.py", [], settings, CHECK_TIMEOUT, log_file)
    if status != "ok":
        return "caught", "invariants check (stopped on the output)", status
    rows = count_rows(os.path.join(report_folder, "invariants_check.csv"), [])
    if rows is None or rows > 0:
        return "caught", "invariants check", str(rows) + " differences"

    # 3. The metamorphic tests: the same mutant on the changed copies.
    for copy_name in ["backtest_times2", "backtest_bid_equals_ask", "backtest_cut", "backtest_random_stress"]:
        status = run_backtest_on(copy_name, code_folder, output_root, log_file)
        if status != "ok":
            return status, "backtest run on " + copy_name, ""
    settings = {"CHECK_COPIES_FOLDER": COPIES_FOLDER, "CHECK_RUNS_OUTPUT": output_root,
                "CHECK_SKIP_STAGE2": "yes", "CHECK_OUTPUT_FOLDER": report_folder}
    status = run_program(TESTS + "/metamorphic/compare.py", [], settings, CHECK_TIMEOUT, log_file)
    if status != "ok":
        return "caught", "metamorphic comparison (stopped on the output)", status
    log_file.flush()
    count = differences_written(log_file.name)
    if count is None or count > 0:
        return "caught", "metamorphic tests", str(count) + " differences"
    return "survived", "", ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def read_done():
    """The mutants already in the results file (so a stopped run continues where it stopped)."""
    done = set()
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                done.add(row["mutant"])
    return done


def main():
    for folder in [COPIES_FOLDER, SYNTHETIC_BASE, MUTATION_FOLDER]:
        if not os.path.isdir(folder):
            raise ValueError("missing " + folder + ": run the three scripts named at the top first")

    with open(os.path.join(MUTATION_FOLDER, "manifest.csv"), newline="", encoding="utf-8") as file:
        manifest = list(csv.DictReader(file))

    done = read_done()
    if not os.path.exists(RESULTS_FILE):
        os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
        with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as file:
            csv.DictWriter(file, fieldnames=RESULT_COLUMNS).writeheader()

    for row in manifest:
        mutant = row["mutant"]
        if mutant in done:
            continue
        code_folder = os.path.join(MUTATION_FOLDER, "mutants", mutant, "Code")
        report_folder = os.path.join(MUTATION_FOLDER, "reports", mutant)
        os.makedirs(report_folder, exist_ok=True)
        file_name = row["file"]
        is_unchanged = mutant == "m000"

        with open(os.path.join(report_folder, "log.txt"), "w", encoding="utf-8") as log_file:
            outcome, caught_by, detail = "survived", "", ""
            if is_unchanged or file_name in PIPELINE_FILES:
                outcome, caught_by, detail = test_with_synthetic_market(mutant, code_folder, report_folder, log_file)
            if outcome == "survived" and (is_unchanged or file_name in BACKTEST_FILES):
                outcome, caught_by, detail = test_with_backtest(mutant, code_folder, report_folder, log_file)

        result = dict(row)
        result["outcome"] = outcome
        result["caught_by"] = caught_by
        result["detail"] = detail
        with open(RESULTS_FILE, "a", newline="", encoding="utf-8") as file:   # "a": add at the end
            csv.DictWriter(file, fieldnames=RESULT_COLUMNS).writerow(result)
        print(mutant + " " + file_name + " line " + row["line"] + " " + row["change"] + ": " + outcome
              + " " + caught_by + " " + detail, flush=True)

        if is_unchanged and outcome != "survived":
            print("The unchanged code did not pass every test: the harness is wrong. Stopped.")
            return

    # The score: caught (incl. crashed and timed out) / all mutants.
    counts = {}
    with open(RESULTS_FILE, newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if row["mutant"] == "m000":
                continue
            counts[row["outcome"]] = counts.get(row["outcome"], 0) + 1
    print()
    for outcome in sorted(counts):
        print("  " + outcome.ljust(12) + str(counts[outcome]).rjust(5))


main()
