# SS002-P002 First Daily Special-Situation Research Inbox v1

Status: **FROZEN BEFORE DAILY CROSS-PLANE ROUTING OUTPUT**
Frozen: 2026-10-10 (Asia/Kolkata)
No LLM inference, market-capitalization, return forecast or portfolio eligibility.

## Purpose

Convert the first completed source-only SS002-P001 daily captures into a complete,
auditable document-review inbox. Every candidate survives; HG001 is a fixed **prior
research snapshot** used to allocate human/LLM attention, not an investment signal.

## Exact source cohorts

Daily source days: 2026-10-05, 2026-10-06, 2026-10-07, 2026-10-08.
The four append-only manifests on `main` are mandatory, with exact hashes:

- 2026-10-05: `abaf46c8a03c15488991451090081c7739c9c3349aece2b763a685d784b92652`;
- 2026-10-06: `182f392a683978f3196e7467b8e832286a6b6b76e4c8bd049c42fa0e24c70772`;
- 2026-10-07: `9eddbcf450672c36ccf090254de16dbd3b7bb6b3898fa25872717f6b73743822`;
- 2026-10-08: `cefe063a076ff9bfb6a88e06293fe435e5a7a62707b0e294d247640d10ca135d`.

The source population is **54** category-hint candidates; **36** matched the
contemporaneous ingestion-time EQ security master; **18** were unmatched/archival.

HG001 historical cross-plane context:

- `HG001-D001-v1`;
- run `37258053642`, artifact `hg001-d001-37258053642`;
- router SHA `79e6b068f95c890e4ef88be62ffe2e8dfb94fabbf293770804e64aaa82d6e5ff`;
- exactly 2,319 as-of-baseline EQ identities.

The HG001 snapshot predates every daily source event. Its earlier earnings, governance,
asset and liquidity facts must **not** be described as refreshed daily data.

## Exact-identity join

An event may inherit HG001 context only when all are true:

1. P001 `mapping_state == SYMBOL_IN_EQ_MASTER_AT_CAPTURE`;
2. symbol appears exactly once in HG001;
3. P001 `current_eq_isin_at_capture` equals HG001 `isin`.

Otherwise no prior HG001 data is attached, even if the ticker text resembles an issuer.

Unmatched P001 symbols are **ARCHIVAL_OR_UNMATCHED_AT_CAPTURE**, not currently
tradable candidates. A symbol found in the capture-day master but without an exact
HG001 symbol+ISIN match is **IDENTITY_REVIEW_REQUIRED** and remains in the inbox.

Ingestion-time EQ master membership does not establish point-in-time historical
identity, issued-share continuity, or tradability.

## Research routing, not a ranking

For exact HG001 matches only:

- `CONVERGENT_PRIOR_RESEARCH`: prior active opportunity lane count >=2;
- `SINGLE_LANE_PRIOR_RESEARCH`: exactly one prior lane;
- `NEW_EVENT_NO_PRIOR_LANE`: no prior lanes.

For other rows:

- `IDENTITY_REVIEW_REQUIRED`: EQ-master symbol matched, no exact HG001 identity;
- `ARCHIVAL_OR_UNMATCHED`: symbol missing from capture-time EQ master.

These are source-context buckets only. None is a better-return claim. All 54 events
must remain in the output regardless of bucket.

## Document-review eligibility

An event is a `DOCUMENT_INTAKE_READY` **only** when:

- capture-day EQ symbol was matched;
- `attachment_state == OFFICIAL_URL`;
- `approved_attachment_url` exists on exact approved NSE archive hosts.

No LLM/model call occurs under P002. The subsequent document ingestion must verify
official attachment bytes and hash them before extraction. Lack of an approved URL,
identity continuity, or HG001 context must never become inferred evidence.

## Document threads

For navigation only, retain `symbol::category_hint` thread memberships.

Do **not** deduplicate multiple announcements as duplicate economic transactions;
retain every canonical announcement ID and its exact source timestamp. Threads are
search/navigation groups, not legal transaction episodes.

## Governance / source cautions

For exact HG001 identities carry the prior frozen governance caution flags
and asset caution flags **without changing them**. They trigger red-team attention,
not automatic rejection.

Carry capture lag classification and distinguish historical backfills from next-day
captures. No event is retroactively claimed to have been processed prospectively
on the original source day if it was acquired later.

## Acceptance

P002 passes source-only validation only if:

1. the four exact source hashes match the frozen contract;
2. the HG001 snapshot SHA and population match;
3. all 54 candidate event IDs are retained exactly once, with no extra events;
4. exact match, unmatched and identity-review states conserve all 54 events;
5. document-ready records carry an approved official NSE URL;
6. category hints are never relabeled as LLM-confirmed economic terms;
7. no capital, market cap, expected return, return outcome or portfolio eligibility
   enters routing.

No ranking score, expected return, live trading, or share-capital clearance is emitted.

## Next permitted step

P002 authorizes a source-only **P003 document ingestion queue** and selective LLM
economic-relevance analysis under the already-frozen SS002-L001 contract. It does
not itself promote an event to an investable thesis.
