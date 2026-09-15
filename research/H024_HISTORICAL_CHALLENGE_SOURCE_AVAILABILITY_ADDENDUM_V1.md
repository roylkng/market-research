# H024 historical challenge source-availability addendum v1

Status: **FROZEN BEFORE H024 RETURN CONSTRUCTION**

Frozen: 2026-09-15
Applies to: `research/H024_HISTORICAL_CHALLENGE_IMPLEMENTATION_V1.md`
Live capital: disabled

## Reason for this addendum

The first execution attempt of the already frozen H024 historical challenge was GitHub Actions run `34956844902`.

The pre-outcome implementation gate passed in full:

- Ruff: passed;
- H024 pure/production tests: 39 passed;
- frozen Original source-panel SHA-256: `94bb81839c7d868736f830e88a3feb83538a04dfc7be01d546a7839e2bf3d101`.

The acquisition phase then fetched the official historical market files through the prior completed sessions but stopped before event-panel construction because the official NSE daily index snapshot for 2026-09-15 was not yet published:

`https://archives.nseindia.com/content/indices/ind_close_all_15092026.csv` -> HTTP 404

The failure occurred before `build_event_panel`, `build_outcome_report`, or `summarize_outcomes` ran. No H024 stock return, benchmark return, excess return, robustness result, or classification was produced or inspected.

## Frozen first-challenge market-data cutoff

For the first H024-v1 historical return challenge, the market-data cutoff is therefore fixed to the latest fully published official NSE session available to that first attempt:

**2026-09-11**

September 12 and 13 are weekend dates. September 14 is already frozen as an NSE cash-market holiday. Therefore September 11 is the immediately preceding completed NSE session in the frozen calendar.

The historical source-event discovery window remains unchanged at **2026-05-01 through 2026-09-15**. Filings whose planned entry lies after the September 11 market-data cutoff simply have no entry session inside this first challenge and cannot contribute a mature outcome.

## What does not change

This addendum does not change:

- H024 actor or transaction eligibility;
- Original-only signal construction;
- the same-symbol pre-entry revision blocker;
- H004 primary investability requirements;
- same-calendar-day execution prohibition;
- entry-price convention;
- 20/60/120-session horizon indexing;
- Nifty 500 benchmark;
- 50 bps cost stress;
- corporate-action blocking;
- bootstrap method or seed;
- robustness definitions;
- coverage gate;
- PROMISING/STRONG/REJECTED thresholds.

No alternative current-day price/index source is substituted for the unavailable frozen official daily file.

## Scientific boundary

The cutoff change is source-availability-driven and was fixed after a failed acquisition that emitted no H024 outcome report. It is not based on any observed H024 return. A later challenge with a later market-data cutoff must be separately versioned and may not replace or rewrite this first sealed result.