# AB001 P002 H024 Cross-Family Orthogonality Pilot v1

Status: FROZEN BEFORE MATERIALIZATION
Frozen: 2026-09-30
Live capital: DISABLED

## Objective

Test whether the already-frozen H024 direct-insider-market-purchase signal
contains OOS information that is genuinely different from AE001's
price/liquidity/delivery model.

P002 is an integration/orthogonality diagnostic. It does not redefine H024 and
does not create a new insider hypothesis.

## Why 20 sessions

H024's sealed historical challenge already defined 20/60/120-session outcomes.
Its 20-session result is secondary but point-in-time and mature for a useful
historical subset.

P002 therefore uses 20 completed NSE sessions.

P002 must NOT reinterpret H024 as a 5-session signal merely to fit P001.

## Frozen H024 source

Event panel:

`research/historical/h024/challenge-2026-09-15/event-panel.json`

Required event-panel SHA:

`65b957a2a66144194690f0298602ca0118eb4af8e725cce5df7549da6b1baec4`

H024 signal remains binary:

- event stock = 1;
- non-event stock = 0.

Purchase value, actor count, quantity, ownership delta and filing count are
descriptive only and may not change the score.

## AE001 EOD causal compatibility

P002 only uses an H024 event when all are true:

1. exchange dissemination date is an actual NSE session;
2. official dissemination time is <= 18:30:00 Asia/Kolkata;
3. H024 planned entry is the immediate next completed NSE session;
4. exact H024 entry symbol + ISIN is present in the AE001 feature cross-section
   on the decision session;
5. the 20-session outcome matures no later than the original H024 historical
   market-data cutoff session, 2026-09-11.

Events disclosed:
- after 18:30 IST;
- on weekends/holidays/non-session dates;
- without exact decision-session identity continuity;
- or whose 20-session horizon had not matured by 2026-09-11

are excluded. They are never shifted to a later decision session.

## Pre-materialization feasibility audit

Read-only audit before this protocol was frozen:

- sealed H024 events: 209;
- AE001-EOD causal matches: 148;
- causal-match distinct symbols: 66;
- causal-match decision sessions: 57;
- complete 20-session causal events by 2026-09-11: 113;
- complete 20-session distinct symbols: 54;
- complete 20-session decision sessions: 41.

This feasibility count does not inspect P002 stock-level cross-sectional returns.

## Market / feature source

Reuse the exact T003/P001 source chain:

- market window: 2025-09-01 through 2026-09-25;
- exact pinned T003 corporate-action ledger;
- exact action-safe feature economics;
- exact delivery-augmented 27-feature panel.

Expected hashes:

- market panel:
  `9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e`
- action-safe base feature panel:
  `300c45cc6cd5f3e0b37dc419c2d6250317175f367bd74757f1ad45b4a4af63c8`
- corporate-action ledger:
  `1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1`
- augmented delivery feature panel:
  `99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90`

Any mismatch fails closed.

## Frozen AE001 comparison alpha

Alpha ID:

`AB001-P002-A1`

Construction:

T003 augmented 27-feature ridge at 20 sessions.

Frozen folds:

1. 2026-04-01 through 2026-06-30;
2. 2026-07-01 through 2026-08-27.

Ridge l2:

`1.0`

Training is purged exactly as merged T003 mechanics require.

P002 reconstructs the 20-session augmented ridge OOS stream, then restricts it
to the exact H024-compatible decision sessions/rows.

No model parameter is tuned to H024 outcomes.

## Frozen H024 alpha

Alpha ID:

`AB001-P002-H024`

For every eligible H024-compatible decision session:

- every common AE001 stock identity receives a record;
- exact H024 event identity receives raw prediction 1.0;
- every other identity receives raw prediction 0.0.

Multiple H024 filings/events for the same symbol+ISIN on one decision session
still produce one binary 1.0 score.

AB001 performs its normal tie-aware per-session percentile normalization.

## Common-row contract

Both alphas are evaluated only on identical:

`(feature_session, symbol, ISIN)`

rows with complete 20-session action-safe outcomes.

No stock/session row may exist in one alpha and not the other in the comparison.

## Diagnostics

### Standalone

For A1 and H024:

- mean/median rank IC;
- top-decile excess;
- bottom-decile excess;
- top-minus-bottom spread;
- top-decile churn.

### H024 event lift

Because H024 is sparse, P002 also reports per decision session:

- mean 20-session excess return of H024 event identities;
- mean 20-session excess return of non-event identities;
- event minus non-event mean excess.

Aggregate inference:

- paired/Newey-West mean event-lift inference;
- lag = 19.

### Orthogonality

Report:

- mean/median daily Spearman prediction correlation;
- daily top-minus-bottom spread correlation;
- common session count;
- common stock-session count.

### Incremental cross-family blend

Baseline:

`A1`

Challenger:

equal-weight rank blend of:

- A1;
- H024.

Compare on exact common rows.

Paired Newey-West lag:

`19`

Metrics:

- rank IC delta;
- top-decile excess delta;
- top-minus-bottom spread delta.

## No dynamic AB001 weighting in P002

P002 does not test the AB001-v1 dynamic efficacy blender.

Reasons:

- only 41 pre-audited mature event decision sessions exist;
- H024 is sparse and horizon-specific;
- P001 already showed that the current dynamic blender can dilute the strongest
  alpha.

The first question is orthogonality/incremental information, not weight tuning.

## Interpretation

P002 may establish:

- whether H024 is prediction-orthogonal to AE001;
- whether H024 event days add incremental 20-session cross-sectional
  information;
- whether a simple equal-weight cross-family blend improves exact common-row
  OOS diagnostics.

P002 does NOT establish:

- new H024 validity;
- prospective H024 validation;
- live-capital readiness;
- an optimal blend weight;
- a 5-day insider alpha.

Historical H024 outcomes were already known before P002 was designed. Therefore
P002 is a combination diagnostic, not an independent discovery test.
