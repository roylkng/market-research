# AE001 D010 Protocol Amendment P3A: CM Short-Selling Parser Resolution

Frozen: 2026-10-01
Status: FROZEN AFTER P3 SHORT-SELLING PARSER FAILURE, BEFORE P3A DIAGNOSTIC
Live capital: DISABLED

## Trigger

D010-P3 run 36882557059 established:

- CM Short Selling archive route was previously source-resolved under P1;
- P3 semantic parsing produced zero READY short-selling sessions across 266
  completed NSE sessions;
- SLB independently passed P3 historical source viability.

P3 opened no return labels.

The short-selling failure therefore requires source-format diagnosis before any
parser change.

## Frozen diagnostic dates

Use only the original source-discovery dates:

- 2026-09-25
- 2026-09-24
- 2025-09-01

## Frozen source route

    https://nsearchives.nseindia.com/archives/equities/shortSelling/
    shortselling_DDMMYYYY.csv

## Diagnostic output

For each date record:

- exact raw SHA-256;
- exact CSV header;
- total non-empty row count;
- row-length distribution;
- first three non-empty source rows;
- last three non-empty source rows;
- unique raw Trade Date strings and counts;
- empty Symbol Name count;
- empty Quantity count;
- quantity values failing numeric parse;
- rows whose field count differs from header length.

No row is mapped to future returns.

## Purpose

P3A may identify the exact source-format reason for P3 rejection.

P3A must not:

- alter the P3 result;
- change source routes;
- aggregate duplicate rows;
- infer missing rows as zero;
- fit any predictive model;
- access stock-return labels.

Any parser repair requires a subsequent frozen P3B amendment and a fresh
full-window source audit.

No live-capital implication.
