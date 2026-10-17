# L001 P003: Archived NSE Total Market industry overlap (advisory)

Research time: October 17, 2026. All source data are real archived repository bytes. This is **not** source-ready industry-factor evidence, because RM001-SC002's frozen acceptance gates have not passed.

## Original-input audit

- Freeze: HG009 D001, 100 names, cohort SHA `e904e5d69dc7a6c2a45ea3cf34933544bc2634f80e3666125185d475372864d5`.
- NSE Indices Total Market constituent CSV: `research/prospective/rm001-sc002/raw/2026-10-16/nifty-total-market-692caee1b8e4fd11912c71e1c2519c4070e9675f9a0a9e6d40294cdf032890fc.csv`, exact original bytes SHA `692caee1...`.
- Pinned RM001-SC002 readiness audit: `research/l001/p003-rm001-sc002-readiness-pinned-20261017.json`, summary SHA `955699a9f6361083c9ed97d806800e518c1ccaf404700f5d638d5b838ed9cb87`.
- The imported original CSV has 755 parsed rows. Join uses **exact symbol + ISIN + EQ series**, no name inference and no use of price outcomes.

## Genuine findings

| Fact | Count |
|---|---:|
| HG009 frozen names retained | **100 / 100** |
| Exact archived Total Market industry CSV matches | **46** |
| Outside this index subset or unmatched | **54** |
| Exact Financial Services matches (review caution) | **4** |
| Fully ready RM001-SC002 pre-cutoff sessions | **0** |
| Industry classifications authorized for investment models | **0** |
| Source-complete attributable-owner-cash valuations | **0** |

The four Financial Services matches are **ABCAPITAL, BAJFINANCE, M&MFIN, MUTHOOTFIN**. This flags them as cases where applying industrial NOPAT/ROIC is especially dangerous. It is **not** permission to apply a regulated-financial valuation from this rejected source-quality stage. Other companies outside the index subset may also be financial and must remain UNCLASSIFIED until verified.

## The important distinction

The CSV is original, hashable and corroborates 46 identities, but the SC002 source-quality ledger reports zero sessions that passed all original **source and before-18:30-IST** gates. The prior D015 parent had documented exceptions involving dummy securities and security-file correspondence. We must not promote a 46-row partial crosswalk into "official industry ready" or retrospectively apply it to October 14 selection.

The original `RM001-SC002` protocol remains unchanged. That workflow, not this analysis, owns the eventual source-readiness decision.

The P002 all-100 source manifest intentionally reported zero independently admitted industry records at its October 17 checkpoint. P003 adds **observed raw-CSV overlap evidence**, not 46 certified model features. These two statements are consistent.

## Reproducible verification

```bash
python scripts/materialize_l001_p003_industry_overlap.py --check
pytest -q tests/test_l001_p003_industry_overlap.py
ruff check src/marketlab/l001_p003_industry_overlap.py scripts/materialize_l001_p003_industry_overlap.py tests/test_l001_p003_industry_overlap.py
```

Machine-readable complete 100-row crosswalk:
`research/l001/p003-hg009-100-nse-industry-overlap-20261017.json`.

### Falsification and next data-source work

The current RM001 source gate must establish three READY_BEFORE_CUTOFF sessions, or a **separately preregistered valid source protocol** must be developed. Do not weaken its old acceptance thresholds. To resolve the 54 absent names, consult a separately captured, exact-identity official source of broader coverage without symbol-guessing or projecting today's industry historically.

Only after that classification gate can L001 request the correct per-company industrial or regulated-finance source documents. Original annual reports and all 252/504/756-session total-return observations remain separate blocked steps. No investment recommendation, changed cohort or live-capital permission.
