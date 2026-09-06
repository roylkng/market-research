# H002 prospective signal v1

## Status

`H002-R001` is **FROZEN for prospective paper testing**.

This does not mean H002 is validated. The historical feasibility result remains inconclusive. Freezing means only that the prospective experiment now has a fixed rule that may not be edited after outcomes begin.

## Why this model

The feasibility pilot showed that raw revenue/profit growth is not the same thing as information surprise. Reliable timestamped analyst-consensus data would be preferable, but the project does not currently have a licensed point-in-time consensus feed.

The first prospective test therefore uses a mechanical expectation available from public filings:

```text
expected_eps = prior_year_same_quarter_basic_eps * corporate_action_factor
```

The primary signal remains the literature-style price-normalized unexpected earnings measure:

```text
UE = (actual_basic_eps - expected_eps) / price_day_minus_2
```

No momentum, valuation, management-guidance score, LLM judgement, or optimized factor weight is part of H002-R001.

## Baseline requirements

The baseline filing must:

- belong to the same symbol,
- use the same accounting basis as the target event,
- represent the same reporting quarter exactly one year earlier,
- have an availability timestamp verified independently of when MarketLab later downloaded it,
- have been available before the current filing publication time.

Historical-reconstruction capture time is never accepted as historical availability.

If prior-year basic EPS is missing, the event becomes `NO_SIGNAL`. MarketLab does not infer or impute EPS.

## Corporate actions

EPS comparability can be affected by splits, bonus issues and similar actions. The expectation therefore requires:

- an explicit `corporate_action_factor`, and
- a non-empty `corporate_action_version` identifying the information set used.

The default economic factor may be 1.0, but the version must still be explicit. Future corporate-action normalization logic must be point-in-time and versioned.

## Price reference

H002-R001 requires a `price_day_minus_2` reference. H002-B only enforces that:

- it belongs to the same symbol,
- it is positive when present,
- its timestamp is strictly before the current filing publication,
- it carries a corporate-action version.

H002-C will define the exchange-calendar logic that proves the price is actually the close of the second eligible trading session before the event. H002-B does not open paper positions.

## Buckets

There is no winsorization and no learned threshold:

```text
UE > 0  -> POSITIVE
UE = 0  -> ZERO
UE < 0  -> NEGATIVE
missing required signal input -> NO_SIGNAL
```

Zero is not silently merged into the negative bucket.

## Leakage guards

The scorer rejects:

- a current event that is not marked `PROSPECTIVE`,
- an expectation timestamp at or after current filing publication,
- baseline evidence first available at or after current filing publication,
- a price timestamp at or after current filing publication,
- scoring before the current filing publication,
- symbol, period, quarter or accounting-basis mismatches.

These checks are intentionally strict. Losing an observation is preferable to silently introducing future information.

## Frozen-rule hash

The canonical H002-R001 contract is stored at:

`registry/h002_signal_rule.yaml`

The declared SHA-256 is validated by the test suite and by `make validate`. A material rule change must create a new rule/version rather than silently changing H002-R001.

## What is not tested yet

This stage does not answer whether H002 makes money. It does not yet provide:

- second-session paper entry,
- 20-session exit,
- market-calendar handling,
- benchmark windows,
- transaction-cost simulation,
- prospective return statistics.

Those belong to H002-C and H002-D after this rule is merged unchanged.
