# INVALIDATED H003-V001 blind review run

Status: **INVALIDATED BEFORE REVIEW-LEDGER FREEZE**

This evidence branch is retained only as an audit trail. It must not be used to produce H003 `ReviewDecision` records, accepted claims, outcomes, features, returns, or scores.

## Reason

The frozen `H003-V001` rule requires reviewer payloads to omit the source publication date. During semantic batch review, a reconstructed transcript header exposed a date string matching the frozen source publication date (for example, a line formatted like `October 16, 2025`).

The package builder correctly removed company symbol/name metadata but did not add the frozen exchange-publication date variants to the redaction set. Therefore the package was internally hash-consistent but did not satisfy the frozen blindness contract.

## Scope of invalidation

- Candidate corpus H003-E002 remains valid and unchanged.
- H003-V001 rule remains valid and unchanged.
- Blind package, compact/triage projections, 20-candidate batches, and intermediate semantic judgments on this branch are invalid for final use.
- Intermediate semantic judgment files `batch-0000.json` through `batch-0007.json` must never be compiled into final review decisions.
- No real H003 review ledger was frozen from this branch.
- No claim outcome, H003 feature, return evaluation, stock recommendation, or live-capital decision was created from this branch.

A corrected package must be rebuilt from the same frozen E002 candidate corpus after deterministic publication-date redaction passes regression tests. Because the corrected redaction changes blind-payload hashes, semantic review restarts from the corrected payloads rather than reusing these intermediate decisions.
