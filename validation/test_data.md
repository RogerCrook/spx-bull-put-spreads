# The test data, exactly (written 2026-11-20)

This file says exactly which data each test of the validation used. Every file is
named, with its number of rows (lines without the header) and its SHA-256 checksum.
A file with the same checksum is the same file, byte for byte.

The option data are licensed from Cboe, so no data file is on GitHub. The changed
copies and the made-up markets lived in the temp folder (`%TEMP%\...`, outside the
project) and can be deleted. Each is rebuilt by the script named below. The same
checksum after a rebuild proves it is the same data.

How to check a file's checksum (PowerShell):

```powershell
Get-FileHash "Data\06_vol30.csv" -Algorithm SHA256
```

## 1. Tests on the real data and the reported runs

These tests read the project's own files directly. Nothing was copied or changed.

| Test | Reads |
|---|---|
| One-step check (`automatic/one_step_check.py`) | the result files of the four runs, `Data/05_atm_vol.csv` |
| Invariants (`automatic/invariants_check.py`) | the result files of the four runs, `Data/03_treasury_bills/DGS3MO.csv`, `Data/05_atm_vol.csv`, `Data/06_vol30.csv`, `Data/07_index_close/GSPC_daily.csv`, `Data/09_total_return/SP500TR_daily.csv` |
| Known answers (`automatic/formula_check.py`) | every 10th row of 16 months of `Data/04_greeks/`: 2012-01, 2013-02, 2014-03, 2015-04, 2016-05, 2017-06, 2018-07, 2019-08, 2020-03, 2020-09, 2021-10, 2022-11, 2023-12, 2024-08, 2025-04, 2026-07. 4,275,742 rows |
| Base against p15 (`automatic/p15_vs_base_check.py`) | the result files of the four runs |
| Second implementation (`second_implementation/backtest.py`) | all of `Data/04_greeks/` (176 months, 2012-01 to 2026-08, 64 GB), `Data/05_atm_vol.csv`, `Data/06_vol30.csv`, `Data/03_treasury_bills/DGS3MO.csv`. 3 Jan 2012 to 14 Aug 2026, 3,675 trading days |
| Hand checks (`hand_checks/`) | the 32 snapshots in section 5, from `Data/01_raw_options`, `03_treasury_bills`, `04_greeks`, `05_atm_vol.csv`, `07_index_close` |

`Data/04_greeks/` is the output of stage 2 after the data rebuild of 2026-10-27. At
64 GB it was not checksummed.

**The result files of the four runs** (`results/`), as the tests read them:

| File | SHA-256 |
|---|---|
| `trades_base_mid.csv` | `7642995746f5cf904243079512a2cf6d5b1520f756edf2ff53828e64039faa64` |
| `trades_base_cross.csv` | `15deff5fe114c68035f2b717812ac4fa9ddd2ec6d8ebefcf83462ae10e41b6b8` |
| `trades_p15_mid.csv` | `2e84555742b461dcf9eacc946ac94716e2d50f13d63edf702a52968e41d31db9` |
| `trades_p15_cross.csv` | `81ab12e22af520fdcc80a9ef1fca614716dd5ca2c2ca04e755d3fbc38e111df8` |
| `equity_base_mid.csv` | `8d12a16412693aa5613708569b30286c83390c60232b0f2e8bb68c0540314aab` |
| `equity_base_cross.csv` | `b34655deb6b48bb23217bf162c5839ff14862538a3f36358190fdd7f2adeb483` |
| `equity_p15_mid.csv` | `aca7b550360576f76d2af687aac4fb199152a663840903c93cc7cdb9cd6e305c` |
| `equity_p15_cross.csv` | `ccb915e23811f509ac235842d532b9582ee86593ec457253f80ac078b42c6420` |
| `quarters_base_mid.csv` | `abd563d79c5e75b4424d1b904bf59187e067848a32e3c2f8ab5bedce09f63424` |
| `quarters_base_cross.csv` | `c786dd1ddda6343ad9c5ca18f3bb7471192c2c162b0ce123f3b96bacce938c30` |
| `quarters_p15_mid.csv` | `513d2575ec8cf557146c6ea873e394f58b2a24fcef5d5dcb6a6afabaccb1e722` |
| `quarters_p15_cross.csv` | `8fef8c1d9595a8998aeffc6cdc5391bb709e42c06009b5f99902cc21c16caaf6` |
| `quotes_base_mid.csv` | `08bc2109290ac57abfba21e9627be5f1a0cc9a1cb90aca2aafc27d78153fc620` |
| `quotes_base_cross.csv` | `6de5c182f39aad0d47869a0c3ab353f959b1898b068809ecdec420f6c9a65050` |
| `quotes_p15_mid.csv` | `7ffe38f3c996b15172e512d3d760235613e618c53b40a7324b2f2c7427227e37` |
| `quotes_p15_cross.csv` | `48bf593722292d0ee8a84d68d2b4e081a972650f10507b7f5a337947b81cde0b` |
| `missing_base_mid.csv` | `c55654ad7bf93a4fd487636fe94e127f79ad51782c1740a837ea0230ac9d5bb8` |
| `missing_base_cross.csv` | `ed8ba699951e5a8b4ed7ee0f0cb42c07f3b228aa1aed4575b720091157be2ec4` |
| `missing_p15_mid.csv` | `e465dd0e664d8a31fea5cde83c9bc90071433490bdf11d65bd14a78e81f90608` |
| `missing_p15_cross.csv` | `48df64983619d11cfc7e7888e13e22a2fb91ee9ecc5a0779a66b9202d9f6f55d` |

