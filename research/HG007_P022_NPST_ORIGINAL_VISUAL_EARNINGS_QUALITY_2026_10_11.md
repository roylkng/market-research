# HG007-P022: NPST Original Q1 and Reg32 Visual Crosswalk

Status: **SOURCE-VERIFIED DOCUMENT LAYOUT CROSSCHECK**, completed
11 October 2026 IST. Not an independent financial-statement audit,
stock recommendation, survivor completion probability or investment
return backtest.

## Source custody

The exact BSE issuer PDF files were originally retained in P018,
their all-pages raw PDF text SHA-256 pinned in P019, numerical facts
reproduced in P020 and five critical page PNGs rendered from the same
exact original files in P021.

Image manifest:
research/hg007/npst-aug2026-originals/june-source-financial-visuals/source-visuals-v1.json

The PNG manifest's immutable Git blob:
4dc4e80d8b58a1f4ec9b83b1be1e682c0572a445.

Previous source-fact packet:
research/hg007/npst-aug2026-originals/june-2026-financial-and-funding-ledger-v1.json

Previous source-fact Git blob:
73809c3d731468b4ef9e43438cd25454a9a6cf0d.

The original source-photo and text hash are preserved per fact,
and the actual five stored images were visually compared against
the issuer table rows. This is an **assistant visual source inspection**,
not sign-off by the issuer's independent auditor or confirmation of
complete explanatory financial notes.

## Regulation 32 column alignment confirmed

Original BSE Reg32 PDF pages 2–3 visibly align each row to
exactly the budget and spending columns used in P020:

| Purpose | Allocation ₹ crore | Spent through 30 June ₹ crore |
| --- | ---: | ---: |
| Global expansion and brand | 60.0000 | 10.7862 |
| Product, infrastructure and strategic acquisition | 170.0000 | 16.8661 |
| Corporate purposes and issue expenses | 70.0041 | 7.9886 |
| **Total** | **300.0041** | **35.6409** |

The source-compatible derived unused allocation is **₹264.3632
crore**. This is not a bank-account balance and says nothing about
whether funds are encumbered, current as of Oct 11 or yet
economically productive.

No deviation of fund usage is reported; absence of deviation is
not proof of high returns from the unused budget.

## Investor presentation: original image vs table discrepancies

The source 18–20 pages visually establish:

| Measure | Graphic original page 18 | Tabular original page 19 | Tabular original page 20 |
| --- | ---: | ---: | ---: |
| Q1 FY27 consolidated EBITDA, ₹cr | **18.78** | **18.79** | **18.79** |
| Q1 FY27 consolidated net profit, ₹cr | **11.04** | **11.05** | **11.05** |
| Q1 FY26 consolidated EBITDA, ₹cr | **11.30** | **11.31** | **11.31** |
| Q1 FY26 consolidated net profit, ₹cr | **7.19** | **7.19** | **7.20** |
| Q1 FY26 diluted EPS, ₹ | not shown | **3.70** | **3.69** |

These are **real intra-presentation inconsistencies** at the
0.01 crore/0.01 EPS reported precision, not a text extraction
or column-ordering error.

Q1 FY27 EBITDA **18.79** and net profit **11.05** are the better
traceable *issuer-presentation accounting bridge*, because the
current-year line-item identities on page 20 reconcile to those
two figures. The discrepancies are not resolved by an
independently audited consolidated financial statement.

## More important underwriting challenge: recurring earnings quality

Original detailed original page 20 reports, ₹ crore:

| Financial line | Q1 FY26 | Q1 FY27 |
| --- | ---: | ---: |
| Revenue from operations | 33.62 | 56.48 |
| Other income | 1.47 | 4.94 |
| Total income | 35.09 | 61.42 |
| Other operating expenses | 2.57 | 19.85 |
| EBITDA | 11.31 | 18.79 |

Reported EBITDA increase **does not establish** incremental SaaS
cash profit unless other-income composition, expense-category
migration, depreciation policies, receivables and cash collection
are reconciled.

Specific points that require original financial statements:

- Other income expanded by ₹3.47 crore (from 1.47 to 4.94).
  The current ₹18.79cr EBITDA arithmetic **includes that other
  income** because ₹61.42cr total income less ₹42.63cr total
  expenditure equals ₹18.79cr.
- Other expenses rose from ₹2.57cr to ₹19.85cr, an increase
  of ₹17.28cr. The presentation alone does not prove which costs
  are recurring, one-off, acquisition-related or category
  reclassifications.
- Q1 FY27 reported EBITDA margin **30.59%** is based on
  **total income 61.42cr**, not operating revenues 56.48cr.
  Calling it a 30.59% core revenue EBITDA margin would be wrong.

The same original P019/HG005 source does not establish how
₹264.36cr unutilized funds can turn into ₹61.43cr additional
annual recurring EBITDA at the illustrative 30x multiple, or
whether that multiple is appropriate.

## Reproducibility

- Source-pinned crosswalk:
  src/marketlab/hg007_npst_visual_crosswalk.py
- CLI: scripts/review_hg007_npst_original_visuals.py
- Tests: tests/test_hg007_npst_visual_crosswalk.py
- CI: .github/workflows/hg007-npst-visual-crosswalk.yml

On main, generate an immutable append-only source-review record:

research/hg007/npst-aug2026-originals/june-visual-financial-review-v1.json

This source image inspection does not meet the standard for
formal company independent auditor financial statement
reconciliation or cash flow/valuation readiness.

**Investment recommendations, current target valuation, live
capital and paper portfolio eligibility remain disabled.**
