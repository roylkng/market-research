# L001 P005: Original NSE financial accounting-form guard

Research date: 2026-10-18. Source evidence is immutable [L001 P004](l001-p004-full-market-original-source-recovery.md), reproduced with 300 original XML SHA verifications and 400 exact XBRL numeric fact checks. P005 consumes that report by its **fixed report SHA**, not an invented ticker-based category.

## Observed filing-format split

The **original NSE annual and quarterly filing URL and XML archive types** consistently distinguish:

- **8 companies using the NSE NBFC-specific Ind AS reporting form:** ABCAPITAL, BAJFINANCE, EMKAY, IBULLSLTD, M&MFIN, MUTHOOTFIN, SATIN, SPANDANA.
- **92 companies using a general Integrated Filing Ind AS form.** Do not label these 92 as industrial companies without an official dated industry classification. General XBRL reporting format is an *accounting filing form*, not a sector license, business model, or regulatory clearance.

The October 16 NSE Nifty Total Market index crosswalk in P003 covered 46 names and identified only 4 Financial Services matches. It missed the other 4 NBFC-form issuers because that index-source subset did not cover every HG009 company. Thus **relying on index inclusion alone would under-detect specialist finance reporting needs**.

## Why this matters

For lenders/NBFC-form reporters, customer loan originations and deposit/funding movements may dominate operating cash flows; CFO-minus-PPE **must not** be ranked against manufacturing companies as distributable free cash or a quality factor. Large positive or negative raw CFO is not a valid buy/sell signal for financial institutions.

P005 uses the original filename only as a **one-way caution signal**:
- NSE NBFC original form => specialist credit/capital/investment economics REQUIRED.
- NSE general Ind AS original form => industry still UNCLASSIFIED, industrial valuation remains blocked.
- Missing/changed/contradictory annual and quarter original forms => fail the entire report.

This audit can be reproduced with:

```bash
pytest -q tests/test_l001_p005_source_form_gate.py
ruff check src/marketlab/l001_p005_source_form_gate.py scripts/materialize_l001_p005_source_forms.py tests/test_l001_p005_source_form_gate.py
python scripts/materialize_l001_p005_source_forms.py \
  --p004-source /tmp/l001-p004-all100-original-audit.json \
  --output /tmp/l001-p005-accounting-form-100.json
```

The PR workflow downloads the exact successful P004 original replay artifact ID `12111414537`. No 252/504/756-session returns, source-complete owner cash, fully diluted October shares, risk-adjusted expected returns or live-capital permissions are created.

**Next:** reconcile original industry and finance company credit/asset-quality data and require an independent cohort-wide owner-cash/financial-capital valuation before promoting any company. Do not treat static form detection as predictive alpha.
