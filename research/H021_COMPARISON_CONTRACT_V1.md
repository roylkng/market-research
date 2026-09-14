# H021 prospective comparison contract v1

Status: **FROZEN BEFORE THE FIRST VALID H021 REVISION COHORT**
Frozen: 2026-09-14
Live capital: disabled
Return outcomes opened: no

## Purpose

This contract translates the already-frozen H021 prospective protocol into fail-closed executable comparison rules. It does not change the H021 hypothesis, selection variable, analyst-count threshold, comparison window, universe, or outcome definition.

The first full U001 consensus anchor is the immutable 2026-09-11 capture. No H021 primary revision signal exists until a later compatible full-panel capture falls inside the frozen 28-35 calendar-day window.

A source-semantics audit completed on 2026-09-14, before any valid revision cohort, confirmed that all 100 rows in the Sep 11 anchor already retain both `period_ending` and `eps_currency`. The comparison contract therefore uses those existing point-in-time fields rather than reconstructing or backfilling the anchor.

## Frozen comparison pair

A prior/current capture pair is eligible for the primary H021 comparison only when all of the following are true:

1. the current capture is 28-35 calendar days after the prior capture;
2. when more than one compatible prior exists, choose the capture with minimum absolute distance from 30 calendar days;
3. if two compatible priors are equally distant from 30 days, choose the earlier prior capture;
4. both captures use the same `source_version`;
5. both captures identify the same frozen universe path and Git blob SHA;
6. both captures contain exactly the same frozen symbol set, with no omission, replacement, or substitution;
7. every frozen symbol has exactly one observation row in each capture.

A pair outside these conditions is not a weaker H021 comparison. It is ineligible for the primary experiment.

## Row-level primary eligibility

For a symbol inside an eligible pair, the primary EPS-revision signal exists only when:

- prior and current observations refer to the same fiscal-period label;
- prior and current observations refer to the same explicit `period_ending` date;
- both observations contain explicit consensus EPS and prior EPS is non-zero;
- both EPS observations use the same explicit three-letter `eps_currency`;
- analyst count is at least 5 at both captures;
- the primary EPS observation remains within a compatible provider/source family.

No FX conversion is introduced into the primary signal. H021 is a within-company expectation-revision experiment, so exact same-currency comparison is sufficient and avoids adding an undeclared market variable.

A provider-domain change is treated as an incompatible EPS source for the primary comparison unless a separately frozen source-version protocol establishes equivalence before that comparison is opened.

A fiscal-period rollover, changed period endpoint, changed EPS currency, or changed provider family is retained explicitly as `NO_SIGNAL`. It must not disappear through an inner join or be repaired by conversion or inference.

## Explicit primary reason codes

Every frozen symbol receives one primary status:

- `ELIGIBLE`
- `FISCAL_PERIOD_MISMATCH`
- `EPS_REVISION_UNAVAILABLE`
- `PERIOD_END_UNAVAILABLE`
- `PERIOD_END_MISMATCH`
- `EPS_CURRENCY_UNAVAILABLE`
- `EPS_CURRENCY_MISMATCH`
- `EPS_SOURCE_CHANGED`
- `ANALYST_COVERAGE_LT_5`

This makes denominator loss observable rather than silently dropping names that fail the primary data contract.

## Primary revision and rank

For an eligible symbol:

`eps_revision_pct = 100 * (EPS_current / EPS_prior - 1)`

A numeric primary EPS revision is not computed when fiscal period, period endpoint, EPS currency, or provider-family semantics are incompatible. This prevents a clean-looking but meaningless percentage from entering diagnostics or ranks.

The primary cross-sectional rank uses this value only. No price return, H013 momentum, H020 timing state, accounting-quality variable, valuation variable, target price, revenue forecast, profit-growth forecast, FX conversion, or discretionary narrative may break a rank tie or alter the primary score.

The primary long cohort is the top decile of eligible rows. The nominal count is `ceil(0.10 * eligible_count)`, with a minimum of one when at least one eligible row exists. If multiple names tie at the cutoff EPS revision, all names at that exact cutoff are included. This preserves an EPS-only primary rule instead of injecting an undeclared tie-breaker.

Secondary revenue, profit-growth, and target-price changes remain diagnostics or separately versioned challengers. They cannot substitute for missing primary EPS revision.

## Artifact integrity

The 2026-09-11 full U001 anchor is retained as a gzip-compressed JSON payload plus manifest. Comparison tooling must therefore support the sealed `.json.gz` artifact directly.

If snapshot-level identity fields are absent from an older sealed payload but present in its immutable sibling manifest, the comparison loader may enrich the in-memory representation from that manifest. It must fail on any payload/manifest identity disagreement and must never rewrite the original artifact.

The frozen anchor identity is:

- capture: `research/prospective/h021/captures/2026-09-11-full-u001-v1.json.gz`
- universe: `research/prospective/universes/FY27-Q2-2026-09-06.json`
- universe Git blob: `8026e81faee3e913d2fba1dba72d60603b69fa07`
- source version: `H021-public-stockanalysis-spgi-plus-trendlyne-secondary-v1`
- explicit `period_ending`: 100/100 rows
- explicit `eps_currency`: 100/100 rows

## Earliest primary comparison

The first scheduled Friday inside the 28-35 day window after the 2026-09-11 anchor is **2026-10-09**, exactly 28 calendar days later.

Captures before that date remain valuable prospective observations, source-continuity evidence, and possible priors for later cohorts, but they cannot be compared with the 2026-09-11 anchor as a primary H021 30-day revision cohort unless they satisfy the frozen 28-35 day rule.

## Scientific boundary

This contract is frozen before any valid H021 primary revision cohort or H021 return outcome exists. The period-ending and EPS-currency clarification was added on 2026-09-14 after direct-source feasibility work exposed the distinction, while the immutable Sep 11 anchor already contained both fields for every company. No result was opened or reconstructed to make this change.

No H021 return, benchmark return, price path, H013 score, H019 quality state, H020 timing state, PF001 result, or live-capital decision may influence these comparison rules. Live capital remains disabled.
