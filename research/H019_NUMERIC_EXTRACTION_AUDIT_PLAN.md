# H019 numeric extraction audit plan

Recorded: 2026-09-09

Status: **ACCOUNTING EXTRACTION VALIDATION ONLY. NO MARKET PRICE, RANKING, SELECTION OR RETURN OUTCOME MAY BE COMPUTED. LIVE CAPITAL DISABLED.**

## Objective

The H019 source audits established that the official NSE annual-report API preserves historical reports for both survivor-proxy and exit-proxy companies, and that the retained reports broadly contain income statement, balance sheet and operating cash-flow disclosures.

Before H019-v1 can freeze an investment score, the project must prove that numeric facts can be extracted deterministically and fail-closed from those reports. Label presence alone is insufficient.

## Frozen corpus

Use only the 12 annual-report documents already selected by the outcome-blind v2 audit in GitHub Actions run `34352537129`, artifact `h019-annual-report-source-audit-34352537129`.

Do not change sample membership based on extraction success.

The corpus contains six `SURVIVOR_PROXY` and six `EXIT_PROXY` reports selected before their contents were inspected.

## Candidate facts

Attempt to recover, for the latest and comparative year shown in the primary audited statements:

- revenue from operations or total operating revenue;
- profit after tax / profit for the year;
- total assets;
- total equity / shareholders' funds / net worth;
- total equity and liabilities when present;
- non-current borrowings;
- current/short-term borrowings;
- finance costs;
- cash flow from operating activities;
- capex/PPE purchase when directly disclosed;
- basic EPS when directly disclosed.

The audit may derive `total_borrowings = noncurrent_borrowings + current_borrowings` only when both components are explicitly extracted for the same reporting basis and year.

No ROE, ROCE, FCF, growth, quality score or investment feature is frozen by this audit. Those are later derived-variable decisions.

## Extraction rules

1. Use PDF text extraction only. No OCR.
2. Prefer the primary audited standalone financial statements for this extraction audit because the statement basis must be deterministic across the sample. A later H019 production protocol may separately freeze consolidated-first logic after numeric extraction is proven.
3. Preserve every extracted value with:
   - report SHA-256,
   - page number,
   - exact source line or bounded text excerpt,
   - detected reporting unit,
   - current/comparative year labels,
   - normalized numeric value and original token.
4. Parenthesized values are negative. Dash/blank is not silently converted to zero unless the source row unambiguously uses dash as a numeric zero in a complete audited statement row, and such conversion is explicitly flagged.
5. Ambiguous multiple statement rows, missing year headers, mixed reporting bases, non-text pages, or unresolvable units fail closed for that fact.
6. A note number or note reference must never be interpreted as a financial value.

## Internal validation

For each report where the needed lines are extracted:

- compare total assets with total equity and liabilities for the same year and require absolute relative residual <= 0.5%;
- require the same check for the comparative year where both values exist;
- require all extracted statement values to share a consistent unit within a statement unless the report explicitly says otherwise;
- flag implausible EPS/share-scale combinations rather than coercing them.

These checks validate extraction consistency, not business quality.

## Independent P&L cross-check

For reports with a matching NSE annual financial-result XBRL/iXBRL available from the same historical period, independently retrieve the exchange-hosted structured filing and compare annual-report values for revenue, PAT and basic EPS when both sources expose the concept.

After unit normalization, require absolute relative difference <= 1% for revenue and PAT. EPS requires <= 1% relative difference or <= 0.02 absolute difference, whichever is more permissive.

A mismatch fails that fact. Do not choose between sources based on which value later predicts returns better.

## Feasibility gates

The numeric source layer is considered viable for the next H019 design stage only if all of these hold:

1. at least 8 of the 12 frozen reports produce current-year revenue, PAT, total assets and total equity;
2. at least 8 of 12 produce current-year operating cash flow;
3. at least 6 of 12 produce both current and comparative-year revenue, PAT, total assets and total equity;
4. at least 6 reports pass a same-year balance-sheet identity check;
5. at least 3 of 6 `EXIT_PROXY` reports produce the core current-year set, so viability is not driven only by survivor-proxy documents;
6. wherever an independent XBRL cross-check is possible, at least 80% of comparable revenue/PAT facts pass the frozen tolerance, with at least five comparisons total;
7. no market price or return data is opened.

Capex, direct EPS, ROE and ROCE have no hard feasibility gate at this stage.

## Decision rule

If the gates pass, build a reusable point-in-time annual financial fact layer before freezing H019-v1.

If the gates fail, improve the accounting extraction/data architecture or narrow the candidate accounting inputs based only on source reliability. Do not inspect returns to decide which extraction failures to tolerate.
