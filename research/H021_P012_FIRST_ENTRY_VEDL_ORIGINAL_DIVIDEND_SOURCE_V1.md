# H021-P012: Original NSE Vedanta ₹5 Dividend Evidence

Status: **ORIGINAL FILINGS SOURCE CAPTURE ONLY, RESEARCH-ONLY**.
Prepared 12 October 2026. This does not change the prospectively frozen
10-stock H021 first cohort, its previous 9 October signal, or its outcome rules.

## Original pre-entry visibility

The exact original NSE 8 October corporate-announcement capture was sealed
before the planned H021 Monday 12 October 09:15 IST opening observation.

- Archived announcement:
  research/prospective/ss002-p001/2026-10-08-v1.json
- Exact Git blob SHA:
  123c858432d2f4af86d76792a85c727077ff7ec0
- Underlying original NSE API source SHA-256:
  aff6e8075d4f2b3067a2fa84349a484ed7ba225825397db6d1978ccea2718171
- Original NSE announcement ID:
  753e6a20e6f165677087990a6c35ec54971b034afa4bbb83ada5ab6c73135092
- Source originally published: **8 October 2026, 07:41:56 UTC (13:11:56 IST)**.
- Original NSE announcement API was independently captured:
  **9 October 2026, 17:28:32 UTC**, before Monday's official planned open.
- The original attachment URL was already in those immutable bytes:

https://nsearchives.nseindia.com/corporate/VEDL_08102026131108_SEIntimationOutcomeofBM1stInterimDividendsigned.pdf

An original filing first retrieved after the 12 October open is **not**
backdated and must not be described as a PDF that was locally cached or
reviewed before the open. The immutable exchange-publication and URL
metadata provide separate historical first-seen evidence.

## What the original *board letter* independently states

The one-page original NSE filing is Vedanta Limited's letter
VEDL/Sec./SE/26-27/108 of 8 October 2026.

The company declared its first interim dividend for FY2026–27:
- ₹5 per ₹1 face-value ordinary equity share;
- total indicated distribution approximately ₹1,955 crore;
- record date **Wednesday 14 October 2026**;
- board approval at **13:00 IST on 8 October 2026**.

**The board letter does not establish the ex-date.**
The NSE corporate-action calendar separately reports 14 October as an
ex-dividend date, but that calendar's source bytes and full exchange
action history are not certified by this document-capture step.

Neither declaration nor record date proves that an H021 research
observation could purchase at the official open, settle in time, or
receive money. The H021 cohort is research-only, not a portfolio.

## Original PDF acquisition contract

- Script: scripts/acquire_h021_vedl_dividend_original.py
- Workflow: .github/workflows/h021-vedl-original-dividend-source.yml
- Regression tests: tests/test_h021_vedl_original_dividend.py

The script must reproduce the exact archived NSE event from original
content-addressed gzip source bytes before touching the PDF URL.
The PDF host/path is fixed, HTTPS only, redirects not followed, no
attempt to work around 401/403/429.

An HTTP 200 must contain a valid minimal PDF envelope and exactly one
text-readable original issuer page with expected original date, name,
₹5 dividend, 14 October record date and 13:00 IST board approval.
These checks verify declaration source identity, not all external
corporate-action or cash-settlement facts.

Original PDF bytes, original source SHA-256, independent page-text SHA,
HTTP status, actual fetch UTC timestamp and first-seen original NSE
announcement anchor are retained. A blocked or malformed source stays
explicitly blocked and creates no successful PDF provenance claim.

On the next successful main workflow run, original bytes and receipt
are immutably anchored at:

research/prospective/h021/dividend-evidence/vedl-2026-10-08/

The action does not modify or replace the existing pre-entry secondary
risk alert:

research/prospective/h021/pre-entry-risk/2026-10-09-vedl-dividend-alert-v1.json

## Outstanding measurement gates

1. Independently verify NSE ex-date 14 October and the relevant share
   entitlement/settlement convention using dated exchange action data.
2. Verify share-class, stock splits, bonus/demerger and other
   entitlements over every future holding interval.
3. Distinguish price-only stock appreciation from cash-inclusive
   shareholder return, tax/reinvestment assumptions, and the Nifty 500
   price index versus TRI benchmark. Do not compare inconsistent bases.
4. Source the real 12 October NSE EQ official stock open and Nifty 500
   index observation **after** the completed market session. An
   observed NSE OHLC open is not a proven actual trade fill.
5. Resolve the 8 November Muhurat special-session and the separately
   verified 2027 exchange calendar before 20/60-session outcome dates
   can be published.

No ex-date/economic entitlement is inferred from the board letter.
No 20/60-session return, confidence interval, alpha discovery, stock
recommendation, portfolio eligibility or live capital is authorized.
