# HG009 P016: NSE Q1 issuer original-byte source replay

**Protocol:** 16 October 2026. Research source attestation, not new share-price forecast or capital authorization.

P015 uses July Q1 FY27 *standalone, unaudited* original NSE issuer filings for **ACE** and **ACUTAAS** and the actual original NSE EQ October 15 close. P015 previously retained only manually transcribed Q1 share capital and pretax income cells. P016 verifies full original HTML bytes with actual capture UTC and immutable SHA-256.

## Exact issuer source contract

- [ACE Q1 FY27 NSE integrated IndAS filing](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_176136_20072026182618_iXBRL_WEB.html), July 20, 2026, original NSE symbol ACE, ISIN INE731H01025.
- [ACUTAAS Q1 FY27 NSE integrated IndAS filing](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_177818_24072026162914_iXBRL_WEB.html), July 24, 2026, original NSE symbol ACUTAAS, ISIN INE00FF01025.

For each filing, the original financial table must reproduce **exactly** the six frozen manually transcribed values: June paid-up basic share capital, nominal face value, revenue from operations, other income, profit before tax, and profit after tax. The same original page must affirm the original symbol+ISIN, June 30, 2026 end date, standalone reporting and unaudited quarter. A mismatched field, HTML identity, incomplete 403, redirect or missing record is an explicit blocked source receipt, never a verified valuation.

Original bytes are stored as deterministic gzip under research/hg009/p016-originals/by-symbol, content-addressed by SHA-256. Every retrieval attempt has its actual UTC timestamp, HTTP status and recorded source state. No earlier source is rewritten. An optional sealed two-company attestation summary appears **only when both original filings are independently replayable**.

## What this does not validate

Quarterly paid-up share capital as of June 30 is an **historical basic share figure**, not necessarily current October 15 fully diluted shares. The Q1 standalone earnings and FY26 consolidated operating cash flows use **different accounting periods and bases**. It is invalid to silently combine those into current parent normalized owner cash flow.

Current October debt, lease, cash, restricted investments, minority ownership, stock splits, share-based compensation, maintenance versus expansion capex, future utilization and all-in trading costs remain unresolved. The observed ACE approximately 42.5x FY26 CFO-less-PPE and ACUTAAS negative FY26 CFO-less-PPE are **reverse hurdles**, not proven margins of safety or 50%-annual-return opportunities.

No P016 result amends original P015 cohort or October 15 stock prices. No live orders, fair value, scenario probabilities or investment recommendations are published until separate audited source gates pass.

## Reproduction and test

Run the source retriever from a network-enabled, GitHub-authenticated runner, or the branch's source-freezer workflow. Source status: ORIGINAL_NSE_Q1_FULL_HTML_REPLAY_VERIFIED or a specific blocked reason. Always run the independent verification with --verify-only and confirm immutable first source receipts. Synthetic HTML tests check issuer/ISIN, multiple current-quarter financial rows, mismatch, HTTP 403 and original gzip tampering.


## Source freezer completed on October 16

GitHub original-source capture run **38854459012** completed and source-replayed both exact NSE HTML filings. Actual bytes were retained under the content-addressed P016 originals repository directories. The signed original-source receipt has SHA **38116caa87ff103519cf81ed271fc2af9b002284f108f6456156c7ef7044a4be**.

| Issuer | Actual original retrieval UTC | Original raw HTML SHA-256 | Financial row matches |
|---|---|---|---:|
| ACE | 2026-10-16T05:11:51.550128Z | 46d4940a2bf3ee97c3427fea3c66b8c864d2e44032679febfe0fde840dfe3f38 | 6/6 |
| ACUTAAS | 2026-10-16T05:11:52.016179Z | 5cfe54d47d782cf9feb469d8dc28bbfc70efbfa20fa9290975b33cba7445ea60 | 6/6 |

Original source evidence is now much stronger than the manual P015 transcriptions. Nevertheless, no new current fully diluted share count, normalized parent owner cash, or risk-adjusted value is claimed. The combined future-earnings and execution assumptions require separate evidence and red-team validation.
