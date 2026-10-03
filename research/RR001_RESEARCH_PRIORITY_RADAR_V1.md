# RR001 Research Priority Radar v1

Status: FROZEN HEURISTIC BEFORE MATERIALIZATION  
Frozen: 2026-10-03  
Outcome-bearing experiment: NO  
Live capital: DISABLED

## Purpose

RR001 answers one operational question:

> Which frozen U001 companies deserve scarce analyst research time now?

It does **not** answer:

- which stock will outperform;
- which stock should be bought;
- which company belongs in PF001;
- whether any RR001 component is validated alpha.

If RR001 is later tested as a return-predictive rule, that test requires a new
preregistered outcome-bearing trial and explicit RTA001 accounting before
outcomes are opened.

## Frozen universe

Input:

`research/prospective/universes/FY27-Q2-2026-09-06.json`

Exactly 100 non-financial Nifty 200 names. No substitutions.

## Frozen market snapshot

Market end:

`2026-10-01`

Official NSE cash UDiFF and Nifty 500 index archives only.

Historical source start:

`2026-06-01`

RR001 uses no market observation after 2026-10-01.

## Frozen consensus snapshot

Input:

`research/prospective/h021/captures/2026-09-25-full-u001-v1.json.gz`

Manifest:

`research/prospective/h021/captures/2026-09-25-full-u001-v1.manifest.json`

RR001 consumes current forward consensus **levels**, not H021 revision outcomes.

Consensus-derived components are eligible only when analyst count is at least 5.
Missing or ineligible components are not imputed and contribute zero to the
composite priority score.

## Short-horizon priority

Equal-weight percentile average of:

1. stock 20-session return minus Nifty 500 20-session return;
2. closeness to the trailing 20-session high;
3. current traded-value turnover divided by prior-20-session median turnover.

No return outcome after 2026-10-01 is used.

## Mid-horizon priority

Equal-weight percentile average of:

1. stock 60-session return minus Nifty 500 60-session return;
2. current forward revenue-growth forecast;
3. current forward profit-growth estimate;
4. current consensus target upside versus 2026-10-01 close.

## Long-horizon priority

Equal-weight percentile average of:

1. current forward revenue-growth forecast;
2. current forward profit-growth estimate;
3. current consensus target upside versus 2026-10-01 close.

This is deliberately simple. No weights are fit or tuned on subsequent returns.

## Context-only signals

H022, H023 and H024 prospective state may be attached to records for analyst
context. They do not modify RR001 scores in v1.

This prevents sparse experimental event signals from silently becoming a new
unregistered alpha blend.

## Sector-balanced research queue

For each horizon RR001 emits:

- raw top 25;
- a 15-name research queue;
- maximum two names from any frozen U001 constituent industry.

Sector balancing allocates research attention. It is not a portfolio constraint
or expected-return claim.

## Promotion path

A name surfaced by RR001 remains only a research candidate.

The path to PF001 is:

`RR001 candidate -> deep evidence review -> sealed Analyst Decision Object -> PF001 policy gates`

No RR001 row by itself is portfolio eligible.
