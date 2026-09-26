# Architecture direction

MarketLab now has two simultaneous responsibilities:

1. preserve falsifiable, independently frozen market hypotheses;
2. build a reusable point-in-time alpha-research system capable of testing many features and models at scale.

These responsibilities must remain scientifically separated.

The detailed implementation program is defined in
`docs/alpha-factory-implementation-plan-v1.md`.

## Track A: frozen scientific experiments

H-series experiments remain mechanism tests.

Their rules, universes, timestamps, horizons and evidence ledgers stay independent.
AE001 may consume only already sealed point-in-time H-series observations whose information timestamps
precede the AE001 decision cutoff. AE001 may never write to or reinterpret canonical H-series state.

This track answers:

> Does a narrowly specified economic mechanism contain predictive information?

## Track B: alpha factory

The alpha factory operates on reusable point-in-time feature vectors across a dynamic investable universe.

```text
Official/public sources
        |
        v
Content-addressed evidence
        |
        v
Point-in-time observations
        |
        v
Dynamic investable universe
        |
        v
Feature snapshots
        |
        v
AE001 horizon-specific models
        |
        v
OOS alpha library
        |
        v
AB001 alpha blender
        |
  +-----+-----+
  |           |
  v           v
RM001 risk   TC001 cost
  |           |
  +-----+-----+
        v
PO001 portfolio optimizer
        |
        v
Paper execution and attribution
```

This track answers:

> Given all information actually available at time t, can we rank tradable stocks by future excess return,
> and does that information survive realistic portfolio constraints and trading costs?

## Horizon separation

Different horizons remain explicit rather than being collapsed into one narrative score.

- next session and 1-5 sessions: events, gaps, positioning, liquidity and fast expectation changes;
- 5-20 sessions: revisions, momentum, flows, event drift and short-horizon fundamentals;
- 20-60 sessions: broader fundamentals, ownership, medium-term momentum and management information;
- longer horizons remain separate research programs unless explicitly frozen.

AE001 v1 begins with an EOD daily sleeve and 1/5/20/60-session labels.

## Current architecture priority

The project no longer has only a signal-validity bottleneck.

It has two bottlenecks that must be attacked in parallel:

- scientific validity of individual mechanisms;
- throughput and comparability of point-in-time cross-sectional research.

Continuing to create isolated H-series experiments without a shared feature/model/evaluation plane would
make the research rigorous but too slow to compound into a portfolio system.

Conversely, building a large ML system without preserving prospective scientific controls would create a
high-throughput backtest-overfitting machine.

The dual-track architecture exists to avoid both failure modes.

## Portfolio research

PF001 remains the frozen simple equal-unit paper-fund baseline.

Future portfolio challengers may use:

- alpha-confidence sizing;
- cross-alpha diversification;
- factor and covariance risk;
- liquidity and turnover constraints;
- explicit transaction-cost and market-impact estimates;
- regime-conditional allocation.

They must be frozen before their comparison outcomes are opened.

## Operational architecture

GitHub is the evidence, review and CI layer.

It must not be the sole clock for time-critical pre-open or event-time collection. Deterministic external
scheduling, idempotent acquisition and stale-data monitoring belong in the prospective operations layer.

The September 25, 2026 H024 delayed/failed pre-entry collection is the reference failure case.

## Explicit non-goals

- broker-connected autonomous live trading before a separate live-capital policy;
- high-frequency or colocation competition;
- an LLM committee that directly selects stocks;
- reinforcement learning before strong simpler baselines exist;
- optimizing model complexity before point-in-time data and OOS evaluation are reliable;
- modifying frozen H-series rules to improve AE001 results.

## Immediate build sequence

1. AE001 point-in-time market feature plane.
2. AE001 reproducible feature snapshots.
3. 1/5/20/60-session label engine.
4. Purged chronological walk-forward evaluation.
5. Linear/rank baseline.
6. Broader feature families and nonlinear challengers.
7. OOS alpha library and orthogonality analysis.
8. AB001 blender.
9. RM001 risk and TC001 cost models.
10. PO001 portfolio construction and a separately frozen paper challenger.

Live capital remains disabled.
