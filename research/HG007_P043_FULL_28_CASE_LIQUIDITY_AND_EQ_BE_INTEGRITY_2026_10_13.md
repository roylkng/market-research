# HG007-P043: Integrate All 28 Original NSE Liquidity Histories into Casework

**Research-only as of 13 October 2026.** Market observation window was
10 September–9 October 2026. This is **post-selection retrospective source
context**, not an alpha discovery trial, buy ranking, execution model or
current-price/market-cap verification.

## Source of truth

P043 independently verifies exact Git-blobs and internal packet digests:

1. Original HG007-P009 capital-source overlay: all 28 original HG002
   companies, including the INOXGREEN stale March fully diluted capital
   reference warning, with zero approved investment recommendations.
2. Original HG007-P041 28-name official NSE 20-session cash-market
   UDiFF evidence (10 Sep–9 Oct): **26 complete EQ series**.
3. Original HG007-P042 independent original NSE series diagnosis:
   ORBTEXP missing 11 EQ days and RETAIL missing 5 EQ days, while
   each corresponding original date has valid same-ISIN **BE-series**
   turnover. BE is not silently promoted to EQ, and no gap becomes zero.

The result preserves each original company's transaction family, catalyst
state, payoff/sensitivity, funding/valuation blockers, capitalization
warnings, and exact original membership. It adds *only* market-source
readiness. No fundamental claims, previous research files, or prospective
signals are changed.

## Observed historical liquidity heterogeneity

Using median daily NSE **EQ traded value**, full 20-session coverage:

| Observed daily cash traded value band | Names | Count |
|---|---|---:|
| Below ₹10 lakh (₹0.1 crore) | BAGFILMS, SANDESH, SUVIDHAA | 3 |
| ₹10 lakh to below ₹1 crore | AXITA, DEVX, GANDHITUBE, HTMEDIA, JINDALPOLY, SARLAPOLY, TREL | 7 |
| ₹1 crore to below ₹10 crore | DATAMATICS, MMFL, NIITLTD, ORCHPHARMA | 4 |
| ₹10 crore and above | Other 12 complete-EQ companies | 12 |
| Incomplete EQ, separately observed BE series | ORBTEXP, RETAIL | 2 |

Band boundaries describe already-observed source turnover, **not an
underwriting admission threshold**, and have not been tested against
subsequent excess returns.

Five of the eleven original HG004 active/procedural live transaction
threads had an EQ historical median daily turnover **under ₹1 crore**:
AXITA, DEVX, SANDESH, SUVIDHAA, TREL. These remain fundamental
research cases; the observation makes order-depth verification important,
not a mathematical claim that the companies are uninvestable.

Illustrative ₹10 lakh source-only ticket comparison against
**1% of previous 20-session median daily traded value**:

- DEVX: 24.48× the comparison quantity at ₹0.408 crore median.
- SANDESH: ~201.08× at ₹0.0497 crore median.
- SUVIDHAA: ~493.96× at ₹0.0202 crore median.
- INOXGREEN: ~0.375× at ₹26.63 crore median.
- ANANTRAJ: ~0.113× at ₹88.73 crore median.

These are **dimensionless ratios**, neither expected trading days,
market impact/slippage, cumulative position capacity, probability
of fill nor evidence that the observed stock was order-executable
at a specific time.

The P041/P042 observation dates precede this P043 study. This is
a retrospective look at already-known prices/quantities; it is
not a prospective selection algorithm, an untouched test, or evidence
of expected future liquidity.

## Machine-readable output and reuse

Model: src/marketlab/hg007_full_liquidity_overlay.py
CLI: scripts/build_hg007_28_liquidity_risk.py
Regression: tests/test_hg007_full_liquidity_overlay.py
Workflow: .github/workflows/hg007-full-liquidity-risk.yml

Immutable after passing main-branch tests:

research/hg007/hg007-p043-28-case-liquidity-risk-v1.json

Reproduce entirely offline:

    python scripts/build_hg007_28_liquidity_risk.py \
      --out /tmp/hg007-28-liquidity-risk.json

The result preserves the P009 capital-readiness status. INOXGREEN's
older March-FD capitalization cannot be reused as today's value;
P008's separate share issuance correction remains basic, not
full diluted EV.

## Remaining actual work, not guessed values

- Official source-verified current EQ/BE series/settlement status
  for ORBTEXP and RETAIL; historical series changes are neither
  exchange suspension nor proof of stock illiquidity today.
- Actual bid/ask depth, auction liquidity, deliverable turnover,
  broker lot/surveillance restrictions, price impact and order slippage.
- Updated issuer share counts, debt, QIP proceeds, splits/dividends,
  liabilities, legal approval and contracted business cash earnings.
- Prospective market outcomes, matched benchmark, costs, and multiple
  testing discipline before any stock-level alpha assertion.
- At least four matured monthly-equivalent H021 cohorts for the
  independent EPS revision experiment; P043 does not modify it.

Portfolio eligibility remains FALSE for all 28. Live capital stays
disabled. No new stock recommendation is created.
