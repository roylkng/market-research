# CC001 runtime: original documents to persistent research decisions

Status: implementation with explicit verification boundaries. Not an investment
recommendation service or validated prediction strategy. No live execution.

## Delivered path

```text
Manifest or locally retained original documents
  -> bounded original-byte acquisition
  -> content-addressed byte store + SQLite capture receipts
  -> HTML period/scope extraction OR explicit labels OR configured LLM proposals
  -> immutable extraction versions + manual semantic review
  -> company-state inbox + financial bridges + explicit decision conditions
  -> reviewed economic features
  -> independent extraction scoring and controlled A/B/C evaluation
```

Three new modules complete the integration around CC001 and its table adapter:

- `company_change_store`: persistent raw bytes, captures, extractions, attempts,
  reviews and research decisions. Repeated input is reused. Changed bytes or
  extractor recipes create new versions. An old acceptance does not approve a
  new revision. SQLite is for one research workspace, not a multi-tenant SaaS.
- `company_change_pipeline`: actual HTTP/local ingestion, bounded HTML span
  expansion with DOM-cell provenance, PDF text intake, a configured HTTP model
  adapter, a research inbox, review actions, feature export and decision records.
- `company_change_evaluation`: extraction precision/recall/abstention accounting,
  a chronological A/B/C comparison reusing `marketlab.alpha_model.fit_ridge`, and
  inference from a frozen numerical model without supplying future labels.

Existing H-series, HG009, AE001 code, registries, cohorts and schedules are not
modified. These modules consume existing capabilities read-only. The new smoke
workflow is PR/manual-triggered, not an ongoing market-monitoring schedule.

## Run original-document intake

```bash
python -m marketlab.company_change_pipeline \
  data/cc001/original-intake.json \
  --workspace .marketlab/cc001 --fetch --require-extracted 3
```

The supplied manifest names three public original NSE filings: Mayur Q1 FY27,
KRBL FY26 and CCL Q1 FY27. They are development/integration inputs, not a new
portfolio or a frozen prediction experiment. No forecast outcomes are read.

The command prints output paths and per-source outcomes. It writes original
response bytes under `blobs/<prefix>/<sha256>`, metadata to `evidence.sqlite3`,
and a content-addressed HTML/JSON inbox under `reports`. Source failures remain
visible and return nonzero status. A malformed document is retained for diagnosis
rather than replaced with a source-derived reconstruction.

An imported local file can be supplied through a `local_file` path relative to
the manifest directory. Its provenance is LOCAL_IMPORT_NOT_ATTESTED_ORIGINAL.
HTTP captures are marked HTTP_RESPONSE_BYTES. A byte hash proves the captured
content, not the issuer's authenticity or accuracy. Publication dates are not
inferred from filenames or backdated. Capture and extraction clocks are actual
runtime observations. Historical filings remain historical reconstruction.

The workspace persists across command executions. GitHub's smoke workspace is
intentionally ephemeral and exported as an artifact. It is not a production
persistent deployment. Use an existing workspace path for repeated local runs.

## Review and export

The ingestion output supplies an exact `extraction_id`. Review operates on that
immutable ID, not merely a company symbol. Its command-line options are
`--review`, `--reviewer`, `--verdict ACCEPT|REJECT`, and `--rationale`, along with
`--workspace`. These are local reviewer attestations, not authenticated approval.
Acceptance permits research feature export but never authorizes trades.

```bash
python -m marketlab.company_change_pipeline \
  --workspace .marketlab/cc001 --export-features
```

Unreviewed or rejected records are excluded. Exported values retain their
symbol, ISIN, scope, reporting period, raw-source hash and latest required
information clock. Outcomes are not attached. The intended join to existing
AE001 inputs must enforce the original identity and decision-time contracts.

`--decision-file` accepts an existing CC001 valuation specification. It locates
one active earnings record, checks semantic review, and records the resulting
research card immutably. Table-only reported EPS does not become normalized
owner EPS automatically. Missing owner normalization or dilution evidence
produces an explicit WAIT, not an invented estimate. Source-labelled complete
inputs can use the existing bear/base/bull computation. No card permits capital.

## Model adapter

