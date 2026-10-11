# HG007-P011: Original NSE Sep-29 Diluted Shares and Promoter Pledge

Status: **SOURCE-VERIFIED ISSUER-REPORTED OWNERSHIP AT SEP-29, NOT CURRENT FAIR VALUE**.
Reviewed 12 October 2026 IST. No portfolio capital, expected returns or
downcase probabilities are promoted.

## What the previously missing source established

HG007-P010 retrieved the **original** NSE shareholding XML for INOXGREEN:

- NSE filing XBRL:
  https://nsearchives.nseindia.com/corporate/xbrl/SHP_1734551_08102026065442_WEB.xml
- Original XBRL SHA-256:
  6c58845fa1b3f17c9c72b2466978bf8c69cece2436b1a92f7d40c4410f8b1822
- Official report as-of date: **2026-09-29**, after the QIP.
- Filing first published: **2026-10-08 13:24:47 UTC**
  (18:54:47 IST, after the regular 8 Oct close).
- Original NSE master record ID: 213525.
- Source receipt:
  research/hg007/inoxgreen-post-qip-reg31/original-source-receipt-v1.json
- Original XML stored at:
  research/hg007/inoxgreen-post-qip-reg31/raw/sha256/
  6c58845fa1b3f17c9c72b2466978bf8c69cece2436b1a92f7d40c4410f8b1822.xml

Exact aggregate XBRL facts:

| Source-defined metric | Original issuer figure |
|---|---:|
| Fully paid ordinary issued shares | 419,602,518 |
| Outstanding ESOP shares | 2,467,620 |
| Fully diluted shares incl. ESOP/instruments | 422,070,138 |
| Current as-of-report warrants | None reported |
| Current as-of-report other convertibles | None reported |
| Promoter group shares | 225,317,291 |
| Promoter ownership (issued capital denominator) | 53.70% |
| Promoter shares pledged | **4,900,000** |
| Pledge as portion of promoter shares | **2.17%** |
| Pledge as portion of total issued shares | **1.17%** |

The issuer's explicit concepts NumberOfSharesOutstandingESOPGranted,
NumberOfSharesUnderlyingOutstandingConvertibleSecuritiesWarrantsAndESOP,
and NumberOfSharesOnFullyDilutedBasisIncludingWarrantsESOPAndConvertibleSecurities
match exactly, while its warrants/other-convertibles flags are false.

The promoter pledged-share count is an issuer-reported regulatory
ownership fact. This source does **not** establish the pledge lender,
security facility/collateral terms, creation date, margin-call terms,
release date or whether any change occurred after 29 September.
A pledge is not by itself a prediction of default or a mandatory sale.

## Corrected historical share denominator: two distinct clock dates

HG007-P008 previously used the 29-Sep issued **basic** count to
reconcile the frozen 1-Oct INR159 and 9-Oct INR128.92 observed closes.

P011 adds the source-verified, *as-of-29-Sep reported FD* count:

| NSE price session | Raw observed close | Post-QIP issued/basic cap | Sep29 reported FD cap |
|---|---:|---:|---:|
| 1 Oct 2026 | INR159.00 | INR6,671.68cr | INR6,710.92cr |
| 9 Oct 2026 | INR128.92 | INR5,409.52cr | INR5,441.33cr |

**Publication-time warning:** the September shareholding XML was
broadcast only **8 October after the close**. The FD values applied
to the Oct1 historical close are retrospective source reconciliation,
NOT evidence a research participant had that precise ESOP state
by 1 October. The same original Reg31 source was available before
the Friday 9 October close. Still, **subsequent** capital changes
by 9/12 October require their own verification; an as-of-Sep29
filing cannot be called guaranteed current indefinitely.

The original HG005-D001 1-Oct result used 403,959,665 March-era
FD shares and remains immutable for audit. It understated the
1-Oct value even relative to the *legally allotted basic shares*
after the 29-Sep QIP.

## What this does not prove

- INOXGREEN's outstanding current shares, ESOP exercises and any
  later new shares as of Oct12 or future purchase dates.
- Consolidated net cash/debt, net QIP cash use, Inox Green/Vibhav
  intercompany elimination and Authum outside claims.
- Completion of the legal WWIL business transfer; conditions
  precedent remained disclosed as pending on Oct7.
- WWIL O&M carve-out normalized EBITDA, receivables, maintenance
  capex, cash conversion and contract renewal economics.
- A completion probability, an enterprise value uplift or an
  expected price return.
- Terms or duration of 4.9m pledged promoter shares.

Because P011 contains historical source facts only, its reference
market-cap multiplication is **not** an execution price and does
not authorize a P/E, EV/EBITDA, buy/sell or capital allocation.

## Replay

- Source audit: src/marketlab/hg007_sep29_fd_pledge.py
- CLI: scripts/reconcile_hg007_sep29_fd_pledge.py
- Negative tests: tests/test_hg007_sep29_fd_pledge.py
- Workflow: .github/workflows/hg007-sep29-fd-pledge-review.yml
- New report (append-only after main merge):
  research/hg007/inoxgreen-post-qip-reg31/sep29-reported-fd-promoter-pledge-v1.json

The audit re-reads all exact original XML facts by concept,
contextRef and unitRef, pins the source SHA, verifies the P010
receipt and P008 legacy price/issued-share denominators,
reconciles promoter pledged shares and published percentages
within the precision of reported rounded fractions, and
fails closed on any changed original source or missing fact.
