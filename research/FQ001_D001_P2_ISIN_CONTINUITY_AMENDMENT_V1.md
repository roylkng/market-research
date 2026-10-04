# FQ001-D001 P2 ISIN continuity amendment v1

Status: **FROZEN BEFORE P2 RERUN**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

P1 passed the original source-feasibility thresholds with 83/100 complete rows.
Two remaining exclusions were not source failures: their FY25 filings carry the
pre-split ISIN while the frozen 2026 universe carries the post-split ISIN.

P2 permits only explicitly verified official-NSE stock-split ISIN transitions.
It does not relax symbol, period, source, or filing-basis identity.

## Frozen bridge file

`research/fq001/fq001-isin-bridges-v1.json`

Exactly two transitions are admitted:

- COFORGE: INE591G01017 -> INE591G01025, effective 2025-06-04;
- ADANIPOWER: INE814H01011 -> INE814H01029, effective 2025-09-22.

Both are official NSE-listed sub-division events.

## Frozen validation rule

A baseline ISIN mismatch may be accepted only when all are true:

1. target filing symbol equals frozen U001 symbol;
2. target filing ISIN equals frozen U001 ISIN;
3. baseline filing ISIN exactly equals a frozen bridge old ISIN;
4. bridge new ISIN exactly equals both target and U001 ISIN;
5. bridge symbol exactly equals the company symbol;
6. bridge effective date is strictly after baseline filing publication;
7. bridge effective date is on or before target filing publication;
8. bridge source is an official NSE archive URL.

No fuzzy company-name match, ticker-only override, manually inferred continuity,
or bridge discovered after score/return outcomes may be used.

## Deliberately unchanged

P2 does not change the six metrics, annual period pair, source-feasibility
thresholds, denominator rules, or any portfolio state.

All other P1 failures remain fail-closed.
