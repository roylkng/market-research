# Market Analyst + Fund Manager Operating System v1

Status: **PROPOSED OPERATING CONTRACT**
Created: 2026-09-12
Live capital: **DISABLED**

## Purpose

Convert `market-research` from a collection of stock-selection experiments into a reproducible investment-research and portfolio-management operating system without weakening the project's point-in-time and out-of-sample standards.

The system must answer five different questions separately:

1. **What is changing in the business?**
2. **What is changing in market expectations?**
3. **Is price beginning to recognize that change?**
4. **Is the current entry/exit state attractive?**
5. **How much capital, if any, should a portfolio allocate given risk, correlation, liquidity and opportunity cost?**

A company can pass one layer and fail another. No layer may silently overwrite another layer's failed result.

## Architecture

```text
Point-in-time evidence
  filings / calls / prices / consensus / macro / news
                |
                v
+-----------------------------------------------+
| Independent research engines                   |
|                                                |
| H019  business/accounting reality              |
| H021  forward-expectation revisions            |
| H013  price recognition / relative momentum    |
| H020  entry timing / price state               |
+-----------------------------------------------+
                |
                v
        Analyst decision object
  thesis + scenarios + calibrated forecasts
                |
                v
        Portfolio construction
 expected alpha / confidence / risk / correlation
                |
                v
           Paper fund
 positions / cash / limits / execution assumptions
                |
                v
   Attribution + forecast calibration
 selection / timing / sizing / regime / costs
                |
                v
         Controlled learning loop
 champion/challenger, promotion/demotion, no hindsight edits
```

The eventual meta-allocator must consume independently validated outputs. It must not be trained by blending every available feature into one opaque score before the component signals have independent evidence.

## Roles

### Research engine

Discovers and validates narrow mechanisms. Existing `Hxxx` experiments live here.

Responsibilities:

- point-in-time source integrity;
- preregistration;
- historical challenge where legitimate;
- prospective testing;
- baselines and costs;
- preserving negative experiments.

It does **not** decide portfolio weights.

### Market analyst

Maintains a decision-ready company view using only information available at the decision timestamp.

For each company/horizon the analyst must publish a frozen **Analyst Decision Object** rather than an unstructured narrative.

Required fields:

- decision timestamp;
- company identity and sector;
- intended horizon;
- business thesis;
- thesis evidence and source timestamps;
- valuation assumptions;
- H019 state/evidence;
- H021 state/evidence;
- H013 state/evidence;
- H020 action state;
- market and sector regime;
- key catalysts and expected windows;
- explicit invalidation conditions;
- base / bull / bear scenarios;
- benchmark-relative return forecast or `null`;
- probability of beating benchmark or `null`;
- downside / adverse-excursion forecast or `null`;
- confidence/calibration status;
- known missing information;
- analyst action: `REJECT`, `WATCH`, `ELIGIBLE`, or `HOLD_REVIEW`.

Unsupported numerical precision is forbidden. A probability may be emitted only from a calibrated model or a clearly labelled experimental forecast series that will itself be scored prospectively.

### Portfolio manager

Transforms eligible analyst views into a portfolio. The PM cannot resurrect a rejected research signal.

Responsibilities:

- opportunity ranking;
- position sizing;
- diversification;
- risk budgeting;
- cash allocation;
- turnover and liquidity trade-offs;
- opportunity cost;
- rebalance/exit decisions;
- documenting every discretionary override.

### Independent risk layer

Risk is not a negative alpha score. It is an independent constraint layer.

Track at minimum:

- single-name concentration;
- sector/theme concentration;
- market beta;
- correlation clusters;
- realized and expected volatility;
- maximum drawdown;
- liquidity / days-to-exit proxy;
- gap/event exposure;
- commodity/FX/rate sensitivities where material;
- portfolio turnover and transaction-cost load.

The risk layer may veto or shrink a position. It may not manufacture a positive expected return.

### Evaluator

Owns outcomes and attribution after the decision is frozen.

The evaluator must be logically separated from the component that wrote the original forecast.

## Forecast object

The project should stop treating `BUY / SELL` as the primary prediction target. Each decision should forecast a distribution or a set of observable outcomes over a specified horizon.

Preferred fields:

- horizon sessions;
- expected benchmark-relative return;
- P10 / P50 / P90 benchmark-relative return where calibrated;
- probability of benchmark outperformance;
- probability of predefined downside barrier before upside barrier;
- expected maximum adverse excursion;
- expected time to thesis/catalyst realization.

If the system cannot support one of these fields, store `null` and the reason. Do not substitute narrative confidence for numerical calibration.

## Decision state machine

```text
RESEARCH_CANDIDATE
      |
      v
WATCH_FUNDAMENTAL
      |
      v
WATCH_TIMING
      |
      v
PORTFOLIO_ELIGIBLE
      |
      +----------> PAPER_POSITION
      |                  |
      |                  v
      |             HOLD_REVIEW
      |                  |
      |          +-------+-------+
      |          v               v
      |       INCREASE         REDUCE
      |                          |
      +--------------------------+
                                 v
                                EXIT
```

