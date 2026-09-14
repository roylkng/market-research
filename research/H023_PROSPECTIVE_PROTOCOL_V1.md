# H023 Mutual Fund Ownership Accumulation prospective protocol v1

Status: **FROZEN BEFORE THE FIRST ELIGIBLE H023 PROSPECTIVE SOURCE**

Frozen: 2026-09-14
Prospective boundary: **2026-09-15 00:00:00 Asia/Kolkata**
Live capital: disabled
Historical return backtest: not authorized

## Objective

Test whether quarter-over-quarter accumulation by Mutual Funds, measured directly from official NSE shareholding-pattern XBRLs, predicts subsequent stock excess returns.

The primary signal is intentionally independent of price momentum, valuation, analyst revisions, management-language signals, accounting-quality scores, H013, H019, H020, H021, H022, PF001, or any combined rank.

## Frozen universe

- universe: `research/prospective/universes/FY27-Q2-2026-09-06.json`
- Git blob: `8026e81faee3e913d2fba1dba72d60603b69fa07`
- member count: 100

No substitutions are permitted inside H023-v1.

## Authoritative source

Discovery uses the official NSE shareholding master endpoint for each frozen symbol. Filing content must resolve to an approved NSE archive host.

Point-in-time publication time is the official NSE `broadcastDate`, interpreted in `Asia/Kolkata` and normalized to UTC.

The frozen Mutual Fund aggregate fact is:

- aggregate context: `MutualFundsOrUTI_ContextI`
- fact: `ShareholdingAsAPercentageOfTotalNumberOfShares`
- unit: `pure`
- value: fraction of total shares, converted to percentage by `fraction * 100`
- context period: exact XBRL instant must equal the selected master report date
- detailed Mutual Fund contexts, when present, must use the known `DetailsOfSharesHeldByMutualFundsOrUTIAxis` taxonomy dimension

Only standard calendar quarter ends are eligible: March 31, June 30, September 30, and December 31.

## Discovery completeness

Every authoritative scan must attempt all 100 frozen U001 symbols. A partially successful scan cannot advance canonical H023 state.

For each scan, retain deterministic source identities, discovery timestamps, official broadcast timestamps, approved XBRL URLs, source hashes, extraction status, and the exact code/source-contract identity. Raw source evidence may be retained in the workflow artifact store, while canonical repository state retains the hashes and derived evidence needed for offline verification.

No alternative provider may fill an NSE gap.

## Prospective eligibility boundary

A symbol-quarter is prospectively eligible only if the **first official NSE broadcast for that standard-quarter report date** is at or after `2026-09-15 00:00:00 Asia/Kolkata`.

If the first official broadcast for a quarter predates the boundary, that quarter is permanently pre-boundary. A later revision or resubmission does not make it prospective.

Pre-boundary Q2/FY27 ownership values used to establish source feasibility must never enter the prospective H023 signal ledger.

## Primary current filing

For each symbol and eligible report quarter, the primary current filing is the first official NSE broadcast for that quarter.

The first source candidate is immutable. If its approved XBRL cannot be fetched, its report period cannot be verified, or its frozen Mutual Fund fact cannot be parsed under the source contract, the symbol-quarter becomes `SOURCE_BLOCKED` for the primary experiment. A later revision cannot replace it as the primary source.

Later revisions remain append-only diagnostics and must never rewrite a sealed primary signal.

## Prior-quarter binding

For current report date `Q`, the only valid prior period is the immediately preceding standard calendar quarter end.

The prior filing is the latest protocol-valid official revision for that prior report date whose NSE `broadcastDate` is **not later than the current filing's broadcast time**.

This cutoff is the current source publication time, not the later collector time. A prior-quarter revision published after the current filing cannot alter the baseline retrospectively.

If no valid adjacent prior-quarter filing existed at the current filing's publication time, the current symbol-quarter is `NO_SIGNAL_PRIOR_UNAVAILABLE`.

## Primary signal

For a valid current/prior pair:

`mf_ownership_delta_pp = current_mutual_fund_percentage - prior_mutual_fund_percentage`

Units are percentage points.

Larger positive values represent stronger Mutual Fund accumulation. Negative values represent distribution.