The HTTP adapter implements the chat-completions structured-JSON contract and
is configured only through `CC001_MODEL_URL`, `CC001_MODEL_NAME`, and optional
`CC001_MODEL_API_KEY`. The URL is the complete endpoint ending in
`/chat/completions`. It can target a compatible self-hosted service such as vLLM.
Plain HTTP is allowed only for loopback when `CC001_ALLOW_LOCAL_MODEL=1` is set.
No credentials or provider selection are shipped. The repository tests use a
controlled transport, not a real model. There is no paid automatic retry.

Set a source's extractor to `llm` to opt in. Source text is untrusted data, not
instructions. The model has no tools. Responses must be complete and contain
allowed fields, exact uniquely occurring quotes, and literals present in those
quotes. The client derives offsets and reuses the existing numeric validation.
No source passage is created to match a model answer. Review remains mandatory.

PDF intake uses pypdf text extraction and explicit page markers. This is not a
vision/layout model or OCR system. Scanned/ambiguous/multi-column documents may
abstain. The current cited-literal interface requires explicit monetary units
in the selected literal. It does not infer monetary header context for arbitrary
PDF prose. Deterministic HTML tables have a separate context-aware adapter.
A configured provider must be tested on real documents before unattended use.

Reference protocol consulted during implementation:
https://docs.vllm.ai/en/latest/features/structured_outputs/

## Independent extraction scoring

The scorer takes a completed pipeline report and a separate gold-label JSON.
Gold labels are not available to the extractor. Each case identifies the exact
source ID, raw SHA-256 and period/scope selector. Each expected field supplies
value, unit and absolute tolerance, or null for expected absence.

```bash
python -m marketlab.company_change_evaluation extraction \
  completed-report.json independently-reviewed-labels.json \
  --out .marketlab/cc001-evaluation
```

The filenames above are the command interface, not shipped validation data.
Emissions without labels count as unexpected. Missing expected values count as
abstentions, not correct values. Missing documents stay in the recall denominator.
The report exposes precision, recall, coverage, wrong/unexpected values and
per-case details. It does not claim independent annotation merely because the
labels reside in a separate file. `independent_labelling_verified` stays false.

## Controlled predictor comparison

A = numerical baseline.
B = the same baseline plus sentiment.
C = the same baseline plus economic-event features.

The spec freezes disjoint feature groups, ridge penalty, minimum training size,
test folds and evaluation cutoff. All arms use identical test observations,
horizons and cost assumptions. Each feature and cost input has its own known-at
clock. Training labels must have fully matured and been observed before the
next test fold. Test targets are joined only after prediction, not passed to
`fit_ridge` or `predict_ridge` for the test examples.

```bash
python -m marketlab.company_change_evaluation abc \
  feature-and-label-dataset.json frozen-comparison-spec.json \
  --out .marketlab/cc001-abc
```

This is an executable interface, not a supplied investment dataset. Numerical
models and their hashes are retained in the result. `predict` mode accepts
unlabelled future feature rows and one frozen model artifact. It verifies the
model hash, artifact availability and per-feature decision-time availability.
No retraining or target column is required at inference.

MSE is reported. The highest-ranked name per date has a simple average
excess-return-minus-supplied-cost diagnostic. With overlapping holdings this is
NOT portfolio PnL, annual return or Sharpe. No significance, calibrated success
probability or validated alpha claim is produced. Model tests use synthetic
inputs. A real prospective experiment still needs independently sourced
point-in-time features, matured outcomes and its own frozen trial registration.
Modern LLM historical knowledge is an additional leakage risk that chronological
splitting alone does not remove.

## Operational boundaries

- No production server, paid feed subscription, vendor endpoint, broker or
  customer account is created by this change.
- Authorized internal source use is required. Usage flags are not licences and
  do not authorize commercial redistribution or sending restricted documents to
  an external model. No commercial service launch is claimed.
- The new acquisition workflow reads only explicit HTTPS allowed-host sources.
  Redirects are rechecked. Requests and documents are bounded. No document code
  is executed. Credentials are environment-only and are not stored in reports.
- Generated reports are internal research artifacts. Historical reconstruction,
  software correctness, extraction accuracy and investment edge remain distinct.

## Verification commands

```bash
pytest -q tests/test_company_change.py tests/test_company_change_tables.py \
  tests/test_company_change_runtime.py
ruff check src/marketlab/company_change*.py tests/test_company_change*.py
```

The normal repository CI exercises the existing ridge integration. The separate
`CC001 original-document smoke` workflow retrieves the actual original HTML,
preserves bytes and database state, and prints compact source-hash/fact evidence.
A failed network capture is a failed smoke run, not substituted sample data.
