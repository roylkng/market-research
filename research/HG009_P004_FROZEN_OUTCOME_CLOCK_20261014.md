# HG009 P004: official NSE clock for the 300-name prospective experiment

**Freeze date:** 2026-10-14, before first planned October 15 NSE cash-market open.  
**Exact source population:** selected HG009-D001 100, matched P001 one-lane 100 and zero-lane 100, all fixed on October 14.  
**Returns:** not opened. **Money deployed:** none. **Purpose:** lock future source measurement, not claim alpha.

## One irreducible timing question

A 100-company source selection is not a forecast. A valid forward comparison needs its price *reference* and every exit clock fixed before results can be inspected. All 300 original symbol+ISIN identities remain, even if entry price is missing, security changes series, issuer suspends, or a stock delists. Missing shares cannot be replaced after the fact by a different security or dropped to improve an arm average.

We use October 15, 2026 official NSE EQ **open** as the predeclared *paper price reference*. Its data may only be obtained via actual original post-close UDiFF, which **does not imply a fill was possible at the open**. All source receipts retain actual retrieval time. A late market source can document that predeclared historical price once publicly available, but it is never an earlier investor decision.

Exit conventions count the entry session as **holding session one**. Comparisons require official NSE EQ close on the exit session and original Nifty 500 **price-index**, not TRI. An economic *total-return* calculation additionally requires dividends, split/bonus/rights, merger/demerger and identity adjustment. Those are **not yet available** and must not be replaced by an unadjusted price ratio.

## Frozen official cash-market horizon audit

| Planned horizon | Source-calendar state | Result |
|---|---|---|
| H1 | October 15 is a frozen official cash session | Price-source observations can begin only after that session closes |
| H5 | Frozen NSE 2026 sessions: Oct 15, 16, 19, 21, 22 | Official possible exit Oct 22 |
| H20 (primary descriptive comparison) | Current frozen session sequence provisionally ends Nov 13, **but November 8 Muhurat remains unresolved** | **Blocked** until exact official special-session timing/calendar treatment is frozen. Do not publish Nov 13 as an unconditional exit |
| H60 | Original official 2026 calendar has only 52 trading sessions from Oct 15 to Dec 31 | **Blocked** pending independently captured, forward-only official NSE 2027 calendar |

The base calendar SHA is **2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce**. New official calendar evidence must be versioned prospectively and retain the original base unchanged. No later holiday corrections silently reassign already-sealed observations.

## Outcomes, descriptive comparisons, and scientific status

The primary observational endpoint is the **20-completed-trading-session** equal-notional distribution of originally priceable, original-symbol+ISIN stock *price* returns (H20). Report all 100 denominators and *missing count per arm*, same-source market-price distribution (mean, median, adverse tail) and matched historical turnover-band context. Difference measures: selected minus one-lane and selected minus zero-lane, with the Nifty 500 *price* index shown separately.

H1 and H5 are early descriptive checks, not replacements for H20. H60 requires 2027 session evidence. A single 300-company cross-section is observational, not statistically independent draws or a controlled treatment. There is no significance, repeatability, factor-neutral, or causal LLM alpha claim from one date. Sector, enterprise size, liquidity and accounting regime remain major unmatched confounders.

If original corporate-action entitlement/dividend/source data are missing, only a provisional unadjusted price-ratio diagnostic could be constructed later and may be badly misleading through ex-dates. The official P004 clock **does not open even that diagnostic**. A separate source-controlled evaluator and immutable return ledger must be coded and independently tested before any return claims.

## Reproducibility and hard stops

Frozen source SHA for selected 100: **e904e5d69dc7a6c2a45ea3cf34933544bc2634f80e3666125185d475372864d5**. Controls SHA: **8c8d9781adf7900addd28a1a60f1cfb33bed9a1e4985e6c410a010d2c819eef8**.

Run **python scripts/materialize_hg009_p004_clock.py --check** and **pytest -q tests/test_hg009_p004_clock.py**. The signed JSON record appears in research/hg009/hg009-p004-2026-outcome-clock-v1.json. No source price label, trade, stock expected return, scenario probability, capital authorization or portfolio weight can be inferred from this clock.
