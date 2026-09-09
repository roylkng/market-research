# H019 numeric extraction audit plan v2

Recorded: 2026-09-09

Status: **ACCOUNTING EXTRACTION VALIDATION ONLY. NO MARKET PRICE, RANKING, SELECTION OR RETURN OUTCOME MAY BE COMPUTED. LIVE CAPITAL DISABLED.**

This version supersedes `H019_NUMERIC_EXTRACTION_AUDIT_PLAN.md` before the first numeric-extraction audit is executed.

## Why v2 exists

Pre-execution inspection of the already-frozen 12-report source corpus showed a presentation-format issue: several valid standalone balance sheets do not print a literal `Total equity` row. Instead they present the complete equity section as explicit components, typically:

- `Equity share capital` + `Other equity`, or
- `Share capital` + `Reserves and surplus` under `Shareholders' Funds`.

Treating those reports as missing equity would make the source audit test typography rather than accounting-data availability. No market data or return outcome has been opened.

## Frozen corpus and scope

Use only the 12 annual-report documents selected by outcome-blind source audit run `34352537129`.

Use PDF text extraction only. No OCR.

Prefer the first primary audited **standalone** balance sheet, statement of profit and loss and cash-flow statement. A consolidated statement must not silently replace a failed standalone extraction.

## Numeric facts

Attempt current and comparative-year extraction for:

- revenue from operations / operating revenue;
- profit after tax / profit for the year;
- finance costs;
- total assets;
- total equity;
- total equity and liabilities when printed;
- non-current borrowings;
- current/short-term borrowings;
- operating cash flow;
- capex/PPE purchase when directly disclosed;
- basic EPS when directly disclosed.

## Frozen mechanical derivations

Only these accounting subtotals may be derived during the audit:

### Total equity

A missing literal `Total equity` may be reconstructed only on the same standalone balance-sheet page, for the same year columns, from exactly one of:

1. `Equity share capital` + `Other equity`;
2. `Share capital` + `Reserves and surplus`, when these are explicitly the complete `Shareholders' Funds` section before the next liability section.

The source rows, tokens and arithmetic must all be retained. Do not infer missing components, minority interest, hybrid instruments or other equity components. If the section contains additional equity components that are not included in the permitted pair, fail closed.

### Total borrowings

`total_borrowings = noncurrent_borrowings + current_borrowings` only when both explicit borrowing rows are extracted from the same standalone balance sheet for the same year columns.

No other accounting subtotal is derived in this audit.

## Extraction provenance

Every fact must preserve:

- report SHA-256 and PDF SHA-256;
- page number;
- exact source line or bounded excerpt;
- statement type;
- detected reporting unit and numeric scale;
- current and comparative year;
- original numeric tokens;
- normalized values;
- direct vs mechanically-derived status.

Parentheses mean negative. Note numbers must never become financial values. Ambiguous rows or year headers fail closed.

## Internal checks

Where both rows are directly extracted, require:

`abs(total_assets - total_equity_and_liabilities) / max(abs(total_assets), 1) <= 0.005`

for current and comparative years.

A mechanically reconstructed equity amount is also checked for finite values and retained component arithmetic, but the balance-sheet identity does not use it as a substitute for `Total equity and liabilities`.

## Independent structured-filing cross-check

For frozen sample reports with a matching standalone NSE annual financial-result XBRL/iXBRL, independently fetch the exchange-hosted source and compare current-year:

- revenue;
- PAT;
- basic EPS when a comparable continuing/total concept exists.

The PDF value is converted using its detected statement unit. Structured facts are read in their native unit.

Revenue/PAT pass at <=1% absolute relative difference. EPS passes at <=1% relative difference or <=0.02 absolute difference, whichever is more permissive.

Do not choose a different filing basis because it matches better. Standalone annual-report facts must be compared with standalone structured filings.

## Feasibility gates

The numeric layer passes only if all hold:

1. >=8/12 reports produce current-year revenue, PAT, total assets and total equity, where equity may be direct or frozen-derived;
2. >=8/12 produce current-year operating cash flow;
3. >=6/12 produce current and comparative-year revenue, PAT, total assets and total equity;
4. >=6/12 pass same-year direct total-assets vs total-equity-and-liabilities identity;
5. >=3/6 `EXIT_PROXY` reports produce the current-year core set;
6. where independent XBRL comparison is possible, >=80% of comparable revenue/PAT facts pass tolerance, with >=5 comparable facts total;
7. no market outcome is opened.

Capex, EPS, direct ROE and direct ROCE have no hard gate.

## Decision rule

If these gates pass, promote annual-report numeric extraction to a reusable point-in-time financial-fact layer and then freeze H019-v1 derived variables and score before any return data.

If they fail, version the accounting source/extraction layer based only on the documented source failures. Do not inspect stock returns to decide what to tolerate.
