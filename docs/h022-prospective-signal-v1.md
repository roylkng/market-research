# H022-P001 — prospective management-information-delta signal stream

## Status

`FROZEN_PROSPECTIVE`

Live capital: **DISABLED**

H022-P001 converts the historically promising but not yet validated H022 feature into an immutable prospective signal stream. Its job is to answer a narrower question than the historical diagnostics:

> When a future qualifying management-call transcript becomes public, can we compute and seal the H022 information delta using only information available at that instant, before any later return is observed?

P001 does not authorize portfolio use and cannot by itself upgrade H022 to validated alpha.

## Prospective boundary

The first eligible publication timestamp is:

```text
2026-09-14T18:30:00Z
= 2026-09-15 00:00:00 IST
```

The boundary is intentionally the next India calendar-day start after this protocol was designed. A source published before that timestamp can never be counted as a P001 prospective signal, even if discovered later.

## Frozen cohort

P001 uses the already-frozen U001 snapshot:

- cohort: `FY27-Q2-2026-09-06`
- file: `research/prospective/universes/FY27-Q2-2026-09-06.json`
- Git blob SHA: `8026e81faee3e913d2fba1dba72d60603b69fa07`
- captured: `2026-09-06T12:21:06.431463Z`
- members: 100
- universe rule: `U001-nifty200-top100-nonfinancial-ffmc-v2`

No discretionary names may be added or removed from this cohort after P001 outcomes begin.

P001 eligibility ends immediately before the capture timestamp of the next frozen U001 cohort. A successor cohort must receive a separate prospective ledger/protocol record. A source is never moved between cohorts after the fact.

## Historical prior context

H022 needs the latest strictly earlier call for the same company. The baseline through the historical cutoff is pinned to the completed expanded E002 corpus:

- cutoff: `2026-09-06T12:21:06.431463Z`
- report SHA: `45f58e5f0ee72c477ed042fd56be54b4b7c297b78532a011350a44d0a68da861`
- source-bundle SHA: `85d30df9286712c362102865c22ec3a27907e85599bd70d0c053bc95554cb34c`
- extraction rule: `H003-E002`

### Mandatory catch-up interval

There is a deliberate gap between that historical cutoff and the prospective start:

```text
(2026-09-06T12:21:06.431463Z,
 2026-09-14T18:30:00Z)
```

Every qualifying U001 transcript in this interval must be discovered and extracted before any P001 prospective signal is sealed.

Those calls are labelled:

`CONTEXT_ONLY_PRE_START`

They may become the previous-call context for a later prospective observation, but they can **never** contribute a prospective P001 outcome. This avoids the subtle error of comparing a Sep-15 call with a Sep-6 prior when an actual Sep-10 call existed.

## Source policy

Discovery reuses the already-audited H003-C001 semantics:

- official NSE corporate announcements;
- symbol-scoped discovery;
- exact NSE publication timestamp;
- original NSE transcript attachment;
- only qualifying earnings/results management-call transcripts;
- raw discovery response and attachment hashes retained;
- no analyst websites or transcript mirrors as source substitutes.

The document class may not be broadened after prospective returns start.

## Extraction policy

P001 reuses H003-E002 unchanged:

- rule SHA: `5aff200d6a2222a7cde972ad341bc43b927d9c5b6d26a58766893980515c24a2`
- parser: `pypdf 6.17.0`
- parser version: `h003_pdf_text_v1`
- OCR forbidden;
- current source must be `TEXT_READY`;
- extraction failure blocks that source instead of silently dropping it.

The feature therefore remains deterministic and auditable rather than becoming an LLM sentiment score.

## Signal formula

For each transcript:

```text
forward_commitment_density
  = H003-E002 candidate_count / text_char_count * 10,000
```

The P001 primary signal remains exactly the historical H022 signal:

```text
management_information_delta
  = current forward_commitment_density
    - latest strictly earlier same-symbol forward_commitment_density
```

