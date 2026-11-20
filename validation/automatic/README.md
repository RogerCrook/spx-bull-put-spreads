# Automatic tests (step 2 of the code validation)

Written from the thesis and `validation/test_specification.md` only, without reading
`Code/`. Each test names the statement IDs it checks.

| File | What it checks | Run |
|---|---|---|
| `one_step_check.py` | At every held snapshot of the four reported runs: the schedule (S13, S19, S22), the broken-quote test and the exit decision (S7–S11, S20, S21, G1, G10, also under G11), and every closed cycle (S1, S6, S12, S15–S18, S24, S26). Reads `results/quotes_*`, `missing_*`, `trades_*` and the snapshot times of `Data/05_atm_vol.csv`. Writes `output/one_step_<run>.csv`. | 2026-11-17, 15 s |
| `formula_check.py` | Method 1, known answers. Part 1: the check's own Black–76 (written from the thesis) on made-up inputs: parity (F2), limits and monotone in σ (F3), Greeks against finite differences (F5), eq:entry-delta and 0.296 (F9), the credits 31.98 / 44.62 / 54.04 (F10), the delta of the 3,900 put in tab:validation, a textbook put (Hull, quoted from memory). Part 2: every 10th stored row of 16 sample months of `Data/04_greeks`: filters (D1), mid (D4), days (D5), price at the stored iv = mid and rows without iv (F4), stored delta / gamma / vega / theta with the chain rule and scalings (F5–F7), signs. Writes `output/formula_check.csv`. | 2026-11-17, about 10 min |
| `invariants_check.py` | Method 4 on the real outputs. Part A: the daily equity of each run rebuilt from the trades, the logged quotes and the 3-month T-bill yield (margin, realised and unrealised P&L at mid, interest on the previous day's margin, total and day P&L, deficit: S26–S28, G13, G14, G21, G9). Part B: quarters against `quarters_<run>.csv` and every cell of `tab:results-years` read from the `.tex` (S29, S30, index column from `Data/09_total_return`). Part C: S and dte in `Data/05_atm_vol.csv` (D2, D5). Part D: the stress threshold and flag in `Data/06_vol30.csv` and in each trade (D13, S32). Part E (added 2026-11-20): the 30-day vol recorded at each entry, recomputed from `Data/05_atm_vol.csv` (D13). Writes `output/invariants_check.csv`. | 2026-11-18, 46 s |
| `p15_vs_base_check.py` | Method 5 without a new run (S33). Wherever base and p15 open at the same snapshot with the same deficit, they must open the same position, and the cycle must end the same way unless base takes profit above Δ₀ − 0.15, where p15 must hold on (or exit on gamma there). Reads only the trade logs. Writes `output/p15_vs_base_check.csv`. | 2026-11-18, 1 s |
| `metamorphic/make_copies.py`, `run_on_copy.py`, `compare.py` | Method 5 with new runs. Builds changed copies of a data slice in the temp folder (`%TEMP%\masterarbeit_metamorphic`, about 3.8 GB, outside the project), runs the project's own code unchanged inside each copy (only its interface used: `Code/README.md` and the settings blocks, Arian 2026-11-18), and compares. T1 F8: stage 2 and the ATM fit on Jan 2012 with prices, strikes and S × 2. T2: the same rerun on the unchanged month against the project's files. T3 S34: backtest on Feb–Mar 2020 × 2. T4 S25: bid = ask. T5 S31/S23/D14: data cut after 10 Mar 2020. T6 S32: random 30-day vol and threshold. Writes `output/metamorphic_check.csv`. | 2026-11-18, copies 6.5 min, 12 runs about 15 min, comparison seconds |
| `synthetic/make_market.py`, `run_pipeline.py`, `check.py` | Method 2 (step 3). A made-up market with known S, rates, dividend yields and smiles, in the layout of the raw Cboe files, in `%TEMP%\masterarbeit_synthetic` (outside the project), with a truth file. Stage 1, stage 2 and the ATM fit run on it unchanged (interface only), and every output is compared with the truth (D1–D12, F5–F7). Writes `output/synthetic_check.csv`. | 2026-11-19, pipeline 31 s, check seconds |
| `synthetic/make_rough_market.py`, `check_rough.py` | Added 2026-11-20 after the mutation tests. A rougher made-up market (`%TEMP%\masterarbeit_synthetic_rough`): parity errors that differ by strike, a cubic smile, slices with exactly 3 and 2 points in the ATM band. The pipeline runs on it with `run_pipeline.py` (folder set by `CHECK_SYNTHETIC_FOLDER`), and the check works out the forward (D8) and the ATM fit (D11) by the rules. Writes `output/synthetic_rough_check.csv`. | 2026-11-20, pipeline seconds |
| `mutation/make_mutants.py`, `run_mutants.py` | Method 6 (step 5). Plants one small bug per copy of `Code/` (71 mutants drawn at random by Python's parser, seed 20261119, plus the unchanged copy m000) in `%TEMP%\masterarbeit_mutation`, and runs the tests on each: the synthetic market for the pipeline files, the one-step check, the invariants check and the metamorphic tests (on Feb–Mar 2020) for the backtest files. Writes `output/mutation_results.csv`. | 2026-11-19, about 1.5 h |
| `mutation/rerun_gaps.py` | The two new tests on the five mutants that survived the first run, and on the unchanged copy. Writes `output/mutation_gaps.csv`. | 2026-11-20, about 5 min |

## Result of `one_step_check.py` (2026-11-17)

- All 380,511 held snapshots (95,122 / 95,131 / 95,130 / 95,128 in base mid / base
  cross / p15 mid / p15 cross) get the decision the rule gives, and all 63,916 trade
  fields checked agree.
- Base mid counts equal the thesis: 95,122 held snapshots, 5 skipped for a broken
  quote, 22 with a leg missing, 5 leg quotes broken, 699 closed cycles.
- Two counts differ from `sec:broken-quotes`: 190,220 comparable leg quotes (thesis
  191,587) and 43 / 12 meeting condition 1 / conditions 1 and 2 (thesis 46 / 14).
  The script counts only held legs. The difference, 1,367 quotes, is likely the legs
  about to be opened (700 entries, 1,400 legs), which the quote log does not compare.
  Not verified.
- Under the G11 rule (last good quote) no decision changes, also not after the
  snapshots with a leg missing.
- **Two exact ties decided by floating-point rounding**: a loss exit
  not taken in base mid on 16 Nov 2012 11:30, and a deficit of 1.8·10⁻¹⁵ instead of 0
  in p15 cross that changed the expiry of the entry on 28 May 2014 12:15.
- The about 20,000 "S20 (edge)" rows per run in the output are noise: an unchanged
  quote makes condition 3 a tie (0 against 0) while condition 1 fails. A separate
  scan found no broken-quote tie that could change a decision. The script's edge flag
  should list only ties that can flip the outcome (not yet changed).

Not tested here: the choice of expiry and strikes at entry, the broken-quote test of
a put about to be opened, the deltas against Black–76, the daily equity file.

## Result of `formula_check.py` (2026-11-17)

- **Part 1** (the check's own Black–76): all pass. Parity to 7·10⁻¹³, `eq:entry-delta`
  to 5·10⁻¹⁵, the credits 31.9829 / 44.6209 / 54.0388 (thesis 31.98 / 44.62 / 54.04),
  2(N(2.3) − N(1)) = 0.295862, the `tab:validation` delta −0.302545 / −0.302536, Hull's
  put 1.1166 (book value 1.12, quoted from memory). The first run failed on three
  floating-point cases at the price limits (F3: a call worth exactly its lower limit
  "fell" by 4·10⁻¹³, a worthless call went from 0 to −5.5·10⁻¹⁴. F5: theta of a deep
  in-the-money call, −3.4·10⁻¹⁰, against a finite difference of 2.3·10⁻⁷). With
  Arian's OK two tolerances were then added to Part 1 only: F3 allows a fall of
  10⁻⁹, F5 passes a Greek within 10⁻⁶ absolute. The tolerances of Part 2 were not
  changed.
- **Part 2** (4,275,742 stored rows, every 10th row of 16 months): the filters (D1),
  the mid (D4), the days (D5), the round trip price at the stored iv = mid (F4), and
  delta, gamma, vega, theta with the chain rule and the scalings (F5–F7) hold on
  every row. 35,542 rows have no iv. 4 rows are flagged, all puts in the money
  whose mid lies within 0.00007 points of the lower limit D(K − F): three with an
  iv although the stored values put the mid on or just below the limit, one without
  an iv although they put it 0.00005 above. Rounding F and D to 6 decimals moves
  the limit by up to about 0.003 points, so the side cannot be decided from the
  stored values. Not errors. (The F4 bounds test has no rounding allowance, unlike
  the round trip. Not changed after seeing the result.)

## Result of `invariants_check.py` (2026-11-18)

- **Part A:** the daily equity of all four runs (14,700 days, 132,300 fields) rebuilt
  from the trades, the logged quotes and the 3-month yield equals the equity files
  in every field: margin, realised and unrealised P&L (at mid, also crossing the
  spread), interest on the previous day's margin at that day's rate with τ = 91/365,
  total and day P&L, deficit. No day ends without a position (so G9 never applies).
- **Part B:** all 236 quarters equal `quarters_<run>.csv`, and all 48 cells of
  `tab:results-years` (index, mid, cross, and the 2012–2026 row) are reproduced to
  the printed decimal. The index's per-year figure uses 3,675/252 years.
- **Part C:** on 2,160,637 rows of `Data/05_atm_vol.csv`, S is the same for every
  expiry of a snapshot, equals the recorded quote at every snapshot except the one
  after the close, where it equals the official close (3,675 snapshots, within
  0.005 points), and dte is the calendar days to expiry.
- **Part D:** every threshold and stress flag in `Data/06_vol30.csv` equals the 80th
  percentile (linear interpolation) of the 252 previous values. Stress days 19.72%
  (thesis 19.7%). The 24 flagged trades were entered on days without a row in
  `06_vol30.csv` (36 days: the 32 early-close days, which have no 15:45 snapshot,
  and 18 Jan, 15 Feb, 18 Apr, 16 May 2012). The script only looks the threshold up
  in the file. Recomputed separately as the percentile of the 252 days before the
  entry, all 24 agree to 3·10⁻¹⁷. Not errors. (The script itself is not changed.)

## Result of `p15_vs_base_check.py` (2026-11-18)

- No difference. At mid 84 cycles are opened by both runs at the same snapshot with
  the same deficit (35 more share the snapshot but not the deficit, not tested).
  Crossing the spread 64 (34). In each of the 148 the position is identical in all
  21 entry columns. 34 + 24 end the same with a loss, 1 + 1 the same with gamma, and
  in the other 49 + 39 base takes profit above Δ₀ − 0.15 and p15 holds on and exits
  later, as the rule requires. No base profit exit fell at or below Δ₀ − 0.15 (the
  base exit always comes at the first snapshot below Δ₀ − 0.10).
- The runs separate in the first cycle (3 Jan 2012, base takes profit at
  Δ_pos 0.173, above Δ₀ − 0.15 = 0.128), so no cycle is identical "from the start".

## Result of the metamorphic tests (2026-11-18)

Every comparison has 0 differences.

- **T1 (F8), stage 2 and the ATM fit with prices × 2:** on all 239,407 rows of Jan
  2012 the forward, strikes and prices are doubled, D, iv and delta unchanged, gamma
  halved, vega and theta doubled (to the 6 stored decimals), and on all 2,484 ATM
  slices the ATM vol is unchanged.
- **T2, reproducibility:** stage 2 and the ATM fit rerun on the unchanged month give
  exactly the project's `Data/04_greeks/spx_2012-01.csv` (4,309,326 fields) and its
  `Data/05_atm_vol.csv` rows.
- **T3 (S34), backtest with prices × 2 (Feb–Mar 2020, at mid and crossing):** the
  same 14 trades at the same snapshots, every amount in points or dollars doubled,
  every delta, iv, day count, reason and return unchanged, in the trades, equity,
  quarters, quote log and missing-leg log.
- **T4 (S25), bid = ask:** the run crossing the spread equals the run at mid in every
  file. (On the unchanged copy the two differ: −460.9 against −352.85 points, so
  the test can fail.)
- **T5 (S31, S23, D14), data cut after 10 Mar 2020:** the 11 trades closed by then,
  the 1,372 logged quotes and the 26 equity days up to then are identical. Nothing
  before a date depends on data after it.
- **T6 (S32), random stress inputs:** everything is identical except the stress
  columns of the trades (the threshold differs in 14 of 14 trades), so the stress
  indicator changes no decision.

Limits: T3–T6 use two months (14 trades per run), chosen to include the crash with
broken quotes and a missing leg. The p15 runs were not repeated on the copies. The
copies were deleted on 2026-11-19 (Arian). `make_copies.py` rebuilds them in about 6.5 min.

## Result of the synthetic market (step 3, 2026-11-19)

The market: three days in March 2031 (the third an early close), index 4,000 /
4,040 / 3,980, T-bill yields with a day missing, dividend yield 1.5% (SPX, SPXQ)
and 1.0% (SPXW), quadratic smiles in x = log(K/F) and one flat one, 9 expiries
(SPX and SPXW on the same date), 250,470 raw rows. Every price is Black–76 at the
true values, with bid and ask symmetric around it.

**0 differences.**

- **Stage 1 (D1, D2, D4, D5):** exactly the 105,122 rows the thesis's filters keep
  are kept. The limits are inclusive: puts at K/S = 0.30 and 1.08, calls at 0.97
  and 1.03, expiries 4 and 100 days away are kept, the next strike or day beyond
  is dropped. The binary root (29,049 rows), the quote with ask = bid and bids
  below 0.025 are dropped. S is the official close at the last snapshot of each
  day (the recorded quote there was 100 points off and is kept as `spot_quote`),
  the mid of the index quote elsewhere. dte and mid are right on every row.
- **Stage 2 (D3, D6–D10, F5–F7):** the SPXQ slice with only two call-put pairs gets
  no forward and is dropped (16,881 rows). On the 88,241 other rows the forward
  equals S·e^{(r−q)τ} (to 10⁻⁵ points; SPX and SPXW on the same date each get
  their own, 2.5 points apart), D = e^{−rτ} with r from the yields as `sec:rates`
  says (forward-filled day, 1-month rate below 30 days), the implied vol equals
  the σ that made the price, and the four Greeks equal Black–76 at the true values.
- **ATM fit (D11, D12):** on all 345 slices the ATM vol equals the smile's value at
  x = 0 (quadratic smiles) and σ for the flat one, to 10⁻⁵.

Not covered: the 30-day vol and the stress threshold (s09 needs 252 days of
history, checked on the real data in `invariants_check.py`), and the backtest
(the specification lists no synthetic statement for it). The folder stays in the
temp folder (about 110 MB).

## Result of the mutation tests (step 5, 2026-11-19)

71 planted bugs (30 in the backtest `s11`, 41 in the pipeline files `s01`, `s03`–`s08`),
one per copy. The unchanged copy m000 passed every test, so the harness itself
raises no false alarm. Full list with the line and the change:
`output/mutation_results.csv`.

**43 caught (38 by a test, 5 crashed the code), 28 survived.** Each survivor was
looked at in the code (only its line and the lines around it):

- **21 can change no result.** 9 sit in the demo blocks that run only when a file
  is started on its own (m012, m016–m018, m022–m024, m029, m030). 5 change only a
  printed counter or message (m035, m067, m069–m071). 1 changes the check of the
  settings at the start (m066). 2 give the same number: `<` vs `<=` at the 10⁻¹²
  floor of the volatility (m019), and × vs ÷ by `RECOVERY_FRACTION = 1.0` (m051).
  2 sit where the data never goes: the rate curve beyond 182 days (m010, every
  maturity is at most 100 days) and the margin of a day without a position (m063,
  no such day in any run). 1 writes pandas' row numbers into the stage-1 files as
  an extra column that stage 2 ignores (m006). 1 stores the stage-2 numbers with 7
  instead of 6 decimals (m031), more precise, not wrong.
- **2 would be caught on the full data, not on the two months the harness uses (argued, not run).** m064
  (a profit below 1 point counted as a loss in the deficit rule): 5 cycles in the
  full runs end with a P&L between 0 and 1 point (2 base mid, 1 base cross, 2 p15
  mid), and the one-step check recomputes the deficit after every cycle. m052 (when
  no expiry's credit covers the deficit, take the second-longest instead of the
  longest): the one-step check only checks that such an entry is at most 90 days
  away, but the blind second backtest (step 4) chooses the expiry itself and agrees
  on all 117 / 169 / 78 / 120 cap entries.
- **5 are real gaps.** Four in the pipeline, because the synthetic market is too
  clean: put-call parity holds exactly at every strike, so the forward is the same
  from 8 or 9 strikes (m013), and every smile is exactly quadratic with the same
  vol for calls and puts, so the ATM fit gives the same value with a band of 0.055
  instead of 0.05 (m036), with the calls left out (m038), and with at least 4
  instead of 3 points (m039). One in the backtest: the 30-day vol at entry
  (`vol30_entry`, written to every trade) computed wrongly (m054). No test checks
  that number itself, only the flag given the number. It changes no decision and
  no number in the thesis (the stress share 19.7% comes from `Data/06_vol30.csv`).
  The four pipeline points were confirmed by reading the code (CLAUDE.md §7: parity
  at the 8 nearest strikes, band 0.05, OTM only, at least 3 points).

Score: of the 50 bugs that can change a result, 43 caught by the tests (86%), 45
if the two argued to be caught on the full data are counted (90%, not run). Backtest alone: 20 of 23 measured.

**The five gaps closed (2026-11-20, Arian's OK).** Two tests were added:

- **A rough made-up market** (`synthetic/make_rough_market.py`, `check_rough.py`,
  in `%TEMP%\masterarbeit_synthetic_rough`, about 10 MB): one day, four SPX slices.
  "noisy" (30 days): the calls carry a parity error that differs by strike near
  the money, so the median of the 8 strikes nearest K₀ is 0.25 points away from
  that of 7 or 9. "cubic" (46 days): the smile has a cubic term, so a band of
  0.055 moves the ATM vol by 1.7·10⁻⁴ and leaving out the calls by 8.9·10⁻⁴
  (tolerance 10⁻⁵). "three" (65 days): strikes 100 apart, exactly 3
  out-of-the-money quotes in the band, so it must get an ATM vol. "two" (79 days):
  the same with the 4100 call priced 10 points above D·F, so it has no volatility,
  only 2 quotes are left and it must get none. (A first try priced that call at
  2,500 points: at 79 days a vol of about 72% gives that price, so the slice had
  3 points and the check rightly flagged it. The market was wrong, not the code.)
  The check works out the forward (D8, both ways of breaking a tie in distance)
  and the ATM fit (D11) with its own code from the rows stage 1 kept and the true
  F, D and σ. **On the project's code: 0 differences** (216 forwards, 81 ATM vols).
- **Part E of `invariants_check.py`:** the 30-day vol recorded at each entry
  (`vol30_entry`), recomputed from the ATM vols of the entry snapshot in
  `Data/05_atm_vol.csv`. The thesis says only "interpolated between the two listed
  expiries around it". The way (total variance σ²τ on a straight line, SPX and
  SPXW with the same days averaged) is taken from `checks/check_vol30.py`.
  **On the four runs: all 2,204 entries agree** (the 24 other differences of the
  run are the threshold rows on early-close days, as before).

`mutation/rerun_gaps.py` ran the new tests on the five mutants: **all five caught**
(m013 54 differences, m036 27, m038 54, m039 27, m054 28), and the unchanged copy
m000 passes both. Output: `output/mutation_gaps.csv`.

Score now: 48 of the 50 bugs that can change a result are caught on the two months
(96%), all 50 if the two argued above are counted (not run). The mutant copies stay in
the temp folder.
