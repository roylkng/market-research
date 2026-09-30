# AE001 T005 Protocol Amendment P4: Verified FO UDiFF Numeric Units

Frozen: 2026-09-30
Status: FROZEN BEFORE ANY T005 MODEL FIT OR OUTCOME METRIC
Live capital: DISABLED

## Trigger

T005 uses aggregate futures volume/OI/notional features whose correctness depends
on the numeric units in the NSE FO UDiFF bhavcopy.

The first T005 materialization failed before model fitting for the unrelated P3
diagnostic-fold omission. That left the trial outcome unopened and allowed a
source-semantics audit before rerun.

D002 was frozen and executed against the exact 2026-09-25 D001 reference source.

## D002 result

Result file:

`research/ae001-d002-result-v1.json`

Exact source SHA-256:

`d7fda7c5881bf6b1aff715af0c90ae5bdc8fccbb7d537c83e3b1e44470dfa4af`

Stock-futures rows:

629.

Open-interest divisibility violations:

0.

Change-in-open-interest divisibility violations:

0.

Traded futures rows checked against notional-implied price:

628.

Price-range violations:

0.

Maximum price-range violation:

INR 0.

## Frozen unit interpretation

- OpnIntrst:
  underlying-equivalent units, divisible by NewBrdLotQty.

- ChngInOpnIntrst:
  underlying-equivalent units, divisible by NewBrdLotQty.

- TtlTradgVol:
  contract count.

- NewBrdLotQty:
  underlying units per contract.

- TtlTrfVal:
  rupee notional.

## T005 feature consequence

The already-frozen formulas remain unchanged.

### Futures volume to OI

    sum(TtlTradgVol * NewBrdLotQty)
    /
    sum(OpnIntrst)

Both numerator and denominator are underlying-equivalent units.

### Futures notional to cash turnover

    sum(FO TtlTrfVal)
    /
    CM TtlTrfVal

Both numerator and denominator are INR.

## Runtime gate

T005 must require P4 and confirm that:

- existing_t005_feature_formulas_unchanged = true;
- OI unit = UNDERLYING_UNITS_DIVISIBLE_BY_BOARD_LOT;
- traded-volume unit = CONTRACT_COUNT;
- transferred-value unit = RUPEE_NOTIONAL.

## Non-changes

P4 changes no:

- feature definition;
- model;
- l2;
- fold;
- horizon;
- success criterion;
- source window;
- outcome.

No prospective or live-capital claim.
