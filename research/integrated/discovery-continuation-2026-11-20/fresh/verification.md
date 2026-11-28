# R Systems verification record

Date: 20 November 2026. This log records performed checks, not intended work.

## Original bytes and source scope

Downloaded original annual, exchange-signed H1 and nine-month results, issuer Q3 press release and presentation, filed call transcript, acquisition terms and postal ballot. Preserved source URLs, retrieval times, byte lengths and SHA-256 hashes. Recomputed hashes from all 16 successfully retained fresh-discovery original files before writing `source_receipts.json`.

Failed issuer routes for eClerx were replaced by successful NSE originals. The BSE H1 R Systems route failed, then the NSE signed PDF succeeded. OFSS remains web-readable original text without locally retained original PDF bytes. Failure entries remain visible and are not upgraded to verified status.

The 19 November price row was supplied by the parent agent's official NSE bhavcopy collection. This agent read the local original-derived record and checked symbol RSYSTEMS, series EQ, ISIN INE411H01032, close ₹242.50, traded shares 242,178 and traded value ₹58,091,478.55. The last-traded price of ₹247.35 is different and was not substituted for the close. One day's turnover does not establish executable position size.

## Visual PDF inspection performed

Each page below was rendered with Poppler and its image was opened and inspected. Financial statement amounts are ₹ million and were divided by ten to obtain ₹ crore.

| Original file | Physical PDF page | Visually verified content | Retained image filename |
|---|---:|---|---|
| rsystems_h12026_signed_nse.pdf | 7 | Consolidated H1 2026/2025 cash, separate PPE and intangible purchases, full leases, financing interest, dividend and prior-period columns | rsystems_h1_cash.png |
| rsystems_fy25_ar.pdf | 226 | Consolidated CY2025/2024 operating cash and investing cash, including acquisition and asset proceeds | rsystems_ar_cash-226.png |
| rsystems_fy25_ar.pdf | 227 | Financing cash, debt issues and repayments, leases, interest and dividends | rsystems_ar_cash-227.png |
| rsystems_9m2026_signed.pdf | 3 | Consolidated owner PAT, nil NCI profit allocation, EPS, RSU-relevant denominator and hedge OCI | rsystems_9m_profit.png |
| rsystems_q32026_pr.pdf | 7 | September cash, bank balances, NCI, equity, borrowings and lease liabilities | rsystems_q3_balance.png |
| rsystems_fy25_ar.pdf | 276 | Novigo ₹400cr cash, ₹192.388cr CCPS, purchase allocation, contributed and pro-forma revenue | rsystems_ar_novigo.png |
| rsystems_fy25_ar.pdf | 251 | Eight-million-share incentive-plan capacity and 100,137 shares issued during 2025 | rsystems_ar_rsu.png |
| rsystems_fy25_ar.pdf | 255 | ₹275cr NCD, 9.75% coupon, semiannual principal beginning month 30, lease payment reconciliation | rsystems_ar_debt.png |
| rsystems_novigo_terms.pdf | 10 | Eight times average FY26/FY27 EBITDA less upfront cash formula for additional stock consideration | rsystems_novigo_formula.png |
| rsystems_q32026_presentation.pdf | 4 | Quarterly EBITDA bridge, operations −₹3.3cr and currency +₹7cr | rsystems_q3_fx.png |
| rsystems_q32026_presentation.pdf | 5 | Nine-month EBITDA bridge, operations +₹41.2cr and currency +₹78.7cr | rsystems_9m_fx.png |

Images are in `work/nov20/fresh/visual/` from the workspace root. Their hashes are also in `source_receipts.json`. The annual PDF text layer duplicates portions of its cash tables. Rendered page inspection, rather than the duplicated text order, resolved period and line placement.

## Correction captured during review

An initial H1 working calculation treated ₹13.031 crore as total capex. The signed statement separately reports ₹2.039 crore intangible purchases. Final total capex is ₹15.070 crore and residual cash ₹120.819 crore. The correction was sent to the parent before model construction. No final model uses the earlier ₹122.858 crore residual.

## Calculation and ownership checks

Executed `rsystems_model.py` successfully. Its assertions verify repayment of all ₹275 crore NCD principal, no debt remaining at exit, cash ledger conservation and funding above the specified operating floor for each supplied scenario. Per-share cash flows include distributions only once and deduct them from retained cash.

Issued shares plus remaining authorized plan capacity plus Velotio OCRPS are 131,464,278 before Novigo. No second subtraction of Novigo NCI or Velotio's historical carrying value occurs. Existing incentive dilution is not also deducted as recurring cash. A separate future compensation cycle is explicitly modeled and stressed.

The independent reviewer used its own reconstruction and matched all three scenario IRRs and tranche-interest arithmetic. This is a named peer arithmetic and evidence check. It is not an unbiased market test or a second independent opinion about the future. See `../independent/rsystems/rsystems_independent_review.md`.

## Remaining limitations that affect interpretation

- Current consolidated growth cannot be cleanly split into organic growth, Novigo and currency from the public data reviewed.
- Novigo's exact future swap ratio is unannounced. The modeled ₹85 crore average earnout EBITDA and assumed conversion prices are scenario inputs. They are not current verified Novigo financial results.
- Novigo FY2025 acquisition-deck revenue and annual calendar-year pro-forma disclosure do not reconcile without more scope/period detail. Both are preserved.
- ₹346.399 crore reconstructed cash differs from management's net ₹348.7 crore by ₹2.301 crore. The model uses the lower reconstruction and a further ₹2 crore reserve.
- Latest signed cash is H1 CY2026. September cash balances come from the original issuer press release, not an invented nine-month cash-flow statement.
- Full existing incentive-plan capacity is a ceiling. It is deliberately more than certain current vested or granted shares.
- Terminal multiples, compensation replacement, working capital, maintenance/growth capex split, operating cash floor and Novigo conversion values are assumptions with sensitivities.
- The terminal base values year-six cash. The comparable year-five-cash result is separately disclosed.
- Forecast interest uses day-weighted annual periods, not exact quarterly coupon cash dates.
- Audit-trail remediation, current pledge status, independent customer checks and management succession depth were not certified.
- No original-source event census for every corporate announcement through 20 November was performed. The case is current through the specifically listed November originals.
- No statistically calibrated probability, historical strategy alpha, benchmark-relative return or future outcome is claimed.

No frozen experiment, older judgment, root handoff, journal or branch state was edited by this agent. Root owns integration and publication.
