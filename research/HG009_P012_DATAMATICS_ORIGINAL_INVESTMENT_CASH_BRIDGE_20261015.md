# HG009 P012: DATAMATICS FY26 cash generation versus investment deployment

**Research date:** October 15, 2026. **Underlying audited FY26 period:** March 31, 2026. **No live capital.**

## Economic question

The prior P049 cash-flow sensitivity used operating cash minus fixed-asset spending of **₹284.42 crore** as a historical proxy. But that is not distributable parent-company owner earnings. The original Datamatics NSE board-result PDF has an additional investing and financing cashflow structure that must be understood before forming an investment thesis.

**Original NSE source:** https://nsearchives.nseindia.com/corporate/DGSL_21052026190445_SEOutcomeUploaded.pdf, official 23-page May 21 audited board-filing, cashflow page 8, balance-sheet page 7.

The first exact 4,068,966-byte original PDF was independently retained October 14 with SHA-256 f96ecf4e698b4ee311126479fa20de0e7021449efc50cffa28a069dde40e8c77. HG009 P012 validates its original retrieval receipt, decompresses the archived PDF and verifies original consolidated FY26 text rows without changing the prior original filings or timestamps.

## FY26 consolidated cashflow waterfall (₹ crore)

| Original cashflow component | FY26 |
|---|---:|
| Operating cash from activities | **+323.99** |
| Fixed assets/CWIP/capital-advance purchase | -39.57 |
| **CFO minus selected fixed-asset spend** | **+284.42** |
| Acquisition of subsidiaries and noncontrolling interests | -33.93 |
| Net financial investment purchases | -262.76 |
| Fixed asset sale proceeds | +1.03 |
| Dividend receipts + interest receipts | +18.69 |
| **Net investing cashflow** | **-316.54** |
| **CFO after all investing flows** | **+7.45** |
| Net financing flows (borrowings, lease, interest, dividend) | -83.67 |
| **Total change in cash** | **-76.22** |
| Cash at beginning of year | 217.64 |
| **Cash at end of year** | **141.42** |

The reconciliation **323.99 - 316.54 - 83.67 = -76.22** must match the original statement. Unlike the CFO-less-PPE proxy, it covers the significant new securities investments, acquisitions and financing uses.

## First-principles interpretation

A ₹262.76 crore purchase of financial investments **does not mean that this money was lost or operating profit was overstated**. It is a conversion of cash into another asset. Those investments may be valuable and potentially liquid, but their restrictions, future fair value, double counting and attribution to the parent must be established before adding them to enterprise/shareholder value.

On the March 2026 consolidated balance sheet, current financial investments were ₹410.13 crore, noncurrent investments ₹228.77 crore, total **₹638.90 crore**. Cash ₹141.42 crore, financial borrowing principal ₹141.36 crore, goodwill ₹611.12 crore. The original balance-sheet **noncurrent lease liability is ₹46.77 crore** and current is ₹32.80 crore, giving **₹79.57 crore total**. This latter source column appears to differ by ₹1 crore from the older P049 manual transcribed noncurrent lease figure. P012 preserves P049 as historical evidence and records the original audit discrepancy instead of rewriting an old signed packet.

A dividend cash payment of ₹29.55 crore and lease principal of ₹23.98 crore belong to the FY26 financing cash statement. Shareholder dividend is a distribution, not loss of operating cash and cannot be subtracted again from already calculated total return without correctly recording entitlement.

The result is a **cash allocation bridge**, not a conclusion that the company has only ₹7.45 crore of economic owner earnings or that shares are overpriced. Investments may constitute excess, restricted or operating assets. Acquisition spending may add recurring revenue and cash flows. Normalized maintenance capex may be much smaller than total investment in a given year.

## Remaining valuation gates

1. Original note-by-note decomposition of ₹638.90 crore financial investments, including subsidiaries, quoted/unquoted instruments, mutual funds, related parties, legal restrictions, minority claims, tax basis and mark-to-market.
2. Subsequent interim FY27 cashflow quality, recurring free-cashflow reconciliation, working-capital timing and lease-adjusted operating economics.
3. Purchase accounting and return on capital for FY26 investments/acquisitions, avoiding double counted cash and acquired future earnings.
4. Current true diluted parent shares, stock options, minority economics, legal merger effective date and point-in-time NSE share price.
5. Source-backed bear/base/bull company equity model with genuinely calibrated probabilities, execution costs, and a falsifiable three-year thesis.

**Investable status: BLOCKED** pending those gates. There is no expected stock return or fair-value per share yet.

### Reproducibility

The original 2026 first-party PDF is pinned by its byte SHA, its Git archive path, and a timestamped original retrieval receipt. Report: research/hg009/hg009-p012-datamatics-fy26-cash-bridge-v1.json. Source parser: src/marketlab/hg009_p012_datamatics_cash.py. CLI: python scripts/materialize_hg009_p012_datamatics.py --check.

The historical P049 original source and its known self-checksum discrepancy are not rewritten. The P012 source validator pins its Git blob instead.
