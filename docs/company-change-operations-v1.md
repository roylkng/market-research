# CC001 P004: operational research pilot

This completes broad issuer discovery, original XBRL intake, a usable local
review desk, and bounded restartable daily processing around the existing CC001
runtime. It does not claim a live LLM provider, commercial data licence, stock
selection advantage, or investment approval.

## Run the local research desk

```bash
python -m marketlab.company_change_discovery --workspace .marketlab/cc001 --days 7 --limit 40 --fetch
python -m marketlab.company_change_app --workspace .marketlab/cc001 --port 8765
```

The desk is at http://127.0.0.1:8765. It is a loopback-only single-workspace
research tool. It does not expose a public server or implement multi-user SaaS
identity. It shows extracted facts, exact evidence, financial calculations,
source hashes, reporting periods, review status and unresolved disclosures.
Accepting facts is not approving an investment or a trade. A changed extraction
must be reviewed separately. Reviews are local operator attestations.

The server checks its Host header, requires an unpredictable review form token,
limits request sizes, escapes source text, and has no document-fetch or model
execution endpoint. The /features.json endpoint exports reviewed facts only.
These controls are not a substitute for authenticated production hosting.

For a read-only portable report:

```bash
python -m marketlab.company_change_app --workspace .marketlab/cc001 --export research-desk.html
```

## Discovery and the denominator

The official current EQ security master supplies symbol/ISIN identity. Existing
NSEClient acquisition is reused. Integrated-financial response pages are read
with explicit page/size controls, source totals and repeat detection. Original
JSON bytes are retained. Financial disclosure candidates and general corporate
announcements are not selected by favourite ticker, price performance or model
prediction. The first processing policy is chronological with a bounded batch.

A current security master is not historical universe membership. Coverage is the
exchange response obtained, not a certified all-market historical census.
Malformed, out-of-window, non-EQ and unsupported-source rows have recorded
exclusion reasons. Announcements without supported economic mappings remain
NEEDS_SEMANTIC_MAPPING. They are counted, not silently converted to investment
signals. Discovery is not an unrestricted commercial-news crawler.

The persistent queue retains PENDING, PROCESSING, EXTRACTED, FAILED and unsupported
states. Interrupted processing leases can be reclaimed. Automatic retries stop
after three failures. The explicit --retry-failed operator action retains attempt
counts. A source failure does not erase successful documents in the same batch.
No facts are automatically marked as reviewed.

The original first discovery probe found a 20-row paginated response and XML
links. It processed zero originals. Its zero-error exit was not extraction
success. The corrected smoke gate now requires at least eight attempted source
documents and zero failed processing attempts. Financial pagination retains all
pages received rather than treating the first page as the universe.

## Original XBRL, not generated stand-in documents

The original XML adapter uses numeric unitRef definitions, context durations,
issuer identity and standalone/consolidated scope. Monetary INR values are
converted from rupees to crore. It never rescales raw XBRL values using the
statement's display-rounding label. Per-share amounts retain per-share units.
Nil facts stay absent. Dimensional segment contexts are not silently treated as
whole-company results. Conflicting duplicate facts/contexts fail.

Each fact retains its original concept, contextRef, unitRef, literal and byte
hash. Reported group profit is never substituted for absent owner-attributable
profit. Recognized spelling variants of the NSE owner-profit concepts are
mapped explicitly. When reported owner-plus-minority profit fails to reconcile
with group profit, the raw values are preserved and a review warning is shown.
No missing normalization or exact diluted share count is invented.

Original HTML is also supported. Dates and periods come from the document, not
from a guessed quarter or transformed source URL. XML and HTML remain separate
source representations. No existing frozen experiment parser is modified.

## Daily operation and durable pilot state

The new `CC001 daily research operations` workflow runs at the configured daily
14:47 UTC schedule, supports manual runs, and initializes once when its workflow
is merged to main. It processes at most 40 documents per run with a seven-day
discovery lookback. Old pending work remains in the database beyond the lookback.
This is medium-frequency research capture, not time-guaranteed trading data.
Actual observations, not scheduled times, determine information availability.

State is kept in the dedicated **cc001-state** branch, never in frozen research
folders on main. Runs share a concurrency group. Existing branch identity is
checked using STATE_FORMAT before restoration. The code refuses to reinitialize
a workspace when remote-state inspection fails, and it never force-pushes.

SQLite uses its backup API for a consistent checkpoint. Each archive member has
a content hash. Restore rejects traversal, symlinks, unexpected paths, modified
members and nonempty destinations. The pilot has a 128 MiB expanded-state cap and
80 MiB compressed-state cap. Reaching the cap stops rather than deleting evidence.
This bounded Git-backed pilot needs approved object storage for sustained scale.
It is not represented as unlimited production storage.

`latest.json` and the read-only desk expose current coverage, run identity,
source commit and review backlog. Source failures still make the run fail after
checkpointing useful work. Actions artifacts are retained for 14 days. The state
branch persists independently of that artifact retention. New schedules and
state are isolated from the existing H-series/HG009/AE001 collectors and ledgers.

## Verification boundaries

Software tests cover discovery pagination, raw response hashes, exclusions,
bounded retries, XML units and dimensions, nil values, issuer/scope checks,
original-byte persistence, review actions, browser request guards, and checkpoint
round trips. Live source smoke tests exercise original disclosures outside the
three-company development list. A source count is not an accuracy percentage.

The original-byte artifacts permit independent review. The same engineer writing
and checking parser rules is not an independent annotation team. A model endpoint
remains unconfigured until an approved endpoint and usage budget exist. No paid
model calls, broker connections or commercial customer deployment are created.
The controlled predictor evaluator exists, but real prospective performance and
licensed multi-user commercial deployment remain separate acceptance gates.
