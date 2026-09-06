# Historical reconstruction workflow

## Purpose

Historical reconstruction is an engineering and data-quality exercise. It teaches MarketLab how to acquire, hash, version, parse and reconcile real exchange disclosures without pretending that old observations are untouched prospective evidence.

Every reconstructed event is hard-coded as:

`HISTORICAL_RECONSTRUCTION`

The local `EventStore` cannot relabel it prospective.

## Current first cases

### CCL Products, FY27 Q1 consolidated

Official NSE Integrated Filing:

`https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_178875_27072026202614_iXBRL_WEB.html`

Verified source properties used by the test fixture:

- NSE symbol `CCL`
- ISIN `INE421D01022`
- consolidated, unaudited, first quarter
- period ended 30-Jun-2026
- currency INR, rounding Lakhs
- revenue from operations 120,044.62 lakhs
- profit before tax 12,901.75 lakhs
- total profit 11,688.05 lakhs
- basic EPS 8.77

### Infosys, FY26 Q4 consolidated

Official NSE Integrated Filing:

`https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_152465_23042026210154_iXBRL_WEB.html`

Verified source properties used by the test fixture:

- NSE symbol `INFY`
- ISIN `INE009A01021`
- consolidated, audited, fourth quarter
- period ended 31-Mar-2026
- currency INR, rounding Lakhs
- revenue from operations 4,640,200 lakhs
- profit before exceptional items and tax 1,079,700 lakhs
- basic EPS 21.01

### Shaily Engineering Plastics, FY26 Q1 consolidated

Official NSE Integrated Filing:

`https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_109908_11082025161038_iXBRL_WEB.html`

Verified source properties used by the test fixture:

- NSE symbol `SHAILY`
- ISIN `INE151G01028`
- consolidated, unaudited, first quarter
- period ended 30-Jun-2025
- presentation currency `INR (in Actuals)`
- revenue from operations 2,466,927,000
- total profit 411,227,000
- basic EPS 8.95

The Shaily case exists specifically to prevent a dangerous normalization bug: its result is reported in actual INR while the CCL and INFY fixtures are in lakhs.

## Source-derived fixtures

Files in `data/fixtures/filings/` are compact source-derived parser fixtures. They preserve selected labels and values from the official documents but are **not original raw bytes** and therefore their SHA-256 must never be presented as the source filing hash.

A future networked capture of the real document hashes the actual downloaded bytes and stores those separately.

## Run one reconstruction

```bash
marketlab reconstruct-event \
  data/fixtures/filings/ccl_fy27_q1_consolidated_source_derived.html \
  --source-url https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_178875_27072026202614_iXBRL_WEB.html \
  --store .marketlab
```

The command writes:

```text
.marketlab/
├── raw/sha256/<content-hash>.html
└── events/<economic-event-id>/<content-hash>.json
```

Re-running identical bytes is idempotent and returns the first stored event record. Changed bytes for the same symbol/period/accounting basis produce a new version under the same economic-event id.

## Important semantic rule

`Total profit before exceptional items and tax` is **not** silently renamed EBITDA or operating profit. NSE's standard Integrated Filing does not provide one canonical operating-profit field across all issuers. Until an explicit, provenance-aware extractor exists, `operating_profit` and `operating_margin` remain unresolved.

This is deliberate. A missing value is preferable to a plausible but false value.
