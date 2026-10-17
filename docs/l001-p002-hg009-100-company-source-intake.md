# L001 P002: HG009 all-100 long-horizon evidence intake

**Research snapshot:** 2026-10-17T12:00:00Z. **Status:** deterministic source-readiness inventory, not a newly frozen investment experiment and not a valuation or return prediction. No live capital.

## Preserved 100 names without a winner-selection rewrite

Inputs, unchanged:
- `research/hg009/hg009-d001-100-experimental-companies-v1.json`, pin `e904e5d69dc7a6c2a45ea3cf34933544bc2634f80e3666125185d475372864d5`.
- `research/hg009/hg009-p014-economic-symmetry-and-cash-v1.json`, pin `093c29805ccf0423c1d8b0bfbb8c80c9d89c83c2f12395ea16348a0d6ae47ddc`.

The generated [intake manifest](../research/l001/p002-hg009-100-source-readiness-20261017.json) retains **100 of 100 symbol+ISIN identities** and original routing-row hashes, with historical turnover-bands explicitly *not* labelled fill capacity. Ten dossiers have bounded P014 original-source investigation, five have prior FY26 consolidated cash-flow replay references. Those cash-flow replays are **not** independently authenticated inside this *new* intake and are not parent-distributable owner cash.

**Observed completeness:**

| Check | Count |
|---|---:|
| Frozen cohort retained | 100 / 100 |
| Earlier detailed P014 dossiers | 10 / 100 |
| Earlier consolidated FY26 cash-replay references | 5 / 100 |
| Fresh official PIT industry classification supplied to this intake | 0 / 100 |
| Current fully source-complete owner-value packets | 0 / 100 |
| Valid 1/2/3-year investment valuations | 0 / 100 |
| Matured prospective 252/504/756-session outcomes | 0 |

This is an **honest progress ledger**, not a failure count for the old repository. Many existing separate experiments have market and other financial data, but they do not together establish the nine fully reconciled parent-cash facts needed per company. Absence of an industry receipt is not evidence that a company has no industry.

## Why all 100 currently abstain

HG009's selected rows do **not** contain a verified, point-in-time NSE industry classification. We cannot infer from the ticker whether a company belongs to a regulated financial business or apply an industrial NOPAT/ROIC model by default.

`l001_p002_intake.industry_from_original` requires NSE-host original bytes containing exact symbol, ISIN, industry name, matching SHA, published/first-seen UTC times no later than the research cutoff and an independently reviewed status (which remains a caller assertion). Unknown, missing, spoofed, mismatched or post-cutoff industry receipts yield `UNCLASSIFIED`. Finance gets **FINANCIAL_SPECIALIST_ONLY**; industrial cases get **INDUSTRIAL_REVIEW_ONLY** but still need original source-complete financials and attribution.

After classification, source roles are required separately:

- **Industrial:** audited consolidated financials, fully diluted shares, attributable owner cash, maintenance versus growth capex, minority/acquisition/lease claims, accessible surplus cash, incremental NOPAT and capital, original corporate actions, delisting and execution receipts.
- **Financial:** regulatory balance sheet, diluted capital, credit losses and asset quality, loan book/funding cost, regulatory capital, parent book value/earnings/ROE and truly distributable capital, acquisitions and minorities, corporate-action and tradability receipts.
- For all: use original documents, separate operating/financing/investing cash, detect rights/bonus/mergers/delistings, version first-seen/known-at times and maintain point-in-time constituent snapshots. No missing values become zeros.

## Deterministic verification

```bash
python scripts/materialize_l001_p002_source_intake.py --check
pytest -q tests/test_l001_p002_intake.py
ruff check src/marketlab/l001_p002_intake.py scripts/materialize_l001_p002_source_intake.py tests/test_l001_p002_intake.py
```

Changing even one frozen symbol, original ISIN or cash packet rejects the pinned signature. All 100 rows are kept. A synthetic bank-issuer classification test verifies that the industrial-invested-capital formula cannot be applied to a verified financial-services issuer.

## What's genuinely left of issue #471

1. Acquire and retain **100 original exchange industry receipts** (or independently authenticated archived source data), rather than silently adding manual sector tags.
2. Acquire original audited and post-result source packets, including 100 share/capital reconciliations, split between finance and nonfinance economics.
3. Reconcile corporate actions/delistings and reliable execution for each 252/504/756-session prospective label, only after it has actually matured.
4. Freeze an **independent future** long-horizon experiment and comparison controls. Historical HG009 October 15 returns and today's post-hoc diligence cannot become prespecified alpha.

This PR completes the **all-company deterministic intake and explicit abstention implementation**. It does **not** fabricate original-source completeness or claim issue #471's data-collection and 1–3-year empirical objectives are already finished.
