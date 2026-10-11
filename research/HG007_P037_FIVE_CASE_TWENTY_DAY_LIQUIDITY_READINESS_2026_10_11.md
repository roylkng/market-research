# HG007-P037: Integrate Verified 20-Day NSE Turnover into Five Casework Reviews

Frozen 11 October 2026 IST. This is source-bound *liquidity readiness*
and is NOT a measured execution model, investor order, new alpha feature,
portfolio allocation or tested return prediction.

## Problem

The original P033 underwriting cases are detailed about demergers,
subordinated debt, operating cash EBIT, capital expenditure and warrant
funding, but that frozen result contains no typical cash-market
liquidity context. P035 exposed large one-day heterogeneity; P036 then
retrieved all 20 actual original NSE UDiFF ZIP files through 9 Oct,
verified all five original stock ISINs, and materialized the full
20-session historical turnover distribution.

A downstream system using P035's Oct9 event day as available capacity
could greatly overstate INOXGREEN tradability or understate DEVX's
routine market-value constraint.

## Original data are still the authority

Immutable sources re-read and revalidated, not copied over old
payoff models:
- P033 five original source-economics cases (ANANTRAJ, DEVX,
  INOXGREEN, NPST, SAMBHV) with all block conditions unchanged;
- P035 actual 9 October exchange EQ source and one-day turn
  counterexamples;
- P036 exact original **20 sessions 10 September–9 October**,
  P10/P25/median and content-addressed UDiFF raw source bytes.

The P037 program **re-extracts all 20 source ZIP files**, verifies
that P036 is reproducible, checks the corresponding P035 single-day
observation and its exact ISIN for each company, and leaves
all earlier code and original files unchanged.

## Observed NSE cash-market traded value, INR crore

| Original company | P10 (nearest rank) | P25 (nearest rank) | Median | 9 Oct | Highest day |
|---|---:|---:|---:|---:|---:|
| ANANTRAJ | 61.69 | 68.52 | 88.73 | 83.44 | 208.30 |
| DEVX | **0.083** | **0.200** | **0.408** | 0.612 | 1.742 |
| INOXGREEN | 6.77 | 15.60 | 26.63 | **943.19** | 943.19 |
| NPST | 4.32 | 8.59 | 12.52 | 14.31 | 558.46 |
| SAMBHV | 21.26 | 25.77 | 47.86 | 41.55 | 932.41 |

This is a historical turnover *distribution*, not current
order-book or total-return evidence.

For a hypothetical INR 10 lakh order and only **1% of the 20-day
median daily traded value**, a dimensionless ticket-to-volume
ratio greater than one occurs only for DEVX (~24.48).
This is a **comparative source-turnover warning**, not an
estimate of actual daily available liquidity or how many trading
sessions an order would require. Actual spreads, depth, broker
market impact, auction conditions, buyer/seller behavior,
delivery settlement and portfolio liquidation risk are unmeasured.

Extreme source days confirm that quoted maxima should not be used:
- INOXGREEN 9 Oct traded ~35.4× its own historical median.
- NPST 16 Sep maximum traded ~44.6× its median.
- SAMBHV 21 Sep maximum traded ~19.5× its median.

These ratios do not establish whether those days involved bulk
deals, surveillance, causal news, manipulation or any repeatable
retail execution opportunity.

## Output and guardrails

Source model: src/marketlab/hg007_liquidity_readiness.py
CLI: scripts/build_hg007_liquidity_readiness.py
Tests: tests/test_hg007_liquidity_readiness.py
Main workflow: .github/workflows/hg007-liquidity-readiness.yml
Machine-readable output:
research/hg007/hg007-p037-five-case-20day-liquidity-readiness-v1.json

All five original transaction and financial due-diligence fields are
preserved. Only a new original-market-source liquidity context field
is appended per case. No investability permission, financial forecast,
completion probability or upside target is promoted.

## Unresolved gates

- Bid/ask spread, depth, time-of-day and realistic multi-order fills.
- Price bands, lot limits, surveillance restrictions and broker costs.
- Current fully diluted share counts and corporate actions.
- Actual audited incremental business cash earnings and funding,
  case-specific downside/payoff probabilities, maturity of prospective
  forward returns and any multiplicity-adjusted alpha evidence.

The above missing items cannot be inferred from transaction turnover.
**No investment recommendations or live capital are authorized.**
