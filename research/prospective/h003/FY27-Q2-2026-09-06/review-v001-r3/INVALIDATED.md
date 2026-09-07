# INVALIDATED H003-V001 r3 blind review run

Status: **INVALIDATED BEFORE REVIEW-LEDGER FREEZE**

This branch is retained only as an audit trail. It must not be used to produce final H003 ReviewDecision records, accepted claims, claim outcomes, features, returns, scores, recommendations, or live-capital decisions.

## Reason

The frozen H003-V001 rule explicitly forbids `source_publication_date` from reviewer inputs. r3 correctly redacted the candidate's frozen NSE exchange-publication timestamp and passed the corresponding full-corpus date audit, but some reconstructed PDF page headers still exposed standalone transcript/source dates such as `April 16, 2026` or `February 09, 2026` when those dates differed from the NSE attachment timestamp.

Those standalone source-header dates are reviewer-visible source metadata and violate the frozen V001 forbidden-input contract.

## Scope

- H003-E002 candidate corpus remains valid and unchanged: 2,692 candidates.
- H003-V001 frozen rule remains valid and unchanged.
- r3 blind payloads, queue/chunks, JSONL projections, and semantic judgments are invalid for final use.
- Semantic judgment files batch-0000 through batch-0023 are intermediate invalidated work and must never be compiled into a final review ledger.
- No H003 review ledger was frozen from r3.
- No accepted-claim ledger, outcome, return evaluation, stock recommendation, or live-capital decision was produced from r3.

A corrected blind package must redact standalone source-header dates independently of the NSE exchange-publication timestamp, pass a full-corpus audit for that class of metadata, and restart semantic review from new payload hashes.
