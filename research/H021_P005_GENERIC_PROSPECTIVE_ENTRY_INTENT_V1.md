# H021-P005 Automatic Prospective Entry Intent, v1

Status: **FROZEN BEFORE THE SECOND VALID H021 MONTHLY REVISION COHORT**.
Established: 2026-10-10 IST. No live capital, paper portfolio entitlement, or return outcomes.

## Problem fixed

H021's existing weekly source process already sealed the immutable company-consensus captures and 28-to-35-day EPS revision comparison. However, it did not automatically freeze the next-open research-observation cohort for each new comparison. The initial H021-P003 intent covered only the 2026-10-09 cohort.

Without this step, researchers could retrospectively choose an entry date, ignore coverage failures or silently change a selected symbol after a subsequent price movement. P005 is a **workflow/data-integrity change**, not a return-predictive hypothesis.

## Scope and authority

P005 runs in .github/workflows/h021-weekly-consensus-capture.yml after the frozen comparison is generated and before the same capture is committed.

Inputs:
- newly sealed H021 source-capture manifest v2
- newly sealed primary revision comparison
- unchanged official 100-member U001 universe
- previously frozen NSE-CM session calendar
- source-byte SHA-256 of both the comparison and capture manifest
- UTC time of actual intent preparation

It preserves the existing H021 signal, eligible analyst threshold (5 at both captures), 28-to-35-day window, top-decile tie rule, prior/current EPS semantics and primary 60-session / secondary 20-session outcomes.

No new filter, score, date-selection rule, fundamental overlay, portfolio eligibility or trading allocation is added. Already excluded companies remain excluded even when the comparison contains a numerical EPS change.

## Chronology that must be satisfied

The original NSE session must close before the source capture. The source capture must complete before intent preparation. The intent must be prepared **before the next completed NSE session's official open**.

A second independent gate in the commit-and-push step checks that the newly created pre-entry intent is still early at the actual push attempt. A delayed GitHub job is a failed or nonprospective cohort, not a way to backdate a signal.

P005 never supersedes H021-P003's 2026-10-09 intent. It starts with later comparison dates, uses unique per-cohort file names in research/prospective/h021/intents and refuses overwrites.

## Repeatability and provenance

Python module: src/marketlab/h021_future_intent.py
CLI: scripts/materialize_h021_future_intent.py
Tests: tests/test_h021_future_intent.py

For each new capture, the CLI requires:
- the H021 comparison path for that exact date
- the same-date original capture manifest
- official calendar and frozen U001 file whose Git blob identities are checked
- a unique, nonexistent output file tied to the exact capture date

Each resulting intent includes the original selected symbol/ISIN, EPS revision, source hashes, source/decision timestamps and next-session open. Price, weight and trade fields remain null or false.

The recorded JSON digest and Git publication timestamp establish an auditable intention, not executed pricing.

## 2027 calendar and unknown future outcomes

The fixed 2026 calendar ends 2026-12-31, so P005 **fails closed** if no future verified NSE session exists. The system may not invent a 2027 holiday list or force a last-known close.

H021's primary 60-session outcomes, benchmark basis, dividend and corporate-action treatment, execution liquidity and market costs remain separately unresolved. P005 does not assign expected returns or improve existing alpha statistical significance.

Validation:

    pytest -q tests/test_h021_future_intent.py

A future cohort may be called prospectively frozen only when the actual Git commit, not just the local JSON, is published before the next NSE open.
