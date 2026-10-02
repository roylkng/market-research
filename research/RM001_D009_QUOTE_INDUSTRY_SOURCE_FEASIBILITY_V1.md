# RM001 D009 NSE Quote Basic-Industry Source Feasibility v1

Status: FROZEN BEFORE SOURCE SCAN
Frozen: 2026-10-02
Live capital: DISABLED

## Objective

Determine whether NSE's official current equity quote endpoint provides a
structured company-level four-tier industry classification with stable identity
fields suitable for starting a prospective point-in-time sector history.

D009 is a source-feasibility diagnostic only.

It opens:
- no return outcomes;
- no alpha outcomes;
- no risk-model fit;
- no portfolio optimization.

It does NOT authorize historical backfill.

## Official source

Endpoint:

    https://www.nseindia.com/api/quote-equity?symbol=<SYMBOL>

Acquisition must use MarketLab's NSE session/cookie client.

Exact response bytes are retained and SHA-256 hashed.

## Frozen sample

16 current NSE equity symbols:

- RELIANCE
- TCS
- HDFCBANK
- BHARTIARTL
- SUNPHARMA
- LT
- MARUTI
- HINDUNILVR
- TATASTEEL
- POWERGRID
- TITAN
- DIVISLAB
- BBOX
- WALCHANNAG
- DAMODARIND
- PIDILITIND

The sample intentionally spans large/mid/smaller names and multiple industries.

No symbol substitution is allowed after the source scan begins.

## Required structured fields

Identity:
- requested symbol;
- returned symbol;
- returned ISIN.

Classification object:
- Macro-Economic Sector;
- Sector;
- Industry;
- Basic Industry.

The parser may normalize JSON key punctuation/casing but must not infer a
classification value from free text.

## Frozen promotion gates

Prospective capture may be authorized only if:

1. at least 90% of the 16 symbols return a parseable quote payload;
2. at least 90% have exact requested-symbol identity;
3. at least 90% expose a non-empty ISIN;
4. at least 90% expose all four non-empty classification levels;
5. no returned symbol conflicts with the requested symbol;
6. all successful rows use one stable industryInfo semantic shape after
   normalized-key mapping;
7. exact raw response bytes are retained for every successful request.

## Promotion meaning

PASS_PROSPECTIVE_SOURCE_FEASIBILITY authorizes only a future prospective
classification capture design.

It does not establish:
- historical point-in-time classification;
- sector-factor risk improvement;
- publication timing relative to a trading decision;
- live-capital readiness.

A future prospective sector source must:
- freeze capture cadence before use;
- bind symbol to same-capture ISIN;
- retain exact raw evidence;
- record classification changes over time;
- never project the latest label backward.

## Failure

If the gates fail:

    FAIL_SOURCE_FEASIBILITY

Sector remains deferred.

Do not weaken D008/D009 by:
- scraping rendered text when structured fields are absent;
- inferring sectors from index membership;
- using current labels historically;
- mapping company descriptions with an LLM.

No live-capital implication.
