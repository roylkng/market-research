# HG009 P003: audit source quality before mistaking EPS growth for hidden-gem alpha

**Method review date:** October 14, 2026.  
**Source universe:** exact October 5, 2026 original HG001 full-market router, 2,319 NSE identities.  
**Fixed company sample:** HG009-D001 selected 100, SHA-256 e904e5d69dc7a6c2a45ea3cf34933544bc2634f80e3666125185d475372864d5.  
**Scientific status:** post-selection, pre-first-prospective-price accounting red-team. It is NOT new alpha preregistration, a price forecast, a valuation, investment advice or a claim of accounting misconduct.

## Why this adds information that HG009 source screening lacks

HG009 already flagged issuer earnings inflections, accounting asset anomalies and current transactions. Those signals can be deceptive:

- Percentage EPS increases may result from a depressed prior base or mark-to-market gains unrelated to recurring operations.
- An investment-heavy balance sheet is not automatically distributable shareholder cash.
- Reported PAT/PBT and operating cash flow may diverge because of inventories, customer collections, supplier terms, capex and investment acquisition.
- Bank/NBFC financial statements cannot be normalized with exactly the same operating-CFO/PPE approach as manufacturing companies.

To preserve an honest denominator, all 100 selected companies remain present. These flags only tell the human/agent researchers which **primary documents** to retrieve next. They do not reorder the 100 by predicted return.

## Fixed diagnostic thresholds from original October 5 HG001 numbers

| Flag | Predeclared review trigger | Cases from 100 |
|---|---|---:|
| EPS-revenue divergence | EPS YoY at least +50%, exceeding revenue YoY by at least 40 percentage points | 34 |
| Pretax margin jump | PBT margin improvement at least 8 percentage points | 23 |
| Extreme EPS versus topline | EPS YoY at least +100%, revenue YoY at most +40% | 16 |
| Negative current pretax margin | Latest source PBT margin below zero | 6 |
| Finance-cost jump | Financing expense YoY at least +100% | 7 |
| Investment/holding asset | Original asset plane flags investment-holding-heavy | 41 |
| EPS denominator undefined | EPS YoY unavailable despite earnings-opportunity lane | 10 |

Numbers overlap and are **not 137 unique companies**. Source metrics may have accounting-regime, denominator, or comparability problems themselves. No arbitrary cutoff is presented as a learned model or statistical false-positive probability.

## Pilot original exchange-filing review, independent of the October 5 router

### MAYURUNIQ: cash conversion, not headline P/E

The issuer's original [May 20, 2026 NSE integrated consolidated FY26 audited filing](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_159322_20052026182510_iXBRL_WEB.html) reports, all in INR lakh:

- FY26 profit before tax 25,898.23.
- Cash from operating activities 13,315.27.
- Purchase of property, plant and equipment 2,420.71.
- Source working-capital changes: inventory cash outflow 4,750.15, trade receivables outflow 2,264.22, other current assets outflow 1,776.33, and trade payables inflow 2,597.16.

In ₹ crore, CFO **₹133.1527 crore** versus pretax earnings **₹258.9823 crore**, or ~**51.41%** cash/PBT. CFO minus PPE purchases gives **₹108.9456 crore**, or ~**42.07%** of PBT. This is an *unadjusted one-year proxy*, not sustainable or normalized free cash flow, and CFO/PBT is not the same as CFO/PAT.

The four specifically identified working-capital cash components net to about **₹-61.94 crore**. They are **not** the entire working-capital line. A single year's customer/inventory build is not proof of chronically poor cash conversion, manipulation or fraud. Investigate FY23-FY27 working-capital reversal, maintenance-versus-growth PPE and investment-account restrictions before setting a normalized value.

### PIXTRANS: material FVTPL investment fair-value gains, not core operating profit

The issuer's original [August 7, 2026 NSE Q1 FY27 **standalone** results](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_183737_07082026172912_iXBRL_WEB.html) explicitly disclose **₹2,529.49 lakh** fair-value-through-P&L gains on investments inside quarterly other income. The original [August 8, 2025 NSE Q1 FY26 **standalone** results](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_109641_08082025184215_iXBRL_WEB.html) give the comparable prior pretax profit.

| Comparable standalone figure | Q1 FY26 | Q1 FY27 |
|---|---:|---:|
| Reported pretax profit, ₹ crore | 30.9666 | 60.8168 |
| Current investment FVTPL gain, ₹ crore | Not separately normalized | 25.2949 |
| FY27 pretax after excluding that **one** item, ₹ crore | Not calculated | **35.5219** |

Unadjusted year-on-year standalone PBT growth is **96.39%**. Removing the current-quarter FVTPL gain from PBT reduces the comparison to **14.71%** YoY, *before* tax, subsidiary consolidation, prior-year non-operating-income normalization, cash flow, investment realizability or market-value adjustments. This is a counterfactual quality challenge, **not** a forecast of what actual EPS would have been. Fair-value gains can be economically valid but should not be mislabeled recurring industrial cash earnings.

**Do not mix:** the separately reported **consolidated** Q1 FY27 PBT of ~₹66.64 crore with these standalone comparators or claim consolidated cash flow was audited in this quarter.

## Why no buy decision follows

A genuine valuation requires original annual balance-sheet notes, multi-year operating cash, normalized maintenance capex, investment/FD availability, shareholder-level diluted share count, working capital/cycle stress, group minority interests, conservative downside and execution costs. Flag frequency does not establish a probability of underperformance.

The original issuer iXBRL URLs above were independently reviewed on October 14. Their full raw HTML bytes, first-observed retrieval timestamps and hash-bound archived page captures **have not yet been stored** in the repo. Therefore P003 is a **manual original-source extraction pilot**, not full source-byte replay of all 100 filings. This limitation is encoded directly in the JSON report and the no-capital decision gates.

The canonical numeric source-screen and pilot calculations are generated from research/hg009/original-hg001-d001-router-20261005.json.gz by src/marketlab/hg009_p003_accounting.py and scripts/materialize_hg009_accounting.py. No market prices or post-entry returns enter this review.

## Next required system work

Automate primary-source retrieval and original byte hashing for all 100 selected plus the 200 control identities where filings exist, with timestamp/period/accounting-basis contracts. Segment cash flow and share notes must be reconciled to a reported parent-company basis. Only after original disclosure checks and a valuation scenario model should any company move from a screen to a **paper** expected-return thesis. Avoid retrospective winner-selection from future prices.

## Frozen reporting receipt

The original-router-derived 100-company accounting packet was materialized and reverified on October 14 before the intended October 15 entry. Signed content SHA-256: **ec1f133f530deba7ee3f4fec1d70f69b78c317aeb426582f5b22cb08d6f8b103**. This hash seals the seven overlapping diagnostic flag counts and the two limited original-exchange filing extracts. The method itself is a **post-selection manual research review**, not an Oct-5 preregistered return signal. The issuer iXBRL source pages are public URLs, not retained full original HTML bytes.
