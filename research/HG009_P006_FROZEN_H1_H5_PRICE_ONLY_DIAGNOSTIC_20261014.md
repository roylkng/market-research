# HG009 P006: original-source H1/H5 observational price diagnostic

**Protocol frozen:** October 14, 2026, before the **October 15** NSE open.  
**Population:** 100 selected, 100 one-signal control, 100 zero-signal control companies, selected **without post-entry prices**.  
**Source basis:** immutable HG009 P002 daily replay from H021's original NSE EQ UDiFF and Nifty 500 **price index**.  
**Status:** *source-only evaluation code and fixed methodology*. The actual experiment has no H1/H5 observations at this registration.  
**Capital:** disabled.

## Rationale and exact accounting

The HG009 P005 original-source baseline already proves the three arms differ on revenue, EPS growth and margins. A future raw return difference is thus observational and cannot be declared LLM-generated investment alpha. With unresolved share adjustment, the correct first diagnostic is a clearly labeled **unadjusted original share-price change**, not total shareholder return.

This stage uses only the original Oct 14 frozen clock P004 and only the two 2026 horizons whose calendar positions are certain:

| Horizon | Frozen NSE holding sessions | First legitimate source-supported evaluation |
|---|---|---|
| H1 | Oct 15 | After official Oct 15 close and original NSE market/index publication |
| H5 | Oct 15, Oct 16, Oct 19, Oct 21, Oct 22 | After official Oct 22 close and complete original source chain |
| H20, predeclared primary | **BLOCKED** by unresolved Nov 8 Muhurat classification | No result until a separately verified official calendar amendment |
| H60 | **BLOCKED** because 2026 calendar contains only 52 sessions | No result until official prospective 2027 extension |

Entry reference is official **Oct 15 EQ open**. For H1 exit is the same session's close, while H5 exit is **Oct 22 EQ close**. This is not proof of a realizable execution at the open. There are no paper orders, fills, trading costs or position weights.

## Exact observation and missingness contract

The evaluator must reparse the original H021 cash UDiFF ZIP and Nifty 500 CSV through HG009 P002 for *each* required session. It validates the P002 observation against the original signed day, original NSE source SHA-256, the permanently pinned 300 frozen symbol+ISIN identities, original UTC source retrieval timestamps and calendar close.

A company's unadjusted gross share-price change is simply (official final EQ close / original initial EQ open - 1), **if and only if** the *same exact symbol and ISIN* have valid official EQ observations in **every** required NSE session. A missing date, BE-series migration, changed ISIN, conflicting EQ identities, suspended security or other missing original source yields **null**, with exact date and source reason. No synthetic quote, zero return, 100% loss assumption, rolling forward or survivorship exclusion.

For every fixed arm, report all 100 original identities, observed denominator, missing-source count/reasons, conditional-on-observed mean/median/min/max. Show selected-minus-control conditional **percentage-point differences** only as *descriptive* and never as causal stock-picking lift. The Nifty 500 price-only change is separate. The observed group means cannot be combined into a portfolio P&L or compared to Nifty 500 TRI.

A dividend or corporate action may make a perfectly observed **unadjusted** price ratio a poor economic proxy. This stage applies **no** dividend, bonus, split, rights, spin-off, merger, demerger, share exchange, holding-company/minority, tax, slippage or spread adjustment. Explicit flags prevent publishing a total-return or investable-alpha result on these numbers.

## Source-clocking and publication contract

No genuine H1/H5 price diagnostic can exist until the corresponding market-close and official original source retrieval. A late published NSE price source can be used to *observe the previously frozen price reference*, but it cannot become a retrospectively submitted entry order or a pre-close decision.

The separate HG009 P002 source workflow first seals the original complete NSE market observations. P006 only reads those original anchored artifacts and replays the raw NSE source bytes. It then publishes an immutable \`research/hg009/price-diagnostics/HG009-P006-H{1|5}-20261015-v1.json\` only after *every exact holding session* is documented. A missing source is a visible pending state, not a license to extrapolate or silently use a later trading date.

There are no return claims from source completeness alone. This stage does not update the prospective T012 futures trial, the H021 ten-stock experiment or the HG009 original 100/control selection.

The reviewer may run:

    python scripts/evaluate_hg009_p006_price.py --check
    pytest -q tests/test_hg009_p006_price.py

The default command without --check seals newly source-matured H1/H5 diagnostics only. Results remain **research diagnostics, not investment recommendations**, until original corporate-action and cash-distribution evidence, industry/size/valuation controls, realistic costs and independent replicated cohorts are implemented.
