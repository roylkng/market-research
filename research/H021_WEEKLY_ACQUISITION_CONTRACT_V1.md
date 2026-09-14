# H021 weekly consensus acquisition contract v1

Status: **FROZEN BEFORE THE FIRST VALID H021 REVISION COHORT**
Frozen: 2026-09-14
Live capital: disabled
Return outcomes opened: no

## Purpose

This contract closes the operational gap between the validated public StockAnalysis acquisition path and the existing immutable H021 capture sealer. It does not change the H021 hypothesis, frozen U001 universe, 28-35 day revision window, analyst-count threshold, EPS-only primary rank, or outcome definition.

The contract is frozen after a source-only full-U001 dry run demonstrated exact target-period and EPS-currency semantic retrieval for 100/100 frozen symbols, and before any valid H021 revision cohort or H021 return outcome exists.

## Frozen source hierarchy

Primary annual expectation fields use the already-frozen source version:

`H021-public-stockanalysis-spgi-plus-trendlyne-secondary-v1`

For unattended primary acquisition:

1. StockAnalysis public NSE forecast pages are the primary acquisition surface.
2. The forecast page must retain the `S&P Global Market Intelligence` provider marker.
3. The frozen NSE symbol remains the H021 identity. Provider-specific symbol aliases may affect only provider URL/page identity resolution and must be explicit in code.
4. StockAnalysis financials pages are queried only when the forecast page does not expose an explicit three-letter financial currency.
5. Public Trendlyne secondary fields remain optional. An unattended primary capture is not blocked merely because profit-growth or target-price diagnostics are unavailable.
6. No authentication, subscription, robots restriction, HTTP access control, rate-limit control, or other provider control may be bypassed.

No current webpage observation is backdated. The H021 observation timestamp is the actual acquisition completion timestamp.

## Frozen target semantics

The first production series remains comparable to the immutable 2026-09-11 full-U001 anchor.

For each frozen symbol, the acquisition target is the exact fiscal period and exact period-ending date sealed in that anchor. Acquisition must not silently roll from FY2027 to FY2028, or otherwise replace a missing target period with a newer forecast period.

A future fiscal-period rollover requires a separately frozen source/version protocol before the first capture using the new target semantics. It cannot be inferred opportunistically from provider layout changes.

## Weekly cadence

The authoritative cadence uses the frozen NSE cash-market calendar at:

`research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json`

A production acquisition may run only after the close of the final frozen NSE session in each Monday-Sunday week.

Therefore:

- a non-session date does not produce a capture;
- an NSE session with a later session in the same week does not produce a capture;
- a holiday-shortened week captures on its last actual session;
- a week containing an `unresolved_special_dates` entry fails closed until that possible special session is resolved and the calendar is reviewed;
- a date outside the frozen calendar coverage fails closed rather than assuming a weekday is a market session.

The current frozen calendar explicitly carries 2026-11-08 as an unresolved special-session date. The workflow must therefore refuse to seal the preceding week from an incomplete calendar rather than assume Friday, 2026-11-06 is the final session.

The existing frozen calendar covers through 2026-12-31. Calendar continuity beyond that date requires a new reviewed calendar snapshot before unattended H021 capture can continue.

## Acquisition-to-capture mapping

Every one of the 100 frozen symbols receives exactly one row. No replacement company or stale carry-forward is permitted.

### `PARTIAL`

A normal StockAnalysis-primary observation is `PARTIAL` when the exact target annual EPS semantics are acquired but one or more optional H021 secondary diagnostics are not acquired by the unattended primary path.

The row may retain:

- exact target fiscal period and period-ending date;
- consensus EPS;
- explicit EPS currency;
- revenue-growth forecast when explicitly parsed;
- analyst count when explicitly parsed;
- StockAnalysis forecast URL;
- source hash/provenance in acquisition evidence.

Profit-growth estimate and target price remain null unless they are explicitly and compatibly acquired under the frozen source hierarchy. Null is not zero or neutral.

### `NO_COVERAGE`

Use when the public provider has no resolvable page for the frozen symbol, or when the exact frozen target period is no longer available on an otherwise valid provider page.

Current forecast values from another fiscal period must not be substituted.

### `SOURCE_BLOCKED`

Use when public retrieval is prevented by robots policy, authentication/access controls, rate limiting, HTTP 401/403/405/429, or a transport failure that prevents a trustworthy observation.

No prior values may be carried forward.

### `IDENTITY_UNRESOLVED`

Use when the retrieved provider page cannot be proven to represent the frozen NSE identity.

No forecast values from the ambiguous page may enter the sealed capture.

### Hard structural failure

Provider-marker removal, an unrecognized/ambiguous annual forecast layout, conflicting explicit currencies, or other structural parser drift aborts the whole capture rather than being converted into a convenient missing row. These conditions can indicate a source-contract change and require review before the experiment continues.

## Source-observed date

If the provider exposes no trustworthy date representing when its consensus snapshot became current, `source_observed_market_date` remains null. The actual prospective evidence boundary is the immutable H021 `captured_at_utc` timestamp. A page access date must not be misrepresented as a provider observation date.

## Raw-source retention boundary

The repository retains source provenance needed to audit acquisition without redistributing provider HTML:

- requested/final URL where available;
- fetch state and HTTP status;
- content byte length;
- SHA-256 of retrieved bytes;
- whether currency fallback retrieval was required;
- parser result or explicit failure class.

Raw StockAnalysis HTML is not committed to the repository by the weekly workflow.

## Sealing boundary

The acquisition engine must derive the 100 frozen identities from the immutable universe/batch contract, populate current observations, validate the complete capture, and pass it to the existing H021 immutable sealer.

The production capture must preserve:

- frozen universe path and Git blob SHA;
- frozen source version;
- frozen protocol/comparison contract paths;
- actual India capture date;
- actual UTC completion timestamp;
- `outcomes_opened=false`;
- `live_capital_allowed=false`.

Any incomplete or structurally invalid acquisition is retained as source evidence where useful, but is not sealed as a valid H021 capture.

## Information firewall

The weekly acquisition path may not consume stock prices, returns, Nifty 500 returns, H013, H019, H020, PF001, valuation, accounting quality, post-capture news, or any H021 outcome.

Source failures and coverage may be debugged using source-only evidence. H021 signal or outcome performance may not be used to change acquisition mappings, source priority, fiscal-period targets, parser tolerances, or capture cadence.
