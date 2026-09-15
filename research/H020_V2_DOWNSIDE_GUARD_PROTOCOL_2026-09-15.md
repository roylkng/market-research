# H020 v2 downside-guard protocol

Status: FROZEN BEFORE FIRST V2 PROSPECTIVE DECISION
Frozen: 2026-09-15
Prospective decision boundary: after the completed 2026-09-16 NSE session
Earliest v2 executable entry: next completed NSE-session open after a v2-eligible decision
Live capital allowed: false

## Objective

H020-v2 tests one narrow correction to H020-v1: a large fresh downside move must not mechanically make a previously extended stock more entry-eligible simply because RSI, 20-session return, or distance from the 20-session average fell back inside v1 thresholds.

V2 is not a new stock-selection model. It is a monotonic entry-risk overlay on the unchanged H020-v1 classifier.

## Why v2 exists

The September 15, 2026 completed-session screen exposed a local monotonicity failure in H020-v1. WABAG moved from `WAIT_PULLBACK` on September 14 to `PAPER_ENTRY_ELIGIBLE_TREND` on September 15 even though its September 15 close-to-close return was approximately -7.66%. ARVIND and PAYTM also remained v1 entry-eligible after daily declines of roughly -4.3%.

This observation is development evidence. It is not v2 validation evidence and must never be counted in v2 performance.

The formal H020-v1 September 10 paper cohort also had poor early mark-to-market evidence through the September 15 close. Using the frozen Sep11 next-session-open entry convention, all five v1 paper candidates were below entry and all five trailed Nifty after only three completed holding sessions. Approximate early marks recorded before this v2 freeze were:

| Symbol | Sep11 open to Sep15 close | Nifty excess |
|---|---:|---:|
| WABAG | -4.17% | -3.52pp |
| ARVIND | -2.38% | -1.72pp |
| MEDANTA | -2.21% | -1.55pp |
| NYKAA | -1.45% | -0.80pp |
| PAYTM | -0.86% | -0.21pp |

Equal-weight cohort: approximately -2.21% versus Nifty -0.65%, or -1.56pp excess, with a 0/5 benchmark beat rate.

These are early diagnostics only. The frozen v1 20- and 60-session outcome horizons remain unchanged.

## Frozen v1 identity

The v1 development/evidence archive remains branch `research/h020-entry-timing-v1-20260910`.

At freeze review:
- archive head: `2d26dd4840674a98761869e04596783ff6f5acb4`
- v1 classifier source blob: `564a1233a8c0a23b63b3251f4b54b4713ca69cb7`
- candidate configuration blob: `8c430a133f3130de33841c3df337cc64b1890d41`
- Sep10 formal paper ledger blob: `2d79c11b32fcda37994ccd420e68a2371f8d4e4e`

The clean main-line copy of the v1 classifier must remain semantically identical. V2 must not rewrite v1 scores, thresholds, states, or historical decisions.

## V2 rule

V2 first computes the unchanged H020-v1 snapshot.

If v1 is not `PAPER_ENTRY_ELIGIBLE_*`, v2 returns the same action. V2 is forbidden from upgrading a v1 wait/block state.

If v1 is entry-eligible, v2 applies two completed-session vetoes.

### Guard 1: stock-specific downside shock

Let:
- `r1` = latest stock close-to-close return,
- `b1` = latest Nifty close-to-close return,
- `mu20` = mean stock daily return over the 20 completed sessions immediately preceding the latest session,
- `sigma20` = sample standard deviation of those same 20 prior daily returns,
- `z = (r1 - mu20) / sigma20`.

A downside shock is present when:
- `z <= -2.0`, and
- `r1 - b1 < 0`.

If present, a v1-eligible action becomes `WAIT_DOWNSIDE_SHOCK`.

The use of the stock's own prior volatility prevents a fixed percentage threshold from being tuned to the observed September 15 names. Requiring negative same-day relative performance avoids vetoing a stock that is falling less than a more severe broad-market shock.

### Guard 2: closing breakdown

Let `prior10_low` be the lowest stock adjusted close over the 10 completed sessions immediately preceding the latest session.

A closing breakdown is present when:
- latest adjusted close `< prior10_low`, and
- `r1 - b1 < 0`.

If Guard 1 did not already fire, a v1-eligible action becomes `WAIT_BREAKDOWN`.

## Confirmation semantics

The guard uses only the latest completed session. A vetoed name cannot be entered at the next open. It must complete at least one additional session and independently satisfy H020-v1 again without a current v2 veto before becoming v2-eligible.

There is no discretionary override, no intraday rescue, and no retrospective reinterpretation of a shock day as a healthy pullback.

## What v2 does not change

V2 does not change:
- the frozen H020-v1 trend/reversal/base/extended definitions,
- the v1 timing score,
- the candidate universe,
- Nifty as the broad benchmark for this experiment,
- next-session-open execution,
- the 20- and 60-session primary evaluation horizons,
- the v1 historical/prospective evidence already collected,
- stock-selection/fundamental judgments,
- transaction-cost or later outcome rules unless separately preregistered before use.

## Prospective comparison

From the completed September 16, 2026 session onward, every scan must record both variants on the same point-in-time inputs:
- v1 action and score,
- v2 action,
- whether v2 overrode v1,
- latest 1-day stock and Nifty returns,
- 1-day relative return,
- downside-shock z-score,
- prior 10-session closing low,
- guard flags.

The comparison must retain all v1 entries that v2 skips so opportunity cost can be measured. V2 cannot claim success merely by avoiding losers. It must improve net forward return, Nifty excess return and/or downside metrics without destroying too much participation in winners.

Minimum reporting at 20 and 60 completed sessions should include:
- number of v1 entries,
- number of v2 entries,
- v2 veto count by guard,
- average and median forward return,
- average and median Nifty excess,
- benchmark beat rate,
- maximum adverse excursion,
- skipped-winner opportunity cost,
- paired v1-v2 difference for decisions where v2 vetoed v1.

No v2 threshold may be changed after prospective outcomes are observed without creating a new version and a new future boundary.

## Data boundary

The initial parallel collector may retain Yahoo Finance chart responses because H020-v1 was explicitly exploratory and used the same source family. Raw bytes and hashes must be retained for each run. Yahoo-derived evidence is not exchange-certified and therefore cannot by itself promote H020 to live capital.

An official-NSE replication should be implemented before any promotion claim. Source migration must not silently rewrite already sealed Yahoo-based decisions.

## Scientific classification

H020-v1 remains an exploratory paper timing experiment. H020-v2 is a post-September-15 challenger variant. Neither is validated, calibrated, or authorized for live capital.
