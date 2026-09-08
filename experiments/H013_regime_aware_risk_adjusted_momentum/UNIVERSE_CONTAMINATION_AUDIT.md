# H013 universe contamination audit

Recorded: 2026-09-08 after the two historical H013 challenge results and before any live-capital promotion.

Status: **H013 HISTORICAL PASS INVALID FOR COMPANY-SELECTION CLAIM. LIVE CAPITAL DISABLED.**

## Material finding

The frozen H013 implementation treated NSE `EQ` series bars as stocks. That is not sufficient to identify operating-company common equity. The retained selected lists contain multiple exchange-traded fund units, including gold, silver and liquid-product symbols such as `GOLDBEES`, `AXISGOLD`, `SILVERBEES`, `HDFCSILVER`, `LIQUID1` and related tickers.

This matters directly to the research objective:

- these are not companies,
- many ETF tickers share the same underlying commodity exposure,
- symbol-level concentration therefore understates economic-factor concentration,
- the later H013 positive tail includes a large cluster of silver ETF winners,
- a company-selection system must not obtain its edge from repeated wrappers around one underlying asset.

Across the combined 613 H013 selections there were only 284 unique symbols, and several ETF symbols appeared in every active cohort. In the later window, numerous silver ETF tickers were among the largest positive excess contributors.

## Decision

Do **not** reinterpret H013 as a valid company-selection result. Do not silently remove the ETFs and keep the H013 label after seeing their outcomes.

The H013 signal mechanism may still be worth testing, but the corrected company-only universe becomes a new hypothesis. The successor must explicitly identify corporate equity before any corrected result is calculated.

## Corrective universe principle

The next hypothesis will require all of:

- NSE `EQ` series,
- stock instrument bars under the retained market-data contract,
- a 12-character ISIN beginning with `INE`, which excludes mutual-fund/ETF unit ISIN families such as `INF`,
- one security identity per selected corporate-equity ISIN,
- the same liquidity, complete-bar, corporate-action and tradability constraints.

This is intentionally conservative. If a security cannot be classified as operating-company equity from retained source identity, it is excluded rather than guessed.

H013 remains useful as evidence that risk-adjusted trend may contain information, but it is **not** a successful answer to the project's company-identification goal.
