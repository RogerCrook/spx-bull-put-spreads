# Test specification: the thesis as checkable statements

Drafted 2026-11-14. Arian checks it before any test is written.

## Purpose

The code is validated against the thesis, not by reading it. This file turns the
thesis into short statements that a test can check, each tied to the LaTeX label it
comes from. Every test of the seven methods (below) must point to one of these
statements. A test that points to none checks nothing the thesis promises.

The statements were written from the `.tex` alone (version of 2026-11-14), without
reading `Code/`. That is deliberate. If the code had been read first, its choices
could have slipped into the statements, and the test would then check the code
against itself.

## The seven methods (short names used below)

| No. | Name | What it does |
|---|---|---|
| M1 | known answers | formulas against values known from elsewhere (textbook, library, hand calculation, round trip, bounds) |
| M2 | synthetic market | quotes simulated from a model with known parameters, run through the whole pipeline, which must recover them |
| M3 | second implementation | a fresh AI session writes its own backtest from the thesis alone, compared trade by trade |
| M4 | invariants | rules every row of the real outputs must obey |
| M5 | metamorphic | change the input in a known way, the output must change in a known way |
| M6 | mutation | bugs planted in copies of the code, counting how many the tests catch |
| M7 | hand checks | Arian works out by hand what the strategy should do at chosen and random snapshots, then compares with the backtest |

M6 measures the other methods and has no statements of its own.

## How to read the statements

Each statement has an ID, the label it comes from, the statement in words, and the
methods that can check it. "Real" means it can be checked on the existing data or
result files, "synthetic" that it needs made-up inputs. Some statements are exact
(must hold to rounding), others are checked with a stated tolerance, which is fixed
before the test is run.

---

## Part F: formulas (chapter 1)

These are checked on made-up inputs, in seconds.

| ID | Label | Statement | Methods |
|---|---|---|---|
| F1 | `prop:black76` | The call and put prices equal `eq:b76-call` and `eq:b76-put`, with d₁, d₀ as in `eq:d1d0`. Checked against an independent library and a textbook example. | M1 |
| F2 | `prop:parity` | For any inputs, model call minus model put equals D(F − K), to rounding. | M1 |
| F3 | `prop:impvol` | The model price rises strictly with σ. Its limits are D(F − K)⁺ and DF for a call, D(K − F)⁺ and DK for a put. | M1 |
| F4 | `prop:impvol`, `rem:bisection`, `sec:iv-impl` | Price → implied vol → price gives back the price. A price outside `eq:noarb-call` / `eq:noarb-put` gets no volatility. The search runs on [0.001, 5] with 60 halvings. | M1 |
| F5 | `prop:greeks-fwd` | Δ_F, Γ_F, vega and Θ equal finite differences of the price map, with D held fixed. A put's Δ_F lies in [−D, 0]. Γ and vega are positive. | M1 |
| F6 | `prop:chainrule` | Δ_S = Δ_F · F/S and Γ_S = Γ_F · (F/S)². | M1 |
| F7 | `rem:scaling` | Vega is reported divided by 100, theta divided by 365. Delta and gamma are unscaled. | M1 |
| F8 | `prop:black76` (homogeneity) | Multiply F, K and the price by the same c > 0. The implied vol and Δ_F stay the same, Γ_F is divided by c, vega is multiplied by c. | M5 |
| F9 | `prop:entry-delta` | At flat vol, with the strikes of `eq:strikes` unsnapped, the position delta of two spreads equals `eq:entry-delta`. | M1 |
| F10 | `prop:credit-maturity` | The integral `eq:credit` equals the Black–76 credit of two spreads, and the credit rises with τ while `eq:credit-condition` holds. | M1 |

## Part D: data pipeline (chapter 3)

