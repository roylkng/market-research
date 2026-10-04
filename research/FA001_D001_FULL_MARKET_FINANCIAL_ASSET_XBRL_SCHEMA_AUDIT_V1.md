# FA001-D001 Full-Market Financial/Asset XBRL Schema Audit v1

Status: **FROZEN BEFORE FA001 SOURCE ACCESS**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Objective

Determine whether current official NSE Integrated Filing - Financials XBRL provides a
stable enough cross-company schema to support the Small-Sum Alpha system's two
non-event opportunity families:

1. hidden-asset / balance-sheet mispricing;
2. earnings and operating inflection.

FA001-D001 is a source-schema audit only. It does not rank companies and does not
calculate asset value, intrinsic value or expected returns.

## Frozen broad-market context

The target market is the passed SS001-D001 current NSE EQ census:

- 2,319 identities;
- census SHA-256:
  `0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7`.

## Frozen audit sample

Reuse exactly the 48-symbol, liquidity-stratified sample already frozen before source
inspection in:

`research/gf001/gf001-d001-current-schema-sample-v1.json`

Sample SHA is bound by file bytes in the FA001 run.

This sample spans I001 liquidity bands L1-L6 and includes both U001 and non-U001
companies. It was selected from source/liquidity state, not stock returns or valuation.

FA001 does not change sample members after source output is opened.

## Filing pair searched

For each sample symbol, query the official NSE Integrated Filing - Financials discovery.

Audit up to two exact period endpoints:

### Annual balance-sheet source

Target period end:

`2026-03-31`

For each accounting basis independently, select the earliest official source at that
period end. Prefer Consolidated when available; otherwise Standalone.

No substitute annual endpoint is introduced in D001. A non-March issuer may therefore
be source-unavailable for the annual part of v1.

### Current quarterly source

Target period end:

`2026-06-30`

Prefer the same accounting basis selected for annual when available. If the annual
source is unavailable, prefer Consolidated and then Standalone for the quarterly schema
audit only.

## Exact source rules

Every filing must:

- come from an approved official NSE archive host;
- retain source URL, discovery bytes/hash and filing bytes/hash;
- be valid XML/XBRL for the XBRL portion of D001;
- preserve all context IDs, units and local concept names.

Rendered HTML is not a substitute for a failed XBRL schema audit in D001.

## Candidate annual balance-sheet concept families

D001 audits exact observed concepts and aliases around:

### Cash / investments

- CashAndCashEquivalents
- BankBalancesOtherThanCashAndCashEquivalents
- CurrentInvestments / InvestmentsCurrent
- NoncurrentInvestments / InvestmentsNoncurrent
- OtherCurrentFinancialAssets
- OtherNoncurrentFinancialAssets

### Debt / obligations

- BorrowingsCurrent / CurrentBorrowings
- BorrowingsNoncurrent / NoncurrentBorrowings
- LeaseLiabilitiesCurrent
- LeaseLiabilitiesNoncurrent
- TotalCurrentLiabilities
- TotalNoncurrentLiabilities

### Asset backing

- TotalAssets
- TotalEquity
- PropertyPlantAndEquipment
- CapitalWorkInProgress
- InvestmentProperty
- Goodwill
- OtherIntangibleAssets
- Inventories
- TradeReceivablesCurrent / TradeReceivables
- OtherCurrentAssets
- OtherNoncurrentAssets

### Capital structure

- PaidUpValueOfEquityShareCapital
- FaceValueOfEquityShareCapital
- BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations
- BasicEarningsLossPerShareFromContinuingOperations

### Cash-flow support

- NetCashFlowsFromUsedInOperatingActivities
- PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities
- ProceedsFromSaleOfPropertyPlantAndEquipment
- PurchaseOfInvestmentsClassifiedAsInvestingActivities
- ProceedsFromSaleOfInvestmentsClassifiedAsInvestingActivities

## Candidate quarterly earnings-inflection concept families

D001 audits exact observed current-quarter concepts around:

- RevenueFromOperations
- TotalIncome
- ProfitBeforeExceptionalItemsAndTax
- ExceptionalItemsBeforeTax
- ProfitBeforeTax
- ProfitLossForPeriod
- FinanceCosts
- DepreciationDepletionAndAmortisationExpense
- EmployeeBenefitExpense
- CostOfMaterialsConsumed
- PurchasesOfStockInTrade
- ChangesInInventoriesOfFinishedGoodsWorkInProgressAndStockInTrade
- OtherExpenses
- BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations
- BasicEarningsLossPerShareFromContinuingOperations

## Context semantics

For every candidate concept retain:

- exact local name;
- contextRef;
- startDate/endDate or instant;
- dimensional/non-dimensional state;
- unitRef;
- numeric parseability.

D001 reports whether facts can be deterministically assigned to:

- annual duration;
- year-end instant;
- current quarter duration;
- current year-to-date duration.

No value is scored in D001.

## Financial-sector divergence

Banks, NBFCs, insurers and other financial businesses may expose materially different
statement concepts.

D001 does not force a non-financial schema onto them.

If stable concept families separate naturally by filing structure, the result may
authorize a later non-financial parser plus a separately frozen financial-sector
extension.

## Frozen feasibility gates

D001 passes the general non-financial source hypothesis only if:

1. at least 40/48 sample symbols return a usable 2026-06-30 XBRL;
2. at least 32/48 return a usable 2026-03-31 annual XBRL;
3. among usable annual XBRLs, >=80% expose deterministic TotalAssets, TotalEquity and
   CashAndCashEquivalents;
4. among usable annual XBRLs, >=70% expose deterministic current + noncurrent borrowings
   semantics or explicit structural equivalents;
5. among usable annual XBRLs, >=70% expose at least one explicit investments family;
6. among usable 2026-06-30 XBRLs, >=85% expose deterministic RevenueFromOperations and
   ProfitLossForPeriod in an identifiable current-quarter duration context;
7. no source bytes or concept definitions are selected using stock-return outcomes.

Thresholds may not be lowered after D001 output is opened.

## Promotion

Passing D001 permits separately frozen:

- FA001-D002 full-market financial fact parsing;
- HA001 hidden-asset deterministic candidate screens;
- EI001 earnings-inflection deterministic candidate screens.

None of those later screens may become a portfolio rule without their own research
contracts.

## Explicit exclusions

FA001-D001 does not:

- compare accounting values with market cap;
- compute net cash;
- compute tangible book;
- value land, subsidiaries or investments;
- calculate revenue/PAT growth;
- use LLM judgment;
- use future returns;
- create buy/sell/hold labels;
- create ADO/PF001/live-capital eligibility.
