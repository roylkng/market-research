# HG007-P008: INOXGREEN Post-QIP Dated Market-Capitalization Correction

Research-only, **10 October 2026**, before any investment expected-return
model. Replaces no frozen HG005 or SS002 source outcome.

## Original source chain

**Original 29 September QIP filing** (filed 30 September) is retained:

research/hg007/inoxgreen-sep2026-qip/raw/sha256/cd1bee4fe84805e2ecbb274ebfedc74b632ad1c50907e694e58ba2f6d43470ee.pdf

- Exact NSE original PDF SHA-256:
  cd1bee4fe84805e2ecbb274ebfedc74b632ad1c50907e694e58ba2f6d43470ee
- Original NSE URL:
  https://nsearchives.nseindia.com/corporate/IGESL_30092026005646_IGESL_SE_Allotment_30092026_S.pdf
- Source original size: 309,090 bytes, exactly three pages.
- Shares issued to 20 qualified institutional buyers: 18,110,473.
- Share issue price: INR 165.65.
- QIP proceeds as issuer-disclosed: INR 2,999,999,852.45 gross.
- Basic shares: 401,492,045 before, **419,602,518** after allotment
  on **29 September 2026**.

The old HG005-D001-v1 record is preserved, with historical price
session **1 October 2026** and original share denominator source
GF001-D002 XBRL:

- Original published official March 31 issuer shareholding:
  https://www.inoxgreen.com/PDF/SHP_31.03.2026.html
- March 31 basic shares: **401,492,045**.
- March 31 reported outstanding ESOP options: **2,467,620**.
- March 31 reported fully diluted shares: **403,959,665**.
- Frozen 1 October NSE close: **INR 159**.
- Original frozen HG005 reported FD market cap:
  **INR 6,422.9586735 crore**.

The original market cap can be reproduced exactly:

403,959,665 * INR 159 / 10,000,000
= INR 6,422.9586735 crore.

**This is March-era fully diluted shares valued at an October price.**
QIP had already been allotted two days before the October price session,
although exchange trading admission for the new shares was scheduled
from October 5. The old label 'current fully diluted market cap' is
not valid for a prospective October investment decision.

A separately frozen SS002-P007 official Oct 9 NSE EQ close of
**INR 128.92** is available with original NSE UDiFF SHA-256
8adbb3410c8cf4372290484a9b1798490ef279d30fc2439c93f082cc20ed198c.

## Mechanical correction, not an estimate of fair value

Use only the **post-QIP September 29 ISSUED basic** count,
419,602,518 shares.

| Session | NSE observed close | Old March FD-based value | Post-QIP basic reference |
|---|---:|---:|---:|
| 1 Oct 2026 | INR 159.00 | INR 6,422.96 crore | INR 6,671.68 crore |
| 9 Oct 2026 | INR 128.92 | NOT updated under frozen HG005 | INR 5,409.52 crore |

At the same 1 October share price, HG005 understates market
capitalization by at least **INR 248.72 crore versus already allotted
September 29 basic shares**, or **3.8724% relative to its old base**.

Applying the observed 9 October price to the dated Sep 29 issued
share base gives **INR 5,409.52 crore**. This is a mechanically dated
reference, **not** proof that no further equity or option exercises
occurred by 9 October.

The simple raw 1-Oct/9-Oct price move is about -18.92%. It is not
a realized H021, HG005 or portfolio holding-period return and does
not establish an alpha, execution fill or corporate-action-adjusted return.

The reported INR 550 crore WWIL payment represents about:

- 8.56% of the old 1 October March-FD market cap;
- **8.24%** of the corrected 1 October post-QIP BASIC market cap;
- **10.17%** of the 9 October post-QIP BASIC share-price reference.

These are **consideration-to-market-cap ratios only**, not acquired
earnings, net enterprise value gains, minority-attributable cash flows
or stock-upside predictions.

## Crucial incomplete FD and financial claims

March reported outstanding options were 2,467,620. If those
same options all persisted after QIP without any cancellations,
exercises, new grants or other issuances, an **illustrative** share
count would be:

419,602,518 post-QIP issued + 2,467,620 March options
= 422,070,138 illustrative shares.

That would imply INR 6,710.92 crore at October 1 price and
INR 5,441.33 crore at October 9 price.

**This is not verified current fully diluted equity.** No claim
that the September 29 or October 9 ESOP balance is unchanged
has passed an original-source shareholding-pattern audit.

The QIP raised around INR 300 crore in gross proceeds. No balance
sheet net-cash addition is assumed: issue fees, actual deployment,
existing financing, purchase consideration and group intercompany
funding must be reconciled. QIP proceeds may already finance
part of other expenditure or have been transferred to subsidiaries;
counting both gross QIP cash and gross WWIL deal value as
independent equity gains would double count.

The original BSE October 7 WWIL PDF further confirms Vibhav's
₹250cr parent subscription, ₹200cr parent subordinated
12% intercompany facility, and ₹100cr outside Authum facility.
That is the **subsidiary capital stack**, not a second QIP or a
verified Inox Green net consolidated cash position.

## Reproducibility

- Model: src/marketlab/hg007_qip_capitalization.py
- CLI: scripts/reconcile_hg007_post_qip_capitalization.py
- Tests: tests/test_hg007_qip_capitalization.py
- Workflow: .github/workflows/hg007-post-qip-capitalization.yml
- Result, append-only after main merge:
  research/hg007/inoxgreen-sep2026-qip/post-qip-market-cap-audit-v1.json

Run the source-pinned report:

    python scripts/reconcile_hg007_post_qip_capitalization.py \
      --out /tmp/inoxgreen-post-qip-cap-review.json

No third-party live API or future returns used. All original Git
blobs, original QIP bytes/receipt and Oct9 source result are
independently checked before any arithmetic.

## Independent next underwriting gate

1. Obtain Sep29/Oct10 current Reg31 shareholding and fully diluted
   option/instrument counts, including any subsequent exercise/issue.
2. Obtain the actual October pro forma consolidated net debt/cash,
   QIP proceeds use, and financing fee impact.
3. Source WWIL O&M audited carve-out EBITDA, FCF, debt and contract
   renewal/receivable quality.
4. Verify completed legal WWIL BTA transfer/conditions and subsidiary
   minority rights, including Authum conversion class/pricing.
5. Build separately frozen operating/downside valuation scenarios
   before attempting even a *conditional* listed-equity payoff.

No equity price target, recommendation, completion probability,
portfolio eligibility or live capital is authorized by P008.
