# PF001 implementation contract v1

Status: **FROZEN BEFORE PF001 VALIDATION OUTCOMES**

Policy freeze commit: `096436711bfe8992cc64e2df491b0e6f7df22768`

Policy freeze timestamp: `2026-09-11T18:46:13Z` (`2026-09-12T00:16:13+05:30`)

Live capital: **DISABLED**

This document fixes implementation details that the PF001 policy intentionally left at a higher level. These mechanics are frozen before any PF001 prospective-validation position is allowed to count toward portfolio evidence.

## Analyst action vocabulary

The canonical positive analyst action is:

`PORTFOLIO_ELIGIBLE`

The v1 Analyst Decision Object accepts exactly:

- `REJECT`
- `WATCH`
- `PORTFOLIO_ELIGIBLE`
- `HOLD_REVIEW`

Any earlier prose using bare `ELIGIBLE` is interpreted as documentation shorthand only. The machine-readable value is `PORTFOLIO_ELIGIBLE`.

## Development versus validation books

Two books are mandatory:

- `DEVELOPMENT`
- `PROSPECTIVE_VALIDATION`

A decision can enter only the book matching its frozen `validation_role`.

A `PROSPECTIVE_VALIDATION` decision must be timestamped strictly after the PF001 policy freeze. Current names that influenced PF001 design may be followed in `DEVELOPMENT` but cannot count as PF001 validation evidence from their already-observed setup.

## Decision-to-entry timing

A decision must be frozen on an Asia/Kolkata calendar date strictly earlier than the entry session date.

This intentionally forbids any same-session retrospective open fill, even if a decision object is written later that day.

The first eligible execution is the next completed NSE session for which the frozen market-data source provides an executable open proxy.

## Same-session ordering

When multiple analyst decisions become executable on the same session, process them deterministically by:

1. `decision_timestamp` ascending;
2. `symbol` ascending as the tie-breaker.

This ordering is not an alpha rank. It exists only to make capacity and sector-cap decisions reproducible. A later priority/alpha allocator is a separate portfolio-policy challenger.

## Position sizing and share units

For all decisions in one same-session entry batch:

- calculate batch NAV once before any fills;
- use friction-adjusted (`net`) NAV for the batch NAV;
- target notional per position = `5% * batch NAV`;
- execute whole shares only;
- shares = floor(target notional / executable open price);
- unused notional remains cash.

If even one share exceeds the target notional, record `MISSED_INSUFFICIENT_UNIT_CAPITAL`.

## Sector cap

Sector exposure is measured using open-position acquisition cost basis.

A new fill is rejected if:

`existing sector cost basis + proposed cost basis > 25% * batch NAV`

The rejection reason is `RISK_REJECTED_SECTOR_CAP`.

## Friction accounting

The frozen 0.50% round-trip research friction is implemented symmetrically:

- 0.25% of executed notional at entry;
- 0.25% of exit proceeds at exit.

The engine therefore keeps separate gross and friction-adjusted cash/NAV ledgers.

This split is an accounting convention for PF001-v1. Any India-specific tax/fee/slippage model is a future challenger and may not rewrite PF001-v1 outcomes.

## Holding-session counting

The entry session counts as holding session 1 because the position is assumed entered at the executable open proxy.

The 20-session checkpoint therefore occurs on the twentieth completed NSE session including the entry session.

The primary maturity occurs on holding session 60 and exits at that completed session's executable close proxy.

## Missing marks and suspended/non-executable exits

Portfolio holding-session count advances with completed NSE market sessions, not only sessions where the security has a fresh quote.

If a security has no usable mark on an intermediate market session:

- carry the last valid price for NAV;
- increment a missing-mark counter;
- continue the market-session holding count.

If the security has no executable mark when the 60-session maturity is reached:

- mark the position `maturity_pending`;
- do not invent an exit;
- exit at the first later completed session with an executable close proxy;
- retain the original maturity condition in the ledger.

## Early exits

An early exit is allowed only when the exact condition was frozen in the Analyst Decision Object with severity `HARD`.

Price weakness alone is not an implicit hard invalidation.

## Research integrity

Any research state containing an unresolved `BLOCKED`, `REJECTED`, or `FAILED` state fails closed for PF001 entry unless a later independently frozen analyst decision resolves that research issue before entry.

`MISSING_EXPECTATION_SIGNAL` for H021 before a valid comparison window is not considered a research block.

## Event ledger

Every state-changing operation emits an append-only deterministic event, including at least:

- fund creation;
- entry filled;
- entry rejected/missed;
- 20-session checkpoint;
- session mark;
- position close.

Event history is evidence. Derived portfolio state may be regenerated or summarized, but historical events must never be edited to improve results.
