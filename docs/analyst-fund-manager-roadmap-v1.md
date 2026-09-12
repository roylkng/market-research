# Analyst + Fund Manager implementation roadmap v1

Status: **ACTIVE ROADMAP PROPOSAL**
Created: 2026-09-12
Live capital: disabled

## Goal

Build a continuously improving research and paper-fund system without turning recent winners into hindsight-optimized rules.

## Workstream 1 — Analyst Decision Ledger

Priority: **P0**

Implement a structured, immutable company-decision record.

Deliverables:

- schema/version for Analyst Decision Object;
- immutable timestamp and source provenance;
- company/horizon state;
- base/bull/bear scenarios;
- catalysts and invalidations;
- H013/H019/H020/H021 references;
- valuation assumptions;
- forecast fields with calibration status;
- action state;
- development-vs-validation flag.

Acceptance:

- the same record can be scored later without reading a rewritten analyst memo;
- unsupported probabilities remain null;
- material changes produce a new record, never mutate history.

## Workstream 2 — PF001 Paper Fund Engine

Priority: **P0**

Implement the frozen PF001 policy.

Deliverables:

- virtual NAV ledger;
- 5% unit entries;
- sector-cap enforcement;
- next-session execution convention;
- 20/60-session checkpoints;
- 0.50% round-trip research friction;
- cash ledger;
- benchmark ledger;
- immutable entry/exit evidence;
- development book separate from prospective validation book.

Acceptance:

- every position and rejected signal is reconstructable;
- capital cannot exceed NAV;
- no retrospective fill price;
- current pre-freeze names cannot be counted as PF001 validation evidence.

## Workstream 3 — Counterfactual Attribution

Priority: **P0**

Run the same frozen analyst decisions through:

- PF001 actual paper policy;
- CF-A immediate-entry book;
- CF-B unconstrained equal-notional book;
- CF-C benchmark-only book.

This is how we answer:

- did stock selection work?
- did H020 timing add value?
- did portfolio constraints help or hurt?
- did cash waiting add value or miss winners?

## Workstream 4 — Forecast Calibration

Priority: **P1**

Create a forecast scorecard by horizon and model.

Track:

- directional hit rate;
- Nifty-500-relative return distribution;
- information coefficient;
- Brier score where probabilities exist;
- probability calibration buckets;
- P10/P50/P90 quantile coverage;
- MAE/MFE;
- time under water;
- forecast error by sector, market-cap and regime.

Do not allow numerical confidence to become a UI decoration. If it is not calibrated, label it experimental or null.

## Workstream 5 — Company Analyst Memory

Priority: **P1**

Maintain a point-in-time company ledger for recurring coverage names.

Per company retain:

- management promises and delivery history;
- capital allocation history;
- order/capacity/catalyst timeline;
- earnings and cash-flow inflection history;
- consensus-revision history;
- valuation history;
- thesis invalidations;
- model mistakes involving that company.

The analyst should become better at a company because it remembers **what was believed at the time and what actually happened**, not because later facts overwrite the earlier record.

## Workstream 6 — Risk Model

Priority: **P1**

Start simple and deterministic:

- rolling volatility;
- beta to benchmark;
- pairwise/cluster correlations;
- sector concentration;
- theme concentration;
- liquidity proxy;
- event/gap flags;
- portfolio drawdown;
- exposure to oil, INR, rates or commodities where explicitly tagged.

Do not build a complex optimizer until simple risk measurements are stable.

## Workstream 7 — Champion / Challenger Registry

Priority: **P1**

For every component maintain:

- champion version;
- challenger versions;
- freeze timestamp;
- design dataset;
- validation dataset;
- prospective observations;
- promotion gates;
- correlation with existing models;
- status: shadow / eligible / promoted / rejected.

No model changes daily because of yesterday's P&L.

## Workstream 8 — Meta Allocator

Priority: **P2 — blocked until independent evidence**

Only after H013/H021 and the analyst/PF001 pipeline have enough independent prospective evidence, test combinations such as:

- equal-weight signal voting;
- reliability-weighted combination;
- regime-conditional model weights;
- expected-alpha / active-risk optimization.

The meta allocator must be a separately frozen experiment.

Its primary comparison is against simple component models and PF001, not against zero.

## Workstream 9 — Fund Manager Dashboard

Priority: **P2**

Build only after ledgers are correct.

Views:

- current portfolio and cash;
- watch / eligible / held / exit states;
- thesis/catalyst calendar;
- signal agreement/disagreement;
- portfolio risk and correlation map;
- benchmark-relative attribution;
- forecast calibration;
- model champion/challenger status;
- research failures and unresolved blockers.

The dashboard must never become the source of truth. It renders immutable ledgers.

## Workstream 10 — Live Capital Gate

Priority: **P3 — disabled**

Do not design broker automation first.

Before any live-capital proposal require:

- sufficient prospective paper observations;
- positive net benchmark-relative evidence;
- acceptable information ratio/drawdown;
- stable source pipelines;
- operational failure tests;
- explicit live risk budget;
- tax/fee/slippage model;
- human approval and kill switch;
- separate live-capital policy.

## Operating learning loop

```text
Observe
  -> freeze evidence
  -> forecast
  -> decide
  -> allocate
  -> wait for outcome
  -> attribute error/value
  -> update model evidence
  -> challenge, not rewrite, the current champion
```

### What may improve continuously

- source coverage;
- data quality;
- company knowledge;
- error taxonomy;
- forecast calibration;
- challenger models;
- risk estimates;
- execution realism.

### What must not change continuously

- frozen experiment rules;
- past analyst decisions;
- historical position fills;
- validation cohorts;
- outcome labels;
- model thresholds currently under evaluation.

## Immediate sequence

1. Merge the operating-system and PF001 policy docs.
2. Implement Analyst Decision Object schema and immutable decision writer.
3. Implement PF001/CF-A/CF-B/CF-C ledgers.
4. Start PF001 validation only on decisions frozen after PF001 policy freeze.
5. Keep H020 daily and H021 weekly capture running.
6. Restore/continue H013 prospective monthly process.
7. Add attribution and calibration reports before experimenting with sophisticated sizing.
8. After sufficient matured prospective decisions, test the first meta-allocator challenger.
