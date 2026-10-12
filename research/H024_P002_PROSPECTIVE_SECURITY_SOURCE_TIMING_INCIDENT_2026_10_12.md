# H024-P002: Pre-Entry Source Chronology and Official 404 Failure Handling

Review date: **12 October 2026**, AFTER the NSE morning entry open.
Classification: prospective-study integrity correction, NOT alpha or a
portfolio strategy change.

## Real observed failure, no hindsight corrections

The original H024 pre-entry sealer scheduled run
[38235977234](https://github.com/roylkng/market-research/actions/runs/38235977234)
started its original source scan at 2026-10-12T10:24:23Z. The existing
frozen NSE calendar's Monday 12 Oct entry open was
**2026-10-12T03:45:00Z (09:15 IST)**.

Thus the run was already **over six hours later than the required entry
open**, and could not legitimately have produced a timely prospective
source-backed entry. The diagnostic job did not write a primary event.

At 2026-10-12T10:26:43Z the run's requested official NSE source URL

    https://www.nseindia.com/api/reports?...date=12-Oct-2026...

returned HTTP 404. The failed run captured source-scan and offline
validation evidence; the canonical H024 event ledger was left
unmodified, with zero sealed events.

The frozen signal ledger includes exactly one intended 12-Oct symbol
entry (**WSI**), based on the original due keys. There is no
authorization to treat this candidate as a post hoc successful entry.

We do NOT infer from a 404 alone whether the original NSE security
master was not yet published, the endpoint/schema changed or the
requested date-specific report is unavailable. No previous-session
security master or another data vendor may be silently substituted.

## Executable behavior after this patch

Before even requesting the current session's security master, the
sealer checks the original signal's official market open and the
configured minimum pre-entry refresh lead. A GitHub job that runs
too late writes a result with:

- BLOCKED_PROSPECTIVE_SOURCE_NO_EVENT_SEALED;
- blocking_reason=PREENTRY_SOURCE_CUTOFF_MISSED;
- actual UTC time, original open and due symbol identities;
- original unmodified signal/event ledger SHA-256s;
- sealed_event_count=0, portfolio_eligibility_allowed=false.

If the NSE security-master report endpoint returns HTTP 404 **in a
timely run**, the source fetch fails closed immediately (no four
identical retries), records an explicit
OFFICIAL_SECURITY_MASTER_HTTP_404 block, and does not fabricate a
valid security/ISIN/liquidity observation.

If the required source acquisition consumes the remaining time
and crosses the official session open, the sealer records
PREENTRY_REFRESH_FINISHED_AFTER_ENTRY_OPEN rather than performing
the final revision scan from an invalid observation time.

Other transient/network errors remain hard failures. They are not
recast as clean exchange report non-publication.

The blocked source report is saved under the run evidence directory,
and the existing main-only anchoring workflow now also commits an
immutable, run-ID-and-attempt-keyed blocked receipt to:

    research/prospective/h024/entry-blocks/

The original H024 event, signal and source ledgers retain their
frozen event definitions. In particular, a blocked receipt is **not**
an event record, later stock prediction, simulated trade fill or
portfolio recommendation.

## Prospective protocol untouched

This correction does not modify:
- original 210 H024 qualifying signals;
- insider direct market purchase event classifier;
- frozen 20/60-session outcome rules;
- original universe/eligible exposure definition;
- same-session investability requirements or security-master identity;
- alpha accounting or live-capital authority.

An old missed date is not eligible for prospective promotion merely
because a later NSE download succeeds. Source-publishing time and
research first-seen time remain separate.

## Verification

    pytest -q tests/test_h024_event_sealer.py

Regression coverage proves the next-open timing gate blocks delayed
jobs, an official 404 causes exactly one original API request without
fallback, and a blocked report cannot represent an investment event.

## Still missing

The **operational availability of the same-day security-master
file before 09:15 IST** needs independent real-session timing
verification. A consistently unavailable source means the H024
primary protocol cannot be executed on those days, not that we
should relax the rules after observing returns.

The 12 October WSI candidate remains **missed/unsealed as a
prospective entry** under the original chronology.
