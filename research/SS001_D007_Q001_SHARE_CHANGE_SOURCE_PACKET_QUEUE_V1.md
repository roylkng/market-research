# SS001-D007-Q001 Share-Change Source Packet Queue v1

Status: **FROZEN BEFORE QUEUE MATERIALIZATION**  
Frozen: 2026-10-08  
Return outcomes opened: no  
Share-count clearance and market capitalization: prohibited  
Portfolio eligibility: disabled  
Live capital: disabled

## Objective

Convert SS001-D006's dated, high-recall share-change *review* signals into
source-addressable evidence packets for document-level adjudication.

The queue supports capacity-aware analyst/LLM review, not a stock-ranking signal.

## Exact inputs

- SS001-D006-v1, run `37817153370`, artifact `11566934481`,
  audit SHA-256 `b2aef97d107a1494adafa70d18321ee2e484d7b4796fe6ed7a7b0f5336f2f479`.
- SS002-D001-P2-v1, run `37203696204`, artifact `11303667832`,
  census SHA-256 `ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071`.

D006 must contain exactly 2,319 symbols including exactly 1,960 D005
`TIME_AND_PRICE_READY` cases.

Exactly 331 review cases are expected:

- 24 `BOTH_SOURCES_REVIEW_REQUIRED`;
- 11 `CORPORATE_ACTION_REVIEW_REQUIRED`;
- 296 `ANNOUNCEMENT_REVIEW_REQUIRED`.

All other D006 states remain accounted for but are not adjudicated in Q001.

## Event and source linking

For every D006 announcement event ID:

1. Require an exact unique match against the frozen SS002 P2 canonical event ID.
2. Require the matched event symbol to equal the D006 symbol.
3. Require P2 state `CURRENT_INVESTABLE_IDENTITY`.
4. Retain P2's official NSE approved attachment URL only when
   `attachment_state=READY` and URL host is exactly an approved NSE archive host.
5. Missing/invalid attachment remains an explicit source-unavailable state.

For D006 corporate-action rows, retain exact source SHA-256, ex-date, subject,
symbol and source ISIN. These are primary source hints, not document-confirmed
issued-share changes.

Do not infer a new document SHA from a URL. A later consumer must bind the URL
to the passed SS002-D002 content-addressed document corpus before LLM inference.

## Frozen priority routing

This is source-review work ordering, *not* an expected-return ranking.

Priority tiers:

1. `BOTH_SOURCES_REVIEW_REQUIRED` (source overlap);
2. `CORPORATE_ACTION_REVIEW_REQUIRED` (exchange action only);
3. `ANNOUNCEMENT_REVIEW_REQUIRED` (announcement only).

Within a tier, order by:

1. descending combined number of dated candidate records;
2. ascending NSE symbol.

The deterministic first pilot contains exactly the first **50** packets from
that ordering. Remaining 281 packets stay in the queue for the same method later.

No market returns, market capitalization, business growth, names-of-interest or
investment outcome may change priority.

## Evidence packet

Each packet retains:

- symbol, frozen review state and priority rank;
- dated action rows and SHA/source identity;
- canonical P2 announcement IDs, exact official source URL when available,
  category hints and exchange publication timestamp;
- source-link readiness counts;
- explicit unresolved review questions:
  - Did an issuer-level equity share-count change actually occur?
  - Was it effective between shareholding report date and October 1?
  - Does it apply to this listed EQ security and ISIN?
  - Did a transaction involve a subsidiary, debt or purely procedural step?
  - Are other share classes/partly-paid shares relevant?

Every packet has:

`share_action_clearance_proven=false`;  
`capitalization_calculation_allowed=false`;  
`portfolio_eligibility_allowed=false`;  
`live_capital_allowed=false`.

## Frozen feasibility gates

Q001 passes only if:

1. the exact D006/P2 input hashes and zero-outcome flags are preserved;
2. all 331 review symbols are included uniquely;
3. each D006 announcement ID maps to exactly one P2 canonical event, same symbol;
4. every purported official attachment URL passes strict approved-host checks;
5. exactly 50 pilot packets are selected deterministically;
6. no issuer is certified unchanged and no capitalization is calculated.

## Promotion

Passing Q001 permits a separately frozen D007-L001 document-adjudication pilot
using the existing SS002-D002/D003 official document/segment provenance
and SS002-L001 structured fact extraction.

It does **not** authorize an LLM to declare share counts unchanged based only
on absence of keywords. Final capitalization requires affirmative dated equity
capital continuity evidence and review of security classes and corporate actions.
