# H002 seasonal unexpected-earnings signal v1

## Purpose

H002 tests whether unexpected quarterly earnings drift into Indian equity prices after the immediate announcement reaction.

This document freezes the first prospective signal before future cohort returns accumulate.

## Signal identity

- signal version: `H002-UE-SIGN-v1`
- expectation model: `seasonal_naive_same_quarter_basic_eps_v1`
- primary horizon: 20 trading sessions
- live capital: disabled

## Expected EPS

The expected EPS for quarter `t` is the **basic EPS from the same reporting quarter and same accounting basis exactly one year earlier**.

Formally:

```text
expected_basic_eps_t = basic_eps_(t-4)
```

The prior EPS must come from a source that was public before the current earnings filing. The current filing's newly presented comparative column is not used as the historical expectation merely because it is convenient. This avoids allowing current-period restatements or presentation changes to rewrite what was knowable before the event.

## Unexpected earnings

```text
UE = (actual_basic_eps - expected_basic_eps) / price_day_minus_2
```

`price_day_minus_2` is the stock closing price from the second eligible trading session before the earnings publication. H002-B accepts a provenance-bearing price observation but does not decide the trading calendar. That deterministic calendar/price construction belongs to H002-C.

## Signal buckets

No optimized threshold is used.

- `POSITIVE`: UE > 0
- `NEGATIVE`: UE < 0
- `ZERO`: UE == 0
- `NO_SIGNAL`: a required input is unavailable or not safely comparable

Zero is not silently grouped with negative earnings surprise.

## No-signal conditions

The signal returns `NO_SIGNAL`, rather than inventing an input, when any required economic input is unavailable, including:

- prior-year same-quarter EPS missing,
- actual or expected basic EPS missing,
- original publication timestamp unavailable,
- day-minus-2 close unavailable or non-positive,
- price timestamp unavailable,
- EPS per-share basis unresolved,
- EPS basis versions differ,
- price basis version unavailable.

Identity/time contradictions are hard errors rather than `NO_SIGNAL`, including:

- symbol mismatch,
- consolidated/standalone mismatch,
- quarter mismatch,
- prior reporting period not exactly one year earlier,
- expected EPS source published after the current filing,
- decision timestamp before the current filing,
- supplied day-minus-2 price timestamp at or after the current filing.

## Corporate actions

EPS values can become incomparable after splits, bonuses or other share-basis changes. H002-B therefore requires both EPS observations to carry the same non-empty `eps_basis_version`.

The first prospective implementation must not guess corporate-action normalization. If the basis cannot be established deterministically, the event is `NO_SIGNAL` until a separately versioned normalization layer exists.

## Analyst consensus

Timestamped analyst consensus would be a distinct and potentially stronger expectation model, but reliable historical/prospective consensus coverage is generally commercial. H002 v1 does not depend on a premium source.

If consensus data is later licensed and captured before results, it must be evaluated as a separate signal version/hypothesis variant. Its performance cannot be silently blended into H002-UE-SIGN-v1.

## Point-in-time contract

For every scored event the ledger must preserve:

- actual EPS and source event/version,
- expected EPS and prior source event/version,
- publication timestamps for both,
- EPS basis version,
- day-minus-2 close, timestamp, source and basis version,
- signal/expectation version,
- decision timestamp,
- UE and bucket or explicit no-signal reasons.

Historical reconstruction can populate prior-year information before prospective launch, but its original publication timestamp must be source-grounded. Reconstruction capture time is never substituted for historical publication time.

## What H002-B does not do

- no paper entry or exit,
- no momentum or valuation overlay,
- no sector or regime filter,
- no LLM subjective adjustment,
- no analyst-consensus substitution,
- no winsorization,
- no optimized threshold,
- no live capital.
