# HG006-D001 P1 Parallel Acquisition Sharding Amendment v1

Status: **FROZEN BEFORE HG006-D001 SOURCE OUTPUT IS OPENED**  
Frozen: 2026-10-05  
Scientific source rules changed: no  
Return outcomes opened: no

## Purpose

Change only the execution topology of HG006-D001 historical source acquisition.

The original single-job runner issues one exact NSE request per calendar day from
2023-01-01 through 2026-09-30. This is scientifically correct but operationally fragile:
a late transient failure would lose an entire long-running job.

P1 parallelizes the same exact daily requests into four immutable date shards.

## Frozen shards

- H2023: 2023-01-01 through 2023-12-31;
- H2024: 2024-01-01 through 2024-12-31;
- H2025: 2025-01-01 through 2025-12-31;
- H2026: 2026-01-01 through 2026-09-30.

## Unchanged source semantics

Each calendar day still uses exactly one whole-market NSE announcement request with:

- from_date = that calendar day;
- to_date = that calendar day.

The canonical announcement parser, taxonomy, initiation window, follow-up cutoff,
thresholds and right-censoring rules remain unchanged.

## Shard evidence

Every shard retains:

- exact raw daily bytes;
- day -> raw SHA-256 mapping;
- row count;
- requested date boundaries.

## Deterministic combine gate

The final census may materialize only when:

1. all four frozen shard manifests exist;
2. every day from 2023-01-01 through 2026-09-30 appears exactly once;
3. no day appears in more than one shard;
4. every retained raw file hashes to the manifest SHA-256;
5. no date lies outside its frozen shard boundaries.

The combine step then calls the unchanged
`build_historical_event_census` implementation.

## Scientific boundary

P1 does not change:

- the historical population;
- event taxonomy;
- source endpoint;
- completion ontology;
- sample thresholds;
- any probability or return calculation.
