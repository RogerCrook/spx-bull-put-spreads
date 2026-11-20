"""
Synthetic market, part 2 of 3: run the project's pipeline on the made-up market.

What this file is for
---------------------
The pipeline scripts read "Data/..." relative to the folder they are started from
and write their outputs there (Code/README.md). This script changes into the folder
made by make_market.py and runs, unchanged and in order:
    stage 1   Code/s01_stage1_extract_simple.py   01_raw_options -> 02_clean
    stage 2   Code/s07_stage2_greeks.py           02_clean -> 04_greeks
    ATM fit   Code/s08_atm_vol.py                 04_greeks -> 05_atm_vol.csv
Only their main() is called (the interface in Code/README.md). Nothing in the
project's Data/ or results/ is read or written.

How to run (from the main folder; seconds to a few minutes):
    python validation/automatic/synthetic/run_pipeline.py
"""

import os               # folders and paths
import sys              # where Python finds modules
import tempfile         # the computer's temporary folder


# The mutation tests (step 5) point the settings marked "(outside)" elsewhere through
# environment variables: os.environ.get("NAME", default) reads a setting given from
# outside the script, or uses the default. Run normally, nothing changes.
WORK_FOLDER = os.environ.get("CHECK_SYNTHETIC_FOLDER", os.path.join(tempfile.gettempdir(), "masterarbeit_synthetic"))   # (outside)
# the code to run: the project's, found before changing folder, or a mutant's (outside)
CODE_FOLDER = os.environ.get("CHECK_CODE_FOLDER", os.path.abspath("Code"))
PROJECT_FOLDER = os.path.abspath(".")     # the main folder, where this script is started


def main():
    if not os.path.isdir(WORK_FOLDER):
        raise ValueError("no synthetic market in " + WORK_FOLDER + ": run make_market.py first")

    sys.path.insert(0, CODE_FOLDER)            # so "import s01_..." finds the project's code
    os.chdir(WORK_FOLDER)                      # from here on "Data/..." means the synthetic Data
    if os.getcwd().startswith(PROJECT_FOLDER):
        raise ValueError("refusing to run inside the project")

    import s01_stage1_extract_simple as stage1
    import s07_stage2_greeks as stage2
    import s08_atm_vol as atm_vol

    print("stage 1 in " + os.getcwd())
    stage1.main()
    print("stage 2 in " + os.getcwd())
    stage2.main()
    print("ATM fit in " + os.getcwd())
    atm_vol.main()


main()
