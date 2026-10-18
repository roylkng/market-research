# L001 P011: Immutable original-document custody for two competing asset-value theses

**Research date:** 2026-10-18. This protocol captures issuer documents **now**, using actual capture timestamps. The original issuer-stated release dates must **never** be substituted for the moment the research system actually obtained a byte-identical copy. All long-horizon predictive claims, price forecasts and live capital stay disabled.

## Source-control purpose

The previous Zuari Industries (L001 P010) and Great Eastern Shipping (L001 P009/P010) memos used original online issuer PDFs but had incomplete byte custody inside GitHub. Preserve six independently retrievable official original PDF documents with SHA-256, page count, full raw bytes, verified selected text anchors and the real collection instant.

| Issuer | Original release-date claim | Dated original PDF |
|---|---|---|
| ZUARIIND | 14 Aug | [Q1 FY27 investor deck](https://www.zuariindustries.in/storage/uploads/images/1786947593.pdf) |
| ZUARIIND | 21 Aug | [17 Aug Q1 earnings-call transcript](https://www.zuariindustries.in/storage/uploads/images/1787307585.pdf) |
| ZUARI, debtor | 18 Sep | [₹214.50 crore ICD repayment](https://www.zuari.in/assets/files/ZACLDisclosureunderReg30-RepaymentofICDs-18-09-2026.pdf) |
| ZUARI, debtor | 30 Sep | [₹44 crore final ICD repayment](https://www.zuari.in/assets/files/Reg30RepaymentofICDsdtd30.09.2026.pdf) |
| GESHIP | 4 Aug | [Q1 FY27 consolidated NAV deck](https://greatship.com/upload/latest_announcements/Q1FY27_Updates_Presentation.pdf_(1).pdf) |
| GESHIP | 13 Oct | [First legal buyback-share extinction certificate](https://greatship.com/upload/investors/buyback_2026/1st_Lot_Buyback_Extinguishment_Certificate.pdf) |

The GH workflow `.github/workflows/l001-p011-issuer-pdf-custody.yml` independently downloads the above originals. It fails if the source domain redirects unexpectedly, PDF is damaged, required relevant evidence isn't extracted, or source bytes exceed the frozen size gate. No stock market API is used.

**The original financial-reporting July/August facts are not guaranteed financially current on the October 15 basic-share market price date.** The actual retrieval timestamp in this P011 is later than that market day and cannot be used as a historical first-seen model timestamp.

## Newly explicit economic caveat: Dubai repatriation collections

The original Zuari August 17 call transcript (published August 21), pp. 16–18, states:
- Management forecast **₹900 crore of profit repatriation in FY27**, with **~₹142 crore received** at the call. The **~₹758 crore balance is guidance**, not proof of settled cash.
- The Dubai property was handed over and ~**40–45% of customer collections remained outstanding**. Management believed demand notes had been raised after completion certification. That is a **collection/execution risk**, not a cash equivalent.
- June 30 real-estate segment assets around **₹770 crore**, including ~₹400 crore Dubai-related assets, are different accounting measures from the **₹900 crore FY27 repatriation guidance**. Neither figure can be mechanically added to a sum-of-the-parts valuation without tracing group ownership, original cost, debtor/customer cash, financing, remittance law and taxes.
- Management referenced South India property development-management projects and a gross development value of roughly **₹4,900 crore**. This **is not consolidated revenue**, and is not cash available to Zuari equity shareholders.

The September 18 and 30 counterparty exchange letters **do** show completed ₹258.50 crore ICD settlement in aggregate, a distinct observable realized financing event. Recovery replaces a receivable with cash, not new wealth. It may have changed collection-risk pricing if that risk was previously priced into equity, which must be studied rather than presumed.

## GESHIP original NAV scope

Issuer original Q1 deck shows a June 30 consolidated NAV **range ₹1,862–₹1,911**, not a precise single fair-value estimate. Original October 13 certificate separately establishes **1,858,941 legal share extinctions on October 10**, reducing basic shares to **140,908,220**. Cash spent on purchases and legally canceled shares must enter the *same-date* NAV bridge together to avoid overstating buyback accretion. Additional purchased shares not in a completed cancellation certificate must remain in the legal denominator.

## Interpretation and priority

These original reports support **catalyst diligence**, not proof of mispricing. A verified original document does not prove the asset's appraised value or business-cash recoverability. Three specific events can falsify the theses:

1. Dubai receipts fall significantly short of management's FY27 ₹900 crore projection or remain trapped in subsidiaries. Then Zuari's debt-relief narrative weakens.
2. Zuari's pledged listed interests cannot be released without material extra cash, losses, covenants or financing. Then headline listed gross mark-to-market overstates realizable shareholder surplus.
3. GESHIP's vessel NAV declines due to shipping-cycle normalization faster than share buybacks accrete NAV. Then its historical ~21% reported discount is not a margin of safety.

The next research stage needs independently archived FY26 annual notes, June-to-October debt and transfer receipts, pledge legal conditions, and an internally consistent **parent attributable** liquidation/owner-cash valuation. No historical HG009 factor will be re-selected using these October analyses. L004 model-time restrictions remain binding.

**This PR is source custody and hypothesis falsification, not new hidden-gem alpha.**
