# Research universe U001

## Goal

Define the prospective H002/H003 coverage panel without discretionary stock selection.

## Frozen selection rule

For each prospective earnings cohort:

1. Fetch the official NSE Nifty 200 constituent CSV and the NSE Nifty 200 live index payload.
2. Require the two source populations to contain exactly the same 200 symbols.
3. Exclude constituent rows whose official CSV `Industry` is `Financial Services`.
4. Rank the remaining constituents by NSE free-float market capitalization (`ffmc`) descending.
5. Break ties by NSE symbol ascending.
6. Select the first **100** companies.
7. Freeze that snapshot for the entire earnings cohort. A later index rebalance affects only a later cohort.

The implementation is frozen as:

`U001-nifty200-top100-nonfinancial-ffmc-v2`

If the official sources disagree, an Industry classification or ISIN is missing, or fewer than 100 eligible names remain, snapshot creation fails. Missing metadata is never silently skipped to manufacture a 100-company list.

This is a **research coverage panel**, not a portfolio and not a list of companies expected to outperform.

## Why the dual-source design

The Nifty 200 live payload supplies the point-in-time FFMC used for ranking, but it does not provide the complete constituent identity/classification contract required by the experiment. The official constituent CSV supplies the exact 200-name membership, company name, `Industry`, series and ISIN.

Using both sources removes the previous need to issue one quote-metadata request per constituent and makes the financial-sector exclusion auditable from a single source artifact.

## Why Nifty 200

Nifty 200 combines large- and mid-cap companies and provides a liquid, broad starting population. The 100-company cap is an operational research choice: large enough for a useful cross-section while keeping prospective filing capture and manual source audits tractable during the first cohort.

The 100-stock limit is not a claim that 100 observations are statistically sufficient. Each eligible quarterly event becomes an observation over time.

## Snapshot record

Every snapshot preserves at least:

- schema/rule version
- cohort identifier
- UTC capture timestamp
- NSE index timestamp
- both source URLs
- canonical SHA-256 of the complete index payload
- raw SHA-256 of the constituent CSV bytes
- symbol
- ISIN
- company name
- official constituent `Industry`
- trading series
- free-float market capitalization used for ranking
- source rank before financial-sector exclusion
- final rank after exclusion
- canonical SHA-256 for the complete frozen snapshot

## Point-in-time behavior

Snapshots are immutable. A later symbol change, index rebalance, industry reclassification, merger, delisting or correction does not rewrite an older cohort.

A revised cohort source creates a new snapshot/version with provenance. It does not silently overwrite the snapshot used by already-captured observations.

## H002 eligibility after universe membership

Universe membership does not guarantee an H002 signal. A member can still be recorded as `NO_SIGNAL` for reasons frozen by H002, including unavailable expected EPS, missing historical EPS needed by the expectation model, non-tradable entry or unresolved corporate-action normalization.

Such observations remain visible in the ledger with reason codes.

## H003 use

H003 uses the same frozen U001 cohort boundary. Its company-delivery feature must be computed using only claim/outcome evidence available by the U001 snapshot date.

## Separate development cohort

The manually chosen development companies in `registry/development_companies.yaml` exist to stress document parsing and company-intelligence workflows. They do not enter H002 or H003 by exception. A development company participates only when it independently satisfies the frozen U001 rule.
