# H002 prospective preparation policy v1

## Objective

Freeze one immutable pre-filing H002 decision slot for every member of the already-frozen U001 cohort. Complete coverage means every company has either a READY numeric expectation or an explicit NO_SIGNAL record. It does not mean every company must produce a numeric signal.

This operational policy does not change H002-R001. The frozen rule still computes expected EPS from prior-year same-quarter EPS and sends missing or unusable required inputs to NO_SIGNAL.

## Accounting-basis selection

For the prior-year same-quarter baseline, MarketLab deterministically prefers a Consolidated Integrated Filing when one exists. If no Consolidated filing exists for that symbol and period, it uses Standalone. Ambiguous filings within the preferred basis fail closed and do not fall through to another basis.

The frozen expectation records the selected basis, and the future actual filing must match that basis before H002 can be scored.

## Official availability timestamp

The availability timestamp is taken from official NSE discovery metadata in this order:

1. broadcast_Date
2. revised_Date
3. creation_Date

A row without any parseable official timestamp is not usable. Exact discovery bytes are retained content-addressed alongside their SHA-256.

## Terminal NO_SIGNAL records

Two pre-filing conditions can occupy an immutable terminal NO_SIGNAL slot in v1:

- unresolved_corporate_action: an EPS-basis action is known but cannot be normalized without inventing an adjustment,
- baseline_identity_mismatch: the official historical filing uses a different symbol while matching ISIN proves issuer continuity; the old-symbol EPS is retained for audit but is not used numerically.

Terminal NO_SIGNAL uses expectation artifact schema 3. The baseline EPS may be retained as evidence, but expected_eps is always null and no numeric UE can be produced. A structural corporate_action_factor of 1.0 is present only to preserve the existing artifact shape and is explicitly not an economic adjustment for terminal NO_SIGNAL.

## Provenance

Preparation retains exact raw bytes for:

- Integrated Filing discovery payloads,
- corporate-action payloads,
- the selected filing source through EventStore.

The preparation attempt records the corresponding hashes. A complete bundle is freeze-ready only when all 100 U001 members have immutable expectation records and the required provenance hashes. Network, source-fetch, parse, and genuinely missing-baseline failures remain UNCOVERED and still block freezing.

## Live capital

Disabled. This policy creates research evidence only.
