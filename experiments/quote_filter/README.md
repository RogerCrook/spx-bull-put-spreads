# Experiment: a rule for broken option quotes (review_log C14)

Separate from the thesis pipeline (Arian, 2026-10-24): the main code and its results
are not changed. Only if Arian decides so does the rule go into the main
`backtest.py` (behind a switch), followed by a rerun and a thesis update.

## Why

Some option quotes in the data are broken for one snapshot, e.g. the SPX put 1990 on
2020-04-03 10:00, quoted 12.3 / 52.6 (mid 32.45, implied vol 46%) while it was 49–50
at 09:45 and 10:15 and the SPXW put of the same strike and expiry was 47.5 / 52.4.
Stage 2 turns such a mid into a meaningless implied vol and delta. In the thesis
runs this caused two false profit exits (base mid 390 / base cross 334; p15 cross
8), in the strike grid (an experiment, deleted 2026-10-26; the affected run is kept
in `checks/data/`) one false loss exit (2025-04-07 10:30). Details and the checks:
review_log C14, `checks/check_quotes_held.py`, `checks/check_quote_cases.py`.

## The rule

**Fixed 2026-10-25 (Arian), from the "count" runs only, before any "on" run:**
a leg's quote is **broken** when all three hold, compared with the same option at
the previous snapshot the backtest used (the stock-close snapshot is never used, C9):

1. its implied vol moved by more than **3 vol points** (absolute, `BROKEN_VOL_JUMP = 0.03`),
2. its bid/ask spread is more than **3 times** as wide as it was then
   (`BROKEN_WIDTH_RATIO = 3`), and
3. the quote **widened more than its mid moved**:
   (width now − width before) > |mid now − mid before|.

Only the past is used (the earlier check also used the next snapshot, which a
trading rule may not). A broken quote is treated like a missing one, as the backtest
already does when a leg is not quoted: while held, no exit test and no new mark;
at entry, the position is not opened at that snapshot. The next snapshot (15 minutes
later) takes over. Why all three: wide quotes alone are common and real around
10:00 data releases and 14:00 Fed announcements; a vol jump alone happens in real
fast markets, where the quote also widens; in a real move the whole quote shifts
(the mid moves more than the width grows), in a broken one a side runs away.

Known limits: a quote broken for two snapshots in a row passes at the second one
(it is compared with the broken one); a broken quote on an expiry that is only a
candidate in the maturity choice, not opened, is not tested.

## Steps

1. **Count** (`QUOTE_RULE = "count"`): the four thesis runs, with the test measured
   for every leg held or opened but nothing changed. The trades must equal the thesis
   runs (`compare_to_thesis.py`). Output `quotes_*_count_c8c9.csv`.
2. **Choose the two limits** from how often the rule would fire and whether it
   catches the known broken quotes, **without looking at any P&L**; write them here
   before step 3.
3. **On** (`QUOTE_RULE = "on"`): rerun the four runs with the limits; show old vs new.
4. Only if Arian agrees: the same lines into the main `backtest.py` (switch, own file
   tag), rerun, thesis update (`sec:data`, `sec:monitoring`, `tab:spec`; say that the
   rule was adopted after the broken quotes were found).

The strike grid (`experiments/strike_grid/`) was **not** rerun with the rule (Arian,
2026-10-24); on 2026-10-26 Arian had it deleted, together with the p15 follow-up
(`experiments/strike_grid_p15/`). Neither was ever in the thesis.

## Differences from the main code

| File | Difference |
|---|---|
| `backtest.py` | input paths point at the main folder (`MAIN`); `QUOTE_RULE`, `BROKEN_VOL_JUMP`, `BROKEN_WIDTH_RATIO`, `QUOTES_FILE`; functions `test_quote`, `quote_record`; in the main loop the test on held legs (step 1a) and on the legs to open, `puts_before` (the previous snapshot used); a column `skipped_broken` in the trades |
| `run_variants.py` | only the four thesis runs, in "count" mode (`base_mid_count` …) and "on" mode (`base_mid_on` …); writes `QUOTES_FILE` per run |
| `rates.py` | `FOLDER` points at the main folder's `TreasuryBills` |
| `greeks.py`, `volatility.py` | unchanged copies |

## Status

- 2026-10-24: folder created, copies of the main code (no main `.py` changed in the
  24 hours before), rule written; syntax checked, not run yet.
