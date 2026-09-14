# H021 StockAnalysis direct source probe result v1

Recorded: 2026-09-14
Status: **DIRECT PRIMARY PAGE RETRIEVAL FEASIBLE. PARSER AUTOMATION NOT YET AUTHORIZED.**
Live capital: disabled
Return outcomes opened: no

## Question

Can the public StockAnalysis NSE forecast pages used by the 2026-09-11 H021 anchor be retrieved reproducibly from GitHub Actions, at low rate, without bypassing robots or other access controls?

A second source-integrity question was added before any H021 revision cohort exists: did the immutable Sep 11 anchor retain enough EPS basis information to distinguish companies whose StockAnalysis financial forecasts use different currencies?

## Frozen probe

Configuration: `research/prospective/h021/stockanalysis-direct-probe-v1.json`

Final retained run: GitHub Actions `34820310915`, attempt 1.

Anchored report: `reports/h021-stockanalysis-direct-probe/run-34820310915-attempt-1.json`

The five frozen direct-retrieval symbols were:

- RELIANCE
- INFY
- TCS
- M&M
- NESTLEIND

The probe used a transparent research user agent, fetched `https://stockanalysis.com/robots.txt` first, checked each forecast URL against the returned robots policy, slept 3 seconds between requests, performed no retries intended to bypass blocking, and retained response hashes rather than raw provider pages.

## Direct retrieval result

Robots retrieval returned HTTP 200. All five frozen forecast URLs were permitted by the observed robots policy and returned HTTP 200 from `stockanalysis.com`.

All 5/5 pages also contained:

- the expected `NSE:<symbol>` identity marker
- `Financial Forecast`
- `EPS Forecast`
- `Revenue Forecast`
- `No. Analysts`
- `S&P Global Market Intelligence`

Decision: **direct primary page retrieval is feasible for the frozen probe cohort.**

This is a source-access result only. It is not evidence that all 100 U001 names will always be retrievable, and it does not authorize bypassing any future source block.

## Sep 11 anchor semantics audit

The immutable first full U001 capture contains 100 observations.

Its observation schema includes both:

- `eps_currency`
- `period_ending`

The audit found:

- non-null EPS semantic field (`eps_currency`): 100/100 rows
- non-null `period_ending`: 100/100 rows

Selected retained examples:

| Symbol | FY | Period ending | EPS | EPS currency | Analysts |
|---|---|---|---:|---|---:|
| RELIANCE | FY2027 | 2027-03-31 | 63.97 | INR | 26 |
| INFY | FY2027 | 2027-03-31 | 0.86 | USD | 42 |
| TCS | FY2027 | 2027-03-31 | 155.08 | INR | 41 |
| HCLTECH | FY2027 | 2027-03-31 | 0.82 | USD | 39 |
| WIPRO | FY2027 | 2027-03-31 | 13.31 | INR | 40 |
| NESTLEIND | FY2027 | 2027-03-31 | 21.53 | INR | 35 |

Therefore the apparent difference between INR-traded NSE listings and the financial currency used for some provider forecasts is already explicitly represented in the frozen Sep 11 evidence. No reconstruction or backfilling of the anchor is required.

## Consequence for H021 comparison integrity

The current H021 comparison implementation checks fiscal-period label and broad source compatibility but does not yet require equality of `period_ending` and `eps_currency`.

That is insufficient. A primary percentage revision is only semantically comparable when the prior and current EPS observations use the same fiscal-period endpoint and the same EPS currency/basis.

Before the first valid 28-35 day H021 revision cohort, the comparison and capture contracts should therefore be hardened so that:

1. future full captures require explicit `period_ending` and `eps_currency` for any row with primary EPS;
2. primary H021 revision eligibility requires matching `fiscal_period`, `period_ending`, and `eps_currency` between prior and current captures;
3. missing or changed period/currency becomes an explicit no-signal reason rather than an inferred conversion;
4. no FX conversion is introduced into the primary signal, because the frozen signal is a within-company revision and same-currency comparison is sufficient;
5. provider/source-semantic changes remain separately fail-closed.

## Decision

Proceed to deterministic StockAnalysis parser development because direct public retrieval is reproducibly feasible on the frozen probe cohort.

Do **not** yet authorize unattended 100-name primary acquisition. The parser must first demonstrate deterministic extraction of annual fiscal period, period ending, average EPS, EPS financial currency, revenue/revenue growth, financial analyst count and provider identity on frozen test fixtures and a live source-only validation cohort.

Browser/search-assisted capture remains an allowed fallback under the existing H021 protocol when direct parsing is unavailable. Fallback failures remain explicit missing/block states and may not be substituted or backfilled.

No H021 return outcome, price signal, H013, H019, H020 or PF001 state was used in this decision.
