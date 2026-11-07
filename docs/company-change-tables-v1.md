# CC001 P002: context-aware statement intake

Status: working development adapter. No live capital, trained predictor or blind
accuracy claim. Existing frozen experiments and parsers remain unchanged.

## What changed

CC001 v1 required explicit label-value lines with units beside each amount.
Actual statements often put units in a header and quarterly/year-to-date values
in different columns. This adapter handles that structured context without
inventing canonical prose or changing source numbers.

The new `marketlab.company_change_tables` module:

- Reads flat HTML table cells without removing blanks, or a preserved row matrix.
- Requires an exact start date, end date and accounting scope for selection.
- Binds each value to its table, row and column, plus currency, rounding and
  period-header evidence.
- Converts lakh/million/crore amounts to INR crore. EPS and face value remain
  INR per share and are not scaled by the monetary header.
- Preserves absent owner-attributable PAT. It never substitutes group profit.
- Keeps pretax exceptional items separate from after-tax owner adjustments.
- Calls the existing CC001 `earnings_bridge` for compatible diagnostics, while
  leaving sustainable owner earnings unknown when required evidence is absent.
- Reconciles equivalent Q1 and year-to-date columns as one requested observation.
  Conflicting duplicates fail rather than selecting the first column.
- Produces content-addressed JSON and an HTML evidence report.

## Run the real-source development replay

```bash
python -m marketlab.company_change_tables \
  data/fixtures/company_change_real_v1.json \
  --out .marketlab/company-change-real

pytest -q tests/test_company_change.py tests/test_company_change_tables.py
```

The new corpus contains **two source-derived reconstructions**, not downloaded
original HTML files:

1. Mayur Uniquoters Q1 FY27 standalone NSE statement. Its quarterly and
   year-to-date periods coincide. Owner-attributable profit cells are blank.
2. KRBL FY26 consolidated NSE statement, with separate fourth-quarter and
   full-year columns sharing the same end date.

The original NSE references, the actual reconstruction-recording time, and the
row-matrix hashes are included in the manifest. The supplied data are factual
financial table rows read from those primary pages. The original HTML bytes
were not captured. The matrix hash must not be described as a source-file hash.

**Result: 36/36 labelled checks across three selected period/scope cases.** This
is a seen development replay. The examples and rules were developed together,
so the result is not an independent accuracy estimate. The corpus has neither
stock-return labels nor investment recommendations. Adding artificial negative
variants to unit tests does not increase the number of real disclosures.

## Collector integration

Existing collectors can call `html_tables(raw_bytes)` on their retained UTF-8
HTML, then pass its tables, provenance manifest, explicit selector and decision
cutoff to `extract_statement`. The manifest must identify the expected symbol
and ISIN and the hash of the table matrix. Original-byte custody stays in the
collector and is not replaced by the matrix hash.

`html_tables` is intentionally limited to flat tables. Nested tables, merged
cells, unrecognised monetary units, inconsistent metadata and ambiguous column
matches fail with `ChangeError`. A layout-specific or reviewed model adapter is
required for unsupported documents. This change does not claim unattended
coverage of arbitrary original NSE HTML, PDFs or prose news.

`evaluate_corpus` supplies only source tables, metadata and the selector to the
extractor. It compares expected labels afterward. A test mutates the expected
value and verifies that the score changes but the extracted statement does not.
Unlabelled extracted fields are counted as failures, not silently omitted.

## Evidence and decision limits

Every output remains `HISTORICAL_RECONSTRUCTION`, `DEVELOPMENT_ONLY`, and
`live_capital_allowed=false`. Observation timestamps are the recording time of
this reconstruction, not backdated publication or trading-entry timestamps.

The reported diluted EPS is not silently promoted to normalized owner EPS.
A zero exceptional-item line does not establish that all non-recurring profit
is absent. The adapter does not derive exact outstanding or weighted-average
shares from rounded capital or EPS. Interim results are not annualized.

No model endpoint, external API billing, scheduler, commercial data licence,
source redistribution right, automated trade execution or portfolio policy was
introduced. The `INTERNAL_DEVELOPMENT` usage marker describes this test scope,
not a commercial licence.

## Verification and next acceptance gate

Focused tests cover exact period selection, blank-cell preservation, scope and
issuer isolation, monetary units, EPS units, accounting signs, duplicate columns,
ambiguous layouts, source hashes, source availability, source-cell replay,
gold-label isolation, HTML escaping and content-addressed output behavior.

The next evaluation must use independently labelled, held-out full documents
covering multiple industries and layouts. Report precision, recall, abstentions
and material-error severity separately. Only after that should the economic-event
features enter a new prospective A/B/C comparison using the existing evaluator.
Software checks and this seen replay establish deterministic behavior, not a
validated predictive advantage.
