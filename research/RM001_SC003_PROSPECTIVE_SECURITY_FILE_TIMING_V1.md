# RM001 SC003 Prospective Security-File Source Timing v1

Status: FROZEN BEFORE FIRST SC003 PROBE
Frozen: 2026-10-01
Live capital: DISABLED

## Objective

Determine prospectively whether the exact same-session NSE Capital Market MII
Security File required by RM001-v2 is available and structurally valid by the
frozen 18:30 Asia/Kolkata EOD decision cutoff.

SC003 is an operational source-timing stream.

It does not calculate returns, fit alpha, or create portfolio decisions.

## Start boundary

First eligible session date:

    2026-10-01

No earlier date may be backfilled into SC003.

## Source

Official NSE archive:

    https://nsearchives.nseindia.com/content/cm/
    NSE_CM_security_DDMMYYYY.csv.gz

Parser:

    RM001 D007 Security File parser

Required source identity fields:

- TckrSymb;
- SctySrs;
- ISIN;
- IssdCptl;
- ParVal;
- DelFlg.

## Frozen source-quality gate

A fetched same-session file is READY only when:

1. gzip/UTF-8/header parsing succeeds;
2. duplicate real EQ symbol+ISIN identity count = 0;
3. at least one real EQ identity exists;
4. at least 99% of real EQ rows have finite positive IssdCptl.

This is a source-only gate.

Exact same-session join coverage against the NSE market panel remains a
separate fail-closed requirement in an eventual RM001-v2 prospective risk
builder.

## Decision cutoff

    18:30:00 Asia/Kolkata

The authoritative observation time is the actual UTC timestamp taken after the
HTTP fetch finishes.

A source is prospective-cutoff eligible only when:

    status = READY
    and captured_at <= 18:30 IST

A READY observation after cutoff establishes publication timing only. It cannot
repair that session for a prospective RM001-v2 decision.

## Evidence

Append-only canonical ledger:

    research/prospective/rm001-sc003/source-ledger.json

Exact fetched bytes:

    research/prospective/rm001-sc003/raw/<session>/
    security-<sha256>.csv.gz

Each attempt records:

- session date;
- actual capture timestamp;
- decision cutoff;
- source URL;
- source SHA-256;
- exact raw repository path;
- parser diagnostics;
- positive IssdCptl coverage;
- READY / UNAVAILABLE / PARSER_REJECTED / SOURCE_QUALITY_EXCLUDED;
- eligible_before_cutoff;
- immutable attempt hash.

## Probe cadence

Approximate same-day probes:

- 17:45 IST;
- 18:00 IST;
- 18:15 IST;
- 18:25 IST.

GitHub schedule time is not evidence.

Actual post-fetch capture timestamp is authoritative.

A manual source-only probe is allowed through the frozen marker:

    [rm001-sc003-probe]

## Stopping rule

Once the first READY observation exists for a session date, later SC003 probes
for that date are no-ops.

The first READY capture is the publication-time observation.

## Promotion rule

Historical D007 evidence plus SC003 READY-before-cutoff evidence may establish
that the Security File is operationally usable for a future prospective
RM001-v2 decision.

Actual prospective risk use must additionally require:

- the same-session market source;
- exact symbol+ISIN market/Security-File join;
- all RM001-v2 point-in-time exposure gates.

SC003 alone does not authorize a portfolio decision.

No live-capital implication.
