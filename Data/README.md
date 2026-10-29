# Data

All data of the thesis, numbered in the order the data sets were made (reorganised
2026-10-27; old names in brackets, as they appear in older notes and logs).

| Folder / file | Before | What it is | Made by |
|---|---|---|---|
| `01_raw_options/` | `Options2/` | raw Cboe option quotes, one CSV per trading day (3,675 files, ~175 GB) | download |
| `02_clean/` | `Clean/` | cleaned quotes, one CSV per month (176 files, ~40 GB) | `Code/s01_stage1_extract_simple.py` |
| `03_treasury_bills/` | `TreasuryBills/` | T-bill yields (1, 3, 6, 12 months) | download |
| `04_greeks/` | `Greeks/` | forward, implied vol and Greeks per quote, one CSV per month (176 files, ~68 GB) | `Code/s07_stage2_greeks.py` |
| `05_atm_vol.csv` | `atm_vol.csv` | ATM forward implied vol per snapshot and expiry (~165 MB) | `Code/s08_atm_vol.py` |
| `06_vol30.csv` | `vol30.csv` | daily 30-day ATM vol and the stress threshold | `Code/s09_vol_series.py` |
| `07_index_close/` | `IndexClose/` | official daily S&P 500 close (`GSPC_daily.csv`) | `checks/fetch_gspc.py` |
| `08_vix/` | | Cboe's daily VIX history (`VIX_History.csv`), cited once in `tab:validation`, used by no script | download from https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv, 27 October 2026 |
| `09_total_return/` | | daily close of the S&P 500 total return index (Yahoo ^SP500TR, dividends reinvested) and of the price index ^GSPC, 1 Dec 2011 to 14 Aug 2026 (`SP500TR_daily.csv`), with the download date and addresses (`retrieved.txt`); for the quarterly comparison in ch. 4 (review_log T69) | `checks/fetch_sp500tr.py`, 29 October 2026 |

Since 2026-10-27 (review_log C15) `02_clean/`, `04_greeks/` and `05_atm_vol.csv`
have a column `spot_quote` (the recorded index quote) next to `spot` (the index level
S used): they differ only at the snapshot after the stock close, where `spot` is the
official close. Puts are kept down to K/S = 0.30. `Code/s08_atm_vol.py` saves the
monthly pieces of `05_atm_vol.csv` in `05_atm_vol_parts/` (so it can resume) and
skips every month already there. The folder was deleted on 2026-10-29, after
`05_atm_vol.csv` was written. Delete it before any rerun on changed data.
Sizes as of 2026-10-29 (decimal GB). The data
before the rerun were kept outside the project folder until checked.

Backtest results are in `../results/`.
