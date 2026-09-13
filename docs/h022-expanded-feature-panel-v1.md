# H022 expanded historical feature panel v1

Status: **FROZEN_OUTCOME_FREE**

Live capital: **DISABLED**

## Purpose

Replay the unchanged H022-R001 management-information-delta feature over the reconstructed point-in-time Nifty 200 historical-union transcript corpus before reopening historical returns.

## Frozen inputs

- expanded E002 candidate report SHA-256: `45f58e5f0ee72c477ed042fd56be54b4b7c297b78532a011350a44d0a68da861`
- transcript sources: **1,558**
- E002 candidates: **5,090**
- H003-E002 rule unchanged
- H022-R001 feature formula unchanged

## Prior-call semantics

Every public same-company call can serve as prior context, including:

- pre-challenge calls;
- challenge-period calls while the company was outside Nifty 200.

The prior call is always the latest call with a **strictly earlier** exchange publication timestamp. Equal-timestamp calls cannot become one another's prior.

First calls remain explicit no-signal observations.

Historical membership affects only whether the **current** challenge event is evaluation-eligible. It never changes the numerical feature calculation.

## Frozen measured panel

- rows: **1,558**
- valid feature deltas: **1,360**
- challenge evaluation-eligible signals: **753**
- no-prior calls: **198**
- ambiguous-prior calls: **0**
- outcome data attached: **false**

Panel SHA-256:

`f07dd7b9c7925b53b10bca1926b40a086832df3bbe6dbdb42caea43164d617fa`

## Comparison with original survivor-panel H022

Original current-U001 historical panel:

- 794 calls
- 697 valid deltas
- 398 challenge signals

Expanded point-in-time Nifty 200 challenger:

- 1,558 calls
- 1,360 valid deltas
- 753 challenge evaluation signals

The expanded panel substantially increases company/event breadth without changing H022-R001.

## Next gate

The next step may now open historical returns, but only under the unchanged H022-X001 execution conventions:

- first executable NSE session open after publication;
- 20/60/120 holding-session closes;
- NIFTY 500 price-index benchmark over the identical interval;
- 50 bps secondary cost stress;
- share-changing corporate actions block the affected horizon unless a verified adjustment is available;
- no missing bar imputation;
- market-data cutoff remains 2026-09-11.

The expanded universe is a separate historical challenger, not an exact historical U001 reconstruction.
