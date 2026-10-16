# AE001 T012: SC003-triggered pre-open operational repair

**Registered operational amendment:** 2026-10-16, after the original Oct 15 to Oct 16 missed decision.

**Scientific protocol:** unchanged. This modifies scheduling only, never the prospective October 13 registration, model, features, original source eligibility, 08:30 IST cutoff, return target, corporate-action rules or T012 trial ledger.

## Original observed failure

The official SC001 October 15 cash/delivery source was captured at 2026-10-15T11:58:29Z, within the frozen 18:30 IST source deadline. The SC003 official October 15 F&O file was retrieved at 2026-10-15T19:22:55Z, before the next trading session October 16 03:00 UTC / 08:30 IST cutoff.

However GitHub scheduled T012 run 38851413775 did not execute until **2026-10-16T04:35:31Z**, well after the pre-open cutoff. It correctly reported **CUTOFF_MISSED**. The immutable T012 ledger still contains **zero** decisions. Workflow success means it skipped a late observation correctly, not that the research forecast succeeded.

**This missed October 15 prediction is unrecoverable**. Backdating it would invalidate the prospective evidence.

## Forward-only operational change

The T012 workflow now triggers on the **successful completion of the SC003 source workflow**, with path-filtered original source push and existing schedule/manual backstops. A source trigger is closer to the real event than GitHub schedule and increases the opportunity to score and anchor before the actual deadline. It cannot guarantee an execution time.

Before Python package installation or heavy original NSE market downloads, a **stdlib-only** operational preflight:

- Requires the latest future READY source target to link to an eligible same-session SC001 original market/delivery attempt.
- Uses the *original frozen NSE trading calendar* to identify the next actual session and 08:30 cutoff, never a guessed weekday.
- Requires the source target to be completed and not already in the immutable T012 decision ledger.
- Stops when less than 120 seconds remain for original result publication to GitHub main.
- Leaves missed deadlines permanently missed. No backdating, retroactive source repair or fake predictions.

A READY_FOR_AUTHORITATIVE_TRIAL_GATES preflight is **not** a scientific certification. It only permits invoking the existing frozen T012 source/model admission, historical input checks and post-computation re-seal.

## Residual failure risk

GitHub workflow_run itself may also be delayed, and download/scoring can be too slow even when the source is ready. Issue #426 remains **P0**, an independent time-synchronized source/score clock on a reliably available host, with actual pre-cutoff remote commit and append-only evidence.

The tests include the actual October 15 source being admissible before its original deadline, blocked after the delayed GitHub run, unlinked cash/futures, missing source, pre-close and duplicate attempts, and malformed frozen sessions. Tests never create real returns, live trading or investment recommendations.

All modifications first apply to October 16 and later feature sessions. The historical T012 October 15 run remains excluded permanently.