**The smaller data files** the tests read or copied:

| File | Rows | SHA-256 |
|---|---|---|
| `Data/02_clean/spx_2012-01.csv` | 239,407 | `367289136f67f97ed990db9d9527b8640085c667a73db3c62d81f0b08cef21b5` |
| `Data/04_greeks/spx_2020-02.csv` | 3,005,325 | `83132ca784dcdd1185a179f9db3a58380d88a3dbffcd732f7545aea37e4dfb67` |
| `Data/04_greeks/spx_2020-03.csv` | 2,492,776 | `5765952d6e785032f480bb099c64e61e612d9baa85bce274a869b8e9fb66e29e` |
| `Data/05_atm_vol.csv` | 2,160,637 | `233c551805648b817d65758546c1d92226ec8c4179619d0d15accccaacc2bfa0` |
| `Data/06_vol30.csv` | 3,639 (3 Jan 2012 to 14 Aug 2026) | `37674056a047cacce685e033111583b662cad0f59cb00b764e4d7f94c90802fa` |
| `Data/03_treasury_bills/DGS1MO.csv` | 3,866 | `8e813c385beb19d565ea649e04a8419bc158785bd5d0d5c4e84837410629bf29` |
| `Data/03_treasury_bills/DGS3MO.csv` | 3,866 | `1ad3af9242fc33504c100c27b72e894ac8a2b081ca35edd3d2aef858cac260bc` |
| `Data/03_treasury_bills/DGS6MO.csv` | 3,866 | `f508f062338a07c5c1331b4ac3f28f8ad375605f8b89257ec0cae4d3e5fd3f5e` |
| `Data/03_treasury_bills/DGS1.csv` | 3,866 | `132a014ca6f04c26bf52e039e1d7afb910b6df27e21eb08dfd5d9388523fc23e` |
| `Data/07_index_close/GSPC_daily.csv` | 3,675 | `d01d5f3d5f7707ca8c4d14c7ef3907d92c504ba7e42a4c14b838e06025bf69ea` |
| `Data/09_total_return/SP500TR_daily.csv` | 3,696 | `73a98e60effb6220f9405a709331ed72e51c3569a43b8cbc26f3dc5aa895a57a` |

## 2. The changed copies (`%TEMP%\masterarbeit_metamorphic`, 3.8 GB)

Built on 2026-11-18 by `automatic/metamorphic/make_copies.py` from the files in
section 1. Each copy is a folder with its own `Data/` inside. Every copy also holds
the four T-bill files, unchanged, with the checksums above.

