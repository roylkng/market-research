# AE001 D010 Protocol Amendment P2: SLB Historical Route Validation

Frozen: 2026-10-01
Status: FROZEN AFTER P1 METADATA RESOLUTION, BEFORE P2 SOURCE PROBE
Live capital: DISABLED

## P1 evidence

D010-P1 workflow run:

    36876730846

P1 report SHA-256:

    fb815a3d26c1aea506fa4c956588f2563435e5b0a08729a6a8a3191fcd2978f6

P1 opened no return labels and fit no model.

P1 established:

### CM Short Selling

The exact NSE archive route:

    https://nsearchives.nseindia.com/archives/equities/shortSelling/
    shortselling_DDMMYYYY.csv

was READY on all three original D010 probe dates.

### SLB Daily Open Positions

Official NSE Daily Reports metadata, query key SLBS, returned:

- fileKey: SLBS-OPEN-POSITION
- displayName: Daily Open Positions (csv)
- filePath:
  https://nsearchives.nseindia.com//archives/slbs/open_pos/
- fileActlName:
  slb_openpos_30092026.csv

This directly identifies the candidate dated archive convention:

    https://nsearchives.nseindia.com/archives/slbs/open_pos/
    slb_openpos_DDMMYYYY.csv

P1 did not assume historical availability from one current metadata row.

## Frozen P2 probe

Test the exact SLB candidate pattern on the same three original source-only
probe sessions:

- 2026-09-25
- 2026-09-24
- 2025-09-01

No additional URL pattern may be tested under P2.

## Acceptance

A frozen session is READY only when:

- HTTP status is 200;
- body is non-empty;
- body is not HTML;
- UTF-8 CSV parsing succeeds;
- the CSV header is non-empty;
- exact raw SHA-256 is retained.

P2 passes only if the single frozen SLB route is READY on all three dates.

P2 records the exact schema and row counts.

## Promotion after P2

If P2 passes:

D010 may proceed to a separately frozen full historical coverage and identity
audit over the standard AE001 window:

    2025-09-01 through 2026-09-25

for BOTH:

- CM Short Selling;
- SLB Daily Open Positions.

That future audit must establish:

- per-session file availability;
- schema stability;
- source date correctness;
- same-session symbol -> official UDiFF EQ symbol+ISIN mapping;
- duplicate semantics;
- sparse-row semantics;
- source row completeness diagnostics.

No alpha model may be fit until that audit passes.

## Scientific boundary

P2 is source-only.

- no stock return labels;
- no model fit;
- no IC/spread metrics;
- no publication-timing inference;
- no live-capital implication.
