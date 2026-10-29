# Delta-managed short bull put spreads on the S&P 500

Code for the master's thesis **"Mathematical Analysis of a Trading Strategy in
Collaboration with Alprime Capital, Zurich"** by Arian Tahirukaj (2026).

The thesis backtests a short bull put spread on the S&P 500 index (SPX) from
January 2012 to August 2026. Each spread sells a put at `K = F·exp(-1·σ√τ)` and
buys a put at `K = F·exp(-2.3·σ√τ)`, where F is the forward and σ the at-the-money
implied volatility of the expiry traded, normally about 30 days away. Two spreads
are held at a time. The position is checked every 15 minutes and closed by its
delta (profit and loss exits) or by a gamma exit. After a loss, the next position
uses the shortest maturity whose credit covers the loss, up to 90 days. Idle
capital earns the 3-month T-bill rate.

This repository holds the code that cleaned the option data, computed forwards,
implied volatilities and Greeks, ran the backtest, and computed the numbers
reported in the thesis. It holds **no data and no results** (see "Data").

| Folder | What it holds |
|---|---|
| `Code/` | the pipeline, `s01` to `s13`, in the order it runs (`Code/README.md`) |
| `checks/` | read-only scripts behind the numbers in the thesis; `checks/README.md` lists, for each, the thesis passages it supports |
| `Data/` | empty here; the expected layout is in `Data/README.md` |

## Data (not included)

The option data are licensed from Cboe and may not be passed on, and neither may
the files made from them (`Data/02_clean`, `04_greeks`, `05_atm_vol.csv`,
`06_vol30.csv`) or the backtest results. To rerun the pipeline you need:

1. **Cboe DataShop, "Option Quotes"**
   (https://datashop.cboe.com/option-quote-intervals): 15-minute intervals (900
   seconds), S&P 500 index options, without the "Calcs" columns, with the
   underlying bid and ask, every trading day from 3 January 2012 to 14 August 2026.
   One CSV file per day, 3,675 files, about 175 GB. Put them in
   `Data/01_raw_options/` (subfolders are fine, `s01` searches them all). The files
   are named `UnderlyingOptionsIntervals_900sec_<date>.csv`, except the 117 days
   from 2 June 2023 to 14 August 2024, which came as
   `hanweck.UnderlyingOptionsIntervalsHanweck_900sec_<date>.csv` with the same 17
   columns:
   `underlying_symbol, quote_datetime, root, expiration, strike, option_type, open,
   high, low, close, trade_volume, bid_size, bid, ask_size, ask, underlying_bid,
   underlying_ask`.
2. **FRED**, the series `DGS1MO`, `DGS3MO`, `DGS6MO` and `DGS1` (the 1-, 3-, 6- and
   12-month Treasury yields, in percent, daily), each downloaded as CSV from
   `https://fred.stlouisfed.org/series/<series>` and saved as
   `Data/03_treasury_bills/<series>.csv` (columns `observation_date,<series>`, a
   "." where a value is missing). The files used run from 1 December 2011 to
   24 September 2026.
3. **The official daily close of the S&P 500** (Yahoo Finance, symbol `^GSPC`):
   `python checks/fetch_gspc.py` writes `Data/07_index_close/GSPC_daily.csv`. The
   thesis used the file downloaded on 22 October 2026. Running the script again
   overwrites that file with a new download, which may differ. Yahoo's chart
   endpoint is not an official interface and may change.

## Setup

Python 3.13.7 on Windows 11. Install the packages with

    pip install -r requirements.txt

**Run every script from the repository root**, e.g. `python Code/s11_backtest.py`:
all paths (`Data/...`, `results/...`) are relative to it.

## Pipeline, in order

| Step | Script | Reads | Writes | Time (approx.) |
|---|---|---|---|---|
| 1 | `checks/fetch_gspc.py` (only if `Data/07_index_close/GSPC_daily.csv` is missing, see "Data") | Yahoo Finance | `Data/07_index_close/GSPC_daily.csv` | seconds |
| 2 | `Code/s01_stage1_extract_simple.py` | `Data/01_raw_options/`, `Data/07_index_close/` | `Data/02_clean/`, one file per month (176 files, about 40 GB) | about 2 hours¹ |
| 3 | `Code/s07_stage2_greeks.py` (uses `s03` to `s06`) | `Data/02_clean/`, `Data/03_treasury_bills/` | `Data/04_greeks/`, forward, implied vol and Greeks per quote (about 68 GB) | about 5 hours¹ |
| 4 | `Code/s08_atm_vol.py` | `Data/04_greeks/` | `Data/05_atm_vol.csv` | hours (not recorded) |
| 5 | `Code/s09_vol_series.py` | `Data/05_atm_vol.csv` | `Data/06_vol30.csv` (30-day vol and stress threshold) | |
| 6 | `Code/s12_run_variants.py base_mid base_cross p15_mid p15_cross` (runs `s11`) | `Data/03` to `07` | per run `trades_`, `equity_`, `quarters_`, `quotes_`, `missing_<run>.csv` | about 20 minutes per run² |
| 7 | `Code/s13_figure_smile.py` | `Data/04_greeks/` | the figure of the smile, `Masterarbeit_Tex_file/figures/smile.pdf` | |