| ID | Label | Statement | Methods |
|---|---|---|---|
| D1 | `sec:cleaning` | Every stored quote passes the six filters: vanilla root, 4–100 days, puts K/S in [0.30, 1.08], calls K/S in [0.97, 1.03], bid ≥ 0.025, ask > bid. Binary and range options are excluded. | M4 (real, sample months), M2 |
| D2 | `sec:data` | At 16:15 (13:15 on early-close days) the index level S is the official close. At every other snapshot S is the midpoint of the underlying's bid and ask. | M4 (real), M2 |
| D3 | `sec:data` | The contract key is (root, expiration, strike, type). An SPX and an SPXW option with the same date are never paired. | M2 |
| D4 | `eq:mid` | Every price used is the midpoint ½(bid + ask), except where the run crosses the spread (S11). | M4 (real) |
| D5 | `def:tau-conv` | τ = calendar days from the quote date to expiry / 365, floored at 1/365, the same for all 27 snapshots of a day. | M4 (real), M2 |
| D6 | `sec:rates` | Yields are in per cent, divided by 100, converted by `eq:rate-conversion` with each series' own maturity. Holidays are forward-filled. Between the four maturities the rate is interpolated linearly, below 1 month it is the 1-month rate. The rate is constant within a day. | M1, M2 |
| D7 | `def:discount` | D = e^{−rτ} with r of D6 at the option's τ. | M1, M2 |
| D8 | `sec:forward-impl` | Per slice (root, expiry, snapshot): pair call and put at each strike. K₀ is the strike with the smallest \|C − P\|. Parity is applied at the 8 strikes nearest K₀ (all pairs if fewer). The forward is the median of these estimates. With fewer than 3 pairs the slice gets no forward and its options are dropped. | M2, M1 (hand-made slice) |
| D9 | `prop:forward` (synthetic) | On quotes made with known S, r, q, the forward found equals S·e^{(r−q)τ}, within a stated tolerance. | M2 |
| D10 | `sec:iv-impl` (synthetic) | On quotes made at a known σ, every implied vol found equals σ, within a stated tolerance. | M2 |
| D11 | `def:atm`, `sec:atm-impl` | Per slice: the out-of-the-money quotes with \|x\| < 0.05, x = log(K/F), puts for x < 0 and calls for x ≥ 0, without those that got no volatility. At least 3 quotes. An unweighted fit of a + bx + cx². σ_atm = a. | M2, M1 (hand-made slice) |
| D12 | `def:atm` (synthetic) | A smile made exactly quadratic in x is recovered exactly. A flat smile gives σ_atm = σ. | M2 |
| D13 | `def:stress` | σ³⁰ is interpolated between the two listed expiries around 30 days. The threshold is the 80th percentile of σ³⁰ over the 252 trading days strictly before t. Stress means σ³⁰ > threshold. | M1, M4 (real), M5 |
| D14 | `def:stress` | The threshold at t does not change when any value on or after t changes (no look-ahead). | M5 |

## Part S: the strategy and the backtest (chapters 2 and 4)

The core of the validation. M3 and M7 check all of it, M4 and M5 parts.

### Opening a position

| ID | Label | Statement | Methods |
|---|---|---|---|
| S1 | `def:entry`, `eq:strikes` | Target strikes are F·e^{−σ√τ} (sold) and F·e^{−2.3σ√τ} (bought), with σ the ATM vol and F the forward of the expiry traded, at t. Each is snapped to the nearest listed put. | M3, M7, M4 (real: the target and snapped strikes in the trade log) |
| S2 | `def:entry` | The position is two spreads: sell 2 puts at the higher strike, buy 2 at the lower. | M3, M7 |
| S3 | `def:entry`, `def:tau-star` | With deficit L = 0 the expiry is the shortest listed one with at least 30 days (τ₃₀). | M3, M7, M4 (real) |
| S4 | `def:tau-star` | With L > 0 the expiry is the shortest one between 30 and 90 days whose credit c(τ) is at least c(τ₃₀) + L. | M3, M7 |
| S5 | `def:tau-star` | With L > 0 and no expiry qualifying, the expiry is the longest listed one of at most 90 days. | M3, M7 |
| S6 | `sec:entry-delta` | Δ₀ is the position delta at the entry snapshot. τ₀ is the time to expiry at entry. | M3, M7, M4 |

