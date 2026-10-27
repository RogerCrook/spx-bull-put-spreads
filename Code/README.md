# Code

The pipeline scripts, numbered in the order they run (reorganised 2026-10-27; old
names in brackets, as they appear in older notes, logs and `old_versions/`). The
`s` in front is needed because Python cannot `import` a file whose name starts with
a digit; the scripts import each other as `import s03_rates as rates`.

**Run every script from the main folder**, e.g. `python Code/s11_backtest.py`: all
data paths (`Data/...`) are relative to it, and outputs are written there.

| Script | Before | What it does |
|---|---|---|
| `s01_stage1_extract_simple.py` | `stage1_extract_simple.py` | stage 1: cleans `Data/01_raw_options` into `Data/02_clean` |
| `s02_check_coverage.py` | `check_coverage.py` | counts the trading days in `Data/02_clean` |
| `s03_rates.py` | `rates.py` | T-bill rates and discount factors (imported) |
| `s04_forward.py` | `forward.py` | forward from put-call parity (imported) |
| `s05_volatility.py` | `volatility.py` | Black-76 price and implied vol (imported) |
| `s06_greeks.py` | `greeks.py` | Greeks (imported) |
| `s07_stage2_greeks.py` | `stage2_greeks.py` | stage 2: `Data/02_clean` into `Data/04_greeks` |
| `s08_atm_vol.py` | `atm_vol.py` | ATM vol per slice, `Data/05_atm_vol.csv` |
| `s09_vol_series.py` | `vol_series.py` | 30-day vol and stress threshold, `Data/06_vol30.csv` |
| `s10_entry_delta.py` | `entry_delta.py` | realised entry delta, `entry_delta.csv` |
| `s11_backtest.py` | `backtest.py` | the backtest (imported by `s12`) |
| `s12_run_variants.py` | `run_variants.py` | runs the backtest variants |
| `s13_figure_smile.py` | `figure_smile.py` | Figure `fig:smile` |

Read-only check scripts are in `../checks/`, the quote-rule experiment in
`../experiments/quote_filter/` (with its own copies of the modules, old names), older
versions in `../old_versions/` (the state just before the renaming in
`old_versions/before_reorg_2026-10-27/`).
