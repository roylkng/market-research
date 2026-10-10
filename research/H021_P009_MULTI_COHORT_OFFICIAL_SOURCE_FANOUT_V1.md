# H021-P009: Source fanout for all future P005 cohorts

Frozen before second valid H021 revision/entry: 10 October 2026 IST.
Status: **PROSPECTIVE SOURCE ROUTING ONLY, NO RETURN RESULTS, NO CAPITAL**.

## Why this fixes a critical research gap

H021's first October revision cohort is covered by P003, P004 and P008.
The weekly acquisition workflow now also creates a fresh independent P005
top-decile intention before each future market open. However, P008 alone
observes only the original ten names.

That architecture would not be capable of accumulating the **four distinct
monthly-equivalent, 60-session-matured prospective cohorts** required by the
frozen H021 hypothesis.

P009 uses P008's **one actual official whole-market daily NSE UDiFF ZIP**
and Nifty 500 index CSV as a common immutable source for every later P005
research cohort, with no second market-data vendor, redundant downloading
or future stock-selection changes.

## Precommitted input and evidence

For each P005 intent, the fanout verifies:

- immutable source packet SHA-256
- preregistered P005 rule identity and source dates
- frozen U001 and exchange calendar Git blob references
- selected symbols, exact ISINs, original EPS ranks and count
- preparation strictly before declared next NSE open
- entry date, primary 60 and secondary 20 completed-session horizons
- portfolio/live-capital and outcome/trade flags explicitly disabled.

For each day, it accepts only an existing sealed **P008 SOURCE_COMPLETE**
packet and verifies the original UDiFF and index bytes against the stored
SHA-256. The same raw ZIP may then expose additional valid EQ/ISIN symbols
not present among the initial ten P003 companies.

A newly selected company's missing/invalid official EQ row remains missing.
P009 does not borrow the first cohort's close, substitute Yahoo prices,
backfill from a later date or silently exclude incomplete companies.

Each independent cohort/day packet identifies its original dated P005
intent, shared P008 raw source hashes, status and full stock/index data.
It clearly distinguishes the first **entry-proxy source** date from subsequent
holding-path price observations, without claiming anyone executed a trade.

## Operations and source integrity

- Module: src/marketlab/h021_cohort_source.py
- CLI: scripts/fanout_h021_future_cohorts.py
- Workflow: .github/workflows/h021-future-cohort-fanout.yml
- Tests: tests/test_h021_cohort_source.py
- Output: research/prospective/h021/future-cohorts/source-packets/

The workflow runs when the P008 official-source workflow completes and
has a weekday catch-up schedule. It never needs another network source.

Outputs are per-cohort, per-completed-market-session, deterministic, SHA
sealed and immutable. Existing packets are compared byte-equivalently by
parsed fields before being skipped. Any source, selected identity or
scientific rule change while processing causes an anchor failure, never
a silent revised portfolio.

## What P009 does not prove

This is source collection, not independently validated alpha. The original
H021 EPS percentage score has known negative-denominator sign anomalies
(P007), which remain reported without rewriting previous cohorts.

The frozen NSE 2026 calendar leaves the 8 November Muhurat trading
session unresolved. A source-verified 2027 extension is also absent,
so neither the 20-session nor 60-session result can be inferred merely
from ordinary weekday counting.

Equity dividends, rights, splits, mergers, demergers, company identity,
price index versus TRI, transaction costs, actual execution/liquidity,
portfolio sizing and capital authorization also remain separate gates.

The system must wait for independently sourced outcomes and for the
existing H021 statistical promotion rules. A future cohort's unchanged
paper-intent is not itself evidence of profitable investing.

Validation is fully offline:

    pytest -q tests/test_h021_cohort_source.py
