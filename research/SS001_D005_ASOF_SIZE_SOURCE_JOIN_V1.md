# SS001-D005 Point-in-Time Size-Source Join Feasibility v1

Status: **FROZEN BEFORE FULL-UNIVERSE MATERIALIZATION**  
Frozen: 2026-10-08  
Return outcomes opened: no  
Market capitalization calculation: prohibited  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Evaluate whether the independent, official NSE share-count source (SS001-D004)
can be joined without look-ahead to an exact official October 1, 2026 price
observation and filing-publication evidence.

D003 failed because NSE quote trade-info returned HTTP 403 on all 2,319 names.
D004 independently passed share-count source feasibility. D005 is the first
**point-in-time readiness** stage, not a market-cap or valuation stage.

## Exact frozen inputs

- SS001-D001 full-market census, run `37197575401`, artifact `11301695772`,
  census SHA `0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7`.
- SS001-D002 shareholding source census, run `37198355430`, artifact `11302177421`,
  census SHA `214c1172491d58800dcded126303e7a2844967e75da57e0e6f666abc3b311293`.
- SS001-D004 reconciled issued-share source panel, run `37719724682`,
  artifact `11525307261`,
  panel SHA `ab782411fef19afd80cdde3da1cba402eff70778ce0aaa0bd3e3afd571ee7428`.

The join is strictly by exact NSE symbol across three inputs. D001's frozen
ISIN and series must be present and SERIES=EQ. No fuzzy company-name matching.

## Price and publication cutoff

Price session is exactly **2026-10-01**. Its D001 `market.last_close`
is usable only when:

- `market.last_observed_session == 2026-10-01`;
- close is finite and positive;
- current series is EQ and frozen ISIN is nonempty.

For shareholding evidence, use the D002 latest standard-quarter source only;
do not substitute a different or later shareholding report after seeing results.

Publication cutoff:

`2026-10-01T13:00:00Z` (18:30 IST).

A D002 source qualifies temporally only when:

- `latest.broadcast_at_utc` is a valid aware ISO timestamp at or before cutoff;
- `latest.report_date` is a valid ISO date no later than 2026-10-01;
- D004 share-count `report_date` equals D002 source report date;
- D004 `source_url` equals D002 `xbrl_url`.

Future-published or malformed sources remain fail-closed. A previous quarter may
be considered only under a new frozen amendment; v1 does not substitute it.

## Share-count eligibility

D004 `capitalization_source_eligible=true` and `status=SHARE_COUNT_READY`
are necessary (not sufficient) for a future current-company capitalization.

D005 requires the reported count to be a strictly positive integer and the
partly-paid flag to be explicitly `FALSE`.

Missing source, unavailable share count or partly-paid uncertainty remain
unavailable; do not infer shares from market price or capital value.

## Corporate-action boundary

SS001-D001 retains one-year categorical corporate-action counts, not a fully
reconciled post-report issuance ledger.

D005 retains one of two **unresolved** states for each temporally ready row:

- `KNOWN_CORPORATE_ACTION_REVIEW_REQUIRED` if D001 reports any bonus, rights,
  split/consolidation or scheme/reorganisation in its full one-year window;
- `NO_FLAG_IN_D001_STILL_UNVERIFIED` otherwise.

Neither state is equivalent to "no intervening share change." ESOP issuance,
conversions, preferential allotments, multi-class capital and other cases can
remain outside that count taxonomy.

**No current market capitalization, size band, EV, P/E or research rank may be
computed from D005.** A subsequent D006 must independently clear intervening
share changes, confirm all relevant share classes, and validate ISIN continuity.

## Frozen feasibility gates

D005 source readiness passes only if:

1. all 2,319 symbols are accounted for exactly once across the three sources;
2. D004's exact 1,965 capitalization-source-eligible records are reconciled;
3. at least **85% of those 1,965** have exact-source, pre-cutoff, positive-price
   joins (`TIME_AND_PRICE_READY`);
4. zero pre-cutoff-ready joins have symbol, report-date or XBRL-URL conflicts;
5. no capitalization outputs exist.

The thresholds cannot be changed after inspecting D005 results.

Passing D005 authorizes D006 share-action and security-class source feasibility
design, not current-size scores or positions.

## Scientific boundary

D005 uses no future returns, security-value estimation, backtest optimization,
investment opinions, ADO, PF001 or live-capital decisions.
