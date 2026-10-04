# FQ001-D001 P2 Issuer Identity Continuity Amendment v1

Status: **FROZEN BEFORE CORRECTED P2 RERUN**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

P1 passed the original FQ001 source-feasibility thresholds with 83/100 complete rows.
Some remaining exclusions are issuer-identity transitions rather than missing accounting
data. P2 permits only deterministic continuity rules that can be verified from exact ISIN
or official NSE ISIN-change evidence.

No return outcomes are opened and no economic metric or feasibility threshold changes.

## Rule A: same-ISIN continuity

A historical filing may use a changed or reformatted symbol when:

- target filing ISIN equals the frozen U001 ISIN; and
- baseline filing ISIN equals the target filing ISIN.

This admits ticker renames such as LTM/LTIM and punctuation changes such as
BAJAJ-AUTO/BAJAJAUTO without fuzzy name matching.

## Rule B: official NSE ISIN bridge

When baseline and target ISIN differ, continuity is allowed only through:

`research/fq001/fq001-isin-bridges-v1.json`

A bridge is valid only when all are true:

1. bridge symbol equals the frozen U001 symbol;
2. baseline filing ISIN equals bridge old ISIN;
3. target filing ISIN equals both bridge new ISIN and frozen U001 ISIN;
4. bridge effective date is strictly after baseline filing publication;
5. bridge effective date is on or before target filing publication;
6. corporate action is a frozen share sub-division;
7. evidence URL is an official `nsearchives.nseindia.com` source.

The frozen bridge file contains exactly:

- COFORGE: INE591G01017 -> INE591G01025, effective 2025-06-04;
- ADANIPOWER: INE814H01011 -> INE814H01029, effective 2025-09-22.

No same-symbol ISIN change is accepted without an explicit frozen bridge.

## Audit output

Every successful FQ001 record retains:

- target and baseline reported symbols;
- target and baseline ISINs;
- continuity state:
  - `SAME_ISIN`, or
  - `VERIFIED_NSE_ISIN_BRIDGE`;
- source record hashes.

## Unchanged rules

P2 does not change:

- the frozen 100-name U001 universe;
- FY26/FY25 annual period pair;
- accounting-basis selection;
- six quality metrics;
- missing-value policy;
- 70 same-basis-pair threshold;
- 60 complete-row threshold;
- 60 per-metric coverage threshold;
- scoring rules;
- PF001 or live-capital state.

Non-March financial-year cases, archive failures and missing same-basis filing pairs
remain fail-closed unless addressed by a separately frozen source amendment.
