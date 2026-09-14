# H022-D006 — point-in-time FFMC source audit

## Status

`BLOCKED_PUBLIC_SOURCE`

Live capital: **DISABLED**

This is a source-integrity gate, not a return experiment. It cannot upgrade H022, alter H022-R001/H022-X001, or authorize a historical universe filter after outcomes are known.

## Why this audit exists

The original H022 historical development result used the Sep-2026 U001 cohort replayed backward. That panel was `PROMISING`, but it has survivor/composition bias.

The later historical reconstruction fixed NIFTY 200 membership point in time and expanded H022 to 211 companies. That broader challenge retained a positive relation but was frozen `INCONCLUSIVE`. Subsequent diagnostics found:

- pre-event momentum does not explain H022;
- industry fixed effects do not remove the aggregate relation;
- Financial Services do not explain the expanded-panel attenuation;
- same-company overlapping 60-session windows and publication-month clustering do not explain it;
- H022 remains positive using within-company variation, including after de-overlap.

The remaining historical composition question is whether the stronger original panel came partly from U001's **free-float-market-cap selection**.

## Exact U001 target

`docs/universe-v1.md` freezes U001 as `U001-nifty200-top100-nonfinancial-ffmc-v2`:

1. obtain point-in-time NIFTY 200 membership;
2. exclude official `Industry == Financial Services`;
3. rank the remaining constituents by NSE free-float market capitalization (`ffmc`) descending;
4. break ties by NSE symbol ascending;
5. take the first 100 names;
6. freeze that snapshot for the cohort.

Therefore a legitimate historical analogue needs **point-in-time constituent FFMC**, not merely historical membership or today's market capitalization.

## What the official public sources establish

### NIFTY 200

Official source:
`https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-200`

The public NIFTY 200 page describes the index and provides current downloads. It establishes the relevant index family and current constituent interface, but this audit did not identify a public historical constituent-level FFMC series there.

### Investible Weight Factor methodology

Official source:
`https://www.niftyindices.com/resources/investible-weight-factors`

NSE Indices states that free-float market capitalization is derived by applying the Investible Weight Factor (IWF) to full market capitalization. It also states that company IWFs are determined from public shareholding disclosed to stock exchanges on a quarterly basis.

This is important because it makes **current IWF an invalid substitute for historical IWF**. A company's public/promoter/strategic ownership can change between quarters.

### FFMC calculation

Official source:
`https://www.niftyindices.com/resources/tutorial/calculation-of-indices`

The official calculation guide gives:

```text
free-float market capitalization
  = total shares outstanding × IWF × stock price
```

So an independent reconstruction would require dated values for all three inputs, or an authoritative dated FFMC field directly.

### Public historical reports

Official source:
`https://www.niftyindices.com/reports`

The public historical-report interface exposes historical index data such as index OHLC, P/E, P/B, dividend yield and total-return index values. It does **not** expose the complete historical constituent-level company/IWF/FFMC panel needed to rerun U001's rank at each historical freeze date.

### Historical constituent data subscription

Official source:
`https://www.niftyindices.com/offerings/data-subscription`

NSE Indices explicitly describes an ongoing and historical **individual-security** data product. It says constituent data include company names, identifiers, market capitalization, weights and prices and gives `indices@nseids.co.in` for subscription.

That is the clearest evidence that authoritative historical constituent-level data exist, but are a dedicated data product rather than the public index-history interface.

## Audit verdict

As of **2026-09-14**, this project has **not identified a complete free official public source** from which the historical U001 FFMC ranking can be reproduced exactly.

Therefore the honest state is:

**`BLOCKED_PUBLIC_SOURCE`**

We must not force the missing factor into existence simply because an FFMC-controlled result would be scientifically useful.

## Explicitly forbidden shortcuts

The following are invalid for H022 historical validation:

- use Sep-2026/current FFMC for 2025 or earlier dates;
- use current IWF for earlier quarters;
- use current shares outstanding for earlier dates;
- infer historical FFMC rank from current index weights;
- use current NIFTY 200 membership to define earlier populations;
- silently backfill missing IWF from a later quarter;
- use ordinary/full market capitalization as if it were FFMC;
- use a third-party present-day market-cap ranking as historical FFMC;
- choose a size cutoff after examining H022 returns;
- select only dates/names for which convenient historical FFMC data happen to be available.

Any of those would reintroduce the same look-ahead/composition problem the expanded historical exercise was created to remove.

## Legitimate unblock paths

### A. Acquire official historical constituent data

Obtain the NSE Indices historical constituent dataset, verify that its dated fields are sufficient to reproduce the relevant FFMC ordering, and preserve provenance/hashes within the applicable license terms.

This is the cleanest route if access/cost is reasonable.

### B. Reconstruct FFMC from official point-in-time components

A separately preregistered reconstruction could combine:

- already-reconstructed historical NIFTY 200 membership;
- historical official industry classification appropriate to the date;
- point-in-time total shares outstanding;
- point-in-time public/strategic shareholding sufficient to calculate the applicable IWF under the then-current NSE Indices methodology;
- point-in-time official security prices.

Before H022 subgroup returns are opened, that reconstruction would need an **external validation gate** against authoritative historical constituent FFMC/weight observations for a substantial sample. Without such a benchmark, subtle IWF classification and corporate-action mistakes can silently change ranks around the top-100 cutoff.

This path is technically possible in principle, but it is a separate historical-data project, not a small H022 patch.

### C. Stop historical FFMC reconstruction and go prospective

This is currently the default research recommendation.

U001 already captures FFMC prospectively at cohort freeze time. Future H022 observations can therefore be evaluated on genuinely frozen point-in-time U001 cohorts without reconstructing historical FFMC at all.

That path is slower in calendar time but scientifically cleaner and avoids paying for or approximating historical constituent data.

## Decision for the current project

Until path A or a validated path B is available:

- do **not** run an H022 historical `top100 nonfinancial FFMC` subgroup test;
- keep the expanded point-in-time NIFTY 200 challenge at its frozen `INCONCLUSIVE` classification;
- keep the original current-U001 replay labeled `PROMISING_HISTORICAL_DEVELOPMENT`, not validation;
- treat D005's positive within-company result as robustness evidence, not a promotion event;
- prioritize prospective H022 capture and evaluation.

## Next implementation gate

The next useful work is to turn H022 from a historical research result into a **prospectively frozen signal stream** on future management-call transcripts using the already-frozen U001 cohorts/source timestamps. The prospective contract must be committed before any future H022 return is observed.
