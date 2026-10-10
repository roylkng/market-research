# HG007-P010: Original NSE September 2026 Shareholding and Pledge Source Gate

Status: **PRE-ANALYSIS SOURCE ACQUISITION ONLY, 10 October 2026**.
No live capital, equity alpha claim or corporate governance penalty.

## Why this gap must be addressed

The company's original 30 June 2026 Regulation 31 shareholding filing
reports a 401,492,045 basic equity count, 2,467,620 outstanding options,
403,959,665 reported fully diluted shares and **no promoter-share pledge**
in its declaration. This original June evidence is not a September fact:

https://www.inoxgreen.com/PDF/SHP_30JUNE2026R.html

The exact NSE original QIP allotment filing confirms that
18,110,473 new basic equity shares were allotted **29 September**,
bringing issued shares to 419,602,518. This is independently stored
and hashed in HG007-P007/P008.

Meanwhile a third-party latest source labelled **29 September 2026**
reports: 225,317,291 promoter shares, 53.70% promoter percentage
and 4,900,000 promoter shares pledged (Inox Wind Limited).
The unchanged nominal promoter holdings and lower percentage are
arithmetically consistent with QIP dilution, but the pledged quantity
cannot be verified from June's original issuer filing.

Third-party discrepancy reference:

https://trendlyne.com/equity/share-holding/1127763/INOXGREEN/latest/inox-green-energy-services-ltd/

A separate vendor still displays June's 56.12% as current.
Conflicting provider recency makes vendor consensus insufficient.

## Missing source and tricky acquisition detail

NSE's official issuer-specific shareholding master API:

https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol=INOXGREEN

The existing prospective H023 parser considers only standard quarter
end dates 31 March, 30 June, 30 September and 31 December.
However an original *29 September* as-of allotment filing, if present,
would be excluded by that science-specific filter even though it
could contain the newest post-QIP ownership and pledge evidence.

P010 captures the exact NSE master original JSON, selects the newest
published report date as of the actual source-capture time **including
special allotment dates**, and then fetches only the corresponding
official NSE archive XBRL. Duplicate/revised records at the same
broadcast time are rejected rather than selected arbitrarily.

The source-identity contract forbids foreign issuers, future-dated
reports, unsupported archive URLs, unseen HTTP redirects, source
substitution or bypassing a 403. NSE's existing H023 sessions are reused
with one attempt for each source. If source acquisition is blocked,
the original unavailability is recorded, not replaced by a provider.

## Analysis rules

The original post-QIP NSE XBRL can verify, **as of its report date**:
- exact issued/basic equity count, to be reconciled to 419,602,518;
- source-reported fully diluted share count and difference to basic;
- original GF001 issuer promoter/public fractions and pledge yes/no,
  subject to exact XBRL category/member semantics.

P010 uses the original HG005 official aggregate share-count parser
and GF001 promoter-encumbrance boolean reader. It does NOT infer
a 4,900,000 pledged *quantity* from a boolean, and does not independently
approve all promoter instrument subrows or current options.

A September 29 or September 30 XBRL filed before October 10 can verify
a historical *as-of-quarter-end* fact. It does **not automatically**
establish the same share count, pledged quantity or economic risk
on subsequent future trading sessions. A fresh same-date share-action
and promoter SAST/disclosure audit remains necessary for current state.

The workflow must distinguish:
- no newer original source available: preserve earlier June as **stale**;
- original new source access blocked: retain failed receipt;
- latest source present but malformed, share-count conflict or ambiguous
  revision: preserve original bytes, no governance promotion;
- post-QIP share count and exact GF001 governance source parsed:
  source-only dated ownership and pledge boolean, not an investment call.

## Code, reproducibility, and immutable custody

- Module: src/marketlab/hg007_ownership_source.py
- Probe: scripts/probe_hg007_inoxgreen_ownership.py
- Tests: tests/test_hg007_ownership_source.py
- Workflow: .github/workflows/hg007-inoxgreen-ownership-original.yml

On-merge and bounded October source retrieval uses the above official
API and approved original NSE XBRL archive. Original JSON/XML bytes
and hashes are anchored only if the source report date is after
the QIP and issuer/sharecount/governance parser checks pass.
Blocked, pre-QIP and partial original receipts remain available
as run artifacts without issuing a false "completed" source claim.

Manual trigger remains supported after October for later original
source recovery; the scheduled job is only active during October.

Even an official as-of report showing 4.9m pledged shares does not
justify a predictive return penalty or automatic disqualification
without a registered hypothesis and independent governance context.

**Post-QIP valuation, current cash-adjusted EV, completion probabilities,
portfolio eligibility and live capital remain disabled.**
