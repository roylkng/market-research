# PO001 I004 RM001-v3 Risk-Treatment Integration v1

Status: FROZEN BEFORE FIRST I004 MATERIALIZATION
Frozen: 2026-10-02
Live capital: DISABLED

## Objective

Measure how the richer RM001-v3 risk model changes a fixed PO001-v3 portfolio
problem when alpha, execution costs, capacity, NAV and optimizer semantics are
held constant.

I004 is an outcome-blind integration study. It does not open any return after
the frozen decision session.

## Decision snapshot

Decision session:

    2026-08-31

Alpha horizon:

    5 completed NSE sessions

Portfolio NAV:

    INR 10,000,000

The subsequent realized five-session return is not opened by I004.

## Alpha input

Exact sealed I002/T003 fold-2 augmented ridge model:

    research/po001-i003/inputs/i002-alpha-model-v1.json

Required model SHA:

    179ce84f40c1b6e461d2ff1f4104753381d3327b2dda35814b4a913547f91260

Required delivery-feature panel SHA:

    47ee538af6cfca16405632ce6396571455a548687b4ceabfd7999040a86f8b44

No alpha refit or ranking change is allowed.

## Execution input

Identical to frozen I003 primary NAV treatment:

- PO001-v3 optimizer;
- NAV = INR 10,000,000;
- TC001 observable buy/sell costs;
- square-root impact coefficient k = 0.50;
- maximum participation per side = 10% ADV20;
- ADV20 = median traded value over latest 20 completed sessions including D;
- volatility = AE001 realized_vol_20 on D;
- max name weight = 5%;
- max invested weight = 100%;
- max traded fraction = 100%;
- starts from cash;
- terminal liquidation = true;
- no hard factor bounds.

No bid-ask spread is fabricated.

## Control risk

Exact sealed I002 RM001-v1 risk state:

    research/po001-i003/inputs/i002-risk-state-legacy.json.gz

Required state SHA:

    b1d6898f1083d752ca7db6dc7509b8ef4a2aef0f1543f24fd8b30f07604d80c1

## Treatment risk

Exact sealed RM001-v3 P001 state from the successful materialization run:

- workflow run: 36958406605;
- artifact: rm001-v3-p001-36958406605;
- required RM001-v3 state SHA:

    32002ec101531c0e28fb551058c79f179fca53aafccf3c36ef07cb0159387441

The exact gzip artifact must be pinned in the I004 namespace before
materialization.

## Control reproduction gate

PO001-v3 with the control risk state must reproduce the sealed I003 primary
INR-10m capacity surface before the treatment portfolio is interpreted.

Frozen I003 reference:

- holding count: 47;
- expected 5D excess return: 0.010268398328395899;
- annualized volatility: 0.12926327992563452;
- total transaction-cost fraction: 0.00268388045086663;
- immediate impact-cost fraction: 0.00022953422543330209;
- terminal impact-cost fraction: 0.00022953422543330209;
- maximum observed participation: 0.0036964433816679327;
- objective utility: 0.005926879431385127.

Frozen scalar tolerance:

    1e-10

Holding count must match exactly.

This is an implementation reproduction gate, not an outcome test.

## Treatment comparison

The control and treatment use the exact same:

- alpha vector;
- common identity universe;
- ADV20;
- realized_vol_20;
- buy/sell observable cost bps;
- NAV;
- optimizer parameters.

Only the supplied risk state changes.

Report:

- target-weight L1 and maximum absolute change;
- holding-count change;
- expected-alpha change;
- annualized-volatility change;
- factor/idiosyncratic/total variance change;
- modeled transaction-cost change;
- utility change;
- concentration/effective-name changes;
- SIZE exposure;
- STAT_PC01..05 exposures;
- top weight increases/decreases.

## Interpretation

I004 does not define success as lower volatility.

RM001-v3 can legitimately increase measured factor variance by reclassifying
common covariance that RM001-v1 treated as idiosyncratic.

The study asks whether the richer risk map causes economically material
portfolio decisions and where those changes come from.

## Prohibited

- no realized post-31-Aug outcome;
- no alpha refit;
- no parameter tuning after treatment results;
- no sector proxy;
- no live capital;
- no prospective claim.

## Next gate

If I004 materializes cleanly, PO001-v3 may be used in a separately frozen
prospective paper-portfolio protocol only after the prospective RM001-v3 source
gate itself has produced a valid state.
