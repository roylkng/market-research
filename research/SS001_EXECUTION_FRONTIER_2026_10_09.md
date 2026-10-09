# Small-Sum Alpha — Verified Execution Frontier (2026-10-09)

Status: **SOURCE INFRASTRUCTURE OPERATIONAL; NO VERIFIED INVESTMENT PREDICTIONS**

This note is a checkpoint for future continuation. It is not a forecast, recommendation,
portfolio approval, or claim that the investment objective has been achieved.

## Completed, source-verified research layers

| Layer | Verified result | Authority |
| --- | --- | --- |
| SS001-D001 NSE EQ census | 2,319 companies; 2,219 outside U001 | `research/ss001-d001-result-v1.json` |
| SS001-I001 liquidity context | all 2,319 searchable; liquidity context is not a hard exclusion | `research/ss001-i001-result-v1.json` |
| GF001-D002 current governance | 1,999/2,050 latest files CORE_READY; 1,976 adjacent-quarter pairs | `research/gf001-d002-result-v1.json` |
| SS002-D001-P2 transaction source | 1,666 current events across 540 symbols; 606 archival events retained | `research/ss002-d001-p2-result-v1.json` |
| SS002-D002 official corpus | 1,659 ready events, 1,539 unique content-addressed documents, zero fetch failures | `research/ss002-d002-result-v1.json` |
| SS002-D003 text | deterministic, page/segment-bound document text | `research/ss002-d003-result-v1.json` |
| FA001-D002 financial facts | full-market financial/asset fact source plane | `research/fa001-d002-result-v1.json` |
| HG006 historical work | historical event episode and stage evidence; not proven 50% CAGR | `research/hg006-s003-result-v1.json` |
| SS001-D007-L001-P2 full issuer queue | 1,240 frozen page requests, 12 issuers, 70 fresh documents | `research/ss001-d007-l001-p2-queue-result-v1.json` |
| R001 real-source preflight | all 1,240 verified, zero LLM calls | `research/SS001_D007_L001_R001_REAL_QUEUE_PREFLIGHT_2026_10_09.md` |
| SS001-D007-A002 sample | 229 source-selected pages, all 70 fresh documents and 12 issuers | `research/ss001-d007-a002-result-v1.json` |

## Latest A002 immutable evidence

- sample run: `37917815919`;
- artifact ID: `11610691741`;
- source queue SHA-256:
  `59929004bcc5a5eae4491cadc237aa1bb26b822102d56b5b50cf61fb6b667618`;
- sample SHA-256:
  `79e106f1d0b27810d06bd1c9e1bd192b967ef185393690ba0608354a698bbe86`;
- selected pages: **229 / 1,240**;
- document coverage: **70 / 70** fresh documents;
- issuer coverage: **12 / 12**;
- capital-language selected: 62 pages;
- multi-entity-language selected: 32 pages;
- model inference executed: **false**;
- independent semantic audit complete: **false**.

A002 samples *pages*. The last two language counts count selection reasons,
not independently verified economic transactions; a page may be selected by more than
one reason.

## Unresolved external/model execution dependency

The frozen full SS001 R001 model queue **has not been executed**.

To initiate an actual inference cohort, use:

`research/SS001_D007_R001_MANUAL_GITHUB_EXECUTION_RUNBOOK_V1.md`

Required configuration for a hosted GitHub run:

- `SS001_R001_MODEL_ID` repository variable;
- `SS001_R001_API_ENDPOINT` repository variable (authorized HTTPS endpoint);
- `MARKETLAB_LLM_API_KEY` GitHub Actions secret;
- explicit `infer` workflow dispatch, chosen shard and maximum request budget.

Alternatively, run the transport locally with a trusted OpenAI-compatible model server.

A ChatGPT subscription is not the provider API key. No provider, credentials, or
billable inference has been implicitly authorized or substituted. The prior native
GPT-5.6 Sol pilot remains a distinct model cohort.

## Next executable sequence

1. Begin with a **small explicitly authorized R001 infer shard**, not all 1,240
   requests or a newly selected sample. Retain original raw output and configuration SHA.
2. Continue the append-only receipts by `previous_run_id`, keeping provider/model
   cohort fixed, until the frozen queue is covered. Failed outputs require explicit
   separate retry decisions.
3. Construct the A002 independent semantic-review packet using
   `scripts/materialize_ss001_d007_a002.py --mode packet`
   from actual validated receipts. Review the 229 preselected pages against original
   NSE text; record unsupported facts, legal stage misreads and entity errors.
4. If semantic quality is inadequate, preserve failure and register a **new**
   extraction protocol/model cohort before retries. Do not silently edit the frozen
   original response.
5. Build the complete L002 issuer evidence ledger, reconcile share count and
   entity-specific share actions with separately reviewed primary source, and
   perform capitalization checks **only** for individually cleared companies.
6. Only then build scenario-specific opportunity underwriting, calibrated
   downside/closure probabilities, independent red-team review and paper portfolio
   trials with predefined outcomes and multiple-testing accounting.

## Hard scientific boundaries

- No absent corporate-action trigger proves unchanged issuer share count.
- A source document linked to an issuer may describe shares issued by **another**
  legal entity. Do not count those securities as the issuer's outstanding shares.
- Approved transaction is not completed transaction.
- An LLM's schema-valid cited statement is not semantically audited evidence.
- A historic stage frequency is not an unconditional current transaction probability.
- **No** 50% CAGR or reliable 50% annual-return capability has been established.
- Portfolio eligibility, market capitalization based on uncleared share counts,
  ADO/PF001 and live capital remain disabled wherever source/semantic gates are unmet.

## Separate near-term experimental event

The existing U001 H021 first comparable 28-day EPS-revision cohort is scheduled for
the 2026-10-09 post-close source cycle. Its already-frozen rules must not be
altered because of SS001 development or any eventual market outcome.
