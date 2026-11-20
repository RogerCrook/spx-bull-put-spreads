# Hand checks (method 7 of the validation)

Arian works out by hand, from the thesis and the quotes, what the strategy must do
at a snapshot, writes it down, and only then compares it with the backtest.

## Files

| File | What it is | Arian opens it |
|---|---|---|
| `select_snapshots.sh` | picks the 22 snapshots by rule branch from the logs in `results/` (and the early-close days from the data calendar), fixed seed 20261116, so a rerun gives the same list. Writes `key_branches.csv` | yes |
| `draw_random.py` | draws the 10 random snapshots from the data's own snapshot times (`Data/05_atm_vol.csv`), compares that list with the backtest's held snapshots, picks the 4 deep checks (one per period 2012–14, 2015–19, 2020, 2021–26), shuffles. Writes `key.csv` and `list.csv` | yes |
| `make_packets.py` | writes one folder per snapshot, `packets/H01` … `packets/H32`, with the inputs only | yes |
| `list.csv` | the 32 snapshots to check, shuffled, numbered H01–H32: run, time, deep check yes/no | **yes, this is the work list** |
| `packets/` | the inputs of each hand check | **yes** |
| `key_branches.csv`, `key.csv` | why each snapshot was chosen and what the backtest did there | **no, only after his answers are written** |

## How the snapshots were chosen (2026-11-16)

- **22 by rule branch** (`B..` in the key), one random case each where the branch
  occurs many times: the first entry, each exit reason, each maturity rule (target,
  recovery, cap), each deficit case (loss on top of a deficit, profit pays part,
  profit clears it), two triggers at once, a broken quote and the snapshot after
  it, a leg missing, the stock close while a trigger holds and the snapshot after
  it, the stock close (13:00) of an early-close day and the 13:15 after it, an
  exit at 16:15, the snapshot just before a loss and
  just before a profit exit, one trade in the run crossing the spread, one profit
  exit of p15, and one day of the equity curve after a weekend.
- **10 at random** (`R..`) from all snapshot times in the data except the stock
  close (by `draw_random.py`). Zero errors
  in 10 random snapshots bounds the error rate only below 30% (rule of three), so
  the random part is a spot check. The full coverage comes from the automatic
  one-step check over all held snapshots (step 2).

**Branch check (2026-11-16, `check_branches.py`):** each of the 22 branch
snapshots meets its condition, tested where possible on the data (calendar,
packet quotes) and otherwise re-read from the trade log. The first definition of
the early-close branch ("an exit at 13:15") was wrong and was replaced before
this check. Note: on 9 March 2020 there is no 09:45 quote for the held puts, so
the broken quote at 10:00 (B10) is measured against 6 March 16:15.

## Result (2026-11-17)

Arian found the manual arithmetic too heavy (2026-11-16) and chose a calculator
written blind by a fresh session from the thesis and the test specification only:
`calculator.py`, its printouts `calc_output/H01.txt` … `H32.txt`, its answers
`calc_output/answers.csv` and the points it had to decide itself,
`calc_output/open_questions.md`. `compare.py` puts its answers next to the
backtest's logs (`calc_output/comparison.csv`).

- **The deep checks:** from the raw quotes, the calculator rebuilt the kept strikes,
  D, the forward, the implied vols and deltas of the legs and the ATM vol of six
  expiries on the four deep-check snapshots. All equal the pipeline's values to 6
  decimals (one ATM vol differs by 10⁻⁶, rounding).
- **The strategy:** 239 fields compared at the 32 snapshots, 237 the same. The
  outcome is the same at all 31 snapshots (12 exits with the right reason, the
  first entry, 13 new positions with the same expiry, maturity rule, target and
  listed strikes, credit, entry delta, exit day and margin, 12 holds, the broken
  quote, the missing leg, both stock closes). The exit cost, P&L, new deficit and
  position delta agree at all 12 exits.
- **The two differences** are one point, the equity day H07 (24 Oct 2016, a
  Monday on which the position changed at 10:00): the interest of the day is
  0.45 dollars in the calculator (on the margin of the new position, 16,440) and
  0.71 in the backtest (on the margin held over the weekend, 26,330), so the day
  P&L differs by the same 0.27 dollars. The thesis does not say which margin
  earns the interest on such a day (open question B1 of the calculator). Not a
  bug in either. Decided 2026-11-17 (Arian): the backtest's reading, the margin
  held at the previous day's close (Part G question G21).

The packet bug found by the calculator (D1: for the first day "the day before"
wrapped round to the last day of the data) was fixed in `make_packets.py` on
2026-11-17. It did not touch any answer (no position is open then), and the
packets were not rebuilt.

## Working order (important)

**Work through the snapshots in time order (the `snapshot` column), not in H order,
and finish each one before opening the next packet.** A packet shows the position
open at its snapshot, and that position may have been opened at an earlier
snapshot of the list. Example: the packets of 9 March 2020 show the position and
the deficit that result from the exit on 6 March 2020. Read in time order, a
packet only shows what was decided at snapshots already checked.

## What is in a packet (`packets/H..`)

- `calendar.txt`: the time of the last snapshot of the day and of the day before
  (16:15, or 13:15 on an early-close day, whose stock close is then 13:00).
- `position.txt`: the position open just before the snapshot, from the trade log.
  The deficit at the snapshot is its `deficit_at_entry`.
- `legs.csv`: both puts of that position at every snapshot of the day before and of
  this day up to the snapshot, including the stock-close snapshot (16:00 / 13:00).
  A put with no row at a snapshot was not in the data then.
- `expiries.csv`: every expiry at the snapshot with its forward and ATM vol.
- `puts.csv`: every put at the snapshot, all expiries (for a new position).
- The equity day (`(day)`): every position open that day, their puts over the day
  before and the day, and the 3-month T-bill rate (FRED, percent) of the week.
- Deep checks (deep = yes) also: `raw.csv` (all raw rows of the snapshot, calls and
  puts, every root), `index_close.csv` (the official close), `rates.csv` (the four
  T-bill rates, percent).

Made 2026-11-16 by `draw_random.py` (12 s) and `make_packets.py` (about 20 min).
The data's snapshot times outside the stock close (95,145) and the backtest's held
snapshots (95,144) are the same list except the first snapshot, 3 Jan 2012 09:45,
where the first position is opened.

## What Arian writes down for each snapshot

1. Is it a snapshot where a decision is allowed (not the stock close)?
2. Are both legs usable (a row with a delta) and not broken (G11: against the last
   good quote)?
3. Position delta now, and which exit holds (loss, profit, gamma, none).
4. If it exits: the cost to close, the P&L, the new deficit.
5. If it exits: the new position (expiry, maturity rule, both strikes, credit,
   entry delta, exit day, margin).
6. For the equity day (H29): unrealised P&L, interest of the day, margin.

The state before the snapshot (the open position, its credit, the deficit) is taken
from the backtest's logs, so each check tests one decision.
