# HG009 P030: original NSE industry evidence collection and forward-cohort readiness

**Method assembled:** 2026-10-21. **First HG009 research entry:** 2026-10-15. **Live capital:** prohibited.

## Why existing HG009 comparisons cannot claim predictive alpha

HG009's 100 selected NSE companies lost **1.4103%** on the original Oct 15 open-to-close source measure, versus **1.2690%** in one-signal controls and **1.0763%** in zero-signal controls. One highly correlated session is not evidence of stable negative alpha, but it is clearly **not evidence of positive alpha**. Retrospectively balancing growth buckets or introducing October 14 futures presence after the H1 result cannot rescue the old test.

The original HG009 P026 sector-source study correctly matched **142 of 300** original symbol+ISIN identities to an October 16 Nifty Total Market *index subset* source. It was dated after original October 15 entry, only covered a subset rather than the complete NSE issuer population, and did **not** independently establish first retrieval timestamps for pre-trade modeling. This means **zero verified pre-Oct15 sector-feature records**. Never count 142 as sector knowledge available at first entry.

## Exactly 300 original source-acquisition tasks

The audit retains every original NSE symbol+ISIN with its selected, one-signal or zero-signal arm. It produces an immutable source-acquisition queue:

| Original arm | Later October 16 provisional sector matches | Unclassified in subset | Minimum verified sector sources for next arm |
|---|---:|---:|---:|
| Selected 100 | 46 | 54 | 90 |
| One-signal 100 | 43 | 57 | 90 |
| Zero-signal 100 | 53 | 47 | 90 |
| **Total 300** | **142** | **158** | **285 / 300 overall** |

The new-trial target is at least **95% independently verified sector/industry coverage overall** and **90% within each arm**. Even in the *counterfactual* case where all 142 provisional Oct16 matches later receive genuine original-document and first-retrieval proof, at least **143 further identities** must be independently classified to meet the 285 total gate. Every row also needs independent float/size, accounting-regime, liquidity and risk/execution provenance.

Provisional matches are **not automatically admissible**. Their issuer classification may change with a corporate event. A present-day NSE sector table cannot be projected backward to an earlier date or used to prove what was knowable before the original Oct15 entry.

### Accepted future source process

For each originally missing issuer, obtain official NSE four-tier basic-industry classification or audited consolidated segment/annual issuer disclosure linked to its frozen symbol+ISIN. The source is not simply an industry name from a current internet article. Record raw source bytes, SHA-256, original URL, source financial period, **actual retrieval UTC timestamp**, published/effective date, group accounting basis and human or independently checked mapping.

For sources captured after October 21, they can become features **only in a subsequently frozen new cohort with a later entry date**, after they were actually available. They cannot reclassify the original October 15 HG009 prospective results. The method must also handle banks, insurers and NBFCs under separate accounting regimes, not an industrial CFO-multiple normalization.

Before independent trial activation, freeze the selection procedure, source metadata, sector/size/float match weights, standardized mean difference (SMD) balance tolerances, 60/120/252-session official NSE trading calendars, dividend and corporate action entitlement, bid/ask spreads and fill/impact model, plus a multi-entry holdout and family-wide trial accounting. The current original 300-company population remains a **development example**, not the new confirmatory cohort.

## Current program state

**BLOCKED_INSUFFICIENT_PREENTRY_PROVENANCE_AND_SOURCE_COVERAGE**

The P030 report makes that outcome machine-checkable. It contains no current or future stock prices, no returns, no Bayesian priors invented from a single trading date and no buy recommendations. Its source receipts pin the original P026 and P027 Git blob hashes. A failure is an actionable source-research backlog, not an excuse to weaken the evidence threshold.

Reproduce with:

    python scripts/materialize_hg009_p030_sector.py --check
    pytest -q tests/test_hg009_p030_sector_queue.py

Canonical file: research/hg009/hg009-p030-sector-proof-queue-v1.json. Relevant NSE methodology: https://www.nseindia.com/static/products-services/industry-classification and original research issue #507. The supporting statistical principle is avoiding data snooping and multiple test selection as described by White (Econometrica, 2000), and Sullivan, Timmermann & White (Journal of Finance, 1999). The current method is designed to avoid making an unfounded claim, not to establish the next cohort has alpha.
