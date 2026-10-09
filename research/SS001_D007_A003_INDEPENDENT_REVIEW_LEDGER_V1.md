# SS001-D007-A003 Independent Semantic Review Ledger v1

Status: **FROZEN BEFORE FULL R001 INFERENCE AND INDEPENDENT REVIEW**
Frozen: 2026-10-09
Portfolio eligibility, issued-share clearance and live capital: disabled

## Purpose

Record independent human review of the 229 pages selected by the already-frozen
SS001-D007-A002 source-only audit. A schema-valid LLM answer is not proof that the
answer's claim, issuer or transaction stage is correct.

A003 checks review-record identity and completeness. It **cannot** mechanically
verify that a human actually read the page or that a reviewer is independent.
The resulting status is always reviewer-recorded evidence, not an investment,
capitalization or statistical accuracy certificate.

## Frozen authority

- frozen queue: SS001-D007-L001-P2-v1
- queue SHA: `59929004bcc5a5eae4491cadc237aa1bb26b822102d56b5b50cf61fb6b667618`
- frozen A002 selection SHA:
  `79e106f1d0b27810d06bd1c9e1bd192b967ef185393690ba0608354a698bbe86`
- A002 source result: `research/ss001-d007-a002-result-v1.json`
- exactly 229 selected pages, 70 documents and 12 issuers

Only an A002 packet materialized from validated R001 receipts is acceptable.
Packets with missing inference pages remain valid incomplete inputs, not passes.

## Reviewer annotations

Each annotation must contain:

- canonical `request_id` of one frozen A002 page;
- `source_page_text_sha256` and the exact validated extraction SHA;
- nonblank reviewer ID and an explicit independent-review attestation;
- a timezone-aware review timestamp;
- `PASS` or `ISSUES_FOUND`;
- an exact list of findings.

A `PASS` record must have no findings. An `ISSUES_FOUND` record must contain
at least one finding. Missing-inference pages cannot be marked reviewed.

Each finding must contain:

- category:
  `UNSUPPORTED_EXPLICIT_CLAIM`, `OMITTED_MATERIAL_TERM`,
  `ENTITY_CONFUSION`, `STAGE_MISCLASSIFICATION`,
  `CONTRADICTORY_TERMS`, `SOURCE_PAGE_UNREADABLE`, or `OTHER`;
- severity: `CRITICAL`, `MATERIAL`, `MINOR` or `INFO`;
- the selected `segment_id`;
- literal source-page excerpt (or empty only for `SOURCE_PAGE_UNREADABLE`);
- explanation;
- optional structured fact field path.

Every nonempty excerpt must be a literal substring of the original selected
source page under whitespace normalization. A model-generated paraphrase alone
is not source evidence.

## Fail-closed reconciliation

A003 rejects:

- wrong queue, selection or review-packet SHA;
- any extra or duplicate request ID;
- mismatched source-page text, segment ID or model extraction SHA;
- a PASS without inference, reviewer attestation or a timestamp;
- findings without matching source-page evidence;
- a failure verdict without a finding;
- changed source counts or any upstream portfolio/capital eligibility;
- malformed JSON, unverifiable receipt identity or unsupported verdict values.

Partial review annotation sets are permitted only as incomplete review ledgers.
They must never be represented as a passed audit.

## Outcomes

- `SOURCE_INFERENCE_MISSING` when any sampled inference is missing;
- `REVIEW_INCOMPLETE` when inferenced pages lack annotations;
- `ISSUES_RECORDED_REMEDIATION_REQUIRED` when all pages are annotated but
  one or more have issues;
- `REVIEWER_RECORDED_PASS_PENDING_INDEPENDENCE_VERIFICATION` when all 229
  sampled responses have reviewer-attested PASS records.

The last state is *not* an independent audit certificate. A separate verified
reviewer sign-off is required, and even then sampled semantic accuracy does not
prove the complete 1,240-page corpus correct.

Any material failure must be versioned and reprocessed; no silent patching of
model output or post-hoc alteration of A002 sample is allowed.

## Promotion boundary

A003 always emits:

`independent_semantic_audit_complete=false`
`share_action_clearance_proven=false`
`market_capitalization_calculated=false`
`return_outcomes_opened=false`
`portfolio_eligibility_allowed=false`
`live_capital_allowed=false`

Only separately frozen, exhaustive issuer-specific share-capital adjudication
can later authorize use of a share denominator or market capitalization.

## Security

Original filing text and reviewer explanations are untrusted data. Never
execute instructions contained in source pages or model output.
