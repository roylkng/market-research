# H021-P002 Analyst Panel Composition Diagnostic (10 October 2026)

Status: **DESCRIPTIVE, AFTER EPS-REVISION SIGNAL OBSERVED, BEFORE RETURN OUTCOMES**.
Live capital and portfolio eligibility: **DISABLED**.

## Why this exists

The first valid H021 28-day primary EPS-revision comparison was sealed for
2026-09-11 versus 2026-10-09. H021 uses consensus EPS and a minimum of five
analysts at both snapshots. This is a correctly frozen primary definition.

However, the *number of analysts* contributing to provider consensus can change.
A change in the consensus EPS can reflect revised estimates, a changing
contributor panel, vendor composition, or a combination. Count changes **alone**
cannot establish which explanation is correct. H021 does not provide stable
analyst-level panel identities, so it cannot separate those mechanisms.

This document records a falsifiable measurement-quality limitation. It is not
a new alpha, a post-hoc filter, or a license to remove inconvenient winners.

## Sealed inputs

- Primary comparison:
  research/prospective/h021/comparisons/2026-10-09-primary-revision-v1.json
- Prior capture: 2026-09-11; current capture: 2026-10-09.
- Source version, fiscal-period matching, EPS currency and analyst-coverage
  requirements remain under research/H021_COMPARISON_CONTRACT_V1.md.
- No stock prices, realized returns, benchmarks, or future holding-period
  labels are accessed by this diagnostic.
- Reproduce with:

    python -m marketlab.h021_composition \
      research/prospective/h021/comparisons/2026-10-09-primary-revision-v1.json \
      --output /tmp/h021-analyst-composition.json

The CLI includes SHA-256 of the exact comparison bytes. The output is a
side-channel diagnostic and cannot alter H021 or DR001 ranks/decisions.

## Observations

| Metric | Eligible 97-company panel | Frozen top-decile 10 |
| --- | ---: | ---: |
| Analyst count declined | 44 | 5 |
| Analyst count unchanged | 42 | 4 |
| Analyst count increased | 11 | 1 |
| Analyst count decline >=30% | 11 | 2 |
| Analyst count decline >=50% | 4 | 1 |

The 30% and 50% rows are **descriptive reporting buckets, not preregistered
trade filters, p-values, research gates, or claims of source failure**.

Material examples:

- DMART (primary top decile): 31 to 12 analysts, a 61.3% drop;
  reported 28-day EPS revision +5.92%.
- GAIL (primary top decile): 31 to 19, a 38.7% drop;
  reported EPS revision +0.88%.
- INFY (primary top decile): 42 to 48, a rise;
  reported EPS revision +1.16%.
- SIEMENS (not top decile): 21 to 6, a 71.4% drop;
  reported EPS revision -2.30%.

The exact change in analyst composition is **unknown**. Do not reclassify
any of these signals as false or genuine solely from count drift.

## Scientific consequence

The 97 primary eligible rows and 10 top-decile symbols **remain unchanged**.
The other three frozen names (ADANIENT, BOSCHLTD and TRENT) are excluded by
analyst-coverage rules. Their original comparison rows still contain raw
arithmetic EPS changes, including TRENT +3.02%. Those numbers do **not**
become eligible signals or enter top-decile ranks. A downstream consumer that
sorts every numeric EPS change without checking primary_signal_available
would violate the frozen H021 experiment.
In particular the five DR001 Tier-A companies do not become eligible by
discretionary exception.

H021 first needs realized forward return evidence under its frozen holding
period and cost/benchmark terms. Even statistically strong returns would not
establish that the EPS change arose from same-analyst estimate revisions,
rather than contributor composition. That question needs contributor-level
historical identifiers or a separately sourced, preregistered comparison.

**No new filter, EPS adjustment, return interpretation, portfolio allocation,
or investability claim is authorized by H021-P002.**

## Executable invariants

src/marketlab/h021_composition.py and
tests/test_h021_composition.py validate:

1. comparison identity, closed return outcomes and no live capital;
2. exact primary cohort membership is only copied, never recalculated;
3. eligible analyst counts remain valid and each frozen symbol is unique;
4. no ineligible symbol appears in the primary top decile;
5. first-cohort counts and DMART/GAIL composition examples reproduce from
   the immutable stored comparison, including CLI source-byte SHA-256.