No winsorization, sector neutralization, market-cap adjustment, momentum overlay, valuation adjustment, narrative override, or discretionary tie-breaker is part of the H023-v1 primary score.

## Signal identity and immutability

There is at most one primary H023 signal record per `(symbol, report_date)`.

A sealed record must bind at minimum:

- frozen universe identity;
- symbol and report date;
- current NSE record ID, XBRL URL, broadcast timestamp, and content hash;
- prior NSE record ID, XBRL URL, broadcast timestamp, and content hash;
- parsed current and prior MF ownership percentages;
- `mf_ownership_delta_pp`;
- source first-seen timestamp;
- actual `signal_frozen_at_utc`;
- parser/source contract identity;
- deterministic record hash.

Sealed records are append-only and cannot be recomputed from later revisions.

## Executability

The nominal entry is the first reviewed completed NSE-session open strictly after the current filing's official broadcast time.

A primary signal is executable only when `signal_frozen_at_utc` is not later than that nominal entry open. Signals frozen after the nominal entry are retained as `LATE_SIGNAL_FREEZE` diagnostics but are excluded from the primary executable population. They are not backdated and the entry is not silently shifted.

Collector scheduling exists only to minimize this operational exclusion. Actual timestamps, not nominal cron times, determine executability.

## Prospective outcomes

Outcome rules are frozen before any H023-v1 return is opened and deliberately reuse the previously frozen H022-X001 discipline for comparability:

- horizons: 20, 60, and 120 completed NSE sessions;
- primary horizon: 60 sessions;
- entry: nominal first NSE open defined above;
- exit: close of the horizon session;
- benchmark: Nifty 500 over the identical entry/exit interval;
- primary return: stock return minus Nifty 500 return;
- frozen round-trip implementation cost: 0.50 percentage point;
- unresolved share-changing corporate actions block the affected horizon rather than being guessed through;
- unresolved NSE special-session dates or insufficient reviewed calendar coverage keep an outcome pending.

No return may be inspected before its exit session has completed.

## Primary statistical evaluation

The primary directional hypothesis is monotonic:

> larger `mf_ownership_delta_pp` predicts higher 60-session Nifty 500 excess return.

For each horizon report:

- Spearman correlation between the raw H023 score and excess return;
- deterministic signal quintiles;
- top-quintile and bottom-quintile mean excess return;
- top-minus-bottom mean excess spread;
- top-quintile median excess;
- top-quintile mean cost-adjusted excess;
- top-quintile Nifty 500 beat rate;
- 10,000-iteration symbol-cluster bootstrap using frozen seed `22022`.

Repeated observations from one company remain in the same bootstrap cluster.

## Frozen evidence gates

The 60-session primary classification uses the same thresholds already frozen for H022, preventing H023 from receiving an easier hurdle after its mechanism was chosen.

Coverage gate:

- at least 200 complete primary observations;
- at least 80% completeness among mature primary observations.

If the coverage gate is not met: `INSUFFICIENT_COVERAGE`.

Otherwise:

- `REJECTED` if top-minus-bottom mean excess spread <= 0 or top-quintile mean excess <= 0;
- `STRONG` if spread >= 4.0 percentage points, symbol-cluster bootstrap 95% lower bound > 0, and top-quintile benchmark beat rate >= 55%;
- `PROMISING` if spread >= 2.0 percentage points, top-quintile median excess > 0, and top-quintile benchmark beat rate >= 55%;
- otherwise `INCONCLUSIVE`.

These classifications are research evidence only and do not authorize live capital.

## Revision and backfill failures

If NSE later exposes a previously unseen filing whose official broadcast time proves that an already-sealed signal used incomplete prior context, the affected symbol-quarter becomes a `RETROACTIVE_SOURCE_GAP`. The historical signal is not rewritten.

If a later revision changes current or prior ownership values, preserve it as diagnostic evidence only. H023-v1 primary signals remain bound to information that was actually public at their frozen event time.

## Scientific boundary

H023-v1 is prospective from the stated boundary. Source-feasibility evidence before the boundary may determine parsing and provenance rules, but no pre-boundary stock return, post-filing price path, benchmark return, H013/H019/H020/H021/H022 result, PF001 result, or combined-rank outcome may alter this signal definition, source contract, horizons, cost assumption, or evidence thresholds.

Live capital remains disabled.
