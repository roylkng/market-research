# RTA001-P002: Preregistered H021 EPS-Direction Multiplicity Family

Registered **13 October 2026**, before H021S001's first eligible
16 October comparison and before any complete 20/60-session
H021 outcome. This is research-governance metadata, **not** a
positive return result, stock recommendation, or a new alpha signal.

## Original and challenger linked explicitly

The global RTA001 trial registry now contains the fixed family:

    H021_DIRECTION_COMPARATORS_V1

It reserves exactly two currently pending original hypotheses:

- **H021:** original positive consensus EPS percent-ratio top decile.
  The 9 October first cohort was frozen before the 12 October
  market open; its 20/60-session forward outcomes remain immature.
- **H021S001:** separately preregistered signed EPS revision with
  fixed denominator floor of INR 1; earliest permissible first
  comparison 16 October, no future stock-price observation yet.

Both share the same original U001, analyst source, original
coverage/fiscal-period rules, entry clock, market liquidity,
benchmark and holding-horizon family. Their prospective outcomes
are statistically dependent and any apparently superior challenger
must be judged as a **paired**, multiple-research-trial comparison.

## Critical software fix

RTA001's existing adjustment functions intentionally reject empty
p-value arrays. That remains correct for direct BH/BY/Holm usage.

However, before either trial matures, the FDR family itself must
exist with zero completed outcomes. The original summary builder
raised an exception for such a preregistered family because it
called the direct adjustment functions with an empty list.

The patch changes only the family coordinator:

- **0 matured completed outcomes:** 2 registered, 0
  completed/adjusted, 2 pending, zero records, zero discoveries,
  zero q-values or p-values invented.
- **1 matured completed outcome:** record the interim adjusted
  result and explicitly show 1 pending family member. Never
  assert full family validation with the other result missing.
- **2 matured completed outcomes:** apply BH, BY, Holm and
  Bonferroni across both actual numeric endpoints. A dependent
  paired comparison and larger global discovery-trial accounting
  remain necessary before any alpha promotion.

No null p-value is silently replaced with 0, and no
historical success gets a free family exemption.

The explicit RTA001 accounting snapshot is dated 13 October
2026 to avoid misrepresenting the expanded contemporary trial
ledger as a full analysis fixed as of 4 October. The original
H021 source/experiment cutoffs are NOT changed.

## Reproduction

- src/marketlab/rta001.py
- tests/test_rta001.py
- research/rta001-trials-v1.json
- research/rta001-summary-v1.json
- scripts/validate_rta001_coverage.py

Run:

    python scripts/build_rta001_summary.py --repo-root .
    python scripts/validate_rta001_coverage.py --repo-root .
    pytest -q tests/test_rta001.py

The valid snapshot shows **68 explicit trials**, a pending-only
2-member H021 family, unchanged original AE001 discovery q-values,
**zero** H021/H021S001 matured stock-alpha outcomes, and
live-capital permissions disabled.

The family roster is preregistered before results. A future
analyst cannot retroactively cherry-pick a new denominator or
remove an unsuccessful member when its 60-session data mature.
