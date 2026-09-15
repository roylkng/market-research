# H020 prospective v1-v2 parallel stream

H020-v1 remains unchanged. H020-v2 is the frozen downside-guard challenger defined in `research/H020_V2_DOWNSIDE_GUARD_PROTOCOL_2026-09-15.md`.

Prospective validation begins with the completed **2026-09-16 NSE session**. The canonical append-only decision ledger is `v1-v2-parallel-ledger.json`; compact per-session reports are written under `scans/` only when a new completed-session decision is sealed.

The scheduled workflow uses the same point-in-time Yahoo chart source family as exploratory H020-v1 so the v1-v2 comparison is source-consistent. Raw responses are retained as workflow artifacts and the decision ledger seals their combined content fingerprint. Yahoo evidence is exploratory and cannot by itself authorize promotion or live capital. An official-NSE replication remains required before any promotion claim.

September 15, 2026 is the design case that motivated v2 and is excluded from v2 validation.

Live capital is disabled.
