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
`reproduction_inventory.md`, not in the code repository). The scripts were rewritten in that style on 2026-10-27 (the versions before were
removed on 2026-10-29); `chapter4_numbers.py` replaces two of the earlier scripts
(`verify_tex_c14.py`, `thesis_numbers.py`).

Removed on 2026-10-29 (Arian), because no thesis number comes from them: the four
scripts `check_entry.py` (the daily 10:00 entry-delta study, replaced by
`entry_delta_backtest.py`, review_log T63), `check_quotes_held.py` (the held-leg
quote screen that found the broken quotes; its 10:00 / 14:00 claim left the thesis
with T56), `check_put_window.py` (the count behind the choice of the put window,
C15) and `check_missing_legs.py` (why a leg was missing; the count of 22 snapshots
comes from `chapter4_numbers.py`), the folder `data/` (the control run of
`check_quotes_held.py`) and the folder `review_2026-10/` (the review tools of
22–28 October and the printouts of the C15 checks, `c15_outputs/`). None of them
was in the code repository except the four scripts, which are in commit `150ce8a`
and earlier.

Without the thesis `.tex` (not in the code repository), `chapter4_numbers.py` still
computes every number but marks the "in the thesis" column with "?".

Since 2026-10-28 the scripts that read backtest results read the current runs in
`results/` (made 2026-10-28 on the rebuilt data, plain names such as
`trades_base_mid.csv`): `chapter4_numbers.py`, `check_broken_quotes_tex.py`,
`credit_by_maturity.py`, `check_vol30.py`, `entry_delta_backtest.py` and, since
2026-10-29, `check_close_snapshot.py` (the two base-case runs without the
stock-close rule; until then the first runs of 2026-10-08, since removed). Until
2026-10-28 the result files carried review_log item numbers (`_c8c9`, `_c8c9q`,
`_c15`).

## Scripts behind thesis numbers

| Script | What it computes | Thesis passages | Inventory row |
|---|---|---|---|
| `chapter4_numbers.py` | every backtest number of ch. 4 and `tab:costs`, for the reported runs and for the runs without the broken-quote rule, plus the base-case return per year without the stock-close rule, each with "in the thesis: yes/-" | `tab:results-base`, `tab:results-years`, `tab:costs`, `tab:losses-months`, `tab:losses-rules`, `tab:p15`, `tab:p15-test`, text of `sec:results-main`, `sec:robustness`, `sec:backtest-design`, the returns in `sec:monitoring` and `sec:broken-quotes` | 24, 26, 27, 28, 31–34 |
| `check_broken_quotes_tex.py` | held and skipped snapshots, refused entries, how often the conditions of `def:broken` hold, the example quotes (3 Apr 2020 at 10:00 and 10:15, 5 Aug 2024), the first trade the rule changes; margins 2012 / 2026, forward first / last cycle (since 2026-10-29 without the distribution of the two measures and the compounding count, which left the thesis with T56 and T61) | `sec:broken-quotes`, `sec:backtest-design`, text after `tab:costs` | 25, 27, 28 |
| `entry_delta_backtest.py` | the entry delta Δ₀ of the backtest's own entries (base mid, base cross for comparison): statistics, histogram, by maturity rule and year, strikes vs targets, distances to an absolute band [0.20, 0.40] (added 2026-10-28, T63) | `sec:realised-entry-delta`, `tab:entry-delta-stats`, `tab:entry-delta-hist`, "Consequence for the band", "averages 0.27" after `prop:entry-delta` | — |
| `check_greeks.py` | stored Greeks recomputed on all quotes of 5 days; Greek formulas against finite differences | `sec:iv-impl` (since 2026-10-28, T62; before `sec:realised-entry-delta`) | 30 |
| `check_s_close.py` | quoted index midpoint at the last and at the stock-close snapshot against the official close | `sec:data` | 12 |
| `check_vol30.py` | 30-day vol and stress threshold rebuilt, stress share, the example days | `sec:stress` | 11 |
| `check_forward.py` | forwards rebuilt on 17 days; SPX vs SPXW, by time of day | `sec:monitoring` | 22 |
| `check_close_snapshot.py` | the two base-case runs without the stock-close rule: exits and spread cost at 15:45 / 16:00 / 16:15 | `sec:monitoring` | 23 |
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

The C15 rerun (2026-10-27) was verified with review tools that were in
`review_2026-10/` (removed 2026-10-29, see above): `test_c15_stage1_days.py` (the new
stage 1 on four days against the old cleaned data) and `compare_c15.py` (old against
new data, row by row, for stage 1, stage 2, the ATM file and the 30-day vol file).
The review log names the other review tools and their printouts where they were
used.

Not in this folder but also behind thesis numbers: the pipeline scripts in `Code/`
(e.g. `s09_vol_series.py` for the 19.7% stress share, `s13_figure_smile.py` for
`fig:smile`, `s11_backtest.py` and `s12_run_variants.py` for the runs in
`results/`).
