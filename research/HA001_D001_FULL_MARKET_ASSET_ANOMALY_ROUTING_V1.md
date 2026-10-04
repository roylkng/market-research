# HA001-D001 Full-Market Asset-Anomaly Routing Plane v1

Status: **FROZEN BEFORE MATERIALIZATION**
Frozen: 2026-10-04
Return outcomes opened: no
Portfolio eligibility: disabled
Live capital: disabled

## Purpose

Use the passed FA001-D002 official financial fact plane to identify balance-sheet
structures worth deep research across the full 2,319-name NSE universe.

HA001-D001 is **not** an intrinsic-value model. It does not use market capitalization,
stock returns, target prices, or analyst estimates.

## Frozen input

Use exactly FA001-D002-v1:

- run `37213394690`;
- artifact `11306919543`;
- panel SHA-256
  `cb8a408b6904799750a5aa08210f909ae8b285005273b5588fb1f8b7a6019124`.

Only annual FY26 READY facts with unitRef exactly `INR` enter arithmetic.

Missing facts remain missing.

## Deterministic derived quantities

When all required facts are READY:

`investments = current_investments + noncurrent_investments`

`borrowings = current_borrowings + noncurrent_borrowings`

`net_financial_assets = cash + investments - borrowings`

`tangible_equity = total_equity - goodwill - other_intangibles`

`working_capital_assets = inventories + trade_receivables`

No unreported bank balance, land value, subsidiary value, lease liability, or contingent
asset is imputed.

## Frozen opportunity flags

### LIQUID_ASSET_HEAVY

Require positive total equity and:

`net_financial_assets / total_equity >= 0.50`

### INVESTMENT_HOLDING_HEAVY

Require positive total assets and:

`investments / total_assets >= 0.20`

### INVESTMENT_PROPERTY_MATERIAL

Require positive total equity and READY investment property:

`investment_property / total_equity >= 0.10`

### CWIP_CAPACITY_INFLECTION

Require positive PPE and READY capital work in progress:

`capital_work_in_progress / PPE >= 0.25`

These thresholds are research-routing thresholds only.

## Frozen caution flags

### INTANGIBLE_HEAVY_CAUTION

Require positive total equity:

`(goodwill + other_intangibles) / total_equity >= 0.50`

### WORKING_CAPITAL_HEAVY_CAUTION

Require positive total assets:

`(inventories + trade_receivables) / total_assets >= 0.40`

## Business-model boundary

The same accounting structure can mean very different things in a bank, NBFC, holding
company, manufacturer, real-estate company, or operating conglomerate.

Therefore every opportunity flag carries:

`business_model_context_required = true`

HA001-D001 does not infer that investments or cash are distributable, surplus, hidden,
or mispriced.

## Output

For each of 2,319 identities retain:

- READY derived ratios where available;
- opportunity flags;
- caution flags;
- exact input fact values/statuses;
- U001 overlap;
- whether any opportunity flag fired.

No score is produced.

## Feasibility gates

D001 passes only if:

1. all 2,319 identities are accounted for exactly once;
2. >=60% have computable net-financial-assets/equity;
3. >=60% have computable investments/assets;
4. >=50% have computable CWIP/PPE;
5. every emitted ratio uses READY INR facts only;
6. no price, return, LLM, analyst or portfolio outcome enters flagging.

Passing permits deterministic joins to GF001 governance, SS001 liquidity, SS002 event
evidence and LLM deep research.

It does not authorize portfolio eligibility or live capital.
