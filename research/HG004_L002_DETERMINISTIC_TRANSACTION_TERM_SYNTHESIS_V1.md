# HG004-L002 Deterministic Company Transaction-Term Synthesis v1

Status: **FROZEN BEFORE PAYOFF-MODEL CONSTRUCTION**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Collapse the 19 validated HG004-L001 document-level extractions into one deterministic
company-level transaction-underwriting state for each of the 11 HG004 companies.

L002 answers:

> Which economic payoff models are justified by explicit source terms today, and which
> critical terms are still missing?

L002 does not estimate expected return, completion probability or intrinsic value.

## Frozen source

Use exactly:

- HG004-L001-GPT56SOL-NATIVE-v1;
- workflow run: `37296227681`;
- artifact ID: `11338148751`;
- run SHA-256:
  `a402b39a8890cd2fac3218bb94673f8b9c00b1f325315f9ec93863c22d9a1d12`;
- result SHA-256:
  `d96e7a865fb27eb7dd4f32ff49f0c3ad58bed127003759e3ec0fffa2e312cc2a`;
- 19 validated document outputs;
- 11 HG004 symbols.

No later L001 rerun may be substituted under L002-v1.

## Frozen symbols

Exactly:

- ANANTRAJ
- AXITA
- DATAMATICS
- DEVX
- FCL
- INOXGREEN
- NPST
- SAMBHV
- SANDESH
- SUVIDHAA
- TREL

## Synthesis principle

L002 is rule-based.

It may:

- merge explicit facts from multiple documents for the same company/semantic cluster;
- retain multiple independent economic lanes for one company;
- identify missing inputs required for a later payoff model;
- calculate simple source-accounting counts.

It may not:

- resolve contradictory terms by discretion;
- infer a missing transaction term;
- assign a valuation multiple;
- estimate transaction completion probability;
- rank the 11 names;
- use stock returns or future outcomes.

## Frozen model-readiness lanes

### DEMERGER_ENTITLEMENT

Eligible when all are true:

- DIRECT_LISTED_SECURITY;
- transaction family includes SCHEME_REORGANISATION;
- explicit exchange-ratio text exists;
- source describes a demerger/separation/value-unlock transaction rather than only a
  wholly owned subsidiary amalgamation.

Readiness state:

- `READY_DEMERGER_ENTITLEMENT`.

Downstream model still requires an independently sourced valuation of the separated
business(es).

### ACQUISITION_ECONOMICS

Eligible when:

- relevance is LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR;
- family includes ACQUISITION_INVESTMENT;
- target/asset description is explicit.

If total/cash consideration is explicit:

- `READY_ACQUISITION_ECONOMICS`.

Otherwise:

- `PARTIAL_ACQUISITION_TERMS_REQUIRED`.

Ready acquisition models still require financing/funding and normalized target economics
when those are not explicit in the event document.

### DILUTION_FINANCING

Eligible for a direct listed-company PREFERENTIAL_WARRANT / preferential financing
thread when:

- issue/exercise price is explicit;
- security count is explicit;
- current transaction is not merely a final historical monitoring/forfeiture report.

Then:

- `READY_DILUTION_FINANCING`.

A later dilution/payoff model must obtain current fully diluted shares and current price
from deterministic market/company-size sources.

### CAPITAL_DEPLOYMENT_MONITOR

Eligible when:

- family includes FUND_RAISE_OTHER;
- explicit amount raised/issue size exists;
- explicit use-of-proceeds or deployment-progress evidence exists.

If the document represents a still-live deployment program:

- `READY_CAPITAL_DEPLOYMENT_MONITOR`.

If it is a completed/final historical utilization or forfeiture report with no current
forward capital-deployment event:

- `HISTORICAL_FINANCING_MONITOR`.

### RIGHTS_TERMS

For a direct listed-company RIGHTS_ISSUE:

- if issue price and entitlement ratio are explicit:
  `READY_RIGHTS_PAYOFF`;
- otherwise:
  `PARTIAL_RIGHTS_TERMS_REQUIRED`.

### INTERNAL_REORGANISATION

A wholly owned subsidiary merger/amalgamation with:

- no consideration; and
- no new listed-company shares / no exchange ratio

is:

- `PROCEDURAL_INTERNAL_REORGANISATION`.

It does not receive a standalone event-payoff model unless later evidence identifies a
material asset, tax, cash-flow or valuation consequence.

## Company primary state

A company may carry multiple lanes.

The primary state is selected by this frozen precedence:

1. READY_ACQUISITION_ECONOMICS
2. READY_DEMERGER_ENTITLEMENT
3. READY_DILUTION_FINANCING
4. READY_RIGHTS_PAYOFF
5. READY_CAPITAL_DEPLOYMENT_MONITOR
6. PARTIAL_ACQUISITION_TERMS_REQUIRED
7. PARTIAL_RIGHTS_TERMS_REQUIRED
8. HISTORICAL_FINANCING_MONITOR
9. PROCEDURAL_INTERNAL_REORGANISATION

The precedence is workflow routing only, not expected-return ranking.

## Explicit missing-input vocabulary

L002 may attach only the following missing-input codes:

- CURRENT_MARKET_PRICE
- CURRENT_MARKET_CAP
- CURRENT_FULLY_DILUTED_SHARE_COUNT
- SEPARATED_BUSINESS_EARNINGS
- SEPARATED_BUSINESS_VALUATION_REFERENCE
- ACQUISITION_FUNDING_STRUCTURE
- TARGET_NORMALIZED_EARNINGS_OR_CASH_FLOW
- FINAL_PURCHASE_PRICE_OR_ADJUSTMENTS
- RIGHTS_ISSUE_PRICE
- RIGHTS_ENTITLEMENT_RATIO
- RIGHTS_RECORD_DATE
- TRANSACTION_EFFECTIVE_DATE
- CURRENT_CAPITAL_DEPLOYMENT_UPDATE
- OTHER_EXPLICIT_SOURCE_REQUIRED

These are research tasks, not model assumptions.

## Frozen expected company-state implications from source semantics

The rules above are expected to route:

- ANANTRAJ: demerger entitlement lane;
- INOXGREEN: acquisition economics + demerger entitlement lanes;
- DEVX: dilution financing + capital deployment lanes;
- SAMBHV: dilution financing lane;
- NPST: capital-deployment monitoring lane;
- AXITA: partial acquisition terms;
- SUVIDHAA: partial rights terms;
- FCL: historical financing monitor;
- DATAMATICS, SANDESH, TREL: procedural internal reorganisations.

These expectations are frozen before L002 materialization. A mismatch fails closed and
requires a source/rule amendment rather than discretionary relabeling.

## Promotion

Passing L002 permits HG005 source-enrichment / family-specific payoff-model protocols.

It does not itself authorize any payoff estimate.

## Scientific boundary

L002 does not:

- calculate expected return;
- assign completion probability;
- set a valuation multiple;
- create a target price;
- rank the cohort;
- create an ADO;
- modify PF001;
- authorize live capital.
