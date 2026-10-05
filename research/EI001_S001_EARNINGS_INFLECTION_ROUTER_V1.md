# EI001-S001 Full-Market Earnings Inflection Research Router v1

Status: **FROZEN BEFORE ROUTER MATERIALIZATION**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Convert the passed EI001-D002 same-quarter comparative fact plane into deterministic
earnings-inflection research states.

S001 is a research router, not an alpha model and not a return forecast.

## Frozen source

Use exactly:

- EI001-D002-v1;
- workflow run: `37217767159`;
- artifact ID: `11308929215`;
- panel SHA-256:
  `14fdc99444ff8c1c62cbef58db91e51cb4cb6730c1259bccb98df979366272cd`;
- 2,319 frozen SS001 identities;
- 1,783 names with comparable revenue and PAT;
- 1,792 names with comparable PBT, finance cost, depreciation and basic EPS.

No later financial filing may replace this source under S001-v1.

## Eligible comparable facts

S001 may use only rows whose EI001-D002 comparable family is
`COMPARABLE_READY`.

No missing fact is imputed.

## Frozen derived diagnostics

For positive nonzero prior values:

`yoy_growth = current / prior - 1`

PBT margin:

`pbt_margin = pbt / revenue`

Margin change:

`pbt_margin_delta_pp = 100 * (current_margin - prior_margin)`

## Frozen positive inflection flags

### REVENUE_GROWTH_15

- prior revenue > 0;
- current revenue > 0;
- revenue YoY >= +15%.

### PAT_GROWTH_25

- prior PAT > 0;
- current PAT > 0;
- PAT YoY >= +25%.

### PBT_MARGIN_EXPANSION_200BPS

- prior revenue > 0;
- current revenue > 0;
- prior PBT > 0;
- current PBT > 0;
- PBT margin change >= +2.00 percentage points.

### LOSS_TO_PROFIT_TURNAROUND

- prior PAT < 0;
- current PAT > 0.

### EPS_GROWTH_25

- prior basic EPS > 0;
- current basic EPS > 0;
- basic EPS YoY >= +25%.

### FINANCE_COST_RELIEF_15

- prior finance cost > 0;
- current finance cost >= 0;
- finance cost YoY <= -15%;
- current revenue >= 95% of prior revenue.

This is a supporting flag only.

## Frozen negative/caution diagnostics

### REVENUE_CONTRACTION_10

- prior revenue > 0;
- current revenue >= 0;
- revenue YoY <= -10%.

### PROFIT_BREAKDOWN

Either:

- prior PAT > 0 and current PAT <= 0; or
- prior PAT > 0, current PAT > 0 and PAT YoY <= -25%.

### PBT_MARGIN_COMPRESSION_200BPS

- prior and current revenue > 0;
- prior and current PBT > 0;
- PBT margin change <= -2.00 percentage points.

## Frozen research state

`STRONG_INFLECTION` when any is true:

1. LOSS_TO_PROFIT_TURNAROUND; or
2. REVENUE_GROWTH_15 and PAT_GROWTH_25; or
3. PAT_GROWTH_25 and PBT_MARGIN_EXPANSION_200BPS.

`SUPPORTED_INFLECTION` when not STRONG and at least two positive flags are present,
excluding FINANCE_COST_RELIEF_15 from satisfying both flags by itself.

`SINGLE_POSITIVE_SIGNAL` when exactly one non-supporting positive flag is present.

`NO_POSITIVE_INFLECTION` otherwise.

Negative diagnostics never create a positive state.

## Scientific boundary

S001 does not:

- use stock returns;
- use valuation;
- use analyst estimates;
- sector-normalize thresholds;
- tune thresholds on outcomes;
- predict next-quarter earnings;
- create portfolio eligibility;
- authorize live capital.
