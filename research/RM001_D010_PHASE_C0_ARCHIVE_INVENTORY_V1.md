# RM001 D010 Phase C0 Annual Archive Inventory v1

Status: FROZEN AFTER PHASE A/B PASS AND BEFORE ANNUAL ARCHIVE BYTE INSPECTION
Frozen: 2026-10-02
Live capital: DISABLED

## Parent evidence

D010 Phase A/B source scan:
- workflow run: 37007303564
- artifact: rm001-d010-37007303564
- Phase A: PASS
- Phase B: PASS_URL_DISCOVERY
- Phase C authorized: true
- Phase A/B result SHA-256:
  64a0ec350f76ba3413d037fc8b3bd234dd9389be915032a5048f9526cd3e444b

## Exact official annual archives discovered under the frozen D010 rule

FY2023-24:
https://nsearchives.nseindia.com/web/sites/default/files/inline-files/BRSR_Data_Dump.zip

FY2024-25:
https://nsearchives.nseindia.com/web/mediaattachment/2026-04/BRSR_DUMP_FY24-25_20260414130852.zip

These exact URLs are now frozen for Phase C.

## Objective

Inspect archive structure before implementing filing-level extraction.

This C0 pass may observe only:
- response/redirect metadata;
- exact archive bytes and SHA-256;
- ZIP member names;
- member sizes and compressed sizes;
- member extensions;
- member SHA-256;
- whether a member is itself a ZIP/XLSX-like container.

It does not yet calculate entity/NIC coverage.

## Scientific invariants

The parent D010 Phase C gates remain unchanged:
- >=500 unique entities/year;
- >=90% explicit NIC coverage;
- >=90% stable identity coverage;
- <=1% duplicate stable identity rate;
- >=99% explicit reporting-year coverage;
- stable NIC semantics across both years.

C0 cannot change these thresholds.

No returns, RM001 fit, covariance result, PO001 result or live capital.
