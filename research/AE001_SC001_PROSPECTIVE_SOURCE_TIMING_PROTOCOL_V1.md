# AE001 SC001 Prospective Source-Timing Protocol v1

Status: FROZEN BEFORE FIRST SC001 PROBE
Frozen: 2026-09-29
Live capital: DISABLED

## Objective

Establish whether the official NSE sources required by the AE001 delivery/VWAP
feature family are actually available, parseable and internally valid before the
frozen AE001 EOD decision cutoff.

SC001 is an operational prospective evidence stream. It does not open return
outcomes and it does not itself test alpha.

## Start boundary

The first eligible probe date is 2026-09-30.

## Frozen decision cutoff

18:30:00 Asia/Kolkata on each candidate decision session.

Actual source-capture timestamps are authoritative. Scheduled workflow time is
not treated as the observation time.

## Required current-session sources

A session is source-timing eligible only when both sources are captured no later
than 18:30 IST:

1. official NSE cash-market UDiFF bhavcopy for that same session;
2. official NSE `sec_bhavdata_full_DDMMYYYY.csv` for that same session.

The UDiFF source must parse as NSE CM STK EQ data.

The delivery source must parse under the T003 schema and must pass the frozen
T003-P3 source-quality rule:

> exclude the whole delivery session if any complete EQ row has an absolute
> difference greater than 0.05 percentage points between reported DELIV_PER and
> 100 * DELIV_QTY / TTL_TRD_QNTY.

No conflicting official field may be silently overwritten or reconstructed.

## Probe cadence

The workflow attempts capture at approximately:

- 17:00 IST
- 17:30 IST
- 18:00 IST
- 18:15 IST
- 18:25 IST

GitHub scheduling delay is expected. The actual UTC capture timestamp determines
whether a probe is before or after cutoff.

Once a session has a successful eligible capture, later probes for that session
are no-ops.

## Evidence contract

Each attempt records:

- session date;
- actual capture timestamp;
- decision cutoff;
- market source URL/status/SHA-256;
- delivery source URL/status/SHA-256;
- delivery source-quality summary;
- whether both required sources were valid before cutoff;
- immutable attempt hash.

Exact successful source bytes are retained under
`research/prospective/ae001-sc001/raw/<session>/`.

The canonical append-only metadata ledger is:

`research/prospective/ae001-sc001/source-ledger.json`

## Relationship to T003

T003 established historical-development information content but explicitly did
not establish that the historical delivery file was available by the decision
cutoff.

SC001 closes only that timing gap.

## Relationship to future T004

No T004 return observation is eligible unless its decision session has an SC001
attempt with:

`eligible_before_cutoff = true`.

T004 parameters and success criteria must be frozen separately before its first
eligible decision session is used.

## Non-goals

- no live trading;
- no portfolio sizing;
- no return-label opening;
- no backfill of a missed source capture;
- no inference that an unavailable GitHub probe proves the NSE source itself was
  unavailable.

A missed/delayed workflow is operational missingness, not negative source
evidence.
