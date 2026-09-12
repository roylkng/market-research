# PF001 attribution contract v1

Status: **FROZEN BEFORE PF001 PROSPECTIVE-VALIDATION OUTCOMES**

Created: 2026-09-12

Live capital: **DISABLED**

This contract defines the first deterministic performance-attribution layer for PF001. It does not change stock selection, H020 timing, PF001 entry sizing, sector limits, holding period, or exits.

## Objective

Answer, separately and reproducibly:

1. Did the capital-constrained paper fund beat its benchmark?
2. Did individual completed positions beat the benchmark over exactly the same executable interval?
3. How much return was lost to the frozen PF001 friction assumption?
4. How much capital remained in cash while the benchmark moved?
5. What drawdown did the portfolio experience?

Timing and constraint counterfactuals remain separate shadow-book experiments. This attribution layer must not infer them from incomplete timestamps.

## Benchmark hierarchy

Preferred benchmark: **NIFTY 500 TRI**.

Allowed benchmark basis values:

- `TOTAL_RETURN`
- `PRICE`

If a verified TRI observation cannot be supplied for a session, a NIFTY 500 price-index series may be used only if the entire continuous attribution segment is explicitly labelled `PRICE`.

Do not splice TRI and price-index observations inside one attribution segment.

When `PRICE` is used, set `dividend_mismatch = true` because PF001 equity returns can include distributions/corporate-action economics that a price-only benchmark does not fully represent.

Every attribution state must retain:

- benchmark name;
- basis;
- source identity/reference;
- first benchmark session;
- initial benchmark open;
- latest benchmark close.

## Portfolio benchmark convention

The benchmark-only shadow portfolio starts with the same PF001 initial NAV, INR 1,000,000.

Its inception price is the **benchmark open on the first completed NSE session processed by the attribution ledger after this contract is active**.

Its current value is:

`initial_nav * benchmark_close[t] / benchmark_open[first_session]`

This benchmark remains continuously invested. Therefore PF001 cash is intentionally measured against the opportunity cost of market exposure rather than being granted a zero-risk exemption.

## Portfolio active return

For every processed session calculate:

- cumulative gross PF001 return;
- cumulative friction-adjusted PF001 return;
- cumulative benchmark return;
- gross active return in percentage points;
- net active return in percentage points;
- friction drag in percentage points;
- net cash weight;
- gross and net drawdown from prior NAV peak.

Primary portfolio comparison uses **net PF001 return minus benchmark return**.

Gross attribution remains visible so the cost of the frozen friction assumption is explicit.

## Position-level benchmark convention

For every PF001 fill:

- benchmark entry = benchmark **open** from the same entry session;
- benchmark exit = benchmark **close** from the actual PF001 exit session;
- benchmark position return = `exit_close / entry_open - 1`.

This intentionally mirrors PF001's stock convention: next-session open entry and completed-session close exit.

At the 20-session checkpoint use the same position benchmark entry open and the checkpoint session benchmark close.

For every closed position calculate:

- stock gross return;
- stock friction-adjusted return;
- benchmark return over the identical interval;
- gross excess return in percentage points;
- net excess return in percentage points;
- whether the net position return beat the benchmark.

Arithmetic return difference is the project's primary excess-return convention so it remains comparable with H009/H013-style stock-minus-benchmark results.

## Daily continuity

Attribution must be advanced for every completed PF001 market session.

If a PF001 entry or exit event appears for an earlier session that the attribution ledger did not process, fail closed. Do not fetch a later historical value and pretend it was captured contemporaneously inside the ledger.

Missing security marks are handled by PF001's implementation contract. The benchmark itself must have a valid positive open/close for every attribution session; otherwise that attribution session is `BLOCKED_BENCHMARK_DATA` and must not be silently interpolated.

## Drawdown

Track gross and net NAV peaks independently.

Session drawdown:

`nav[t] / peak_nav_through_t - 1`

Store maximum drawdown as the most negative observed percentage.

No intraday portfolio drawdown estimate is claimed from daily closes.

## Information ratio

After at least 20 attribution sessions, an exploratory information ratio may be reported from daily active returns:

`mean(daily_portfolio_return - daily_benchmark_return) / std(...) * sqrt(252)`

Use sample standard deviation. Report `null` with fewer than 20 observations or zero active-return variance.

This statistic is descriptive until a preregistered PF001 promotion gate defines how much evidence is sufficient.

## Cash

Cash earns 0% in PF001-v1.

Report per session:

`cash_weight = cash_net / net_nav`

and the arithmetic average across attribution sessions.

The benchmark-only shadow book provides the overall opportunity-cost comparison. A more granular decomposition of cash drag versus selection requires a separately frozen shadow-book policy and must not be reverse engineered after outcomes.

## Cost drag

At portfolio level:

`cost_drag_pp = (gross_portfolio_return - net_portfolio_return) * 100`

At position level, retain both gross and friction-adjusted stock returns.

Do not substitute a later tax/slippage model into PF001-v1 history. A more realistic India cost model is a challenger.

## Explicitly deferred attribution

### Timing contribution / CF-A

PF001 policy requires a counterfactual that enters an otherwise eligible business thesis without H020 timing.

The current Analyst Decision Object does not yet provide a machine-verifiable timestamp for the moment a thesis became **selection-eligible before H020**. Therefore CF-A is **BLOCKED_BY_SELECTION_TIMESTAMP_CONTRACT** in attribution-v1.

Do not infer this timestamp from later `PORTFOLIO_ELIGIBLE` decisions, historical charts, or narrative memory.

A later contract must create an immutable pre-H020 selection event before CF-A can be evaluated legitimately.

### Constraint contribution / CF-B

The equal-selection unconstrained book will be implemented as a separately frozen shadow portfolio that consumes the same post-freeze analyst decisions while ignoring PF001 capacity/sector rejections.

It is not part of this first attribution engine so its accounting conventions can be frozen independently before any PF001 constraint rejection outcome is opened.

## Required summaries

At any point the attribution report should expose:

- attribution session count;
- gross and net PF001 cumulative return;
- benchmark cumulative return;
- gross and net active return;
- cost drag;
- current and average cash weight;
- maximum gross/net drawdown;
- closed-position count;
- mean/median position gross excess;
- mean/median position net excess;
- net benchmark beat rate;
- exploratory information ratio when eligible;
- benchmark basis and dividend-mismatch flag;
- blocked/deferred attribution components.

## Scientific boundary

This contract may measure already-frozen PF001 decisions once they occur. It may not change those decisions.

Attribution results cannot be used to rewrite PF001-v1 history, move entry timestamps, remove losing positions, change the benchmark retrospectively, or relabel development-book trades as prospective validation.
