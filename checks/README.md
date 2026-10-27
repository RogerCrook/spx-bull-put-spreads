# Check scripts (provenance of the numbers in the thesis)

Read-only scripts that compute, from the data or from the backtest results, the
numbers the thesis reports, or that check the pipeline code against the thesis.
They only read and print; none of them writes into the project. Some read large
parts of `Data/04_greeks/` and take several minutes.

**Run every script from the main folder**, e.g. `python checks/check_sample_day.py`:
all paths (`Data/...`, `results/...`) are relative to it.

Since 2026-10-27 this folder holds only the scripts behind numbers in the thesis,
all written in the style of `Code/s03_rates.py` (simple steps, a comment on almost
every line). Which thesis passage each one supports is listed below (the
"inventory row" refers to the author's list of the thesis numbers,
`reproduction_inventory.md`, not in the code repository). The review tools of
22–27 October that no thesis number depends on are in `review_2026-10/` (not in the
code repository). The versions of ten scripts from before the style rewrite are in
`old_versions/checks_before_style_2026-10-27/` (not in the code repository);
`chapter4_numbers.py` replaces two of them (`verify_tex_c14.py`, `thesis_numbers.py`).

`data/trades_ks125_kl230_mid_c8c9.csv` is the one file kept from the strike-grid
experiment when it was deleted (2026-10-26, Arian): the run K1 1.25 / K2 2.3 at mid,
which contains the broken quote of 2025-04-07 10:30. `check_quotes_held.py` uses it
as its control (the check must flag that quote). Copied unchanged. Not in the code
repository, because it is backtest output (Cboe prices).

Without the thesis `.tex` (not in the code repository), `chapter4_numbers.py` still
computes every number but marks the "in the thesis" column with "?".

## Scripts behind thesis numbers

| Script | What it computes | Thesis passages | Inventory row |
|---|---|---|---|
| `chapter4_numbers.py` | every backtest number of ch. 4 and `tab:costs`, for the reported runs and for the two earlier sets of runs (without the broken-quote rule, without the stock-close rule), each with "in the thesis: yes/-" | `tab:results-base`, `tab:results-years`, `tab:costs`, `tab:losses-months`, `tab:losses-rules`, `tab:p15`, `tab:p15-test`, text of `sec:results-main`, `sec:robustness`, `sec:backtest-design`, `sec:realised-entry-delta`, the returns in `sec:monitoring` and `sec:broken-quotes` | 24, 26, 27, 28, 31–34 |
| `check_broken_quotes_tex.py` | broken-quote distributions, the two example quotes, skipped snapshots; compounding artefact, margins 2012 / 2026, forward first / last cycle | `sec:broken-quotes`, `sec:backtest-design`, text after `tab:costs` | 25, 27, 28 |
| `check_quotes_held.py` | every held-leg quote of the four runs before the rule: width and vol spikes; flags by time of day (10:00, 14:00) | `sec:broken-quotes` | 25 |
| `check_entry.py` | every figure of the realised entry delta from `results/entry_delta.csv`; 12 days rebuilt | `sec:realised-entry-delta`, `tab:entry-delta-stats`, `tab:entry-delta-hist`, after `prop:entry-delta` | 6, 29 |
| `check_greeks.py` | stored Greeks recomputed on all quotes of 5 days; Greek formulas against finite differences | `sec:realised-entry-delta` | 30 |
| `check_s_close.py` | quoted index midpoint at the last and at the stock-close snapshot against the official close | `sec:data` | 12 |
| `check_vol30.py` | 30-day vol and stress threshold rebuilt, stress share, the example days | `sec:stress` | 11 |
| `check_forward.py` | forwards rebuilt on 17 days; SPX vs SPXW, by time of day | `sec:monitoring` | 22 |
| `check_close_snapshot.py` | runs without the stock-close rule: exits and spread cost at 15:45 / 16:00 / 16:15 | `sec:monitoring` | 23 |
| `credit_by_maturity.py` | illustrative Black–76 credit at 30 / 60 / 90 days and κ; measured credit by maturity rule | `rem:credit-size` | 9, 10 |
| `check_formula_values.py` | factor N(d1)/N(−d1); round trip; finite-difference delta (example inputs, no data) | `rem:atm-otm`, `tab:validation` | 1, 21 |
| `check_expiry_count.py` | expiries listed on 28 Sep 2012 and 28 Jul 2026 | `sec:data` | 13 |
| `check_sample_day.py` | 8 Jun 2021: near-money vols, slices, points per ATM fit, fitting window | `sec:iv-impl`, `rem:atm-band` | 18, 19 |
| `check_root_forwards.py` | SPX vs SPXW forwards on 1 and 5 Aug 2024 | `tab:validation` | 21 |
| `check_ohlc_zeros.py` | share of raw rows with OHLC all zero, first trading day of each month | `sec:cleaning` | 14 |
| `check_iv_failures.py` | quotes without an implied volatility over all of `Data/04_greeks/` | `sec:iv-impl`, `rem:bisection` | 15 |
| `check_forward_error.py` | single-strike parity error by distance from the money, raw quotes, 8 Jun 2021 10:00 | `sec:forward-impl` | 17 |
| `check_atm_bias.py` | bias and noise of the ATM fit on the one-sided window (simulation, stated inputs) | `rem:atm-band` | 20 |
| `check_validation_day.py` | call vs put vol, smile shape, where the Greeks peak, on the two `fig:smile` slices | `tab:validation` | 21 |
| `fetch_gspc.py` | downloaded `Data/07_index_close/GSPC_daily.csv` (Yahoo ^GSPC) on 2026-10-22 | data source of `sec:data` | 12 |

