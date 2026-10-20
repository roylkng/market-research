# L001 P018: Zuari October 19 same-day listed-stake repricing

**Research cutoff:** October 20, 2026. October 20 is an NSE Dussehra holiday.  
**Exchange price basis:** actual complete original **October 15 and October 19** cash-market NSE UDiFF archives.  
**Holding units:** older *June 30*, issuer rounded quoted investment marks.  
**Net debt:** older *March 31* borrowings less cash, **not synchronized**.  
**Purpose:** falsify stale portfolio-value assertions, not issue a buy recommendation.

## Core correction

P012 originally repriced five listed investments to the **October 15** NSE closes, finding a source-scaled ₹3,820.124826 crore portfolio mark. P017 later found Zuari Industries itself closed **₹259.10 on October 19**, but correctly left the October 19 portfolio fair-value field null because it used only the *HG009 300-company subcohort*, which does not contain all five held securities.

This was unnecessarily conservative about **data availability**. Our independently archived H021 October 19 source contains the **complete NSE EQ market ZIP**. We can independently reprice all five underlying stock marks using that original source, on the same October 19 date as Zuari's own close.

## Full-source contract

The source analysis validates original H021 daily packet SHA, raw original NSE UDiFF ZIP SHA-256 and byte count, original index CSV receipt, first actual capture UTC after that session's official close, frozen exchange calendar, exact symbol+ISIN for each stake, and the older previously issuer-PDF-verified original June price/value assumptions.

- CHAMBLFERT, ISIN INE085A01013
- ZUARI (Zuari Agro Chemicals), INE840M01016
- PARADEEP, INE088F01024
- TEXRAIL, INE621L01012
- TEXINFRA, INE435C01024
- Parent ZUARIIND, INE217A01012

The issuer's five individually rounded June values sum ₹4,224cr, but issuer total is ₹4,223cr. Preserve the earlier P012 same rounding scale; crosscheck that independently reproduced **October 15** whole-market mark is **₹3,820.124826cr**. Only then compute the source-backed **October 19** hypothetical unchanged-June-holdings mark.

The original [NSE holiday calendar](https://www.nseindia.com/resources/exchange-communication-holidays) lists October 20 Dussehra as a holiday and November 8 Muhurat subject to further session notice. No October 20 stock price, 2027 market session or ex-date return is invented.

## Two distinct clocks and serious caveats

**Stock quote clock:** all six listed closes are actual **October 19** NSE exchange prices, *retrieved after the close* and securely persisted. A later original-market retrieval is a valid historical observation, not an October 19 intraday execution.

**Financial/equity claim clock:** the historical positions were issuer-reported in June, share counts are historical basic shares, parent/subsidiary collateral shares may have changed, and debt/cash are from March. A same-day quoted market asset mark **does not make these underlying balance-sheet claims contemporaneous** or prove the parent's realisable unencumbered shareholder equity.

The extra portfolio markdown that causes hypothetical repriced assets minus *old March net debt* to equal *October 19 market price times older basic shares* is a **reverse break-even sensitivity**. It is not a probability, certified margin of safety, liquidation price, acquisition value, or future-return expectation.

Further required issuer evidence before conviction includes: original October pledge release, outstanding claims per lender, August/September equity/ICD transfers, legal entity/subsidiary control, current NCI, block sale taxes, actual underlying share units, repatriated cash and *current* fully diluted Zuari shares. Without those, no fair value or live capital.

## Repeatable result

Canonical reproducible report: research/l001/l001-p018-oct19-five-stake-source-repricing-v1.json. Source-bound command: python scripts/materialize_l001_p018.py --check. Regression tests: pytest -q tests/test_l001_p018_zuari_fullmarket.py.

This closes a **source-price synchronization gap** in P017 without amending its historically sealed report or the original HG009 100/200 selection. P017's original conclusion that NAV cheapness is **unproven** remains correct.


## Original NSE market replay result

The dedicated source-freeze workflow independently verified both H021 raw NSE ZIP + Nifty 500 index receipts. It reproduced the existing October 15 P012 mark before using original October 19 closes for all five securities.

| Previously disclosed stake | Oct 15 close ₹ | Oct 19 close ₹ | Oct 15 hypothetical stake mark ₹Cr | Oct 19 hypothetical mark ₹Cr |
|---|---:|---:|---:|---:|
| Chambal Fertilisers | 390.30 | 382.95 | 2,320.4012 | 2,276.7041 |
| Zuari Agro Chemicals | 206.39 | 202.73 | 278.1120 | 273.1801 |
| Paradeep Phosphates | 146.41 | 144.26 | 8.6103 | 8.4839 |
| Texmaco Rail | 112.89 | 109.27 | 726.2961 | 703.0062 |
| Texmaco Infrastructure | 123.98 | 128.27 | 486.7053 | 503.5464 |
| **Five-stake quoted mark, scaled to June issuer aggregate** | | | **3,820.1248** | **3,764.9208** |

The hypothetical original quoted investment mark declined **₹55.2040 crore** from October 15 to October 19. This is *not* Zuari's executed holding P&L or a shareholder cash realization because the June portfolio quantity assumption is not verified unchanged.

October 19 issuer original NSE close: **₹259.10**. Historical March basic shares: **2,97,81,184**, which imply cross-dated basic market capitalization **₹771.6305 crore**. Original **March 31** net borrowings: **₹2,519.4245 crore**, not October net debt. Quoted portfolio mark less old net debt = **₹1,245.4963 crore**, a hypothetical gap of **₹473.8658 crore** over that historical basic equity cap.

The additional portfolio markdown sufficient to eliminate this purely hypothetical gap is **12.5863%**, compared with **13.19%** on October 15. A 10% further quoted-stake markdown leaves only **₹97.3737 crore** of hypothetical gap, and a 20% markdown makes it **negative ₹279.1184 crore**.

**This improves source-date alignment but does not prove an undervalued share.** Pledge release, October collateral/covenant waterfall, current stake units, parent/subsidiary claims, current net borrowings and diluted shares, liquidity/tax costs and true owner cash remain unresolved. The date-synchronized figures must not be promoted to issuer NAV or investment permission.

Original Oct19 UDiFF ZIP SHA-256: f0a2e9bf7cb185bb112704355772d2954d662abee3d7295414aabc26d6ecfbde. Index source SHA-256: ebff93c77dc6cdf82f1536a92c36a611a644fa6f87e267aa7c2ed5edfcf46502. Source-bound result SHA-256: 7b07899a164a2a078930cb8cd749f6be093ea7632c71521ca04ad341c5d240d7.
