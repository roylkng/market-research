# EI001-S001 Full-Market Earnings-Inflection Research Router v1

Status: **FROZEN BEFORE COMPANY-LEVEL ROUTING OUTPUT IS OPENED**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Convert the passed EI001-D002 exact Q1 FY27 versus Q1 FY26 comparative fact plane into
a transparent earnings-inflection research-routing layer.

S001 is not an alpha model, target-price model or portfolio signal. It identifies
operating patterns worth deeper research.

## Frozen input

Use exactly EI001-D002-v1:

- workflow run: `37217767159`;
- artifact ID: `11308929215`;
- panel SHA-256:
  `14fdc99444ff8c1c62cbef58db91e51cb4cb6730c1259bccb98df979366272cd`;
- identities: 2,319;
- comparable revenue + PAT: 1,783.

No other quarter, analyst estimate, stock price, target price or future outcome enters
S001-v1.

## Frozen deterministic transforms

For a comparable fact pair:

`growth = current / prior - 1`

Growth is calculated only when the prior value is strictly positive.

For revenue-positive current and prior periods:

`PAT margin = PAT / revenue`

`PAT margin delta bps = 10,000 * (current PAT margin - prior PAT margin)`

`PBT margin delta bps` is calculated analogously.

No percentage growth is emitted from a zero or negative denominator.

## Frozen opportunity flags

### BROAD_GROWTH_LEVERAGE

Require:

- current and prior revenue > 0;
- current and prior PAT > 0;
- revenue growth >= 15%;
- PAT growth >= 30%;
- PAT margin expansion >= 100 bps.

### STRONG_GROWTH

Require:

- current and prior revenue > 0;
- current and prior PAT > 0;
- revenue growth >= 25%;
- PAT growth >= 25%.

Margin expansion is not required.

### MARGIN_INFLECTION

Require:

- current and prior revenue > 0;
- current and prior PAT > 0;
- revenue growth >= 5%;
- PAT margin expansion >= 300 bps.

### PROFIT_TURNAROUND

Require:

- prior PAT <= 0;
- current PAT > 0;
- current and prior revenue > 0;
- revenue growth >= -10%.

A turnaround flag does not infer that the profit is durable.

## Frozen caution flags

### LOW_BASE_PAT

Prior PAT is positive but prior PAT margin < 1%.

### REVENUE_CONTRACTION

Comparable revenue growth <= -10%.

### CURRENT_LOSS

Current PAT <= 0.

### BUSINESS_MODEL_CONTEXT_REQUIRED

Always true.

Financial institutions, commodity companies, project businesses and other special
business models may require different economic interpretation. S001 does not infer
quality from a flag.

## Output

For every one of 2,319 identities retain:

- source state;
- current/prior comparable facts;
- deterministic growth/margin metrics where valid;
- opportunity flags;
- caution flags;
- U001 overlap.

No composite score is produced.

## Promotion

Passing S001 permits joins with:

- HA001 asset-anomaly flags;
- GF001 governance/ownership facts;
- SS001-I001 liquidity/capacity context;
- SS002 current special-situation events and validated LLM evidence.

Those joins are research routing only unless separately frozen.

## Scientific boundary

S001 does not:

- use future returns;
- use market capitalization;
- use analyst estimates;
- infer intrinsic value;
- use an LLM;
- rank names by expected return;
- create ADO/PF001 eligibility;
- authorize live capital.