**Two months for the backtest.** February and March 2020: 41 trading days, 3 Feb
2020 09:45 to 31 Mar 2020 16:15, 1,103 snapshot times. Chosen as a calm month followed
by the crash (broken quotes on 9 and 16 March, legs missing on 20 March). The
backtest on a copy starts on 3 Feb 2020 with no position and no deficit. So its
trades are not those of the reported runs. Each backtest copy was run in the base
case, at mid and crossing the spread.

**One month for stage 2.** January 2012 (`Data/02_clean/spx_2012-01.csv`, the
smallest cleaned month): 20 trading days, 3 to 31 Jan 2012.

| Copy | Files and the change | Rows | SHA-256 |
|---|---|---|---|
| `stage2_original` | `02_clean/spx_2012-01.csv`, unchanged | 239,407 | same as the source |
| `stage2_times2` | the same month, `strike`, `bid`, `ask`, `mid`, `spot`, `spot_quote` × 2 | 239,407 | `bb1f10cfbe5fa8ff4bfdfbb4b3970e839536c26da5fa686a27f0f6ea3042a77a` |
| `backtest_original` | `04_greeks/spx_2020-02.csv` and `spx_2020-03.csv`, unchanged | 3,005,325 and 2,492,776 | same as the source |
| | `05_atm_vol.csv`, only the rows of Feb and Mar 2020 | 27,331 | `5c69b6b73a58acc1c31ad4932b7f17e13fff7582c86a1e7ba0392ccae2e01a3d` |
| | `06_vol30.csv`, all of it, unchanged (the stress threshold needs the history) | 3,639 | same as the source |
| `backtest_times2` | `04_greeks`: `strike`, `bid`, `ask`, `mid`, `spot`, `spot_quote`, `forward` × 2, `gamma` ÷ 2, `vega` and `theta` × 2, `iv` and `delta` unchanged | 3,005,325 and 2,492,776 | `7b10f85faf12c1c49baee63d423e1dd4208eb568ee7568effe34c4f12855f977` and `a7ff29d38bbf4086a56ad18478d844c34a2a590c3531f383091b2611f558c3ae` |
| | `05_atm_vol.csv`, Feb and Mar 2020, `spot`, `spot_quote`, `forward` × 2 | 27,331 | `95a10ea9738226a2f3a522ee615896898b9b2936fe2fc2ae1cfe8a6fb68be02d` |
| | `06_vol30.csv`, unchanged | 3,639 | same as the source |
| `backtest_bid_equals_ask` | `04_greeks`: `bid` and `ask` set to `mid` | 3,005,325 and 2,492,776 | `6cebc76248b9b146494c6fb27e484fbb68deea37ce16d85d12c8eb0ca92f1c97` and `456fe012612525ded6a94330c301a5a30af2d81f4c1d628c5e8cf6dbaec6315e` |
| | `05_atm_vol.csv` and `06_vol30.csv` as in `backtest_original` | | same |
| `backtest_cut` | every row after 10 Mar 2020 removed: `04_greeks` (February unchanged) | 3,005,325 and 928,381 | February the same as the source, March `cd52b2f381c4c4a19113c229680ee779a662c06f87df3496989319e994cf44c0` |
| | `05_atm_vol.csv`, 3 Feb to 10 Mar 2020 (26 days, 701 snapshot times) | 17,768 | `044decf255ef63cc5d8264627aa3fc9080d69166ae791848808c139512b1eac2` |
| | `06_vol30.csv`, 3 Jan 2012 to 10 Mar 2020 | 2,035 | `420ed5cfb6dd8255d3198a8a297e84fa6001c00a91ee069b1c5924d9b2b3be17` |
| `backtest_random_stress` | `04_greeks` and `05_atm_vol.csv` as in `backtest_original` | | same |
| | `06_vol30.csv`: `vol30` and `threshold` replaced by random numbers between 5% and 80%, the flags by random True/False, seed 20261118 | 3,639 | `b177c5ed26938959dfe48b4c00157893559aad72faadbc3ba5d4e68e7b33c852` |

"Same as the source" was checked: the checksum of the copy equals that of the file
in `Data/`.

## 3. The made-up markets

