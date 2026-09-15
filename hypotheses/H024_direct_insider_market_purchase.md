# H024 - Direct insider market purchase

## Status

`FROZEN_PENDING_SOURCE_GATE`

## Economic mechanism

A promoter, promoter-group member, director, or key managerial person who commits personal or controlled capital through a disclosed open-market equity purchase is taking an economically costly action under asymmetric information. A qualifying purchase can therefore contain information about private conviction, perceived undervaluation, or future operating conditions that is not equivalent to management language, analyst expectations, institutional ownership, or stock momentum.

The hypothesis is deliberately narrow. Compensation grants, ESOP exercise, gifts, off-market transfers, pledges, preferential allotments, generic employee transactions, immediate-relative transactions, derivatives, and sales are not treated as positive commitment events in H024-v1.

## Universe

At the decision timestamp, the issuer must satisfy the already frozen H004 primary investability rule without importing H004's catalyst or momentum conditions:

- India, NSE main-board common equity `EQ`;
- not SME, ETF, REIT, InvIT, preference share, or suspended security;
- median traded value over the prior 20 completed NSE sessions at least INR 20,000,000;
- at least 60 completed sessions of price history;
- no nominal-share-price filter.

Eligibility is evaluated point in time before entry. Later liquidity or classification changes cannot rewrite a sealed H024 event.

## Authoritative source

Discovery uses the official NSE `corporates-pit-gg` Regulation 7(2) filing feed. Filing content must resolve to an approved NSE archive XBRL URL and parse under the frozen H024 raw-XBRL contract.

The official information timestamp is NSE `exchdisstime`, interpreted in `Asia/Kolkata` and normalized to UTC. Transaction date and company-intimation date are never substituted for exchange dissemination time.

## Signal

The H024-v1 primary signal is binary. A filing can create a candidate only when all of the following are true in the authoritative raw XBRL:

- submission is `Original`, not `Revision`;
- regulation is exactly `Regulation 7 (2)`;
- actor category is exactly one of `Promoter`, `Promoter Group`, `Director`, `KMP`, or `Promoter and Director`;
- instrument is exactly `Equity`;
- transaction type is exactly `Buy`;
- acquisition mode is exactly `Market Purchase`;
- transaction quantity is strictly positive;
- transaction value is strictly positive INR;
- executed exchange is exactly `NSE` or `BSE`.

If at least one transaction context qualifies, the source filing is a qualifying purchase filing. Multiple qualifying contexts in one filing do not increase the primary score. Multiple qualifying original filings for one symbol that map to the same planned entry session collapse into one binary symbol-entry event.

Purchase value, quantity, ownership delta, actor count, and filing count are retained as descriptive evidence only. They are not weights in H024-v1.

## Revision rule

A revision never creates a positive H024-v1 signal.

Because the official feed does not reliably populate revision linkage for every filing, H024-v1 fails closed at symbol level. If any same-symbol Regulation 7(2) `Revision` is disseminated after a qualifying original but before that candidate's planned entry open, the symbol-entry candidate is `REVISION_BLOCKED` and does not enter the primary experiment.

A revision disseminated after a primary event has already been sealed and entered is appended as revision evidence. It cannot rewrite the prior decision, entry, or outcome.

## Decision rule

- information timestamp: official NSE `exchdisstime`;
- same-calendar-session execution: prohibited;
- entry: open of the first completed NSE trading session whose calendar date is after the exchange dissemination date;
- signal freeze must occur before that entry open;
- a signal first frozen after its nominal entry is `LATE_SIGNAL_FREEZE` and excluded from the primary executable population;
- primary holding period: 60 completed NSE sessions;
- secondary holding periods: 20 and 120 completed NSE sessions;
- exit: close of the horizon session.

## Benchmarks

Primary benchmark: Nifty 500 total price movement over the identical entry and exit interval.

Pre-frozen robustness views:

- industry/sector composition;
- first qualifying event per symbol;
- non-overlapping events per symbol, retaining the earliest event when 60-session holding windows overlap;
- event concentration by symbol, industry, publication month, and purchase-value bucket.

These robustness views cannot alter the primary signal definition.

## Costs

Frozen implementation stress: 0.50 percentage point round trip, applied to the stock return before comparing economic attractiveness.

## Primary test

The primary outcome is 60-session stock return minus Nifty 500 return from the frozen entry open to the frozen exit close.

Coverage gate:

- at least 100 complete primary events;
- at least 50 distinct symbols among complete primary events;
- at least 80% completeness among mature primary events.

If coverage fails, classification is `INSUFFICIENT_COVERAGE`.

Otherwise:

- `REJECTED` if mean excess return <= 0 or median excess return <= 0;
- `STRONG` if mean excess return >= 4.0 percentage points, the 10,000-iteration symbol-cluster bootstrap 95% lower bound for mean excess is > 0, and benchmark beat rate >= 55%;
- `PROMISING` if mean excess return >= 2.0 percentage points, median excess return > 0, and benchmark beat rate >= 55%;
- otherwise `INCONCLUSIVE`.

A `STRONG` or `PROMISING` classification also requires first-event and non-overlapping-event robustness to retain a positive mean excess sign. These are research classifications only and never authorize live capital.

## Known failure modes

- Regulation 7(2) is thresholded disclosure data, not a census of every insider transaction.
- source categories and labels can change, so unknown semantic variants fail closed rather than being inferred;
- revisions can correct transaction mode, category, value, quantity, ownership, or dates;
- insider purchases may cluster by issuer size, industry, family ownership, or market regime;
- a disclosed purchase can be motivated by signalling, governance, liquidity, or control considerations rather than undervaluation;
- NSE archive throttling is an acquisition problem and must never be solved by weakening parser semantics;
- repeated events from the same company are statistically dependent and stay in the same bootstrap cluster;
- unresolved share-changing corporate actions block affected return horizons rather than being guessed through.

## Scientific boundary

No H024 stock return, benchmark return, post-event price path, or downstream paper-fund result may be inspected before this signal/source/outcome contract is merged to `main` and the prospective boundary is established.

Pre-freeze historical Regulation 7(2) filings may be used only for source feasibility, parser semantics, event-frequency estimation, and provenance design.

## Freeze record

- rule version: H024-R001
- parser contract: `src/marketlab/h024_insider.py`
- source contract: official NSE Regulation 7(2) PIT-GG discovery plus approved NSE archive raw XBRL
- intended prospective boundary: 2026-09-16 00:00:00 Asia/Kolkata if and only if the complete protocol is merged before that timestamp; otherwise the boundary advances to the next 00:00 Asia/Kolkata after integration
- live capital: disabled

## Result

Not opened. H024 outcomes remain sealed until source feasibility and protocol integration are complete.
