# HG005-D002 Family-Specific Payoff Source Enrichment v1

Status: **FROZEN BEFORE NEW PAYOFF-SOURCE ACQUISITION**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Enrich the five HG005-D001 payoff-ready companies with only the additional business
economics required to construct family-specific scenario/payoff models.

HG005-D002 is source enrichment. It does not assign completion probability, expected
return, target price or portfolio weight.

## Frozen upstream

Use exactly:

- HG005-D001-v1;
- workflow run: `37303366312`;
- artifact ID: `11343026198`;
- context SHA-256:
  `f8cb5079e266f451013d964b67b38dd833c7212bdffa4ffe23bd4fcef28fa48b`.

Symbols are exactly:

- ANANTRAJ
- DEVX
- INOXGREEN
- NPST
- SAMBHV

No new company may enter D002-v1.

## Source hierarchy

For every missing input, acquire evidence in this order:

1. exact NSE/BSE/SEBI/regulatory filing or order;
2. company document filed to an exchange, including scheme documents, investor
   presentations, annual reports and monitoring reports;
3. official target-company filing when the economic target is a separate issuer/entity;
4. regulated credit-rating report or lender disclosure when financing/debt economics
   are unavailable in company filings.

General news, broker target prices, screening websites and unsourced web summaries are
not primary D002 evidence.

A lower-priority source may supplement but may not override contradictory higher-priority
official evidence.

## Common evidence object

Every enriched fact must retain:

- symbol;
- economic lane;
- fact name;
- explicit value/text;
- unit;
- effective/reporting date;
- source URL;
- source type;
- source publication date;
- exact raw/source SHA-256 when acquired into the repository;
- evidence status:
  - EXPLICIT_READY
  - EXPLICIT_RANGE
  - EXPLICIT_BUT_STALE
  - CONFLICTING
  - NOT_FOUND.

No NOT_FOUND value is imputed.

---

# Family A — Demerger entitlement

Applies to:

- ANANTRAJ;
- INOXGREEN.

## Required enrichment

### ANANTRAJ

Acquire explicit evidence for the separated Ashok Cloud/data-centre business:

- FY26 revenue/turnover;
- FY26 EBITDA/EBIT/PAT when disclosed;
- transferred assets;
- transferred liabilities/debt;
- capacity in operation;
- capacity under construction / committed expansion;
- scheme effective-date / record-date status when available;
- exchange-ratio confirmation.

Also retain remaining Anant Raj/stub economics when separable in official disclosures.

### INOXGREEN

Acquire explicit evidence for the Power Evacuation Business / resulting Resco entity:

- transferred assets;
- transferred liabilities;
- historical revenue;
- EBITDA/PAT/cash flow when disclosed;
- operating capacity/assets;
- effective/record-date status;
- exchange-ratio confirmation.

## Frozen payoff identity

For one parent share:

`shareholder_value = parent_stub_value_per_share + entitlement_units * separated_business_value_per_unit`

D002 does not assign either valuation term.

It only determines whether source facts are sufficient for a later D003 valuation
framework.

## D002 readiness

- DEMERGER_SOURCE_READY:
  explicit exchange ratio plus enough separated-business operating/financial evidence to
  support at least one independently specified valuation method.
- DEMERGER_SOURCE_PARTIAL:
  entitlement exists but business economics remain incomplete.

---

# Family B — Acquisition economics

Applies to:

- INOXGREEN / Wind World (India) O&M business.

## Required enrichment

Acquire:

- final or latest purchase consideration / adjustment mechanism;
- funding source:
  - cash on balance sheet;
  - debt;
  - equity;
  - internal accrual;
  - mixed;
- incremental financing amount and explicit interest terms when disclosed;
- target FY24/FY25/FY26 revenue;
- target FY24/FY25/FY26 EBITDA or operating profit;
- target PAT;
- target operating cash flow / free cash flow when available;
- target debt and cash transferred/assumed;
- explicit synergies only when management quantifies them;
- closing/completion status.

## Frozen mechanical metrics after enrichment

When explicit inputs exist:

`purchase_price_to_revenue = purchase_consideration / target_normalized_revenue`

