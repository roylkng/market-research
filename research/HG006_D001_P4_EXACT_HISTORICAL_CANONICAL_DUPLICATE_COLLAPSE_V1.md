# HG006-D001 P4 Exact Historical Canonical Duplicate Collapse v1

Status: **FROZEN AFTER SOURCE-ONLY SHARD AUDIT, BEFORE A COMBINED D001 CENSUS EXISTS**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Completion probabilities assigned: no  
Chronology counts opened: no  
Scientific event taxonomy changed: no

## Why P4 exists

After P3 established `an_dt` as the historical daily timestamp authority, the exact
frozen shards exposed repeated rows that become the same canonical announcement identity.

The first combine failure was canonical identity:

`d4f1284c106146eddd5b3865c89487e34c68dabef2482bf4b7d33e104cad7c3f`

for PIXTRANS / seq_id 105579745 on 2023-08-07. The raw daily response contains two rows
with identical symbol, seq_id, an_dt, description, attachment text and attachment URL,
but different later `exchdisstime` / `difference` metadata.

Under P3, these are one economic announcement.

## Source-only full-shard duplicate audit

Using the exact four successful shard artifacts from workflow run `37340989709`,
before any combined HG006 census or chronology output existed:

- raw source rows: 663,521;
- repeated P3 canonical identity instances: **23**;
- repeated identities occurring across different requested days: **0**;
- repeated same (symbol, seq_id) with the same canonical identity: **23**;
- same (symbol, seq_id) with conflicting P3 canonical identities: **0**.

The 23 repeated canonical instances are therefore duplicate historical API rows, not
distinct or ambiguous announcement semantics.

## P4 duplicate policy

For HG006 historical daily-source normalization only:

1. within one requested daily payload, the first occurrence of a P3 canonical
   announcement identity is retained;
2. later occurrences of the exact same canonical identity in that same daily payload
   are collapsed;
3. same (symbol, seq_id) producing different canonical identities still fails closed;
4. the same canonical announcement identity appearing across different requested source
   days still fails the unchanged global uniqueness gate;
5. exact raw daily bytes and raw SHA-256 evidence remain retained unchanged.

## Current parser boundary

Default/current `normalize_announcement_payload` behavior remains unchanged and
continues to reject duplicate canonical identities.

P4 is enabled only through an explicit historical duplicate policy used by HG006-D001.

## Census accounting

HG006-D001 must retain both:

- raw_source_row_count;
- source_row_count = canonical rows after exact historical duplicate collapse;
- historical_canonical_duplicate_collapse_count =
  raw_source_row_count - source_row_count.

This makes the normalization visible rather than silently discarding source rows.

## Explicitly unchanged

P4 does not change:

- source shard bytes;
- historical timestamp authority;
- event taxonomy;
- initiation or censoring windows;
- attachment semantics;
- chronology thresholds;
- stage/outcome ontology;
- probability estimator;
- bootstrap method;
- any current HG005 company evidence.

## Scientific boundary

P4 is a historical source deduplication repair only. No probability, return, or
portfolio output is permitted until the unchanged D001 gates pass.
