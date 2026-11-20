# Open questions of the blind calculator (2026-11-16)

`calculator.py` was written from the thesis and Part G of
`validation/test_specification.md` only, without the backtest code, its logs or the
answer key. Below is every point where neither the thesis nor Part G decided
something, so the calculator had to choose. Each one is marked `CHOICE` in the code.
These are findings: where the backtest chose differently, the comparison will show a
difference that is not a bug in either.

"Matters here" says whether the choice changed or could have changed an answer in
the 32 checks.

## A. The strategy

| No. | Point | Calculator's choice | Matters here |
|---|---|---|---|
| A1 | G11, a quote at a snapshot that was skipped because the **other** leg was missing or broken: is it a "good" quote for the next comparison? | Yes. G11 says "the last quote of the same put that was not broken", and this quote was not broken. (The literal `def:broken`, "the previous snapshot at which the backtest took a decision", would skip it.) | H27 (9 Mar 2020 10:15): the sold put is compared with 10:00 (where only the bought put was broken), not with 6 Mar 16:15. Both comparisons give "not broken", so the answer is the same. |
| A2 | G11 for the first quote in reach: the packet goes back only to 09:45 of the day before. | The first usable quote of each put in the packet counts as good without a test. | No: no check snapshot depends on it. |
| A3 | G11 for the legs of a **new** position: each must be compared with its own last good quote, but `puts.csv` holds only the snapshot itself, so the packet has no history of the new puts. | Not tested. The calculator assumes the new legs are not broken and says so in step 5e. | Possibly at all 13 snapshots with an entry. Needs either earlier quotes in the packet or the comparison done by the other session. |
| A4 | G2, a tie in snapping (two listed strikes equally near the target). | The lower strike, and the tie is printed. | No tie occurred. |
| A5 | G7 + `def:tau-star`: if the shortest expiry with 30 days or more cannot be used, what is τ₃₀ (for the target rule and for c(τ₃₀) in the recovery rule)? | The next usable expiry in the order of G4 becomes τ₃₀. | No expiry was skipped at any entry. |
| A6 | The cap of `def:tau-star`, "the longest listed maturity of at most 90 days": must it be usable (G7)? Two roots on that date? | The longest **usable** expiry of 30 to 90 days. On the same date the first root of G4 (SPX, SPXQ, SPXW). | The two cap entries (H05, H16) had one root on the longest date. |
| A7 | Names of the maturity rules. | `target` (L = 0), `recovery` (some τ qualifies), `cap` (none qualifies). The backtest's labels may differ in wording. | Wording only. |
| A8 | The gamma-exit day: the calculator has no list of trading days. | The calendar date expiry − ⌊max(τ₀/2, 10)⌋, moved to the Monday if it falls on a weekend. If it is a market holiday, the exit is on the next trading day, which the calculator cannot see. | Check the reported dates against holidays by hand. |
| A9 | `def:tau-conv` counts days "to T". Before about 2015 the data list the SPX monthly expiry on the **Saturday** after the third Friday (e.g. SPX 2012-02-18, 2012-04-21), while the root table of `sec:data` says "third Friday". | The calculator counts to the date as listed (the packet's `dte`), so these expiries are one day longer than to the Friday. | Not a choice of the calculator, but it touches the 30-day and 90-day limits and τ₀/2 (H09, H23, H31 open SPX expiries listed on a Saturday). Worth one sentence in the thesis or a check. |
| A10 | The exit tests use the packet's deltas, which are rounded to 6 decimals. | Used as they are. | No trigger level was within 0.0003 of the position delta, so rounding cannot flip a test here. |
| A11 | The stress indicator (G16, deferred). | Not computed: it changes no decision. | No. |

## B. The equity day (H07)

| No. | Point | Calculator's choice | Matters here |
|---|---|---|---|
| B1 | The interest on a day when the cycle changes during the day: on which margin? `sec:results-main` says "the margin held that day is the margin of the currently open cycle", which reads as the cycle open at the end of the day. G14 fixes the rate and the day count but not the margin. | The margin of the cycle open at the end of the day (16,440 dollars). The printout also gives the interest on the margin held over the weekend (26,330 dollars): 0.71 instead of 0.45 dollars. | Yes for H07 (a difference of 0.27 dollars). |
| B2 | Converting the 3-month rate for the interest (G14: "continuous compounding as in `sec:rates`"). | `eq:rate-conversion` with the series' own maturity of 91 days, then interest = margin × (exp(r × days/365) − 1). | Tiny (well below 0.01 dollars a day here). |
| B3 | The day P&L of the two positions of the day (S28). | The closed one: its mark at the last usable snapshot of the day before minus the cost to close. The new one: its credit (at execution) minus its mark at the last usable snapshot of the day (at mid). Day P&L = 100 × the sum + interest. | Defines the H07 answer. |

## C. The data pipeline (deep checks H04, H11, H30, H31)

| No. | Point | Calculator's choice | Matters here |
|---|---|---|---|
| C1 | "Vanilla roots only" (`sec:cleaning`): which roots exactly? | SPX, SPXW and SPXQ, the roots of the table in `sec:data`. Others in `raw.csv` (e.g. BSZ, binary options) are dropped. | No: only these three slices were rebuilt. |
| C2 | The limits of the cleaning filters: inclusive or not? | 4 ≤ dte ≤ 100, 0.30 ≤ K/S ≤ 1.08 for puts, 0.97 ≤ K/S ≤ 1.03 for calls, all inclusive. | No: the kept put strikes equal the packet's in all six slices. |
| C3 | The maturities of the four T-bill yields in days, and the order of the two steps (`sec:rates`). | 30, 91, 182, 365 days. Each yield converted with its own maturity first, then interpolated linearly in calendar days. | No: D equals the packet's to 6 decimals in all six slices. |
| C4 | "The 8 strikes nearest K₀" (`sec:forward-impl`): does K₀ count as one of the 8, and what on equal distance? | K₀ is one of the 8, on equal distance the lower strike first. | No: the forward equals the packet's to 6 decimals. |
| C5 | Bisection (`sec:iv-impl`): which number after the 60 halvings? | The midpoint of the last interval. | No: the implied vols equal the packet's to 6 decimals. |

## D. The packets

| No. | Point |
|---|---|
| D1 | H09 (the first snapshot, 3 Jan 2012): `calendar.txt` gives "the day before" as 2026-08-14, the last day of the data. Harmless (no position is open), but the packet maker wraps around at the start. |
| D2 | H30: the ATM vol of the held slice comes out 0.124805 against 0.124804 in the packet, a difference of about 10⁻⁶ (rounding of the printed inputs). Every other deep-check value agrees to the printed 6 decimals. |
