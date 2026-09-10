# H021: Forward expectation revision with quality confirmation

Status: **FROZEN PROSPECTIVE DESIGN. RETURN OUTCOMES UNOPENED.**
Created: 2026-09-11
Live capital: disabled

## Question

Do upward changes in point-in-time forward earnings expectations predict subsequent 20- and 60-session excess returns in covered Indian equities, and does independently measured accounting quality improve that signal?

H021 is deliberately separate from price momentum and entry timing. Its primary signal may not use stock returns, moving averages, RSI, MACD, volume, support/resistance, H013 scores, or H020 action states.

## Motivation

Earlier project evidence rejected raw accounting growth as a sufficient predictor. H009's accounting rank failed, while its predeclared prior-60-session relative-momentum comparator was materially stronger. H013 later achieved a historical challenge pass. H020 now addresses current entry timing.

The missing independent question is whether the market underreacts to **changes in forward expectations**, not merely to reported growth or current price momentum.

External design evidence available before H021 outcomes are opened includes NSE corporate-earnings reviews that track LSEG/IBES consensus revisions, public Trendlyne documentation of Indian analyst estimates/revisions, and academic evidence from another Asian equity market that motivates testing revision changes. None of that establishes that H021 works in India.

## Architecture boundary

- H019: point-in-time accounting observations and later quality guardrails.
- H021: expectation-change stock-selection hypothesis.
- H013: independent price-momentum/regime hypothesis.
- H020: downstream entry-timing/execution hypothesis.

No H013 or H020 variable can enter the primary H021 score. H019 quality cannot rescue a failed H021 primary result. A later ensemble is permitted only after components have independent evidence.

## Source decision

Historical company-level consensus revision backtesting is **not authorized** by the completed source probes. H021 therefore proceeds prospectively from the first immutable capture on 2026-09-11. See `research/H021_SOURCE_FEASIBILITY_RESULT_V1.md` and `research/H021_PROSPECTIVE_PROTOCOL_V1.md`.

## Primary signal

Once two same-period captures approximately 30 calendar days apart expose valid consensus EPS:

`eps_revision_30d_pct = 100 * (consensus_eps_current / consensus_eps_prior - 1)`

If either same-period EPS estimate is absent or the prior value is zero, the primary signal is `NO_SIGNAL`. Revenue/profit-growth forecast changes and target-price revisions are diagnostics or separately versioned challengers, not substitutes for missing EPS.

## Outcomes

Primary horizon: 60 completed NSE sessions.
Secondary horizon: 20 completed NSE sessions.

Report raw return, Nifty 500 excess return, sector-relative excess where a frozen mapping exists, beat rate, median/mean excess, maximum adverse excursion, positive-P&L concentration, missing coverage, and implementation costs for portfolio simulations.

H021-alone and any later H021+H020 execution overlay must be reported separately.

## Scientific guardrails

- prospective immutable capture history only unless a later source protocol independently establishes genuine historical snapshots
- frozen market universe independent of provider success
- explicit no-coverage/source-blocked states
- same fiscal period across revision pairs
- no current-constituent substitution for missing companies
- no return outcomes used to tune capture rules, analyst-count thresholds, revision windows, or selection thresholds
- discussed names such as Transrail, Genus Power, Arvind, WABAG, Netweb, and Shaily may be observed but cannot become special-case tuning examples
- live capital remains disabled until independent prospective evidence exists
