# H021-P007: source-bound EPS ratio sign semantics audit

Status: **OUTCOME-BLIND DIAGNOSTIC AFTER FIRST EPS SIGNAL** (10 October 2026 IST).
The original September/October H021 primary cohort, ten selected identities and
the next-open intention remain immutable. Live capital disabled.

## Mathematically material problem

H021-R001 uses:

    ratio_revision_pct = 100 * (EPS_current / EPS_prior - 1)

This equals:

    100 * (EPS_current - EPS_prior) / EPS_prior

When EPS_prior is NEGATIVE, this ratio has the **opposite sign** from the
absolute signed improvement EPS_current - EPS_prior. It is not a matter of
opinion, model quality, future returns or individual analyst composition.

For example, when expected EPS improves from -2 to -1, H021's ratio is
-50 percent although the projected loss narrows. When EPS worsens from -2
to -3, the ratio is +50 percent although the projected loss widens.

Any investment statement labeling all H021 positive ratios as earnings
upward revisions is therefore wrong if some eligible denominator EPS values
were negative. The exact source-dependent prevalence must be measured.

## What this diagnostic does

- Loads the exact already sealed 11 September baseline and 9 October
  primary capture, through the repository's original gzip-manifest validation
  and legacy-v1 adapter. No alternative provider, later quotes or stock prices
  are involved.
- Reconciles all 100 original symbol rows and 97 primary-covered rows
  against the frozen 28-day H021 comparison, EPS currencies, fiscal periods
  and source analyst counts.
- Recomputes every primary percentage algebraically and rejects any source
  disagreement, incompatible fiscal period/currency, or altered selection.
- Classifies each originally covered company as positive or negative prior EPS,
  signed EPS change and direction inversion, plus whether it was in the
  original H021 top decile.
- Retains original source SHA-256 hashes and 100/97/10 frozen identities.
- Leaves all original ratio ranks, original top ten, prospective entry intents,
  return outcomes, portfolio decisions and live-capital state unchanged.

The diagnostic is **post-signal and outcome-blind**. It cannot be promoted
to a new tested alpha, and no failed or successful H021 position may be
retroactively removed because the underlying EPS had a negative denominator.

## Reproduction

    python scripts/audit_h021_eps_sign.py --out /tmp/h021-eps-sign-audit.json
    pytest -q tests/test_h021_eps_sign_audit.py

The CI workflow runs the actual exact-source diagnostic and prints the
negative denominator and direction-inversion counts. The saved JSON contains
the evidence-bound individual cases and original capture provenance.

## Constructive next experiment

A future, separately registered H021-v2 challenger can test a direction-
preserving metric such as:

    signed_change_pct = 100 * (EPS_current - EPS_prior) / abs(EPS_prior)

But this ratio becomes unstable as prior EPS approaches zero and should not
be deployed without a prospectively frozen denominator floor or scale. A
different price-scaled EPS-change measure could be preferable, but neither
measure is validated here and neither may replace the frozen H021-v1 test.

The best causal interpretation also requires analyst contributor-level
identifiers, because a change in the vendor's analyst population can move
consensus EPS without any individual analyst revising an estimate.

## Governance

This audit has **zero** return observations, zero target prices, zero
recommendations and zero change to 20/60-session evaluation. The prospective
H021-v1 study must retain its original top decile and report its economic
direction caveat as a source-measurement limitation.

No capital allocation is authorized by H021-P007.
