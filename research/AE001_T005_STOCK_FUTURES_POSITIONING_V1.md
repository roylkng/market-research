# AE001 T005 NSE Stock-Futures Positioning Feature Trial v1

Status: FROZEN BEFORE OUTCOME MATERIALIZATION
Frozen: 2026-09-30
Live capital: DISABLED

## Objective

Test whether official NSE stock-futures contract structure adds incremental
cross-sectional information beyond the merged 27-feature AE001
price/liquidity/delivery model.

T005 is a new feature-family trial. It does not modify T003/T004.

## Historical source window

2025-09-01 through 2026-09-25.

Evidence class:

`HISTORICAL_RECONSTRUCTION_DEVELOPMENT`

Historical FO publication timestamps are not preserved by the archive.
Therefore T005 may establish historical information content only. It cannot count
as prospective validation.

## Official derivative source

NSE display report:

`F&O - UDiFF Common Bhavcopy Final (zip)`

Direct archive convention verified by D001:

`https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip`

D001 reference session: 2026-09-25.

Verified D001 schema includes:

- FinInstrmTp;
- TckrSymb;
- XpryDt / FininstrmActlXpryDt;
- settlement/close/previous close;
- underlying price;
- open interest;
- change in open interest;
- traded volume;
- transferred value;
- trade count;
- board lot.

Verified instrument code for stock futures:

`STF`

The 2026-09-25 source contained 629 STF contract rows.

## Identity

FO UDiFF stock-futures rows do not carry a usable equity ISIN.

Every futures symbol is rebound on the same session to the exact NSE CM EQ
symbol+ISIN identity from the official cash UDiFF panel.

No symbol-only historical identity is allowed beyond that same-session join.

## Contract selection

For one symbol/session:

1. retain only valid `STF` contracts with expiry >= trade date;
2. sort by actual expiry date, then financial instrument ID;
3. front contract = earliest expiry;
4. next contract = second distinct expiry;
5. all listed stock-future expiries are used for total-OI / total-volume fields.

A row requires at least two distinct valid expiries.

No synthetic continuous futures price is created.

## Frozen T005 feature family

Ten raw derivative features:

1. `fut_front_basis`
   - front settlement / cash close - 1.

2. `fut_front_log_basis_per_day`
   - log(front settlement / cash close) / calendar days to front expiry.

3. `fut_next_log_basis_per_day`
   - log(next settlement / cash close) / calendar days to next expiry.

4. `fut_curve_slope_per_day`
   - next log basis/day - front log basis/day.

5. `fut_front_oi_change_fraction`
   - front change-in-OI / front prior OI;
   - prior OI = current OI - change in OI;
   - requires prior OI > 0.

6. `fut_total_oi_change_fraction`
   - sum(change in OI across valid expiries) / summed prior OI;
   - requires summed prior OI > 0.

7. `fut_front_oi_share`
   - front OI / total OI across valid expiries.

8. `fut_total_volume_to_oi`
   - sum(traded contracts * board lot) / total OI.

9. `fut_notional_to_cash_turnover`
   - sum FO transferred value across valid stock-future expiries /
     same-session cash traded value.

10. `fut_front_settlement_return_1`
    - front settlement / front previous close - 1.

All features must be finite.

No discretionary long-buildup/short-buildup labels are added in v1. The ridge may
learn only linear combinations of the frozen numeric fields.

## Base and augmented models

Base:

- exact merged 27 AE001 price/liquidity/delivery features.

Augmented:

- same 27 base features;
- plus the ten frozen T005 futures features.

Model family:

`ridge`

Frozen l2:

`1.0`

Base and augmented models use identical futures-complete stock/session rows.

## Horizons

### Primary

5 completed NSE sessions.

Folds:

1. 2026-04-01 through 2026-06-30;
2. 2026-07-01 through 2026-09-18.

Paired Newey-West lag: 4.

Primary success requires BOTH:

- augmented-minus-base mean rank IC > 0 with two-sided p < 0.05;
- augmented-minus-base mean top-minus-bottom spread > 0 with two-sided p < 0.05.

### Secondary

1 completed NSE session.

Folds:

1. 2026-04-01 through 2026-06-30;
2. 2026-07-01 through 2026-09-24.

Paired Newey-West lag: 5.

Secondary cannot rescue a failed primary.

### Diagnostic

20 completed NSE sessions.

Folds:

1. 2026-04-01 through 2026-06-30;
2. 2026-07-01 through 2026-08-27.

Paired Newey-West lag: 19.

Diagnostic cannot rescue a failed primary.

## Exact comparison contract

For every horizon:

- same exact symbol+ISIN rows;
- same feature sessions;
- same action-safe labels;
- same folds;
- same ridge l2;
- only difference is base 27 vs augmented 37 features.

Missing/invalid FO source rows are excluded from BOTH sides. They are not imputed.

## Source-quality rules

Whole FO session fails closed if:

- archive is not a ZIP with exactly one CSV;
- required UDiFF columns are missing;
- trade date/segment/source contract is inconsistent.

Individual symbol/session futures row is excluded if:

- fewer than two distinct valid stock-futures expiries;
- non-positive settlement/cash price;
- non-positive board lot;
- non-positive required OI denominators;
- duplicate expiry/financial-instrument ambiguity;
- nonfinite derived feature.

Exact raw FO bytes are retained content-addressed.

## Interpretation

T005 may establish that stock-futures positioning/term-structure information adds
historical OOS cross-sectional information beyond AE001.

It does NOT establish:

- prospective validation;
- calibrated execution value;
- an options alpha;
- participant/FII category alpha;
- live-capital readiness.

Participant-wise OI/trading-volume and FII derivative statistics are explicitly
deferred to a separate market-regime feature family.
