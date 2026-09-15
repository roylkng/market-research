# H020-v2 adverse-shock challenger

Status: **FROZEN CHALLENGER AFTER 2026-09-15 DESIGN CASE, BEFORE FORWARD VALIDATION**

Live capital: disabled.

## Purpose

H020-v1 is preserved unchanged. H020-v2 tests one additional entry-timing proposition: a strong trailing trend should not trigger an immediate paper entry when the latest completed session contains a materially adverse stock-specific shock.

September 15, 2026 is explicitly design-influenced evidence for this challenger and cannot validate H020-v2.

## Frozen shock rule

Using only completed sessions available at the decision cutoff:

- `stock_return_1d` = latest stock adjusted-close return;
- `benchmark_return_1d` = latest benchmark adjusted-close return;
- `relative_return_1d` = stock return minus benchmark return;
- `prior_relative_vol_20d` = sample standard deviation of the preceding 20 daily relative returns, excluding the latest session;
- `shock_threshold` = `max(2.0 percentage points, 1.5 * prior_relative_vol_20d)`.

`adverse_relative_shock_v2 = true` only when:

1. the stock's latest one-day return is negative; and
2. the latest relative return is less than or equal to `-shock_threshold`.

If H020-v1 says `PAPER_ENTRY_ELIGIBLE_*` and this shock flag is true, H020-v2 changes the action only to `WAIT_SHOCK_CONFIRMATION`.

H020-v2 never upgrades a non-entry v1 action. It does not alter H020-v1's market-regime, trend, reversal, extension, RSI, volume, or score calculations.

## Why volatility-scaled

A fixed percentage-drop veto would treat stocks with very different normal volatility as equivalent and would be easy to overfit to the September 15 design case. The 1.5-sigma component scales the threshold to the stock's recent idiosyncratic volatility, while the 2-point floor prevents immaterial low-volatility deviations from blocking entries.

The latest session is excluded from the volatility estimator so the shock does not inflate its own denominator.

## Forward comparison

From the next completed NSE session after this challenger is frozen, retain both H020-v1 and H020-v2 decisions. Compare:

- entry count and deferred-entry count;
- next-session and 5/20-session stock return;
- Nifty-relative return over the same windows;
- adverse excursion after entry;
- cases where v2 deferred a v1 entry and whether later confirmation improved execution.

No H020-v2 threshold may be changed using September 15 outcomes or later outcomes without creating another versioned challenger.

Yahoo Finance remains exploratory input for H020 current screens. It is not exchange-certified validation evidence. Research only.
