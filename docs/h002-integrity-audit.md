# H002 input-integrity audit, 6 September 2026

## Scope

This patch hardens the existing H002-R001 implementation. It does not change the
frozen economic rule, universe, thresholds, expected-EPS model or holding period.
The signal remains prior-year same-quarter basic EPS adjusted by an explicit
corporate-action factor, with surprise divided by the reference share price.
H002 remains unvalidated and live capital remains disabled.

## Defects addressed

1. A filing could previously be scored after exchange publication but before its
   recorded local capture. Scoring now requires both timestamps to be reached.
2. Non-finite numeric inputs could pass comparisons or produce non-finite outputs.
   For example, an infinite reference price could produce a ZERO surprise bucket.
   EPS, factors, prices and computed outputs must now be finite. Booleans and
   numeric strings are not accepted as financial numbers. Output overflow and
   nonzero values underflowing to zero are errors, not trading signals.
3. The original expectation identity omitted baseline and expected EPS values.
   The scorer also trusted modified expectation payloads. The identity now covers
   every expectation field except the identity itself, and the scorer recomputes
   the frozen EPS arithmetic and checks status consistency.
4. A price reference could have a trading date inconsistent with its timestamp,
   or an empty source. The scorer now validates the exchange-local date using
   Asia/Kolkata, requires a non-empty source and rejects same-day references.

## Expectation artifact schema 2

New expectations use schema_version 2 and a complete-payload digest. The economic
model version remains seasonal_same_quarter_basic_eps_v1 and the rule remains
H002-R001. The frozen registry rule and its hash are unchanged.

Schema 1 expectations are not silently accepted or relabelled. Retain any old
artifacts for audit. A replacement prospective expectation must be created from
verified evidence before the target filing is published. An expectation rebuilt
after publication cannot be promoted into prospective evidence by backdating it.

## Regression coverage

The added synthetic model-level tests cover capture boundaries, invalid numbers,
output overflow and underflow, altered payloads, unknown contracts, recomputed
arithmetic, price-date consistency, missing values and valid zero/negative EPS.
The pre-existing tests remain responsible for exercising parsed filing fixtures.

## Explicit remaining limits

A digest detects inconsistent payload changes. It is not proof that a source is
true or that an expectation was actually retained before publication. Source-byte
verification and an immutable expectation-capture ledger remain necessary.

Exchange-local date consistency does not prove that the price is the close of the
second eligible trading session before the event. H002-C must supply the exchange
calendar, validated price window, deterministic paper entry and exit, and the
corresponding no-trade states. Corporate-action normalization still requires
independently verified evidence, not merely a non-empty version label.

This audit supplies no new return observations, profitability result or investment
recommendation. Historical reconstructions remain separate from prospective data.
