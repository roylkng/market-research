# H003 blind review operations v1

## Objective

This layer operationalizes the already-frozen `H003-V001` review contract. It does not change candidate extraction or review semantics. Its only job is to turn the externally anchored complete `H003-E002` candidate corpus into identity-redacted review payloads, deterministic semantic-review chunks, and finally a complete accepted/rejected review ledger.

## Frozen denominator

The H003 cohort contains 100 companies. H003-C001 froze three companies with zero eligible management-call transcript sources: `BHEL`, `ITC`, and `TRENT`. Therefore the complete 794-source E002 candidate report has:

- `expected_member_count = 100`
- `processed_company_count = 97`
- `processed_source_count = 794`

The three zero-source companies remain in the H003 cohort denominator. Requiring 100 source-bearing companies would make the valid frozen source corpus impossible to review and would incorrectly rewrite H003-C001 after the fact.

## Candidate evidence reuse

The complete sharded extraction artifact already contains every exact candidate-bearing PDF under `store/raw/sha256/<raw_sha256>.pdf`. `build_h003_review_package.py --candidate-store ...` reads those bytes locally and recomputes SHA-256 before review packaging. A missing or mismatched PDF is a hard failure.

Network re-fetch remains available only as a fallback when no candidate store is provided.

## Blind package

For each candidate-bearing source the package builder:

1. verifies the PDF bytes against the E002 candidate `raw_sha256`,
2. reconstructs the exact page/line text with the frozen `pypdf 6.17.0` parser,
3. verifies E002's 600-character excerpt reconstruction,
4. redacts the canonical symbol and company name,
5. emits a hash-bound `BlindReviewPayload`,
6. applies only H003-V001's high-confidence mechanical rejection rules,
7. leaves every other candidate in a symbol-free semantic review queue.

No candidate is mechanically accepted.

## Deterministic semantic chunks

`chunk_h003_review_queue.py` validates the blind-payload hashes and splits the semantic queue without reordering it. The default chunk size is 40 candidates. A manifest binds:

- full semantic queue SHA-256,
- exact candidate count,
- chunk count and size,
- each chunk SHA-256,
- first and last candidate id in every chunk.

The union of chunks must equal the original semantic queue exactly once.

## Review-ledger freeze

`freeze_h003_review.py` combines the frozen mechanical decisions with semantic decision files. It rejects duplicate decisions and then delegates complete candidate/payload/decision coverage to `freeze_review_ledger`.

Freeze is impossible unless every E002 candidate has:

- exactly one validated blind payload,
- exactly one ACCEPTED or REJECTED decision,
- a decision whose `blind_payload_sha256` equals the exact payload,
- and, for ACCEPTED decisions, normalized objectively resolvable `ManagementClaim` fields.

Rejected candidates remain in the ledger. Accepted claims are emitted through the existing claim-ledger schema. Claim outcomes remain empty in H003-B.

## Evidence separation

The canonical repository keeps rules, code, compact anchors and final review-ledger proofs. Bulky candidate reports, source PDFs, extracted text and intermediate blind packages remain on evidence branches and Actions artifacts. This keeps code review tractable without weakening reconstruction.

H003 remains paper-only. `live_capital_allowed` remains false.
