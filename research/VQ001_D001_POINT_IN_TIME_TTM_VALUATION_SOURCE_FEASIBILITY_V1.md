# VQ001-D001 Point-in-Time TTM Valuation Source Feasibility v1

Status: **FROZEN BEFORE SOURCE DIAGNOSTIC**
Frozen: 2026-10-04
Return outcomes opened: no
Portfolio eligibility: disabled
Live capital: disabled

## Objective

Determine whether official NSE financial filings, official NSE cash-market prices and
official NSE corporate-action records can reconstruct a small point-in-time history of
company valuation multiples for the frozen 100-company U001 universe.

VQ001-D001 is source feasibility only. It does not claim valuation alpha and it does
not rank companies for portfolio use.

## Frozen universe

Use exactly:

`research/prospective/universes/FY27-Q2-2026-09-06.json`

Expected SHA-256:

`cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb`

## Valuation measure

The primary source-feasibility multiple is a trailing-twelve-month P/E proxy:

`share_count = paid_up_equity_share_capital / face_value_per_share`

`market_cap = NSE_price * share_count`

`TTM_PAT = sum(total_profit for the latest four same-basis quarters)`

`TTM_PE_proxy = market_cap / TTM_PAT`

All monetary facts must be explicit INR filing facts. No share count, earnings or
corporate-action adjustment is inferred from a third-party data vendor.

The measure is called a proxy because paid-up equity share capital is used as the
issued-share-count source and because company-specific treasury/dilution nuances are
not reconstructed.

## Historical snapshot grid

Exactly four historical information snapshots are attempted:

1. quarter end 2025-09-30, TTM quarters:
   2024-12-31, 2025-03-31, 2025-06-30, 2025-09-30;
2. quarter end 2025-12-31, TTM quarters:
   2025-03-31, 2025-06-30, 2025-09-30, 2025-12-31;
3. quarter end 2026-03-31, TTM quarters:
   2025-06-30, 2025-09-30, 2025-12-31, 2026-03-31;
4. quarter end 2026-06-30, TTM quarters:
   2025-09-30, 2025-12-31, 2026-03-31, 2026-06-30.

The current point-in-time snapshot is fixed to **2026-10-01**, the latest completed NSE
session available when this protocol was frozen. It reuses the 2026-06-30 TTM
fundamental denominator and latest 2026-06 filing share count.

## Filing selection

For every required quarter:

1. query official NSE Integrated Filing - Financials and legacy Financial Results
   discovery sources;
2. prefer a usable Integrated Filing candidate when present;
3. otherwise use the usable legacy candidate;
4. use the earliest official filing for that quarter/basis;
5. use one accounting basis for all four quarters in a snapshot;
6. prefer Consolidated when all four required quarters are available;
7. otherwise use Standalone when all four are available;
8. a same-timestamp multi-URL ambiguity fails closed;
9. all component filings must have been public no later than the latest-quarter filing
   used for that snapshot.

No later restatement may replace an earlier already-public filing.

## Issuer identity continuity

Quarterly profit facts may cross a verified issuer identity transition only under the
already-frozen FQ001 identity rules:

- same explicit ISIN, or
- an exact bridge in `research/fq001/fq001-isin-bridges-v1.json`.

No fuzzy company-name or ticker-only ISIN replacement is allowed.

## Share-count contract

The latest-quarter filing for a snapshot must expose:

- `PaidUpValueOfEquityShareCapital`;
- `FaceValueOfEquityShareCapital`.

Both must be finite and strictly positive.

For XBRL filings the monetary share-capital amount is treated as actual INR, consistent
with the existing NSE XBRL normalization contract.

Derived share count must be finite and strictly positive.

When `EquityShareCapital` is also present at the same period end, paid-up share capital
and equity share capital must agree within a small source-format tolerance of 0.1%.
A larger disagreement fails closed.

## Price timestamp

For each historical quarter snapshot:

- valuation session = the first official NSE EQ trading session strictly after the
  latest-quarter filing publication date;
- search is bounded to the next 10 calendar days;
- price = official NSE UDiFF **close price** for that session;
- market identity is matched by exact filing ISIN rather than ticker text.

This uses a completed post-publication price and avoids claiming the filing was tradable
before it became public.

For the current snapshot, use the official 2026-10-01 NSE UDiFF close.

## Corporate-action safety

Share count is period-end accounting data. Therefore any share-changing action between
the latest quarter end and valuation session can make raw share count and raw price
incompatible.

For each snapshot, query official NSE corporate actions from the day after quarter end
through the valuation session.

Any split, sub-division, consolidation, bonus, rights issue, or unresolved share-changing
action blocks that snapshot.

No price or share-count back-adjustment is introduced in D001.

## Eligibility

A valuation snapshot exists only when:

- all four same-basis quarterly PAT values are explicit and finite;
- TTM PAT is strictly positive;
- latest filing share count is valid;
- no relevant corporate action contaminates the price/share-count basis;
- exact filing ISIN appears in the official price file;
- resulting market cap and TTM P/E are finite and strictly positive.

Missing values remain missing. No imputation or winsorization is allowed.

## Frozen feasibility thresholds

VQ001 may proceed to a separately frozen normalized-valuation score only if all are true:

1. at least 70 U001 companies have at least three valid historical valuation snapshots;
2. at least 60 U001 companies have all four historical snapshots;
3. each historical snapshot date has at least 70 valid companies;
4. at least 60 companies have a valid 2026-10-01 current valuation snapshot.

Thresholds may not be lowered after output inspection.

## Proposed next-stage normalized valuation

If D001 passes, a later S001 protocol may compute for each company with all required
history:

- current TTM P/E;
- median of the four historical point-in-time TTM P/E values;
- current / historical-median multiple;
- current percentile within the four historical values plus the current observation;
- optional cross-sectional valuation context.

No scoring formula, weight, buy/sell rule or return model is frozen in D001.

## Scientific boundary

D001 opens no stock-return outcome and fits no predictive model.

Passing D001 establishes only that point-in-time historical valuation can be
reconstructed reproducibly. It does not establish that cheap or expensive valuations
predict future returns. PF001 and live capital remain disabled.
