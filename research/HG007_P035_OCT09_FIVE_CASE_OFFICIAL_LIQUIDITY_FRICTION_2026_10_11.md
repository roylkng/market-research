# HG007-P035: Five Hidden-Gem Stocks, One Official NSE Session's Liquidity Friction

As-of original exchange source: **9 October 2026**.
This is a pre-next-open (12 October) source-only capacity *diagnostic*.
It is **not** an execution model, alpha trial, recommendation, or estimate
of the days needed to buy/sell any company.

## Why

For a smaller-cap hidden gem, 50% theoretical market re-rating means little
if the position cannot be entered or exited without substantial price impact.

The original, exact NSE Oct9 CM UDiFF ZIP was saved through SS002-P007
and cross-validated for five HG005 issuers under HG007-P034:

- Source SHA-256: 8adbb3410c8cf4372290484a9b1798490ef279d30fc2439c93f082cc20ed198c
- P034 source status: original NSE exchange ZIP hash, exact EQ series and
  original symbol / ISIN / close / day traded value.
- Original source **not** Yahoo, quote-panel inference, future source,
  executed order report or market depth.

P035 rechecks the exact original source, including original five symbol/ISIN
records, closes, high/low, volume, traded INR and executed trade counts.
It also verifies daily traded value divided by volume lies inside the
source-reported day's high/low range.

## Source-verified market facts

| Stock | 9 Oct close, INR | One day's NSE traded INR crore | Primary concern |
|---|---:|---:|---|
| ANANTRAJ | 570.75 | 83.44 | Not necessarily repeatable around legal scheme milestones |
| DEVX | 39.92 | **0.6124** | Extremely small observed turnover relative to ₹1cr hypothetical ticket |
| INOXGREEN | 128.92 | 943.19 | One volatile post-news trading day may grossly overstate ordinary capacity |
| NPST | 1752.20 | 14.31 | One-day record is insufficient to establish attainable ticket size |
| SAMBHV | 160.41 | 41.55 | Future share warrants/financing could change turnover and capital structure |

These are one source-day observations, not a sorted investment return
ranking. No conclusion about persistent market liquidity follows.

## Illustrative participation arithmetic, not execution capacity

For a fixed participation fraction *p* of the day's total reported traded
value, define the single-session reference amount:

    source_day_value_fraction = p × NSE total_traded_value

P035 displays p = 1% and 5%, applied to hypothetical order sizes
₹1 lakh, ₹10 lakh and ₹1 crore. Its quotient is simply:

    ticket / source_day_value_fraction

It is **NOT** a prediction of how many days are required: the
fraction may not be achievable, bid/ask depth is unknown, available
seller inventory may be absent, reported flow can be one-off,
and actual orders cause nonlinear spread/slippage/market impact.

DEVX's 9 Oct source day was just ₹61.24 lakh total executed value.
At the illustrative 1% turnover participation:

- source-day fraction: about ₹61,241, not a promised executable amount.
- ₹10 lakh ticket / ₹61,241 = ~16.33 one-day-turnover-fraction units.
- It would be **incorrect** to claim this means execution in 17 sessions,
  even with unlimited funds or repeated order placement.

At 5%, the same source day's value fraction is ~₹3.06 lakh. Again,
there is no guarantee of a fill or any repeatable volume.

INOXGREEN's ₹943.19 crore turnover is very large on the same source
day, but its daily high-low range (₹112–135 around ₹128.92 close)
signals an exceptional range. P035 does not infer that this day's
liquidity is typical or repeatable.

## What remains before investment-scale claims

At least 20 completed official sessions of same-basis NSE turnover,
with corporate-action/holiday and abnormal-event treatment, are needed
before describing a median, lower-quartile or minimum observed volume.
For tradable liquidity, separately obtain bid-ask quotes/depth and
order type/session/time-of-day conditions, plus commission, STT,
impact cost and exchange restrictions. Do not use backfilled future
volumes to present earlier market capacity.

Neither an official close nor one-day turnover proves executable
entry at that price. No broker interaction or capital deployment is
authorized.

## Deterministic replay

- Model: src/marketlab/hg007_liquidity_friction.py
- CLI: scripts/build_hg007_liquidity_friction.py
- Tests: tests/test_hg007_liquidity_friction.py
- CI: .github/workflows/hg007-five-case-liquidity-friction.yml
- Append-only result: research/hg007/hg007-p035-five-case-liquidity-friction-v1.json

The exact original Oct9 ZIP and P034 Git blob must be unchanged.
All original selection, event-stage evidence, expected-return and
portfolio eligibility gates remain **unchanged and disabled**.
