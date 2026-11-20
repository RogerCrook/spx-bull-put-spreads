# Open questions: the choices of the second implementation

Written before the comparison with the project's backtest, from the thesis and
`validation/test_specification.md` (Part G) only. Each item is a detail the thesis
and Part G leave open, the choice made in `backtest.py` (marked `# CHOICE` there),
and why.

| No. | Rule | Open detail | Choice in `backtest.py` |
|---|---|---|---|
| C1 | `def:entry`, G2 | Exact tie between two listed strikes, equally near the target | Take the lower strike. Ties are counted (`strike_ties` in `summary.txt`). |
| C2 | `def:tau-star`, G7 | Is τ₃₀ "the shortest listed expiry of at least 30 days" or "the shortest usable one"? | The shortest usable one: an expiry without forward, ATM vol or snappable strikes is skipped before τ₃₀ is fixed. |
| C3 | `def:tau-star` | Which root if the longest expiry of at most 90 days is listed under two roots on the same date (cap case)? | The first root in name order (SPX, SPXQ, SPXW), as G4 does for τ₃₀. |
| C4 | `def:tau-star` | L > 0 and τ₃₀ itself is above 90 days, so no expiry of 30 to 90 days exists | Take τ₃₀, rule `cap_none_below_90`, counted (`cap_without_expiry`). Expected never to happen. |
| C5 | `def:tau-star`, G6 | Are the credits c(τ) required to be positive? | No. In the runs crossing the spread a spread with bid of the sold put below the ask of the bought put would still be a candidate. |
| C6 | `def:tau-conv` | τ of a candidate expiry | The `dte` of `Data/05_atm_vol.csv` (calendar days), floored at 1, divided by 365. |
| C7 | `def:broken`, G11 | A put about to be opened that has no earlier quote at all (newly listed) | It cannot be tested, so it counts as not broken. |
| C8 | `def:broken`, G11 | How far back to look for the last good quote of a put about to be opened | Through the current and the previous month. A quote without a volatility is not a reference. Quotes judged broken earlier in the same run are skipped. |
| C9 | `def:broken`, G11 | A held leg at a snapshot where the other leg is missing or broken | Each quoted leg is tested on its own. A leg found good becomes the new reference even if the snapshot is skipped because of the other leg. |
| C10 | `def:broken`, G11 | Reference of the legs just after entry | The entry quotes themselves (they were tested at entry). |
| C11 | `sec:monitoring`, G20 | Which days are early-close days | Read from the data: a day whose last snapshot is 13:15 or earlier. Its stock close is 13:00, otherwise 16:00. The list found is printed in `summary.txt` (the thesis says 32). |
| C12 | `def:stress`, G16 | Which value of the stress flag is recorded on a trade | The daily `stress` column of `Data/06_vol30.csv` on the entry date. It changes no decision. |
| C13 | `sec:cash`, G14 | The 3-month rate as a continuous rate | `eq:rate-conversion` with τ = 91/365 (the 3-month point of the rate curve), the yield forward-filled over days without a value. |
| C14 | `sec:results-main`, G13 | A day on which a held position has no usable snapshot at all | Its value stays at the last usable mark (of an earlier day), so its unrealised P&L that day is zero. |
| C15 | `sec:backtest-design` | A position whose leg stays missing until expiry | Not handled (no rule in the thesis). It would stay open; none occurred if `summary.txt` shows no such position. |
| C16 | `def:exits` | Days to expiry for the gamma test | The `dte` of the sold put's row at t (calendar days, whole), compared with max(τ₀/2, 10) in days (G10). |
| C17 | trade log | The position still open at the end (G18) | Not written as a trade (only closed cycles are). It is valued in the daily file and named in `summary.txt`. |

## After the full run and the comparison (added 2026-11-19)

Which choices were ever needed in the four runs:

- Never needed: C1 (no strike tie), C4 (no expiry missing below 90 days), C7 and C8
  in any case that mattered (no entry refused for a broken quote), C15 (no position
  stuck).
- C9 was needed once (p15_mid, 16 March 2022 14:00, a broken sold put at a snapshot
  where the bought put had no quote). No effect: the snapshot is skipped either way.
- C12 differs from the project (which takes the flag at the entry snapshot) on 18 to
  33 trades per run. Only a record, no effect on any decision. It stays open with G16.
- C11 found the 32 early-close days of `sec:data`.

The other choices are the same as the project's, as far as the identical results
show. No question raised by the comparison needs Arian's answer before the thesis
can rely on the backtest. Two points for Arian (see `README.md`): the stress flag is
undefined on every early-close day (G16), and the wording "95,122 snapshots with an
open position" in `sec:broken-quotes`.