- 2026-10-25, step 1 done: the four "count" runs (`run_count.ps1`, logs in `logs\`,
  empty error logs) equal the thesis runs exactly (`compare_to_thesis.py`: 0
  differing cells, daily equity identical); about 191,000 quote rows per run.
- 2026-10-25, step 2 (no P&L looked at), proposal for Arian:
  `quote_rule_counts.py`: vol jump + width ratio alone also fire on real fast
  markets (March 2020, 2024-08-05 open: bid and ask moved together).
  `quote_rule_counts_2.py`: requiring the new quote to bracket the old one removes
  those, but misses the known 2012-06-14 15:30 case. `quote_rule_counts_3.py`: a
  third condition **"the quote widened more than its mid moved"**, with vol jump
  > 3 points and width > 3×, flags 3–5 snapshots per run; the ones at a decision
  are exactly the known/broken-looking cases (base: 2020-04-03 10:00; p15 mid:
  2015-10-28 14:00; p15 cross: 2012-06-14 15:30 and 2020-12-01 10:00), all
  profit exits on a blown-up quote.
  (`quote_rule_counts.py` counted an empty action as a decision, fixed in `_2`.)
- 2026-10-25: rule fixed by Arian as proposed (3 points, 3×, widened more than
  moved; see "The rule"), written here before the "on" runs.
- 2026-10-25, step 3 done: the four "on" runs (`run_on.ps1`, logs in `logs\`, empty
  error logs). Skipped snapshots (`list_skipped_on.py`): base mid 5, base cross 4,
  p15 mid 4, p15 cross 3, no entry refused. They are the cases found in step 2
  (2020-04-03 10:00; 2012-06-14 15:30; 2015-10-28 14:00; 2020-12-01 10:00;
  2022-12-14 14:00), the two snapshots right after the March 2020 trading halts
  (2020-03-09 and 03-16 10:00, no decision there, no trade changed by them), and one
  new one in p15 mid on the changed path (2015-12-16 14:00, FOMC: put 1665 4.0 / 4.9
  → 3.3 / 10.0). Old vs new (`compare_on.py`, same formulas as
  `checks/thesis_numbers.py`):

  | run | %/yr old → new | 2012–18 | 2019–26 | total $ | trades changed (old / new) |
  |---|---|---|---|---|---|
  | base mid | 38.4 → 37.9 | 39.9 → 39.9 | 37.9 → 37.2 | 234,648 → 231,012 | 10 / 10 |
  | base cross | 2.5 → 2.8 | −22.8 → −22.8 | 11.6 → 12.0 | 15,600 → 17,421 | 12 / 11 |
  | p15 mid | 32.7 → 32.5 | 32.0 → 31.1 | 32.9 → 32.9 | 215,531 → 213,936 | 8 / 12 |
  | p15 cross | 8.7 → 9.5 | −7.9 → −6.5 | 14.5 → 15.1 | 58,038 → 63,861 | 66 / 65 |

  The trade 2020-03-24 (put 1990): mid +46.0 at the false exit → +37.1 three days
  later; cross +2.0 → +33.4 (the false exit had closed at the broken ask). "Trades
  changed" includes the knock-on effect: after one exit moves, the following entries
  move too, until the chain falls back onto the old one (p15 cross: 2012-06 to
  2013-12 and 2020-12 to 2022-01). p15 test (cross, monthly): mean +0.49 → +0.55 pp,
  t 1.62 → 1.69, 89 → 88 months ahead, bootstrap (seed 1) 4.8% → 4.3% behind,
  interval −0.06 to +0.89 → −0.05 to +0.98: still not significant at 5%, if only just.
  Unchanged: worst quarter of every run, negative quarters, cost share 11.0%, Δ₀
  quantiles, months profitable 109 of 176. Next (step 4): Arian decides.
- 2026-10-25, step 4 (Arian: yes): the rule is in the main `backtest.py`
  (`QUOTE_RULE = "on"` by default, file tag `_c8c9q`; differs from this copy only in
  the paths, comments, the default and the tag) and `run_variants.py`; the four "on"
  runs were copied to `results/*_c8c9q.csv` and are in the thesis
  (`sec:broken-quotes`). Base mid was rerun with the main code as a check: trades,
  equity, quarters and quotes identical to the "on" run, 0 differing cells
  (`checks/compare_confirm_c14.py`; files in `confirm_main/`).
