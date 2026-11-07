# CC001: lossless generated-report history and checkpoint recovery

## Actual incident

The first merged P008 daily run generated its research outputs, but its existing
128 MiB expanded checkpoint limit stopped persistence. The branch still held the
previous valid checkpoint. The uploaded top-level reports were newer than that
checkpoint and must not be described as a successfully persisted workspace.

Generated full-snapshot JSON/HTML reports repeated earlier evidence and consumed
28.12 MiB in the previously restored workspace alone. Those reports are useful
audit history, but they do not need to be expanded into the active SQLite/source
workspace on every run.

## Correction without removing evidence

`company_change_report_archive` moves only generated files below `reports/` into
content-addressed, immutable history parts under a separate `report-history/`
directory on the existing `cc001-state` branch. Original source blobs, captures,
extractions, reviews, decisions and the SQLite database are not moved or edited.

Each part records original relative paths, byte lengths and SHA-256 values. A
receipt links every original report to its archive. The complete parts, receipt
and still-present report bytes are checked before active report copies are
removed. A verification failure leaves the active reports intact. An interrupted
removal does not destroy history because the verified archive is already present.
A historical report is recoverable byte-for-byte, not regenerated approximately.

Part publication is atomic and never overwrites a different existing archive.
Restore rejects traversal, symlinks, unknown member types, duplicate members,
manifest inconsistencies, changed content and nonempty target directories.
Independent per-part and aggregate limits apply before expanding any history.
Only JSON and HTML generated reports are eligible. Original documents cannot be
placed in this path to escape the original evidence-store constraints.

## Bounded pilot policy

- Active checkpoint limits are unchanged: 128 MiB expanded, 80 MiB compressed.
- Report-history parts are at most 32 MiB expanded.
- One archival batch is at most 128 MiB expanded and 25,000 files.
- Retained report history is capped at 256 MiB on disk.

The guard is not replaced with unlimited storage. If raw sources plus the
database reach the active limit, or report history reaches its separate limit,
the workflow stops. Sustained market-wide service still needs approved durable
object storage. This change neither provisions it nor claims production scale.
The existing public repository is for the public-source research pilot only.

## Daily operation

Before the active checkpoint, the workflow archives generated report history.
Both the new checkpoint and report-history files are added to the same state
commit, so the branch retains source records and report history together. The
existing latest-view HTML/JSON exports remain at their usual top-level paths.
Their current success/failure metadata still controls freshness claims.

The checkpoint JSON receipt is first written to a temporary path and moved into
place only after checkpoint success. A failed checkpoint no longer truncates the
previous receipt through shell redirection.

If export/persistence fails, a separate `cc001-uncheckpointed-recovery` Actions
artifact retains the actual working SQLite directory, source blobs and pending
reports. Normal artifacts also contain the report-history directory. This is a
14-day recovery artifact, not proof of durable branch persistence. A run can
still correctly be red for unsupported source documents or historical identity
mismatches even when the checkpoint itself is safely saved.

Schedule cadence, 40-document intake, three-issuer context batch, source authority,
review gates, live-capital settings and frozen experiments remain unchanged.

## Local interface

```bash
python -m marketlab.company_change_report_archive archive \
  --workspace .marketlab/cc001 \
  --history .marketlab/cc001-report-history
```

The command prints the receipt hash. `restore` mode takes the exact receipt JSON
as `--history` and an empty directory as `--workspace`, recreating the original
`reports/` paths. Archives are also ordinary ZIP files with manifests for audit.
Do not run the archiver concurrently with a process rewriting those reports.
The daily workflow's existing concurrency group provides its single-writer gate.

## Verification

Tests cover exact report-byte restoration, unchanged original source and database
bytes, idempotent repeated input, split parts, corrupted archives, storage bounds,
unsafe paths, symlinks, conflicting destinations, and checkpoint recovery under
an intentionally small test cap. A real retained workspace was also archived and
restored separately. These tests establish persistence behavior, not semantic
accuracy or investment performance.