No real data and no randomness. Every value is fixed in the script, so a rebuild
gives the same files. Only the inputs are listed below. The pipeline's outputs
(`02_clean`, `04_greeks`, `05_atm_vol`) are made from them when the test runs.

**The first made-up market** (`%TEMP%\masterarbeit_synthetic`, 110 MB), built by
`automatic/synthetic/make_market.py`. Three trading days, 3 to 5 March 2031, the
third an early close. Index level 4000, 4040, 3980. Nine expiries (SPX, SPXW, SPXQ
and the binary root BSZ, from 3 to 101 days). Puts every 25 points from 1125 to 3600
and every 5 points to 4400, calls every 5 points from 3600 to 4400. The script gives
the full list of parameters and traps.

| File | Rows | SHA-256 |
|---|---|---|
| `01_raw_options/UnderlyingOptionsIntervals_900sec_2031-03-03.csv` | 98,010 | `5a68df3c5c2475eaaa6b2a846590cbfa19b98073fe835e16d5f1bcefa506830e` |
| `01_raw_options/UnderlyingOptionsIntervals_900sec_2031-03-04.csv` | 98,010 | `0c969c7fa91b3ec033e1657907c9730f2de5081e89f8d9d4b190dc8a796ccff3` |
| `01_raw_options/UnderlyingOptionsIntervals_900sec_2031-03-05.csv` | 54,450 | `0456b766a01746bc74757b6aea5a1670057848cfb81b12747ba3958e96eef897` |
| `03_treasury_bills/DGS1MO.csv` | 4 | `2cf3a8eebd5d3844a48cee6c3169ba7a00b2ee44680d79748d635e0de2f51956` |
| `03_treasury_bills/DGS3MO.csv` | 4 | `eb89cbf46bb8184aa51457a0c29cdfd69a9f3ec9a7a9b4d5ff9f5b57b20f7756` |
| `03_treasury_bills/DGS6MO.csv` | 4 | `e2f3d6eee5f924103a99435d765ac4c0481c714af70d71a7efde8b190ee19878` |
| `03_treasury_bills/DGS1.csv` | 4 | `ba621aa635196c8b85ab53c124964b30721d41fb3a8750c04c39b92226bd19fd` |
| `07_index_close/GSPC_daily.csv` | 3 | `3757e6c9e2a5cadc30d08bc568f743d26f2f9cb4cc9c892d2d2bf3aad8205326` |
| `truth.csv` (the known answer for every raw row) | 250,470 | `87e67d348eccfba62d039199267d8bbbf0d3f2ce2f3cc7f33f12c9ff6ae6699c` |

**The rough made-up market** (`%TEMP%\masterarbeit_synthetic_rough`, 10 MB), built
on 2026-11-20 by `automatic/synthetic/make_rough_market.py`. One trading day, 3 March
2031, index level 4000, dividend yield 1.5%. Four SPX expiries: one with parity
errors that differ by strike (2 April 2031), one with a cubic smile (18 April), one
with exactly 3 out-of-the-money points in the ATM band (7 May), one with exactly 2
(21 May, a call priced 10 points above its no-arbitrage limit so it has no
volatility).

| File | Rows | SHA-256 |
|---|---|---|
| `01_raw_options/UnderlyingOptionsIntervals_900sec_2031-03-03.csv` | 24,840 | `4be48e615b71de5bcd1941674383ab64028df7fa35cc363f0d33c7ffb6ca9f29` |
| `03_treasury_bills/DGS1MO.csv` | 2 | `8ac1bdf2ce9225a660f13a993309137e8c65bb29de7875616d6b3a5ab5d0a2a2` |
| `03_treasury_bills/DGS3MO.csv` | 2 | `9dbe7d0a70efd363239045071cd62812410a6828665b5fc7d475d7bcf6586394` |
| `03_treasury_bills/DGS6MO.csv` | 2 | `ba4a157a2d42b073ecb25cbeda4df8965a67f18ad326a1750bc3fb5dbce237d5` |
| `03_treasury_bills/DGS1.csv` | 2 | `a93d3b80333550b4f0b5f97946a541528b1371a6c2d59fa34ec7184f2f5ab5c9` |
| `07_index_close/GSPC_daily.csv` | 1 | `e49a061073bc2486d8d8ab7413cbc25ea0b83ebbb6a4dee1e6a1d114b31c76e5` |
| `truth.csv` | 24,840 | `eed612ac054eb1fe5da4d2d2547c78f4ab0638bd739c05dc462c5d57a5f4cce4` |

