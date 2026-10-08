# SS001-D006 Dated Share-Change Evidence Review Queue v1

Status: **FROZEN BEFORE CROSS-SOURCE RECONCILIATION**  
Frozen: 2026-10-08  
Return outcomes opened: no  
Market capitalization / size ranks: prohibited  
Portfolio eligibility: disabled  
Live capital: disabled

## Objective

Produce a conservative *review queue* for share-changing activity that may make
a June/September share count stale relative to the 2026-10-01 close.

Do not interpret the absence of a flagged event as proof of unchanged issued capital.
D006 is explicitly **not** capitalization authorization.

## Exact frozen input sources

1. SS001-D005-v1, run `37815803355`, artifact `11567141610`,
   SHA `b5fe97c3a9e83e8acbfce9cddf4eed476d60c29ca5125caa400368b4f5c7e984`.
2. SS001-D001-v1, run `37197575401`, artifact `11301695772`,
   SHA `0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7`,
   including all seven official NSE corporate-action discovery chunks.
3. SS002-D001-P2-v1, run `37203696204`, artifact `11303667832`,
   SHA `ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071`.

D006 must account for exactly 2,319 D005 identities and the 1,960
`TIME_AND_PRICE_READY` subset.

## NSE corporate-action event evidence

Use exactly the corporate-action bytes content-addressed by D001:
`raw/corporate-action-discovery/sha256/<sha>.bin`.

Verify each of the seven raw SHA-256s from the D001 source manifest and
reproduce the recorded row count.

Only `series=EQ` action rows can trigger the listed-equity review queue.
For source completeness, parse every EQ `exDate` as a calendar date; malformed
or absent dates are explicit failures rather than guessed dates.

An event is **intervening** only when:

`shareholding_report_date < ex_date <= 2026-10-01`.

Join by exact NSE symbol. Retain the action's source ISIN for review, but never
discard an action because a split changed the ISIN.

An intervening EQ action is a possible share-change trigger when the subject
contains one of these frozen case-insensitive strings:

- `bonus`; `rights`; `split`; `sub-division`; `sub division`;
- `consolidat`; `demerg`; `merg`; `scheme`;
- `buyback`; `buy back`; `capital reduction`; `conversion`;
- `warrant`; `allotment`.

Other actions (including dividends) are retained in source accounting but do
not automatically trigger the share-change queue.

## Official corporate-announcement evidence

Use only the frozen P2 `CURRENT_INVESTABLE_IDENTITY` events.

For each shareholding-report date, an event can trigger a review only when
its exchange publication time satisfies:

`report_date < exchange_publication_IST_date`
and
`exchange_published_at_utc <= 2026-10-01T13:00:00Z`.

Use only these P2 taxonomy families as **possible** capital changes:

- `RIGHTS_ISSUE`
- `PREFERENTIAL_WARRANT`
- `SCHEME_REORGANISATION`
- `CAPITAL_REDUCTION`
- `BUYBACK`
- `INSOLVENCY_RESOLUTION`

This is intentionally a high-recall *review* routing layer. Examples such as a
listed parent subscribing to its subsidiary's rights issue, a buyback of bonds,
and procedural NCLT updates can be false positives. Only document-level
evidence under SS002-L001/L002 can resolve those cases.

## Deterministic review states

For each D005 `TIME_AND_PRICE_READY` security:

- `BOTH_SOURCES_REVIEW_REQUIRED` — dated action and P2 event evidence;
- `CORPORATE_ACTION_REVIEW_REQUIRED` — dated NSE corporate-action evidence;
- `ANNOUNCEMENT_REVIEW_REQUIRED` — P2 announcement evidence;
- `NO_OBSERVED_TRIGGER_STILL_UNVERIFIED` — neither source has a trigger.

Other D005 identities keep `D005_SOURCE_NOT_READY`.

In every state:

- `share_action_clearance_proven=false`;
- `capitalization_calculation_allowed=false`;
- no market cap or size score is emitted.

## Frozen feasibility gates

D006 passes as a source review queue only when:

1. exact 2,319 D005 identity accounting;
2. exact 1,960 D005 `TIME_AND_PRICE_READY` accounting;
3. all seven corporate-action raw files SHA-verified and their expected
   row counts reproduced;
4. every NSE EQ corporate-action ex-date is parseable;
5. all original P2 current events are accounted for without changing IDs;
6. zero automatic share-action clearances or capitalization outputs.

These are source-completeness gates, not accuracy/alpha claims. Their result
does not authorize market caps.

## Next permitted use

Passing D006 permits a separately frozen D007 reconciliation program for
document-supported issuer-level share changes, ISIN continuity and multi-class
equity. Later capitalization may be published only for individually verified
cleared names, not for a negative-keyword screen.

No future returns, valuation outcomes, parameter optimization, portfolio
changes or live-capital actions enter D006.
