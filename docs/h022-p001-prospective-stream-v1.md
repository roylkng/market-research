# H022-P001 prospective stream contract v1

## Status

`FROZEN_BEFORE_FIRST_PROSPECTIVE_SOURCE`

Frozen: 2026-09-14

Prospective source boundary: `2026-09-14T18:30:00Z` = `2026-09-15 00:00 IST`

Live capital: **DISABLED**

Outcome inputs: **FORBIDDEN**

## Purpose

This contract defines the append-only source, extraction, scan, and signal state used after the H022-P001 mandatory pre-start context has been sealed. It does not alter the frozen H022 management-information signal, U001 cohort, H003 source rule, H003-E002 extraction rule, historical baseline, or H022-X001 outcome rule.

The central requirement is complete management-information chronology. A later transcript must never be compared against an older prior merely because an intervening official source was missed or failed extraction.

## Discovery surface

Each prospective pass queries official NSE corporate announcements for every company in the frozen U001 cohort over the full prospective date interval from 2026-09-15 through the pass cutoff.

A canonical scan can advance repository state only when all 100 U001 discovery requests are complete. A failed request is `INCOMPLETE`, not zero coverage. A partial scan may be retained in workflow evidence but cannot advance source, extraction, or signal ledgers.

Each successful scan seals a full-U001 manifest containing:

- exact scan cutoff and completion timestamp;
- per-company raw NSE discovery-response SHA-256;
- all qualifying H003-C001 source identities visible by the cutoff;
- complete/incomplete coverage state;
- full source-ID set;
- frozen cohort and source-rule identity;
- `outcome_data_attached=false`;
- `live_capital_allowed=false`.

The entire prospective window is replayed on every pass. This makes scheduler misses recoverable and makes late NSE source appearance detectable.

## Immutable source ledger

Every newly discovered qualifying H003-C001 source is appended once with:

- frozen NSE symbol;
- NSE sequence identity;
- official publication timestamp;
- approved NSE attachment URL;
- H003 discovery-row SHA-256;
- H003 source ID;
- actual first-seen timestamp in the research process.

Identical rediscovery is idempotent.

The same symbol/sequence identity reappearing under a different H003 source ID is source-identity drift and fails closed. Existing source-ledger bytes are never rewritten.

## E002 ledger and unresolved sources

The prospective E002 ledger accepts only valid `TEXT_READY` H003-E002 records whose source disposition is `PROSPECTIVE_SIGNAL_ELIGIBLE`.

A discovered source without a `TEXT_READY` E002 record remains an explicit unresolved source. Raw acquisition/extraction attempts are retained in workflow evidence and may be retried on later passes.

An unresolved source is not silently discarded and is not converted into a neutral management-information observation.

## Chronology gap rule

Before sealing a signal for a current source, the stream checks all discovered same-symbol sources with official publication timestamps strictly earlier than the current source.

If any such source is unresolved, the current signal is blocked with:

`UNRESOLVED_EARLIER_SOURCE`

The later source may remain as a valid E002 record, but no P001 signal is sealed until the earlier source becomes `TEXT_READY`.

Equal-publication-timestamp peers do not block one another as earlier sources. This preserves the already-frozen H022 timestamp-group rule. If multiple equal-timestamp sources become valid E002 records, they form the ambiguity group for the next strictly later source.

## Prospective context construction

For each signal-ready current E002 record, context consists only of:

1. the exact static pre-start prior record group bound by the frozen P001 prior index; and
2. all validated prospective E002 records for the same symbol with publication timestamps no later than the current record, excluding the current source itself.

The pure frozen P001 signal sealer then applies its existing latest-strictly-earlier timestamp-group rule.

The caller may not omit the frozen static prior. The operational sealer verifies its exact source and E002 record IDs.

## Retroactive source-gap rule

A later full-window scan can expose an NSE source that was not visible on earlier complete scans but carries an official publication timestamp earlier than an already sealed same-symbol P001 signal.

That event is:

`RETROACTIVE_SOURCE_GAP`

It is a prospective integrity break. The scanner must fail before canonical state is advanced. It must not insert the backfilled source and silently recompute or rewrite already sealed signals.

The raw discovery evidence remains available for investigation. Any treatment of affected signals requires an explicit protocol decision made without using their return outcomes.

## Scan cadence and actual availability

The production workflow targets at least:

- 08:30 IST pre-open pass;
- 09:05 IST pre-open pass;
- 18:15 IST after-close pass;

on weekdays.

These cron targets are collection attempts, not claims of availability. GitHub Actions can start late. Every P001 signal retains its actual `signal_frozen_at_utc`.

The separately frozen H022-P001 acquisition contract controls H022-X001 executability:

```text
signal_frozen_at_utc <= nominal_entry_open_utc
```

Otherwise the future primary evaluator must classify the observation as `LATE_SIGNAL_FREEZE`. It may not backdate the signal or silently move the primary entry.

## Append-only state

The canonical prospective state contains three distinct ledgers:

1. source ledger, proving what qualifying official NSE sources have been discovered;
2. E002 ledger, proving which sources yielded immutable deterministic transcript extractions;
3. existing P001 signal ledger, proving which E002 observations were sealed into the frozen signal.

A signal source must exist in both the source and E002 ledgers. An E002 source must exist in the source ledger. All three ledgers are canonically sorted, hashed, idempotent for identical replay, and conflict on changed immutable bytes.

Successful scan manifests are stored separately by their SHA-256, including scans with zero new sources. This preserves evidence of negative discovery.

## Repository and raw evidence boundary

The Git repository may retain:

- canonical source ledger;
- canonical E002 ledger;
- canonical signal ledger;
- successful scan manifests and scan summaries;
- mandatory context artifacts.

Large raw NSE discovery payloads, PDFs, extracted text, and per-attempt debugging evidence remain content-addressed in the workflow artifact bundle rather than being copied into Git.

## Main-branch race guard

A scan starts against one exact `main` commit. Before it anchors observations, it fetches current `origin/main`. If `main` moved during acquisition, the scan refuses to write. A later full-window pass can safely replay discovery against the new reviewed rules.

## Scientific firewall

The source stream may not consume or derive from:

- stock prices;
- market or benchmark returns;
- future H022 outcomes;
- valuation;
- broker targets;
- H021 revisions;
- H013 momentum;
- H019 quality;
- H020 timing;
- post-publication news used to reinterpret a transcript;
- later management calls used when sealing an earlier signal.

No stream failure policy, parser tolerance, discovery rule, or signal rule may be changed using future P001 return performance.
