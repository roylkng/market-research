# RM001-v3 P001 Protocol Amendment P1: Named-Covariance Isolation Gate

Frozen: 2026-10-02
Status: FROZEN BEFORE FIRST RM001-v3 STATE CONSTRUCTION
Live capital: DISABLED

## Trigger

RM001-v3 model amendment P1 changed the challenger risk-estimation clock to
match RM001-v2:

- 60-session factor covariance;
- 60-session idiosyncratic variance.

Before the first real RM001-v3 state was built, review identified an additional
treatment-isolation invariant.

## Frozen gate

Because the first six factor-return histories are inherited unchanged from
RM001-v2 and are measured over the identical latest 60 realized sessions, the
upper-left 6x6 named-factor covariance block in RM001-v3 must reproduce the
RM001-v2 covariance matrix.

Frozen absolute tolerance:

    5e-15

P001 also requires exact equality of:

- factor_covariance_first_realized_session;
- factor_covariance_last_realized_session;
- factor_covariance_window = 60.

Any larger named-covariance drift fails closed.

## Purpose

This ensures that the historical v2-v3 treatment difference is only:

    ADD FIVE STATISTICAL RESIDUAL FACTORS

and not a hidden change in the original named-factor risk estimates.

## Outcome boundary

No RM001-v3 real-data state or P001 attribution result existed when this
amendment was frozen.

No alpha or portfolio-return outcome is opened.

No live-capital implication.
