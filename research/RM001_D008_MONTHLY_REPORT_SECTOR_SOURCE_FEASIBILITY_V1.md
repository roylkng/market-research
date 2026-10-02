# RM001 D008 NSE Monthly Exchange Report Sector-Source Feasibility v1

Status: FROZEN BEFORE SOURCE SCAN
Frozen: 2026-10-02
Live capital: DISABLED

## Objective

Determine whether official dated NSE Capital Market Exchange Monthly Reports
contain a broad company-level point-in-time industry classification that can
support a future RM001 sector factor without projecting today's classification
backward.

D008 is a source-feasibility diagnostic only.

It opens:
- no stock-return outcomes;
- no alpha outcomes;
- no risk-model fit;
- no portfolio optimization.

## Motivation

D007 established that the daily NSE CM MII Security File is suitable for
point-in-time total-market-cap SIZE but does not materially populate company
industry classification.

NSE quote pages expose current Basic Industry, and NSE Indices maintains a
formal four-tier classification, but current labels may change annually or after
corporate events. Current labels therefore cannot be backfilled historically.

The Exchange Monthly Reports are immutable dated official snapshots and are the
next source candidate.

## Frozen official sample

D008 scans four official NSE Capital Market Exchange Monthly Report workbooks:

### September 2025

https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Exchange_Data_CM_Segment_Sept%2725.xlsx

### December 2025

https://nsearchives.nseindia.com/web/mediaattachment/2026-01/Exchange_Data_CM_Segment_20260112185218.xlsx

### January 2026

https://nsearchives.nseindia.com/web/mediaattachment/2026-02/Exchange_Data_CM_Segment_Jan2026_20260217133015.xlsx

### August 2026

https://nsearchives.nseindia.com/web/mediaattachment/2026-09/Exchange_Data_CM_Segment_Aug26_20260911134110.xlsx

Exact downloaded bytes and SHA-256 values are retained.

No URL substitution is allowed inside D008 after source inspection begins.

## Frozen XLSX parser contract

D008 uses only the ZIP/XML structure of XLSX workbooks.

No formula recalculation is required.

The parser must enumerate:
- workbook sheet names;
- shared strings;
- inline strings;
- worksheet cell text and row/column coordinates.

A sheet is a classification candidate only if one row within the first 75
non-empty rows contains:

### Identity evidence

At least one of:
- ISIN;
- SYMBOL / TICKER / SECURITY SYMBOL;

AND at least one security/company descriptor such as:
- COMPANY;
- SECURITY;
- ISSUER;
- NAME.

### Classification evidence

At least one of:
- BASIC INDUSTRY;
- INDUSTRY;
- SECTOR;
- MACRO ECONOMIC SECTOR;
- INDUSTRY CLASSIFICATION.

Token matching is case-insensitive after whitespace/punctuation normalization.

## Candidate-sheet diagnostics

For every candidate sheet report:
- header row index;
- normalized header names;
- identity-header matches;
- classification-header matches;
- non-empty data-row count;
- rows with non-empty classification value;
- classification coverage;
- duplicate detected identities;
- unique classification-value count;
- sample classification values.

D008 must not infer classification from free-text descriptions when an explicit
classification column is absent.

## Frozen source-promotion gates

D008 may authorize a full historical sector-source scan only if ALL four sample
workbooks satisfy:

1. at least one classification candidate sheet exists;
2. candidate sheet contains a direct company/security classification column;
3. candidate mapping contains an ISIN column OR a unique symbol column that can
   be deterministically rebound to same-month NSE Security File symbol+ISIN in a
   separately frozen successor diagnostic;
4. at least 500 non-empty company/security data rows exist;
5. classification coverage is at least 90%;
6. duplicate direct identities are zero or explainable solely by multiple
   security series with a frozen exact-EQ filter;
7. classification column semantics are stable across the four sampled months;
8. no fixed 100/200/500-row source cap is indicated by the workbook.

## Direct-promotion gate

D008 itself may directly promote a point-in-time sector source only if, in
addition to the source-promotion gates:

- all four workbooks contain exact ISIN;
- mapping is one row per relevant equity identity after a frozen EQ filter;
- four-tier or Basic Industry classification semantics are explicit and stable.

Otherwise D008 may only authorize a separately frozen join diagnostic.

## Failure interpretation

If the monthly workbook does not contain broad company-level classification:

    FAIL_SOURCE_FEASIBILITY

Sector remains deferred.

Do not:
- use today's Basic Industry historically;
- infer sector from index membership;
- infer sector from company name or business description;
- treat turnover/size/PCA as semantic sector;
- open return outcomes to justify a weaker source.

## Success interpretation

A passing D008 proves only source/schema feasibility.

It does not prove:
- sector factor predictive value;
- risk-model improvement;
- prospective publication timing;
- live-capital readiness.

Any historical sector factor requires a separately frozen full-source scan and
point-in-time join contract.

Any prospective sector factor additionally requires source-timing validation.

Live capital remains disabled.