Not in this folder but also behind thesis numbers: the pipeline scripts in `Code/`
(e.g. `s09_vol_series.py` for the 19.7% stress share, `s10_entry_delta.py` for
`results/entry_delta.csv`, `s13_figure_smile.py` for `fig:smile`, `s11_backtest.py`
and `s12_run_variants.py` for the runs in `results/`).

## `review_2026-10/`: review tools, no thesis number depends on them (not in the code repository)

| Script | What it checked | Recorded in |
|---|---|---|
| `check_stage1.py` | stage 1 filters re-applied on 4 sample days | review_log_archive (2026-10-22), C8 |
| `check_rates.py` | `rates.py` vs `sec:rates`, stored D reproduced | review_log_archive (2026-10-22) |
| `check_iv.py` | `volatility.py` re-implemented, stored iv, inversion failures on sample days | review_log_archive (2026-10-22), T8 |
| `check_atm.py` | `atm_vol.py` re-implemented on 9 days | review_log_archive (2026-10-23) |
| `check_trades.py`, `check_trades_c8c9.py` | rule checks on all trades of the 4 runs (old, `_c8c9`) | review_log_archive (2026-10-23) |
| `check_cycles.py` | 12 cycles re-simulated from scratch | review_log_archive (2026-10-23) |
| `check_d4.py` | carry ratio F/S at the last snapshot (D4) | review_log C8 |
| `check_missed.py` | triggers missed at the last snapshot because of C8 | review_log C8 |
| `check_1615_exits.py` | what the 16:15 exits would do at 09:45 next day | review_log C8 |
| `runner.py` | test harness for the C8/C9 code on 3 months | review_log (2026-10-23) |
| `compare_runs.py` | old vs new key figures of the 4 runs | review_log (2026-10-23) |
| `thesis_numbers_2.py`, `verify_tex.py` | ch. 4 numbers of the `_c8c9` runs and their check against the `.tex` (superseded by `chapter4_numbers.py`) | CLAUDE.md §6 |
| `check_f_1615.py` | F and σ_atm at 16:15 on the broken-S days | review_log C13 |
| `check_quote_20250407.py` | the broken 3975 put quote on 2025-04-07 10:30 | review_log C14 |
| `check_broken_exits.py` | first screen for exits at a too-high short-put quote (superseded by `check_quotes_held.py`) | review_log C14 |
| `check_atm_spikes.py` | σ_atm spikes at every entry of the 4 runs (0 at entry) | review_log C14 |
| `check_quote_cases.py` | the two broken quotes at a thesis decision, with neighbours | review_log C14 |
| `compare_confirm_c14.py` | base mid rerun with the main backtest against the experiment's run, cell by cell | backtest_status.md (C14), reproduction_inventory N1 |
| `compare_numbers_tex.py` | every number in a backup `.tex` against the current one (guard for rewrites) | review_log T39 |
| `check_reorg_paths.py` | after the 2026-10-27 reorganisation: paths in `Code/` exist, modules load | review_log T41 |

These keep their fixed `C:/Dokumente/...` paths and their original style.
