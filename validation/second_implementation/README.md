# Second implementation of the backtest (validation method 3)

Done 2026-11-19 (step 4 of the validation). An independent backtest, written from the
thesis and `validation/test_specification.md` alone, run on the full data and only
then compared with the project's backtest, cycle by cycle and day by day.

## Result

**The two backtests agree completely.** In all four reported runs every cycle is the
same in all 27 compared fields, and every trading day is the same in margin,
interest, P&L and open P&L (largest daily difference 3·10⁻¹¹ dollars, rounding).

| Run | Cycles (ours / project) | Identical cycles | First divergence | Days identical | Return a year, ours / project |
|---|---|---|---|---|---|
| base_mid | 699 / 699 | 699 (100%) | none | 3,675 of 3,675 | 37.88 / 37.88 % |
| base_cross | 631 / 631 | 631 (100%) | none | 3,675 of 3,675 | 2.75 / 2.75 % |
| p15_mid | 451 / 451 | 451 (100%) | none | 3,675 of 3,675 | 32.46 / 32.46 % |
| p15_cross | 423 / 423 | 423 (100%) | none | 3,675 of 3,675 | 9.54 / 9.54 % |

The return of every year agrees to two decimals in all four runs (`comparison.txt`),
and so does every value of `tab:results-years` and `tab:p15-years`.

The 27 fields: exit time, root, expiry, days to expiry at entry and exit, maturity
rule, forward, ATM vol, both target strikes, both strikes, both implied vols at entry
and at exit, credit at execution and at mid, entry delta, exit reason, exit delta,
cost to close at execution and at mid, P&L in points, deficit before and after,
margin. The entry time is the key the cycles are lined up by. Numbers count as equal
within 10⁻⁶; the largest difference found in any field is 0.

**Negative control** (that `compare.py` can see a difference at all): our base case
at mid against the project's run without the broken-quote rule. It finds 689 of 708
cycles identical and the first divergence at the cycle opened 24 March 2020, which
the run without the rule closes at 10:00 on 3 April 2020 on the broken 1990 put, the
example of `sec:broken-quotes`.

## Other agreements

- **Broken quotes.** The snapshots skipped as broken are the same in all four runs
  (5 / 4 / 4 / 3), on the same legs. The one extra broken quote of our p15_mid run
  (SPX 3870 put, 16 March 2022 14:00, quoted 8.5 / 24.4 between 23.8 / 24.1 and
  30.3 / 30.9) is at a snapshot where the other leg had no quote, so both backtests
  skip it anyway, and the next quote passes the test under both rules.
- **Missing legs.** Snapshots with a leg missing: 22 / 13 / 14 / 16, the same as the
  project's `missing_<run>.csv`. 22 is the number in `sec:backtest-design`.
- **Early-close days.** Found from the data: 32, the number in `sec:data`.
- **Counts of the thesis.** Base mid: 95,117 snapshots tested + 5 skipped as broken =
  95,122, the number in `sec:broken-quotes`. Every label count (maturity rule, exit
  reason) agrees.

## The two rules where Arian's answer differs from the code (G9, G11)

This implementation follows Arian's answers, the project's code the other way.

- **G9** (a day that ends with no position counts the last margin): no such day
  occurs in any run, here as there. No effect.
- **G11** (compare with the last good quote of the same put): no effect in any of
  the four runs, now checked for every snapshot, including the ones after the 22
  with a leg missing that Part G still listed as unchecked. The skipped snapshots
  and all trades are the same.

So the code change planned for G9 and G11 would not change any reported number.

## Differences that are not divergences

- **Stress flag** (recorded only, changes no decision, G16 deferred). We record the
  day's flag of `Data/06_vol30.csv` (at 15:45). The project evaluates it at the
  entry snapshot. They differ on 33 / 23 / 18 / 24 trades. Not compared in the 27
  fields for that reason.
- **Names.** Our maturity rule "base" is the project's "target".
- **Strike ties** (G2): ours takes the lower strike, the code the first in the
  data's order. No tie occurred in any run.

## Bugs

None found in either implementation. Everything the comparison could see agrees.

## Side observations (not bugs in the backtest)

1. The 36 trading days without a 30-day volatility (`sec:stress`) are exactly the 32
   early-close days, which have no 15:45 snapshot, plus 2012-01-18, 2012-02-15,
   2012-04-18 and 2012-05-16. So the stress flag is undefined on every early-close
   day. It changes no decision, but it belongs to G16.
2. `sec:broken-quotes` says the rule "skips 5 of the 95,122 snapshots with an open
   position". 95,122 are the snapshots with both legs quoted. With the 22 snapshots
   where a leg was missing, the position was open at 95,144 snapshots after entry.
   The wording may need "with both legs quoted".

## How blind it was

Before the outputs were written, only the thesis, the test specification, `CLAUDE.md`
and the data were read, as the brief allowed. `Code/` was never opened. One limit: the
section "Part G against the code" of the test specification describes some of the
code's choices (e.g. G2, G7, G13, G14 and the function names), and it was read before
the implementation. Where a detail was left open, the choice is marked `# CHOICE` in
`backtest.py` and listed in `open_questions.md`.

## Files

| File | What it is |
|---|---|
| `backtest.py` | the second implementation, all four runs in one pass over `Data/04_greeks/` (about 20 min) |
| `compare.py` | the comparison with `results/`, writes `comparison.txt` |
| `open_questions.md` | the choices made where the thesis and Part G leave a detail open |
| `output/` | `trades_<run>.csv`, `equity_<run>.csv`, `summary.txt` of the full run |
| `output_test_2012-01_2012-02/`, `output_test_2020-03_2020-04/` | the two test runs (not comparable to the project's runs: they start with no deficit) |
| `full_run_log.txt` | the printout of the full run |
| `comparison.txt` | the full report of `compare.py` |

Run from the main folder: `python validation/second_implementation/backtest.py`, then
`python validation/second_implementation/compare.py`.
