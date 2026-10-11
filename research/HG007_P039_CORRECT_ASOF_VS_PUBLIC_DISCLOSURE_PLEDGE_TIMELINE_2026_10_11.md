# HG007-P039: INOXGREEN original ownership and pledge as-of/publication chronology

Source-only evidence reconciliation frozen 11 October 2026 IST.
**Neither a stock recommendation nor a timestamp-corrected alpha trial.**

## Source chronology matters more than the reporting period

Full-market GF001-D002 had an independently retained NSE shareholding
state for the original 28 HG002 outside-U001 hidden gems. Its original
full-market snapshot was collected **4 October 2026 at 12:58 UTC**.
All 28 original sources were available and revalidated in P038.

For INOXGREEN, that available October 4 snapshot used the latest
published *standard quarter-end* filing as of **30 June 2026**,
first publicly broadcast on **3 August**. It reported:

- Promoter/promoter-group: 56.12%.
- Public: 43.88%.
- Promoter-share pledged boolean: FALSE.
- Mutual-fund holding: 1.61% at that particular reporting date,
  not an as-of-October-11 current figure.

That is an accurate, historically knowable Oct4 filing state,
not proof promoters had no additional pledges after June.

The original NSE **exceptional September 29 QIP allotment-date**
filing was first publicly broadcast on **8 October 2026 at
13:24:47 UTC (18:54:47 IST)**. Its original P011/P012/P013
document/XBRL had:

- Issued equity: 419,602,518 (after 18,110,473 new QIP shares).
- Promoter group: 53.70%.
- Public: 46.30%.
- Promoter-share pledged boolean: TRUE.
- Named pledging promoter: Inox Wind Limited.
- Exact pledged promoter shares: 4,900,000.
- This particular pledged amount is as of **29 September**,
  not proof of the date the pledge was created.
- Original September 29 filing is **not** a regular September 30
  quarterly H023 observation and was **unavailable on October 4**.

Thus P038's zero pledged-company booleans in its source snapshot and
P013's subsequently public 4.9 million INOXGREEN pledged shares are
**not contradictory source errors**. They refer to different report
dates and different first-publication dates.

## Avoid fabricating a promoter sale

The reported promoter-group percentage decreased about 2.42 percentage
points between June30 and September29. Issued shares grew from
401,492,045 to 419,602,518 after the September QIP.

If June's rounded promoter percentage were applied to the old basic
share denominator and **only the denominator increased**,
the resulting promoter percentage would be near September's 53.70%.

This is evidence that dilution is a plausible arithmetic
explanation; it is **not proof that promoters neither bought nor
sold shares**, because current actual named holdings and rounding
must be independently reconciled before attributing transactions.

Nor does the later pledged-share disclosure identify its exact
creation date, lender, collateral terms or any possible release
after September29. We cannot apply that disclosed September29
pledge amount as a verified current October11 pledged balance.

## Consequences for 28-stock research

P039 preserves all 28 HG002 source cases, including the baseline
October4 GF001 governance evidence, while only INOXGREEN gets
an independently sourced subsequent filing timeline.

For the other 27 original hidden-gem companies, no claim is made
that their October11 ownership, direct pledges, outstanding options,
insider trades or current governance are verified by this exercise.

Before an equity recommendation:
- Recheck each company's actual latest public filing or pledge release.
- Respect source-first-seen timestamps, not retrospective "as-of" dates.
- Separate capital denominator dilution from real promoter stake disposals.
- Keep current share-based valuation, target WWIL business cashflow,
  completion odds and execution/liquidity gates independent.

## Reproducibility

Original source inputs pinned by Git blob:
- research/hg007/outside-u001-governance-2026-10-04/28-original-governance-v1.json
- research/hg007/hg007-p013-28-case-sept29-fd-pledge-overlay-v1.json
- research/hg007/inoxgreen-post-qip-special/original-promoter-pledge-v1.json
- research/hg007/inoxgreen-post-qip-special/original-receipt-v1.json

Code:
- src/marketlab/hg007_governance_timeline.py
- scripts/reconcile_hg007_governance_timeline.py
- tests/test_hg007_governance_timeline.py

Generated fixed record:
research/hg007/hg007-p039-inoxgreen-governance-first-seen-timeline-v1.json

No fit, alpha hypothesis revision, current investability approval, expected
return, stock buy/sell, paper trade or live capital is authorized.
