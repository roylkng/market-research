# H024 Protocol Amendment P1: Sealed Observed-Session Immutability

Frozen: 2026-10-03
Status: FROZEN AFTER FAIL-CLOSED SOURCE-DRIFT DIAGNOSTIC AND BEFORE RESUMING OUTCOMES
Live capital: DISABLED

## Trigger

H024 outcome workflow run 37044398388 failed closed while rechecking the already
sealed 2026-09-16 Nifty 500 session:

`2026-09-16: H024 observed-session official evidence changed`

The canonical H024 session ledger had already sealed that completed market
session prospectively on 2026-09-16, including its exact source URL, raw SHA-256,
open, close, and observation timestamp.

The later NSE historical archive no longer reproduced those exact bytes.

No H024 return outcome was changed or opened by the failed run.

## Frozen evidence principle

The first valid prospective observation of a completed NSE session is immutable
H024 evidence.

A later mutation of an upstream historical archive must never:

- rewrite the sealed benchmark bar;
- replace the sealed raw hash;
- change the sealed observation timestamp;
- alter an entry or outcome already bound to that session;
- block future outcomes solely because the external archive no longer reproduces
  the old bytes.

This is the same point-in-time principle already frozen for H024 events and
revisions.

## Outcome-session discovery after P1

The rolling `session_recheck_days` window remains in place, but its purpose is
now explicitly:

> discover dates in the recent window that are still absent from the canonical
> H024 session ledger.

This preserves discovery of late-available or special NSE sessions.

Dates already present in the canonical session ledger are not re-fetched by the
outcome advancement job and are never submitted to `append_session` again.

The strict `append_session` immutability check remains unchanged. Any other
code path attempting to overwrite a sealed observed session still fails closed.

## Missing and special sessions

For a recent date absent from the session ledger:

- fetch official Nifty 500 session evidence;
- if no valid session exists, leave it absent;
- if a valid session is observed, append it prospectively;
- reviewed-calendar mismatch checks remain unchanged.

Thus P1 does not assume weekdays are sessions and does not hide special-session
evidence.

## Historical source drift

The failed run artifact remains retained evidence that the upstream 2026-09-16
archive changed after the prospective freeze.

P1 does not classify the later upstream bytes as more correct and does not
retroactively select between archive versions.

Any future source-drift research is diagnostic only and cannot rewrite the
canonical H024 session ledger.

## Scientific boundary

This amendment changes only how the outcome collector treats already sealed
source evidence.

It changes no:

- H024 event definition;
- entry session;
- entry price;
- horizon;
- benchmark definition;
- cost assumption;
- corporate-action rule;
- return formula;
- evidence threshold;
- live-capital policy.

Live capital remains disabled.
