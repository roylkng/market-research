# AE001 D005 Stock-Options Source Feasibility v1

Status: FROZEN BEFORE SOURCE AUDIT
Frozen: 2026-10-01
Live capital: DISABLED

## Objective

Determine whether official NSE FO UDiFF archives contain a sufficiently broad,
structurally stable stock-options surface to justify a separately frozen options
alpha trial.

D005 is source-only. It does not create labels, fit a model, calculate returns or
open any alpha outcome.

## Historical window

2025-09-01 through 2026-09-25.

The completed NSE session calendar is taken from the existing official cash
market-panel construction.

## Official source

NSE F&O UDiFF Common Bhavcopy Final:

BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip

Relevant fields:

- FinInstrmTp;
- TckrSymb;
- XpryDt / FininstrmActlXpryDt;
- StrkPric;
- OptnTp;
- SttlmPric;
- PrvsClsgPric;
- UndrlygPric;
- OpnIntrst;
- ChngInOpnIntrst;
- TtlTradgVol;
- TtlTrfVal;
- TtlNbOfTxsExctd;
- NewBrdLotQty.

Stock-option instrument code:

STO

Option types:

CE / PE.

## Identity

FO option rows are rebound on the same session to the exact CM EQ symbol+ISIN
identity from the official cash panel.

No symbol-only historical identity is accepted beyond that same-session join.

## Frozen structural surface rule

For one symbol/session:

1. retain valid STO contracts;
2. exclude contracts whose actual expiry is <= trade date;
3. select the earliest remaining expiry as front expiry;
4. require both CE and PE rows;
5. require at least three distinct strikes present in BOTH CE and PE;
6. require cash close > 0;
7. require at least one paired strike whose absolute moneyness versus cash close
   is <= 10%;
8. require positive strike, settlement price and board lot;
9. require non-negative OI and volume;
10. duplicate symbol/expiry/strike/option-type contracts fail closed for that
    symbol/session.

D005 does not require or compute implied volatility.

## Frozen viability gates

A future options alpha trial is permitted only if ALL are true:

- parser-rejected session count = 0;
- READY source sessions >= 200;
- median usable option-surface symbols per READY session >= 100;
- 10th percentile usable option-surface symbols per READY session >= 75.

These are source-feasibility gates only.

Passing D005 does not imply options alpha.

## Outputs

D005 reports:

- session counts;
- STO row counts;
- distinct stock-option symbols;
- exact-EQ mapped symbols;
- usable front-surface symbols;
- exclusion reasons;
- per-session usable counts;
- median, p10, p90, min and max usable symbols;
- source hashes.

Exact raw FO archives are retained content-addressed in the workflow artifact.

## Non-goals

- no return labels;
- no options alpha features;
- no model fitting;
- no prospective claim;
- no live-capital claim.
