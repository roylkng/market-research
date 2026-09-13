# H022 expanded historical transcript source corpus v1

Status: **FREEZE_READY**

Live capital: **DISABLED**

## Purpose

Stress-test H022's original current-U001 survivor panel by rebuilding official management-call source coverage over the reconstructed point-in-time Nifty 200 historical union.

This is a source/data-quality gate only. It contains no prices or return outcomes.

## Historical universe

- universe rule: `H022-UH001`
- reconstruction SHA-256: `dee26ffc683781202da21e789cc45f480d625772e8510f3beb1f65aa4a6ba144`
- union companies: **211**
- current U001 companies included: **100/100**
- additional companies versus current U001: **111**
- ad-hoc base-membership audit: `COMPLETE_NO_ADDITIONAL_PERMANENT_BASE_CHANGES`

## Source rule

`H022-US001` in `registry/h022_expanded_transcript_source_rule_v1.yaml`.

The transcript classifier is not redesigned for H022. It directly reuses the frozen H003-C001 selection semantics implemented by `marketlab.h003_sources.select_transcript_sources`.

Source window:

- begins 1-Sep-2024;
- exact cutoff `2026-09-06T12:21:06.431463Z`;
- source of record: symbol-scoped NSE Corporate Announcements plus original NSE archive attachment identity;
- exact discovery response bytes retained content-addressed.

Membership semantics:

- calls before 1-Oct-2025 are `PRE_CHALLENGE_CONTEXT` and can only supply prior-call information;
- challenge-period calls are `SIGNAL_ELIGIBLE` only when the company was a reconstructed Nifty 200 base member on its Asia/Kolkata publication date;
- challenge-period calls outside the index remain `CONTEXT_ONLY_NONMEMBER` and may still serve as publicly available prior context;
- temporary demerger dummies are excluded from the company universe.

## Measured coverage

The one-shot official-NSE sweep completed all **211** union members.

- `COMPLETE`: **198**
- `COMPLETE_ZERO_SOURCE`: **13**
- `INCOMPLETE`: **0**
- `freeze_ready`: **true**
- official qualifying transcript sources: **1,558**
- challenge signal-eligible transcript sources: **754**
- context-only transcript sources: **804**
- discovery artifacts retained: **211/211**

Zero-source symbols are retained rather than substituted:

`BAJAJHLDNG, BDL, BHEL, GODFRYPHLP, IREDA, ITC, ITCHOTELS, MCX, MRF, NTPCGREEN, OFSS, TATAINVEST, TRENT`

Frozen bundle SHA-256:

`85d30df9286712c362102865c22ec3a27907e85599bd70d0c053bc95554cb34c`

H022-US001 rule-file SHA-256:

`3e22fc99c90c11d5477fb81b5fe4d0f4cdf325ea2ae42817f9fc7b2c582403ab`

Exact discovery-byte artifact:

- workflow run: `34774636608`
- artifact id: `10323670057`
- artifact digest: `sha256:fda58881c3dc2730fc2875324678585e62b8358ac5afe5310beac1234fa76031`

## Next gate

The source corpus is complete enough to proceed.

Next, the 1,558 transcript PDFs must be processed with the **same H003-E002 parser and candidate semantics**:

- `pypdf 6.17.0`, `strict=False`;
- no OCR;
- same future-marker/deadline/domain/quantitative filters;
- every source must be accounted for;
- any `NO_TEXT`, `PARSE_ERROR` or unresolved fetch failure blocks candidate-corpus freeze;
- membership status from H022-US001 must be carried forward unchanged;
- candidate and H022 feature panels must freeze before expanded returns are reopened.

No H022-R001 signal threshold or formula changes because this expanded corpus exists.
