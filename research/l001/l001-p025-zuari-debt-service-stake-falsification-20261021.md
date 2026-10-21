# L001 P025: Zuari Industries debt-service and strategic-stake falsification

**Dated source review:** 21 October 2026. **No buy recommendation, valuation approval or live capital.**

## Research question

Can Zuari Industries's apparently inexpensive five-listed-investee portfolio meaningfully support shareholder value after finance costs, parent borrowings, pledges, taxes and ownership claims, or is the apparent discount an accounting cross-date illusion?

The analysis uses the original NSE October 19 share closes and shareholder capital assumption already frozen in L001 P018, and cross-checks its financing risk with the August 14 first-party issuer Q1 FY27 presentation. It is **post-entry research** and cannot be inserted retroactively into the October 15 HG009 prospectively selected universe.

## First-party company evidence

[Zuari Industries investor presentation submitted to NSE/BSE, dated 14 August 2026, 30-page PDF](https://www.zuariindustries.in/storage/uploads/images/1786947593.pdf):

- PDF page 20 (zero-based page 19) lists the five strategic holdings at **₹4,223 crore** for June 30, up from **₹3,681 crore** March 31. These are *market marks*, not liquidated proceeds.
- PDF page 26 (zero-based page 25) reports consolidated Q1 FY27 **segment EBITDA ₹8.05 crore**, versus **finance costs ₹61.54 crore**, plus net unallocable income ₹13.74 crore.
- PDF page 25 (zero-based page 24) reports **PBT before associate/JV earnings −₹39.75 crore**, JV/associate accounting earnings **₹34.37 crore**, exceptional income **₹4.81 crore**, resulting total **PBT −₹0.57 crore** and PAT **₹0.05 crore**.
- Other comprehensive income of **₹519.69 crore** is not operating cash, distributable parent income, or a realized shareholder return.

That segment EBITDA covers only **13.08% of the quarter's finance expense**, but is **not itself a debt-service coverage ratio**. Associate profit is on equity-accounting basis, rather than independently verified repatriated dividends. To calculate actual debt service and owner value, the original detailed parent cash-flow, lender waterfall and pledge documents remain necessary.

## Mixed-date market and debt bridge

The independently sealed original L001 P018 October 19 source puts the five listed stakes using reported *June share units*, marked to NSE October 19 prices, at **₹3,764.92078 crore**. Earlier original March 31 net borrowings were **₹2,519.4245 crore**. Zuari's historical basic-share-based October 19 equity capitalization was **₹771.6305 crore**. Their nominal gap is **₹473.86578 crore**.

This is **not** a shareholder sum-of-parts value. It omits contemporaneous lender debt, cash encumbrances, portfolio pledge release, unlisted-subsidiary net cash/debt, the current rights/holding share units, minority claims, tax on dispositions, proceeds available for distribution and market-impact haircut.

### Illustrative scenario table

| Extra markdown on these October 19 marks | Remaining investee stakes (₹ crore) | Gap after *stale March borrowing* and historical October equity cap (₹ crore) |
|---:|---:|---:|
| 0% | 3,764.921 | +473.866 |
| 5% | 3,576.675 | +285.620 |
| 10% | 3,388.429 | +97.374 |
| 12.5863% | 3,291.055 | approximately zero |
| 15% | 3,200.183 | −90.872 |
| 20% | 3,011.937 | −279.118 |

A mere **12.5863% additional discount** on the investee marks erases the apparent gap. This threshold is a *reverse stress level*, not a calibrated downside probability or a future price target.

## Investment decision status

**Not investable on current evidence.** Preserve null for after-tax realizable stakes, share count, owner cash, current debt/lease/pledge waterfall, probability-weighted attributable equity, and expected 1/3-year return.

Key falsifiers: (1) parent financing cost exceeds sustainable operating cash, (2) company ownership stakes are collateralized or inaccessible without creditors, (3) unlisted ventures require additional reinvestment, (4) parent dilution and buybacks change share counts, (5) liquidating listed positions incurs tax/impact, and (6) the present market already capitalizes probable realizations.

**Source provenance at the model's freeze:** The public issuer 30-page PDF was visually reviewed when the numerical packet was first sealed. Its complete raw PDF bytes were not yet available **in the original mathematical packet**, which therefore keeps its `original_pdf_bytes_archived_in_this_packet=false` flag unchanged. The two prior Git JSON research inputs were independently pinned and verified.

## Independently completed original PDF custody

The subsequent original-source job retrieved the **exact same** August 14 presentation and successfully verified the issuer plus financial tables on all required original pages. The original PDF bytes are now retained in a **separate, immutable source receipt**, rather than retroactively altering the signed mathematical packet:

- Actual original retrieval: **2026-10-21T16:12:01.446882Z**, not presumed August publication time.
- Original 30-page PDF length: **7,696,113 bytes**.
- Original raw PDF SHA-256: `6ebec1ef99aba350000aab28b1e9f1b6c6a39471458df488ece9c7f8ea4fb25b`.
- Verified issuer, original 14-Aug announcement, June investment-table amounts, consolidated Q1 profit/loss and segment finance/EBITDA original pages.
- Original PDF: `research/l001/originals/zuari_q1/sha256/6ebec1ef99aba350000aab28b1e9f1b6c6a39471458df488ece9c7f8ea4fb25b.pdf`.
- Signed independent receipt: `research/l001/originals/zuari_q1/receipts/6ebec1ef99aba350000aab28b1e9f1b6c6a39471458df488ece9c7f8ea4fb25b.json`, receipt SHA `331f55592d26eae018dca3c696b4d78b7d1dcabee486211271738e8a17885cf7`.

This upgrade proves original source custody and page-level numerical consistency only. It does **not** convert the mixed-date stress analysis into a contemporaneous attributable shareholder NAV or an investment recommendation.

Canonical report: research/l001/l001-p025-zuari-q1-debt-stake-falsification-v1.json.
Generator: scripts/materialize_l001_p025_zuari.py.
Regression: tests/test_l001_p025_zuari.py.
No trading or original HG009 selection change.
