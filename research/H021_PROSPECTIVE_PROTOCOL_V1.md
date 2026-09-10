# H021 prospective consensus-revision protocol v1

Status: **FROZEN BEFORE H021 RETURN OUTCOMES**
Frozen: 2026-09-11
Live capital: disabled

## Decision after source feasibility

Historical company-level consensus-revision backtesting is not authorized. The automated Trendlyne consensus probe captured only 1/8 frozen source-test names and did not verify historical point-in-time EPS consensus snapshots. A separate automated broker-report source probe also failed to retrieve explicit revision text from its frozen pages. Browser/search indexing can expose current summaries and some dated report excerpts, but that is not a complete historical sampling frame.

Therefore H021 proceeds prospectively. No later discovery of a convenient historical page may be inserted into the prospective evidence as if it had been available today.

## Universe

Primary prospective market universe: the existing frozen U001 / FY27-Q2 NIFTY 200 company universe captured on 2026-09-06. H021 does not create a new company universe from successful data-provider lookups.

For every scheduled capture, each frozen symbol must end in one of these data states:

- `OBSERVED`: required public consensus fields were captured.
- `PARTIAL`: some consensus fields were captured but primary EPS revision inputs are incomplete.
- `NO_COVERAGE`: source explicitly indicates no analyst consensus.
- `SOURCE_BLOCKED`: coverage may exist but the permitted browser-access path could not retrieve it.
- `IDENTITY_UNRESOLVED`: company/source mapping is ambiguous.

No failed symbol may be replaced by another company.

## Capture cadence

Capture once each week after the final Indian market session of the week. The intended operational time is Friday after market close. If Friday is not a completed NSE session, capture after the week's final completed NSE session or record `NO_MARKET_SESSION` and retain the calendar evidence.

Each capture is immutable. Corrections create a new version with a reason and never overwrite the original observation silently.

## Permitted acquisition path

Use public browser/search-accessible pages and official/public source documents. Do not bypass HTTP 405/429 responses, authentication, subscription controls, robots/access controls, or download limits.

Trendlyne may be used for public indexed consensus summaries. A licensed provider may replace or supplement it only in a new source-version protocol with entitlement recorded.

Store at minimum:

- capture date in Asia/Kolkata
- symbol and stable identity where verified
- source URL
- source-observed market timestamp/date when visible
- fiscal period
- consensus EPS if explicitly available
- revenue forecast or revenue-growth forecast when explicitly available
- profit/net-income forecast or profit-growth forecast when explicitly available
- analyst count
- consensus target price when explicitly available
- source/data state
- retrieval notes and conflicts

Null means unavailable. Null is never converted to zero or neutral.

## Primary revision signal

The primary H021 signal remains the change in same-fiscal-period consensus EPS over approximately 30 calendar days:

`eps_revision_30d_pct = 100 * (EPS_current / EPS_prior - 1)`

The prior observation is selected from immutable captures 28-35 calendar days earlier, minimizing absolute distance from 30 days. Ties choose the earlier capture. Both observations must refer to the same fiscal period and source-version semantics.

If either EPS value is unavailable or zero, the primary signal is `NO_SIGNAL`.

Public headline profit-growth or revenue-growth forecast changes are retained as secondary diagnostics only. They must not substitute for missing EPS in the primary test.

## Coverage strata

Analyst coverage is endogenous and may itself carry information. To prevent changing the rule after seeing returns, H021 reports two strata separately:

- `PRIMARY_COVERAGE`: analyst count >= 5 at both the prior and current captures.
- `LOW_COVERAGE_STRESS`: analyst count 2-4 at either capture while both required consensus values are otherwise usable.

Names with fewer than two analysts do not enter the primary or low-coverage portfolio tests but remain in the coverage report.

The >=5 primary threshold is chosen before outcomes using the same order of magnitude as NSE corporate-earnings revision studies that use at least five analysts for covered-company samples. It is not optimized on H021 returns.

## Selection rule to freeze once the first 30-day revision exists

Until the first valid 28-35 day revision pair exists, H021 produces no long signal and no ranking based on return outcomes.

At that point, the initial test is deliberately simple:

1. require `PRIMARY_COVERAGE`;
2. compute `eps_revision_30d_pct`;
3. rank the valid covered cross-section by this revision only;
4. evaluate the top decile as the primary long cohort;
5. report zero/negative revision names and the full valid covered cohort as comparators.

No H013, H020, RSI, MACD, price momentum, support/resistance, volume, valuation or accounting-quality variable enters the primary H021 rank.

Secondary predeclared challengers, evaluated separately rather than substituted for the primary result:

- positive revision sign only;
- 90-day EPS revision once enough prospective history exists;
- change in revenue-growth forecast;
- change in profit-growth forecast;
- revision breadth if upward/downward analyst counts become available;
- low-coverage stress cohort.

## Quality and valuation overlays

H019 accounting quality and point-in-time valuation are downstream challengers/guardrails. They are not allowed to rescue a failed primary H021 test.

Once source-faithful inputs exist, report at least:

- H021 revision alone;
- H021 + H019 quality guardrail;
- H021 + valuation guardrail;
- H021 + H020 timing, only as a downstream execution comparison;
- H013 separately and, only after independent evidence, H021 + H013.

## Outcomes

Primary outcome: 60 completed NSE-session excess return versus Nifty 500.
Secondary outcome: 20 completed NSE-session excess return versus Nifty 500.

Entry proxy for H021-alone historical/prospective evaluation: next completed-session open after the capture decision becomes final and executable. H020, if used, gets its own later entry and must be reported separately.

Report median and mean excess return, beat rate, maximum adverse excursion, raw return, positive-P&L concentration, missed/unavailable observations and implementation costs for portfolio simulations.

## Information firewall

Before a capture's 20/60-session outcomes mature, do not alter the frozen primary revision formula, the 28-35 day matching rule, the >=5 analyst primary-coverage stratum, or the top-decile primary cohort using those outcomes.

Previously discussed names including Transrail, Genus Power, Arvind, WABAG, Netweb and Shaily may be observed prospectively but cannot be used as special-case tuning examples.

## Promotion rule

H021 remains research-only until:

1. at least four prospective monthly-equivalent decision cohorts exist;
2. primary coverage is sufficient to form non-trivial cross-sectional deciles;
3. 60-session outcomes have matured for those cohorts;
4. the primary revision cohort shows positive median Nifty 500 excess return;
5. mean Nifty 500 excess return is positive;
6. selected-stock beat rate exceeds 55%;
7. performance is not dominated by one company or one sector;
8. the result is compared against prior-60 relative momentum and H013 without changing H021 weights;
9. transaction-cost sensitivity does not erase the signal.

These are promotion gates, not a claim they will pass.
