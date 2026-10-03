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

## Global research-trial accounting

Per-trial freezing is necessary but not sufficient once the lab runs many
experiments.

Every outcome-bearing research trial must also be represented in:

`research/rta001-trials-v1.json`

before its result is opened whenever operationally possible.

The global entry records:

- trial identity;
- scientific category;
- registration mode;
- frozen primary endpoint;
- reported primary support state;
- scalar primary p-value when valid;
- multiple-testing family when applicable;
- result/source provenance.

Rules:

1. Secondary or diagnostic endpoints never replace a failed frozen primary.
2. A trial discovered to be missing from the global ledger is backfilled as
   `RETROSPECTIVE_ACCOUNTING_BACKFILL`; omission never removes it from the
   research budget.
3. Feature-discovery trials are evaluated under RTA001 family-level
   multiplicity diagnostics in addition to their original nominal inference.
4. Combination diagnostics, portfolio integration, source feasibility,
   risk-model and solver studies remain globally counted but are not silently
   pooled into the stock-alpha FDR family.
5. A nominally supported historical result that is not multiplicity-robust is
   preserved as nominally supported, but promotion language must disclose the
   global accounting result.
6. Prospective confirmation remains the preferred route for promotion.

### CI accounting gate

Repository CI fails closed when any of the following occurs:

- a new `research/**/*result*.json` artifact exists without an explicit RTA001
  trial result path or source-feasibility entry;
- an `AE001` `TRIAL_REGISTERED` event is absent from the RTA001 trial manifest;
- a canonical hypothesis in `registry/hypotheses.yaml` is absent from RTA001;
- RTA001 references a result artifact that no longer exists;
- the checked-in `research/rta001-summary-v1.json` does not exactly match the
  current explicit manifest.

The gate detects missing accounting only. It does not infer scientific category,
primary endpoint, preregistration status, p-value, or FDR family. Those remain
explicit reviewed research decisions.

This means a new result cannot become invisible simply because its author forgot
to update the global accounting surface.

