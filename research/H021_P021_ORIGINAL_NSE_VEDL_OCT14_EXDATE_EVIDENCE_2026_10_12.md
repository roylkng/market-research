# H021-P021: Original NSE VEDL Dividend Ex-Date Source

Prepared 12 October 2026 IST, before the officially published 14
October VEDL ex-date. **Research source/date verification only.**

## Original pre-entry evidence

The frozen H021 cohort selected VEDL under the original 9 October EPS
revision rule. Original Vedanta Limited board filing, published by NSE
on 8 October, was available to research before the original 12 October
open and independently source-pinned under H021-P012:

- VEDL ISIN INE205A01025.
- Board approved a first interim FY27 dividend **INR 5/share**.
- Original issuer filing declared **Wednesday 14 October 2026 RECORD date**.
- Original issuer PDF SHA:
  abdd026339469b9e51ab75fb2a37551be23812dcc037c875759cd79a8e6cb364.

**A corporate board record-date announcement is not, by itself,
independent evidence of the stock-exchange ex-date.**

On 12 October the NSE's publicly available Corporate Filings/Actions
calendar already displayed VEDL as:

    Interim Dividend - Rs 5 Per Share | Ex-Date 14-Oct-2026

Public NSE front-end reference:

https://betanseapi.nseindia.com/companies-listing/corporate-filings-application

This protocol independently seeks the **original machine-readable NSE
equity corporate-action API** bytes, not an investor newsletter,
Nifty 500 index move or web screenshot.

## Exact acquisition and source contract

Original official URL, with date scope and exact VEDL identity:

https://www.nseindia.com/api/corporates-corporateActions?index=equities&symbol=VEDL&from_date=08-10-2026&to_date=16-10-2026

Use an ordinary public NSE filings-page visit to establish a public
web session, followed by one exact original action-JSON request.
Do not bypass 401/403/429, automatically switch host or data
vendor, follow redirects, fabricate source bytes or mask HTTP errors.

Raw JSON must be independently retained and SHA-256 verified.
A source match requires exactly one official VEDL EQ dividend row
reporting ₹5 with 14-Oct-2026 EX date, not a different amount,
class, company or ex-date. Any inconsistent/duplicate record,
missing official row or blocked response is **not verified**.

Actual UTC acquisition timestamps must be recorded. A report obtained
after 14 October NSE 09:15 IST may corroborate historic ex-date
but cannot be labeled independently captured *before* ex trading.

## Immutable source custody

- Pure parser: src/marketlab/h021_vedl_exdate.py
- Official source probe: scripts/acquire_h021_vedl_nse_exdate.py
- Tests: tests/test_h021_vedl_exdate.py
- GitHub Action: .github/workflows/h021-vedl-original-action-exdate.yml

On merge and a small bounded 12-14 October retry window, the workflow
runs the pure regression suite and attempts public original source
acquisition. Only a source-verified single matching event is anchored:

- research/prospective/h021/dividend-evidence/vedl-2026-10-08/original-nse-exdate-v1.json
- matching original raw NSE JSON under original-nse-actions/sha256/

On access blocked or malformed source, the workflow retains the
attempt and original status as a GitHub Actions artifact and does not
invent an event or push a verified source.

## What an ex-date confirms, and what it does not

The ex-date is a market-event timetable attribute, not a guaranteed
paper or actual holder's dividend cash receipt. The H021 open on
12 October is a *hypothetical original official-open price proxy*;
actual fills, order depth, settlement timing, hypothetical position
entitlement, cash payout date, taxes and reinvestment are unverified.

Dividend-adjusted VEDL shareholder total returns and the Nifty 500
price-index (not TRI) are still economically mismatched. Likewise
the other 9 selected stocks' future corporate-action windows remain
unreviewed for the frozen 20/60 completed-session evaluation.

This evidence acquisition does not revise the original H021 stock
selection, remove VEDL, assign expected returns, publish alpha or
enable capital.
