# AE001 T005 Protocol Amendment P1: Strictly Future Expiry Selection

Frozen: 2026-09-30
Status: FROZEN BEFORE OUTCOME MATERIALIZATION
Live capital: DISABLED

## Trigger

D001 confirmed that the FO UDiFF file includes settlement/open-interest records
for stock-futures contracts by actual expiry date.

The original T005 protocol stated that contract parsing may retain expiry >= trade
date, while the frozen basis-per-day features require a strictly positive
days-to-expiry denominator.

No T005 outcome/model comparison has been materialized.

## Frozen resolution

For T005 feature construction:

- parser may retain structurally valid STF rows whose expiry >= trade date;
- feature construction uses only contracts with expiry > trade date;
- expiring-today contracts are excluded from front/next selection and all
  T005 aggregate OI/volume/notional fields;
- front contract = earliest strictly future expiry;
- next contract = second distinct strictly future expiry;
- at least two distinct strictly future expiries are required.

This keeps carry/basis denominators strictly positive and avoids a special
expiry-day clamp.

## Non-changes

P1 does not change:

- source window;
- ten frozen feature definitions;
- model family or ridge l2;
- folds;
- horizons;
- success criteria;
- exact-row base-vs-augmented comparison;
- any outcome.

No prospective or live-capital claim.
