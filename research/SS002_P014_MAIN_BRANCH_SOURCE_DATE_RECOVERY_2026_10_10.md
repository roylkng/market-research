# SS002-P014: Main-Branch Source Window Recovery Correction

Date: 10 October 2026 IST. Source-data integrity correction only.

## Exact problem

The new P013 on-merge source workflow run 38058974470 completed CI
successfully yet its source step printed:

    P001 ALREADY_CAPTURED: no missing completed source days

The actual 9 October canonical NSE corporate-announcement source did
NOT exist and the previous 10 October source acquisition failed on
an official NSE read timeout. The post-merge workflow had silently
restricted all push-triggered runs to the feature-branch bootstrap
window 5–8 October:

    if RUN_EVENT == push:
        --start-date 2026-10-05 --end-date 2026-10-08

Both existing canonical 5–8 October source packets were legitimately
already captured, hence the erroneous "already captured" output.
That status **did not certify source coverage through October 9**.

## Change

Only the original, explicitly named experimental feature branch keeps
the October 5–8 historical bootstrap constraint.

Normal **main push** and scheduled runs now use the same oldest
missing completed NSE source-day resolver without any hard-coded end
date. Manual workflow dispatch retains the date-scoped override for
original source recovery.

A static regression ensures the branch-specific gate cannot be
accidentally restored for all pushes.

All source-data and statistical boundaries from P001/P013 are unchanged:
- original NSE source acquisition required;
- missing Oct 9 stays missing until original bytes arrive;
- official timeout receipts do not become zero announcements;
- immutable earlier 5–8 source packets are preserved;
- no new company results, returns or live capital authorized.

This correction triggers another main-branch capture attempt on merge.
It can produce a valid source packet OR a verifiable source-failure
receipt. Neither outcome may be guessed ahead of the run.
