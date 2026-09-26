# Alpha Factory implementation plan v1

Status: IMPLEMENTATION STARTED
Created: 2026-09-26
Scope: AE001 / AB001 / RM001 / TC001 / PO001
Live capital: DISABLED

## Objective

Evolve MarketLab from a serial hypothesis laboratory into a point-in-time alpha factory that can:

1. ingest and retain market and company information without look-ahead;
2. produce reusable cross-sectional features for the investable NSE universe;
3. create multiple horizon-specific forecasts;
4. measure each alpha's out-of-sample information content and orthogonality;
5. combine only out-of-sample predictions;
6. construct portfolios under explicit risk, liquidity and cost constraints;
7. compare the resulting portfolio against simple frozen baselines;
8. preserve the existing H-series experiments as scientifically independent evidence.

This program does not authorize live capital.

## Architectural separation

Three tracks run concurrently.

### Track A: frozen scientific experiments

H002-H024 continue unchanged under their existing contracts.

Their canonical prospective ledgers are read-only inputs to AE001. AE001 may consume an already sealed
signal only when its actual information timestamp is known and precedes the AE001 decision cutoff.
AE001 must never write to, backdate, reinterpret, or tune an H-series observation.

### Track B: alpha factory

AE001 creates point-in-time feature panels, labels, model trials, and out-of-sample predictions.

The unit of research is not "one hypothesis". It is:

    (symbol, decision timestamp, feature vector, horizon)

All reusable features live behind a common contract and can be tested across models and horizons.

### Track C: portfolio and execution research

AB001 blends independent OOS alphas.
RM001 estimates risk.
TC001 estimates implementable trading cost.
PO001 converts expected returns into constrained target weights.

PF001 remains the simple equal-unit baseline that future portfolio policies must beat.

## Non-negotiable research invariants

1. No feature value may have a known-at timestamp after its decision cutoff.
2. Labels are stored separately from features and cannot be imported by feature builders.
3. Dynamic universe membership is reconstructed point in time.
4. Identity is symbol + ISIN, not symbol alone.
5. Train/validation/test splits are chronological and purged for overlapping labels.
6. Model selection uses only training/validation evidence. Final test windows remain untouched.
7. Every model/feature trial is logged, including failed trials.
8. In-sample predictions never enter the alpha library.
9. Frozen H-series scientific rules cannot be changed to improve AE001.
10. Portfolio simulation must include turnover and cost before a strategy is called useful.
11. Missing data remains missing. No retrospective repair may use future information.
12. Live-capital execution remains disabled.

## System architecture

    Official/public sources
            |
            v
    Content-addressed raw store
            |
            v
    Point-in-time normalized observations
            |
            +--------------------+
            |                    |
            v                    v
      Dynamic universe      Event ledgers
            |                    |
            +---------+----------+
                      v
               Feature builders
                      |
                      v
          AE001 feature snapshots
                      |
          +-----------+-----------+
          |                       |
          v                       v
      Label engine            Trial ledger
          |                       |
          +-----------+-----------+
                      v
             Walk-forward models
                      |
                      v
           OOS alpha prediction store
                      |
                      v
                 AB001 blender
                      |
          +-----------+-----------+
          |                       |
          v                       v
       RM001 risk             TC001 cost
          |                       |
          +-----------+-----------+
                      v
                 PO001 optimizer
                      |
                      v
              Paper execution/PnL
                      |
                      v
            attribution + monitoring

## Phase 0: preserve the existing laboratory

### Work

- Keep all H-series workflows and registries unchanged.
- Add an explicit namespace for alpha-factory artifacts.
- Require evidence-class metadata on every AE001 artifact.
- Keep all AE001 development outputs outside canonical H-series directories.
- Record every AE001 model trial in a machine-readable ledger.

### Definition of done

AE001 can be deleted without changing one byte of any H-series canonical prospective state.

## Phase 1: point-in-time feature contract

### Initial decision sleeve

Start with end-of-day medium-frequency research.

- feature session: completed NSE session D;
- decision cutoff: 18:30 Asia/Kolkata on D;
- earliest execution: next completed NSE session open;
- horizons: 1, 5, 20 and 60 completed holding sessions;
- primary benchmark: Nifty 500 price index;
- sector-relative labels are secondary when a point-in-time sector map exists.

