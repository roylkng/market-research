# H024 Direct Insider Market Purchase prospective protocol v1

Status: **FROZEN PENDING MAIN INTEGRATION**

Frozen design date: 2026-09-15
Intended prospective boundary: **2026-09-16 00:00:00 Asia/Kolkata**, valid only if the complete H024 protocol is merged to `main` before that timestamp
Fallback boundary: the next `00:00:00 Asia/Kolkata` after complete H024 integration if the intended boundary is missed
Live capital: disabled
Pre-freeze H024 return inspection: prohibited

## Objective

Test whether a disclosed discretionary open-market equity purchase by a directly informed company insider predicts positive subsequent stock excess return.

The economic channel is internal capital commitment. H024-v1 is intentionally independent of:

- H002 unexpected earnings;
- H003 management delivery credibility;
- H004 catalyst and momentum triggers;
- H021 analyst expectation revisions;
- H022 management information delta;
- H023 Mutual Fund ownership accumulation;
- valuation, market-cap, stock-momentum, or narrative overlays.

Those features may later be tested as independent controls or ensemble inputs only after H024-v1 is evaluated on its own.

## Scientific sequence

The sequence is mandatory:

1. establish official source feasibility and parser semantics without opening returns;
2. freeze H024-v1 source, signal, entry, outcome, cost, and evidence rules;
3. merge the complete protocol to `main` before the prospective boundary;
4. only after that freeze, run any historical point-in-time H024 return challenge;
5. simultaneously collect fully prospective H024 events after the boundary;
6. live capital remains disabled regardless of historical or prospective result.

The May 2026 to September 15, 2026 Regulation 7(2) corpus is source-feasibility evidence before step 2. Its stock and benchmark returns remain sealed until after step 3.

## Investability universe

H024 is event-driven and is not restricted to the frozen U001 research cohort.

At each candidate's decision timestamp, the issuer must satisfy the primary investability portion of the already frozen H004-R001 rule:

- India;
- NSE main-board common equity `EQ`;
- exclude SME, ETF, REIT, InvIT, preference shares, and suspended securities;
- median traded value over the prior 20 completed NSE sessions at least INR 20,000,000;
- at least 60 completed NSE sessions of price history;
- no nominal-share-price filter.

H024 does **not** import H004 catalyst, momentum, expectation-gap, or stage-2 trigger logic.

Investability is evaluated point in time before the planned entry. Later liquidity or classification changes cannot rewrite a sealed event.

## Authoritative discovery source

The primary discovery source is the official NSE Regulation 7(2) PIT-GG feed:

`https://www.nseindia.com/api/corporates-pit-gg`

Only records whose `regulation` is exactly `Regulation 7 (2)` are in scope.

Each discovery record must bind at minimum:

- symbol;
- company name;
- `appId`;
- `typeOfSubmission`;
- `broadcastDateTime`;
- `exchdisstime`;
- `xmlFileName`;
- `ixbrl`;
- revision remark when present;
- `prevAppId` when present.

`prevAppId` is not assumed to be complete and is not required for safe revision handling.

## Official information timestamp

The authoritative public-information timestamp is NSE `exchdisstime`.

H024-v1 interprets that timestamp in `Asia/Kolkata` and normalizes it to UTC for canonical state.

The following are explicitly **not** valid substitutes for public availability:

- transaction date;
- transaction date range;
- date of intimation to the company;
- raw XBRL `DateOfFiling` without the exchange dissemination timestamp;
- collector first-seen time.

Collector first-seen time is retained separately as an operational provenance field.

## Authoritative filing content

Filing content must resolve to an approved NSE archive host and parse under the frozen raw-XBRL contract in `src/marketlab/h024_insider.py`.

The parser fails closed on unknown semantic changes. The frozen contract includes:

- regulation exactly `Regulation 7 (2)`;
- transaction typed axis `ChangeInHoldingOfSecuritiesOfPromotersAxis`;
- `TypeOfInstrument` is required in every disclosure context;
- exact required cash-security transaction concepts apply to every non-derivative disclosure context;
- an exact `Derivative` context is recognized and excluded from H024-v1 rather than coerced into the cash-security schema;
- quantity unit `shares`;
- transaction-value unit `INR`;
- ownership unit `pure`;
- ownership values interpreted as fractions and multiplied by 100 for percentages;
- no unrecognized additional typed axes in a transaction context;
- exact symbol agreement between discovery and XBRL.

Archive throttling or fetch failure is a transport failure. It must never be treated as evidence that parser semantics should be relaxed.

## Primary transaction semantics

A transaction context qualifies for H024-v1 only when every condition is true:

- actor category is exactly one of:
  - `Promoter`;
  - `Promoter Group`;
  - `Director`;
  - `KMP`;
  - `Promoter and Director`;
- instrument is exactly `Equity`;
- transaction type is exactly `Buy`;
- acquisition mode is exactly `Market Purchase`;
- transaction quantity is strictly positive;
- transaction value is strictly positive INR;
- executed exchange is exactly `NSE` or `BSE`.