¹ From the times the first and the last output file were written, on the author's
machine.
² Ten runs in two processes of five runs each, 97 minutes per process, on the
author's machine.

Step 6 with the names `base_mid_without_quote_rule`, `base_cross_without_quote_rule`,
`p15_mid_without_quote_rule`, `p15_cross_without_quote_rule`,
`base_mid_without_close_rule` and `base_cross_without_close_rule` makes the six
comparison runs the thesis quotes, with one or both of the data rules below switched
off.

`s01`, `s07` and `s08` skip every month whose output file already exists, so that
a run can be stopped and started again. To rebuild from changed input, first delete
the old output: `Data/02_clean/` for `s01`, `Data/04_greeks/` for `s07`, and for
`s08` its monthly pieces in `Data/05_atm_vol_parts/` (the folder is made by the
run, and can be deleted once `Data/05_atm_vol.csv` is written).

Step 6 writes its files into the repository root. The check scripts expect them in
`results/`, so move them there. The script numbers have gaps (`s02` and `s10` were
removed on 29 October 2026, see `Code/README.md`).

## The backtest settings

The base case is set at the top of `Code/s11_backtest.py`. `Code/s12_run_variants.py`
runs the variants without editing that file: `base` and `p15` (profit exit at
Δ₀ − 0.15 instead of Δ₀ − 0.10), each at the mid quote (`_mid`) and crossing the
bid/ask spread (`_cross`). The variants `p0`, `t45` and `t60` are defined too. They
were fixed before any of them was run, and the thesis reports only `base` and
`p15`. The `p0` variant is invalid from 18 March 2020 (the long leg it holds is no
longer quoted).

Two switches handle problems in the data. Both are on in the four reported runs:

| Switch | Default | What it does |
|---|---|---|
| `SKIP_CLOSE_SNAPSHOT` | `True` | no decision at the stock-close snapshot (16:00, 13:00 on early-close days), where the option quotes are unreliable |
| `QUOTE_RULE` | `"on"` | skips broken option quotes (`"count"` only measures the test, `"off"` uses every quote) |

A third problem is handled in stage 1: at the snapshot after the stock close (16:15,
13:15) the stored index quote can be far from the official close, so `s01` stores
the official close as the index level there and keeps the recorded quote in a
column `spot_quote`.

A run is named after its variant alone (`trades_base_mid.csv`). A run with a data
rule switched off says so: `..._without_close_rule` when `SKIP_CLOSE_SNAPSHOT` is
`False`, `..._without_quote_rule` when `QUOTE_RULE` is `"off"`.

## Check scripts

`checks/README.md` lists each script, what it computes and the thesis passages it
supports. They only read and print. Some read all of `Data/04_greeks/` (e.g.
`check_iv_failures.py`, about 9 minutes). The scripts on the backtest results need
the four reported runs in `results/`, and `chapter4_numbers.py` and
`check_close_snapshot.py` also the comparison runs.

## Which code made the reported runs

- **Every backtest figure in the thesis** comes from the four reported runs and
  the six comparison runs, made on 28 October 2026 by `Code/s11_backtest.py`, run
  through `Code/s12_run_variants.py`, on the data as stage 1 now makes it
  (official close at 16:15 / 13:15, puts down to K/S = 0.30).
- **The broken-quote rule** was developed in a separate experiment on the data
  before that rebuild. Its runs are not reported.
- **Earlier runs and code** (the first runs of 8 and 9 October 2026, the runs of
  23 and 25 October, the experiment, and copies of earlier versions of the code in
  a folder `old_versions/`) were removed from this repository on 29 October 2026.
  The code is in commit `150ce8a` and earlier. The code before the rebuild of the
  data is exactly the state of commit `4aca3ae` (tag `thesis-v1`).

## Labels in the comments

The comments refer to the author's review log (`review_log.md`, not included) and
to an inventory of the thesis numbers ("reproduction inventory, row ...", not
included). The labels that matter for the code:

- **C8**: at the snapshot after the stock close (16:15, 13:15 on early-close days)
  the stored index quote can be far from the official close. First fixed in the
  backtest (a switch `USE_OFFICIAL_CLOSE`, since removed), now in stage 1 (C15).
- **C9**: the option quotes at the stock-close snapshot (16:00, 13:00) are
  unreliable. Fixed by `SKIP_CLOSE_SNAPSHOT`.
- **C14**: option quotes broken for one snapshot. Fixed by `QUOTE_RULE`
  (`sec:broken-quotes` in the thesis).
- **C15**: the rebuild of the data: stage 1 stores the official close as the index
  level after the stock close and keeps puts down to K/S = 0.30 (was 0.45).
- Older result names carry these labels: `_c8c9` (stock-close rule), `q`
  (broken-quote rule), `_c15` (the rebuilt data).

## Random numbers

Everything is deterministic except three checks, which fix their seed with
`numpy.random.default_rng`: the bootstrap in `checks/chapter4_numbers.py` (seed 1),
the simulation in `checks/check_atm_bias.py` (seed 1), and the 2,000 random
example puts of the finite-difference test in `checks/check_greeks.py` (seed 0).

## Licence and citation

The code is released under the MIT licence (`LICENSE`). Please cite the thesis.
The version the thesis refers to is given there by its commit ID.
