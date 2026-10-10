# H021-P006: verified NSE calendar gate before 20/60-session outcomes

Status: outcome-blind calendar readiness only. Prepared 10 October 2026 IST. Portfolio and live capital disabled.

## Why this correction is necessary

The original, immutable H021-P003 observational next-open cohort is scheduled for 12 October 2026. The hypothesis requires exactly 20 completed NSE sessions for its secondary outcome and 60 completed NSE sessions for its primary outcome.

The exact frozen NSE cash-market calendar (NSE-CM-FY27Q2-v1) records 8 November 2026 as unresolved special-session date, corresponding to Diwali Muhurat trading, and contains no actual verified special-session open/close timings.

It would be invalid to declare 9 November 2026 the final 20-session exit merely by counting ordinary weekdays. Depending on the officially verified treatment of the 8 November Muhurat session, the 20-session date may differ. This is NOT a post-hoc timing choice.

The frozen calendar ends 31 December 2026. It contains only 55 provisional completed sessions from the expected 12 October entry, whereas the primary horizon requires 60. At least five more sessions must be sourced, and that minimum could change once the special session is resolved.

## Executable fail-closed implementation

- Module: src/marketlab/h021_horizon_readiness.py
- CLI: scripts/check_h021_horizon_readiness.py
- Regression tests: tests/test_h021_horizon_readiness.py
- Input: original first H021-P003 intent and original source-hashed frozen NSE 2026 calendar, with all original H021 comparison and universe ancestry verified before calculation.

The readiness result marks BOTH horizons BLOCKED. For 20 sessions it reports the 9 November weekday-only candidate as NOT VERIFIED, with 8 November's unresolved special session as a blocker. For 60 sessions it emits no exit date, records the same special-session blocker, and separately requires an official 2027 calendar extension.

The result explicitly retains the absence of any observed future stock prices, benchmark return, verified share-adjustment or capital eligibility.

A strict consumer must call require_horizon_calendar_ready and may not read a guessed exit session when the readiness state is BLOCKED. New outcome evaluation is prohibited until the official calendar evidence is verified and the scientific input amended under a separately versioned, prospectively documented calendar correction.

## Scientific invariants

The original 28-to-35-day EPS comparison, 100-name U001 universe, 10 H021 selected identities, 12 October entry proxy, primary 60-session horizon, secondary 20-session horizon, Nifty 500 benchmark family and prospective selection protocol are UNCHANGED.

No prior record or prospective return is recomputed, no guessed 2027 dates are inserted and no market price is fetched.

This is infrastructure/readiness verification only, not an alpha trial, not a portfolio change, and not evidence for 50 percent annualized returns.

## How to reproduce

    python scripts/check_h021_horizon_readiness.py
    pytest -q tests/test_h021_horizon_readiness.py

To require a currently verified 20-session exit, the following command intentionally exits with an error:

    python scripts/check_h021_horizon_readiness.py --require-horizon 20

Source-data correction requires a new independently sourced calendar version and revalidation. The original frozen 2026 calendar must remain immutable.
