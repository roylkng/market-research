# AE001 T009 NSE Stock-Options Positioning Feature Trial v1

Status: FROZEN BEFORE OUTCOME MATERIALIZATION
Frozen: 2026-10-01
Live capital: DISABLED

## Objective

Test whether official NSE stock-options positioning and premium structure adds
incremental cross-sectional information beyond the merged 37-feature AE001
price/liquidity/delivery/futures model.

T009 is a new feature-family trial. It does not modify T003, T005 or T006.

## Source-feasibility prerequisite

AE001-D006-v1 PASSED before T009 was frozen.

D006 sealed result:

- report SHA-256:
  `4aaa0fb2166c5093eb7e23b16b72ceccd19c7eb5ab3b441528160fe527a965c6`;
- 266 / 266 READY sessions;
- parser-rejected sessions: 0;
- minimum usable option symbols: 204;
- p10 usable option symbols: 207;
- median usable option symbols: 209.

D005 remains FAILED and is not reinterpreted.

## Historical source window

2025-09-01 through 2026-09-25.

Evidence class:

`HISTORICAL_RECONSTRUCTION_DEVELOPMENT`

Historical FO publication timestamps are not preserved by the archive.

T009 may establish historical information content only.

It cannot count as prospective validation.

## Official source

NSE:

`F&O - UDiFF Common Bhavcopy Final (zip)`

Archive:

`https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip`

Stock-option instrument code:

`STO`

D006 row/logical-key source contract is authoritative.

## Identity

FO options do not provide an equity ISIN suitable for historical identity.

Every option symbol is rebound on the same session to the exact NSE CM EQ
symbol+ISIN identity from the official cash UDiFF panel.

No symbol-only historical identity is accepted beyond that same-session join.

## Option surface

For each stock/session:

1. retain D006-valid contracts only;
2. exclude expiry <= trade date;
3. front expiry = earliest strictly future expiry;
4. retain paired strikes present as both CE and PE;
5. require at least three paired strikes;
6. nearest paired strike must be within 10% absolute moneyness versus cash close.

All aggregate call/put features use PAIRED front-expiry strikes only so unequal
call/put listing breadth cannot create a directional ratio mechanically.

Near-ATM means absolute strike moneyness <= 5%.

## Frozen T009 feature family

Ten raw option features:

1. `opt_front_log1p_days_to_expiry`
   - log(1 + calendar days to front expiry).

2. `opt_nearest_abs_moneyness`
   - absolute nearest-paired-strike / cash-close - 1.

3. `opt_atm_straddle_fraction`
   - (nearest call settlement + nearest put settlement) / cash close.

4. `opt_atm_put_call_premium_imbalance`
   - (put settlement - call settlement) /
     (put settlement + call settlement).

5. `opt_paired_put_call_oi_imbalance`
   - (paired put OI - paired call OI) /
     (paired put OI + paired call OI).

6. `opt_paired_put_call_volume_imbalance`
   - (paired put traded contracts - paired call traded contracts) /
     (paired put traded contracts + paired call traded contracts);
   - frozen value = 0 when both sides have zero traded contracts.

7. `opt_paired_put_call_change_oi_imbalance`
   - (paired put change-OI - paired call change-OI) /
     (abs(put change-OI) + abs(call change-OI));
   - frozen value = 0 when both aggregate changes are zero.

8. `opt_paired_total_oi_change_fraction`
   - aggregate paired change-OI /
     aggregate reconstructed prior paired OI;
   - prior OI = current OI - change-OI;
   - requires aggregate prior paired OI > 0.

9. `opt_near_atm_oi_share`
   - paired CE+PE OI at strikes within 5% absolute moneyness /
     total paired front-expiry CE+PE OI.

10. `opt_near_atm_volume_share`
    - paired CE+PE traded contracts at strikes within 5% absolute moneyness /
      total paired front-expiry traded contracts;
    - frozen value = 0 when total paired traded contracts = 0.

All features must be finite.

No implied volatility, Greeks, bid-ask spread, Black-Scholes assumptions or
risk-free/dividend inputs are introduced in T009.

## Base and augmented models

Base:

- exact merged T005 37-feature
  price/liquidity/delivery/futures feature set.

Augmented:

- same 37 base features;
- plus the ten frozen T009 option features.

Model:

`ridge`

Frozen l2:

`1.0`

Base and augmented models use identical option-complete symbol/session rows.

## Primary horizon

5 completed NSE sessions.

Folds:

1. 2026-04-01 through 2026-06-30;
2. 2026-07-01 through 2026-09-18.

Paired Newey-West lag:

4.

Primary success requires BOTH:

- augmented-minus-base mean rank IC > 0 with two-sided p < 0.05;
- augmented-minus-base mean top-minus-bottom spread > 0 with two-sided p < 0.05.

## Secondary horizon

1 completed NSE session.

Folds:

1. 2026-04-01 through 2026-06-30;
2. 2026-07-01 through 2026-09-24.

Paired Newey-West lag:

5.

Secondary cannot rescue a failed primary.

## Diagnostic horizon

20 completed NSE sessions.

Folds:

1. 2026-04-01 through 2026-06-30;
2. 2026-07-01 through 2026-08-27.

Paired Newey-West lag:

19.

Diagnostic cannot rescue a failed primary.

## Exact comparison contract

For every horizon:

- same exact symbol+ISIN rows;
- same decision sessions;
- same action-safe labels;
- same folds;
- same ridge l2;
- only difference is base 37 vs augmented 47 features.

Missing/invalid option source rows are excluded from BOTH sides.

They are not backfilled or outcome-selected.

## Frozen upstream lineage

Expected reproducible upstream inputs from sealed T005:

- market panel:
  `9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e`;
- corporate-action ledger:
  `1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1`;
- delivery-augmented panel:
  `99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90`;
- futures panel:
  `02656c828a1d5fe22660c154a445ebd69a7492b56f1807da0d8c959a6f0c11d5`;
- 37-feature futures-augmented panel:
  `62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f`.

D006 source hashes:

`edf21ed30ea4021a82118c8699f1a7470442bcee29155810772a09c4b24bc6dc`

The T009 option-panel and 47-feature-panel hashes must be sealed in a separate
pre-outcome protocol amendment before any model fit is allowed.

## Source timing

The options and futures rows reside in the SAME official FO UDiFF archive.

SC002 is therefore the source-timing authority for any future options
confirmation.

SC002 has not yet frozen a successor decision cutoff.

T009 cannot make a prospective claim.

## Interpretation

T009 tests whether observable options positioning contributes information beyond
the already-supported stock-futures feature family.

Passing T009 does not establish:

- prospective source timing;
- option-trading profitability;
- implied-volatility alpha;
- execution capacity;
- live-capital readiness.

If T009 passes, its incremental prediction should be tested for orthogonality
against the existing T005 futures delta in AB001 before any blender promotion.