### Holding and closing

| ID | Label | Statement | Methods |
|---|---|---|---|
| S7 | `eq:posdelta` | Δ_pos(t) = 2(Δ_S of the bought put − Δ_S of the sold put), with each put's sticky-strike delta at its own implied vol. | M3, M7, M4 (real: from the logged leg deltas) |
| S8 | `def:exits` | Profit exit at the first tested snapshot with Δ_pos ≤ Δ₀ − 0.10. | M3, M7, M4 |
| S9 | `def:exits` | Loss exit at the first tested snapshot with Δ_pos ≥ Δ₀ + 0.10. | M3, M7, M4 |
| S10 | `def:exits`, `eq:gamma-exit` | Gamma exit at the first tested snapshot with τ ≤ max(τ₀/2, 10 days). | M3, M7, M4 |
| S11 | `def:exits` | At every tested snapshot where none of S8–S10 holds, the position is kept. | M7 (the snapshot before each exit), M4 (real: no logged hold snapshot outside the band) |
| S12 | `sec:strategy`, `sec:backtest-design` | When a position is closed, the next one is opened at the same snapshot and first tested at the next one. | M3, M4 |
| S13 | `sec:results-main` | At the end of every trading day exactly one position is open. Never two at once. | M4 |

### Deficit

| ID | Label | Statement | Methods |
|---|---|---|---|
| S14 | `def:deficit` | L = 0 at the start. | M4 |
| S15 | `def:deficit` | After a cycle with π ≥ L: L becomes 0. | M4 (real, every trade), M7 |
| S16 | `def:deficit` | After a cycle with 0 ≤ π < L: L becomes L − π. | M4, M7 |
| S17 | `def:deficit` | After a cycle with π < 0: L becomes −π, any earlier deficit is dropped. | M4, M7 |
| S18 | `def:deficit` | π = credit received − cost of closing, in index points, for the two spreads. | M4, M7 |

### Adopted rules

| ID | Label | Statement | Methods |
|---|---|---|---|
| S19 | `sec:monitoring` | No position is opened or closed at 16:00, or at 13:00 on early-close days. | M4 (real, every trade), M7 |
| S20 | `def:broken` | A leg's quote at t is broken if, against the same contract at the previous snapshot t⁻ at which a decision was taken: \|iv_t − iv_t⁻\| > 0.03, and w_t > 3 w_t⁻, and w_t − w_t⁻ > \|m_t − m_t⁻\|. | M1 (hand-made quotes), M4 (real: the logged quotes), M7 |
| S21 | `sec:broken-quotes` | At a snapshot with a broken leg the position is neither marked nor tested, and no position is opened there. | M4, M7 |
| S22 | `sec:backtest-design` | At a snapshot where a leg is not quoted the triggers are not tested. | M4, M7 |
| S23 | `sec:broken-quotes` | The test uses only quotes up to t. | M5 |

### Execution, capital and returns

| ID | Label | Statement | Methods |
|---|---|---|---|
| S24 | `sec:costs` | At mid every leg trades at its midpoint. Crossing the spread, a leg is sold at the bid and bought at the ask, at entry and at exit. | M4 (real: credit and cost from the logged bid/ask), M7, M5 |
| S25 | `sec:costs` (synthetic) | If every quote has bid = ask, the run crossing the spread gives exactly the run at mid. | M5 |
| S26 | `sec:cash`, `sec:results-main` | The margin of a cycle is the maximum loss of the position at entry, fixed for the cycle. | M4 |
| S27 | `sec:cash` | The margin earns the 3-month T-bill rate of `sec:rates`. | M4, M1 |
| S28 | `sec:results-main` | Daily P&L = realised P&L + change in value of the open position + interest. The open position is valued at the midpoints of its two puts at the day's last snapshot, also in the runs crossing the spread. | M4 |
| S29 | `sec:results-main` | The return of a period = its P&L / the average daily margin over its trading days. | M4, M1 |
| S30 | `tab:results-years` | The 2012–2026 row: total P&L / average daily margin / (3,675/252) for the strategy, compounded for the index. | M4, M1 |

