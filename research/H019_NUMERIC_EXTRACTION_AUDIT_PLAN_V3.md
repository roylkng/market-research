# H019 Numeric Extraction Audit v3

Purpose: determine whether deterministic, outcome-blind extraction can reconstruct a reusable point-in-time accounting fact layer from the already frozen H019 annual-report corpus.

This is a **new audit version**. v2 remains failed and immutable.

## Frozen evidence corpus

Use exactly the 12 annual reports retained by source-audit run `34352537129` and no replacements.

Required source-artifact digest:
`sha256:37aeda56b72b34a74f599ecfbd78a94a68de41d61ff3b96da27dcc8695ecb621`

No OCR. No report substitution. No manual company-specific overrides.

## Prohibited data

The extractor and workflow must not access or calculate:

- security prices or bhavcopy data
- benchmark/index returns
- future returns
- portfolio selections or portfolio returns
- any H019 investment score
- live-capital recommendations

## v3 changes permitted relative to v2

Only these accounting-source mechanics may change.

### 1. Statement heading normalization

For statement-page classification only, form a compact heading representation by removing non-alphanumeric characters and whitespace from extracted text.

Recognize compact equivalents of:

- `balancesheet`
- `statementoffinancialposition`
- `statementofprofitandloss`
- `profitandlossaccount`
- `cashflowstatement`
- `statementofcashflows`

Retain the existing preference against consolidated pages and auditor/note pages. Add an explicit penalty when the beginning of a candidate page identifies it as notes to financial statements.

Do not add symbol-specific page numbers.

### 2. Explicit balance `Total` fallback

Only on a page already selected as the balance sheet:

- locate the explicit `Assets` section heading;
- if literal `Total Assets` is absent, accept the last numeric row whose textual label is exactly `Total` after the Assets heading as total assets;
- if literal `Total Equity and Liabilities` is absent, accept the last numeric row whose textual label is exactly `Total` before the Assets heading as total equity/liabilities;
- retain balance-identity validation with the existing 0.5% tolerance.

Do not derive assets from a sum of component rows in v3.

### 3. Explicit unit wording normalization

Recognize only explicit statement disclosures equivalent to INR, lakhs/lacs, or crores. The parser may normalize wording/punctuation variants including:

- `All amounts in Rs. (lakhs)`
- `All amounts in INR Lakhs`
- `All amounts are in rupees lakhs`
- `Rs. in lakhs`, `INR in lakhs`, `in lacs`
- analogous crore wording

No unit may be inferred from magnitude, company identity, XBRL closeness, market capitalization, or price data.

### 4. Structured XBRL period semantics

Before comparing any annual-report P&L/EPS fact with NSE structured data:

- derive financial-year start and end from explicit structured metadata;
- derive each context's reporting-period start/end, standalone/consolidated nature, and audited/unaudited status from facts carrying that context reference;
- a comparison candidate is eligible only if its context is `Standalone`, its reporting-period start equals financial-year start, and its reporting-period end equals financial-year end;
- when audited/unaudited metadata exists for that context, require `Audited`;
- if no eligible full-year context exists, record `NO_COMPARABLE_FULL_YEAR_CONTEXT` and do not count that fact as a pass or failure.

Numerical closeness must never choose a context.

Within one eligible context, concept choice remains restricted to the frozen v2 concept-name families. Multiple eligible facts for the same concept/context must fail closed unless they are numerically identical after parsing.

## Frozen v3 gates

Use the same minimum quality thresholds as v2. They are not lowered:

- core current reports >= 8
- operating cash flow reports >= 8
- core two-year reports >= 6
- balance-identity current pass reports >= 6
- exit-proxy core current reports >= 3
- valid structured revenue/PAT comparisons >= 5
- valid structured revenue/PAT agreement >= 80%
- market outcomes opened = false

Core facts remain revenue, PAT, total assets, and total equity. Operating cash flow remains separately gated. Capex remains non-blocking.

## Required diagnostics

The v3 artifact must retain, per report:

- selected statement page numbers
- statement-page classification evidence
- extracted fact source lines
- direct vs permitted arithmetic derivation
- explicit unit evidence and normalized scale
- balance-identity residuals
- source hashes

For each structured cross-check, retain:

- financial-year start/end
- candidate context metadata
- selected eligible context, if any
- structured concept/value
- annual-report value
- difference and pass/fail
- explicit `NO_COMPARABLE_FULL_YEAR_CONTEXT` when applicable

## Decision rule

If all gates pass, v3 may be promoted into a reusable company-year accounting ledger builder. This still does **not** authorize opening market outcomes or defining H019 feature weights.

If any gate fails, record the failed audit. Further changes require another versioned, accounting-only protocol.