# AE001 T008 Credit-Rating Semantic Attachment Features v1

Status: FROZEN BEFORE HISTORICAL OUTCOME MATERIALIZATION
Frozen: 2026-09-30
Live capital: DISABLED

## Objective

Test whether deterministic semantic information extracted from official NSE
credit-rating attachment PDFs adds short-horizon cross-sectional predictive
information beyond the frozen AE001 CORE27 price/liquidity/delivery feature set.

T008 is a new trial ID.

It does not retune T007's failed broad announcement taxonomy.

## Source lineage

Parent source:

- sealed T007 whole-market announcement panel;
- panel SHA-256:
  fc3be48ce09905b8d2ebef1ad0e75a7ed22815202abbd7d7b328fe6dfcd3957d;
- source window:
  2025-09-01 through 2026-09-25 inclusive.

Source-only diagnostics performed before T008 outcome materialization:

- rating source profile run:
  36726903972;
- deterministic attachment-language sample run:
  36727389077.

No T008 return outcome was opened by either diagnostic.

## Frozen rating source class

Normalize NSE announcement desc by collapsing whitespace and applying casefold.

Include exactly these normalized description values:

- credit rating
- credit rating- revision
- credit rating- new

Exclude:

- credit rating- others
- generic updates/press releases containing rating words
- ESG-rating announcements outside the exact source class

Expected selected source count from the sealed T007 panel:

2552.

Every selected source must have:

- NSE symbol;
- seq_id;
- parseable official exchange dissemination timestamp;
- HTTPS attachment URL on an allowed NSE archive host;
- attachment suffix .pdf.

Any source-class/count mismatch fails closed before return outcomes are opened.

## Attachment evidence

Each selected PDF is fetched from the exact NSE attachment URL.

Raw PDF bytes are retained content-addressed by SHA-256.

Parser:

- pypdf 6.17.0;
- strict = false;
- OCR forbidden;
- semantic scope = first three PDF pages only.

The first-three-page restriction is frozen from source-only diagnostics because
the rating-action summary/table consistently appears there and later pages often
contain generic surveillance/methodology boilerplate.

Source statuses:

- TEXT_READY
- NO_TEXT
- PARSE_ERROR
- FETCH_ERROR

Unresolved FETCH_ERROR blocks T008 materialization.

NO_TEXT and PARSE_ERROR do not silently become zero-event rows. The rating event
remains present from exchange metadata and sets:

rating_text_unavailable_current = 1

while body-derived action features remain zero.

## Frozen semantic parser

The parser scans normalized non-empty lines from the first three pages.

### Boilerplate exclusions

For withdrawal semantics, ignore lines containing generic agency boilerplate such
as:

- reserves the right to withdraw
- right to withdraw
- may withdraw

These phrases describe agency rights, not the current rating action.

### Action markers

UPGRADE:
- upgrade
- upgraded
- upgrading

DOWNGRADE:
- downgrade
- downgraded
- downgrading

REAFFIRMED:
- reaffirmed
- re-affirmed
- reaffirmation

OUTLOOK_POSITIVE:
- a line containing outlook and positive

OUTLOOK_NEGATIVE:
- a line containing outlook and negative

WATCH_POSITIVE:
- rating watch / watch with positive implications

WATCH_NEGATIVE:
- rating watch / watch with negative implications

WATCH_DEVELOPING:
- rating watch / watch with developing implications

WATCH_REMOVED:
- removed from rating watch
- rating watch removed

NONCOOPERATION:
- issuer not cooperating
- issuer non-cooperating
- non-cooperation
- non cooperation

WITHDRAWN:
- withdrawn / withdrawal on a non-boilerplate action-bearing line

One attachment may activate multiple semantic markers.

No marker is assigned a bullish/bearish numerical weight by hand. Ridge learns
the sign from purged training data.

## Point-in-time decision mapping

T008 inherits T007's frozen decision clock:

18:30:00 Asia/Kolkata.

Each rating announcement maps exactly once to the earliest completed NSE session
whose 18:30 IST decision cutoff is greater than or equal to the official exchange
dissemination timestamp.

Symbol is rebound to the exact same-session NSE EQ symbol + ISIN identity from
official UDiFF.

No symbol-only identity is carried through an ISIN break.

## Frozen T008 feature set

Seventeen features are added to CORE27:

1. rating_event_current
2. rating_new_current
3. rating_upgrade_current
4. rating_downgrade_current
5. rating_reaffirmed_current
6. rating_outlook_positive_current
7. rating_outlook_negative_current
8. rating_watch_positive_current
9. rating_watch_negative_current
10. rating_watch_developing_current
11. rating_watch_removed_current
12. rating_noncooperation_current
13. rating_withdrawn_current
14. rating_upgrade_20
15. rating_downgrade_20
16. rating_sessions_since_directional_cap60
17. rating_text_unavailable_current

rating_upgrade_20 and rating_downgrade_20 include the current decision session.

A directional rating event for recency means a current event with at least one
of:

- upgrade
- downgrade
- positive outlook
- negative outlook
- positive watch
- negative watch
- non-cooperation

rating_sessions_since_directional_cap60 is capped at 60. If no directional
rating event exists in available source history, value = 60.

## Base and challenger

Base CORE27:

- 18 price/liquidity features;
- nine T003 delivery/VWAP features.

Challenger CORE44:

CORE27 + exact 17 T008 rating-semantic features.

Base and challenger use exactly the same stock-session rows.

The rating feature layer may not filter rows based on whether a rating event
occurred.

## Model

Both models:

- ridge regression;
- l2 = 1.0;
- within-session tie-aware percentile inputs;
- identical labels and folds;
- chronological purged training.

No hyperparameter search is allowed.

## Primary endpoint

Horizon: 5 completed NSE sessions.

Entry:

next completed NSE session open.

Exit:

holding-session-5 close, entry session counting as holding session 1.

Target:

stock return minus Nifty 500 return over the identical interval.

Frozen validation folds:

1. 2026-04-01 through 2026-06-30
2. 2026-07-01 through 2026-09-18

Paired Newey-West lag: 4.

Primary support requires BOTH:

1. CORE44 minus CORE27 mean daily rank IC > 0 with two-sided p < 0.05;
2. CORE44 minus CORE27 mean daily top-minus-bottom spread > 0 with two-sided
   p < 0.05.

Intersection rule.

## Secondary endpoint

Horizon: 1 completed NSE session.

Frozen folds:

1. 2026-04-01 through 2026-06-30
2. 2026-07-01 through 2026-09-24

Paired Newey-West lag: 5.

Secondary evidence cannot rescue a failed 5D primary.

## No 20-session endpoint

T008-v1 does not test 20 sessions.

A medium-horizon rating trial requires a new trial ID.

## Trial accounting

T008 must be registered in research/ae001/trial-ledger.json before the first
T008 return outcome is materialized.

The source list, semantic parser markers and feature definitions must be
hash-frozen in a pre-outcome protocol amendment.

## Interpretation

T008 can establish historical-development incremental information for
deterministically parsed credit-rating semantics.

It cannot establish:

- prospective information content;
- causal impact of rating agencies;
- perfect semantic interpretation of all PDF formats;
- calibrated trading profitability;
- live-capital readiness.

If historically supported, the next gate is a separately frozen prospective
confirmation plus AB001 orthogonality against delivery and futures alphas.

Live capital remains disabled.
