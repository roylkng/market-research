# H002-D production orchestrator v1

## Goal

Run the frozen FY27-Q2 H002 prospective experiment automatically without discretionary inclusion, mutable runtime state, or loss of point-in-time evidence when GitHub Actions workers disappear.

This layer does not change H002-R001, H002-X001, H002-D001, U001, or any signal threshold.

## Schedule

The production workflow runs once daily at 13:00 UTC, which is 18:30 Asia/Kolkata. The frozen discovery window is 1-Oct-2026 through 31-Jan-2027. Before or after that window, the workflow does not poll NSE or manufacture observations.

A daily post-market run is sufficient for the frozen second-subsequent-session entry rule. A result discovered the day after a late evening filing is still captured before the scheduled second subsequent session can open.

## Persistent evidence branch

GitHub-hosted runners are ephemeral. Runtime evidence therefore lives on a dedicated branch:

`evidence/h002-fy27q2`

Each active run checks out that branch in a separate worktree, runs the canonical code from `main`, then commits only the runtime evidence tree. This keeps `main` free of accumulating raw observations while preserving the full append-only experiment state.

The runtime root is:

`research/prospective/runtime/FY27-Q2-2026-09-06/`

It contains the content-addressed filing and market-data store, hash-chained observation snapshots, the latest completed-only report, immutable per-run summaries, and per-run GitHub anchor metadata.

If the cohort iteration fails after capturing only part of the universe, the workflow still commits any partial runtime evidence in an `always()` step. This protects the original local capture timestamps from being lost and recreated later.

## Sources

Result discovery and filing bytes use NSE Integrated Filing data and original NSE archive documents.

Stock execution prices use the official CM UDiFF Common Bhavcopy Final ZIP. Benchmark execution prices use the official Indices Daily Snapshot CSV. The runner does not use NSE historical JSON price endpoints because a hosted-runner probe on 6-Sep-2026 showed that those endpoints returned anti-bot HTML with HTTP 200.

## Frozen calendar

The first live calendar snapshot is:

`research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json`

Calendar SHA-256:

`2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce`

It is built from exact NSE holiday-master bytes and explicit regular 09:15-15:30 Asia/Kolkata cash-market sessions. November 8, 2026 remains an unresolved Muhurat special-session date because NSE has not yet published exact session times. Any position whose schedule depends on that date is `CALENDAR_PENDING`, not guessed.

The v1 calendar ends on 31-Dec-2026. A delayed result requiring 2027 sessions also remains `CALENDAR_PENDING` until a separately versioned 2027 calendar is frozen.

## Idempotency and revisions

The first eligible filing is chosen by earliest official NSE publication timestamp for the frozen symbol, target period, and accounting basis. Later revisions are retained but never rescore the observation.

Repeated polling of identical raw bytes reuses the original artifact identity and capture timestamp. Reconstructing the same pending paper position at a later poll does not create a new semantic ledger state merely because `evaluation_as_of_utc` changed.

## Corporate-action integrity

Price-basis audits are phase-specific:

- expectation freeze to result publication,
- publication to paper entry,
- publication to paper exit.

If a share-basis action changes the price basis between entry and exit, the observation becomes `PRICE_BASIS_UNRESOLVED`. The runner does not let the lower-level execution engine turn that into a generic error or silently compare incomparable raw prices.

## Evaluation

Only latest `COMPLETED` positions enter return statistics. Pending, skipped, price-basis-unresolved, calendar-pending, unresolved-exit, and error states remain visible but cannot leak partial returns into the evaluation.

Every generated report remains paper-only and explicitly records `live_capital_allowed: false`.
