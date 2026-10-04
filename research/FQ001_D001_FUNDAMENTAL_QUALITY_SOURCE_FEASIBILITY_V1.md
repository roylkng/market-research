# FQ001-D001 Fundamental Quality Source Feasibility v1

Status: **FROZEN BEFORE SOURCE DIAGNOSTIC**
Frozen: 2026-10-04
Return outcomes opened: no
Portfolio eligibility: disabled
Live capital: disabled

## Objective

Determine whether official NSE Integrated Filing - Financials documents provide enough
point-in-time annual balance-sheet and cash-flow data to support a new fundamental-quality
layer for the frozen 100-company U001 research universe.

FQ001-D001 is source and metric feasibility only. It is not an alpha test and does not
rank companies.

## Frozen universe

Use exactly:

`research/prospective/universes/FY27-Q2-2026-09-06.json`

Expected SHA-256:

`cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb`

No company may be added because its filing is easier to parse.

## Frozen annual filing pair

Target financial year end:

`2026-03-31`

Baseline financial year end:

`2025-03-31`

For each U001 symbol:

1. query the existing official NSE Integrated Filing - Financials discovery source;
2. require the same accounting basis for target and baseline;
3. prefer Consolidated only when both years have a usable Consolidated filing;
4. otherwise use Standalone only when both years are usable;
5. target = earliest official filing for FY26 on that basis;
6. baseline = latest FY25 filing on that basis already public before the target;
7. same-timestamp multi-URL ambiguity fails closed;
8. preserve discovery bytes, filing bytes, URLs, exchange timestamps and SHA-256s.

These selection rules reuse the already-audited T008 filing-pair machinery. They do not
reuse T008's failed alpha model.

## Frozen raw facts

Only explicit filing facts may be used. No balance-sheet or cash-flow value may be
inferred from another fact.

Target and baseline facts:

- revenue from operations;
- profit before tax;
- finance costs;
- total profit for period;
- total assets;
- total equity;
- total current liabilities;
- cash and cash equivalents;
- current borrowings;
- non-current borrowings;
- net cash flow from operating activities;
- purchase of property, plant and equipment.

All monetary values must be normalized to INR using explicit filing metadata.

XBRL facts are treated as actual currency amounts. Rendered HTML/table amounts use the
explicit presentation-rounding scale.

Missing values remain missing. Zero is accepted only when explicitly filed as zero.

## Frozen quality diagnostics

Exactly six core metrics are evaluated for source feasibility.

### 1. ROCE proxy

`EBIT_proxy = PBT + finance_costs`

`capital_employed = total_assets - current_liabilities`

`ROCE_proxy = EBIT_proxy_target / mean(capital_employed_target, capital_employed_baseline)`

This is an accounting proxy, not a claim that it equals a company's reported ROCE.

### 2. Cash conversion

`CFO_to_PAT = operating_cash_flow / profit_after_tax`

### 3. Cash conversion after PPE investment

`CFO_minus_PPE_to_PAT = (operating_cash_flow - abs(PPE_purchases)) / profit_after_tax`

This deliberately does not call itself full free cash flow because other capitalized
investment may exist.

### 4. Accrual intensity

`accruals_to_avg_assets = (profit_after_tax - operating_cash_flow) / average(total_assets)`

Lower values generally indicate stronger cash backing, but D001 makes no ranking claim.

### 5. Net borrowings to equity

`net_borrowings_to_equity = (current_borrowings + noncurrent_borrowings - cash) / total_equity`

Current investments are not netted because their liquidity/economic role is not assumed.

### 6. PPE capital intensity

`PPE_capex_to_revenue = abs(PPE_purchases) / revenue`

## Feasibility thresholds

The quality layer may proceed to a separately frozen scoring/design stage only if:

- at least 70 of 100 U001 members have a same-basis FY26/FY25 annual filing pair;
- at least 60 members have all six core metrics available;
- every individual core metric has coverage of at least 60 members.

Thresholds may not be lowered after the diagnostic output is opened.

Passing D001 permits only design of the next quality-scoring experiment. It does not
establish alpha and does not permit PF001 use.

## Explicit exclusions

D001 does not:

- use stock prices or future returns;
- fit a model;
- assign quality weights;
- optimize thresholds;
- compare sectors;
- infer working capital from unavailable fields;
- calculate incremental ROCE;
- create an Analyst Decision Object;
- authorize PF001 or live capital.

The next stage may add working-capital and incremental-capital diagnostics only under a
new frozen amendment after source coverage is known.
