# H002 prospective specification — H002-UE-v1

## Status

`FROZEN`

This specification governs prospective H002 observations after the first U001 cohort was frozen. It does not rewrite the earlier feasibility experiment in `SPEC.md`.

## Research question

Does a positive seasonal unexpected-earnings signal predict higher subsequent 20-session returns than a negative signal among eligible U001 companies after the immediate earnings reaction?

## Universe

Frozen rule: `U001`.

Current cohort snapshot:

`research/prospective/universes/FY27-Q2-2026-09-06.json`

The cohort is fixed before outcomes. No company enters or leaves H002 because it looks attractive, reports strong results, or moves sharply.

## Signal version

`H002-UE-v1`

Canonical rule file:

`registry/signals/H002-UE-v1.json`

Rule SHA-256:

`24eb8325216e68db8e3f14db440a0f470f9f576a3d1aea034b570812c70686ff`

## Expected EPS

Seasonal-naive expectation:

`expected_eps_t = basic_eps_t_minus_4`

The prior EPS must come from the same reporting quarter and accounting basis, and its source must have been public before the current result.

## Primary signal

```text
unexpected_eps = actual_basic_eps - prior_year_basic_eps
UE = unexpected_eps / price_day_minus_2
```

`price_day_minus_2` is the official close of the second prior NSE trading session relative to the local calendar date of the exchange publication.

## Buckets

- `POSITIVE`: UE > 0
- `ZERO`: UE == 0
- `NEGATIVE`: UE < 0
- `NO_SIGNAL`: any required input is missing, invalid or non-comparable

No quantile thresholds and no winsorization are used in v1.

## Corporate actions

If EPS is not directly comparable because of a split, bonus, rights issue, merger or other share-basis event, H002 produces `NO_SIGNAL` unless a deterministic pre-event adjustment is available and versioned.

## Decision timing

Signal decision timestamp is the exchange publication timestamp of the current result.

Forbidden information includes:

- later earnings-call transcripts,
- post-result brokerage revisions,
- post-result prices,
- future corporate-action data,
- any prior EPS source that was not public before the current filing.

## Execution

Execution remains governed by H002-C (#6), not this gate:

- no event-day trade,
- no first-subsequent-session trade,
- second eligible session open is the planned entry convention,
- 20 trading sessions is the primary holding horizon.

No paper position may be opened merely because this signal code exists.

## Benchmarks

At minimum:

- broad Indian benchmark,
- deterministic sector-matched benchmark where available,
- Nifty 200 Momentum 30 or equivalent simple momentum benchmark.

## Missingness

Every eligible U001 earnings event must appear in the prospective ledger even when the signal is `NO_SIGNAL`. Missing prior EPS, price, accounting comparability or corporate-action state must be reported as a reason rather than silently excluding the company.

## Deferred variants

These are not H002-UE-v1 and require separate registration:

- analyst-consensus surprise,
- standardized SUE using historical forecast-error volatility,
- guidance surprise,
- momentum/valuation overlays,
- LLM interpretation,
- alternative holding horizons.

## Promotion rule

Prospective evidence must remain economically meaningful after benchmark, cost and winner-concentration stress before H002 can be considered promising. `PROMISING` still does not authorize live capital.