A failed short-term entry may not be relabelled as a long-term holding merely because price falls.

## Portfolio and model namespaces

Keep research hypotheses and portfolio rules separate:

- `Hxxx`: economic/forecasting hypotheses;
- `PFxxx`: paper-fund portfolio policies;
- `Rxxx`: risk policies or revisions when needed;
- `Cxxx`: champion/challenger model-combination experiments when independent signal evidence exists.

Creating a portfolio policy is **not** a new stock-selection hypothesis.

## Attribution

Every paper-fund outcome should decompose value added into at least:

1. **selection**: did eligible names outperform the benchmark?
2. **timing**: did H020 improve entry/exit versus immediate-entry counterfactuals?
3. **sizing**: did portfolio weights improve versus equal weight?
4. **regime**: was performance concentrated in particular market states?
5. **costs**: how much edge disappeared after realistic friction?
6. **cash/opportunity cost**: did waiting help or merely miss winners?

Maintain deterministic counterfactual portfolios so each layer can be evaluated independently.

## Error taxonomy

For every material miss, classify the first-order error rather than rewriting the thesis:

- `BUSINESS_THESIS_ERROR`
- `EXPECTATION_REVISION_ERROR`
- `VALUATION_ERROR`
- `TIMING_ERROR`
- `REGIME_ERROR`
- `SIZING_ERROR`
- `EXIT_ERROR`
- `DATA_OR_IDENTITY_ERROR`
- `UNFORESEEABLE_EVENT`
- `MODEL_CALIBRATION_ERROR`

One observation can carry secondary labels, but the taxonomy must not be chosen to protect a favoured model.

## Continuous improvement loop

### 1. Capture before outcome

All research signals, analyst decisions, portfolio weights and overrides must be immutable before their evaluation window opens.

### 2. Score every forecast

At maturity report:

- benchmark-relative return;
- information coefficient where applicable;
- hit rate;
- Brier score / calibration buckets for probabilities;
- quantile coverage for P10/P50/P90 forecasts;
- maximum adverse and favourable excursion;
- time under water;
- transaction-cost-adjusted value added;
- concentration and leave-one-out sensitivity.

### 3. Maintain champion and challengers

The current production paper rule is the **champion**. New models run in shadow mode as **challengers**.

A challenger may replace the champion only after preregistered, independent evidence. Never promote a model because it explains the most recent loss.

### 4. Review on an evidence clock, not an emotion clock

Do not retune models daily.

Suggested model-review checkpoints:

- after a preregistered minimum number of matured prospective decisions;
- quarterly structural review;
- immediately only for source corruption, implementation defects or invalid assumptions that make the experiment uninterpretable.

### 5. Track model correlation

Two individually good signals that make the same decisions are not two independent edges. Track correlation between H013, H021 and future signals before assigning ensemble weight.

### 6. Calibrate confidence

A model saying `70%` must win approximately 70% of comparable observations over a sufficiently large series. If not, recalibrate or stop reporting probabilities.

### 7. Preserve failures

Every rejected variant remains in the registry. Failed ideas count toward multiple-testing interpretation.

## LLM role

LLMs are research assistants, not the unrestricted portfolio optimizer.

Good uses:

- source discovery and contradiction checks;
- filing/call extraction with provenance;
- scenario generation;
- thesis red-teaming;
- catalyst/invalidation extraction;
- producing analyst memos from frozen structured evidence;
- identifying missing questions.

Deterministic code should own:

- point-in-time joins;
- feature calculation;
- score calculation;
- portfolio weights;
- risk limits;
- backtests;
- performance attribution;
- promotion gates.

Any LLM discretionary override must be frozen as a separate decision so its incremental value can be measured.

## Operating cadence

### Daily after market close

- ingest completed prices;
- run H020;
- update portfolio marks;
- process material company events;
- identify state transitions only;
- run risk checks.

### Weekly

- capture H021 consensus data;
- refresh company watchlist catalysts;
- analyst review of meaningful thesis changes;
- portfolio/risk attribution snapshot.

### Monthly

- run H013 prospective process at its frozen decision dates;
- performance and attribution review;
- forecast calibration dashboard;
- sector/theme concentration review;
- review opportunity cost of cash and rejected candidates.

### Quarterly

- earnings-season company thesis refresh;
- model champion/challenger review using only matured evidence;
- portfolio-policy review;
- research-roadmap prioritization.

## Promotion path

```text
Idea
 -> historical/source feasibility
 -> frozen historical challenge
 -> prospective shadow signal
 -> paper-fund eligibility
 -> sustained prospective portfolio evidence
 -> tiny live-capital policy
 -> gradual risk-budget increase
```

No stage may be skipped because recent paper returns are attractive.

## Definition of success

The end product is not a system that is always right.

It is a system that can demonstrate, prospectively and after costs:

- measurable forecasting skill;
- positive benchmark-relative value added;
- calibrated uncertainty;
- controlled drawdowns;
- diversification of independent edges;
- explainable attribution;
- stable behaviour when individual hypotheses fail;
- disciplined capital allocation.

That is the standard for becoming a credible market analyst and eventually a fund-management process.
