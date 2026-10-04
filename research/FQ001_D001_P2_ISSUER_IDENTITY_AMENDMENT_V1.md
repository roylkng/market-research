# FQ001-D001 P2 Issuer Identity Continuity Amendment v1

Status: **FROZEN AFTER P1 SOURCE FEASIBILITY, BEFORE P2 RERUN**
Frozen: 2026-10-04
Return outcomes opened: no
Portfolio eligibility: disabled
Live capital: disabled

## Motivation

P1 passed every frozen source-feasibility threshold with 83 complete rows. The remaining
17 failures include five cases where official filings exist but strict historical
symbol/ISIN equality rejects the same issuer across a corporate identity transition.

Observed source-only cases:

- COFORGE: FY25 ISIN `INE591G01017`, FY26/current U001 ISIN `INE591G01025`,
  symbol remains COFORGE;
- ADANIPOWER: FY25 ISIN `INE814H01011`, FY26/current U001 ISIN
  `INE814H01029`, symbol remains ADANIPOWER;
- BAJAJ-AUTO: FY25 symbol `BAJAJ-AUTO`, FY26 filing symbol `BAJAJAUTO`,
  ISIN remains `INE917I01010`;
- LTM: FY25 filing symbol `LTIM`, FY26/current symbol `LTM`, ISIN remains
  `INE214T01019`;
- TMPV: FY25 filing symbol `TATAMOTORS`, FY26/current symbol `TMPV`, ISIN remains
  `INE155A01022`.

These are accounting-statement continuity cases. FQ001 does not use per-share facts, so
a share split / ISIN replacement by itself does not invalidate historical assets, cash
flow, profit or capital-employed facts.

## Frozen P2 identity rules

### Target filing

The target FY26 filing must match the frozen current U001 member's ISIN whenever both
contain an ISIN.

A target symbol formatting or rename mismatch may be accepted only when that exact
current ISIN match exists.

### Baseline filing

After the target identity is validated, the FY25 baseline is accepted only when at least
one deterministic issuer-continuity condition holds:

1. baseline ISIN equals target ISIN; or
2. normalized baseline symbol equals normalized target symbol.

Symbol normalization is limited to uppercase alphanumeric characters. It removes
punctuation such as hyphens but does not perform fuzzy matching or name similarity.

Thus:

- same-ISIN symbol renames are accepted;
- same-symbol ISIN replacements are accepted;
- an unrelated issuer that matches neither condition fails closed.

### Provenance

Every successful record must retain the target and baseline reported symbols and ISINs
so the accepted lineage is auditable.

## Unchanged rules

P2 changes no economic metric, score, model, universe, period pair, accounting-basis
preference or feasibility threshold.

The three non-March financial-year cases remain excluded. The one archive 404 and eight
missing same-basis pair cases remain source failures unless independently repaired under
another frozen source amendment.

No return outcomes are opened.
