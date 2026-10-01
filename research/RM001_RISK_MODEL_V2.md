# RM001 Transparent Equity Risk Model v2

Status: DEVELOPMENT BASELINE
Frozen initial specification: 2026-10-01
Live capital: DISABLED

## Objective

Extend RM001-v1 with a validated point-in-time total-market-cap SIZE factor while
preserving all RM001-v1 artifacts and hashes unchanged.

RM001-v2 is a separate model ID. RM001-v1 remains immutable.

## Promoted source

D007 result:

- protocol: research/RM001_D007_SECURITY_MASTER_SIZE_FEASIBILITY_V1.md
- result: research/rm001-d007-result-v1.json
- result SHA: 4151612cb85c88d605344fd018fab85118c295e71a90fabbe6c2223d15f27c14

Official daily source:

    https://nsearchives.nseindia.com/content/cm/
    NSE_CM_security_DDMMYYYY.csv.gz

Frozen size formula:

    TOTAL_MARKET_CAP_INR = OFFICIAL_NSE_CLOSE * IssdCptl

Identity join:

    same-session symbol + ISIN

ParVal is retained as source metadata and is not used in the size formula.

## Factor set

RM001-v2 factors:

1. MARKET_COMMON
2. BETA60_RELATIVE
3. MOMENTUM20
4. VOLATILITY60
5. LIQUIDITY
6. SIZE

The first five definitions are identical to RM001-v1.

### SIZE

For each completed decision session:

1. join the action-safe AE001 eligible cross-section to the same-session D007
   Security File by exact symbol + ISIN;
2. compute total market cap using official close * IssdCptl;
3. preserve only finite positive market caps;
4. compute tie-aware within-session market-cap percentile over the exact
   RM001-v2 common cross-section;
5. transform to:

       SIZE = 2 * percentile(total_market_cap_inr) - 1

Therefore:

- smallest eligible names approach -1;
- median names approach 0;
- largest eligible names approach +1.

No free-float adjustment is used.

## Missing size

A feature row without an exact finite positive same-session total-market-cap join
is excluded from RM001-v2.

No symbol-only carry-forward.
No current-value backfill.
No size imputation.

D007 historical minimum exact join coverage was 99.457%, so this exclusion is
expected to be small.

## Factor-return estimation

Unchanged from RM001-v1 except for the sixth factor.

For exposure session D:

- exposures use only information available through D;
- response is exact same-identity close-to-close return from D to the next
  completed NSE session;
- share-changing corporate actions fail closed;
- equal-weight cross-sectional OLS;
- minimum 100 observations;
- full-rank six-factor design required.

## Factor covariance

Unchanged:

- latest 60 completed factor-return observations with realized session <= D;
- ordinary sample covariance;
- ddof = 1;
- no shrinkage in v2.

## Idiosyncratic risk

Unchanged:

- latest up to 60 residual observations per current identity;
- minimum 20;
- sample variance ddof = 1;
- conservative current-universe p75 fallback for insufficient histories.

## Canonical serialization

Same as RM001-v1:

- persisted floats rounded to 15 decimal places.

## Historical evidence class

Historical RM001-v2 materialization using archived Security Files is:

    HISTORICAL_RECONSTRUCTION_DEVELOPMENT

D007 proved historical source completeness, not live publication timing.

## Prospective limitation

The Security File may not be used in a prospective RM001-v2 decision until a
separate source-timing stream proves the exact same-session Security File was
captured by the frozen EOD decision cutoff.

Until then:

    PROSPECTIVE_SIZE_SOURCE_TIMING_VERIFIED = false

## Deferred factors

### Free-float size

DEFERRED_SOURCE_NOT_POPULATED.

D007 observed 0% positive FreeFltCptl coverage.

### Sector / industry

DEFERRED_POINT_IN_TIME_COMPANY_CLASSIFICATION_SOURCE_NOT_FROZEN.

D007 confirmed the Security File does not materially populate company industry
classification fields.

## Promotion

RM001-v2 is eligible for:

- historical alpha risk attribution;
- historical PO001 size-exposure diagnostics;
- development portfolio optimization.

It is not eligible for:

- prospective size-aware risk decisions before source-timing validation;
- sector-neutral optimization;
- live capital.