`purchase_price_to_ebitda = purchase_consideration / target_normalized_ebitda`

`incremental_interest = explicit_incremental_debt * explicit_interest_rate`

No missing margin is inferred from Inox Green's own margin.

## D002 readiness

- ACQUISITION_SOURCE_READY:
  purchase consideration + funding structure + normalized target earnings/cash-flow
  evidence available.
- ACQUISITION_SOURCE_PARTIAL:
  one or more remain absent.

---

# Family C — Dilution financing

Applies to:

- DEVX;
- SAMBHV.

HG005-D001 already has sufficient market/share denominators.

D002 must enrich **use-of-proceeds economics**, not repeat dilution math.

## DEVX required enrichment

Acquire:

- exact total cash actually received from preferential equity/warrants to date;
- warrant exercise cash still receivable;
- security-deposit amount paid;
- lease/rent economics for the proposed ~450,000 sq ft centre;
- expected operational/fit-out timeline;
- expected capacity/seats/racks or revenue-bearing units if disclosed;
- capex/fit-out amount;
- expected revenue/EBITDA contribution if explicitly guided;
- current project status.

## SAMBHV required enrichment

Acquire:

- allotment status of the 8,695,400 warrants;
- upfront cash received;
- remaining exercise cash receivable;
- explicit use of proceeds;
- named capex/working-capital/debt-repayment projects;
- capacity addition and commissioning timing;
- explicit incremental revenue/EBITDA potential when disclosed.

## Frozen financing reference

The later payoff model may compare:

`cash_raised / dilution_created`

and:

`incremental_value_created / incremental_diluted_shares`

but D002 does not assign incremental value unless operating evidence explicitly supports
a later scenario framework.

## D002 readiness

- FINANCING_DEPLOYMENT_SOURCE_READY:
  financing status plus sufficiently specific use/deployment economics exist.
- FINANCING_DEPLOYMENT_SOURCE_PARTIAL:
  financing terms exist but operating deployment economics remain incomplete.

---

# Family D — Capital deployment

Applies to:

- NPST;
- DEVX.

## NPST required enrichment

Acquire the latest available post-March-2026 utilization statement for the ₹300 crore
raise, including:

- cumulative amount deployed;
- unutilized amount;
- spending by stated object;
- acquisitions completed with proceeds;
- product/infrastructure investment completed;
- global expansion/brand spend;
- explicit revenue/cost/operating consequences when disclosed.

Also acquire current Q1/Q2 FY27 operating evidence linked to those deployment objects
when management explicitly connects it.

## DEVX

Use the DEVX financing/deployment evidence specified above.

## D002 readiness

- CAPITAL_DEPLOYMENT_SOURCE_READY:
  current deployment state and at least one explicit operating consequence or measurable
  deployment asset exists.
- CAPITAL_DEPLOYMENT_SOURCE_PARTIAL:
  current deployment amount is known but economic consequence is not yet measurable.

---

# Source conflicts and time ordering

When multiple official documents disagree:

1. retain every value;
2. order by publication/effective date;
3. label superseded facts;
4. never silently select the most favorable value.

Post-event documents may update transaction stage/consideration but do not rewrite what
was known at an earlier point in time.

## No probability yet

HG005-D002 must not estimate transaction completion probability.

Probability work requires a later frozen protocol using:

- family-specific historical base rates;
- current stage;
- required approvals;
- financing certainty;
- elapsed time;
- event-specific disconfirming evidence.

The LLM may extract those facts later, but cannot assign the probability itself.

## Promotion

Passing a family lane permits HG005-D003 family-specific scenario valuation/payoff
frameworks.

D003 may define valuation equations and scenario variables, but any subjective assumptions
must be:

- explicit;
- sensitivity-tested;
- separated from source facts;
- frozen before portfolio outcome evaluation.

## Scientific boundary

D002 does not:

- set valuation multiples;
- annualize one quarter by default;
- assign synergies not explicitly disclosed;
- infer target margins;
- estimate expected return;
- rank the five names;
- create a target price;
- create an ADO;
- modify PF001;
- authorize live capital.
