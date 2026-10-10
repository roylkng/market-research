# H021-P008: Source-only prospective daily market observation

Frozen design date: 10 October 2026, before the 12 October initial open.
Status: **SOURCE CAPTURE ONLY. NOT A RETURN/ALPHA/TRADING STRATEGY.**

## Problem

The immutable H021-P003 first decision cohort and P004 12 October entry-price
source observation are necessary but insufficient to ever evaluate the
prospectively frozen 20- and 60-completed-NSE-session hypotheses. An
independently dated stock and benchmark observation path is needed.

The H021 outcome rule stays:
- next completed-session open for the original 9 October decision
- secondary 20 completed NSE sessions and primary 60 completed NSE sessions
- market-relative excess versus Nifty 500, identical price interval
- no adjustment or portfolio outcome before fully sourced maturity and
  reviewed corporate action, dividends, trading calendar and costs.

## What P008 collects

For the **original** 10-name H021-P003 cohort only, beginning with the first
completed cash-market session **after 12 October 2026**, source daily:

1. Exact official NSE cash-equity UDiFF EQ bhavcopy ZIP.
2. Exact official NSE daily Nifty 500 index OHLC CSV.

The collector retains each complete original file with a content-addressed
SHA-256 plus original source URL, UTC capture timestamp and HTTP status.
It validates every U001 symbol/ISIN against the frozen first-cohort intent.
Corporate-action adjusted prices are **not** inferred, and individual
share-price records are never used as actual fills.

Each day has a unique immutable source packet, but only if all ten official
stock rows plus the official Nifty 500 index row validate. Otherwise the
collector records an append-only source attempt, preserving each missing or
blocked reason. It does not substitute another vendor, another date or
zero returns.

## Operational limits

The source workflow runs on weekdays, post-close, in two scheduled passes
with bounded source retries. It selects the oldest completed 2026 NSE
session that is not successfully sealed. No session is fetched before
its official close timestamp.

Each unresolved day receives at most three *automatic* source attempts.
After that, the day remains an explicit recovery/missing-data gap and later
sessions can continue. A separately source-verified manual recovery may
address the same exact date, but cannot re-date an observation.

Only the frozen original NSE-CM-FY27Q2-v1 session list through 31 December
2026 is accepted. On 8 November 2026, potential Muhurat trading is
explicitly unresolved in the original calendar. This workflow **cannot
silently assume that Sunday was a regular non-session or invent its hours**.
The existing P006 20/60-session outcome gate remains blocked across that
unresolved date.

The 2027 official exchange calendar is not yet verified and no January
2027 date is invented. Calendar extension requires a versioned and
independently sourced new contract.

## Storage and reproducibility

- Module: src/marketlab/h021_daily_prices.py
- Collector: scripts/collect_h021_daily_official.py
- Scheduler: scripts/resolve_h021_daily_session.py
- Workflow: .github/workflows/h021-daily-official-prices.yml
- Tests: tests/test_h021_daily_prices.py
- Records: research/prospective/h021/daily-prices/

Original source bytes are retained in the repository by SHA-256, with
independent GitHub Actions artifacts as additional execution receipts.
The source-state packet contains **no 20/60-session returns, benchmark
excess, target price, paper trade or order instructions**.

The workflow can be triggered when future sessions have actually
completed. No historical prices or future outcomes are fabricated in
this pre-entry implementation.

## Remaining gates

- P004 entry source must be collected successfully after 12 October.
- P008 real future data coverage must accrue over subsequent sessions.
- November 2026 Muhurat timing and 2027 NSE session calendar must be
  sourced officially and versioned under a separate protocol.
- Split, bonus, rights, demerger, dividends and identity breaks require
  verified, horizon-wide treatment before interpreting price returns.
- Benchmark index price-versus-TRI comparability, transaction-cost
  scenarios, liquidity and actual execution sensitivity remain unproven.
- Four monthly-equivalent prospective H021 cohorts and matured
  60-session outcomes are required under the precommitted promotion gate.

**Live capital and PF001 portfolio eligibility remain disabled.**
