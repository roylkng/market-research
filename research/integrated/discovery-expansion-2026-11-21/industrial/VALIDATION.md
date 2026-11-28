# Validation and unresolved limits

## Completed checks

1. Matched each reference quote to the original NSE EQ row and exact ISIN. Preserved the full bhavcopy byte hash. No aggregator quote replaces the official price.
2. Read PIX consolidated results, balance sheet and cash-flow columns visually from the original PDF. Verified annual cash-flow FVTPL loss and the exact share-count note visually.
3. Resolved the ₹0.11 lakh unpaid allotment-money difference. Share count uses 13,625,200 issued shares, not net paid-up capital divided by face value.
4. Built TTM using FY26 plus H1FY27 less H1FY26. FVTPL gains and losses are handled symmetrically. All other income is excluded from core EBIT and the FY26 FVTPL expense is restored, producing ₹168.3463 crore core EBIT.
5. Used source-period cash capex, including intangible cash spending. TTM CFO ₹155.5851 crore less capex ₹16.9521 crore and interest ₹2.7688 crore produces ₹135.8642 crore. This is a historical cash measure, not a forecast of maintenance cash flow.
6. Funded growth and maintenance spending separately, plus operating working capital and cash reserves. Existing provisions are reserved from opening financial assets. No future provision addback is used.
7. Debt is repaid with cash in year two. Interest is charged while outstanding. Terminal debt is zero and repayment is not deducted twice.
8. Executive pay and related rent remain within operating expenses and margins. They are not deducted a second time from cash or equity value.
9. Cash retention, treasury income, dividends and debt repayment reconcile in every model year. Terminal cash is added once, separately from operating profit value. Treasury earnings are not included in the terminal operating multiple.
10. IRR independently satisfies zero present value of the specified per-share investor cash flows. Every scenario has zero unfunded cash gap under the modeled capital needs. This is an arithmetic and funding check, not evidence that any forecast will occur.
11. Full-treasury-credit, current-margin, higher-growth and more-productive-capacity sensitivities test whether conservatism is manufacturing the WATCH verdict. The 10% growth/current-margin case supports a current-price upgrade.
12. Older data include a difficult spending year and subsequent recovery, plus uneven later sales. The record is labeled unblinded. No historical stock return or retrospective purchase is claimed.
13. Source manifests rehashed successfully from captured bytes. Failed downloads have no accepted hash or source-content claim.
14. A separate analyst reproduced the base return and terminal price and checked capital intensity. Implied net PP&E/sales is about 41.9% in year five versus 41.7% at entry. Working capital reaches the assumed 34%. The review prompted explicit disclosure that 16× terminal NOPAT is about 24.1× funded year-five owner cash and an isolated multiple sensitivity. This supports funding coherence, not forecast accuracy.

## Remaining economic uncertainty

- The company does not separately disclose maintenance capex or a verified current utilization figure in the sources used. Capital-intensity assumptions can be wrong.
- Mutual-fund asset composition and realization taxes are not fully resolved. The portfolio and terminal cash discounts are disclosed analyst assumptions.
- September ownership original download was blocked. March ownership is the accepted primary figure. The issuer-linked September file and secondary references are not silently promoted to original accepted evidence.
- Latest H1 results and inspected issuer disclosures support the current share basis. A complete original corporate-action feed through the reference date was not captured. No actual execution is authorized by this analysis.
- Customer replacement share, retention, concentration and product win/loss economics were not independently established.
- One day's liquidity does not establish position capacity.
- Terminal operating multiples, growth, margins and treasury accessibility dominate long-term returns. The results are scenarios, not probability estimates.
- No current portfolio-level opportunity-cost ranking or personalized allocation is claimed by this industrial lane.

## Reproduction

```bash
python calculate.py
```

The script uses the Python standard library and reads local `inputs.json`. The resulting numerical schedules overwrite `outputs.json` only within this case directory. The analyst decision and evidence notes are separate from that mechanical output.