Starting with EOD avoids making GitHub scheduling reliability part of the first alpha-model experiment.
Pre-open and event-time sleeves can be added later with their own contracts.

### Required feature-row identity

Each row contains:

- engine/version;
- session date;
- decision timestamp;
- symbol;
- ISIN;
- point-in-time industry/sector when available;
- dynamic-universe snapshot ID/hash;
- feature-definition-set hash;
- feature values;
- per-feature known-at timestamps;
- exact source references/hashes;
- snapshot hash;
- outcomes_attached=false.

### Initial feature families

#### Price and trend
- 1/3/5/10/20/60/120-session close momentum;
- market-relative and sector-relative momentum;
- distance from 20/60/252-session highs;
- overnight gap;
- open-to-close return;
- short-term reversal.

#### Volatility and liquidity
- 20/60-session realized volatility;
- downside volatility;
- high-low range where official fields exist;
- traded-value level and surprise;
- volume level and surprise;
- trade-count surprise;
- Amihud-style return/traded-value proxy;
- delivery percentage and delivery surprise where available.

#### Fundamental
- earnings yield;
- book-to-price;
- sales-to-enterprise-value where sourceable point in time;
- ROE/ROIC;
- gross profitability;
- margin level/change;
- leverage;
- accrual/cash-conversion proxies;
- sales/EPS growth and acceleration.

#### Expectations
- 1w/1m/3m EPS revision;
- analyst-count change;
- dispersion;
- breadth of upgrades/downgrades;
- revision acceleration;
- post-earnings revision interaction.

#### Corporate/event
- announcement category;
- event novelty;
- quantified commitment;
- guidance delta;
- order/capex/regulatory/management-change flags;
- time since event;
- event count/intensity.

#### Ownership/informed capital
- sealed H024 binary event;
- insider purchase/sale descriptors as separate AE001 exploratory features;
- mutual-fund/institutional ownership change;
- promoter holding/pledge change.

#### Derivatives and flows
- futures OI change/acceleration;
- futures basis;
- participant OI;
- FII derivative positioning;
- option IV/skew/OI features where reliable data is available;
- bulk/block/short-selling features.

### Phase 1 implementation order

1. machine-readable feature definition registry;
2. point-in-time row validator;
3. dynamic universe builder;
4. official NSE daily market panel;
5. price/volume feature pack;
6. feature snapshot writer/verifier;
7. leakage tests.

### Definition of done

For a chosen historical session, MarketLab can rebuild the same feature snapshot byte-for-byte using only
information known by the declared cutoff, and a deliberate future-timestamp injection fails closed.

## Phase 2: labels and walk-forward dataset

### Label contract

For each feature row and horizon h:

- entry = next completed NSE session open after the decision session;
- exit = close of holding session h, with entry session counting as 1;
- raw stock return;
- Nifty 500 return over identical open-to-close interval;
- stock minus Nifty 500 excess return;
- sector-relative return when point-in-time mapping exists;
- outcome/source status;
- corporate-action status;
- exact evidence hashes.

### Split contract

Never use random row splits.

Use purged chronological walk-forward folds:

- training data precedes validation;
- every training label must mature before validation begins;
- final evaluation periods are untouched by feature/model selection;
- symbols may appear in multiple folds, dates may not leak forward;
- overlapping 60-session labels are purged at fold boundaries.

### Definition of done

A dataset manifest proves that every feature was known before the associated entry and that every training
label was fully mature before the next fold's decision period.

## Phase 3: baseline model laboratory

Start with deliberately different model classes.

1. cross-sectional linear/ridge baseline;
2. nonlinear tree model;
3. shallow neural model;
4. pairwise/ranking model;
5. simple single-factor baselines for comparison.

Do not start with an opaque deep sequence model.

### Model outputs

Every model emits only OOS records:

- model ID/version;
- training window;
- validation window;
- prediction timestamp;
- symbol/ISIN;
- horizon;
- raw prediction;
- cross-sectional percentile/rank;
- model artifact hash;
- feature snapshot hash.

### Required metrics

Per horizon:

- daily Spearman rank IC;
- IC mean, median and information ratio;
- top-decile excess return;
- bottom-decile excess return;
- top-minus-bottom spread;
- long-only top-decile excess;
- hit rate;
- turnover;
- 0/25/50 bps cost views initially;
- concentration by stock/sector/date;
- performance by year/regime/market-cap/liquidity bucket.

