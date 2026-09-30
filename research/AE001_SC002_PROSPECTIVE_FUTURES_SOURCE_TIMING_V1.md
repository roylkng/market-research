# AE001 SC002 Prospective Stock-Futures Source-Timing Protocol v1

Status: FROZEN BEFORE FIRST SC002 PROBE
Frozen: 2026-09-30
Live capital: DISABLED

## Objective

Establish whether the official same-session NSE F&O UDiFF source required by
AE001-T005 is actually available and parseable before the frozen AE001 EOD
decision cutoff.

SC002 is an operational prospective source-timing stream. It does not open
returns and does not itself validate T005 alpha.

## Start boundary

First eligible probe date: 2026-09-30.

## Frozen decision cutoff

18:30:00 Asia/Kolkata.

The actual timestamp after the HTTP fetch completes is authoritative. Cron time
or workflow start time is not evidence of source availability.

## Required source

Official NSE:

`F&O - UDiFF Common Bhavcopy Final (zip)`

Archive convention frozen by T005/D001:

`https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip`

The source must pass the merged T005 parser contract:

- ZIP contains exactly one CSV;
- required FO UDiFF columns exist;
- TradDt equals the candidate session;
- Sgmt = FO;
- Src = NSE;
- at least one valid STF contract row exists.

Individual invalid symbols may be excluded exactly as T005 requires. A structural
session-level parser failure is not eligible.

## Probe cadence

Approximate IST attempts:

- 17:00
- 17:30
- 18:00
- 18:15
- 18:25

GitHub scheduling delay is expected.

A missed or delayed workflow is operational missingness, not proof the NSE source
was unavailable.

Once one same-session source observation is READY before or at 18:30 IST, later
SC002 probes for that session are no-ops.

## Evidence contract

Each attempt records:

- session date;
- actual post-fetch UTC timestamp;
- cutoff UTC timestamp;
- source URL;
- status;
- raw SHA-256;
- exact raw repository path;
- parser diagnostics including STF/accepted-row counts;
- eligible_before_cutoff;
- immutable attempt hash.

Exact fetched bytes are retained under:

`research/prospective/ae001-sc002/raw/<session>/`

Canonical ledger:

`research/prospective/ae001-sc002/source-ledger.json`

## Relationship to SC001

SC001 proves current-session cash UDiFF + delivery-source timing.

SC002 independently proves current-session FO UDiFF timing.

A future prospective futures confirmation may use a decision session only when
BOTH SC001 and SC002 contain eligible-before-cutoff evidence for that same
session.

## Relationship to T005

T005 established historical-development information content but explicitly did
not verify historical FO publication timestamps.

SC002 closes only that source-timing gap.

## Non-goals

- no model fitting;
- no stock prediction;
- no return-label opening;
- no backfill of missed capture;
- no live trading;
- no claim that source timing on one day generalizes to all future days.

Live capital remains disabled.
