# PO001 I003 Protocol Amendment P1: RM001 Canonical Representation

Frozen: 2026-09-29
Status: FROZEN BEFORE ANY I003 PORTFOLIO RESULT
Live capital: DISABLED

## Trigger

The first frozen I003 materialization attempt (run 36575345889) failed closed
before portfolio construction because the rebuilt RM001 state SHA-256 differed
from the SHA recorded by the sealed I002 result.

No I003 portfolio result was produced.

## Root cause

PR #132 introduced RM001's frozen 15-decimal canonical float serialization after
the original I002 materialization had recorded its risk-state hash.

The original I002 state:

`b1d6898f1083d752ca7db6dc7509b8ef4a2aef0f1543f24fd8b30f07604d80c1`

The current canonical RM001-v1 rebuild:

`7a0a440515a2f75e0114281dd37a1bf4c6801e1b2e17a0b78183e89fe663abce`

## Frozen equivalence audit

Diagnostic run: 36579160593.

The diagnostic downloaded the exact sealed I002 evidence and the exact failed
I003 evidence and compared the two risk-state artifacts directly.

Required invariants passed:

- identical model ID;
- identical as-of session;
- identical factor names;
- identical covariance window and realized-session boundaries;
- identical idiosyncratic windows;
- identical security count;
- identical deferred-factor state;
- identical symbol + ISIN identity set.

Maximum numerical differences:

- factor exposure: 1.3322676295501878e-15;
- factor covariance: 0.0;
- idiosyncratic variance: 0.0;
- idiosyncratic fallback p75: 0.0;
- idiosyncratic status differences: 0.

Frozen audit tolerance: 5e-15.

Classification:

`ECONOMICALLY_EQUIVALENT_CANONICAL_REPRESENTATION`

## I003 reproduction rule after P1

I003 must preserve both hashes:

- legacy I002 risk-state SHA as source provenance;
- canonical RM001-v1 risk-state SHA as executable reproduction state.

The canonical SHA may replace the legacy SHA only for the mechanical execution
gate after this amendment.

This amendment does not change:

- factor definitions;
- covariance;
- idiosyncratic risk;
- alpha;
- risk aversion;
- portfolio constraints;
- impact coefficient;
- participation cap;
- NAV surfaces;
- realized outcomes.

## Downstream PO001-v1 gate

The sealed I002 PO001-v1 optimizer artifact hash also embeds the legacy RM001
state hash. Therefore its hash must not be mechanically replaced without a
separate portfolio-level equivalence audit.

I003 remains blocked at that downstream gate until the portfolio equivalence
audit is completed and frozen.

No I003 result may be opened before that second audit passes.
