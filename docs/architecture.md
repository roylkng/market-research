# Architecture direction

The project starts as a research ledger and experiment harness. It should not become an autonomous trading platform until independent signals survive prospective testing.

## Eventual model system

```text
Global regime
  rates / dollar / oil / global risk
        |
India regime
  liquidity / flows / inflation / credit / INR
        |
+-------------------------------+
|               |               |
Earnings        Momentum        Event
model           model           model
|               |               |
+---------------+---------------+
                |
         Meta allocator
                |
           Risk model
```

The meta layer should not directly predict price. Its eventual job is to estimate which specialized model is more trustworthy in the current regime.

## Separation by horizon

Do not combine features that operate on different horizons into one narrative score.

- **Intraday / next session:** overnight global moves, event surprises, positioning, liquidity, auction mechanics.
- **1–20 sessions:** earnings revisions, momentum, breadth, flows, rates, oil, sector-relative strength.
- **1–6 months:** earnings breadth, credit conditions, valuations, macro regime, capital flows.
- **multi-year:** earnings growth, ROIC, reinvestment runway, governance, starting valuation.

## Phases

### Phase 0 — current
Research ledger, hypothesis registry, evaluation harness, failed experiments preserved.

### Phase 1
Point-in-time earnings dataset and prospective H002 paper tracking.

### Phase 2
Backtest engine, factor registry, walk-forward evaluation. Only after a signal survives Phase 1.

### Phase 3
Regime model, multiple independent signals, portfolio/risk allocator.

### Phase 4
Tiny live-capital experiment after prospective evidence and explicit governance.

### Phase 5
UI, automation, broker integration or productization only after economic evidence.

## Explicit non-goals today

- broker integration
- autonomous order execution
- reinforcement-learning trader
- LLM committee picking stocks
- options strategy engine
- high-frequency infrastructure
- production UI

The current bottleneck is signal validity, not infrastructure throughput.
