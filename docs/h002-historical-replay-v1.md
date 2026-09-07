# H002 historical replay v1

## Objective

H002-HR001 accelerates learning while the frozen prospective H002-R001 cohort waits for FY27 Q2 filings. It replays the same seasonal-EPS surprise arithmetic on historical NSE evidence without relabeling reconstructed observations as prospective.

Historical replay is supporting evidence only. H002-R001 remains the authoritative forward test and `live_capital` remains false.

## Why a separate replay rule exists

A historical result can be useful and still be contaminated by information that was unavailable at the simulated decision time. The replay therefore has its own frozen rule and explicit evidence mode:

- target and baseline events remain `HISTORICAL_RECONSTRUCTION`,
- no historical event can satisfy the prospective event-mode guard,
- all official publication timestamps are retained,
- baseline revisions are filtered by the historical freeze time,
- corporate actions are evaluated as-of the historical freeze,
- post-freeze share-basis changes cause a skip,
- outcome prices are forbidden during signal construction.

This separation prevents a successful backtest from being misrepresented as forward evidence.

## Freeze convention

The FY27 Q2 prospective expectations were frozen on 6-Sep-2026 for a 30-Sep-2026 quarter end. H002-HR001 preserves that 24-calendar-day lead time.

For each replay quarter:

```text
historical_freeze = target_period_end - 24 calendar days at 23:59:59 Asia/Kolkata
```

Initial quarters:

| Replay quarter | Target period | Baseline period | Freeze |
| --- | --- | --- | --- |
| FY26 Q4 | 31-Mar-2026 | 31-Mar-2025 | 7-Mar-2026 23:59:59 IST |
| FY27 Q1 | 30-Jun-2026 | 30-Jun-2025 | 6-Jun-2026 23:59:59 IST |

The latest matching baseline filing revision that was public at or before the freeze is eligible. A later revision cannot enter the expectation.

## Filing selection

For each company and quarter:

1. Prefer a consolidated target and same-basis prior-year baseline when both exist.
2. Otherwise use a standalone target and same-basis prior-year baseline.
3. Use the first official target filing by exchange timestamp.
4. Use the latest baseline revision available by the historical freeze.
5. Require symbol, period, quarter and accounting-basis identity to match the H002 signal contract.
6. Retain exact source bytes and SHA-256 evidence.

Missing or ambiguous evidence is not imputed.

## Signal

H002-HR001 transports H002-R001 unchanged except for the historical event-mode wrapper:

```text
expected_eps = prior_year_same_quarter_basic_eps * corporate_action_factor
UE = (actual_basic_eps - expected_eps) / price_day_minus_2
```

Buckets remain `POSITIVE`, `ZERO`, `NEGATIVE`, or `NO_SIGNAL`. No historical threshold is fitted.

The price reference is the close of the second NSE trading session strictly before the target filing local date. This price is pre-outcome evidence because it precedes the filing.

## Two-phase anti-leakage execution

### Phase A: signal capture

Permitted inputs:

- frozen cohort definition,
- official target and baseline filing metadata and bytes,
- official publication timestamps,
- corporate actions known by the freeze or target publication,
- official pre-filing reference price,
- official trading calendar.

Forbidden inputs:

- entry price,
- exit price,
- post-filing benchmark returns,
- realized stock return,
- winner/loser labels,
- any outcome-conditioned rule change.

Phase A emits a content-hashed manifest. That manifest must be frozen before Phase B begins.

### Phase B: outcome reconstruction

Only after the Phase-A manifest is fixed:

- enter at the second eligible session open after the filing,
- hold exactly 20 trading sessions,
- exit at close,
- reconstruct Nifty 50 and Nifty200 Momentum 30 benchmark outcomes,
- run the same cost and winner-dependence diagnostics used by the prospective harness.

## Initial cohort and survivorship bias

The first replay uses the already-frozen 100-company FY27 Q2 U001 cohort as a **transport test**. This answers whether the mechanics and signal show useful historical separation on companies that are in the current cohort.

It is not unbiased historical validation because membership is known as of September 2026. The output must carry:

`SURVIVORSHIP_SENSITIVE_FIXED_2026_COHORT`

A second replay must reconstruct point-in-time historical universes before H002 historical evidence can be treated as validation-quality evidence.

## Point-in-time follow-up

The stronger replay will use the Nifty 200 membership and non-financial selection information available at each historical cohort freeze. It must not backfill 2026 membership into earlier periods.

The target hierarchy is:

1. exact historical Nifty 200 membership and ranking evidence if archived,
2. deterministic historical constituent snapshot with verifiable effective date,
3. if historical FFMC cannot be reconstructed without inference, use a separately registered historical universe rule rather than approximating U001 silently.

## Interpretation

Historical replay can reject H002 quickly if the sign relationship repeatedly fails across sufficiently large, independently reconstructed quarters. Positive historical evidence can increase confidence and guide sample-size planning, but it cannot replace the prospective FY27 Q2 test.

No live capital is authorized by H002-HR001.
