# HG007-P020: NPST Original June 2026 Earnings and Capital-Deployment Facts

Status: **SOURCE-RECONCILED FINANCIAL DISCLOSURES, NOT AN INVESTMENT RETURN OR TARGET.**
Date: 11 October 2026 IST. No retroactive changes to HG005, HG002 or H021.

## Two primary BSE filings, distinct accounting purposes

The original BSE documents were retrieved and retained in HG007-P018 and
all original pages pinned by SHA-256 in HG007-P019:

| Document | Original PDF SHA-256 | Relevant pages |
| --- | --- | --- |
| 11 August NPST Q1 FY27 Investor Presentation | 5afd8b272e7bd2f7f3fad549aa1270e4899e1d24c8d982268cab16a17bbe2225 | 18, 19, 20 |
| 11 August NPST Reg32 June quarter preferential-funding statement | 79010c968b0fe8359f685d27a203c891a8e35f684a73b86a67cf78ee46b54013 | 1, 2, 3 |

Investor presentation:
https://www.bseindia.com/xml-data/corpfiling/AttachLive/5fab053f-1334-4b70-8ba7-4325e7f07b2e.pdf

Regulation 32:
https://www.bseindia.com/xml-data/corpfiling/AttachLive/0f52b8e1-9062-4b5a-be7c-ef0206f32489.pdf

The filing date was **11 August 2026**; the reporting quarter was
**30 June 2026**. An announcement dated 11 August but describing an
earlier March monitoring quarter is not June funding evidence and
remains independently excluded.

## Regulation 32: source-backed allocation budget

The company reports **₹300.0041 crore** raised by preferential
allotment (5 September 2025), including a disclosed 14,46,500 shares.
Its source document reports no deviation from fundraising purposes.

| Stated original purpose | Allocation (₹cr) | Spent through 30 June (₹cr) | Allocation unutilized (₹cr) |
| --- | ---: | ---: | ---: |
| Global expansion, brand building | 60.0000 | 10.7862 | 49.2138 |
| Product development, infrastructure and strategic acquisitions | 170.0000 | 16.8661 | 153.1339 |
| General corporate purpose, including issue expenses | 70.0041 | 7.9886 | 62.0155 |
| **Total** | **300.0041** | **35.6409** | **264.3632** |

Every row is tied to original Reg32 page 2 or 3, verified against the
P019 page-text SHA and original six-megabyte BSE PDF file SHA.
All three allocation and spending subtotals reconcile exactly.

Thus 11.88% of the stated original allocation has been spent and
**88.12% remains unutilized by arithmetic**. This is **not** evidence
of ₹264.3632cr unencumbered cash in NPST bank accounts, or of promised
deployment, returns, new profit or sponsor support. Whether the
remaining proceeds were held in bank deposits, earmarked investments,
related-party funds or otherwise has not been independently traced
to a quarterly cash-flow/balance-sheet statement.

## Consolidated Q1 FY27 issuer presentation

Original financial tables on pages **19 and 20** state (₹ crore):

| Reported line | Q1 FY27 |
| --- | ---: |
| Revenue from operations | 56.48 |
| Other income | 4.94 |
| Total income | 61.42 |
| Total expenditure | 42.63 |
| **EBITDA (table)** | **18.79** |
| Finance costs | 0.21 |
| Depreciation | 4.09 |
| PBT | 14.49 |
| Tax | 3.44 |
| **Net profit (table)** | **11.05** |

The filing's arithmetic reconciles:

- ₹56.48cr revenue + ₹4.94cr other income = ₹61.42cr total income.
- ₹61.42cr total income - ₹42.63cr expenditure = ₹18.79cr
  table EBITDA.
- ₹18.79cr EBITDA - ₹0.21cr finance costs - ₹4.09cr
  depreciation = ₹14.49cr PBT.
- ₹14.49cr PBT - ₹3.44cr tax = ₹11.05cr net profit.

The company's quoted **30.59% EBITDA margin** is calculated on
*total income* ₹61.42cr. It is NOT the margin on just ₹56.48cr
operating revenue. The table's EBITDA arithmetic includes
**₹4.94cr other income**, so its underlying recurring or
non-operating composition needs an additional note-level
reconciliation before using this EBITDA for long-term multiples.

**Visible source discrepancy preserved:** the graphic on original
page 18 says ₹18.78cr EBITDA and approximately ₹11.04cr net
profit, while tables on pages 19 and 20 say ₹18.79cr and
₹11.05cr, respectively. The 0.01cr difference may be a chart
rounding/production discrepancy, but no audit conclusion is
available. The P020 arithmetic uses the two agreeing financial
tables, clearly marking the graphic disagreement and pending
visual/audited statement verification.

The source investor presentation is not a substitute for an
independent audited or exchange-filed consolidated standalone
accounting reconciliation.

## No proof of NPST's ₹61.43 crore economic hurdle

Original frozen HG005-D003 had an *illustrative*, not forecast,
50% equity-upside reverse hurdle:

- At 30x illustrative multiple, **₹61.42562125cr additional
  annual EBITDA** required.
- Q1 FY27 ₹18.79cr table EBITDA times four = ₹75.16cr
  historical-quarter annualization, **not a full-year forecast**.
- The required additional annual EBITDA equals about **81.73%**
  of that naive quarter-times-four baseline.

There is no source-verified mechanism for converting ₹264.36cr of
unutilized proceeds into ₹61.43cr recurring annual incremental
EBITDA, and no proof of sustainably earning 30x, current
fully diluted shares, cash conversion, business concentration,
receivable collection, acquired technology quality, or likely
downside.

## Reproducibility and remaining gaps

- Module: src/marketlab/hg007_npst_june_facts.py
- CLI: scripts/reconcile_hg007_npst_june_facts.py
- Regression: tests/test_hg007_npst_june_facts.py
- Exact P019 Git blob: 4fd4b6b9c09b425284c1b4c420bdc0f4b0092506.
- Original HG005-D003 Git blob:
  b235bd9168bc658f7511f9cec1913f20f82cf311.
- Two actual PDF file SHA-256 and issuer/date/period receipts are
  independently checked, then individual page text hashes and
  support phrases rechecked before every calculation.

Generated after main merge:

research/hg007/npst-aug2026-originals/june-2026-financial-and-funding-ledger-v1.json

Next independent review:
1. Visually inspect graphic page 18, financial tables pages 19–20,
   and Reg32 object/total table pages 2–3, including any merged rows.
2. Reconcile the original audited or SEBI filed consolidated
   financial statements with presentation EBITDA, other income,
   cost classifications and related-party receivables.
3. Obtain bank-deposit/cash custody and monitoring-agency June
   quarter evidence consistent with the Reg32 amount.
4. Establish incremental deployed capital, acquired contracts,
   retained customers and independently documented additional
   cash EBITDA, not assumed percentages.
5. Validate current full diluted count, price, debt and corporate
   action history before any multiple or stock return work.

This review does not open future price returns, change company
selection, promote a survivor-conditioned completion probability,
issue an equity target or authorize portfolio/live capital.
