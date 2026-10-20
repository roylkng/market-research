# L001 P025 | GESHIP original buyback cash versus stale per-share NAV

**Research cutoff:** October 21, 2026, after issuer October 19 daily reporting. **No current fair value, guaranteed return or authorized capital.**

The October 20/21 P024 original issuer PDF custody independently verified the September legally extinguished 1,858,941 GESHIP shares, post-lot paid-up shares 140,908,220, and **3,095,660 cumulative October 19 purchases**. Later purchases cannot be treated as legally extinguished shares without later share-capital certificate.

## New independently replayable source requirement

The [original GESHIP Buy Back 2026 page](https://greatship.com/buyback-2026.html) publishes daily share purchase counts, **two-decimal rounded average acquisition prices**, and cumulative totals for September 4 to October 19. It explicitly states prices **exclude brokerage/transaction charges**.

This page is mutable. P025 captures its actual retrieved HTML, validates 30 rows and the two month-end totals against certified share/issuer-daily reports, and retains the exact source bytes in a content-addressed file with a UTC receipt. It intentionally rejects another page version with later activity rather than silently reconstructing the historically seen edition. If the original page is unavailable or changed, the derived study remains blocked.

## Reconstructed purchase cash, *not* audited cash settlement

| Period | Original shares bought | Estimated cash at rounded published average prices |
|---|---:|---:|
| September 4–30 | **1,858,941** | **₹262.715 crore** |
| October 1–19 | **1,236,719** | **₹187.802 crore** |
| Cumulative through Oct 19 | **3,095,660** | **₹450.517 crore** |

Actual cash outflows, transaction charges, settlement timing, and parent-consolidated financing balances are NOT proved by multiplying two-decimal displayed averages. Even the issuer October 19 original detailed PDF price is shown to four decimal places while its web table is rounded to two.

## Reverse NAV attribution, not an updated NAV estimate

Start with company **June 30** reported ₹1,886 NAV per **old** share and historic **142,767,161** shares. The following intentionally unrealistic arithmetic holds *all other fleet, offshore, FX, debt, tax, lease and cash changes to zero*, and takes only buyback cash/spares:

| Counterfactual assumption | Formula result | Difference to original June NAV/share |
|---|---:|---:|
| September ₹262.715 crore cash spent and 1,858,941 certified canceled shares | **₹1,892.24/share** | **+₹6.24/share** |
| Also all 1,236,719 October purchases legally canceled, subtract October ₹187.802 crore spent | **₹1,895.55/share** | **+₹9.55/share** |

Full-counterfactual increase is only **0.506%** of old June NAV. October post-September cancellations are **not** presently certified, so the second row is particularly hypothetical.

Compare with the already-signed October 20 L001 P023 stress: a **27.74% write-down of the noncash June NAV residual** can eliminate the **19.44%** observed October 19 headline share discount. **A ₹9.55/share buyback arithmetic effect cannot resolve the fleet-NAV uncertainty.**

## Capital decision

No actual October 19 current fair value or expected return follows. A defensible investor model needs: original ship-by-ship values, tanker/offshore industry cycle, present cash/debt after buyback, all legal canceled shares and future cash commitments, segment sustainable owner cash, NAV controls, and execution liquidity. Existing L001/PF001 trading studies are unchanged. **Do not promote GESHIP to a buy recommendation.**

Code: src/marketlab/l001_p025_nav_accretion.py; original-source CLI scripts/archive_l001_p025_nav_accretion.py; signed output research/l001/l001-p025-geship-issuer-buyback-cash-nav-v1.json. Unit tests are fully synthetic as to issuer HTML, while numeric values derive from the company website's dated daily table.


## Original issuer HTML custody completed

Official GESHIP Daily Activity page bytes were successfully archived under research/l001/originals/geship_2026_buyback_table. Actual first-seen retrieval by this workflow: **2026-10-20T19:03:50.394496Z** (October 21, 00:33:50 IST). Original 86,249-byte HTML SHA-256 **ad9fa14e0dea3f740a915fadef21af2cf76debf02d50dbdf48b0b023f146c83f**. The frozen 30-row original-source arithmetic report SHA-256 is **e0759fda15b35a50689b91e08a91a6fa47fe5ce194a9b43819d67fc9f7996224**. Both have source-based CI checks and independent byte replay. The source timestamp is retrieval time only, not presumed first-ever public issuer publication. Prices are displayed to two decimal places by the issuer, and transaction fees and actual settlement cash are excluded.

The replay produced September ₹262.714746cr and October through 19th ₹187.802444cr. The two June NAV counterfactual values are ₹1,892.236792 and ₹1,895.545561 respectively. Neither is an October 2026 fleet NAV.
