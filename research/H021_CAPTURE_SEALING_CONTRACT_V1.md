# H021 capture sealing contract v1

Status: **FROZEN BEFORE THE SECOND FULL U001 WEEKLY CAPTURE**
Frozen: 2026-09-14
Live capital: disabled
Return outcomes opened: no

## Purpose

H021 depends on a prospective sequence of immutable analyst-consensus snapshots. The first full U001 anchor was captured on 2026-09-11. This contract makes subsequent full-panel captures machine-verifiable before any valid H021 revision cohort or H021 return outcome exists.

This contract does not change the H021 hypothesis, source hierarchy, 100-company universe, weekly cadence, revision window, analyst-count threshold, top-decile selection rule, or outcome definition.

## Frozen capture identity

Every full weekly capture must carry:

- `logical_capture_id`
- `capture_date_ist`
- explicit UTC `captured_at_utc`
- source version `H021-public-stockanalysis-spgi-plus-trendlyne-secondary-v1`
- frozen universe path `research/prospective/universes/FY27-Q2-2026-09-06.json`
- frozen universe Git blob `8026e81faee3e913d2fba1dba72d60603b69fa07`
- `research/H021_PROSPECTIVE_PROTOCOL_V1.md`
- `research/H021_COMPARISON_CONTRACT_V1.md`
- `research/prospective/h021/capture-batches-v1.json`

The logical capture ID must be exactly `YYYY-MM-DD-full-u001-vN`, where the date equals `capture_date_ist` and `N` is a positive integer. This also prevents a capture ID from being interpreted as an arbitrary filesystem path.

The India calendar date derived from `captured_at_utc` must equal `capture_date_ist`.

The first successfully sealed capture for a date uses `v1`. A correction uses a later version and must include a non-empty `correction_reason`. Correction versions preserve the original artifact rather than replacing it.

## Complete frozen cross-section

A full capture contains exactly one row for every frozen U001 symbol and no other symbol. Source failure, lack of coverage, identity ambiguity, or provider blocking cannot remove a symbol or substitute another company.

Each row must retain the frozen-universe identity:

- symbol
- ISIN
- universe rank
- fixed batch ID

Ranks 1-50 belong to B01 and ranks 51-100 belong to B02.

## Per-symbol data state

Every full-capture row has exactly one `data_state`:

- `OBSERVED`
- `PARTIAL`
- `NO_COVERAGE`
- `SOURCE_BLOCKED`
- `IDENTITY_UNRESOLVED`

Every row also retains explicit `retrieval_notes`.

`NO_COVERAGE`, `SOURCE_BLOCKED`, and `IDENTITY_UNRESOLVED` are current-capture failures. They must not carry forward prior EPS, revenue/profit forecasts, analyst count, or target price. Those current fields remain null. This prevents a stale previous observation from masquerading as a current consensus value.

`PARTIAL` preserves only fields explicitly observed in the current capture. Missing fields remain null.

## Immutable artifact bundle

`seal_h021_capture.py` converts a validated full-capture draft into exactly three artifacts using the logical capture ID:

1. `<capture-id>.json.gz`: deterministic gzip of canonical sorted JSON
2. `<capture-id>.manifest.json`: hashes, byte sizes, frozen identities, coverage counts, and batch summaries
3. `<capture-id>.md`: human-readable capture summary

The payload has both compressed and uncompressed SHA-256 hashes in the manifest. Verification also checks canonical JSON, deterministic gzip bytes, payload/manifest identity agreement, coverage totals, batch totals, and the manifest payload path.

If an artifact path already exists with identical bytes, sealing is idempotent. If the same logical capture ID is reused with different bytes, sealing fails. A correction therefore requires a new versioned capture ID and an explicit reason rather than rewriting history.

Repository CI automatically validates every future schema-v2 H021 capture bundle committed under `research/prospective/h021/captures/`. A malformed payload, false manifest summary, missing report, identity drift, or tampered hash therefore fails the repository gate.

## Source boundary

The sealer validates evidence structure. It does not acquire consensus data and does not authorize weaker sources.

The existing source hierarchy remains unchanged:

- public StockAnalysis pages identifying S&P Global Market Intelligence for primary annual EPS/revenue observations where available
- compatible public Trendlyne information only for secondary or explicitly labeled fallback fields
- no bypass of authentication, subscription, robots/access controls, HTTP 405/429, or download restrictions

A different provider or source-semantic contract requires a separately frozen source version before it can enter a primary H021 comparison.

## Information firewall

Capture sealing may not consume stock prices, returns, H013, H019, H020, PF001, valuation, subsequent news, or H021 future outcomes.

The purpose of sealing is to preserve what was observable at the capture time. It cannot be used to repair, backfill, or improve a capture after later market outcomes are known.

## Legacy anchor

The 2026-09-11 full U001 capture predates this sealer. Its gzip and uncompressed payload hashes, byte counts, frozen symbol set, explicit-EPS count, and analyst-count strata are independently verified in repository CI against its immutable manifest. It remains the valid first prospective full-panel anchor and is not rewritten into the new format.