### Definition of done

A model is useful only if it improves OOS ranking or net long-only results over simple momentum/value/quality
baselines across more than one time slice.

## Phase 4: alpha library and orthogonality

Create one canonical OOS alpha store.

For every candidate alpha calculate:

- IC history;
- alpha-alpha prediction correlation;
- return-spread correlation;
- marginal IC after existing alphas;
- incremental top-decile spread;
- turnover overlap;
- sector/factor exposure overlap;
- stability and decay by horizon.

Reject "new" alphas that are merely renamed versions of existing momentum or size exposure unless they
provide incremental net performance.

### Multiple-testing controls

The trial ledger must support:

- number of attempted variants;
- Deflated Sharpe Ratio;
- false-discovery controls;
- parameter sensitivity;
- feature ablation;
- model ablation;
- leave-period-out and leave-sector-out tests.

## Phase 5: AB001 alpha blender

Blend only OOS model predictions.

Initial blender should be simple and auditable:

1. cross-sectionally standardize each alpha;
2. shrink weights for correlated alphas;
3. weight by trailing OOS efficacy using only evidence available before the rebalance;
4. cap any single alpha's contribution;
5. compare against equal-weight alpha blending.

Later challengers may use regime-conditional or nonlinear meta-models.

## Phase 6: RM001 risk model

Initial exposures:

- market beta;
- sector/industry;
- size;
- momentum;
- value;
- quality;
- volatility;
- liquidity.

Estimate factor covariance and idiosyncratic risk using only trailing observations.

The optimizer must be able to state whether an apparent alpha is actually a disguised factor bet.

## Phase 7: TC001 transaction-cost model

Replace the research-only flat 50 bps stress with a separate implementability model.

Components:

- statutory fees/taxes;
- half-spread proxy;
- volatility/liquidity slippage;
- participation-rate penalty;
- order-size/ADV impact;
- opening-auction/open-price special treatment.

Retain the existing 50 bps scenario as a comparable stress test.

## Phase 8: PO001 portfolio optimizer

Initial long-only objective:

    maximize expected_alpha
             - risk_penalty
             - turnover_penalty
             - trading_cost

Constraints:

- long only;
- no leverage;
- individual-name cap;
- sector active-weight cap;
- minimum liquidity;
- turnover budget;
- factor-exposure bounds;
- minimum number of holdings;
- optional cash.

Required comparisons:

- PF001 equal-unit;
- equal-weight top-decile;
- alpha-weighted without risk model;
- risk-aware optimizer;
- benchmark-only.

## Phase 9: deterministic prospective operation

GitHub remains the immutable evidence/CI layer, not the only clock for time-critical collection.

For pre-open/event-driven sleeves:

- deterministic scheduler outside GitHub cron;
- idempotent source collectors;
- content-addressed evidence;
- monotonic checkpoints;
- heartbeat and stale-data alarms;
- GitHub sealing after capture.

The 2026-09-25 H024 failure is the reference operational case this layer must prevent.

## Phase 10: paper portfolio challenger

Only after AE001 has OOS predictions and TC001/RM001 exist:

- freeze a new paper policy separate from PF001;
- run long-only;
- attribute selection, sizing, risk, cost and timing independently;
- compare against PF001 and Nifty 500;
- no live capital.

## Immediate implementation sequence

The first code milestone contains:

- this implementation plan;
- registry/ae001_alpha_engine.yaml;
- src/marketlab/alpha.py;
- tests/test_alpha.py.

Next commits should add:

1. NSE daily panel parser that retains all feature-relevant UDiFF fields;
2. dynamic investable-universe snapshots;
3. initial price/volume feature builders;
4. AE001 snapshot CLI;
5. historical panel materialization;
6. label engine;
7. walk-forward evaluator;
8. first linear baseline.

## Success criterion for the program

The program succeeds when we can answer, prospectively and after realistic costs:

> Given every stock we could actually have traded at time t, did our OOS ranking contain incremental
> information about future excess returns, and did the portfolio construction layer convert that information
> into diversified benchmark-relative P&L?

Anything weaker is a research artifact, not an investable alpha system.
