# Validation of the code: summary (step 6, 2026-11-20)

The question: does the code do what the thesis says, without reading the code line
by line? Seven methods were chosen on 2026-11-14. Each test was
written from the `.tex` and `test_specification.md` alone. The code's logic was not
read to write a test.

**Result: no bug was found in the code.** Every number the thesis reports comes out
the same when checked. The only known departures from the thesis's exact rule are
two ties decided by floating-point rounding (below).

Details, scripts and outputs are in the folders named in the table.

## What was done

| Step | Method | What it checks | Scale | Result |
|---|---|---|---|---|
| 0 | Test specification (`test_specification.md`) | Every rule of the thesis written as a testable statement: 10 on formulas (F1–F10), 14 on the data pipeline (D1–D14), 35 on the strategy (S1–S35). Part G: 20 questions the thesis leaves open, answered by Arian. | | 5 of Arian's answers differ from the code. 3 decided as the code does it, 2 (G9, G11) as Arian said |
| 1 | Hand checks (`hand_checks/`), method 7 | A calculator written blind by a fresh session works out what the strategy must do at 32 snapshots (22 picked by rule branch, 10 at random). At 4 of them it rebuilds stages 1 and 2 from the raw quotes. | 32 snapshots, 239 fields | 237 fields the same, the decision the same at every snapshot. The 2 differences are one point (which day's margin earns interest on a day the position changes). Arian chose the code's reading (G21) |
| 2 | One-step check (`automatic/one_step_check.py`) | At every snapshot the position was held: the schedule, the broken-quote test and the exit decision. Every closed cycle. | 380,511 snapshots, 63,916 trade fields, four runs | All agree except the two ties (below) |
| 2 | Known answers (`automatic/formula_check.py`), method 1 | Black–76, Greeks, the illustrative numbers of the thesis. Every 10th stored row of 16 sample months of `Data/04_greeks`. | 4,275,742 rows | All hold. 4 rows flagged, all at the no-arbitrage limit within rounding |
| 2 | Invariants (`automatic/invariants_check.py`), method 4 | The daily equity of each run rebuilt from trades, quotes and the T-bill yield. Quarters and every cell of `tab:results-years`. S and dte. Stress threshold and flag, and the 30-day vol at each entry. | 132,300 equity fields, 236 quarters, 48 table cells, 2,204 entries | All agree |
| 2 | Metamorphic tests (`automatic/p15_vs_base_check.py`, `automatic/metamorphic/`), method 5 | Base and p15 must agree where the rules say so. Runs on changed copies of the data: prices × 2, bid = ask, data cut after 10 Mar 2020 (no look-ahead), random stress threshold, stage 2 rerun. | 148 paired cycles, 12 runs | 0 differences |
| 3 | Made-up markets (`automatic/synthetic/`), method 2 | Quotes made from known S, rates, dividend yields and smiles, with traps on every filter limit, run through stages 1, 2 and the ATM fit. A second, rough market with parity errors, a cubic smile and slices with 3 and 2 points. | 250,470 + 24,840 raw rows | 0 differences |
| 4 | Second implementation (`second_implementation/`), method 3 | A fresh session writes its own backtest from the thesis, never opening `Code/`, runs it on the full data and compares trade by trade. | 4 runs, 2,204 cycles, 3,675 days | Every cycle identical in all 27 fields, every day identical (largest difference 3·10⁻¹¹ dollars), every yearly return the same |
| 5 | Mutation tests (`automatic/mutation/`), method 6 | 71 small bugs planted at random, one per copy of the code, to measure the tests themselves. | 71 bugs | 43 caught at first. Of the 28 left, 21 cannot change any result. The 5 real gaps were closed with two new tests. Now 48 of the 50 bugs that can change a result are caught on two months of data. The other 2 only matter in situations those months lack. Reasoning (not run) says the one-step check and the second backtest would catch them on the full data |

## What was found

- **Two ties decided by rounding.** The data store deltas and prices with few
  decimals, so a value can sit exactly on a threshold. Twice in the four runs the
  floating-point result falls on the other side: base mid on 16 Nov 2012 (Δ_pos =
  Δ₀ + 0.10 exactly, so a loss exit by `def:exits`, but the code kept the position)
  and p15 crossing the spread in May 2014 (deficit exactly paid back, but 1.8·10⁻¹⁵
  left over). The second backtest decides both the same way as the code. Each
  changes the run from that point on. **Arian decides. Rerun? yes.**
- **The interest on a day the position changes** (G21): the margin held at the
  previous day's close earns it. This is what the code does. Decided by Arian. A
  sentence for `sec:cash` is planned.
- **G9 and G11** (a day without a position keeps the last margin; the broken-quote
  test compares with the last good quote): Arian's versions change nothing in any of
  the four runs, checked at every snapshot by the second backtest. There is no day
  without a position in any run.
- **The filter limits are inclusive** (K/S 0.30, 1.08, 0.97, 1.03, and 4 and 100
  days are kept). The thesis does not say.
- **The 10-day floor of the gamma exit never binds,** because every entry has at
  least 30 days, so τ₀/2 ≥ 15.
- **The stress flag is undefined on every early-close day** (no 15:45 snapshot).
  These are 32 of the 36 days without a 30-day vol. No decision depends on it.
- **The wording in `sec:broken-quotes`:** 95,122 is the number of held snapshots with
  both legs quoted. With the 22 snapshots where a leg was missing, the position was
  open at 95,144 snapshots.
- **Bugs in the test tools,** not in the code: the hand-check packets took "the day
  before" the first day from the end of the data (fixed). The first rough market
  priced a "no volatility" call at a price that does have one (fixed).

## Limits

- **How blind it was.** The tests were written without reading the code's logic. To
  run the code on copies, its interface was read: `Code/README.md` and the settings
  at the top of the scripts. The step-4 session never opened `Code/`, but it read
  the specification's section "Part G against the code", which names some of the
  code's choices. To sort the 28 mutants that got through, their lines in the code
  were read.
- **Tolerances.** In the known-answer test, two floating-point tolerances were added
  after the first run failed on rounding (with Arian's OK). Every other tolerance was
  fixed before the first run.
- **Mutation tests.** 71 bugs is a sample, run on two months of data (Feb–Mar 2020).
  Two of the 50 relevant bugs are caught only on the full data.
- **The thesis leaves some things open.** Where a test had to make a choice (e.g. the
  percentile convention, how the 30-day vol is interpolated), it is marked as a
  choice in the script.
- **Not tested:** `s09_vol_series.py` on made-up data (it needs 252 days of history).
  It is checked on the real data by `invariants_check.py` and `checks/check_vol30.py`.
  The figure scripts `s13` and `s14`.

## Open (Arian)

1. Fix the two ties (a tolerance of 10⁻⁹, or round to the data's decimals)
   and rerun. Best together with G9 and G11.
2. G9 and G11 into the code and the `.tex`. They change no number.
3. The G21 sentence for `sec:cash`, and maybe "with both legs quoted" in
   `sec:broken-quotes`.
4. Where the validation goes in the thesis (a short section, an appendix, or not
   at all).
5. Done 2026-11-20: `validation/` is in the code repository, the scripts and notes
   only. The data packets of the hand checks and every output (`.csv`, `.txt`) stay
   out, because the option data are licensed.
6. Delete the temp folders when done: `%TEMP%\masterarbeit_metamorphic` (3.8 GB),
   `masterarbeit_synthetic` (110 MB), `masterarbeit_synthetic_rough` (10 MB),
   `masterarbeit_mutation` (82 MB).
