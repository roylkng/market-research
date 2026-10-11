# HG007-P036: Official Twenty-Session Turnover Distribution for Five Hidden-Gem Cases

**Study registered 11 October 2026.** All market sessions in scope are
historical, ending 9 October. This is a liquidity-source diagnostic,
not a prospective stock-selection alpha test, an order-book simulator,
or evidence that quoted turnover is available to execute a buy or sale.

## Why the P035 one-day result is insufficient

The original, SHA-verified 9 October NSE cash-equity UDiFF report
recorded only **₹0.6124 crore** of turnover for DEVX, while INOXGREEN
traded **₹943.19 crore** amid an unusually wide daily high/low spread.

Neither observation tells us what turnover is ordinarily available.
An exceptional earnings or transaction-news day must not be treated
as representative future execution liquidity.

## Frozen window and exact sources

Use the original, unchanged 20 completed official NSE cash-market
sessions **10 September through 9 October 2026**, selected from the
Git-blob-verified NSE-CM-FY27Q2-v1 trading calendar. The original
five-company cohort and exact 9 October ISINs come only from
source-sealed HG007-P035:

- ANANTRAJ
- DEVX
- INOXGREEN
- NPST
- SAMBHV

The **9 October** original NSE UDiFF ZIP is already independently
retained at SHA-256
8adbb3410c8cf4372290484a9b1798490ef279d30fc2439c93f082cc20ed198c.
The pipeline reuses those exact original bytes, never replacing them.

For the earlier **19 trading sessions**, retrieve only the exact original
dated NSE CM UDiFF bhavcopy ZIP URLs from the official exchange archive.
Each successful file receives original bytes, UTC acquisition timestamp,
SHA-256, exact URL and HTTP evidence in the repository.

A source is accepted only when its:
- original ZIP archive has a valid UDiFF NSE cash-equity schema;
- reported trade date matches the actual frozen NSE session;
- all five names have exactly one EQ row and the SAME pinned ISIN;
- volume, traded value, transaction count and OHLC are finite and valid;
- computed traded-value/volume lies inside the original daily high/low;
- it is captured AFTER the exchange completed that session.

HTTP 401/403/429, 404, redirects, missing files, duplicate/changed
ISINs or malformed data fail closed. They are recorded as unresolved,
never substituted by Yahoo, current prices, different dates or zero
traded value.

## Strict completion gate

Compute the following *only if all 20 sessions and all five company
rows validate*. Otherwise publish no median, P10, P25 or execution
quotient:

- median, nearest-rank P10 and P25, minimum and maximum original
  *daily cash-market traded INR value* for the 20 completed dates;
- the single 9 October traded value divided by its **trailing 20-session
  median, including 9 October**;
- a **₹10 lakh / (1% × historical daily median traded value)** dimensionless
  quotient, clearly not an estimate of calendar days or actual fills.

Percentiles follow nearest-rank, not a guessed interpolated exchange
volume. These are traded-value distribution descriptions only, not
bid/ask spreads, available offer sizes, share inventories, or capacity
at a user-specified order price.

## Reproducibility and operational recovery

- Model: src/marketlab/hg007_liquidity_history.py
- Original NSE collector: scripts/acquire_hg007_liquidity_history.py
- Tests: tests/test_hg007_liquidity_history.py
- Workflow: .github/workflows/hg007-twenty-session-liquidity.yml
- Source and final output:
  research/hg007/twenty-session-liquidity/

Workflow on first main merge and bounded October 11–17 recovery
attempts. It reuses previously source-retained exact original ZIPs,
and appends unique attempts for missing/unavailable days.

Only if the full window is verified is
twenty-session-liquidity-v1.json written once. No partial-day
statistics are published. Original ZIPs are retained content-addressed
under raw/sha256/ with date-specific source receipts and append-only
failure attempts in Git. GitHub Actions artifacts provide separate
time-stamped execution evidence.

Run source-only acquisition on a current checkout:

    python scripts/acquire_hg007_liquidity_history.py \
      --repo-root . \
      --attempt-key manual-20261011-unique-001

## What this cannot establish

Historical September trading data were gathered *after* the original
five-company opportunity selection, so this is not a preregistered
alpha result or untouched return sample. Even verified 20-day
turnover data do NOT establish prospective fills, stable order book,
depth, slippage, bid/ask spreads, impact cost, taxes, circuit-band
feasibility, exchange surveillance risk, delivery eligibility or
how many days a ticket would take to transact.

The five-case investment review still requires original fiscal
cash-flow evidence, current issued/diluted shares, capitalization,
corporate-action proof, fully financed project milestones and
downside valuation. P036 does not revise frozen HG005/HG006
estimates, make a recommendation or authorize capital.