### The strategy as a whole

| ID | Label | Statement | Methods |
|---|---|---|---|
| S31 | `sec:strategy` | Every rule uses only information available at the time of the decision. Changing any quote after t leaves every decision up to t unchanged. | M5 |
| S32 | `def:stress` | The stress indicator is recorded at each entry and changes no decision. Replacing the threshold by any other value leaves every trade unchanged. | M5, M4 |
| S33 | `sec:robustness` | The p15 variant differs from the base case only in the profit exit, at Δ₀ − 0.15. | M3, M5 |
| S34 | `prop:black76` (scale) | Multiply every price, strike and the index by c > 0: the same trades at the same times, every P&L in points multiplied by c. | M5 |
| S35 | `sec:backtest-design` | Each trade records its strikes, implied vols, credit, Δ₀, maturity rule, exit reason and stress indicator. | M4 |

---

## Part G: what the thesis leaves open

A complete specification would answer every question below. The thesis does not, so
the code had to choose. For M3 and M7 each needs an answer **before** the second
implementation is written and before the hand checks start. Otherwise a difference
cannot be told apart from a bug. Arian answers them **without looking at the code**.
Where his answer differs from the code's choice, that is a finding in itself: either
the code or the intention is wrong. Some answers may also belong in the thesis.

| ID | Rule | Open question | Answer (Arian) |
|---|---|---|---|
| G1 | `def:exits` | If two triggers hold at the same snapshot (e.g. gamma and loss), which reason is recorded? | One reason, tested in the order loss, profit, gamma: the first that holds is recorded. (Changed 2026-11-16 to the code's choice. Arian first wanted every trigger recorded.) |
| G2 | `def:entry` | "Nearest listed put": nearest in strike? What if two are equally near? Must the put have a valid quote, volatility and delta at t? | Nearest in strike. A tie should practically never happen (the target is a real number), a test checks it. Valid quote: see G12. |
| G3 | `def:entry` | Can the snapped sold and bought strikes coincide? What then? | The targets always differ, but after snapping to the listed strikes they could in theory coincide. They must not, and realistically it never happens. (In the four runs the narrowest spread is 55 points, checked 2026-11-14 on the trade logs.) |
| G4 | `def:entry`, `def:tau-star` | Which roots are candidates (SPX, SPXW, SPXQ)? If two roots list the same date, which is taken? (Also open in the review of the thesis.) | Every root. On the same date SPX first, then SPXQ, then SPXW (sorted by name). (Changed 2026-11-16 to the code's choice. Arian first said SPXW before SPXQ.) |
| G5 | `def:tau-star` | Are the 30 and 90 days whole calendar days of D5 (so "at least 30 days" = 30 or more)? | Yes. |
| G6 | `def:tau-star` | Is the credit c(τ) in the maturity choice at mid, or at the execution price in the runs crossing the spread? | At execution: mid in the mid runs, bid/ask in the runs crossing the spread. |
| G7 | `def:tau-star` | What if an expiry has no forward or no ATM vol at t, or one of its two strikes cannot be snapped? Skipped as a candidate? | Skipped. For now no maximum distance between a target and its snapped strike. |
| G8 | `def:tau-star` | What if no listed expiry has 30 days or more (τ₃₀ does not exist)? | No position is opened, the next attempt is at the next snapshot. (Changed 2026-11-16 to the code's choice. Arian first said the closest expiry below 30 days.) Realistically it never happens (an SPX monthly expiry is always 30 to about 65 days away), a test checks it. |
| G9 | `def:entry`, `sec:broken-quotes` | If a position cannot be opened at a snapshot (no candidate, or a broken quote), when is the next attempt, and is that day still "one position open"? | At the next snapshot. If a day ends with no position open, the margin of the last position counts for that day (Arian's proposal). A test checks whether such a day occurs at all (S13). Kept as Arian's version on 2026-11-16: the code (margin 0) is to be changed and the rule stated in the `.tex`. |
| G10 | `eq:gamma-exit` | τ₀/2 can be a half day (e.g. 23.5). Is the comparison τ ≤ τ_exit made in whole days, as τ is? | Yes, in whole days, so τ_exit = 23.5 acts as 23 (rounding down). Not blind: this was seen in the code while answering G1. |
| G11 | `def:broken` | "The previous snapshot at which the backtest took a decision": does a snapshot skipped because of a broken or missing leg count? What is t⁻ for a leg about to be opened, which was not held before? | Always compare with a good quote: the last quote of the same put that was not broken. A put about to be opened is compared with its own last good quote (it was listed before, only not held). Kept as Arian's version on 2026-11-16: the code (compares with the previous snapshot used, even a broken one, and does not test a leg missing there) is to be changed and the rule stated in the `.tex`. |
| G12 | `sec:backtest-design` | When is a leg "not quoted": no row at all, or also a row without volatility or delta? | Both: no row, or a row without a delta. At such a snapshot no decision is taken. |
| G13 | `sec:results-main` | The day's last snapshot for the valuation: 16:15 (13:15)? What if a leg is missing or broken then? | The last usable snapshot: 16:15 (13:15) normally. If a leg is missing or broken there, the last usable one before it, never the stock close (16:00 / 13:00). |
| G14 | `sec:cash` | How is the interest computed: rate of which day, which day count, simple or continuous, over weekends and holidays? | The 3-month T-bill rate of the day the interest is paid, i.e. the end of the period (Monday's rate for Friday to Monday), calendar days (Friday to Monday = 3 days), continuous compounding as in `sec:rates`. |
| G15 | `sec:cash` | Maximum loss at entry = (2 × width − credit) × 100 dollars? At mid or at the execution price in the runs crossing the spread? | Yes, (2 × width − credit) × 100 dollars, with the credit at the execution price. The formula is not in the thesis. |
| G16 | `def:stress` | Is σ³⁰ at t taken at the entry snapshot itself, while the 252 past values are taken at 15:45? Interpolated in variance or in volatility? (Also open in the review of the thesis.) | Deferred (Arian, 2026-11-14): the stress indicator changes no decision. |
| G17 | `def:deficit` | In the runs crossing the spread, does the deficit use π at the execution prices? | Yes, at execution: the loss actually made is the one to win back. |
| G18 | `sec:backtest-design` | What happens at the end of the sample to the position still open: closed, or only valued? | Only valued. |
| G19 | `def:entry` | Is the first position opened at the first snapshot of 3 January 2012, and with which deficit (0)? | Yes, with no deficit. The margin is available from the start. |
| G20 | `sec:monitoring` | Which days are early-close days, and where does that list come from? | The source does not matter, as long as the list holds the real early-close days. |
| G21 | `sec:cash`, `sec:results-main` | On a day the position changes, which margin earns that day's interest: the one held over the night before, or the new one? (Added 2026-11-17: found by the blind calculator, open question B1, on the equity day 24 Oct 2016, 0.71 vs 0.45 dollars.) | On each trading day t the margin earns interest for the calendar days since the previous trading day, on the margin held at the close of that previous day: interest(t) = M(t−1) × (e^{r(t)·days/365} − 1), with M the maximum loss at entry of the position open at the last snapshot of the day, r(t) the 3-month rate of day t (G14), days in calendar days. The first trading day earns nothing. A change of position during a day changes the margin from the close of that day on. Returns divide by the average of M(t) at each day's close (`sec:results-main`). This is what the backtest does, so no code change. A sentence for `sec:cash` is to be written with the next batch of thesis edits. |

## Part G against the code (2026-11-14)

Arian's answers compared with what `Code/s11_backtest.py` does, read after all the
answers were given (G1 and G10 were seen earlier). "Effect" is measured on the four
reported runs in `results/`: the trade logs, the daily equity files, the quote logs
and, for G4, `Data/05_atm_vol.csv`.

| ID | Arian | Code | Effect on the four runs |
|---|---|---|---|
| G1 | record every trigger that holds | records one, in the order loss, profit, gamma (`check_exit`) | **differs, label only.** A delta exit while the gamma trigger also held: 7 / 4 / 6 / 5 trades (base mid / base cross / p15 mid / p15 cross). P&L and deficit unchanged. |
| G2 | nearest strike, ties should not occur | nearest among the puts with a delta and a mid. On a tie the first in the data's order (`find_put`) | same. Ties still to be checked by a test. |
| G3 | must not coincide | if the sold strike is not above the bought one, that expiry is skipped (`build_spread`) | same. Never happened (narrowest spread 55 points). |
| G4 | SPX, then SPXW, then SPXQ | sorted by root name: SPX, then **SPXQ**, then SPXW (`open_position`) | **differs, no effect.** At all 31 SPXQ entries SPXW listed no expiry on the same date. |
| G5 | whole calendar days | 30 ≤ days ≤ 90, whole days | same |
| G6 | at execution | at execution (`price_when_selling`, `price_when_buying`) | same |
| G7 | skipped, no maximum distance | expiry skipped without ATM vol, or with fewer than 2 usable puts. No maximum distance | same |
| G8 | the closest expiry below 30 days | no position, try again at the next snapshot | **differs, no effect.** Every new position opened at the snapshot of the previous exit, so no snapshot after the first was ever without a position. |
| G9 | next snapshot. A day without a position counts the last margin | next snapshot. A day without a position counts margin 0 (`finish_day`) | **differs, no effect.** No day ended without a position. |
| G10 | whole days, so rounding down | whole days | same (not blind) |
| G11 | compare with the last good quote | compares with the previous snapshot used, even if it was skipped as broken. A leg missing there is not tested at all | **differs, no effect on the skipped snapshots.** At each snapshot after a broken one (5 / 4 / 4 / 3) the test against the last good quote also passes. Not yet checked: the snapshots after the 22 with a leg missing. |
| G12 | no row, or no delta | no row, or no delta, or no mid (`find_leg`) | same |
| G13 | last usable snapshot, never the stock close | the mid mark of the last snapshot with both legs and no broken quote. The stock close is skipped | same |
| G14 | rate of that day, calendar days, continuous | 3-month rate of the day the interest is paid, i.e. the **end** of the period (Monday's rate for Friday to Monday), calendar days, continuous (`interest_for_day`) | same, if "that day" means the day of payment. If it means the day the money was put in, it differs by one day's rate change. |
| G15 | (2 × width − credit) × 100, credit at execution | the same (`build_spread`) | same |
| G16 | set aside | – | – |
| G17 | at execution | at execution (`update_deficit` with the trade's P&L) | same |
| G18 | only valued | only valued | same |
| G19 | first snapshot, no deficit | first entry 3 Jan 2012 09:45, deficit 0, no interest on the first day | same |
| G20 | the real early-close days | a day is an early close when its last snapshot is 13:15 (`end_of_day_times`) | same, if the data are complete. A test compares the list with the exchange calendar. |

Result: no difference changes a P&L, a deficit or a return in the four runs. G1
changes labels, so it changes the split by exit reason (e.g. `tab:costs`).

Decided 2026-11-16 (Arian): G1, G4 and G8 take the code's choice (the Answer
column above is changed to it), and G14 is read as the code does it. G9 and G11
keep Arian's version: the code is to be changed and both rules written into the
`.tex` (later, with a rerun of the reported runs). Detail still to fix for G11: a
put that was never tested before has no "good" quote in the strict sense. The
proposal is its last quote at a snapshot used, as now.

## What happens next

1. Arian reads this file: missing statements, wrong ones, statements to drop.
2. Arian answers Part G without looking at the code. (Done 2026-11-14, compared
   with the code above.)
3. Then the tests, method by method, in the order listed in `validation/README.md`. Each test
   names the statement IDs it checks, and the results go into one table:
   statement, method, result.
