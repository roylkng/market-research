# SS002-P013: Fail-Closed NSE Daily Announcement Source Recovery

Status: **SOURCE-ONLY RECOVERY**, 10 October 2026 IST. No investment advice,
return outcome, market price estimate, or source backdating.

## What failed and what remains original evidence

On 10 October GitHub Actions run 38056665478 failed in the SS002 P001
"Capture missing completed NSE source days" step.
The underlying NSEClient raised NSEAcquisitionError because the
official https://www.nseindia.com/api/corporate-announcements
web session timed out (25-second read timeout) after its bounded retries.

Days **5–8 October 2026** were already independently captured and
hashed as canonical YYYY-MM-DD-v1.json packets; they are never
discarded or recomputed. The original **9 October** source date
remains explicitly unobserved until NSE raw announcement bytes are
actually retrieved.

A source request failure is not evidence of zero announcements,
zero relevant special situations, or a missing company catalyst.

## Source-failure receipt contract

Source collection retains prior raw/gzip source SHA values, original
dates and source acquisition timestamps under the original P001
capture contract. P013 adds only a distinct noncanonical receipt:

    research/prospective/ss002-p001/attempts/YYYY-MM-DD/<run-id>.json

Each such attempt retains:
- exact original NSE date requested and actual UTC run timestamp;
- failed source phase (listed-EQ master or announcements endpoint);
- limited failure category and diagnostic, plus original source date;
- a digest of the receipt and a unique immutable GitHub run identity;
- NULL announcement count, unavailable raw announcement bytes;
- NO canonical YYYY-MM-DD-v1.json publication or zero-event claim;
- return outcomes and portfolio/live-capital permissions explicitly false.

A failure receipt is evidence that NSE acquisition failed, NOT evidence
for or against any company announcement. Git retains the receipt and
validates its digest. Independent CI artifacts cover source/Git races.

## Bounded automatic retry and manual backfill

The scheduler retries the failed missing date across at most **three
separate scheduled runs**. If it remains inaccessible, the canonical
day stays explicitly missing and later runs can progress to other
unobserved days, preventing endless blockage of later research.

The bound avoids repeated expensive NSE requests during a site-wide
timeout. It does NOT validate the skipped day, treat it as a holiday,
or substitute another date. These remain explicit data-quality gaps.

Researchers can deliberately recover an exact source date with the
existing --start-date and --end-date options, even after the bound.
The original requested date stays fixed, while the actual later UTC
acquisition and historical-backfill classification remain recorded.
A successful original-source capture is the only possible promotion
to the canonical daily source packet. No sealed original is overwritten.

When the official endpoint is unavailable, the source runner writes
the gap receipt and stops, rather than hammering the same NSE site
for six more historical dates. Only the expected acquisition error
is classified. Malformed data, mismatched dates, or source-contract
defects still cause explicit failure.

## Workflow changes

.github/workflows/ss002-p001-daily-special-situations.yml now:
- runs automatically on merge of P013 into main and continues its
  original once-daily schedule;
- validates all successful canonical raw/gzip evidence and the hashes
  and data-quality flags of any failure receipts;
- reports blocked source dates in the GitHub Step Summary;
- commits official source bytes or source-unavailable receipts in
  append-only fashion with bounded safe-rebase retries;
- retains independent 90-day run artifacts for failed source attempts.

Tests:
- tests/test_ss002_p001_source_gaps.py
- tests/test_ss002_daily_capture.py

## Still missing

Actual 9 October NSE announcement bytes are **not** supplied or
invented by this patch. Failure receipts never contain a retrospective
event list, a ticker ranking or alpha results. Only genuine NSE
source acquisition can advance the source-day gate.

This infrastructure patch does not alter the frozen HG007 shortlist,
H021 research selection, original SS002 casebook, 20/60-session
prospective return protocols or company valuation stages. No live
portfolio or capital is authorized.
