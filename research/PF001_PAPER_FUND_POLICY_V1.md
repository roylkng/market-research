# PF001 — Equal-unit prospective paper fund v1

Status: **PROPOSED / FREEZE BEFORE PORTFOLIO OUTCOMES**
Created: 2026-09-12
Live capital: **DISABLED**

## Objective

Measure whether the project's research and entry-timing process can create benchmark-relative value in an actual capital-constrained portfolio, rather than only in isolated stock observations.

PF001 is intentionally simple. It is the portfolio-management baseline that future sizing/optimization policies must beat.

PF001 is not a new stock-selection hypothesis. It consumes only signals that have already passed their own applicable research gates.

## Start boundary

PF001 prospective validation starts with decisions frozen **after this policy is committed**.

Companies that materially influenced the design discussion before this freeze, including ARVIND, WABAG, TRANSRAILL, GENUSPOWER and other current H020 development names, may be tracked in a separate development book but may not be used to claim PF001 validation success from their already-observed setup.

## Mandate

- Indian listed equities only.
- Long-only.
- Unlevered.
- No derivatives.
- No short selling.
- Cash is permitted and its opportunity cost is measured.
- No broker execution or live orders.

## Benchmark

Preferred primary benchmark: **NIFTY 500 TRI**, if an official or otherwise source-verified point-in-time total-return series is available for the entire PF001 observation period.

If TRI cannot be sourced consistently, use the NIFTY 500 price index as an explicitly inferior fallback and report the dividend mismatch. Do not silently compare a price-only portfolio calculation with a total-return benchmark or vice versa.

## Capital

Initial virtual NAV: **INR 1,000,000**.

A new eligible position receives a fixed **5% of contemporaneous portfolio NAV** at entry.

Rationale: fixed units avoid fitting position size to recently discussed winners and make selection/timing attribution observable. Smarter sizing belongs to a later challenger policy.

## Position constraints

- initial target weight: 5% NAV;
- no pyramiding in PF001-v1;
- maximum 20 concurrent positions from unit sizing;
- maximum 25% contemporaneous cost-basis exposure to one sector;
- if a new position would breach the sector cap, record `RISK_REJECTED_SECTOR_CAP` and keep the capital in cash;
- no discretionary increase because a position is winning;
- no averaging down.

Weight drift from price movement is allowed. Any later rebalance rule is a new policy version.

## Eligibility

A position may enter PF001 only when a frozen analyst decision object says `PORTFOLIO_ELIGIBLE` and the associated research state is not blocked by unresolved data leakage or source-integrity issues.

Until the combined analyst object is implemented, an interim PF001 candidate must at minimum have:

1. an explicit business/valuation thesis with timestamped evidence;
2. no known research-layer rejection that directly contradicts the thesis;
3. an H020 state that permits a paper entry;
4. a recorded benchmark, horizon, catalyst and invalidation condition;
5. no risk-layer veto.

H021 absence before its first valid revision window is `MISSING_EXPECTATION_SIGNAL`, not a negative signal and not a positive confirmation.

## Execution convention

The decision is frozen after a completed market session.

Entry uses the **next completed NSE session's first executable open proxy** from the frozen market-data source. If the security cannot execute under the source/exchange constraints, record a missed trade. Do not fill at the prior close or use the day's low/high retrospectively.

No same-session retrospective entries are permitted.

## Friction

PF001-v1 records both gross and friction-adjusted returns.

Initial frozen all-in research friction assumption: **0.50% round trip** per completed position, consistent with the existing prospective H013 research convention.

Also report raw turnover so a later India-specific fee/tax/slippage model can challenge the simple friction assumption without rewriting PF001-v1.

## Holding and exit convention

PF001-v1 uses a standardized **60 completed-session holding horizon** as its primary evaluation horizon so portfolio results can be compared with the project's medium-horizon research experiments.

A position exits earlier only for a prospectively defined hard invalidation that existed at entry, such as:

- identity/source error invalidating the decision;
- corporate event that makes the security non-investable under the policy;
- analyst thesis condition explicitly marked as `HARD_INVALIDATION` before entry.

PF001-v1 does not introduce an optimized stop-loss, trailing stop or profit target after seeing outcomes. Those are separate portfolio-policy challengers.

Record 20-session checkpoints but do not force an exit at 20 sessions.

## Cash

Unused capital remains cash.

Report:

- average cash weight;
- return contribution from cash assumption;
- number of signals rejected by capacity/sector constraints;
- benchmark opportunity cost of uninvested cash.

For v1, cash earns 0% unless a separately sourced and frozen cash-return convention is added before PF001 begins. This is conservative but must be disclosed.

## Required portfolio ledger

Every decision record must include:

- portfolio policy/version;
- decision timestamp;
- symbol/ISIN;
- sector;
- analyst-decision ID;
- H013/H019/H020/H021 state references where available;
- action: enter / reject / exit / mature;
- reason;
- target notional;
- executable entry convention;
- realized entry;
- holding-session count;
- current/exit value;
- gross return;
- friction-adjusted return;
- NIFTY 500 excess;
- maximum adverse excursion;
- maximum favourable excursion;
- invalidation events;
- source hashes/provenance.

## Counterfactual books

Maintain at least these shadow books from the same frozen eligible decisions:

### CF-A — immediate entry

Enter the eligible business thesis at the next session without applying H020 timing.

Purpose: measure H020's incremental timing value.

### CF-B — equal selection without portfolio constraints

Track every eligible signal independently at equal notional.

Purpose: measure the effect of capacity and sector constraints.

### CF-C — benchmark only

Equivalent starting NAV invested in the benchmark.

Purpose: measure whether active management adds value.

No counterfactual may influence the live paper-book decision after outcomes begin.

## Evaluation

Primary portfolio metrics after sufficient matured observations:

- annualized and cumulative benchmark-relative return;
- information ratio;
- maximum drawdown;
- volatility and downside volatility;
- hit rate of matured positions versus benchmark;
- mean/median position excess return;
- portfolio turnover;
- average cash weight;
- winner concentration;
- sector contribution;
- selection contribution;
- timing contribution versus CF-A;
- constraint/sizing contribution versus CF-B;
- cost drag;
- leave-one-name-out sensitivity.

Do not promote PF001 from a small number of attractive current trades.

## Future challengers

After PF001 has prospective evidence, later portfolio policies may challenge it with:

- volatility-scaled sizing;
- expected-alpha / forecast-confidence sizing;
- correlation-aware optimization;
- active-risk budgeting;
- sector-neutral or benchmark-aware active weights;
- dynamic cash exposure by regime;
- explicit stop/trailing-exit policies;
- multi-horizon sleeves.

Each challenger must be frozen before its comparison outcomes are opened.

## Promotion

PF001 is a paper-fund experiment only.

Any future live-capital policy requires a separate document specifying at minimum:

- acceptable loss and drawdown;
- live capital amount;
- broker/execution controls;
- position and sector limits;
- liquidity limits;
- taxation/cost model;
- kill switch;
- operational failure handling;
- human approval requirements.

PF001 itself never authorizes live capital.
