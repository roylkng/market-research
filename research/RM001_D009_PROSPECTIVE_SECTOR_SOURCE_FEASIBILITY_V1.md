# RM001 D009 Prospective NSE Quote Sector-Source Feasibility v1

Status: FROZEN BEFORE FIRST QUOTE-SOURCE INSPECTION
Frozen: 2026-10-02
Live capital: DISABLED

## Objective

Determine whether the official current NSE equity quote endpoint can supply an
explicit company-level point-in-time industry classification suitable for a
future prospective RM001 semantic sector factor.

D009 is source/schema feasibility only.

It opens no return labels, alpha outcomes, risk-fit outcomes or portfolio
outcomes.

## Motivation

D007 established that the daily NSE CM MII Security File is a valid
point-in-time total-market-cap source but does not materially populate company
industry fields.

D008 established that four dated official NSE Capital Market Exchange Monthly
Reports contain no broad company-level classification mapping.

NSE's current quote page exposes Basic Industry, and NSE Indices publishes a
four-tier company industry-classification methodology.

D009 tests the underlying current quote payload directly and prospectively.

## Official source endpoint

NSE web JSON quote endpoint:

    https://www.nseindia.com/api/quote-equity?symbol=<SYMBOL>

Acquisition must use the existing MarketLab NSEClient cookie/session flow.

Exact response bytes are retained for every attempted symbol.

## Frozen identity universe

Source snapshot:

    research/prospective/ae001-sc001/raw/2026-10-01/
    market-ccc5fb27872716bbcc99d2d87e522ab304f6620e11c3a5045c30e1ff25cbfb73.zip

Expected raw SHA-256:

    ccc5fb27872716bbcc99d2d87e522ab304f6620e11c3a5045c30e1ff25cbfb73

Trading session:

    2026-10-01

Parse exactly the official NSE CM STK EQ rows under the existing AE001 UDiFF
contract.

## Frozen deterministic sample

For every exact EQ identity:

    key = SHA256("RM001-D009|SYMBOL|ISIN")

Sort by:

1. key;
2. symbol;
3. ISIN.

Take the first:

    50 identities.

No symbol may be added, removed or substituted after quote outcomes are opened.

## Frozen required quote identity fields

For every successful quote payload:

    payload["info"]["symbol"]
    payload["info"]["isin"]

must exactly match the frozen sample symbol + ISIN.

Any identity mismatch fails that observation.

No symbol-only classification carry-forward is allowed.

## Frozen required classification object

Candidate object:

    payload["industryInfo"]

Required non-empty string fields:

- macro
- sector
- industry
- basicIndustry

D009 does not infer a missing parent level from another level.

## Feasibility gates

D009 passes only if all of the following hold:

1. sample count is exactly 50;
2. at least 48/50 quote requests return parser-valid JSON;
3. every successful quote has exact symbol + ISIN identity match;
4. at least 48/50 total sample identities have all four required non-empty
   industryInfo fields;
5. at least 5 distinct Sector values occur among complete rows;
6. at least 10 distinct Basic Industry values occur among complete rows;
7. no successful identity has more than one conflicting classification in the
   same run;
8. exact raw bytes and SHA-256 are retained per request.

## Classification

PASS_PROSPECTIVE_SECTOR_SOURCE_FEASIBILITY

only if every frozen gate passes.

Otherwise:

FAIL_PROSPECTIVE_SECTOR_SOURCE_FEASIBILITY.

## Promotion boundary

A PASS result authorizes only a separately frozen broad prospective sector
snapshot collector.

A PASS result does NOT authorize:

- historical backfill before D009;
- retroactive use in C001/C002;
- direct RM001 sector-factor promotion;
- live capital.

A future sector factor requires a separately frozen prospective history,
classification-change policy, coverage threshold and forecast validation.

## Prohibited

- no return labels;
- no alpha/model fit;
- no today's-classification backfill to past sessions;
- no HTML text inference when the JSON field is absent;
- no third-party sector substitution;
- no live capital.
