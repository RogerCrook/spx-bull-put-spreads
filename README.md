# Delta-managed short bull put spreads on the S&P 500

Code for the master's thesis **"Mathematical Analysis of a Trading Strategy in
Collaboration with Alprime Capital, Zurich"** by Arian Tahirukaj (2026). The thesis
describes the strategy, the data and the results. This repository holds only the
code, **no data and no results**, because the option data are licensed from Cboe.

| Folder | What it holds |
|---|---|
| `Code/` | the pipeline, `s01` to `s14`, in the order it runs (`Code/README.md`) |
| `checks/` | read-only scripts behind the numbers in the thesis (`checks/README.md`) |
| `Data/` | empty here. The expected layout is in `Data/README.md` |

## Data (not included)

1. **Cboe DataShop, "Option Quotes"** (https://datashop.cboe.com/option-quote-intervals),
   15-minute intervals, S&P 500 index options, without the "Calcs" columns, with the
   underlying bid and ask, every trading day from 3 January 2012 to 14 August 2026
   (3,675 CSV files, about 175 GB). Put them in `Data/01_raw_options/` (subfolders
   are fine).
2. **FRED**, the series `DGS1MO`, `DGS3MO`, `DGS6MO` and `DGS1`, each saved as
   `Data/03_treasury_bills/<series>.csv`.
3. **Yahoo Finance**, the daily close of the S&P 500 (`^GSPC`, made by
   `checks/fetch_gspc.py`) and of its total return index (`^SP500TR`, made by
   `checks/fetch_sp500tr.py`). A new download may differ from the files the thesis
   used (retrieved 22 and 29 October 2026).

## Running

Python 3.13 (`pip install -r requirements.txt`). **Run every script from the
repository root**, e.g. `python Code/s11_backtest.py`, because all paths are relative
to it.

| Step | Script | Writes | Time |
|---|---|---|---|
| 1 | `checks/fetch_gspc.py` | `Data/07_index_close/GSPC_daily.csv` | seconds |
| 2 | `Code/s01_stage1_extract_simple.py` | `Data/02_clean/` (176 files, about 40 GB) | about 2 hours |
| 3 | `Code/s07_stage2_greeks.py` (uses `s03` to `s06`) | `Data/04_greeks/` (about 68 GB) | about 5 hours |
| 4 | `Code/s08_atm_vol.py` | `Data/05_atm_vol.csv` | hours |
| 5 | `Code/s09_vol_series.py` | `Data/06_vol30.csv` | minutes |
| 6 | `Code/s12_run_variants.py base_mid base_cross p15_mid p15_cross` (runs `s11`) | `trades_`, `equity_`, `quarters_`, `quotes_`, `missing_<run>.csv` | about 20 minutes per run |
| 7 | `Code/s13_figure_smile.py`, `Code/s14_figures_results.py` | the figures | seconds |

- Step 6 writes into the repository root. The check scripts read the runs from
  `results/`, so move them there.
- The comparison runs of the thesis are step 6 with `base_mid_without_quote_rule`,
  `base_cross_without_quote_rule`, `p15_mid_without_quote_rule`,
  `p15_cross_without_quote_rule`, `base_mid_without_close_rule` and
  `base_cross_without_close_rule`.
- `s01`, `s07` and `s08` skip every month already written, so a run can be stopped
  and started again. Delete the old output before a rebuild (`Data/02_clean/`,
  `Data/04_greeks/`, `Data/05_atm_vol_parts/`).

## Settings

The base case is set at the top of `Code/s11_backtest.py`. `Code/s12_run_variants.py`
runs the variants without editing it: `base` and `p15` (profit exit at Δ₀ − 0.15),
each at mid (`_mid`) and crossing the spread (`_cross`). The variants `p0`, `t45` and
`t60` are defined too. All were fixed before any was run, and the thesis reports
only `base` and `p15`. Two switches handle problems in the data, and both are on in
the reported runs.

| Switch | Default | What it does |
|---|---|---|
| `SKIP_CLOSE_SNAPSHOT` | `True` | no decision at the stock-close snapshot (16:00, 13:00 on early-close days) |
| `QUOTE_RULE` | `"on"` | skips broken option quotes (`"count"` only counts them, `"off"` uses every quote) |

The comments name the stock-close rule and the broken-quote rule (the two switches
above), the official close (stage 1 stores the official close as the index level
after the stock close) and the data rebuild of 2026-10-27, when that was added.

## Licence and citation

MIT licence (`LICENSE`). Please cite the thesis, which gives the commit it refers to.
