#!/bin/bash
# Selects the snapshots for the hand checks (method 7 of the validation).
#
# Reads the backtest logs in results/ (trades, quotes, missing, equity) and,
# for the early-close days only, the snapshot times of Data/05_atm_vol.csv.
# Writes one file next to this script:
#   key_branches.csv : id, branch, run, snapshot, what the backtest did there,
#                      for the 22 snapshots chosen by rule branch (B01-B20).
#                      (Changed 2026-11-16: B14 was "an exit at 13:15", which
#                      is an ordinary snapshot on most days. It is now the
#                      stock close of a real early-close day, B14, and the
#                      snapshot after it, B14b.)
#                      Part of the ANSWER KEY: Arian does not open it before his
#                      hand checks. The 10 random snapshots, the shuffled work
#                      list and the full key come from draw_random.py.
#
# Every random pick uses gawk's rand() with a fixed seed, so running the script
# again gives the same snapshots. Run from the main folder:
#   bash validation/hand_checks/select_snapshots.sh

SEED=20261116                      # base seed; branch n uses SEED + n
R=results                          # the folder of the logs
OUT=validation/hand_checks         # where key_branches.csv goes

# ---------------------------------------------------------------------------
# pick_trade N BRANCH RUN CONDITION FIELD
#   Picks at random ONE trade of trades_RUN.csv for which CONDITION holds.
#   CONDITION is awk code. It can use t[name] (this trade's column "name")
#   and n[name] (the NEXT trade's column, empty for the last trade).
#   FIELD is the column that gives the snapshot (entry_time or exit_time).
#   Prints one line of key.csv.
# ---------------------------------------------------------------------------
pick_trade () {
  gawk -F, -v seed=$((SEED + 10#$1)) -v id="B$1" -v branch="$2" -v run="$4" -v field="$5" '
    NR == 1 { for (i = 1; i <= NF; i++) col[i] = $i; next }     # header: column names
    { for (i = 1; i <= NF; i++) row[NR, col[i]] = $i; last = NR } # keep every row
    END {
      count = 0
      for (r = 2; r <= last; r++) {
        delete t; delete n
        for (i in col) { t[col[i]] = row[r, col[i]]; n[col[i]] = row[r + 1, col[i]] }
        if ('"$3"') { count++; pick[count] = r }
      }
      if (count == 0) { print id ",\"" branch "\"," run ",NONE FOUND,"; exit }
      srand(seed)
      r = pick[int(rand() * count) + 1]
      what = "trade entered " row[r, "entry_time"] " exits " row[r, "reason"] \
             " pnl " row[r, "pnl"] " deficit " row[r, "deficit_at_entry"] "->" row[r, "deficit_after"] \
             " | next entry rule " row[r + 1, "maturity_rule"] " (" count " candidates)"
      print id ",\"" branch "\"," run "," row[r, field] ",\"" what "\""
    }' $R/trades_$4.csv
}

{
echo 'id,branch,run,snapshot,what the backtest did'

# B01: the very first entry (fixed, no random choice)
# (columns 18 and 19 of the trade log are entry_time and maturity_rule)
gawk -F, 'NR == 2 { print "B01,\"first entry, no deficit\",base_mid," $18 ",\"opened, rule " $19 "\"" }' $R/trades_base_mid.csv

pick_trade 02 "profit exit with no deficit, then a target entry"  "t[\"reason\"] == \"profit\" && t[\"deficit_at_entry\"] + 0 == 0" base_mid exit_time
pick_trade 03 "loss exit, then a recovery entry"                  "t[\"reason\"] == \"loss\" && n[\"maturity_rule\"] == \"recovery\"" base_mid exit_time
pick_trade 04 "loss exit, then a cap entry"                       "t[\"reason\"] == \"loss\" && n[\"maturity_rule\"] == \"cap\"" base_mid exit_time
pick_trade 05 "gamma exit"                                        "t[\"reason\"] == \"gamma\"" base_mid exit_time
pick_trade 06 "loss on top of a deficit (deficit replaced)"       "t[\"deficit_at_entry\"] + 0 > 0 && t[\"pnl\"] + 0 < 0" base_mid exit_time
pick_trade 07 "profit pays the deficit down in part"              "t[\"deficit_at_entry\"] + 0 > 0 && t[\"pnl\"] + 0 >= 0 && t[\"deficit_after\"] + 0 > 0" base_mid exit_time
pick_trade 08 "profit clears the deficit"                         "t[\"deficit_at_entry\"] + 0 > 0 && t[\"pnl\"] + 0 >= 0 && t[\"deficit_after\"] + 0 == 0" base_mid exit_time
pick_trade 09 "delta exit while the gamma trigger also held"      "t[\"reason\"] != \"gamma\" && t[\"dte_exit\"] + 0 <= t[\"exit_days\"] + 0" base_mid exit_time
pick_trade 15 "exit and entry at 16:15 (official close as S)"     "substr(t[\"exit_time\"], 12) == \"16:15:00\"" base_mid exit_time
pick_trade 18 "exit and entry at bid/ask (run crossing the spread)" "1" base_cross exit_time
pick_trade 19 "profit exit with the band 0.15 (p15)"              "t[\"reason\"] == \"profit\"" p15_mid exit_time

# B10 and B11: a held snapshot skipped for a broken quote, and the snapshot after it
gawk -F, -v seed=$((SEED + 10)) '
  NR > 1 && $2 == "held" && $3 == "short" { time[++k] = $1; act[k] = $16 }
  END {
    count = 0
    for (i = 1; i <= k; i++) if (act[i] == "skipped (broken)") pick[++count] = i
    srand(seed); i = pick[int(rand() * count) + 1]
    print "B10,\"held snapshot with a broken quote\",base_mid," time[i] ",\"skipped (broken) (" count " candidates)\""
    print "B11,\"the held snapshot after B10\",base_mid," time[i + 1] ",\"action: " (act[i + 1] == "" ? "held" : act[i + 1]) "\""
  }' $R/quotes_base_mid.csv

# B12: a held snapshot with a leg missing
gawk -F, -v seed=$((SEED + 12)) '
  NR > 1 { time[++k] = $1; what[k] = "short missing " $6 ", long missing " $7 }
  END { srand(seed); i = int(rand() * k) + 1
        print "B12,\"held snapshot with a leg missing\",base_mid," time[i] ",\"skipped, " what[i] " (" k " candidates)\"" }' $R/missing_base_mid.csv

# B13: the first exit at 16:00 in the run without the stock-close rule
# (fixed: before it both runs held the same positions). In the reported run
# nothing may happen at 16:00, and the exit comes at 16:15 (B13b).
echo 'B13,"stock close (16:00) while a trigger holds",base_mid,2012-03-13 16:00:00,"no decision (the run without the stock-close rule exits here, profit)"'
echo 'B13b,"the snapshot after B13",base_mid,2012-03-13 16:15:00,"profit exit and new entry"'

# B14 and B14b: an early-close day, a day whose last snapshot in the DATA is
# 13:15. B14 is its stock close (13:00), where no decision may be taken, and
# B14b the snapshot after it (13:15, the official close).
gawk -F, -v seed=$((SEED + 14)) '
  NR > 1 { day = substr($1, 1, 10); time = substr($1, 12, 8)
           if (time > last[day]) last[day] = time }          # the latest time seen per day
  END {
    count = 0
    for (day in last) if (last[day] == "13:15:00") early[++count] = day
    asort(early)                                              # sort the days, so the draw repeats
    srand(seed); day = early[int(rand() * count) + 1]
    print "B14,\"stock close (13:00) of an early-close day\",base_mid," day " 13:00:00,\"no decision (" count " early-close days)\""
    print "B14b,\"the snapshot after B14 (13:15)\",base_mid," day " 13:15:00,\"see the logs\""
  }' Data/05_atm_vol.csv

# B16 and B17: the last held snapshot before a loss exit / before a profit exit
for pair in "16 loss" "17 profit"; do
  set -- $pair
  gawk -F, -v seed=$((SEED + 10#$1)) -v id="B$1" -v reason="$2" '
    NR > 1 && $2 == "held" && $3 == "short" { time[++k] = $1; act[k] = $16 }
    END {
      count = 0
      for (i = 2; i <= k; i++) if (act[i] == reason && act[i - 1] == "") pick[++count] = i - 1
      srand(seed); i = pick[int(rand() * count) + 1]
      print id ",\"held snapshot just before a " reason " exit\",base_mid," time[i] ",\"held, no trigger (" count " candidates)\""
    }' $R/quotes_base_mid.csv
done

# B20: one day of the equity curve over a weekend (a Monday), base_mid
gawk -F, -v seed=$((SEED + 20)) '
  NR > 1 { split($1, d, "-")
           # day of the week: mktime needs "YYYY MM DD HH MM SS"; %u gives 1 = Monday
           if (strftime("%u", mktime(d[1] " " d[2] " " d[3] " 12 00 00")) == 1) monday[++k] = $1 }
  END { srand(seed); i = int(rand() * k) + 1
        print "B20,\"one day of the equity curve after a weekend\",base_mid," monday[i] " (day),\"unrealised, interest_today and margin of that row (" k " Mondays)\"" }' $R/equity_base_mid.csv

} > $OUT/key_branches.csv

echo "written: $OUT/key_branches.csv (the random snapshots, the shuffle and list.csv come from draw_random.py)"
