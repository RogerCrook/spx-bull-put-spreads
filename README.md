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
| `experiments/quote_filter/` | the experiment in which the broken-quote rule was developed; its four runs are the ones reported in the thesis (see "Which code made the reported runs") |
| `old_versions/` | the backtest code behind two earlier sets of runs, which the thesis quotes once each |
| `Data/` | empty here; the expected layout is in `Data/README.md` |

## Data (not included)

The option data are licensed from Cboe and may not be passed on, and neither may
the files made from them (`Data/02_clean`, `04_greeks`, `05_atm_vol.csv`,
`06_vol30.csv`) or the backtest results. To rerun the pipeline you need:

1. **Cboe DataShop, "Option Quotes"**
   (https://datashop.cboe.com/option-quote-intervals): 15-minute intervals (900
   seconds), S&P 500 index options, without the "Calcs" columns, with the
   underlying bid and ask, every trading day from 3 January 2012 to 14 August 2026.
   One CSV file per day, 3,675 files, about 167 GB. Put them in
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
| 1 | `Code/s01_stage1_extract_simple.py` | `Data/01_raw_options/` | `Data/02_clean/`, one file per month (176 files, about 33 GB) | about 2 hours¹ |
| 2 | `Code/s02_check_coverage.py` (optional) | `Data/02_clean/` | nothing, counts the trading days | |
| 3 | `Code/s07_stage2_greeks.py` (uses `s03` to `s06`) | `Data/02_clean/`, `Data/03_treasury_bills/` | `Data/04_greeks/`, forward, implied vol and Greeks per quote (about 60 GB) | about 5 hours¹ |
| 4 | `Code/s08_atm_vol.py` | `Data/04_greeks/` | `Data/05_atm_vol.csv` | hours (not recorded) |
| 5 | `Code/s09_vol_series.py` | `Data/05_atm_vol.csv` | `Data/06_vol30.csv` (30-day vol and stress threshold) | |
| 6 | `checks/fetch_gspc.py` | Yahoo Finance | `Data/07_index_close/GSPC_daily.csv` | seconds |
| 7 | `Code/s10_entry_delta.py` | `Data/04_greeks/`, `Data/05_atm_vol.csv` | `entry_delta.csv` | |
| 8 | `Code/s12_run_variants.py base_mid base_cross p15_mid p15_cross` (runs `s11`) | `Data/03` to `07` | per run `trades_`, `equity_`, `quarters_`, `quotes_<run>_c8c9q.csv` | about 1 hour per run |
| 9 | `Code/s13_figure_smile.py` | `Data/04_greeks/` | the figure of the smile, `Masterarbeit Tex File from claude/figures/smile.pdf` | |

¹ From the times the first and the last output file were written, on the author's
machine.

Steps 7 and 8 write their files into the repository root. The check scripts expect
them in `results/`, so move them there.

## The backtest settings

The base case is set at the top of `Code/s11_backtest.py`. `Code/s12_run_variants.py`
runs the variants without editing that file: `base` and `p15` (profit exit at
Δ₀ − 0.15 instead of Δ₀ − 0.10), each at the mid quote (`_mid`) and crossing the
bid/ask spread (`_cross`). The variants `p0`, `t45` and `t60` are defined too. They
were fixed before any of them was run, and the thesis reports only `base` and
`p15`. The `p0` variant is invalid from 18 March 2020 (the long leg it holds is no
longer quoted).

Three switches handle problems in the data. All three are on in the reported runs:

| Switch | Default | What it does |
|---|---|---|
| `SKIP_CLOSE_SNAPSHOT` | `True` | no decision at the stock-close snapshot (16:00, 13:00 on early-close days), where the option quotes are unreliable |
| `USE_OFFICIAL_CLOSE` | `True` | at the snapshot after it (16:15, 13:15) the deltas use the official daily close instead of the stored index quote |
| `QUOTE_RULE` | `"on"` | skips broken option quotes (`"count"` only measures the test, `"off"` uses every quote) |

Output files carry a tag: `_c8c9` when either of the first two switches is on,
plus `q` when `QUOTE_RULE` is `"on"`.

