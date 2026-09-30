# PO001 I003 Protocol Amendment P2: PO001-v1 Portfolio Equivalence Audit

Frozen: 2026-09-29
Status: FROZEN BEFORE ANY I003 PORTFOLIO RESULT
Live capital: DISABLED

## Purpose

P1 established that the legacy I002 RM001 state and the current canonical RM001
state are economically identical within the frozen serialization tolerance.

The sealed I002 PO001-v1 optimizer artifact embeds the legacy risk-state SHA.
Before I003 may replace that mechanical hash gate, the portfolio itself must be
reconstructed under both RM001 representations.

## Frozen audit inputs

Alpha, market, action, delivery, cost and PO001-v1 parameters are identical to
sealed I002:

- decision session: 2026-08-31;
- horizon: 5 sessions;
- T003 fold-2 augmented ridge;
- validation start: 2026-07-01;
- risk aversion: 5.0;
- max name weight: 5%;
- max invested weight: 100%;
- max traded fraction: 100%;
- starts from cash;
- terminal liquidation: true;
- no factor hard bounds;
- TC001 observable buy/sell costs only.

Legacy I002 optimizer artifact SHA:

`ad77db26c76e54921254aea9e49c30da8b1f044076b57961671229e93100154e`

Legacy RM001 state SHA:

`b1d6898f1083d752ca7db6dc7509b8ef4a2aef0f1543f24fd8b30f07604d80c1`

Canonical RM001 state SHA:

`7a0a440515a2f75e0114281dd37a1bf4c6801e1b2e17a0b78183e89fe663abce`

## Required audit

1. Reconstruct the exact I002 alpha vector from sealed I002 source artifacts.
2. Optimize PO001-v1 using the legacy I002 RM001 state.
3. Require exact optimizer artifact SHA match to the sealed I002 optimizer SHA.
4. Optimize the identical alpha/cost problem using the canonical RM001 state.
5. Compare portfolios identity-by-identity.

Frozen equivalence tolerances:

- maximum absolute target-weight difference: 1e-9;
- invested-weight difference: 1e-10;
- expected-alpha difference: 1e-12;
- total daily variance difference: 1e-12;
- risk-penalty difference: 1e-12;
- immediate cost difference: 1e-12;
- terminal cost difference: 1e-12;
- objective-utility difference: 1e-12;
- maximum absolute factor-exposure difference: 1e-12.

All identity sets must be identical.

## Promotion rule

If and only if all gates pass, the canonical PO001-v1 optimizer artifact SHA may
be frozen in a subsequent pre-result I003 amendment and used as the executable
baseline reproduction gate.

The legacy optimizer hash remains immutable provenance.

No I003 stock-impact optimizer result may be opened before this audit passes.
