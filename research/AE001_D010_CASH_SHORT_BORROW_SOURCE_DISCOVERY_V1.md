# AE001 D010 Cash Short/Borrow Flow Source Discovery v1

Status: FROZEN BEFORE SOURCE PROBE
Frozen: 2026-10-01
Live capital: DISABLED

## Objective

Discover and validate the exact official NSE archive locations and row schemas
for two new cash-market positioning sources:

1. CM Short Selling daily report;
2. SLB Daily Open Positions report.

D010-P0 is source discovery only. It opens no stock-return outcomes, fits no
model and creates no alpha claim.

## Motivation

The current alpha factory has:

- a useful price/liquidity/delivery core;
- a historically strong and orthogonal stock-futures delta;
- failed incremental options, fundamentals and simple announcement-taxonomy
  feature families.

Short-selling and securities-lending/borrowing pressure are a genuinely new
positioning family and are not currently implemented in MarketLab.

## Official source families

NSE's official reports pages list:

- CM - Short Selling;
- SLB - Daily Open Positions.

The human-facing report pages do not expose stable static download URLs in the
server-rendered HTML. D010-P0 therefore probes a frozen finite set of official
nsearchives.nseindia.com URL patterns.

No non-NSE source is eligible.

## Frozen probe sessions

- 2026-09-25
- 2026-09-24
- 2025-09-01

These dates are source/schema probes only.

## Frozen short-selling candidate URL patterns

For DDMMYYYY:

1. https://nsearchives.nseindia.com/products/content/shortselling_DDMMYYYY.csv
2. https://nsearchives.nseindia.com/content/equities/shortselling_DDMMYYYY.csv
3. https://nsearchives.nseindia.com/content/cm/shortselling_DDMMYYYY.csv
4. https://nsearchives.nseindia.com/content/shortselling/shortselling_DDMMYYYY.csv

## Frozen SLB open-position candidate URL patterns

For DDMMYYYY:

1. https://nsearchives.nseindia.com/content/slbs/slb_openpos_DDMMYYYY.csv
2. https://nsearchives.nseindia.com/content/slb/slb_openpos_DDMMYYYY.csv
3. https://nsearchives.nseindia.com/products/content/slb_openpos_DDMMYYYY.csv
4. https://nsearchives.nseindia.com/content/SLBS/slb_openpos_DDMMYYYY.csv

## Discovery acceptance

A candidate response is READY only when:

- HTTP status is 200;
- body is non-empty;
- body is not HTML;
- CSV parsing succeeds;
- at least one header field exists;
- exact raw SHA-256 is retained.

For each candidate D010 records:

- URL;
- status code;
- byte length;
- content type;
- raw SHA-256 when present;
- CSV header;
- data-row count;
- parser status.

## Promotion to D010-P1

A source family may proceed to historical coverage/identity audit only if one
single URL pattern is READY on all three frozen probe sessions.

D010-P0 does not decide predictive usefulness.

## Future identity contract

If promoted:

- source symbol must be rebound to the same-session official NSE UDiFF EQ
  symbol+ISIN identity;
- symbol-only carry-forward is prohibited;
- sparse source absence is not equivalent to zero unless the file itself is
  successfully captured for that session.

## Point-in-time boundary

Historical archive availability does not establish publication time.

Any future alpha trial requires a separately frozen prospective source-timing
protocol before prospective claims are allowed.

No live-capital implication.
