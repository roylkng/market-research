# H018-v1 retirement

Recorded: 2026-09-09

Status: **RETIRED_UNEVALUABLE_FROZEN_COVERAGE_FAIL**

Live capital: **DISABLED**

## Frozen experiment reached its first selection boundary

After resolving the historical official-source problems without changing H018-v1 research semantics, workflow run `34333669674` completed the entire frozen market calendar:

- 1,308 calendar days classified;
- 879 fully sourced equity + Nifty/CNX 500 sessions;
- 426 confirmed no-session days;
- 3 explicitly retained equity sessions with unavailable benchmark rows (`2014-12-15`, `2015-03-12`, `2015-07-08`);
- 882 total equity trading sessions;
- zero unresolved market dates;
- zero market parse errors, source mismatches, fetch failures, or hard timeouts.

All five frozen H018 outcome entry/exit endpoints have real retained benchmark rows. Corporate-action acquisition also completed across 43 monthly source chunks.

## Frozen stop condition

H018-v1 uses the previously frozen point-in-time company-candidate function and requires at least 300 eligible companies at every decision cohort.

On the second decision cohort, `2015-05-29`, the fully reconstructed point-in-time company universe contained **298 eligible companies** after the frozen identity, history, liquidity, and corporate-action screens.

The runner therefore failed closed before selecting any H018 portfolio:

`ValueError: H016 requires >=300 point-in-time companies on 2015-05-29; found 298`

This is the same >=300 coverage requirement already encoded in H018-v1. The fact that the inherited helper raises first does not change the H018 contract.

## Outcome-blindness state

No H018-v1 company-selection or return outcome was produced:

- no `point-in-time-selections.json`;
- no `challenge-summary.json`;
- no `selected.csv`.

The retained partial artifact contains only source/calendar diagnostics and manifests. Therefore there is no H018 return result to interpret as positive or negative.

## Decision

Do **not** lower the minimum from 300 to 298, delete a session, relax liquidity/history requirements, or otherwise modify H018-v1 to make this cohort pass. The pre-outcome promotion audit explicitly required H018-v1 to be retired if its original frozen challenge failed rather than rescued after observing a blocker.

H018-v1 is retired as **unevaluable under its frozen coverage contract**.

This result does not prove that low volatility lacks predictive value in India. It proves only that this exact H018-v1 historical challenge cannot satisfy its predeclared coverage requirement on the reconstructed company-only universe.

## Research implication

The next research branch should be orthogonal rather than another low-volatility threshold variant. Priority shifts to a transparent long-horizon fundamental-quality / fundamental-inflection company-selection hypothesis using point-in-time filings, with independent quality-factor and broad-company comparators and a frozen historical holdout before outcome access.
