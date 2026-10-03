# AB001 P004 Regime-Conditioned Alpha-Efficacy Selector v1

Status: FROZEN BEFORE RG001 VALUES ARE OPENED
Frozen: 2026-10-03
Live capital: DISABLED

## Objective

Test whether predeclared session-level market context can predict the relative
out-of-sample efficacy of two already-sealed, economically distinct 5-session
alpha families:

- CORE27: AE001 price/liquidity + delivery/VWAP alpha;
- FUTURES_DELTA: the isolated T005 stock-futures positioning delta.

P004 does not create a new stock-level feature family.

RG001 variables are common to every stock on a session. Their only allowed use
in P004 is to choose which already-existing alpha family is trusted more on that
session.

## Frozen sources

### Alpha source

Sealed AB001 P003 evidence:

- workflow run: 36703199954;
- artifact id: 11090624849;
- artifact name: ab001-p003-36703199954;
- report SHA-256:
  0d833a280dcc741ebba13bfe8b753689b7ff1ad41f0b2c13181fd8b0c37552c6;
- library SHA-256:
  4e04142bb3b33ca9f1c86de456bed1e5479d7d6c89bd72e59bff14b5c713ec36;
- horizon: 5 completed NSE sessions;
- historical common sample in P003: 112 sessions.

Only OOS alpha records from P003 may enter P004.

### Market-context source

AE001 RG001-v1.

Frozen P004 context variables:

1. nifty500_return_20
2. nifty500_realized_vol_20
3. breadth_positive_momentum20_fraction

No additional RG001 variable may be added under P004 after values are opened.

## Relative-efficacy target

For every completed source session t:

    relative_ic_t =
        rank_ic(FUTURES_DELTA, t)
        - rank_ic(CORE27, t)

The target is session-level relative rank IC.

No individual stock return is used directly to fit the regime selector.

## Causal training rule

For decision session D, the selector may use only source sessions t whose entire
5-session alpha outcome matured before D:

    exit_session_t < D

The current session's target and partially matured prior targets are prohibited.

Minimum matured training sessions: 40.

Sessions before 40 matured observations exist are excluded from the primary
selector comparison rather than backfilled.

## Frozen context transform

For every decision D:

- compute mean and population standard deviation of each context variable using
  only the selector's matured training sessions;
- standardize the current D context using those training-only statistics;
- a zero training standard deviation maps that variable to 0 for both train and
  current observation.

No full-sample normalization is allowed.

## Frozen selector model

Ordinary ridge regression with intercept.

Input vector:

    [
      z(nifty500_return_20),
      z(nifty500_realized_vol_20),
      z(breadth_positive_momentum20_fraction)
    ]

Target:

    relative_ic

Ridge penalty:

    lambda = 1.0

No hyperparameter search.

## Frozen session choice rule

For session D:

- if predicted relative_ic > 0, select FUTURES_DELTA;
- otherwise select CORE27.

No tuned threshold.

The selected alpha's existing normalized score becomes the P004 selector score
for every common symbol+ISIN on D.

## Frozen baselines

P004 is compared on the exact same eligible sessions and stock rows against:

1. ALWAYS_FUTURES_DELTA
   - strongest distinct standalone alpha in AB001 P003.

2. STATIC_EQUAL_BLEND
   - 50% CORE27 + 50% FUTURES_DELTA normalized scores.

P004 does not compare against an outcome-tuned blend.

## Primary endpoint

Paired daily mean rank-IC difference:

    P004_SELECTOR - ALWAYS_FUTURES_DELTA

Inference:

- Newey-West;
- lag = 4, matching overlapping 5-session labels.

Primary support requires:

- mean delta > 0;
- two-sided p < 0.05.

## Secondary endpoints

On identical sessions:

- top-decile excess delta vs ALWAYS_FUTURES_DELTA;
- top-minus-bottom spread delta vs ALWAYS_FUTURES_DELTA;
- rank-IC delta vs STATIC_EQUAL_BLEND;
- spread delta vs STATIC_EQUAL_BLEND;
- selector directional accuracy:
  sign(predicted relative_ic) == sign(realized relative_ic);
- fraction of sessions selecting each alpha.

Secondary inference uses Newey-West lag 4.

Secondary endpoints cannot rescue a failed primary endpoint.

## Diagnostics

Report:

- ridge coefficients by decision session;
- predicted relative IC;
- realized relative IC;
- selector choice;
- training sample count;
- training context means/stds;
- coefficient sign stability;
- context distribution by selected alpha.

No post-result coefficient pruning or context-variable removal under P004.

## Interpretation

P004 can establish only whether RG001 context contains historical-development
information about relative efficacy between these two sealed alpha families.

It cannot establish:

- a new stock-level alpha;
- a prospective regime effect;
- a production blender;
- portfolio-level value;
- live-capital readiness.

If P004 is supported, the next step is a separately frozen prospective
regime-conditioned blender or interaction trial.

If P004 fails, RG001 remains usable for risk/portfolio diagnostics without
forcing regime conditioning into AB001.
