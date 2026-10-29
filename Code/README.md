# Code

The pipeline scripts, numbered in the order they run (reorganised 2026-10-27; old
names in brackets, as they appear in older notes and logs). The
`s` in front is needed because Python cannot `import` a file whose name starts with
a digit; the scripts import each other as `import s03_rates as rates`.

**Run every script from the main folder**, e.g. `python Code/s11_backtest.py`: all
data paths (`Data/...`) are relative to it, and outputs are written there.

| Script | Before | What it does |
|---|---|---|
| `s01_stage1_extract_simple.py` | `stage1_extract_simple.py` | stage 1: cleans `Data/01_raw_options` into `Data/02_clean` |
| `s03_rates.py` | `rates.py` | T-bill rates and discount factors (imported) |
| `s04_forward.py` | `forward.py` | forward from put-call parity (imported) |
| `s05_volatility.py` | `volatility.py` | Black-76 price and implied vol (imported) |
| `s06_greeks.py` | `greeks.py` | Greeks (imported) |
| `s07_stage2_greeks.py` | `stage2_greeks.py` | stage 2: `Data/02_clean` into `Data/04_greeks` |
| `s08_atm_vol.py` | `atm_vol.py` | ATM vol per slice, `Data/05_atm_vol.csv` |
| `s09_vol_series.py` | `vol_series.py` | 30-day vol and stress threshold, `Data/06_vol30.csv` |
| `s11_backtest.py` | `backtest.py` | the backtest (imported by `s12`) |
| `s12_run_variants.py` | `run_variants.py` | runs the backtest variants |
| `s13_figure_smile.py` | `figure_smile.py` | Figure `fig:smile` |

**Removed 2026-10-29 (Arian):** `s02_check_coverage.py` (counted the trading days in
`Data/02_clean`; no thesis number came from it) and `s10_entry_delta.py` (the daily
10:00 entry-delta study, `entry_delta.csv`; replaced in the thesis by the entry
delta of the backtest's own entries, `../checks/entry_delta_backtest.py`, review_log
T63). The numbers `s02` and `s10` were not given to other scripts, so the names
in the thesis and in older notes stay valid. Both are in commit `150ce8a` and
earlier.

**Changed 2026-10-27 (review_log C15):** stage 1 takes the index level S at the
snapshot after the stock close (16:15, or 13:15 on early-close days) to be the
official daily close (`Data/07_index_close/GSPC_daily.csv`) and keeps the recorded
quote in a column `spot_quote`, and it keeps puts down to K/S = 0.30 (was 0.45).
The backtest no longer corrects the deltas after the close itself (the switch
`USE_OFFICIAL_CLOSE` is gone). `s01`, `s07`,
`s08` can be stopped and restarted (finished months are skipped, files are written
under a temporary name first) and can be imported without running. The versions
before are those of commit `4aca3ae` (tag `thesis-v1`).

**Output names (since 2026-10-28):** a backtest run is named after its variant
alone, e.g. `trades_base_mid.csv`, `trades_p15_cross.csv`; a run with one of the two
data rules switched off says so, `..._without_quote_rule`, `..._without_close_rule`.
Until then the names carried review_log item numbers (`_c8c9` = stock-close rule,
`q` = broken-quote rule, `_c15` = the rebuilt data). Those older runs were
removed on 2026-10-29.

Read-only check scripts are in `../checks/`.
