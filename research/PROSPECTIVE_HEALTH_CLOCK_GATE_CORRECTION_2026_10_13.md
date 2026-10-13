# Prospective health: actual NSE clock versus SC001 source deadline

Status: **REALTIME MONITORING BUG FIX, NOT AN ALPHA/TRADING CHANGE**.
Prepared 13 October 2026 IST.

## Observed production bug

The workflow that refreshes
research/prospective/health/latest.json
passed the flag \`--after-market-close\` **unconditionally**, including
workflow-run-triggered execution before 09:15 IST and at 09:50 IST.

For example, the 13 October morning snapshot at approximately 08:42
IST encoded \`"after_market_close": true\`, expected the still-in-progress
13 October NSE cash session, and classified AE001 SC001 as \`STALE\`
although the latest eligible source was 12 October. This was a false,
premature operational alert.

There are two independent clock boundaries:

- Official NSE cash-market session closes at **15:30 IST**.
- The frozen AE001 SC001 source/decision evidence cutoff is **18:30 IST**
  on its target session, as implemented by
  marketlab.alpha_prospective_sources.decision_cutoff_utc.

The latter is **three hours after market close**. A daily source is not
overdue at 09:50 or even 16:00 simply because today is an NSE session.
The old fixed workflow flag was misleading on both sides of the boundary.

## Fixed chronology

The workflow passes **one actual UTC snapshot timestamp** from the
GitHub runner to the CLI. The CLI explicitly parses and converts that
timestamp to Asia/Kolkata. It derives:

- session as-of date in IST;
- whether actual cash-session close at 15:30 IST has passed;
- whether the SC001 18:30 IST evidence deadline has passed.

Only the third condition allows the current session to become the
expected-latest SC001 source. Before it, the latest *previous* completed
and due NSE source session is used.

The displayed \`after_market_close\` remains a truthful market-close
clock marker, and a separate \`sc001_source_cutoff_passed\` makes the
source deadline explicit.

On 13 October:

| IST | Actual market closed? | SC001 source due? | Latest due session |
|---|---|---|---|
| 09:50 | no | no | 12 October |
| 15:29 | no | no | 12 October |
| 15:30 | yes | no | 12 October |
| 18:29 | yes | no | 12 October |
| 18:30 | yes | yes | 13 October |

These examples are timing-rule fixtures, not independently captured
market data. On a scheduled holiday or weekend, only sessions actually
present in the pinned exchange calendar are eligible.

## Backwards-compatible operator interface

Manual retrospective CLI invocations with
\`--as-of-date YYYY-MM-DD --after-market-close\` are preserved, with the
old interpretation that after-market-close also implies that the
source deadline has passed unless overridden.

The realtime workflow switches to the preferred
\`--as-of-utc YYYY-MM-DDTHH:MM:SSZ\`. It cannot combine that timestamp
with manually asserted clock flags. The as-of IST date is derived from
the same timestamp to avoid midnight timezone inconsistency.

A manual invocation can explicitly supply
\`--as-of-date ... --after-market-close\` **without** the
\`--sc001-source-cutoff-passed\` flag to make an intermediate after-close
but before-18:30 report.

## Governance

The existing latest.json historical generated snapshots are derived
operational monitoring products. They do not define the frozen
underlying SC001 evidence. This change does **not** modify:

- any original daily NSE source bytes or source SHA receipts;
- H021 October 9 stock selection or October 12 first entry observation;
- SC001/T004/T006 primary features, statistical endpoints or cutoffs;
- portfolio eligibility, return labels, expected returns or live capital.

No false source capture or backdated observation is created. A new
health snapshot is allowed to supersede the previously mistaken
morning \`STALE\` report while preserving the source/evidence ledgers.

Tests cover 09:50, 15:29, 15:30, 18:29, 18:30 and 20:30 IST,
timezone-naive/non-UTC input rejection, old CLI compatibility and
the distinction between operational health and scientific trial state.
