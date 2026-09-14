# H022-P001 acquisition and context contract v1

## Status

`FROZEN_BEFORE_FIRST_PROSPECTIVE_SOURCE`

Frozen: 2026-09-14

Prospective source boundary: `2026-09-14T18:30:00Z` = `2026-09-15 00:00:00 IST`

Live capital: **DISABLED**

Outcome data in acquisition: **FORBIDDEN**

## Purpose

This contract operationalizes the already-frozen H022-P001 signal core without changing its signal formula, universe, source classification, extraction rule, historical baseline, or prospective boundary.

Its purpose is to prevent three operational errors that the pure signal function cannot prevent by itself:

1. silently missing a transcript in the mandatory Sep-6-to-Sep-15 context gap;
2. supplying an older prior transcript while omitting the actual latest pre-start prior;
3. treating a signal frozen after its nominal H022-X001 entry open as if it had been executable at that open.

## Frozen sources and extraction

P001 acquisition reuses the existing audited contracts unchanged:

- discovery: `H003-C001`;
- discovery rule SHA-256: `a48e9cd1e1d56b69429696168fb1a2097b288d3179c7830ac79cbd8582835f0e`;
- source: official NSE corporate announcements only;
- attachment hosts: `nsearchives.nseindia.com` and `archives.nseindia.com`;
- transcript classification: the frozen H003-C001 transcript/conference-call policy;
- extraction: `H003-E002`;
- extraction rule SHA-256: `5aff200d6a2222a7cde972ad341bc43b927d9c5b6d26a58766893980515c24a2`;
- parser: `pypdf 6.17.0`;
- parser version: `h003_pdf_text_v1`;
- OCR: forbidden.

No transcript mirror, analyst website, LLM reconstruction, OCR fallback, or manually substituted document may replace an unavailable official source.

## Mandatory pre-start context catch-up

The exact context-only interval is:

```text
(2026-09-06T12:21:06.431463Z,
 2026-09-14T18:30:00Z)
```

The first successful context gate must prove discovery coverage for every member of the frozen U001 cohort.

A company with no qualifying source is valid only when its official NSE discovery request completed successfully and deterministically yielded zero qualifying sources. A failed or ambiguous discovery request is `INCOMPLETE`, not zero coverage.

Every discovered source in the strict interval must receive a valid `TEXT_READY` H003-E002 extraction record. Any fetch, parse, no-text, identity, source-policy, or extraction failure blocks the context gate.

The context gate cannot be sealed before the prospective boundary even if discovery/extraction completes earlier.

## Frozen historical baseline

The pre-existing historical context remains pinned to:

- expanded E002 report SHA-256: `45f58e5f0ee72c477ed042fd56be54b4b7c297b78532a011350a44d0a68da861`;
- expanded source-bundle SHA-256: `85d30df9286712c362102865c22ec3a27907e85599bd70d0c053bc95554cb34c`;
- historical cutoff: `2026-09-06T12:21:06.431463Z`.

The expanded historical report adds H022 membership metadata around original H003-E002 records. P001 may remove only those known enrichment fields when reconstructing the original E002 record for digest validation. It may not edit the original E002 fields.

## Static prior index

After the full catch-up succeeds, P001 seals one static prior entry for each of the 100 U001 companies.

For each symbol, combine:

1. its validated historical E002 records at or before the historical cutoff; and
2. all validated context-only catch-up E002 records after the cutoff and before prospective start.

Then select the latest publication timestamp group strictly before prospective start.

The sealed state is exactly one of:

- `NO_PRIOR_TRANSCRIPT`;
- `UNIQUE_PRIOR`;
- `AMBIGUOUS_PRIOR_TIMESTAMP`.

For every member of the selected timestamp group, the static prior index stores the exact `source_id`, `record_id`, publication timestamp, and source disposition.

A future signal sealer must prove that its supplied context contains every source/record identity in that symbol's frozen static prior group. It may not omit the static prior and fall back to an older record.

Later prospective records can naturally supersede the static prior under the already-frozen latest-strictly-earlier timestamp rule, but the original static prior remains immutable evidence.

## Context artifact binding

A valid operational context binds together by SHA-256:

- the full-U001 catch-up discovery manifest;
- the existing H022-P001 core context gate;
- the static prior index;
- the frozen U001 identity;
- the catch-up source count;
- the completion timestamp.

No outcome, price, benchmark, H021, H013, H019, H020, valuation, or post-publication-news input is permitted in any of these artifacts.

## Prospective discovery cadence

After the context gate is complete, prospective source discovery is run on every NSE business day with at least two operational passes:

1. a pre-open pass targeted before the 09:15 IST cash-market open;
2. an after-close pass targeted after the completed cash-market session.

The implementation may add more source-only passes without changing the signal formula. Every pass deduplicates by immutable H003-C001 `source_id` and may only append newly discovered sources.

The workflow schedule is an acquisition mechanism, not an assumption that the signal was available at a specific market time. Actual `signal_frozen_at_utc` controls executability.

## Capture-latency and H022-X001 guard

The already-frozen H022-X001 nominal entry is the first NSE session open strictly after the official publication timestamp.

A prospective P001 signal is primary-outcome executable at that nominal entry only when:

```text
signal_frozen_at_utc <= nominal_entry_open_utc
```

Otherwise its execution status is:

`LATE_SIGNAL_FREEZE`

A late signal may remain in source/coverage diagnostics, but a future primary prospective evaluator must not backdate it to the missed open and must not silently shift its primary entry to a later session. Any alternative delayed-entry diagnostic must be separately reported as secondary.

This rule prevents a post-open or after-close acquisition run from receiving a price interval that was not actually available to the research process.

## Append-only source and signal state

For each prospectively eligible transcript:

- official discovery identity is immutable;
- raw PDF and extracted text are content-addressed evidence;
- H003-E002 extraction record is immutable;
- P001 signal record is immutable;
- duplicate identical processing is idempotent;
- changed bytes for an existing source or signal identity are a conflict, not an update.

Raw NSE PDFs and large discovery payloads may remain in workflow artifact/content-addressed storage rather than the Git repository. Repository evidence must retain sufficient hashes and record identities to prove exactly which bytes produced each signal.

## Failure policy

Fail closed on:

- incomplete U001 catch-up discovery;
- missing catch-up extraction;
- non-`TEXT_READY` catch-up extraction;
- source-identity/hash mismatch;
- historical baseline digest mismatch;
- static-prior omission;
- context artifact digest mismatch;
- future-context leakage;
- prospective source outside U001;
- source publication before the prospective boundary;
- prohibited outcome input.

A source failure can reduce prospective coverage after the initial context gate, but it cannot be replaced by another company, another document class, a transcript mirror, or a manually reconstructed signal.

## Scientific boundary

This acquisition contract is frozen without inspecting any H022-P001 future return. It does not assert that management-information delta contains alpha. It exists only to make the future test causally and operationally valid.
