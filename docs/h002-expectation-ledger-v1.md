# H002 pre-filing expectation ledger v1

## Objective

H002-R001 is only prospective if its expected EPS existed before the result. A timestamp
inside an expectation object is not sufficient evidence because that object could be
constructed after publication with a backdated `expectation_as_of_utc`.

This ledger creates a separate immutable capture boundary before the filing arrives.
It does not change the H002 signal formula.

## Frozen rule binding

The ledger accepts only H002-R001 and binds every record and cohort manifest to the
frozen signal-rule SHA-256:

`a86218ec529ea53f7c7918d415961bcda30c5bbdda141a05ae13225c081db2c6`

A different 64-character digest is rejected rather than treated as another compatible
rule.

## One slot per company

Within a U001 earnings cohort there is exactly one expectation slot per symbol.

The first valid capture wins. Repeating the exact same expectation is idempotent.
Trying to replace that slot with a different expectation is an error, even if the new
record is captured before the eventual filing. This deliberately removes the ability to
iterate expectation variants and select the favorable one after outcomes become known.

If the first record is wrong, the observation should be treated as unusable rather than
rewriting the research history.

## Two-stage freeze

### Stage 1: expectation capture

Each record preserves:

- cohort id,
- frozen universe snapshot hash,
- H002-R001 rule hash,
- ledger capture timestamp,
- complete expectation payload hash,
- complete record hash,
- the schema-2 H002 expectation itself.

The expectation's claimed information cutoff cannot be later than the ledger capture
time. The universe must already have been frozen when the expectation is captured.

### Stage 2: cohort manifest

Before the cohort starts producing result filings, the records are sealed into one
manifest. The manifest partitions the complete frozen U001 universe into:

- symbols with exactly one captured expectation, and
- explicit `uncovered_symbols`.

After the manifest exists, no new expectation can be added to that cohort. An uncovered
symbol therefore cannot be silently added after its result is known.

Capture and manifest freeze share a cohort file lock so a concurrent writer cannot race
a new expectation across the manifest boundary.

## Prospective scoring gate

`ExpectationStore.load_for_event` accepts only a prospective event whose cohort and
universe snapshot match the ledger. It then requires both:

- the expectation record capture time to be strictly before exchange publication, and
- the manifest freeze time to be strictly before exchange publication.

The record id used for scoring must be the same id committed into the frozen manifest.
A symbol listed as uncovered produces an explicit `ExpectationNotFrozen` state rather
than falling through to an arbitrary expectation.

`ExpectationStore.score_event` is the preferred H002 prospective scoring path because it
resolves the expectation through this gate before calling the existing H002-R001 scorer.

## Tamper evidence

Records and manifests contain canonical SHA-256 identities and are written with
exclusive-create semantics. Valid JSON edits to a stored record or manifest are detected
when it is reloaded.

This is tamper-evident local storage, not a trusted timestamp authority. A user with
filesystem and clock control can still manipulate local evidence. For research-grade
external anchoring, the frozen cohort manifest should be exported and committed to the
hosted repository, or anchored by another trusted timestamp service, before the first
eligible filing in the cohort is published.

## Platform behavior

Concurrent-safe writes currently use POSIX file locking. The module remains importable on
platforms without `fcntl`, but capture/freeze operations fail closed rather than silently
falling back to an unsafe concurrent-write mode.

## Non-claims

This ledger creates no return observation and provides no evidence that H002 is
profitable. It changes neither `expected_eps`, UE, the entry rule, the 20-session holding
period nor the benchmark set. Live capital remains disabled.
