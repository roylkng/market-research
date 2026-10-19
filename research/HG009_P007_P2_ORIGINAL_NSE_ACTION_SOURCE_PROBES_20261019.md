# HG009 P007 P2 | Original NSE action-source capture and replay

**Research implementation date:** October 19, 2026. **Original 300-company study dates:** October 15 entry, October 22 H5 exit. Live capital disabled.

## Problem this solves

P006 now has original exchange price records for October 15, 16 and 19, but share-price differences are **not shareholder total returns**. Dividends, bonus/split/rights and corporate restructuring may affect a share even when its original ISIN remains the same.

The original HG009 P007 action-risk baseline was correctly **NO_ORIGINAL_SOURCE**. P2 acquires exchange original discovery responses through the existing NSEClient corporate-actions endpoint, records actual post-request receipt UTC, preserves HTTP/source failures, SHA-256-addresses original JSON, and independently replays the full 300 identity source screen.

**A successful empty NSE API response is not an exhaustive source audit.** The API may be paginated or incomplete. No P2 outcome, regardless of events or success status, may clear any issuer for economically adjusted returns or authorize investment.

## Immutable source and clock contract

1. Original source only: https://www.nseindia.com/api/corporates-corporateActions requested for 2026-10-15 through 2026-10-22, over all equities. This is not an issuer primary-filing replacement.
2. Each real attempt uses an immutable GitHub run-attempt ID, timestamps *after* network retrieval, records URL, SHA-256, byte length or a failed-original-access reason, and commits original byte data to content-addressed research/hg009/p007-originals/raw/sha256.
3. The signed screen always preserves 100 + 100 + 100 original symbol/ISIN identities, with reasoned hazards and ambiguities. The original P007 missing-source baseline packet is never overwritten.
4. Before official October 22 H5 close, the screen explicitly reports BLOCKED_SOURCE_CAPTURE_BEFORE_INTERVAL_END even if the endpoint supplies events. On and after the exit, source parsing remains SOURCE_SCREENED_COVERAGE_NOT_CERTIFIED, **never** economically cleared.
5. The capture window closes October 26 UTC. Any later scheduled run is a no-op. Every actual on-time source attempt is append-only, no retroactive first-seen date and no rewrite after outcomes.
6. An independent verifier hashes original raw JSON and recomputes the whole 300-issuer action screen, including original selected/control source membership. A changed original-source file, altered issuer, modified hazard packet, or failed/premature source cannot be promoted.

## Run and scientific status

    python scripts/probe_hg009_p007_actions.py --verify

Actual network capture is performed only on the dedicated GitHub workflow, which stamps its real source receipt:

    python scripts/probe_hg009_p007_actions.py --attempt-id github-run-id-attempt

Original NSE filing-level legal entitlement/adjustment still must be independently audited for every source hazard. The work is an **original-source risk inventory**, not a complete corporate-action or dividend total-return implementation. H5 price-only observation on October 22 does not by itself establish an investment strategy.