Secondary frozen diagnostics remain:

- deadline-candidate density delta;
- operating-domain breadth density delta;
- explicit-deadline share delta;
- current forward-commitment density level.

No optimized composite is introduced.

## Prior-selection rule

For a current source, eligible prior context can come from:

1. the pinned historical baseline;
2. the pre-start catch-up ledger;
3. an earlier sealed P001 source.

For the same symbol, identify the **latest qualifying publication timestamp that is strictly earlier than the current timestamp**. That earlier timestamp group must contain exactly one source to be usable as prior.

This deliberately matches the frozen historical H022 grouping semantics:

- if there is no strictly earlier timestamp, seal `NO_SIGNAL_NO_PRIOR_TRANSCRIPT`;
- if the latest strictly earlier timestamp contains multiple qualifying sources, seal `NO_SIGNAL_AMBIGUOUS_PRIOR_TIMESTAMP`;
- if the latest strictly earlier timestamp contains exactly one source, use it as prior;
- multiple **current** qualifying transcripts sharing one timestamp may each use that same unique earlier prior;
- after such a multi-source timestamp has occurred, the next later transcript will see an ambiguous latest-prior group and therefore receive `NO_SIGNAL_AMBIGUOUS_PRIOR_TIMESTAMP`.

No ordering is invented between sources that share an NSE publication timestamp.

## Forbidden signal inputs

Signal generation may not use:

- stock prices or returns;
- benchmark returns;
- valuation;
- broker targets;
- H021 analyst revisions;
- H013 momentum;
- H019 quality/accounting state;
- H020 timing state;
- post-publication news;
- a later management call.

Those can only be evaluated downstream after the H022 signal has been sealed.

## Immutable signal ledger

Every prospective source produces one immutable ledger record containing at minimum:

- protocol and cohort IDs;
- source ID and symbol;
- exact exchange publication timestamp;
- E002 extraction record ID;
- raw/text hashes;
- prior source ID/timestamp when available;
- current/prior deterministic metrics;
- primary and secondary deltas;
- signal status;
- signal freeze timestamp;
- canonical SHA-256 of the record.

An existing source record may not be overwritten with different bytes. Corrections require an append-only provenance record and cannot replace the originally scored signal after outcome information exists.

## Future outcome semantics

When a separately frozen prospective evaluator is later opened, it must reuse H022-X001:

- entry at the first NSE session open strictly after publication;
- primary exit at holding session 60 close;
- secondary 20/120-session exits;
- official NIFTY 500 price-index benchmark over the same interval;
- 50 bps research friction stress;
- H022-X001 corporate-action handling.

P001 signal capture itself does **not** fetch or attach those returns.

## Prospective confirmation boundary

The historical `STRONG`, `PROMISING`, `REJECTED` and `INCONCLUSIVE` economic thresholds are already frozen. They will not be re-optimized for prospective data.

A future prospective evaluator may combine only protocol-compatible, prospectively sealed cohort ledgers and must be frozen before opening their outcomes. It may not issue a confirmation label until the pre-existing H022 primary coverage floor is met:

- at least 200 complete 60-session observations;
- at least 80% complete share of mature observations;
- an explicit company-breadth gate frozen before that evaluator opens outcomes.

P001 alone is expected primarily to create the first clean prospective wave, not to reach the full confirmation sample immediately.

## Portfolio boundary

H022-P001 is research evidence only. PF001 or any future live/paper portfolio may not consume H022 prospectively until a separate pre-outcome integration contract defines how H022 combines with quality, expectations, timing, valuation and risk.

## Next implementation gates

1. deterministic P001 signal-record builder with fail-closed validation;
2. mandatory Sep-6 to Sep-15 context catch-up;
3. official NSE post-start discovery/extraction workflow;
4. append-only prospective ledger;
5. only later, after signals mature, a separately frozen prospective outcome evaluator.
