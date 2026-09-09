# H019 Numeric Extraction Audit v2 Result

Status: **FAILED AS PREREGISTERED**

Evidence run: `34355319272`
Evidence artifact: `h019-numeric-extraction-audit-34355319272`
Artifact SHA-256: `3d4c1f5c4f71d1c5463a64d79dcff026a40f673b71ab36b2292367598ceb4357`
Frozen annual-report source run: `34352537129`
Frozen source artifact SHA-256: `37aeda56b72b34a74f599ecfbd78a94a68de41d61ff3b96da27dcc8695ecb621`

No market-price, return, benchmark-return, portfolio, or live-capital outcome was opened.

## Frozen v2 result

- frozen reports: 12
- extracted reports: 11
- `NO_TEXT_NO_OCR`: 1
- core current reports: 6, required >= 8 -> **FAIL**
- operating-cash-flow reports: 9, required >= 8 -> PASS
- core two-year reports: 6, required >= 6 -> PASS
- balance-identity current pass reports: 7, required >= 6 -> PASS
- exit-proxy core current reports: 2, required >= 3 -> **FAIL**
- structured revenue/PAT comparisons: 8, required >= 5 -> PASS
- structured revenue/PAT agreement: 6/8 = 75%, required >= 80% -> **FAIL**

Therefore v2 remains failed. Its thresholds will not be lowered and its evidence will not be rewritten.

## Accounting-only failure classification

The following diagnosis used only the retained annual reports, retained NSE result XBRLs, and accounting structure. It did not use any security-price outcome.

### Correctable deterministic parser defects

1. **Standalone statement heading normalization**
   - AHLWEST's actual standalone P&L page contains a merged extracted heading equivalent to `STATEMENTOF PROFITAND LOSS...`.
   - BALLARPUR's actual standalone P&L page contains a split/merged extracted heading equivalent to `STATEMENT OF PROFIT AND LOSS`.
   - v2's phrase matcher under-scored these pages and selected later accounting-note pages instead.

2. **Explicit generic balance total inside the Assets section**
   - AFTEK's standalone balance sheet presents the final assets total as an explicit row labeled only `Total`, after the `Assets` section, rather than `Total Assets`.
   - The same page contains the matching pre-Assets liabilities/equity `Total`.
   - Accepting the final explicit `Total` inside the Assets section is an accounting-structure reconstruction, not an inferred investment fact.

3. **Statement-unit wording normalization**
   - Valid source pages use variants such as `All amounts in Rs. (lakhs)`, `All amounts in INR Lakhs`, and `All amounts are in rupees lakhs`.
   - v2 recognizes a narrower wording set. v3 may normalize these explicit unit disclosures only. It may not infer a unit from company size, price data, or return behavior.

4. **Structured XBRL reporting-period semantics**
   - v2 compared each annual-report fact with whichever XBRL numeric candidate was closest.
   - For AIFL and BHARATWIRE, the retained XBRL exposes Jan-Mar reporting-period contexts, not an Apr-Mar full-year current context. Those are not valid annual-report cross-checks.
   - For 20MICRONS, ASTEC, and BSLIMITED, the XBRL contains a standalone full-year context whose reporting-period start/end equals the financial-year start/end. Those facts match the annual report.
   - v3 must select a structured comparison by period semantics first. It must never select a context by numerical closeness.

### Source limitations that remain failures

- AUSTRAL: no usable text under the frozen no-OCR rule.
- CELESTIAL: primary financial-statement pages are image/scanned-style under text extraction. No OCR rescue is authorized by this protocol.
- Banking/financial-company presentation differences are not a reason to weaken the non-financial H019 data contract.

## Decision

Do not build or score H019 yet.

Proceed to a separately frozen v3 numeric-extraction audit that changes only the four accounting-source mechanics above. Keep the same 12-report corpus, the same no-OCR rule, the same market-outcome ban, and at least the same v2 coverage/identity/agreement thresholds.