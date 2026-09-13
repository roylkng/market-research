# H022 expanded E002 candidate corpus v1

Status: **FREEZE_READY**

Live capital: **DISABLED**

## Purpose

Apply the already-frozen H003-E002 deterministic future-commitment extraction unchanged to H022's reconstructed 211-company historical Nifty 200 union.

No price or return outcome is present in this corpus.

## Frozen inputs

- H022-US001 source bundle SHA-256: `85d30df9286712c362102865c22ec3a27907e85599bd70d0c053bc95554cb34c`
- transcript sources: **1,558**
- signal-eligible sources: **754**
- context-only sources: **804**
- H003-E002 rule SHA-256: `5aff200d6a2222a7cde972ad341bc43b927d9c5b6d26a58766893980515c24a2`
- parser: pypdf 6.17.0, strict=False, no OCR
- deterministic shards: **16**

Membership status is copied from H022-US001 as provenance and does not change candidate extraction.

## Measured extraction result

All **16/16** shard jobs completed successfully and the aggregate gate passed.

- processed sources: **1,558 / 1,558**
- source status: **1,558 TEXT_READY**
- `FETCH_ERROR`: **0**
- `PARSE_ERROR`: **0**
- `NO_TEXT`: **0**
- freeze blockers: **none**
- complete: **true**
- candidates: **5,090**
- signal-eligible candidates: **2,419**
- context-only candidates: **2,671**
- companies with >=1 candidate: **166**
- signal-eligible companies with >=1 candidate: **159**

Frozen candidate-report SHA-256:

`45f58e5f0ee72c477ed042fd56be54b4b7c297b78532a011350a44d0a68da861`

The compact aggregate evidence artifact is Actions artifact `10323860922`, digest:

`sha256:ac506a64f7c001cc7c24eef161806166dbc3387e42064f3db5cb4878db99b870`

Original PDF/text evidence is retained across 16 per-shard Actions artifacts from run `34775365468`; all 16 shard jobs and the aggregate job completed successfully.

## Comparison with original survivor-panel corpus

Original H022/H003-E002 survivor panel:

- 794 transcript sources
- 2,692 candidates

Expanded historical-union corpus:

- 1,558 transcript sources
- 5,090 candidates

The expanded corpus therefore materially increases both company breadth and transcript/candidate coverage without changing E002 semantics.

## Next gate

Build a new **outcome-free expanded H022-R001 feature panel** from this exact report.

Rules:

- the prior call is the latest strictly earlier same-company call among all 1,558 sources, including context-only calls;
- equal-timestamp calls cannot become each other's prior;
- first calls remain explicit no-signal observations;
- current challenge rows are evaluation-eligible only when `signal_eligible=true`;
- H022-R001 formula remains unchanged;
- feature panel must be hashed and frozen before any expanded stock/benchmark return is joined.
