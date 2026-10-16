# H022 document-comparability audit v1

Implemented October 15, 2026. This is a **noncanonical audit**, not a change to
H022-P001, H003-C001, the frozen feature extractor, or the outcome evaluator.
No price/return data enter the audit. No trading or live-capital permission is created.

## Finding and evidence boundary

At inspected commit `434ce97508de7c1005d1acfef9829cfe90199c22`, P001 still contains
MARICO signal `bf5fa646682f45594d9c11f981408539fd4ae2fdf8779dab3b9ee939144ec2f9`.
Its October 15 current source is described in the retained announcement as an
invitation for November 2, 2026, with a transcript to be published subsequently.
The stored current commitment count is zero. The August 11 prior has five
candidates. Their frozen density delta is `-0.9360140776517278`.

That number remains the frozen record. The audit marks its management-commitment
interpretation unavailable (`null`), not neutral (`0`). The notice remains useful
as event-scheduling information, not evidence of what was said at an unheld call.

The two input JSON files were reconstructed from connector-returned text and
matched their complete upstream Git blob IDs, byte-for-byte:

| File | Git blob SHA |
| --- | --- |
| signal-ledger.json | 898e4fadc226cd078a38760b949fe051d3334786 |
| source-ledger.json | 6c225a5169a925805f51eb8e5ce6d59460186081 |

Their canonical ledger hashes and each individual signal/source-record hash were
also recomputed. These are verified repository JSON copies, **not freshly fetched
NSE PDF bytes**. Direct PDF retrieval did not succeed. A public search result and
a fetched Coforge listing returned different cache windows, so neither was used
to assert that the pinned attachment was a link-only notice or a full transcript.

## What runs

`src/marketlab/h022_document_audit.py` provides:

- strict finite JSON decoding, duplicate-key rejection, canonical record/ledger
  verification, identity and timestamp consistency checks, and outcome-input rejection;
- conservative announcement triage, with a future-call plus deferred-transcript
  statement flagged as a notice based on **metadata only**;
- an exact-text-bound review interface for full transcripts, link-only notices,
  other documents and incomplete documents;
- a two-sided comparability function that preserves true zeroes and refuses
  unsupported current or prior inputs;
- a complete ledger audit and create-once, atomically published audit JSON output.

Positive eligibility requires a review attached to the expected text hash,
source ID, reviewer/evidence references and event time. The expected text hash
must come from retained provenance, not a newly substituted document. Review
assertions do not independently verify the reviewer's identity or judgement.
A full transcript with a cover letter remains eligible. A filename containing
`intimation`, a transcript keyword, a large character count or zero commitments
cannot establish document completeness.

The review timestamp can be later than the original cutoff. That does not move
the cutoff. A call that postdates the purported transcript publication is
rejected. Conflicting metadata and content are referred for review rather than
silently resolved in favour of either source.

**The command-line audit is metadata-only.** It cannot load PDFs, follow embedded
links, import new transcripts, backfill missing baselines or change prospective
signal selection. The content-review API is tested on synthetic text. It has
not yet been supplied the eight complete historical/current documents for this
snapshot. A future content-review pass needs their original artifact hashes,
applicability and point-in-time availability evidence.

## Observed bounded audit

| Symbol | Current-side observation | Audit result |
| --- | --- | --- |
| MARICO | Future call and deferred transcript explicitly stated in retained announcement | NOT_COMPARABLE |
| COFORGE | Transcript intimation in filename, attachment body unavailable for this audit | REVIEW_REQUIRED |
| SOLARINDS | Transcript metadata only in the audited inventory | REVIEW_REQUIRED |
| TCS | Transcript metadata only in the audited inventory | REVIEW_REQUIRED |

All four prior-source links are considered. Their complete source metadata and
body text are absent from this two-ledger input scope. This is not a claim that
the prior transcripts never existed. No record is positively certified by this
metadata-only audit, and the three review-required rows are not confirmed defects.

When an ineligible source later appears as a prior-source ID, the same classifier
blocks that comparison in the shadow view. This detects the false-rebound failure
mode without changing the original baseline selection.

## Preserve frozen science

The protocol's `immutability.revisions` clause requires separate provenance
corrections and disallows replacing the sealed signal in original outcome scoring.
This change touches no files in `research/prospective`, no frozen registry rules,
and no existing outcome/scanning/feature code. The test-fixture copies are not new
prospective records. They stay fixed when live ledgers append future signals.

Every annotation records the original signal hash, time and value. Every report
records both input file hashes, Git blob IDs, the declared pinned commit and its
own canonical hash. The CLI checks input bytes again before publication. Output
is confined to `research/audits/h022/P001/*.json`, never a canonical ledger. An
identical write is idempotent. A different write to an existing name is refused.
An optional previous-audit hash forms a chronological chain without overwriting it.

`--snapshot-commit` is a caller-supplied provenance identifier. During this run it
was checked through GitHub and the input blob IDs matched. The generic library
cannot independently authenticate an arbitrary caller's Git commit claim.

A filtered outcome analysis must be a separately labelled, non-confirmatory
sensitivity analysis. There is no automatic exclusion from P001 evaluation here.
A future collection filter requires a separately versioned/frozen successor rule.
The existing P001 collector is **not silently patched** by importing this module.

## Reproduce

From a complete repository checkout, with Python 3.11+:

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_h022_document_audit.py' -v
PYTHONPATH=src python -m marketlab.h022_document_audit \
  --repo-root . \
  --snapshot-commit 434ce97508de7c1005d1acfef9829cfe90199c22 \
  --output research/audits/h022/P001/my-new-review.json \
  --check
```

Use the actual checked-out commit in a new review. Do not reuse this commit label
for a different snapshot. Exit 0 means the audit was written. With `--check`, exit
2 means it was written but comparability blockers remain. Exit 1 means invalid
inputs or an output failure. Findings are not neutral market signals. This module
uses only the Python standard library and has no network code.

## Executed checks

Python 3.13.5: 66 focused unittest tests passed. Pytest independently ran the same
66 tests and reported 13 subtests passed. Those are **not 132 independent tests**.
Branch/line coverage for the new module is approximately 90%. Compileall passed.
The focused no-network test blocks socket construction. Full market-research test
and lint suites were not run, because a complete local checkout/dependency set was
unavailable. No GitHub Actions, cloud deployment or portfolio action was invoked.

Tests cover invitations, deferred transcripts, notice-only text, complete
transcripts with cover letters, missing/failed extraction, exact text and review
bindings, future availability, a real zero, invalid current and prior documents,
false rebounds, fixed original hashes, missing baselines, stale inputs, changed
frozen bytes, forbidden outcome data, audit chaining and protected output paths.

## Remaining review

Retrieve and verify the original current and prior document artifacts, especially
COFORGE's notice/linked-content distinction. Audit the wider historical source
inventory with the same separation between discovery metadata and actual content.
Do not silently substitute a later MARICO transcript or retune the frozen signal.
