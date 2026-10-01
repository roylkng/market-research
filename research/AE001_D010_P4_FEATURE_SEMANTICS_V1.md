# AE001 D010 P4 Short/Borrow Feature Semantics v1

Status: FROZEN BEFORE FEATURE MATERIALIZATION
Frozen: 2026-10-01
Live capital: DISABLED

## Objective

Convert the historically validated CM Short Selling and SLB Daily Open Positions
sources into deterministic AE001 feature semantics without opening return labels
or fitting a predictive model.

P4 answers only:

> Given the source reports and their resolved timing/identity contracts, what
> numerical features are allowed to enter a later alpha trial?

## Frozen upstream evidence

CM Short Selling:
- D010-P3B report SHA:
  0cc1f518d8c91d4648851d55861cee66cca722c0e1858204cbdd6635f7c98528
- file named for publication session D contains short-selling trades from the
  previous completed NSE cash session D-1;
- 265/266 publication sessions READY;
- 99.541% trade-date identity mapping;
- 99.980% same-ISIN continuity into publication session.

SLB Daily Open Positions:
- D010-P3 report SHA:
  e41e749a9d0514ffc4a01af6dd923d6c838e898320bf0e4f0e699bafc9d8dd27
- 266/266 sessions READY;
- one stable schema;
- 97.972% identity mapping.

## Short-selling semantic contract

Regulatory/publication context establishes a scrip-wise consolidated short-sale
report. The historical audit independently proves the one-session publication
lag.

For publication session D:

1. the source trade date must equal previous completed NSE session D-1;
2. source Symbol Name maps to D-1 official UDiFF EQ symbol+ISIN;
3. the same ISIN must exist on D;
4. duplicate mapped ISIN rows fail closed;
5. on a READY, parser-valid file, an eligible mapped identity absent from the
   report is assigned reported short quantity = 0;
6. an unavailable/parser-rejected file never implies zero.

Current short quantity is therefore information about D-1 activity observed in
the file associated with D.

## SLB semantic contract

NSE SLB series identify distinct reverse-settlement contracts. Monthly series
01..12 and X1..XD represent separate contracts, and R3 is a separate short-tenure
contract.

For session D:

1. source Security maps to same-session UDiFF EQ symbol+ISIN;
2. duplicate symbol+series rows fail closed;
3. outstanding quantity is additive across DISTINCT series for the same ISIN;
4. current active-series count is the number of distinct reported series;
5. on a READY, parser-valid file, an eligible identity absent from the report is
   assigned SLB outstanding quantity = 0 and active-series count = 0;
6. an unavailable/parser-rejected file never implies zero.

No maturity weighting is introduced in v1.

## Frozen features

Seven features are allowed.

### 1. short_volume_share_lag1

    reported_short_quantity_(D-1) / cash_traded_volume_(D-1)

### 2. short_volume_share_change_1

    short_volume_share_lag1(D)
    - short_volume_share_lag1(previous completed publication session)

### 3. short_volume_share_zscore_20

Current short-volume share standardized against the PRIOR 20 completed,
source-valid publication sessions for the same ISIN.

If prior standard deviation is zero, value is null.

### 4. slb_outstanding_days_volume20

    total_SLB_outstanding_quantity_D
    / median_cash_traded_volume_(prior 20 completed NSE sessions)

Current D cash volume is not included in this denominator.

### 5. slb_outstanding_change_days_volume20

    (total_SLB_outstanding_D - total_SLB_outstanding_(D-1))
    / median_cash_traded_volume_(prior 20 completed NSE sessions)

### 6. slb_outstanding_zscore_20

Current total SLB outstanding quantity standardized against the PRIOR 20
source-valid publication sessions for the same ISIN.

If prior standard deviation is zero, value is null.

### 7. slb_active_series_count

Number of distinct SLB series with an outstanding-position row for the ISIN on D.

## History and missingness

A P4 feature row requires:

- the identity is already eligible in the supplied AE001 action-safe base panel;
- current short and SLB source sessions are READY;
- 20 immediately preceding completed NSE publication sessions are available for
  both source families;
- exact symbol+ISIN continuity through the required source joins;
- positive required cash-volume denominators.

Any source gap breaks the 21-session feature window.

No interpolation.

No zero fill for an unavailable file.

No future information.

## P4 output

P4 augments the existing action-safe 18-feature AE001 panel with the seven frozen
D010 features on the common source-complete rows.

The output contains no return outcomes.

## Timing limitation

Historical archive availability does NOT establish intraday publication time.

P4 evidence class:

    HISTORICAL_RECONSTRUCTION_DEVELOPMENT_SOURCE_TIMING_UNVERIFIED

A future prospective alpha claim requires a separately frozen live source-timing
gate for BOTH:

- shortselling_DDMMYYYY.csv;
- slb_openpos_DDMMYYYY.csv.

## P4 audit gates

Materialization passes only when:

- feature set is exactly 25 = 18 base + 7 D010;
- at least 200 completed feature sessions survive warmup/source gaps;
- at least 100,000 feature rows survive;
- every row has exact symbol+ISIN identity;
- no infinite numeric feature exists;
- no outcome is attached;
- short and SLB source-report hashes are bound in the artifact.

No predictive usefulness gate exists in P4.

## Promotion

A passing P4 may proceed to a separately pre-registered historical-development
incremental alpha trial.

No live-capital implication.
