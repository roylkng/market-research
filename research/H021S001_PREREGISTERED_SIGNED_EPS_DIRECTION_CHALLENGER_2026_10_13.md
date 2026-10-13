# H021S001: Preregistered Signed-EPS Direction Challenger (v1)

Registration date: **13 October 2026**, BEFORE the earliest permitted
comparison on **Friday 16 October 2026** and its planned next NSE open.
Registration mode: new independent alpha-mechanism discovery trial,
not a modification of incumbent H021, not a retrospective selection.

## Why this is worth testing

H021's original primary ratio is:

    100 * (EPS_current / EPS_prior - 1)

With prior EPS < 0 it reverses the direction of expected earnings.
The earlier, frozen and outcome-blind 9 October diagnostic H021-P007
verified three sign inversions across 97 H021-eligible companies,
including IDEA: its expected loss widened, yet the original ratio
reported a positive revision.

That diagnostic is NOT proof that an alternative factor predicts stock
returns; selecting a new formula based on the subsequent returns of
the first October cohort would be prohibited. The proposed replacement
does not rewrite the 9 October H021 selected names or outcomes.

## Independent signed score (immutable BEFORE 16 October)

    score_pct = 100 * (EPS_current - EPS_prior)
                / max(abs(EPS_prior), INR 1.00)

This is an *earnings-direction* signal, not a justified probability
of business success or investment alpha. It produces a positive score
when loss forecast improves from -2 to -1 and a negative score when
loss worsens from -2 to -3.

A fixed 1 INR denominator floor avoids unlimited relative scores when
the previous consensus EPS nears zero. It is a manually chosen
measurement-scale prior, **not calibrated to future returns**. It
can still rank different nominal EPS scales imperfectly; the floor
is never adjusted after observing performance.

## Cohort and eligibility contract

Reuse exactly the same frozen U001 100 nonfinancial companies, per-symbol
original ISIN, analyst EPS source family, 28-35 calendar-day time window,
**same fiscal period and ending date**, INR EPS currency and required
**minimum five analysts at both observations** as the original H021
primary comparison.

Ineligible H021 names remain ineligible, including names for which
the old H021 ratio contains raw arithmetic but coverage is invalid.
Prior EPS zero remains H021-ineligible, preserving comparator coverage.
Every originally eligible ratio must independently reproduce from
the two originally sealed, byte-hashed source snapshots.

The signed primary selection is the **top 10% of all originally
eligible symbols**, ceiling(0.10 * eligible_count), plus all ties
at the cutoff. No fundamental quality overlay, stock story,
momentum, sector filter, analyst-count weighting, ex-post removal
or side-dependent threshold may be introduced.

For comparability retain the incumbent H021 symbols and record
the two cohorts' overlap, but do not merge/change either selection.

## Prospective chronology

The first permitted cohort is **2026-10-16** (if the NSE calendar
confirms a completed trading session and actual source capture).

A fresh independent P005 H021 primary comparison is generated from
source snapshots after that completed session. H021S001 may then be
frozen and Git-anchored **strictly before** the following NSE market
session's official opening timestamp. If source acquisition or GitHub
runner is late, the challenger observation becomes nonprospective and
is NOT backdated, or deferred to a later price.

The 2026-10-09 original decision is never used as an H021S001
prospective trial. It may be used in offline mathematical negative
tests only to reject retroactive conversion.

The challenger is a distinct H021S001 research hypothesis and must
be added to the explicit RTA001 trial accounting, including its own
multiple-testing family. A positive standalone p-value for H021S001
cannot be shown as proven alpha without adjustment for the
preexisting research trials and the newly created challenger.

## Frozen outcome comparison

- Same intended next official NSE session open as the original H021
  cohort captured on the same Friday, no retroactive trade fills.
- Secondary 20 **completed official NSE sessions**.
- Primary 60 **completed official NSE sessions**.
- Primary cohort comparison: signed-EPS top decile's 60-session
  Nifty 500 benchmark excess against the same-day incumbent H021
  top decile, with identical market price/total-return and expense
  assumptions, as independently and prospectively specified.
- At least **four monthly-equivalent eligible prospective cohorts**
  with fully source-matured primary outcomes before trial promotion.
- Both mean and median benchmark excess positive; at least 55%
  name-level benchmark-beat rate; cost/slippage and source timing checks,
  placebo/base/universe controls; prior H021 and H021S001 multiple
  trials and universe membership correlations in the discovery
  multiplicity ledger. Results with violated rules or missing source
  data remain blocked, NOT scored as zero.

The original H021 and H021S001 signals may overlap substantially.
Their correlation and their incremental paired performance must be
reported, not interpreted as independent experiments.

Official 8 November 2026 Muhurat cash session and a verified
2027 exchange calendar are NOT currently source-complete.
The existing corporate-action/dividend/borrow and price-vs-TRI
basis gates remain mandatory. No automatic return evaluator is
authorized by this registration.

## Current state and authority

H021S001 code:
- src/marketlab/h021_signed_challenger.py
- scripts/freeze_h021_signed_challenger.py
- tests/test_h021_signed_challenger.py

Future-source workflow:
- .github/workflows/h021-signed-eps-challenger.yml

Re-run first-cohort negative controls offline:

    pytest -q tests/test_h021_signed_challenger.py

Only new immutable future entry research intent packets may be
committed under research/prospective/h021/signed-intents/.
No historical H021 selection, price outcome, portfolio eligibility,
live capital, return conclusion, beta fitting or 50% CAGR claim
is changed or authorized.
