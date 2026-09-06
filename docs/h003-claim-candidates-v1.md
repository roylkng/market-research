# H003 deterministic claim-candidate extraction

## Objective

H003 needs management commitments that existed before the FY27-Q2 cohort decision, not retrospectively selected anecdotes. The frozen H003-C001 source bundle contains 794 official NSE management-call transcript attachments across the 100-company U001 cohort. H003-A turns that source corpus into reconstructable claim candidates while keeping every candidate unreviewed and non-scoring.

## Fixed source boundary

Candidate extraction consumes only:

`research/prospective/h003/FY27-Q2-2026-09-06/source-coverage-v1.json`

Frozen source bundle SHA-256:

`583af88b3c070e15fe94a7782962c9e1fb1ce167e1412a08fd5c7b2f2dcaf7ee`

The source cutoff remains `2026-09-06T12:21:06.431463Z`. Post-cutoff outcome evidence, prices and returns are forbidden inputs.

## PDF evidence contract

Original NSE PDF bytes are retained content-addressed by SHA-256. Text is extracted with exactly `pypdf 6.17.0`, parser version `h003_pdf_text_v1`, `strict=False` and no OCR. Page boundaries and non-empty normalized line order are preserved. Image-only documents are explicit `NO_TEXT`. Malformed documents are explicit `PARSE_ERROR`. Neither state is treated as a successful zero-candidate source.

## E001 pilot

The first frozen candidate rule, `H003-E001`, is preserved in `registry/h003_extraction_rule_v1.yaml` with SHA-256:

`db954a0737bf9b049130c899104008479e677460a21c98b6a54855188180def8`

A deterministic 30-source live sample produced:

- 30/30 `TEXT_READY`
- 920 raw candidates
- 24 companies with at least one candidate

The sample proved that standard PDF text extraction was viable but exposed a mechanical precision flaw. Symmetric context windows allowed a future marker on one line to combine with unrelated current-period numbers on neighboring lines, and produced overlapping duplicates.

No candidate had been accepted/rejected and no return or outcome data were used when this flaw was corrected.

## E002 canonical candidate rule

`H003-E002` supersedes E001 before candidate review. Canonical SHA-256:

`5aff200d6a2222a7cde972ad341bc43b927d9c5b6d26a58766893980515c24a2`

E002 requires:

- a first-person management future marker on the anchor line
- at most one following extracted line for PDF line-wrap recovery
- at least one operating or financial commitment-domain marker
- at least one quantitative token or explicit deadline marker
- no safe-harbor/operator/moderator boilerplate
- one deterministic candidate identity per source/page/normalized excerpt

Candidates remain `UNREVIEWED`. Candidate generation never creates a credibility score and cannot mark a commitment `MET`, `PARTIAL`, `MISSED` or `LATE`.

The identical deterministic 30-source sample under E002 produced:

- 30/30 `TEXT_READY`
- 93 candidates
- 23 companies with at least one candidate

That is an 89.9% reduction from E001 while retaining obvious concrete commitments such as Reliance's target to add roughly one million homes per month and Infosys's stated FY2026 constant-currency growth guidance.

E002 is intentionally not a perfect semantic reviewer. Question-speaker and weak-context false positives can remain. Those are handled by a separately versioned review layer so extraction provenance is not repeatedly changed to chase subjective precision.

## Full-corpus execution

The extraction runner is resumable per source. Each non-transient source result is written immediately to a hash-validated checkpoint under the extraction store. `FETCH_ERROR` is never trusted as terminal and is retried on resume. This prevents one long hosted run from losing hundreds of already-processed source decisions.

The full candidate corpus may be frozen only if all 794 sources are processed and every source is `TEXT_READY`. Any `NO_TEXT`, `PARSE_ERROR` or unresolved fetch failure remains an explicit blocker.

## Next gate

After the complete E002 candidate corpus is externally anchored, H003 review must separate management statements from analyst questions, classify measurable commitments, preserve explicit rejections, and only then resolve accepted claims using evidence available by each claim's resolution deadline. H003 remains paper-only and cannot use live capital.