Together the two markets have 250,470 + 24,840 = 275,310 raw quotes (the number in
`tab:code-validation`).

## 4. The mutation tests (`%TEMP%\masterarbeit_mutation`, 82 MB)

No new data. 72 copies of `Code/` (`m000` unchanged, `m001` to `m071` with one
planted bug each), made on 2026-11-19 by `automatic/mutation/make_mutants.py` with
seed 20261119. The list of bugs is `manifest.csv` in that folder (72 rows, SHA-256
`b00ea766182cc7f6192a98cd349d4ab01df9b792c9d378285f152c739757b838`). The same
seed rebuilds it.

The mutants were run on the data above:
- bugs in the pipeline files (`s01`, `s03` to `s08`) on the first made-up market
  (section 3)
- bugs in the backtest (`s11`), and in `s03` and `s06`, which the backtest also
  uses, on the copies of Feb and Mar 2020 (section 2), at mid and crossing the
  spread, then the one-step check, the invariants and the changed-data tests
- the five gaps again (`rerun_gaps.py`, 2026-11-20): four on the rough made-up
  market, one on `backtest_original` with the new Part E of the invariants

## 5. The hand checks: the 32 snapshots

Picked on 2026-11-16 (22 by rule branch, seed 20261116, and 10 at random). The data
of each snapshot are in `hand_checks/packets/H01` to `H32` (kept locally, not on
GitHub). "Deep" means the calculator also rebuilt stages 1 and 2 from the raw quotes.
"(day)" means the check covers the whole day.

| Check | Run | Snapshot | Deep |
|---|---|---|---|
| H01 | base_mid | 2014-01-13 09:45 | no |
| H02 | base_mid | 2016-04-26 13:30 | no |
| H03 | base_mid | 2025-02-27 14:15 | no |
| H04 | base_mid | 2025-04-02 13:00 | yes |
| H05 | base_mid | 2020-03-06 15:00 | no |
| H06 | base_cross | 2016-06-29 16:15 | no |
| H07 | base_mid | 2016-10-24 (day) | no |
| H08 | base_mid | 2012-04-09 12:15 | no |
| H09 | base_mid | 2012-01-03 09:45 | no |
| H10 | base_mid | 2018-11-28 16:15 | no |
| H11 | base_mid | 2020-02-26 13:30 | yes |
| H12 | base_mid | 2019-05-31 09:45 | no |
| H13 | base_mid | 2012-03-13 16:00 | no |
| H14 | base_mid | 2023-06-13 12:30 | no |
| H15 | base_mid | 2025-01-13 15:45 | no |
| H16 | base_mid | 2015-12-11 15:15 | no |
| H17 | base_mid | 2025-04-07 10:30 | no |
| H18 | base_mid | 2020-03-09 10:00 | no |
| H19 | base_mid | 2018-10-16 12:30 | no |
| H20 | base_mid | 2022-02-24 15:45 | no |
| H21 | base_mid | 2023-07-28 10:15 | no |
| H22 | base_mid | 2015-07-20 09:45 | no |
| H23 | base_mid | 2013-08-15 09:45 | no |
| H24 | base_mid | 2018-06-25 11:00 | no |
| H25 | p15_mid | 2023-11-14 09:45 | no |
| H26 | base_mid | 2020-11-27 13:00 | no |
| H27 | base_mid | 2020-03-09 10:15 | no |
| H28 | base_mid | 2024-10-16 11:30 | no |
| H29 | base_mid | 2020-11-27 13:15 | no |
| H30 | base_mid | 2016-09-22 09:45 | yes |
| H31 | base_mid | 2012-03-13 16:15 | yes |
| H32 | base_mid | 2016-03-31 12:30 | no |

Why each snapshot was picked is in `hand_checks/key_branches.csv` and `key.csv`
(local only).
