# H002 FY27-Q2 cohort preparation v1

## Goal

Turn the frozen 100-company U001 panel into an externally auditable set of pre-filing H002-R001 expectations before FY27-Q2 results arrive.

This stage does not select attractive stocks. It prepares every company under the same rule so later results cannot influence who was included.

## Baseline discovery

For the FY27-Q2 cohort, v1 searches NSE Integrated Filing - Financials for the consolidated filing with reporting period end `2025-09-30`. The exact discovery response bytes are hashed.

Candidate rows must match all of:

- type `Integrated Filing- Financials`,
- exact NSE symbol,
- consolidated basis,
- quarter end `2025-09-30`,
- non-empty original NSE archive URL,
- exchange broadcast timestamp.

If official revisions exist, the latest broadcast revision available before preparation is selected deterministically. Two different URLs at the same latest broadcast timestamp are treated as ambiguous and not guessed.

The selected original archive bytes are retained by `EventStore`, parsed with the existing integrated-filing parser, and independently checked again for symbol, period end and consolidated basis.

## Corporate-action factor

H002-R001 requires an explicit EPS comparability factor. Preparation queries NSE corporate actions from after the baseline quarter through the actual preparation date and hashes the exact response bytes.

V1 can mechanically resolve:

- bonus ratios such as `1:1`, and
- face-value split/subdivision/consolidation descriptions that explicitly state old and new face values.

Dividends are irrelevant to EPS share-count comparability and are ignored. Rights issues and any share-changing description that cannot be parsed exactly fail closed as `UNRESOLVED_CORPORATE_ACTION`.

The corporate-action version is derived only from the relevant share-changing actions and their ex-dates. With no relevant action, the factor is 1.0 but still receives a deterministic version.

## Coverage attempts

Every acquisition attempt is append-only and records a reason code. Technical failures and missing or ambiguous source evidence remain visible. A failed company is never silently removed from the denominator.

The preparation report contains the latest attempt for every U001 member and is `freeze_ready` only when all 100 companies have captured expectation records. This is intentionally stricter than the generic expectation-ledger manifest, which supports explicit uncovered symbols. For this first real cohort, we do not permit discretionary omissions.

## Frozen bundle

Once all 100 are captured, `freeze_complete_bundle` freezes the expectation manifest and exports a self-contained JSON bundle containing:

- frozen universe SHA,
- exact H002-R001 SHA,
- preparation report SHA,
- frozen expectation manifest,
- complete expectation capture records,
- per-company preparation attempts,
- discovery response hashes,
- selected baseline row hashes and archive URLs,
- original baseline source hashes,
- corporate-action response hashes, factors and versions.

The bundle itself has a canonical SHA-256. Committing it to the hosted repository before the first eligible FY27-Q2 filing provides a practical external timestamp anchor. Local timestamps alone are not treated as proof of prospectivity.

## Runner

```bash
python scripts/prepare_h002_cohort.py \
  --universe research/prospective/universes/FY27-Q2-2026-09-06.json \
  --baseline-period-end 2025-09-30 \
  --report-out research/prospective/preparation/FY27-Q2-2026-09-06-report.json
```

Re-running skips companies already captured and retries uncovered companies. Do not use `--freeze` until the report says `freeze_ready=true`.

When complete:

```bash
python scripts/prepare_h002_cohort.py \
  --universe research/prospective/universes/FY27-Q2-2026-09-06.json \
  --baseline-period-end 2025-09-30 \
  --report-out research/prospective/preparation/FY27-Q2-2026-09-06-report.json \
  --freeze \
  --bundle-out research/prospective/expectations/FY27-Q2-2026-09-06.json
```

No return observation, profitability result or live order is created by this workflow.
