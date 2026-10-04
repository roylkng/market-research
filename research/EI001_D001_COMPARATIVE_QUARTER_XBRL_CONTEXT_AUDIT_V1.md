# EI001-D001 Current-vs-Prior-Year Quarter XBRL Context Audit v1

Status: **FROZEN BEFORE EI001 SOURCE ACCESS**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Objective

Determine whether current official NSE Q1 FY27 Integrated Filing XBRL contains explicit,
deterministic same-quarter-prior-year facts suitable for a full-market earnings-inflection
plane.

EI001-D001 is a source/context audit only. It does not calculate growth, rank companies,
or infer an earnings surprise.

## Frozen sample

Use exactly:

`research/fa001/fa001-d001-sample-v1.json`

48 liquidity-stratified NSE symbols selected before FA001/EI001 outcomes.

## Current filing source

For each sample symbol, use official NSE Integrated Filing - Financials discovery and
select the same 2026-06-30 quarterly filing candidate under the FA001 basis preference:

1. prefer the accounting basis selected for exact FY26 annual filing when available;
2. otherwise Consolidated;
3. otherwise Standalone.

Selection implementation authority:

`src/marketlab/fa001_schema_audit.py::select_audit_filings`

## Frozen comparative contexts

### Current Q1 FY27

Require a non-dimensional duration context:

- endDate = 2026-06-30;
- duration = 80-100 calendar days.

### Prior-year Q1 FY26

Require a non-dimensional duration context:

- endDate = 2025-06-30;
- duration = 80-100 calendar days.

No YTD, annual, instant, dimensional, reconstructed, or arithmetic-derived comparable is
permitted in D001.

## Frozen fact families

Audit exact FA001 alias families for:

- revenue;
- PAT;
- PBT;
- finance costs;
- depreciation/amortisation;
- basic EPS.

For each family and period retain:

- selected concept;
- numeric value;
- contextRef;
- unitRef;
- ambiguity/missing state.

Alias precedence is exactly the FA001 frozen alias order. A later alias may be used only
when an earlier alias lacks a deterministic value in the required context set.

## Comparable readiness

A family is COMPARABLE_READY only when:

1. current and prior-year values are each deterministic numeric facts;
2. current and prior-year unitRef are both present;
3. unitRef strings match exactly;
4. neither context is dimensional.

D001 does not convert currencies or units.

## Frozen feasibility gates

D001 passes only if all are true:

1. at least 40/48 sample symbols have a usable 2026-06-30 XBRL;
2. at least 75% of usable current filings have COMPARABLE_READY revenue;
3. at least 75% have COMPARABLE_READY PAT;
4. at least 70% have both revenue and PAT COMPARABLE_READY;
5. at least 60% have revenue, PAT and PBT COMPARABLE_READY;
6. no comparable is constructed from annual/YTD arithmetic or external data.

Thresholds may not be lowered after audit output is opened.

## Promotion

Passing D001 permits a separately frozen EI001-D002 full-market comparative-quarter fact
plane and then an EI001-S001 deterministic inflection candidate screen.

## Scientific boundary

D001 does not:

- calculate YoY growth;
- calculate margin change;
- calculate earnings acceleration;
- compare with stock price;
- use analyst estimates;
- use LLM inference;
- use future returns;
- create ADO/PF001/live-capital eligibility.