The following cannot create a primary positive H024-v1 signal:

- immediate relatives;
- employees or designated persons who are not in an allowed direct category;
- ESOP or compensation transactions;
- gifts;
- off-market transfers;
- inter-se transfers;
- preferential allotments;
- pledge creation, invocation, revocation, or other encumbrance changes;
- sales;
- derivatives;
- warrants or non-equity instruments;
- transactions with zero quantity, zero value, or no recognized executed exchange.

## Filing eligibility

Only an NSE discovery record whose `typeOfSubmission` is `Original` can create a candidate.

The matching raw XBRL must indicate a non-revised filing and contain at least one qualifying transaction context.

A filing with qualifying and non-qualifying contexts still qualifies, but only qualifying contexts contribute descriptive purchase evidence.

## Primary signal

H024-v1 is a **binary event**, not a magnitude rank.

For an eligible symbol-entry event:

`h024_direct_market_purchase = 1`

Purchase value, purchase quantity, ownership delta, actor count, and filing count are retained as descriptive evidence but do not alter the primary H024-v1 score.

No winsorization, logarithmic value weighting, ownership weighting, actor weighting, market-cap scaling, sector neutralization, momentum overlay, valuation overlay, management-text adjustment, analyst-revision adjustment, or Mutual Fund-ownership adjustment is permitted in the primary rule.

Any later magnitude study is a distinct exploratory or challenger protocol and cannot retroactively redefine H024-v1.

## Same-symbol event aggregation

The planned entry convention determines the event key.

If multiple qualifying original filings for one symbol map to the same planned entry session, H024-v1 creates one binary symbol-entry event. All qualifying source filings are retained in that event's provenance bundle.

Descriptive fields may aggregate purchase value, quantity, distinct actors, and qualifying filings. Those aggregates do not increase the primary score above 1.

## Revision handling

A revision never creates a positive H024-v1 candidate.

NSE's discovery feed does not reliably provide complete `prevAppId` linkage for every revision, so H024-v1 uses a conservative symbol-level rule.

If any same-symbol Regulation 7(2) `Revision` is exchange-disseminated after a qualifying original but before that candidate's planned entry open:

- the candidate becomes `REVISION_BLOCKED`;
- the primary experiment does not enter it;
- no attempt is made to infer that the revision is unrelated from incomplete linkage.

If a revision is disseminated only after an event has already been sealed and entered:

- append the revision as later source evidence;
- mark the event as subsequently revised for diagnostics;
- never rewrite the sealed signal, entry, or realized outcome.

This asymmetry preserves point-in-time truth.

## Prospective eligibility boundary

A filing is prospectively eligible only when its official NSE `exchdisstime` is at or after the active prospective boundary.

The intended boundary is `2026-09-16 00:00:00 Asia/Kolkata` only if the complete H024 implementation and protocol are merged to `main` before that timestamp.

If integration occurs at or after that timestamp, the intended boundary is invalid. The boundary automatically advances to the next midnight in `Asia/Kolkata` after integration. No filing disseminated before the effective boundary can enter the fully prospective H024-v1 ledger.

This rule prevents a late merge from backdating prospectiveness.

## Entry convention

Same-calendar-session execution is prohibited even when a filing is disseminated before the market opens.

For a qualifying event, the nominal entry is the open of the first completed NSE trading session whose calendar date is strictly after the exchange dissemination date.

Examples:

- filing disseminated Monday at 08:00 IST -> Tuesday open;
- filing disseminated Monday at 19:00 IST -> Tuesday open;
- filing disseminated Saturday -> Monday open, subject to the reviewed NSE calendar.

The actual signal must be frozen before the nominal entry open. If collection or parsing finishes only after that open, retain the event as `LATE_SIGNAL_FREEZE` diagnostic evidence and exclude it from the primary executable population. The entry is never silently shifted to make a late signal executable.

## Prospective source and event state

Canonical H024 state must be append-only and independently verifiable.

At minimum retain:

- discovery source identity and immutable discovery fields;
- official exchange dissemination timestamp;
- collector first-seen timestamp;
- approved raw-XBRL URL;
- raw-XBRL SHA-256;
- parser/source-contract identity;
- filing type and revision metadata;
- parsed transaction evidence;
- qualifying transaction evidence;
- point-in-time investability evidence;
- planned entry session;
- event status;
- actual event freeze timestamp;
- deterministic source and event hashes.

A sealed primary event cannot be rewritten from later sources.

## Historical point-in-time challenge after freeze

After the complete H024-v1 protocol is merged, a historical challenge may evaluate eligible official Regulation 7(2) filings that predate the prospective boundary.

That challenge is explicitly **historical development evidence**, not prospective validation, even though filing and execution timestamps are reconstructed point in time.

The source and signal definitions frozen here cannot change in response to historical returns.

The historical challenge must use the same:

- direct-purchase semantics;
- revision blocking rule;
- investability rule;
- entry convention;
- 20/60/120-session outcomes;
- Nifty 500 benchmark;
- 0.50 percentage-point round-trip cost stress;
- corporate-action and calendar failure rules;
- evidence classifications.

## Outcomes

H024-v1 outcomes use completed NSE sessions:

- secondary horizon: 20 sessions;
- primary horizon: 60 sessions;
- secondary horizon: 120 sessions.

For every horizon:

- entry price: frozen nominal entry-session open;
- exit price: horizon-session close;
- benchmark: Nifty 500 over the identical entry/exit interval;
- excess return: stock return minus Nifty 500 return;
- cost-adjusted excess subtracts the frozen 0.50 percentage-point round-trip implementation stress from the stock side;
- unresolved share-changing corporate actions block the affected horizon rather than being guessed through;
- unresolved special sessions or missing required market bars remain pending or blocked;
- no horizon return may be opened before its exit session is complete.

## Primary statistics

At 60 sessions report:

- complete event count;
- distinct symbol count;
- mean Nifty 500 excess return;
- median Nifty 500 excess return;
- Nifty 500 benchmark beat rate;
- mean cost-adjusted excess return;
- 10,000-iteration symbol-cluster bootstrap confidence interval for mean excess using seed `24024`.

Repeated observations from one company stay in the same bootstrap cluster.

## Pre-frozen robustness tests

The following robustness views are frozen before outcomes and cannot alter the primary signal:

1. **first event per symbol**: retain only the earliest complete eligible event for each symbol;
2. **non-overlapping events**: for each symbol, retain the earliest event and remove later entries whose 60-session holding window overlaps a retained event;
3. **industry composition**: report results and concentration by pre-event industry classification;
4. **publication-month composition**: report dependence on calendar month;
5. **purchase-value composition**: descriptive buckets only, without changing the primary binary score.

A positive primary result that reverses sign in both first-event and non-overlapping-event views cannot be promoted.

## Frozen evidence gates

Coverage gate at the 60-session primary horizon:

- at least 100 complete primary events;
- at least 50 distinct symbols among complete primary events;
- at least 80% completeness among mature primary events.

If the gate is not met: `INSUFFICIENT_COVERAGE`.

Otherwise:

- `REJECTED` if mean excess return <= 0 or median excess return <= 0;
- `STRONG` if mean excess return >= 4.0 percentage points, the symbol-cluster bootstrap 95% lower bound for mean excess is > 0, benchmark beat rate >= 55%, and both first-event and non-overlapping-event mean excess returns are positive;
- `PROMISING` if mean excess return >= 2.0 percentage points, median excess return > 0, benchmark beat rate >= 55%, and both first-event and non-overlapping-event mean excess returns are positive;
- otherwise `INCONCLUSIVE`.

The economic spread thresholds deliberately match the strictness already used in H022/H023 while using statistics appropriate for a binary event rather than pretending H024 has meaningful top and bottom quintiles.

These classifications are research evidence only. Live capital remains disabled.

## Source-feasibility gate

The pre-outcome source gate is closed. The retained result is `research/H024_SOURCE_FEASIBILITY_RESULT_V1.md`.

The 2026-05-01 through 2026-09-15 official corpus contained 2,506 eligible Regulation 7(2) Original/Revision raw-XBRL documents. Rate-limited audit plus targeted schema closure resolved 2,505 documents and leaves one explicit raw-source HTTP 404 blocked rather than inferred. Four initial semantic failures were valid derivative disclosure contexts, now recognized and excluded without weakening any Equity purchase rule.

The final strict H024-v1 purchase filter remains frequent enough for the frozen coverage gate to be plausible: 788 qualifying source filings across 159 symbols in pre-outcome source-frequency evidence. This is feasibility evidence only, not evidence of predictive return.

The source gate permanently requires:

Transport failures such as NSE archive HTTP 403/429 must be distinguished from parser failures.

The source gate requires:

- strict parser tests green;
- no known deterministic semantic parser failure left unexplained in the audited current corpus;
- acquisition failures handled by bounded rate limiting/backoff rather than semantic relaxation;
- direct purchase events occur at a frequency sufficient for the frozen coverage gate to be plausibly reachable;
- exact source evidence retained by hash/artifact and compact feasibility evidence retained in repository history.

If this gate fails, H024-v1 remains `SOURCE_INFEASIBLE` or `SOURCE_INCOMPLETE`. The solution is not to weaken transaction semantics after seeing returns.

## Scientific boundary

No H024 stock return, benchmark return, future price path, H002/H003/H004/H021/H022/H023 outcome, PF001 outcome, or combined-rank result may change the source contract, qualifying actor categories, transaction semantics, entry rule, horizons, implementation cost, coverage gate, or evidence thresholds defined here.

Pre-freeze source data can establish only source feasibility, parser semantics, public timestamps, revision behavior, and event frequency.

Live capital remains disabled.
