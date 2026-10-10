# HG007-P012: Exact Named Promoter Pledge in Original INOXGREEN NSE XBRL

**Primary issuer source, as-of 29 September 2026, publicly broadcast
8 October at 18:54:47 IST.** Research/governance evidence, not a
prediction, expected return or trading recommendation.

## Reconciled source chain

- Exact original NSE October 8 source master, SHA-256:
  dcdf2485a74174667ad230d5da200936d666a60137f62f06b52383b902d40e38
- Unique special shareholding report ID: 213525, dated 29 Sep
  (not a standard 30 Sep quarter-end filing).
- Original official NSE XBRL:
  https://nsearchives.nseindia.com/corporate/xbrl/SHP_1734551_08102026065442_WEB.xml
- Exact retained raw XBRL SHA-256:
  6c58845fa1b3f17c9c72b2466978bf8c69cece2436b1a92f7d40c4410f8b1822
- June official source: 30 June 2026 shareholding, last revised
  3 Aug, original XBRL declared promoter pledge FALSE.

The P012 code verifies exact original SHA-256 bytes and original
prior evidence receipts, rather than trusting a financial data website.

## Three independent XBRL contexts

| Original XBRL context | Issued shares | Pledged shares |
|---|---:|---:|
| Listed company, ShareholdingPattern_ContextI | 419,602,518 | 4,900,000 |
| Aggregate promoter group, ShareholdingOfPromoterAndPromoterGroup_ContextI | 225,317,291 | 4,900,000 |
| Named promoter Inox Wind Limited, OthersIndianShareholders_Context15 | 205,274,791 | 4,900,000 |

The separate original name fact
NameOfTheShareholder, context D_OthersIndianShareholders_Context15,
independently identifies **Inox Wind Limited** as the pledgor.

The original XBRL also reports **422,070,138 fully diluted shares**
as of 29 Sep, including **2,467,620** shares of outstanding
dilutive securities beyond current ordinary issued basic shares.

This confirms the previously hypothetical scenario in HG007-P008
**as an as-of-29-Sep reported figure**, but not as a guarantee that
nothing changed from 29 September to 11 October.

## Denominator semantics

The 4.9 million pledged shares correspond to approximately:

- **2.17% of the entire promoter group's holdings**;
- **1.17% of issued ordinary shares of the company**;
- **2.39% of Inox Wind Limited's own shares in INOXGREEN**.

The XBRL contains the corresponding rounded fractions 0.0217,
0.0117 and 0.0239. These are different denominators, and must
not be conflated. No gross source market-cap interpretation is
derived from promoter pledge alone.

The June report's no-pledge declaration plus 29 September yes
shows a changed reported governance position. It **does not
establish which day the pledge was created**, what debt it
secures, loan-to-value, default triggers, creditor recourse,
or what happened to the pledge after 29 September.

## Scientific and valuation state

A promoter pledge is a risk-diligence flag, not an automatic
causal forecast of negative stock returns.

No hypothesis, user allocation, survivor-conditioned special
situation probability, corporate-action-adjusted portfolio
return, EV/EBITDA fair value or trade authorization changes.

The correct subsequent diligence is to obtain any separately
required stock-exchange pledge creation and release filings,
and complete current Reg31 plus share changes and post-QIP
cash/debt before publishing a current October fully diluted
issuer capitalization.

## Reproduction

- src/marketlab/hg007_pledge_xbrl.py
- scripts/audit_hg007_pledge_xbrl.py
- tests/test_hg007_pledge_xbrl.py
- .github/workflows/hg007-pledge-original-xbrl.yml

Output on main:

research/hg007/inoxgreen-post-qip-special/original-promoter-pledge-v1.json

All issuer expected returns, stock price targets, portfolio
eligibility and live capital remain DISABLED.
