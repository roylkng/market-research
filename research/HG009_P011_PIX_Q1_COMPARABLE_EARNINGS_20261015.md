# HG009 P011: PIXTRANS quarterly earnings, unit normalization and non-operating income

**Research date:** October 15, 2026. **Source:** original NSE iXBRL Q1 FY26 and Q1 FY27 standalone filings. **No live capital or price target.**

This is an **accounting-quality correction** to the previous HG009 P003 asymmetric profit-growth sensitivity. P003 reported +14.71% PBT change when only FY27's disclosed investment fair-value-through-profit-and-loss (FVTPL) gain was removed from the current quarter but the prior Q1 FY26 remained unadjusted. That one-sided comparison is *not* a valid estimate of underlying operational earnings growth.

## Original NSE iXBRL source and an important unit mismatch

| Source / Q1 fiscal period | Original published units | Reporting basis |
|---|---|---|
| [Q1 FY26 ended June 30, 2025](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_109641_08082025184215_iXBRL_WEB.html) | Actual INR rupees | Standalone, unaudited |
| [Q1 FY27 ended June 30, 2026](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_183737_07082026172912_iXBRL_WEB.html) | INR lakh | Standalone, unaudited |

Each historical original HTML is stored in the P009 source archive. This research pins an exact earliest-retained SHA and signed actual-retrieval receipt for each, independently verifies symbol PIXTRANS, ISIN INE751B01018, source period and unit, and cross-reconciles original PBT = reported total income minus reported expenses. A different NSE HTML version is not automatically assumed equivalent.

## Comparable reported pre-tax profits, ₹ crore

| Metric | Q1 FY26 | Q1 FY27 |
|---|---:|---:|
| Revenue from operations | 110.6415 | 134.5320 |
| Total other income | 14.1867 | 27.3112 |
| Total income | 124.8282 | 161.8432 |
| Total expenses | 93.8616 | 101.0264 |
| **Reported PBT** | **30.9666** | **60.8168** |
| Current FVTPL gain included in other income | **Not isolated by this source** | 25.2949 |
| Current PBT after removal of *only* this FVTPL gain | N/A | 35.5219 |
| **PBT excluding all other income in both periods** | **16.7799** | **33.5056** |

Reported PBT increased **96.39%**, while the current-quarter investment FVTPL is **41.59%** of the *current quarter's* PBT. The prior P003 **+14.71%** diagnostic is mathematically (₹35.5219cr ÷ ₹30.9666cr − 1), but it removes the current FVTPL while retaining FY26's entire ₹14.1867cr other income. It must be labeled **asymmetric**, not recurring operational growth.

The *symmetric*, deliberately coarse (PBT minus all other income) comparison increases **99.68%** year-on-year. It is a **pre-tax proxy** including all operating costs and financing effects and may exclude legitimate recurring interest income. It is **not** audited cash generation, economic owner free cash flow, a true segment EBITDA proxy or a future EPS estimate. A separate bank/investment ledger, debt/interest and cashflow reconciliation is still needed. It also does not prove the earlier fair-value gains were manipulation.

## Remaining investment gates

1. Reconcile standalone versus consolidated Q1 results and parent equity earnings.
2. Separate legitimately recurrent financing income, treasury FVTPL marks, operating product sales, inventory and raw-material cost changes.
3. Locate FY26 and FY27 quarterly/annual cashflow and investment realizations. Do not infer realized shareholder cash from an income-statement gain.
4. Verify current diluted shares, actual subsidiary minority ownership, ordinary dividends, latest dated NSE EQ price and executable spread/depth.
5. Build source-backed downside/central/upside owner-cash growth and valuation with calibrated uncertainty. Until that evidence exists, **no investment eligibility**.

Reproduce: `python scripts/materialize_hg009_p011_pix.py --check` and `pytest -q tests/test_hg009_p011_pix.py`. Output is a new signed research packet under `research/hg009/hg009-p011-pix-symmetric-quarter-profit-v1.json`. P003 original report and the selected hundred-company cohort remain unchanged.
