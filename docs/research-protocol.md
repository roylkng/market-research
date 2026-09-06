# Research protocol

## Purpose

`market-research` exists to discover whether a narrowly specified market hypothesis produces economically useful out-of-sample evidence. It does not exist to keep a hypothesis alive.

## Hypothesis lifecycle

Every hypothesis moves through these states:

`PROPOSED -> FROZEN -> TESTING -> REJECTED | INCONCLUSIVE | PROMISING`

A frozen hypothesis is immutable for that experiment. Any material change to universe, feature, entry rule, holding period, benchmark, or cost model creates a new hypothesis/version.

## Required pre-registration

Before outcomes are inspected, record:

- hypothesis ID and economic mechanism
- universe and exclusions
- information timestamp / decision timestamp
- feature definition
- entry and exit convention
- holding horizon
- benchmark(s)
- transaction-cost assumptions
- primary metric and rejection criteria
- known data-quality limitations

## Experiment rules

1. Include every eligible observation, not only illustrative winners.
2. Missing data remains missing. Never infer a historical trade fill from a daily high/low alone.
3. Do not mix cash and futures prices.
4. Corporate actions and restatements must be handled point-in-time.
5. A result generated after a rule change belongs to a new experiment.
6. Every tried parameter or filter counts as a research trial.
7. Report winner concentration and leave-one-out sensitivity.
8. Compare against simple investable baselines before adding model complexity.

## Promotion standard

A result may be marked `PROMISING` only when it:

- has a plausible economic mechanism,
- survives realistic costs,
- is not dominated by a handful of observations,
- beats appropriate simple benchmarks at comparable risk,
- survives walk-forward / holdout testing,
- and has no material unresolved point-in-time leakage.

`PROMISING` authorizes prospective paper testing, not live capital.

## Live-capital gate

No live-capital deployment is allowed from repository research until a separate live-capital policy is created and explicitly approved. Current status: **disabled**.
