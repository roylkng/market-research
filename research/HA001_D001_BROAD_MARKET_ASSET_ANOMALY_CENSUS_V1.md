# HA001-D001 Broad-Market Asset Anomaly Source Census v1

Status: **FROZEN BEFORE FULL-PANEL ANOMALY MATERIALIZATION**
Frozen: 2026-10-10 (Asia/Kolkata)
Return outcomes opened: no
Investment recommendations: disabled
Portfolio eligibility: disabled
Live capital: disabled

## Purpose

Turn the existing 2,319-identity FA001 annual financial and asset fact plane into an
**outcome-blind research triage census** of economically interpretable accounting
anomalies. The result may trigger filing/notes/subsidiary investigation, but does not
assert that any security trades at a discount.

This is deliberately not an intrinsic-value, liquidation-value, market-capitalization,
or return-prediction experiment.

## Exact source input

- `FA001-D002-v1`;
- source run `37213394690`, artifact ID `11306919543`;
- artifact `fa001-d002-merged-37213394690`;
- logical panel SHA-256
  `cb8a408b6904799750a5aa08210f909ae8b285005273b5588fb1f8b7a6019124`;
- frozen SS001 source census SHA
  `0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7`;
- exactly 2,319 frozen EQ identities.

The annual filing period-end is **2026-03-31**. No later filing data is substituted.
Rows with no usable annual source are retained as explicit missing-source cases.

## Fiscal/basis/unit gates

Use only FA001 annual `READY` parsed facts. For every participating fact:

1. `status == READY`;
2. numeric finite `value`;
3. exact `unit_ref == INR`;
4. source annual period-end 2026-03-31;
5. source raw SHA-256 and source URL present;
6. source basis is retained unchanged as Consolidated or Standalone.

All required facts for one signal must come from the same annual filing. No sector,
issuer or accounting-basis conversion is guessed.

Negative cash, investment and physical-asset balances are invalid for the related
signal. Borrowings must be nonnegative. `total_assets` must be strictly positive.
A missing field stays unknown—never zero.

FA001 includes NBFC/financial-sector filings; HA001 does not present their cash or
borrowings as industrial-company net-cash economics. Where the exact filing source URL
indicates an NBFC taxonomy, the signal is **not evaluated**, but the issuer remains
in the 2,319-company census.

## Exactly three frozen source-only flags

Each flag is independent; an issuer may carry multiple flags. All thresholds below
are economic triage materiality choices frozen before observing the HA001 output.

### F1: MATERIAL_FINANCIAL_SURPLUS_PROXY

Required year-end facts (all INR):

- cash and cash equivalents;
- current investments;
- current borrowings;
- non-current borrowings;
- total assets.

`surplus_proxy = cash + current_investments - current_borrowings - noncurrent_borrowings`

`surplus_to_assets = surplus_proxy / total_assets`

Flag only if `surplus_to_assets >= 0.20`.

This is **not net cash or distributable equity value**. Current investments are
carrying values; lease liabilities, restricted cash, contingent liabilities, taxes,
unconsolidated subsidiaries and holdco leakage may be important.

### F2: MATERIAL_BOOK_INVESTMENTS

Required year-end facts (all INR):

- current investments;
- non-current investments;
- total assets.

`investment_assets_share = (current_investments + noncurrent_investments) / total_assets`

Flag only if `investment_assets_share >= 0.30`.

This is a lead for subsidiary/holding-company and marketable-security schedule review,
**not a claim that investments are liquid, realizable or hidden**.

### F3: TANGIBLE_CAPITAL_CONCENTRATION

Required year-end facts (all INR):

- PPE;
- capital work in progress;
- investment property;
- total assets.

`physical_assets_share = (PPE + CWIP + investment_property) / total_assets`

Flag only if `physical_assets_share >= 0.50`.

This is a lead for land/property, capex, replacement-cost and utilization research,
**not evidence that property is undervalued**.

## Outputs and source accounting

Materialize exactly one row for each of 2,319 source symbols with:

- symbol / ISIN / company name / U001 overlap;
- annual filing state, accounting basis, period, source URL, source raw SHA;
- each flag's state: `FLAGGED`, `NOT_FLAGGED`, `MISSING_REQUIRED_FACT`,
  `INVALID_NUMERIC_OR_UNIT`, `FINANCIAL_SECTOR_NOT_COMPARABLE`,
  or `ANNUAL_SOURCE_UNAVAILABLE`;
- for an eligible numeric row: numerator, denominator and dimensionless ratio;
- required-fact evidence (fact key, selected XBRL concept, unit, context refs);
- independent counts and flagged source-symbol arrays.

Do not sort issuers by these accounting ratios or assign them a valuation score.
Do not remove companies because of low liquidity, high P/E, index status or ownership.

## Frozen operational acceptance tests

This **source materialization** passes only if:

1. all 2,319 frozen identities appear exactly once;
2. all flags have a recognized state on every identity;
3. any flagged ratio reproduces the frozen equation from exact input facts;
4. no input row with missing/ambiguous/invalid required facts is flagged;
5. all source raw SHA-256 references for eligible facts are present;
6. no outside price, capitalization, target, future return or model output enters.

Source coverage must be reported unconditionally. No post-hoc coverage minimum is
introduced that would favor apparently attractive names.

## Promotion

Passing D001 authorizes **issuer-specific document diligence queues** and the next
source-only inflection experiment design. It does not authorize an intrinsic valuation,
stock recommendation, Analyst Decision Object, PF001 position or live capital.

A real hidden-asset opportunity still needs, in later frozen work:

- entity-level ownership and asset schedule reconciliation;
- asset encumbrance/recoverability;
- taxes, subsidiary minority interests, related parties and debt;
- a contemporaneous price *and fully reconciled issued-share denominator*;
- a credible realization/catalyst path; and
- independent red-team review.

## Scientific boundary

No return outcomes, no backtest, no outcome-tuned thresholds, no LLM inference, no
probability estimates, no synthetic market cap and no capital allocation.
