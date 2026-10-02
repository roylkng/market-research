# RM001 SC001 Operational Trigger Redundancy P1

Status: OPERATIONAL HARDENING
Applied: 2026-10-02
Scientific protocol changed: NO
Live capital: DISABLED

## Incident

The first RM001-SC001 observation date was 2026-10-02.

GitHub did not create any of the six scheduled RM001-SC001 workflow runs before
the frozen 08:30 IST cutoff. Therefore the 2026-10-01 target session has no
prospectively valid RM001-SC001 observation and must remain missing.

It must not be backfilled.

## Change

The frozen source, target-selection rule, 08:30 cutoff, parser, quality gates,
three-session promotion threshold, and actual post-fetch timestamp semantics are
unchanged.

Operational trigger redundancy is added:

1. the six original cron triggers remain unchanged;
2. RM001-SC001 also wakes when either of these independent workflows completes:
   - AE001 SC003 previous-session futures pre-open timing;
   - H024 prospective insider stream;
3. every trigger resolves the current India clock after install/verification;
4. if local time is after 08:30, the workflow records no source attempt;
5. only the timestamp generated after the Security File fetch can establish
   ready_before_preopen_cutoff.

A workflow_run trigger therefore creates another opportunity to execute the same
frozen observation. It cannot make a late source causal.

## Interpretation

- 2026-10-01 target: operationally missed, permanently non-ready.
- Future targets: eligible only under the original frozen scientific contract.
- No return or alpha outcomes are opened by this amendment.
