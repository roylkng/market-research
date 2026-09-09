# H018 remaining-session resolution rule, frozen before first outcome

Status: **FROZEN BEFORE ANY H018-v1 SELECTION OR OUTCOME IS OPENED**

This note changes calendar/source acquisition only. It does **not** change H018-v1 dates, company eligibility, liquidity rule, low-volatility score, top-50 selection count, semiannual schedule, execution convention, benchmark identity, random seed, friction, comparators, or pass/fail gates.

## Context

The exact acquisition-only corpus from workflow run `34329703489` contains 1,029 durable checkpoints: 861 `COMMON_SESSION` checkpoints and 168 `NO_SESSION` checkpoints. It leaves 279 calendar dates unresolved. The acquisition-only summary records `market_selection_outcomes_opened: false`, with zero parser errors, fetch failures, or source mismatches in the second accelerator pass.

The unresolved set contains two qualitatively different cases:

1. dates where one official market source is already valid, which are trading-session candidates and must never be classified as holidays merely because the other source is unavailable;
2. dates where all observed evidence is absence/blocking, which require stronger official-source evidence before a `NO_SESSION` checkpoint may be written.

The earlier conservative H018 runner is not informative for these dates because it repeatedly retries the same blocked archive host and resolved zero of 328 unresolved dates across two full acquisition passes.

## Frozen multi-host resolution rule

Before first H018-v1 outcome access, the remaining dates may be resolved using only exact official NSE/NSE Indices static sources under these rules.

### Trading-session rule

A date is a `COMMON_SESSION` only when both of the following exact source documents are obtained and parse successfully for the same requested date:

- an official NSE cash-equity bhavcopy from `archives.nseindia.com` or `nsearchives.nseindia.com`;
- an official broad-index daily snapshot containing the frozen Nifty 500 benchmark, or its already-frozen pre-2015-11-09 `CNX 500` source label, from one of:
  - `archives.nseindia.com/content/indices/ind_close_all_DDMMYYYY.csv`,
  - `nsearchives.nseindia.com/content/indices/ind_close_all_DDMMYYYY.csv`,
  - `www.niftyindices.com/Daily_Snapshot/ind_close_all_DDMMYYYY.csv`,
  - `niftyindices.com/Daily_Snapshot/ind_close_all_DDMMYYYY.csv`.

HTTP 200 alone is not evidence. The bytes must pass the existing exact-date bhavcopy parser or frozen H018 Nifty/CNX 500 parser. HTML, empty bodies, malformed CSV, wrong dates, or other indices do not qualify.

If either side produces a valid source, the date is a **trading-session candidate** and must not be written as `NO_SESSION`. It remains unresolved until the other side is independently recovered.

### No-session rule

A `NO_SESSION` checkpoint may be written only when all of the following are true after the resolver retries the official hosts:

1. no official bhavcopy host returns a valid parsable cash-equity bhavcopy for the date;
2. no official index host returns a valid parsable Nifty/CNX 500 daily row for the date;
3. at least one official NSE bhavcopy archive host returns an explicit HTTP 404 for the exact dated bhavcopy path;
4. both NSE index archive hosts return explicit HTTP 404 for the exact dated daily-index path;
5. neither Nifty Indices daily-snapshot host returns a valid parsable benchmark row.

This rule intentionally does not infer closure from weekday/weekend status because the frozen period contains real special weekend trading sessions. Calendar labels are therefore not sufficient evidence by themselves.

### Failure behavior

Any date that does not satisfy either the full `COMMON_SESSION` rule or the full `NO_SESSION` rule remains unresolved. It must not be guessed, forward-filled, dropped silently, or converted to a holiday.

## Outcome blindness

The resolver is acquisition-only. It must not create or read `point-in-time-selections.json`, `challenge-summary.json`, `selected.csv`, or any H018 outcome-derived artifact. Only after the market-source calendar is complete may the unchanged frozen H018-v1 challenge execute.
