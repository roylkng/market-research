# HG007 P028: NSE Alternative Original for June ANANTRAJ QIP Cash Evidence

Date: 11 October 2026 IST.
Status: **OFFICIAL SOURCE CUSTODY, NOT A CERTIFIED DEMERGER CASH BALANCE**.

## Why this follow-up is necessary

P027 looked up the original BSE listing attachment for Anant Raj's
8 August 2026 Infomerics monitoring report (quarter 30 June 2026).
GitHub Actions recorded an actual HTTP **404** from the BSE AttachLive
URL, retained as an independent original-source acquisition failure.
No BSE original was falsely saved, and no 404 bypass was attempted.

We separately located the same filing on another authoritative
exchange's *own published URL* through its discoverable original
announcement on 8 August at 18:23 IST:

https://nsearchives.nseindia.com/corporate/ANANTRAJ_08082026182321_Intimation_Monitoring_Agency_08082026.pdf

The original exchange PDF has **21 pages** and is independently
accessible to public document readers. P028 treats the NSE source
as a separate original document, not a redirect, a guessed
BSE URL, a replaced BSE failure record or a third-party transcript.

## Original-report numerical context (pending custody replay)

The original exchange publication includes at 30 June 2026:

| Monitoring object, INR crore | Allocated | Cumulative use | Unused |
|---|---:|---:|---:|
| Data-centre subsidiary | 440.00 | 81.26 | 358.74 |
| Other company construction | 164.40 | 9.99 | 154.41 |
| Land and land rights | 185.00 | 70.92 | 114.08 |
| Loan repayment | 125.00 | 125.00 | 0 |
| General corporate purposes | 157.80 | 95.87 | 61.93 |
| Issue expenses | 27.80 | 26.97 | 0.83 |
| TOTAL gross QIP | 1100.00 | 410.01 | 689.99 |

The original-page location is PDF pages **10–14** (1-based), with
the data-centre category subtotal on **page 12** and overall
total on **page 14**. The original cost objects are on pages 9–10.

The monitoring report, page 8, specifically notes
**commingling of QIP funds in SBI cash-credit/current accounts**,
with the monitoring agency relying in part on CA certification
because the QIP was not spent only from a segregated account.

Therefore:
- ₹358.74cr is **earmarked, unutilized as of June30**, not
  certified bank cash unencumbered on October11;
- ₹81.26cr is **reported historical funds invested toward cloud
  subsidiary**, not confirmed newco standalone equity/FCF;
- ₹331.25cr of the total ₹689.99cr unused allocation is for other
  issue objects, and must **not** be assigned to Ashok Cloud as
  special-situation free cash.
- The original scheme's clause 1.13 can route related QIP funds
  and general-purpose debt into the undertaking, but it does not
  provide a **quantified amount already legally transferred**.

No QIP money shall be counted twice across parent and resulting
cloud shareholder value.

## Evidence protocol

P028 source:
- scripts/probe_hg007_anantraj_june_qip_nse_original.py
- tests/test_hg007_anantraj_june_qip_nse_original.py
- .github/workflows/hg007-anantraj-qip-nse-original.yml

On merge, an independent GitHub Actions run fetches the **exact
hardcoded NSE 21-page PDF**. It checks original source SHA,
issuer, quarter, original agency and page-text identity, then
retains the full original PDF by SHA-256 with an independent
receipt. The separate BSE 404 run remains archived; automatic
BSE retries are disabled, though manual BSE source review is
still possible.

Original packet (once retrieved):
research/hg007/anantraj-qip-monitor-june2026/nse-original-receipt-v1.json

Original bytes:
research/hg007/anantraj-qip-monitor-june2026/nse-original/sha256/

## Review still necessary

P029 must reconcile exact page-12 through page-14 monitored
object balances with page images and a strong arithmetic check,
distinguish project investment versus underlying asset capex,
and join cloud-specific ₹440/₹81.26/₹358.74 to the already
source-verified 48-page demerger legal asset/debt transfer rules.

The monitoring agency explicitly does not perform a full
independent financial audit. Bank balances, asset values, pro
forma liabilities, minority stakes and final legal transfer
remain unverified. No stock-return or investment capital
approval is issued.
