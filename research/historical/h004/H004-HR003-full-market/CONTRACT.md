# H004-HR003 full-market denominator contract

Status: **FROZEN BEFORE OUTPUT INSPECTION**  
Live capital: **NO**

Purpose: measure the full liquid-market opportunity set that H004 ultimately has to recall, rather than conditioning evaluation on companies that filed results.

## Window

- decision snapshots: 2025-10-01 through 2026-07-31
- price history: 2025-05-01 through 2026-08-31
- official market source: NSE UDiFF daily bhavcopy
- design-set week 2026-08-31 through 2026-09-07 is outside the replay window

## Primary universe

At each daily close, a symbol is eligible only when:

- NSE EQ-series common stock row is present,
- at least 60 prior trading observations exist for the symbol,
- median traded value over the prior 20 symbol sessions is at least INR 2 crore.

Discovery-tier observations use INR 25 lakh to < INR 2 crore and are reported separately.

## Pre-momentum opportunity day

A daily snapshot is pre-momentum eligible when:

- 1-session return < 8%,
- 5-session return < 10%,
- 20-session return < 20%.

The forward opportunity label uses an entry proxy at the next available session open. A day is a latent explosive opportunity when the maximum high over the following 20 symbol sessions is at least 25% above that next-session open.

## Episode collapse

The full-market denominator is **episodes**, not repeated overlapping positive days.

For each symbol:

1. take the first pre-momentum opportunity day whose next-open forward window reaches +25%,
2. record the first future session whose high reaches +25% from that entry,
3. suppress additional positive opportunity days for that symbol through the recorded hit session,
4. allow a new episode only after the previous hit session and only if the frozen pre-momentum conditions are again satisfied.

This produces one denominator unit for one distinct latent explosive run rather than counting the same run many times.

## Momentum-only baseline

The baseline has **no accounting, filing, catalyst, valuation, sector, management or news information**.

At each primary-universe daily close, candidates require:

- 5-session return > 0%,
- 20-session return > 0%,
- current volume / prior-20-session median volume >= 1.0,
- current session is not a flat positive circuit proxy (`high == low == close` with daily return >=4.9%).

The frozen ranking score is the equal-weight mean of that day's cross-sectional percentile ranks of:

1. 5-session return,
2. 20-session return,
3. volume / prior-20-session median volume.

No future information enters the score.

Predeclared signal budgets are top 1, 2, 3, 5 and 10 candidates per trading day. They are all reported. When H004 Stage-2 signal count is known, the baseline comparison uses the predeclared budget whose total signal count is closest to H004, without choosing based on returns.

Baseline entry is next-session open. Baseline precision is the fraction of entries whose maximum high over the next 20 symbol sessions reaches +25%.

Episode recall counts an episode as recalled when at least one baseline signal for the same symbol occurs from the episode start snapshot through the session before the first +25% hit. The earliest such signal is used for lead-time reporting.

## Outputs

Required:

- primary and discovery episode counts,
- episodes by quarter and symbol,
- top-mover concentration,
- momentum baseline precision at each frozen signal budget,
- momentum baseline episode recall at each budget,
- median lead time before +25%,
- median 20-session max and close returns for baseline entries.

This reconstruction is not out-of-sample validation. The contract may not be modified after output inspection to improve H004 or baseline statistics on the same window.
