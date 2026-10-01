# AE001 SC004 Prospective Short-Selling / SLB Source-Timing Protocol v1

Status: FROZEN BEFORE FIRST SC004 PROBE
Frozen: 2026-10-01
Live capital: DISABLED

## Objective

Prospectively establish whether the exact official NSE sources required by
AE001-D010 are available, parseable and identity-valid before the frozen AE001
EOD decision cutoff.

SC004 is operational source-timing evidence only.

It opens no return labels, fits no model and creates no alpha claim.

## Start boundary

First eligible probe date:

    2026-10-02

No earlier observation may be made eligible by backfill.

## Frozen decision cutoff

    18:30:00 Asia/Kolkata

The authoritative observation timestamp is taken AFTER all required source
requests complete.

Workflow start time and cron time are not evidence of source availability.

## Required current publication session D

SC004 first requires official NSE cash UDiFF for D to parse as a completed
NSE CM STK EQ session.

SC004 then identifies D-1 as the immediately preceding completed NSE cash
session by probing earlier official UDiFF dates and selecting the latest valid
session before D.

Maximum backward calendar search:

    7 days

The selected D-1 UDiFF bytes are retained as support evidence.

## Required CM Short Selling source

Official archive:

    https://nsearchives.nseindia.com/archives/equities/shortSelling/
    shortselling_DDMMYYYY.csv

where DDMMYYYY is publication session D.

Frozen timing semantics from D010-P3A/P3B:

- the file associated with publication session D contains short-selling trades
  from completed NSE session D-1;
- every source Trade Date must equal the resolved D-1 session;
- Symbol Name maps to D-1 UDiFF EQ symbol+ISIN;
- the mapped ISIN must still exist on D;
- duplicate mapped short identities fail closed.

A parser-valid file with zero source rows remains source-valid.

For a nonempty file, SC004 requires:

- trade-date identity mapping fraction >= 95%;
- same-ISIN continuity into D >= 95%.

## Required SLB Daily Open Positions source

Official archive:

    https://nsearchives.nseindia.com/archives/slbs/open_pos/
    slb_openpos_DDMMYYYY.csv

where DDMMYYYY is session D.

Frozen identity semantics:

- exact merged D010 SLB schema;
- source Security maps to same-session D UDiFF EQ symbol+ISIN;
- duplicate symbol+series rows fail closed.

A parser-valid file with zero source rows remains source-valid.

For a nonempty file, SC004 requires same-session identity mapping fraction
>= 95%.

## Eligibility

A session D receives:

    eligible_before_cutoff = true

only when ALL are true:

1. D UDiFF is READY;
2. D-1 completed-session UDiFF is resolved and READY;
3. short-selling D file is READY under the lagged D-1 contract;
4. short-selling live identity gates pass;
5. SLB D file is READY;
6. SLB live identity gate passes;
7. actual post-fetch capture time <= 18:30 IST.

A late valid observation is recorded but remains ineligible.

## Probe cadence

Approximate IST attempts:

- 16:37
- 17:07
- 17:37
- 17:57
- 18:17
- 18:27

Uncommon minutes reduce scheduler contention.

Diagnostic-only post-cutoff attempts:

- 20:07
- 21:07
- 22:07
- 23:07

A READY observation after 18:30 remains permanently ineligible. These later
attempts exist only to characterize publication timing when the pre-cutoff gate
fails.

GitHub scheduling delay is expected.

A missed/delayed workflow is operational missingness, not proof that NSE did
not publish a source.

Once a session has an eligible observation, later SC004 probes for that
session are no-ops.

## Evidence contract

Each attempt records:

- publication session D;
- resolved previous completed session D-1;
- actual post-fetch UTC timestamp;
- cutoff UTC timestamp;
- D UDiFF source URL/status/SHA/path/row count;
- D-1 UDiFF source URL/status/SHA/path/row count;
- short-selling source URL/status/SHA/path/row count;
- short-selling mapping and continuity fractions;
- SLB source URL/status/SHA/path/row count;
- SLB mapping fraction;
- eligible_before_cutoff;
- immutable attempt SHA.

Exact fetched source bytes are retained under:

    research/prospective/ae001-sc004/raw/<D>/

Canonical append-only ledger:

    research/prospective/ae001-sc004/source-ledger.json

## Relationship to D010 P4

D010 P4 establishes historical feature semantics only.

SC004 closes the source-publication-time gap for a future D010 confirmatory
trial.

Historical P4/T010 results may never be reclassified as prospective evidence
because SC004 later passes.

## Non-goals

- no feature calculation;
- no model fitting;
- no return labels;
- no backfill of missed captures;
- no live trading;
- no claim that one successful day proves all future publication times.

No live-capital implication.
