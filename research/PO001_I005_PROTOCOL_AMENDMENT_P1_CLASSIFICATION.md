# PO001 I005 Protocol Amendment P1: Materiality Classification Rule

Frozen: 2026-10-02
Status: FROZEN BEFORE PINNED S001 PORTFOLIO INSPECTION
Live capital: DISABLED

## Purpose

The parent I005 protocol froze individual materiality thresholds before the
pinned S001 weight vectors were inspected.

P1 freezes how those thresholds combine into the final I005 classification.

## Frozen materiality flags

Define:

### Reallocation material

True if either:

    weight L1 change >= 0.05

or:

    maximum absolute name-weight change >= 0.005

### Alpha material

True if:

    absolute expected 5D excess-return delta >= 0.0001

### Cost material

True if:

    absolute total transaction-cost fraction delta >= 0.0001

### RM001-v1 common-map risk material

True if:

    absolute annualized-volatility delta,
    treatment weights minus control weights,
    evaluated under RM001-v1
    >= 0.005

### RM001-v3 common-map risk material

True if:

    absolute annualized-volatility delta,
    treatment weights minus control weights,
    evaluated under RM001-v3
    >= 0.005

## Final classification

If either frozen optimality sanity check fails:

    IMPLEMENTATION_SANITY_CHECK_FAILED

Otherwise if ANY materiality flag above is true:

    MATERIAL_RISK_MODEL_PORTFOLIO_EFFECT

Otherwise:

    LIMITED_RISK_MODEL_PORTFOLIO_EFFECT

## Important interpretation

A MATERIAL classification means only that changing the risk map caused a
material portfolio-construction effect under the frozen historical snapshot.

It does NOT mean RM001-v3 is a more accurate risk forecast.

No realized return is opened.

No live-capital implication.
