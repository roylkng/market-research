# HG005-D001 Market Denominators and Mechanical Payoff Context v1

Status: **FROZEN BEFORE PAYOFF METRIC MATERIALIZATION**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Supply deterministic current market denominators and purely mechanical transaction ratios
for the five HG004 companies whose transaction lanes are already payoff-model ready.

HG005-D001 does not estimate expected return, completion probability, intrinsic value or
target price.

## Frozen source set

### HG004 transaction terms

Use exactly:

- HG004-L002-v1;
- workflow run: `37297528769`;
- artifact ID: `11339427625`;
- synthesis SHA-256:
  `6bd1a43d29460fc18389dfdcb7241c95d1de0acb80b769a728946ef81c031683`.

Exactly five payoff-model-ready symbols:

- ANANTRAJ
- DEVX
- INOXGREEN
- NPST
- SAMBHV

No additional company may enter D001-v1.

### Current market price

Use exactly the frozen SS001-D001 October 1, 2026 official NSE market context:

- run: `37197575401`;
- artifact ID: `11301695772`;
- census SHA-256:
  `0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7`.

For each symbol use only:

`market.last_observed_session == 2026-10-01`

and:

`market.last_close`

No later market price enters v1.

### Current share counts

Use exactly GF001-D002 latest shareholding XBRL evidence:

- run: `37202941712`;
- artifact ID: `11303742567`;
- panel SHA-256:
  `dd338cd91f44396278300e27e8cdac1506dae11b63dd31ce827505fe62e8abe7`.

From each latest official XBRL use exact context:

`ShareholdingPattern_ContextI`

and exact concepts:

- `NumberOfFullyPaidUpEquityShares`;
- `NumberOfSharesOnFullyDilutedBasisIncludingWarrantsESOPAndConvertibleSecurities`.

Both must use unitRef `shares`.

No share count is inferred from EPS, market capitalization, promoter percentages or
third-party data.

### Financial context

Use exactly FA001-D002-v1:

- run: `37213394690`;
- artifact ID: `11306919543`;
- panel SHA-256:
  `cb8a408b6904799750a5aa08210f909ae8b285005273b5588fb1f8b7a6019124`.

Retain only READY INR / INRPerShare facts needed for context:

- annual total equity;
- annual cash;
- annual current/non-current investments;
- annual current/non-current borrowings;
- annual investment property;
- annual CWIP;
- annual PPE;
- annual basic EPS;
- Q1 FY27 revenue;
- Q1 FY27 PAT;
- Q1 FY27 basic EPS.

Missing facts remain missing.

## Frozen current market-cap definitions

### Basic market capitalization

`basic_market_cap_inr = close_price * fully_paid_equity_shares`

### Reported fully diluted market capitalization

`reported_fd_market_cap_inr = close_price * reported_fully_diluted_shares`

No NSE quote-endpoint market capitalization is used because SS001-D003 source testing
showed the quote trade-info route is blocked by HTTP 403.

## Event-adjusted diluted shares

D001 may compute event-adjusted diluted shares only for an explicit HG004 dilution lane.

### DEVX

HG004-L001 explicitly records ALLOTMENT_COMPLETED for:

- 44,44,440 preferential equity shares;
- 33,33,330 convertible warrants.

GF001 latest report date is 2026-06-30.

The reported latest values must exactly reconcile:

- fully paid shares = post-allotment paid-up shares;
- reported fully diluted minus fully paid = 33,33,330 warrants.

If exact reconciliation fails, DEVX event-adjusted dilution fails closed.

Event-adjusted diluted shares equal the reported fully diluted shares.

### SAMBHV

HG004 records BOARD_APPROVED on 2026-07-15 for 86,95,400 preferential warrants,
after the GF001 latest report date 2026-06-30.

D001 therefore treats those securities as pending relative to the frozen shareholding
snapshot:

`event_adjusted_fd_shares = reported_fd_shares + 8,695,400`

No assumption is made that approval became allotment or conversion.

This is a pro-forma dilution context, not a claim about current issued shares.

### Other symbols

ANANTRAJ, INOXGREEN and NPST do not receive event share-count adjustments under D001-v1.

## Frozen mechanical metrics

### All companies

When inputs exist:

- basic_market_cap_inr;
- reported_fd_market_cap_inr;
- current_trailing_pe = close_price / FY26 basic EPS when EPS > 0;
- net_financial_assets =
  cash + current investments + non-current investments
  - current borrowings - non-current borrowings;
- net_financial_assets_to_reported_fd_market_cap.

These are context, not valuation claims.

### Dilution-financing lane

For DEVX and SAMBHV:

- event_security_count;
- event_security_count / pre-event-or-frozen fully diluted shares;
- issue_price_per_security / current_price - 1;
- event_adjusted_fd_shares;
- event_adjusted_fd_market_cap at frozen current price;
- explicit gross issue consideration when HG004 contains it;
- gross issue consideration / reported_fd_market_cap.

No value is assigned to use of proceeds.

### Acquisition lane

For INOXGREEN:

- stated acquisition consideration;
- stated consideration / reported_fd_market_cap;
- stated consideration / annual total equity;
- target stated operating revenue where HG004 explicitly supplies it.

No target EBITDA, margin, synergies or completion probability is inferred.

### Demerger lane

For ANANTRAJ and INOXGREEN:

- retain exact exchange-ratio text;
- retain explicit separated-business description;
- retain any explicitly stated separated-business turnover/operating metric.

D001 must not convert an exchange ratio into value without an independently sourced
separated-business valuation.

### Capital-deployment lane

For NPST and DEVX:

- stated capital raise / reported_fd_market_cap when amount is explicit;
- stated utilization/unutilized amounts;
- stated use-of-proceeds text.

No deployment return is inferred.

## Governance context

Carry GF001 latest:

- promoter percentage;
- quarter-on-quarter promoter percentage-point delta;
- promoter pledge boolean;
- promoter NDU boolean;
- other promoter encumbrance boolean.

Governance fields do not add upside.

## Output states

For each lane:

- `DENOMINATOR_READY` when all deterministic market/share inputs required by that lane exist;
- `SOURCE_INPUT_REQUIRED` when a deterministic denominator is missing;
- `VALUATION_INPUT_REQUIRED` when denominators exist but intrinsic/economic value still
  requires separately sourced business economics.

A company may have multiple lane states.

## Scientific boundary

HG005-D001 does not:

- assign an expected-return number;
- assign probability of completion;
- select valuation multiples;
- annualize Q1 earnings;
- infer target margins;
- infer synergies;
- rank the five names;
- create a target price;
- create an ADO;
- modify PF001;
- authorize live capital.

Passing D001 permits family-specific HG005 valuation-source enrichment and scenario-payoff
frameworks under separately frozen contracts.
