# H022 document-comparability audit v2 hardening

October 16, 2026. This note extends the noncanonical audit in
`h022-document-comparability-audit.md`. It does **not** change the frozen P001
signal, source rule, collector, feature extractor, or outcome evaluator.

## Review findings fixed

The first audit correctly identified MARICO's future-call notice, but review found
two integrity gaps before merge:

1. a malicious or accidental caller could re-seal both JSON ledgers under a
   different cohort/rule identity and still satisfy the v1 local hashes;
2. the audit ignored the already-frozen E002 extraction ledger, so extraction
   status, parser identity, raw/text digests, and signal-to-extraction bindings
   were not part of its evidence chain.

The v2 wrapper closes those gaps while preserving v1 as historical audit logic.

## Exact frozen scope now required

The audit refuses drift in the P001 protocol, H022 hypothesis, cohort ID/hash,
H003-C001 rule ID/hash, prospective start, management-forward-information feature
version, H003-E002 rule ID/hash, parser version, or pinned pypdf version.

For every sealed signal it requires exactly one current source and exactly one E002
record. Symbol, publication timestamp, attachment URL, E002 record ID, raw SHA-256,
and text SHA-256 must agree across the frozen records. The current inventories must
match exactly. A sealed signal depending on a non-TEXT_READY extraction is rejected
as an internally inconsistent snapshot rather than interpreted as a zero.

E002 metadata is included in each annotation. Page count and text length remain
**diagnostics only**. They cannot promote a document to FULL_TRANSCRIPT.

## Snapshot commit is no longer merely caller-asserted in the CLI

The v2 command authenticates the local checkout:

- `git rev-parse HEAD` must equal `--snapshot-commit`;
- the Git blob ID of each of the three live input files must equal
  `HEAD:<path>`;
- the bytes read by the audit must hash to those same blob IDs;
- the bytes are checked again immediately before the append-only audit is written.

`--no-git-verify` exists only for isolated fixtures/library use and is explicitly
not the repository-audit path. The generated report records whether Git binding was
verified.

This verifies the local Git snapshot. It does not cryptographically attest a
remote GitHub identity or signed commit.

## E002 evidence in the pinned snapshot

The fixed snapshot has four E002 TEXT_READY records. Their metadata are now bound
to the four signals. This improves provenance but does not establish full-document
comparability because the extracted text bodies are not committed in this audit
scope.

Notable diagnostics remain:

- COFORGE: one extracted page, 1,253 characters;
- SOLARINDS: fourteen pages, 38,164 characters;
- TCS: twenty-nine pages, 51,214 characters;
- MARICO: three pages, 4,082 characters.

These numbers are never classification thresholds. MARICO stays NOT_COMPARABLE
because the retained announcement itself schedules a future call and says the
transcript will be published subsequently. COFORGE, SOLARINDS, and TCS stay
REVIEW_REQUIRED until exact retained text/document evidence is reviewed.

## Audit chaining

A v2 audit can chain only to another v2 audit with the same protocol, cohort, and
frozen scope identity. The existing v1 audit remains preserved as historical
evidence but is not silently treated as a v2 predecessor.

## Tests added

The v2 tests cover re-sealed cohort/rule/feature drift, E002 rule drift,
signal-to-E002 raw/text mismatches, extra extraction records, v1/v2 audit-chain
boundaries, Git checkout mismatch, working-file/blob mismatch, and the retained
MARICO/COFORGE E002 diagnostics.

The full repository test suite still needs to be executed in a complete checkout.
Until then, treat these additions as review hardening with focused tests supplied,
not as whole-repository validation.


## Investment-research interpretation before merge

This is a **document-source integrity audit**, not a new management execution-credibility alpha result. A TEXT_READY extraction may contain only a few pages, and no full-conference-call comparability follows from raw/text hash agreement. COFORGE, SOLARINDS and TCS require actual retained document content review; MARICO remains non-comparable while its transcript is not available.

Auditing older frozen H022 source and E002 records is valid source-custody work, but cannot retroactively create a pre-publication trading signal or rescue unavailable future transcripts. Any future credibility weighting must be frozen separately before first eligible portfolio decision and evaluated against original prospective outcomes.

This original-source audit is reviewed for whole-repository integration before merge, rather than assuming fixture-only tests are sufficient.