## Check scripts

`checks/README.md` lists each script, what it computes and the thesis passages it
supports. They only read and print. Some read all of `Data/04_greeks/` (e.g.
`check_iv_failures.py`, about 9 minutes). The scripts on the backtest results need
the four reported runs in `results/`, and `chapter4_numbers.py` and
`check_close_snapshot.py` also need the earlier runs (see below).
`check_quotes_held.py` uses one more run as its control,
`checks/data/trades_ks125_kl230_mid_c8c9.csv` (not included): the base case with
the short put at `K1 = 1.25` instead of 1.0, at mid, without the broken-quote rule.
It comes from a strike-grid experiment that was later deleted, run with the code of
that time (`old_versions/backtest_2026-10-25_before_c14.py`). Whether a rerun with
that file and `K1 = 1.25` reproduces it has not been checked.

## Which code made the reported runs

- **The four reported runs** (`*_c8c9q`) were made by
  `experiments/quote_filter/backtest.py` in "on" mode (`run_on.ps1`) and copied to
  `results/`. `Code/s11_backtest.py` differs from it only in the paths, the
  comments, the default of `QUOTE_RULE` and the file tag. Rerun with
  `Code/s11_backtest.py`, base mid gave identical files (0 differing cells). The
  other three runs were not rerun with it.
- `experiments/quote_filter/` is kept as it was run: its scripts contain fixed
  paths on the author's machine (`C:/Dokumente/Python/Masterarbeit/`, in `MAIN`,
  `HERE`, `RESULTS`, `FOLDER` and `$here`) and the module names from before the
  renaming (`backtest.py`, `rates.py`, `greeks.py`, `volatility.py`). Its README
  records how the limits of the rule were fixed from the "count" runs before any
  "on" run was made.
- **The runs without the broken-quote rule** (`*_c8c9`, quoted once in the thesis):
  `old_versions/backtest_2026-10-25_before_c14.py` and
  `old_versions/run_variants_2026-10-25_before_c14.py`.
- **The runs without the end-of-day fix** (`trades_mid_latest`, `base_cross`,
  `p15_mid`, `p15_cross`, made 8 and 9 October 2026, quoted once in the thesis):
  `old_versions/backtest_2026-10-23_before_c8c9.py` and
  `old_versions/run_variants_2026-10-23_before_c8c9.py`. This is a copy saved on
  23 October 2026; that it is identical to the code of 8 and 9 October has not been
  checked.
- Both old versions use the folder and module names from before the renaming
  (`Greeks/`, `atm_vol.csv`, `import greeks`, ...). `Code/README.md` maps old
  names to new ones. In principle `Code/s11_backtest.py` with the switches off
  gives the same runs (`QUOTE_RULE = "off"` for `_c8c9`, and also
  `SKIP_CLOSE_SNAPSHOT = False`, `USE_OFFICIAL_CLOSE = False` for the earliest
  runs); this has not been checked by a rerun.

## Labels in the comments

The comments refer to the author's review log (`review_log.md`, not included) and
to an inventory of the thesis numbers ("reproduction inventory, row ...", not
included). The labels that matter for the code:

- **C8**: at the snapshot after the stock close (16:15, 13:15 on early-close days)
  the stored index quote can be far from the official close. Fixed by
  `USE_OFFICIAL_CLOSE`.
- **C9**: the option quotes at the stock-close snapshot (16:00, 13:00) are
  unreliable. Fixed by `SKIP_CLOSE_SNAPSHOT`.
- **C14**: option quotes broken for one snapshot. Fixed by `QUOTE_RULE`
  (`sec:broken-quotes` in the thesis).

## Random numbers

Everything is deterministic except three checks, which fix their seed with
`numpy.random.default_rng`: the bootstrap in `checks/chapter4_numbers.py` (seed 1),
the simulation in `checks/check_atm_bias.py` (seed 1), and the 2,000 random
example puts of the finite-difference test in `checks/check_greeks.py` (seed 0).

## Licence and citation

The code is released under the MIT licence (`LICENSE`). Please cite the thesis.
The version the thesis refers to is given there by its commit ID.
