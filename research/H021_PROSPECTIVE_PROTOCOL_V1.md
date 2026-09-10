# H021 prospective consensus-revision protocol v1

Status: **FROZEN BEFORE H021 RETURN OUTCOMES**
Frozen: 2026-09-11
Live capital: disabled

## Source decision

Historical company-level consensus-revision backtesting is not authorized. The completed source probes did not establish reproducible historical company-level consensus snapshots or a complete dated broker-revision sampling frame. H021 therefore proceeds prospectively.

## Universe

Primary prospective market universe: the existing **frozen 100-company U001 panel drawn from NIFTY 200** at `research/prospective/universes/FY27-Q2-2026-09-06.json`, Git blob `8026e81faee3e913d2fba1dba72d60603b69fa07`. The existing H002 cohort-preparation contract independently confirms that U001 contains 100 companies. The panel was captured before H021 and is independent of analyst-provider success.

H021 does not expand this panel to all 200 NIFTY 200 constituents after observing the source result. A later full-index experiment, if useful, requires a separately frozen universe version.

Every frozen symbol must receive one data state per capture:

- `OBSERVED`
- `PARTIAL`
- `NO_COVERAGE`
- `SOURCE_BLOCKED`
- `IDENTITY_UNRESOLVED`

No failed symbol may be replaced.

## Capture cadence

Capture once per week after the final completed Indian market session of the week. Intended operational cadence is Friday after market close. If Friday is not a completed NSE session, use the week's final completed session where feasible or record `NO_MARKET_SESSION` with calendar evidence.

Each capture is immutable. Corrections create a new version with a reason.

The 100-name panel is processed in two fixed contiguous rank batches of 50. Both are part of one logical weekly capture and neither may be silently omitted.

## Acquisition boundary

Use public browser/search-accessible pages and public or official documents. Do not bypass HTTP 405/429, authentication, subscription controls, robots/access controls, or download restrictions.

A licensed provider may be added only through a new source-version protocol with entitlement and timestamp semantics recorded.

Capture at minimum:

- capture date and timestamp
- symbol and stable identity where verified
- source URL
- source-observed market date/timestamp when visible
- fiscal period
- consensus EPS if explicitly available
- revenue forecast or revenue-growth forecast when explicitly available
- profit/net-income forecast or profit-growth forecast when explicitly available
- analyst count
- consensus target price when explicitly available
- source/data state and retrieval notes

Null means unavailable. It is never converted to zero or neutral.

## Primary revision signal

`eps_revision_30d_pct = 100 * (EPS_current / EPS_prior - 1)`

The prior observation must be an immutable capture 28-35 calendar days earlier, minimizing absolute distance from 30 days. Ties choose the earlier capture. Both observations must refer to the same fiscal period and compatible source-version semantics.

If either EPS value is unavailable or the prior value is zero, the primary signal is `NO_SIGNAL`.

Revenue/profit-growth forecast changes and target-price revisions are secondary diagnostics only. They must not substitute for missing EPS.

## Coverage strata

Analyst coverage is endogenous and is reported explicitly.

- `PRIMARY_COVERAGE`: analyst count >= 5 at both prior and current captures.
- `LOW_COVERAGE_STRESS`: analyst count 2-4 at either capture while both required EPS values are otherwise usable.
- fewer than two analysts: coverage report only.

The >=5 primary threshold is frozen before H021 outcomes and is in the same order as the minimum-coverage conventions used in NSE earnings-revision analysis. It is not optimized on H021 returns.

## Primary selection test

Until a valid 28-35 day revision pair exists, H021 produces no primary long signal.

When the first valid cross-section exists:

1. require `PRIMARY_COVERAGE`
2. compute `eps_revision_30d_pct`
3. rank the valid covered cross-section by EPS revision only
4. evaluate the top decile as the primary long cohort
5. report zero/negative-revision names and the full valid covered cohort as comparators

No H013, H020, RSI, MACD, price momentum, volume, valuation, or accounting-quality variable enters this primary rank.

Predeclared secondary challengers:

- positive revision sign only
- 90-day EPS revision once enough prospective history exists
- change in revenue-growth forecast
- change in profit-growth forecast
- revision breadth if up/down analyst counts become available
- low-coverage stress cohort

Each challenger must be reported separately and cannot silently replace a failed primary result.

## Quality, valuation, momentum, and timing

H019 accounting quality and point-in-time valuation are downstream guardrails/challengers. H013 remains the independent price-momentum hypothesis. H020 remains the downstream timing hypothesis.

Report independently before any ensemble:

- H021 revision alone
- H021 + H019 quality guardrail
- H021 + valuation guardrail
- H013 alone
- H021 + H020 timing as an execution comparison

A downstream overlay cannot rewrite a failed H021 selection result.

## Outcomes

Primary: 60 completed NSE-session excess return versus Nifty 500.
Secondary: 20 completed NSE-session excess return versus Nifty 500.

H021-alone entry proxy: next completed-session open after the capture decision is final and executable. Any H020-timed entry is later and reported separately.

Report median/mean excess, beat rate, raw return, maximum adverse excursion, positive-P&L concentration, coverage failures, and implementation costs for portfolio simulations.

## Information firewall

Before outcomes mature, do not change the primary formula, 28-35 day match rule, >=5 analyst primary stratum, or top-decile rule using those outcomes.

Previously discussed names such as Transrail, Genus Power, Arvind, WABAG, Netweb, and Shaily may be captured but cannot become special-case tuning examples.

## Promotion gates

H021 stays research-only until all of the following are true:

1. at least four prospective monthly-equivalent decision cohorts exist
2. primary coverage supports non-trivial cross-sectional deciles
3. 60-session outcomes have matured for those cohorts
4. primary cohort median Nifty 500 excess is positive
5. mean Nifty 500 excess is positive
6. selected-stock beat rate exceeds 55%
7. performance is not dominated by one company or sector
8. results are compared against prior-60 relative momentum and H013 without changing H021 weights
9. transaction-cost sensitivity does not erase the signal

These are gates, not claims they will pass.
