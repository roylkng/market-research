# H019 Numeric Extraction Audit v3 Result

Status: **PASSED AS PREREGISTERED**

Evidence run: `34362075440`
Source commit: `7567c33e5c627aebb77dee347f54a17803063f0b`
Evidence artifact: `h019-numeric-extraction-audit-v3-34362075440`
Artifact ID: `10108385426`
Artifact SHA-256: `134d08dac687ef5023d50d51983755815f3722bc5a32be8157a2d5d186cc8f88`

Frozen annual-report source run: `34352537129`
Frozen source artifact: `h019-annual-report-source-audit-34352537129`
Frozen source artifact SHA-256: `37aeda56b72b34a74f599ecfbd78a94a68de41d61ff3b96da27dcc8695ecb621`

v2 remains failed and immutable. v3 used the same 12-report corpus, the same no-OCR rule, and the same numeric quality gates. No threshold was relaxed.

No market-price, return, benchmark-return, portfolio, investment-score, or live-capital outcome was opened.

## Frozen v3 result

- frozen reports: 12
- extracted reports: 11
- `NO_TEXT_NO_OCR`: 1
- core current reports: 9, required >= 8 -> **PASS**
- operating-cash-flow reports: 9, required >= 8 -> **PASS**
- core two-year reports: 9, required >= 6 -> **PASS**
- balance-identity current pass reports: 8, required >= 6 -> **PASS**
- exit-proxy core current reports: 3, required >= 3 -> **PASS**
- valid structured revenue/PAT comparisons: 8, required >= 5 -> **PASS**
- valid structured revenue/PAT agreement: 8/8 = 100%, required >= 80% -> **PASS**
- valid structured EPS comparisons: 4
- valid structured EPS agreement: 4/4 = 100%
- market outcomes opened: false -> **PASS**

All frozen v3 gates passed.

## What v3 established

The retained NSE annual-report source can support deterministic reconstruction of the accounting facts needed for a point-in-time fundamental ledger, including:

- revenue
- profit after tax
- total assets
- total equity
- operating cash flow
- borrowings when explicitly reconstructable
- finance cost
- basic EPS
- capex where explicitly available, still optional

The successful corrections were accounting-source mechanics only:

1. normalized merged financial-statement headings;
2. accepted section-scoped explicit balance-sheet `Total` rows where the statement omits a literal `Total Assets` label;
3. normalized explicit INR/lakh/crore wording without magnitude inference;
4. required true standalone full-year XBRL contexts before a structured comparison could enter the validation denominator.

The remaining no-text source was not rescued with OCR.

## Decision

Promote v3 into a reusable **point-in-time company-year accounting ledger** layer.

This promotion authorizes source acquisition, observation versioning, accounting fact normalization, provenance retention, accounting validation, and coverage measurement only.

It does **not** authorize:

- defining H019 feature weights;
- choosing securities using future performance;
- opening any market return or benchmark-return outcome;
- changing the H019 investment hypothesis based on later returns;
- deploying live capital.

The next research artifact must freeze the accounting-ledger data model and an outcome-blind coverage audit before any H019 score is specified.