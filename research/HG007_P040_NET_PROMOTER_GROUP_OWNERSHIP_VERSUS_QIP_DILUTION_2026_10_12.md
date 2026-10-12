# HG007-P040: Original June-to-September Promoter Share-Count Reconciliation

Research-only as of **12 October 2026**. The purpose is to isolate
QIP denominator dilution from changes in *reported net promoter
holdings*, not to predict INOXGREEN stock returns.

## Original primary evidence

Two independently SHA-verified NSE Regulation 31 shareholding XBRLs
are already retained in the repository:

1. Standard **30 June 2026** report, source publicly broadcast
   **3 August 2026 11:36:18 UTC**, original SHA-256
   fcb8910121252da982dc38937f3b3fd012c15c51e43ea494a4342f7a4d7e3c47.
   Source:
   https://nsearchives.nseindia.com/corporate/xbrl/SHP_1706948_03082026041959_WEB.xml
2. Exceptional **29 September 2026** post-QIP allotment-date report,
   first publicly broadcast **8 October 2026 13:24:47 UTC**,
   original SHA-256
   6c58845fa1b3f17c9c72b2466978bf8c69cece2436b1a92f7d40c4410f8b1822.
   Source:
   https://nsearchives.nseindia.com/corporate/xbrl/SHP_1734551_08102026065442_WEB.xml

This P040 audit reads both exact original raw XML files and requires
the same promoter-group aggregate context and report-date instant,
share units, exact NSE listed-company symbol, issued-share and
fully diluted aggregate counts. It binds the older 4 October
GF001 28-company governance snapshot and later P012/P039
first-publication/pledge records to their original Git blobs.

## Reconciled facts

| Filed figure | 30 June 2026 | 29 September 2026 |
|---|---:|---:|
| Promoter group reported net shares | 225,317,291 | 225,317,291 |
| Total issued basic shares | 401,492,045 | 419,602,518 |
| Reported diluted shares | 403,959,665 | 422,070,138 |
| Promoter holding fraction | 56.12% | 53.70% |
| Official promoter pledge boolean | false | true |
| Group pledged shares | not inferred from absent June quantity field | 4,900,000 |

The **net reported promoter-group share-count change is exactly zero**.
The total issued share count increased **18,110,473** due to the
September QIP. Applying the original 225,317,291 shares to the two
respective denominators reproduces the reported ownership percentages
to the original filing's rounding.

Therefore the *reported ownership percentage decline* is explained by
denominator expansion, with **no observed change in net promoter group
shares between these two report dates**.

However, this is **not proof that no promoter shares were bought,
transferred, or sold in gross terms** during the interval. Such
offsetting flows, intra-promoter transfers, an older or subsequent
pledge creation date, and lending/encumbrance conditions cannot be
excluded by two end-of-period holdings.

## Governance and temporal integrity

The September post-QIP XBRL reports **4.9 million pledged promoter
shares** and a true pledged-share flag, versus a false flag in the
June XBRL. The first publicly seen special report was 8 October, so
an analyst running the original 4 October snapshot could not
legitimately have known these later reported pledge details.

The original 4 October source and the newer 8 October source
therefore remain **separate historical evidence states**, not
retrospective entry selection filters.

No filing in this P040 pair establishes the pledge's effective
creation date, lender, loan, cash collateral rights, whether it has
since been released, or changes after 29 September. **Current
12 October pledge/capital verification remains blocked.**

## Replay

- Source validator and computation:
  src/marketlab/hg007_promoter_net_ownership.py
- Deterministic CLI:
  scripts/reconcile_hg007_promoter_net_ownership.py
- Regression tests:
  tests/test_hg007_promoter_net_ownership.py
- Scheduled source-only CI on merge:
  .github/workflows/hg007-promoter-net-ownership.yml
- Output:
  research/hg007/hg007-p040-net-promoter-share-reconciliation-v1.json

Run:

    python scripts/reconcile_hg007_promoter_net_ownership.py \
      --output /tmp/ino-green-promoter-net-share-review.json

No market price, model fit, earnings forecast, completion probability,
liquidity assumption, updated buy recommendation or actual stock return
is created. This source audit **does not prove an investable edge**
and leaves portfolio and live-capital permissions false.
