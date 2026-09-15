# H024 historical point-in-time challenge result v1

Status: **SEALED HISTORICAL DEVELOPMENT EVIDENCE**

Result sealed: 2026-09-15
Execution rule: `H024-R001`
Evidence class: `HISTORICAL_POINT_IN_TIME_DEVELOPMENT`
Live capital: disabled

## Official classification

**`INSUFFICIENT_COVERAGE`**

This classification is final for this frozen historical challenge. It must not be upgraded because the observed return statistics are favorable.

The frozen 60-session coverage gate required all of:

- at least 100 complete primary events;
- at least 50 distinct symbols among complete primary events;
- at least 80% completeness among mature primary events.

Observed:

- complete 60-session events: **105**;
- distinct complete symbols: **42**;
- complete share of mature events: **98.13%**.

The distinct-symbol requirement is not met. Therefore the result remains `INSUFFICIENT_COVERAGE` even though the observed performance metrics would otherwise satisfy the frozen `STRONG` thresholds.

## Frozen event construction

The pre-freeze source panel contained:

- 785 qualifying `Original` source filings;
- 158 source symbols.

After applying the already-frozen point-in-time rules:

- 274 filings remained investable/eligible;
- 209 symbol-entry events were formed;
- 79 distinct symbols entered the event panel.

Exclusions from the 785 source filings:

- `LIQUIDITY_BELOW_H004_PRIMARY`: 357;
- `MISSING_ENTRY_EQ_BAR`: 99;
- `NO_ENTRY_SESSION_BEFORE_CUTOFF`: 38;
- `INSUFFICIENT_60_SESSION_PRICE_HISTORY`: 16;
- `REVISION_BLOCKED`: 1.

No exclusion rule was changed after opening returns.

## Primary 60-session result

Among 107 mature events:

- complete events: **105**;
- complete symbols: **42**;
- mean Nifty 500 excess return: **+11.67 percentage points**;
- median Nifty 500 excess return: **+6.60 percentage points**;
- mean cost-adjusted excess after the frozen 0.50pp round-trip stress: **+11.17 percentage points**;
- Nifty 500 beat rate: **64.76%**;
- symbol-cluster bootstrap 95% CI for mean excess: **+1.40pp to +21.65pp**;
- valid bootstrap iterations: 10,000.

Primary-horizon exclusions after event construction:

- `CORPORATE_ACTION_BLOCKED`: 1;
- `MISSING_EXIT_STOCK_BAR`: 1;
- `NOT_MATURE`: 102.

The positive cluster-bootstrap lower bound is material because repeated filings from one issuer do not receive independent bootstrap treatment.

## Pre-frozen robustness views

### First event per symbol

- count: 42;
- distinct symbols: 42;
- mean excess: **+11.59pp**;
- median excess: **+3.18pp**;
- mean cost-adjusted excess: **+11.09pp**;
- benchmark beat rate: **57.14%**.

### Non-overlapping 60-session events

- count: 42;
- distinct symbols: 42;
- mean excess: **+11.59pp**;
- median excess: **+3.18pp**;
- mean cost-adjusted excess: **+11.09pp**;
- benchmark beat rate: **57.14%**.

Both pre-frozen anti-dependence views preserve the positive sign. This argues against the headline result being solely an artifact of repeated same-company events, but it does not repair the failed 50-symbol coverage gate.

## Publication-month robustness

Only May and June events have matured through the 60-session horizon under the frozen market-data cutoff.

### May 2026

- complete events: 33;
- distinct symbols: 12;
- mean excess: **+12.33pp**;
- median excess: **+10.02pp**;
- benchmark beat rate: **78.79%**.

### June 2026

- complete events: 72;
- distinct symbols: 37;
- mean excess: **+11.37pp**;
- median excess: **+4.24pp**;
- benchmark beat rate: **58.33%**.

Both matured publication months are positive. Later months are not used to infer 60-session returns before maturity.

## Purchase-value composition diagnostic

Purchase value is descriptive only and never changes the binary H024-v1 score.

At 60 sessions:

- `<1cr`: 28 events, mean excess **+20.16pp**, median **+9.28pp**;
- `1-10cr`: 48 events, mean excess **+7.23pp**, median **+5.28pp**;
- `10-100cr`: 26 events, mean excess **+11.04pp**, median **+10.86pp**;
- `>=100cr`: 3 events, mean excess **+8.94pp**, median **+4.85pp**.

All frozen value buckets have positive observed mean and median excess. These are composition diagnostics, not evidence for adding value weighting to the primary signal.

## Secondary 20-session result

Among 155 mature events:

- complete events: 152;
- distinct complete symbols: 61;
- mean excess: **+3.86pp**;
- median excess: **+2.09pp**;
- mean cost-adjusted excess: **+3.36pp**;
- benchmark beat rate: **59.21%**;
- symbol-cluster bootstrap 95% CI: **-0.04pp to +8.00pp**.

The 20-session point estimate is positive, but its frozen cluster interval still includes zero. It is secondary evidence only.

## 120-session result

No event is mature at 120 sessions under the frozen market-data cutoff. No 120-session return is inferred or extrapolated.

## Evidence integrity

The sealed artifacts bind:

- source panel SHA-256: `94bb81839c7d868736f830e88a3feb83538a04dfc7be01d546a7839e2bf3d101`;
- event panel SHA-256: `65b957a2a66144194690f0298602ca0118eb4af8e725cce5df7549da6b1baec4`;
- outcome report SHA-256: `09534a5c8fd0427535b6801ed5b80cdf2255ac7c153e95936bafccb205783596`;
- outcome summary SHA-256: `4756419195a3dac4b2663a7bcd6afc00d90293d9080410925ebe296a0a276b42`;
- evidence manifest SHA-256: `ab206942f196c92ad078069aea9f4273e0382a910b034f05196b9a7f8955eb68`.

The run captured 173 official Nifty 500 index artifacts, 173 official NSE UDiFF market files, five PIT-GG discovery artifacts, and 79 corporate-action source artifacts. All 79 event symbols had a resolved corporate-action audit.

## Interpretation

The first frozen historical challenge provides a **strong directional signal but insufficient primary coverage**.

The economically important facts are:

1. the 60-session mean and median excess returns are large and positive;
2. the result remains positive after the fixed cost stress;
3. the benchmark beat rate exceeds the frozen 55% threshold;
4. the symbol-cluster confidence interval is above zero;
5. first-event and non-overlapping-event robustness remain positive;
6. both mature publication months remain positive;
7. the result does not meet the pre-frozen distinct-symbol coverage gate.

Therefore H024 should **not** be promoted or reweighted from this historical result. The superior next test is the already-frozen fully prospective stream beginning at the September 16, 2026 boundary. Its event and outcome rules must remain unchanged.

Industry robustness is intentionally reported as unavailable because a pre-event industry-classification source was not frozen before the challenge. No post-outcome industry reconstruction may be used to retroactively satisfy that diagnostic.

## Decision

- historical result classification: `INSUFFICIENT_COVERAGE`;
- mechanism status: directionally strong enough to continue prospectively;
- signal definition: unchanged;
- thresholds: unchanged;
- historical result may not authorize live capital;
- prospective validation remains mandatory.
