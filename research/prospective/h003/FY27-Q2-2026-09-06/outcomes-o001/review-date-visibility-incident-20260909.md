# H003-O001 review-date visibility incident — 2026-09-09

Status: **FROZEN BEFORE BATCH-6 SEMANTIC JUDGMENT**

Live capital: **NO**

## Incident

The frozen H003-O001 blind-review contract requires `later_evidence_publication_dates_visible: true`.

The authoritative `review-batches/batch-*.json` packets satisfy that requirement through `evidence[].exchange_published_at_utc`. However, `manual-review-workset-v1/batch-*.json` copied only `passage_id` and `text`, omitting `exchange_published_at_utc`.

The omission does not alter the frozen retrieval set or evidence text, but the v1 workset by itself is not a complete reviewer surface for timing-sensitive outcome judgment.

## Fail-closed treatment

1. No H003 return, benchmark, price, sector-return, or future-market outcome may be accessed because of this incident.
2. No private company/symbol binding may be accessed before a semantic batch is frozen.
3. Existing manual-review batch 5 is **QUARANTINED_PENDING_DATE_REAUDIT** and must not enter the H003 resolved denominator until re-audited with publication timestamps visible.
4. Batches 6–44 must not be judged from `manual-review-workset-v1` alone.
5. Until a corrected reviewer workset is generated, a reviewer may use the matching authoritative `review-batches/batch-*.json` packet together with the v1 workset, because the source packet is already identity-redacted, contains no market outcomes, and exposes the frozen publication timestamp required by H003-O001.
6. The semantic status set and every H003-O001 threshold remain unchanged: `MET`, `PARTIAL`, `MISSED`, `LATE`, `UNRESOLVED`; ambiguous timing and conflicting evidence force `UNRESOLVED`.

## Remediation requirement

Generate a lossless reviewer workset v2 that preserves exactly these reviewer-visible evidence fields from the already-frozen source packet:

- `passage_id`
- `exchange_published_at_utc`
- `text`

Do not expose company identity, symbol, source URL, exchange sequence, market outcomes, retrieval tuning, or private bindings.

Re-audit batch 5 against the corrected date-visible surface before counting it. Review batch 6 only after this incident is frozen.

## Contamination statement

At freeze time for this incident:

- batch-6 semantic outcomes had not been frozen;
- H003 market/return outcomes had not been accessed for this review;
- private company/symbol bindings had not been accessed for this review;
- live capital remained disabled.
