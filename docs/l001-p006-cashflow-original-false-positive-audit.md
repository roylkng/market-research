# L001 P006: Original XBRL cash-flow anomalies and false-positive diagnosis

Research date 2026-10-18. **Post-hoc source audit, NOT a frozen HG009 model update or a buy list.** Source inputs: exact original 100 FY26 annual XBRL documents from signed L001 P004 report, already independently verified as 300/300 original-source files and 400/400 core numeric facts. All L001 P006 outputs remain source-only, with no investment recommendations or future-return claims.

## Key original-source falsification: PNCINFRA

Original NSE FY26 consolidated filing (19 May 2026): https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_1669538_19052026074756_WEB.xml, source SHA `4b56fbaca0349ed6d009c1976c37e4d5faad76d58e425cf374d1102e18b71ddc`. Direct original `FourD` INR XBRL contexts:

| FY26 source or illustration | Amount ₹ crore |
|---|---:|
| Operating cash flow | 4,592.9651 |
| PPE cash purchases | 326.0076 |
| Naive CFO less PPE | 4,266.9575 |
| Receivable-reduction cash adjustment, XBRL `AdjustmentsForDecreaseIncreaseInTradeReceivablesNoncurrent` | **4,146.1024** |
| CFO with *just that one* adjustment removed, arithmetic only | 446.8627 |
| CFO-minus-PPE with that adjustment removed, arithmetic only | **120.8551** |

P014 original NSE price October 15 ₹143.01 and historic issued-share count 25.6539165 crore yield illustrative basic cap ~₹3,668.77 crore. Thus naive FY26 CFO−PPE / basic cap **116.31%** versus single-receivable-component-removed sensitivity **3.29%**. These are **not owner-cash yields**, especially because the receivable-reduction may include concessions or disposed subsidiaries, other working-capital movements remain, and the share denominator is not fully diluted.

The significant FY26 cash receipt from trade receivables and multiple subsidiary disposals should **not** be extrapolated as recurring operating earnings. The original filing's equity/concession disposal accounting needs separate review. This case invalidates simplistic high-CFO search ranking, without proving the stock overvalued.

## Second trap: OIL zero reported PPE in generic XBRL concept

Original NSE Oil India FY26 consolidated filing: https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_1666714_13052026084312_WEB.xml.

Its generic selected XBRL purchase-of-PPE concept in the independent FA001 source panel is **zero**, while the same original FY26 filing reports net investing outflow **₹10,381.37 crore**, including `OtherInflowsOutflowsOfCashClassifiedAsInvestingActivities` **−₹11,396.33 crore**. This means `CFO - standard PPE line` mechanically equals CFO ~₹10,683.75 crore, but clearly **does not prove the company's actual sustaining and exploration/development capital spending was zero**. Fiscal consolidated upstream oil accounting can include exploration and development cash in other investing taxonomy. Independently reconcile annual-report capital expenditure before using the ratio.

Neither zero standard-tag PPE nor nonzero other investing automatically determines normalized owner cash. Do not mechanically subtract *all* net investing either, since investments/deposits may be financial assets.

## Third case: RPOWER needs debt/earnings reconciliation

Reliance Power original FY26 consolidated NSE XBRL shows CFO ₹2,824.36 crore, PPE ₹115.93 crore and financing cash outflow ₹1,827.76 crore. FY26 PBT was negative, with substantial noncash depreciation, financing cost and impairment adjustments. A raw CFO-minus-PPE above ₹2,700 crore **cannot be equated with distributable shareholder profit or value**. Debt service, asset cash restrictions and financing claims remain decisive. This is a source-led research caution, not a ranking.

## Implementation scope

- `src/marketlab/l001_p006_cash_anomalies.py` reads the exact FY26 original XML per issuer for *all 100*, by pinned P004 SHA and original-XML SHA. It emits the original CFO, pre-tax operating cash, current and noncurrent receivable cash adjustments, inventories, payables, investing cash, unusual generic investing movements and PPE sales/purchases.
- Missing original tagged values are **null**, not zero; contradictory original values fail closed.
- It records **only an algebraic "remove observed receivable adjustment" sensitivity** when both current and noncurrent adjustment values exist. That arithmetic is not sustainable earnings.
- `.github/workflows/l001-p006-cash-anomaly.yml` downloads the exact successful P004 workflow artifact `12111414537` and reproduces all 100 source diagnostics.
- Unlike H004 or other HG009 frozen experiments, no score, rank, new buy candidate, return attribution or altered cohort is created.

## Next causal economic work

1. For high provisional cash yields, compare FY24, FY25 and FY26 complete source-original statements, attrition from disposals/mergers and cash-conversion persistence. A single year must not define normalized owner cash.
2. Reconstruct working-capital and asset investment **independently** from generic XBRL selected PPE. Detect exploration/capitalized development, lease, intangible and acquisition cash not in a common PPE tag.
3. For NBFC-format reporters, retain the separately merged P005 specialist accounting gate.
4. Only after independent owner-attributable cash, post-report dilution, corporate actions and executable pricing are reconciled should L001 proceed to *prospectively frozen* 252/504/756-session factor tests with controls.

**Conclusion:** More XBRL records create opportunity for deterministic research, but automatic ranking by CFO-minus-PPE produces severe false positives. The PNCINFRA and OIL source facts demonstrate two distinct failure modes.
