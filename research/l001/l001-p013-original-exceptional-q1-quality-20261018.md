# L001 P013 | A falsifiable exceptional-profit screen across all 100 original Q1 FY27 NSE filings

**Investigation cutoff:** 2026-10-18. **Publication boundary for underlying filings:** no later than 2026-10-15T13:00:00Z. This is **post-hoc accounting diligence**, not a preregistered HG009 signal, forecast, or trading recommendation. Source panels were separately archived and re-audited later; original filing publication timestamps do not prove the model knew them at historical decision time.

## Why exceptional items are a crucial quality-control layer

Reported PAT can rise sharply because of a land sale, acquisition remeasurement, or a one-time gain. None proves that the recurring operating business became more profitable. But it is equally wrong to treat a one-off gain as economically worthless: its cash realization, taxes and balance-sheet reinvestment can still affect shareholder value.

Our new admission gate independently opens all **100 exact raw Q1 FY27 XBRL source files** from the GitHub archived [P004 original pack](https://github.com/roylkng/market-research/pull/475) and replays the 7 audited accounting cells retained by [P007](https://github.com/roylkng/market-research/pull/478). The P004 and P007 report SHA-256s are pinned, the original PDF/XML bytes are checked, and every issuer's original pre-exceptional PBT + signed exceptional value must equal the original reported PBT.

**Full archived cohort:**

| Status | Companies |
|---|---:|
| Frozen HG009 identities retained | 100 |
| Original exceptional-item bridge source-complete | 100 |
| Zero reported exceptional item | 93 |
| Positive exceptional item | 5 |
| Negative exceptional item | 2 |
| Positive exceptional item exceeds half of positive PBT, industrial NBFC-form excluded | **2** |

This 50% screen is a post-hoc **triage threshold only**, NOT a new return-predictive feature or discovered optimized investment threshold.

## The two major accounting alerts

| Original source issuer | Q1 FY27 revenue (₹Cr) | Pre-exceptional PBT (₹Cr) | Exceptional (₹Cr) | Reported PBT (₹Cr) | Reported PAT (₹Cr) | Exceptional/PBT |
|---|---:|---:|---:|---:|---:|---:|
| MMFL | 409.8963 | 35.0696 | +56.2520 | 91.3216 | 90.4244 | **61.60%** |
| MINDACORP | 1,846.3100 | 112.9800 | +123.9900 | 236.9700 | 206.2500 | **52.32%** |

**MM Forgings (MMFL):** NSE/BSE issuer clarification dated **August 15, 2026** attributes ₹56.25 crore exceptional reported profit to the sale of land near **Oragadam, Chennai**. This is an asset realization, not ordinary forging-product revenue. The issuer describes the amount as net of tax in its separate clarification, while NSE integrated XBRL tags the positive value as `ExceptionalItemsBeforeTax` and the PBT bridge adds it directly. **Do not subtract one tagged amount from PAT blindly or assume the form's label reconciles tax treatment.** Preserve the statement and original clarification as two distinct evidence claims. Issuer letter reproduced by NSE/BSE announcement archive: https://www.bazaarwatch.com/announcement/77637/mm-forgings-limited-general-updates .

**Minda Corporation (MINDACORP):** Its Q1FY27 reported exceptional value in the integrated source is **₹123.99 crore**, while the issuer's earnings release reports an approximately **₹106 crore post-tax gain** related to consolidation of **Minda VAST**. The difference between a statement line item and issuer post-tax gain is precisely why this gate never manufactures normalized PAT. Minda also reported underlying revenue growth and EBITDA growth, so the business may have genuine improvement despite the accounting gain. See issuer relations https://sparkminda.com/investor-relations/press-release and contextual results review https://www.kotakneo.com/news/stocks/minda-corporation-q1-results-fy27-profit-revenue/ . Original issuer exceptional-gain supporting note and after-tax statutory reconciliation remain a follow-up source requirement.

Both cases demonstrate that headline Q1 PAT growth can be materially different from a normalized business-profit trend. The reported Q1 PBT-before-exceptional value is **not** automatically standardized operating EBIT, after-tax owner cash or annual recurring profit.

### Remaining five nonzero smaller or negative exceptional entries

| Source issuer | Signed Q1 exceptional ₹Cr | Critical nuance |
|---|---:|---|
| HTMEDIA | +1.1800 | Other-income/PBT still exceeds 100%, separate from exceptional item |
| SANDESH | +0.0728 | Tiny exceptional, but large financial other-income exposure needs attribution |
| ZUARIIND | +4.8125 | Holding-company portfolio and dividend economics dominate cash reconciliation |
| NIITLTD | −1.5220 | Negative exceptional expense makes headline PBT smaller |
| AMBUJACEM | −24.0000 | Negative exceptional, not a positive PAT booster |

Many firms with exceptional zero still require other-income, subsidiary/minority, discontinued-operations, inventory, share-capital and cash-flow scrutiny.

## Code/CI acceptance contract

- `src/marketlab/l001_p013_exceptional_profit.py`: hash-and-identity sealed original 100-file replay, source-time matching, PBT algebra, negative/positive/zero flags and null normalized profit.
- `scripts/materialize_l001_p013_exceptional_profit.py`: accepts exact P004 and P007 original workflow archives, reopens raw source XML, and emits reproducible machine-readable 100-name report.
- `tests/test_l001_p013_exceptional_profit.py`: adversarial tests for numerical reconciliation, NaN/Inf, source spoofing, financial-company caution and failure to invent after-tax normalization.
- `.github/workflows/l001-p013-exceptional-profit.yml`: independently verifies **100 original Q1 XML SHA-256s** and **700 source numeric cells** from immutable pinned artifacts, publishes digest-bound report, and changes no frozen selection/return ledger.

## What this teaches the investment engine

1. Do **not** equate exceptional-item concentration with a company being bad or good. Disclosed gains can be genuine realizable wealth but should not be capitalized as recurring operating profit.
2. Separate PAT *including* exceptional items from earnings **before the exceptional line**, then independently reconcile tax, minority and accounting notes before calculating attributable operating/owner earnings.
3. A positive 52–62% exceptional-to-PBT share invalidates naive extrapolation of headline PAT into 1–3-year owner cash.
4. Evaluate whether a proposed fundamental signal still has explanatory value after excluding corporate asset sales, acquisition-remeasurement gains, and denominator dilution. Require an untouched new prospective protocol and future actual returns before claiming alpha.

**Capital-eligible firms from this output: 0. Expected return estimates: null. Original HG009 experiment unchanged.**
