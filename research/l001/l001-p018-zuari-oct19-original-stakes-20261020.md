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
