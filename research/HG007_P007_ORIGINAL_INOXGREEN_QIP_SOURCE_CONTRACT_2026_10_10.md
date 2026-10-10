# HG007-P007: Preserve Original September 2026 INOXGREEN QIP Filing

Status: **SOURCE ACQUISITION ONLY, NOT AN APPROVED FULLY DILUTED VALUATION**.
Frozen research date: 10 October 2026 IST.

## Material source issue

HG005-D001 used a March 2026 reported fully diluted share count from an
official XBRL, as frozen with 1 October 2026 ₹159 price. Subsequent
September 2026 INOXGREEN QIP share allotment changes basic equity.

Original public NSE issuer QIP filing of 30 September 2026:

https://nsearchives.nseindia.com/corporate/IGESL_30092026005646_IGESL_SE_Allotment_30092026_S.pdf

The original filing reports:
- Shares allotted on 29 September 2026: 18,110,473.
- Price: ₹165.65/share.
- Total QIP proceeds as disclosed: ₹2,999,999,852.45.
- Issued/basic ordinary shares BEFORE allotment: 401,492,045.
- Issued/basic ordinary shares AFTER allotment: 419,602,518.
- QIP allotment difference: exactly 18,110,473.
- The QIP issue was approved 29 September and filed 30 September.

BSE listing notice 20261001-8 reported that the new shares would be
admitted for trading 5 October. **Legal allotment and first exchange
listing are distinct dates.** The HG005 1 October benchmark reference
does not mean QIP shares were not yet legally issued.

The exact March 31 issuer shareholding source was:

https://www.inoxgreen.com/PDF/SHP_31.03.2026.html

That filing reported:
- Basic shares: 401,492,045.
- Employee options outstanding: 2,467,620.
- Total reported fully diluted shares: 403,959,665.

These options represent a **March 31 state**, NOT independently confirmed
options still outstanding on 29 September or 9 October.

## P007 custody contract

Source-only Python:

scripts/probe_hg007_qip_nse_original.py

Scheduled on merge and during October in:

.github/workflows/hg007-inoxgreen-qip-original.yml

The exact URL is hardcoded. No alternate host or document, cookies,
unverified redirect or access-control evasion is allowed. On HTTP 403
the attempt is documented as blocked, never represented as a successful
original. A fake 200 HTML page is rejected.

A candidate PDF must pass envelope and an exact three-page issuer,
allotment date, 18,110,473 issuance, 401,492,045/419,602,518 basic
capital and ₹165.65 issue-price text reconciliation. The original PDF
and original SHA-256 receipt are retained once, append-only. The
upstream source PDF remains the authority; no third-party text is
substituted as equivalent evidence.

## What comes next

The next separately versioned model should:

1. Recheck the exact original PDF bytes, page text, issue amounts and
   original XBRL used by HG005.
2. Preserve HG005 1 October ₹159 raw price and calculate a corrected
   POST-QIP BASIC MARKET CAPITALIZATION. Preserve the earlier ₹6422.96
   crore reported-March-FD figure as an immutable historical artifact.
3. Use the independent 9 October ₹128.92 NSE price only for a
   separately dated post-close sensitivity, not an Oct1 replacement.
4. Confirm current outstanding ESOP/option count and any intervening
   allotments before claiming post-QIP FULLY DILUTED capitalization.
5. Address QIP proceeds already used, consolidation, intercompany
   funding, third-party debt and minority claims before enterprise
   value or target price.

The September QIP shares were already allotted before the October
first price; the old March diluted denominator must not be
misrepresented as current shares.

No stock target, current fully diluted share count, prediction,
expected return, PF001 eligibility or live capital permission is
authorized by P007.
