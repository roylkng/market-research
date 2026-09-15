# H010 independent historical robustness result

Recorded: 2026-09-08

Status: **FAILED. LIVE CAPITAL DISABLED.**

H010 was frozen after the prior-60-session relative-momentum comparator looked strongest in 2026 medium-horizon diagnostics, and before any H010 60-session outcome from the 2024-10-01 through 2025-06-30 robustness window was opened.

The one-shot replay completed from retained official NSE result listings, UDiFF EQ-series daily prices, Nifty 500 index snapshots and retained corporate-action records. Repository lint, tests and registry validation passed before the outcome step executed.

## Coverage

- deduplicated official result events: 4,279
- evaluable primary-liquidity events: **1,942**
- selected at frozen top 10%: **195**
- common market sessions retained: 322
- market symbols retained: 2,466

Main exclusions were 904 events below the INR 2 crore median prior-20-session traded-value floor, 1,142 observations with a missing stock bar in an exact signal/holding window, 273 symbols without sufficient market history, 14 observations crossing unresolved structural corporate actions, and four flat entry bars.

## Frozen H010 top-10% result

- median Nifty 500 60-session excess: **-4.08 percentage points**
- mean Nifty 500 excess: **-2.88 percentage points**
- Nifty 500 beat rate: **40.00%**
- median raw stock return: **-7.98%**
- excess >= +5 percentage points: **28.21%**
- maximum company contribution to aggregate positive gross close-return P&L: **6.88%**

Quarter diagnostics were also negative:

- 2024-Q4 selected cohort median excess: **-3.21 pp**, beat rate 44.0%
- 2025-Q1 selected cohort median excess: **-9.21 pp**, beat rate 31.1%

The matched prior-20-session momentum comparator was less bad but still negative, with -3.29 pp median excess. The first-session tape comparator had -2.36 pp median excess.

The full eligible cohort itself had -4.61 pp median excess and -3.31 pp mean excess. H010 therefore improved only marginally on a broadly hostile period and did not produce an absolute or market-relative investment edge.

Fixed-seed 10,000-draw matched random tests produced one-sided empirical p-values of approximately 0.32 for the H010 median and 0.33 for the mean. H010 is statistically indistinguishable from random matched selections under the frozen test.

H010 failed the frozen gates for median/mean excess, beat rate, positive raw return, +5 pp hit rate, superiority to prior-20 momentum, required improvement over the unconditional cohort, quarter stability, and both random-significance tests. Coverage, selection count and concentration gates passed.

## Implication

The positive 2026 event-conditioned relative-momentum result does not generalize backward to the 2024-Q4/2025-Q1 correction regime. This falsifies the simple claim that a result announcement plus strong prior-60 relative momentum is a stable medium-horizon company-selection edge.

The common failure pattern across H005-H010 is now informative. Conditioning the stock universe on result events does not create a stable edge, while momentum effectiveness changes materially with the broad market regime. The next hypothesis should remove the earnings-event gate and test a cross-sectional full-market momentum mechanism with an explicitly frozen market-regime rule, rather than tuning another event-specific signal.
