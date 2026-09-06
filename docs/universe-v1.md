# Research universe v1

## Goal

Define the prospective H002 coverage panel without discretionary stock selection.

## Frozen selection rule

For each prospective earnings cohort:

1. Fetch the official NSE Nifty 200 constituent snapshot.
2. Exclude constituents whose NSE macro-sector classification is `Financial Services`.
3. Rank the remaining constituents by NSE free-float market capitalization (`ffmc`) descending.
4. Break ties by NSE symbol ascending.
5. Select the first **100** companies.
6. Freeze that snapshot for the entire earnings cohort. A later index rebalance affects only a later cohort.

If fewer than 100 companies can be classified deterministically, snapshot creation fails. Missing metadata is never silently skipped to manufacture a 100-company list.

This is a **research coverage panel**, not a portfolio and not a list of companies expected to outperform.

## Why Nifty 200

Nifty 200 combines large- and mid-cap companies and provides a liquid, broad starting population. The 100-company cap is an operational research choice: large enough for a useful cross-section while keeping prospective filing capture and manual source audits tractable during v1.

The 100-stock limit is not a claim that 100 observations are statistically sufficient. Each eligible quarterly event becomes an observation over time.

## Snapshot record

Every snapshot must preserve at least:

- schema/rule version
- cohort identifier
- UTC capture timestamp
- NSE index timestamp where supplied
- source URL(s)
- symbol
- ISIN
- free-float market capitalization used for ranking
- rank before and after financial-sector exclusion
- NSE macro sector
- sector
- industry
- basic industry
- listing date where supplied
- canonical SHA-256 for the final snapshot

## Point-in-time behavior

Snapshots are immutable. A later symbol change, index rebalance, sector reclassification, merger, delisting, or correction does not rewrite an older cohort.

A revised source snapshot creates a new version with provenance. It does not overwrite the original bytes or normalized output.

## H002 eligibility after universe membership

Universe membership does not guarantee an H002 signal. A member can still be recorded as `NO_SIGNAL` for reasons frozen by H002, including unavailable expected EPS, missing historical EPS needed by the expectation model, non-tradable entry, or unresolved corporate-action normalization.

Such observations remain visible in the ledger with reason codes.

## Separate development cohort

The manually chosen development companies in `registry/development_companies.yaml` exist to stress document parsing and company-intelligence workflows. They do not enter H002 by exception. A development company participates in H002 only when it independently satisfies this frozen universe rule.
