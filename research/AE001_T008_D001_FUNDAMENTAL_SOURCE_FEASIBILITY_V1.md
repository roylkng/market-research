# AE001 T008-D001 Fundamental Filing Source Feasibility v1

Status: FROZEN BEFORE SOURCE DIAGNOSTIC
Frozen: 2026-09-30
Live capital: DISABLED

## Objective

Measure whether official NSE Integrated Financial filings provide sufficient
point-in-time, same-basis quarterly facts to support a new fundamental
growth/profitability alpha family.

D001 is a source/feature feasibility diagnostic only.

It does not open stock returns and it does not test alpha.

## Frozen cohort

Use the existing 100-member U001 snapshot:

`research/prospective/universes/FY27-Q2-2026-09-06.json`

Expected universe SHA-256:

`cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb`

No member may be added because its filing is convenient.

## Period pair

Target quarter end:

`2026-06-30`

Prior-year same-quarter baseline:

`2025-06-30`

This pair is fully historical as of D001 and is used only to measure source and
feature coverage.

## Filing selection

For each symbol:

1. query the official NSE Integrated Filing - Financials discovery source;
2. consider only the frozen target/baseline period ends;
3. require the same accounting basis for both periods;
4. prefer Consolidated only when both periods have a usable Consolidated filing;
5. otherwise use Standalone only when both periods have a usable Standalone filing;
6. target event = earliest official target-period publication for that basis;
7. baseline = latest official baseline-period publication that was already public
   strictly before the target event;
8. a same-timestamp multi-URL ambiguity fails closed;
9. later target revisions may be retained as evidence but cannot replace the
   first target event.

## Exact evidence

Retain:

- exact discovery JSON bytes and SHA-256;
- exact selected target filing bytes and SHA-256;
- exact selected baseline filing bytes and SHA-256;
- official discovery-row hashes;
- exchange publication timestamps;
- parsed FinancialEvent payloads.

Historical reconstruction capture time is never used as historical availability.

## Frozen facts

D001 may use only facts already parsed directly by MarketLab:

- revenue_from_operations;
- profit_before_tax;
- total_profit;
- exceptional_items.

EPS is measured for source diagnostics but is not part of the proposed T008
feature family because share-count changes complicate raw YoY comparability.

No balance-sheet, cash-flow, market-cap, share-count, ROE, ROIC, FCF or valuation
fact may be inferred.

## Monetary normalization

A filing pair is monetary-comparable only when both filings are INR.

Normalization is source-format aware:

- native XBRL numeric facts are already actual currency amounts and are not
  multiplied again by presentation-rounding metadata;
- legacy Integrated Filing HTML/table values are presentation values and must be
  converted to INR using their explicit rounding metadata.

Allowed HTML/table rounding families:

- actual / rupees / units -> 1;
- thousands -> 1,000;
- lakhs -> 100,000;
- millions -> 1,000,000;
- crores -> 10,000,000.

Unknown currency or required HTML/table rounding fails closed for monetary
features.

## Candidate T008 features

When required facts are finite and denominators are valid:

1. revenue_yoy
   = revenue_t / revenue_yago - 1

2. pbt_change_to_prior_revenue
   = (pbt_t - pbt_yago) / abs(revenue_yago)

3. total_profit_change_to_prior_revenue
   = (profit_t - profit_yago) / abs(revenue_yago)

4. pbt_margin
   = pbt_t / revenue_t

5. pbt_margin_delta_yoy
   = pbt_t / revenue_t - pbt_yago / revenue_yago

6. total_profit_margin_delta_yoy
   = profit_t / revenue_t - profit_yago / revenue_yago

Exceptional-items/revenue is coverage-diagnostic only in D001 and is not frozen
as a T008 alpha feature.

## Feasibility thresholds

D001 does not automatically create T008.

Report exact coverage for every feature.

A later T008 alpha trial may be frozen only if:

- at least 70 of 100 U001 members have a same-basis filing pair;
- at least 60 members have all six candidate features;
- no monetary normalization rule is changed after D001 outcomes are inspected.

If these thresholds fail, either improve source parsing under a new source
diagnostic or abandon this family. Do not lower thresholds post hoc.

## Non-goals

- no return labels;
- no model fitting;
- no feature weighting;
- no winsorization;
- no imputation;
- no live trading.

Live capital remains disabled.
