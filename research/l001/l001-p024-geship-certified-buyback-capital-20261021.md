# L001 P024 | GESHIP: purchased shares are not necessarily canceled shares

**Research as of:** October 21, 2026, after the October 19 market session and after the pre-existing L001 P023 falsification review. **No live capital or investment recommendation.**

## Two independent original issuer documents

1. [First-lot September share extinguishment certificate, issuer PDF dated Oct 13](https://greatship.com/upload/investors/buyback_2026/1st_Lot_Buyback_Extinguishment_Certificate.pdf). Five pages, includes shareholder-capital table, registrar/secretarial confirmations and NSDL account debit evidence.
2. [Original October 19 buyback daily report, issuer PDF](https://greatship.com/upload/investors/buyback_2026/dailyreport.pdf). Two pages at the actual Oct 21 research retrieval time. **Mutable URL warning:** the issuer can replace dailyreport.pdf when reporting a later session. Never treat a newer PDF as the October 19 original.

### Legally recognized versus economically executed

| Original share evidence | Shares | What it actually proves |
|---|---:|---|
| Pre-buyback reported paid-up equity | 142,767,161 | Starting certified share capital |
| September shares legally extinguished | 1,858,941 | NSDL-confirmed cancellation executed Oct 10, certificate Oct 13 |
| Certified post-September capital | 140,908,220 | First lot share denominator only, not fully diluted Oct 19 denominator |
| October 19 daily shares repurchased | 194,000 | Buyback execution that day, not legal extinguishment |
| Cumulative repurchased by October 19 | 3,095,660 | Issuer transaction cumulative, NOT total shares legally extinguished |
| Cumulative repurchased minus certified September lot | 1,236,719 | Purchases *not proven canceled by the first-lot certificate* |

An October 19 outstanding-share denominator is **not established**. A purely hypothetical no-other-issuance boundary would be 140,908,220 shares if none of the 1,236,719 later repurchases were canceled, or 139,671,501 if all were. Neither is claimed as the actual paid-up capital and the boundary need not survive unrelated corporate actions or further cancellation notices.

### Consequences for hidden-gem valuation

The additional outstanding-share *uncertainty from the October repurchases alone* is under 1% of the first-lot certified denominator. This is meaningful for exact per-share valuation but much smaller than the L001 P023 stress finding: an illustrative **27.74% haircut in June's noncash NAV residual can eliminate the Oct 19 19.44% headline discount**. The old June 30 reported issuer NAV ₹1,886/share and October 19 observed NSE close ₹1,519.30 remain cross-dated evidence, not an independently updated fleet NAV or buy floor.

**Do not invent a shareholder NAV uplift just by reducing the share count.** The issuer paid cash for the buybacks. A correct capital bridge must reduce distributable NAV by actual net repurchase cash and fees, use current shipping fleet and offshore appraisals, adjust vessel purchase/sale commitments and minority liabilities, and use current legally canceled shares and true dividend/corporate-action dates.

## Original-source reproducibility

New research code independently validates the **five-page** first-lot PDF, **two-page** Oct 19 issuer buyback PDF, dates, original NSE symbol/ISIN, certified capital quantities, and the separate 19 October day/cumulative purchase quantities. It records actual retrieval UTC and SHA-256 for both source files, saves original PDFs in SHA-addressed repository paths, and emits an immutable signed derivative report. A missing HTTP source or a daily PDF updated to another date remains a blocked receipt, not a fabricated input.

Expected canonical output: research/l001/l001-p024-geship-buyback-capital-bridge-v1.json. Implementation: src/marketlab/l001_p024_geship_buyback.py, scripts/archive_l001_p024_geship.py and tests/test_l001_p024_geship_buyback.py.

**Still unresolved:** October legally canceled shares after the first lot, November cycle-normalized fleet/offshore values, updated net cash after buyback, price-to-current-NAV and cost-adjusted investment IRR. An 18-month or 3-year positive expected-return signal is not yet warranted.