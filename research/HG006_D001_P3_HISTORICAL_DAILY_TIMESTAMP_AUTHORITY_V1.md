# HG006-D001 P3 Historical Daily Announcement Timestamp Authority v1

Status: **FROZEN AFTER SOURCE-ONLY SHARD AUDIT, BEFORE A COMBINED D001 CENSUS EXISTS**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Completion probabilities assigned: no  
Chronology counts opened: no  
Scientific event taxonomy changed: no

## Why P3 exists

After P2 aligned HG006's redundant day guard to Asia/Kolkata, the combine step still
failed inside the previously audited canonical announcement parser for:

`AHLUCONT / seq_id 152114`

The exact frozen source row came from the requested NSE daily source
`2023-02-14` and contains:

- `an_dt = 14-Feb-2023 13:05:54`;
- `sort_date = 2023-02-14 13:05:54`;
- `exchdisstime = 02-Mar-2023 20:33:52`.

Thus the historical daily API row belongs to the requested February 14 source partition
while `exchdisstime` reflects a later exchange/revised dissemination timestamp.

## Source-only full-shard audit

Using the exact four successful shard artifacts from workflow run `37340989709`,
before any combined HG006 census or chronology output existed:

- raw daily rows inspected: 663,521;
- parseable `an_dt` whose Asia/Kolkata date equals requested source day:
  **663,521 / 663,521**;
- parseable `sort_date` whose date equals requested source day:
  **663,520 / 663,521**;
- `exchdisstime` whose Asia/Kolkata date equals requested source day:
  **662,016 / 663,521**;
- rows where `exchdisstime` differs/is unavailable but both `an_dt` and
  `sort_date` match requested source day: **1,505**;
- rows where none of the source timestamp fields match requested day: **0**.

No transaction-stage labels, completions, returns, payoff outcomes, current-company
results, or chronology counts were inspected in making this decision.

## P3 historical timestamp authority

For HG006 historical daily-source normalization only:

1. canonical event time is parsed from `an_dt`;
2. naive `an_dt` is interpreted in Asia/Kolkata, consistent with NSE daily source
   semantics;
3. its UTC-normalized instant remains the canonical
   `exchange_published_at_utc` stored in HG006;
4. the Asia/Kolkata calendar date of `an_dt` must exactly equal the requested source
   day;
5. a missing or unparseable `an_dt` fails closed.

`exchdisstime`, `sort_date`, and `dt` remain retained in exact raw source bytes but
do not override HG006 historical daily partition identity.

## Implementation boundary

Do **not** change the default/current behavior of
`marketlab.alpha_announcements.normalize_announcement_payload`.

Add an explicit historical timestamp-authority option used only by HG006-D001. Existing
SS002/current announcement research keeps its previously audited timestamp semantics.

## Canonical identity

HG006 canonical announcement identity is calculated from the same frozen semantic fields
as before, except that `exchange_published_at_utc` is produced from the P3 historical
`an_dt` authority.

Global canonical identity uniqueness remains an unchanged D001 gate.

## Explicitly unchanged

P3 does not change:

- exact four source shard artifacts;
- source window;
- initiation window;
- right-censoring cutoff;
- event-family taxonomy;
- attachment URL semantics;
- minimum source-feasibility thresholds;
- stage ontology;
- transaction episode threading;
- terminal outcome ontology;
- stage-conditioned competing-risk estimator;
- bootstrap uncertainty rules;
- any HG005 current-company payoff data.

## Regression requirements

Tests must prove:

1. default/current canonical announcement parsing still prioritizes its existing audited
   timestamp behavior;
2. HG006 historical normalization accepts a daily row where `an_dt` is on the
   requested day but `exchdisstime` is later;
3. HG006 historical normalization fails when `an_dt` is not on the requested day.

## Scientific boundary

P3 is a historical source-timestamp repair only. Probability estimation remains blocked
until unchanged HG006-D001 source-feasibility gates pass.
