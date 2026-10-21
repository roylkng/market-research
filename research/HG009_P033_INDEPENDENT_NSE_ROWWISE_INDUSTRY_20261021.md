# HG009 P033: independent row-wise NSE industry evidence

**Registered:** 21 October 2026. **Market use:** for a new future cohort only. **Capital:** disabled.

## Correcting the source bottleneck without weakening proof

P031 attempted to retrieve original NSE quote-equity company classifications but verified zero four-tier issuer records out of the original 300. P032 attempted the original NSE Nifty Total Market constituent CSV and recorded a blocked file-level validation. Its original parser rejected all ~750 issuer records if even one row had invalid industry, series, symbol, ISIN, or ambiguity.

A single invalid row must not contaminate other valid records. The separate P033 method therefore allows **strict row-wise admission** while preserving every invalid source row as an explicit negative evidence receipt. The P032 protocol and source records remain unchanged.

Official NSE source: https://nsearchives.nseindia.com/content/indices/ind_niftytotalmarket_list.csv

The Nifty Total Market index covers approximately 750 companies, not all NSE-listed companies. Its single Industry field is NOT proof of all four NSE industry classification tiers.

## Original source admission

Require original Symbol, ISIN Code, Industry, and Series columns, UTF-8 CSV and a plausible full-index byte count. Accept only unique, valid EQ rows with correctly formatted ISIN and an original nonempty industry cell. Duplicate symbols are rejected even if only one of their rows is otherwise valid. Keep row-numbered reasons.

The file-level guard additionally requires 650 to 800 original constituent rows, at least 650 unique completely valid EQ rows, and at most 20 rejected/ambiguous source rows. Underlying bytes are SHA-256 archived with actual retrieval UTC timestamp. A failed source is quarantined and signed, never silently replaced by third-party classifications.

Join every source record to the original 300-company frozen NSE symbol AND ISIN. Each of selected, one-lane and zero-lane comparison groups keeps exactly 100 original identities. All unmatched names stay missing.

## Causal firewall

October 15's first HG009 cohort already has its H1 outcome, in which the selected group lagged both comparison groups. No industry source first retrieved October 21 may be retrofitted into those original features or used to rescue their result.

A second, entirely independent study is required for any future claims. Minimum new industry coverage: 90/100 per arm and 285/300 overall. Even that source threshold is insufficient without independent size/free-float, beta/risk, four-tier industry, accounting-regime, share basis, corporate action, transaction cost and future model-freeze gates. Industry matching alone cannot imply statistically significant after-cost alpha.

Retained original source receipts: research/hg009/p033-totalmarket-rowwise. Offline replayer: python scripts/capture_hg009_p033_rowwise.py --check. Targeted tests: pytest -q tests/test_hg009_p033_rowwise.py.

**No current recommendation, portfolio, projected return or live-capital authorization.**
