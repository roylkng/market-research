# HG005-D003 Family-Specific Break-Even and Payoff Sensitivity Frameworks v1

Status: **FROZEN BEFORE D003 MATERIALIZATION**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Completion probabilities assigned: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Convert the source-ready HG005 payoff lanes into deterministic, falsifiable payoff
surfaces.

D003 does not choose a single fair value. It answers:

> What operating/valuation conditions are required for the current equity value to gain
> 25%, 50% or 100%, and what gross value ranges follow from explicitly frozen
> sensitivity variables?

This is a valuation/hurdle framework, not expected return.

## Frozen upstream

### Market denominators

HG005-D001-v1:

- context SHA-256:
  `f8cb5079e266f451013d964b67b38dd833c7212bdffa4ffe23bd4fcef28fa48b`;
- price session: 2026-10-01.

### Payoff facts

HG005-D002B-P1-v1:

- result SHA-256:
  `7129a3eb75852372c724c63c74fa3efa3fde27ea9a2aa953830322229b0c9065`;
- synthesis SHA-256:
  `beee365eb088e22b52e1827e0c1d6e2b68e842d36015c8ac988b8f5380f07287`;
- exact run artifact: `hg005-d002b-37319444854`.

Source-ready lanes:

- ANANTRAJ — DEMERGER_ENTITLEMENT;
- DEVX — DILUTION_FINANCING;
- DEVX — CAPITAL_DEPLOYMENT_MONITOR;
- NPST — CAPITAL_DEPLOYMENT_MONITOR;
- SAMBHV — DILUTION_FINANCING.

INOXGREEN remains SOURCE_PARTIAL and receives no completed D003 payoff surface.

## Common uplift hurdles

For every source-ready company evaluate current-equity-value hurdles:

- +25%;
- +50%;
- +100%.

These are not forecasts. They are reverse-engineered requirements.

## ANANTRAJ — demerger value surface

Explicit source facts:

- FY26 demerged-business revenue: INR 145.90 crore;
- operational data-centre capacity: 28 MW IT load;
- entitlement: 1 Ashok Cloud share for every 1 Anant Raj share.

Frozen sensitivity methods:

### A. Current-revenue multiple

Gross separated-business enterprise value:

`EV = FY26_demerger_revenue * EV_revenue_multiple`

Multiples:

- 5x;
- 10x;
- 15x.

### B. Current-operating-capacity multiple

Gross separated-business enterprise value:

`EV = operational_MW * EV_per_MW_inr_crore`

EV/MW sensitivity:

- INR 25 crore/MW;
- INR 50 crore/MW;
- INR 75 crore/MW.

Report every implied EV as a percentage of current Anant Raj fully diluted market cap.

Do **not** convert gross separated-business EV into shareholder equity value because
quantified transferred cash/debt/liabilities are not explicit.

Do not value planned 357 MW as if operational. Planned capacity remains context only.

## DEVX — Winston capital-deployment hurdle

Explicit source facts:

- current reported fully diluted market cap;
- 450,000 sq ft Winston area;
- INR 35.10 crore refundable security-deposit requirement;
- INR 23.75 crore received in Q1 FY27 and deployed toward the deposit;
- nine-year lease;
- current Winston stage.

No Winston-specific revenue or EBITDA guidance is explicit.

Therefore D003 uses reverse valuation only.

For each target equity uplift `U` and selected EV/EBITDA multiple `M`:

`required_incremental_EBITDA = current_market_cap * U / M`

EV/EBITDA sensitivity:

- 10x;
- 15x;
- 20x.

Also report:

`required_annual_EBITDA_per_sqft = required_incremental_EBITDA * 1e7 / 450000`

This is a hurdle, not a forecast.

The refundable security deposit is retained as capital tied up; it is not deducted as
permanent capex.

## NPST — capital-deployment/growth hurdle

Explicit source facts:

- current reported fully diluted market cap;
- Q1 FY27 revenue: INR 56.48 crore;
- Q1 FY27 EBITDA: INR 18.79 crore;
- preferential raise: INR 300 crore;
- cumulative deployment by 2026-06-30: INR 35.64 crore;
- unutilized proceeds: INR 264.36 crore;
- international subsidiary is revenue-contributing.

For each target equity uplift `U` and EV/EBITDA multiple `M`:

`required_incremental_annual_EBITDA = current_market_cap * U / M`

Multiple sensitivity:

- 20x;
- 30x;
- 40x.

For interpretability only:

`quarterly_equivalent = annual_required / 4`

`quarterly_equivalent_vs_Q1_EBITDA = quarterly_equivalent / 18.79`

This does not annualize Q1 FY27 earnings into a valuation. It only compares the size of
the hurdle with an observed quarter.

Also retain deployed/unutilized proceeds as percentages of current market cap.

## SAMBHV — Phase-I capacity/dilution payoff surface

Explicit source facts:

- current reported fully diluted market cap;
- event-adjusted fully diluted shares;
- warrant count and issue price;
- current finished-products capacity: 0.62 MMTPA;
- long-term finished-products target: 2.03 MMTPA;
- Phase-I stainless capacity addition: 0.36 MMTPA;
- Phase-I stated capex: INR 8,100 million;
- target commissioning: Q4 FY27;
- latest financing stage: in-principle exchange application.

D003 may deterministically convert:

`INR 8,100 million = INR 810 crore`.

Frozen operating sensitivities:

Capacity utilization:

- 70%;
- 85%;
- 100%.

Incremental EBITDA per tonne:

- INR 5,000;
- INR 7,000;
- INR 9,000.

EV/EBITDA multiple:

- 8x;
- 10x;
- 12x.

For each grid point:

`incremental_EBITDA_cr = 0.36e6 * utilization * EBITDA_per_tonne / 1e7`

`gross_incremental_EV_cr = incremental_EBITDA_cr * multiple`

Conservative equity-value bridge:

`net_incremental_equity_value_cr = gross_incremental_EV_cr - 810`

The subtraction treats the stated Phase-I capex as capital that must be funded by
shareholders/debt/internal cash. It does not assume a financing mix.

Report:

- gross incremental EV/current market cap;
- net incremental equity value/current market cap;
- net incremental value per event-adjusted fully diluted share.

This is a sensitivity surface. It is not a target price.

## INOXGREEN

D003 explicitly retains:

`PAYOFF_FRAMEWORK_BLOCKED_SOURCE_PARTIAL`

for both:

- acquisition economics;
- demerger entitlement.

Reason:

- WWIL funding structure missing;
- normalized WWIL EBITDA/PAT/OCF missing;
- separated-business financial economics missing.

No proxy margin from Inox Green may be substituted.

## No completion probability

D003 does not estimate the probability that:

- a scheme becomes effective;
- warrants are allotted/exercised;
- capacity commissions on time;
- deployment produces assumed EBITDA;
- an acquisition closes.

A later HG006 probability protocol must be frozen separately and use historical
family-specific base rates plus current stage evidence.

## No expected return

D003 does not multiply payoff by probability.

It may show:

- gross value sensitivity;
- hurdle requirements;
- current market-cap percentage;
- break-even economics.

It may not show probability-weighted expected return.

## Promotion

D003 permits:

- HG006 historical family-specific completion/base-rate research;
- red-team source work;
- later expected-value/IRR calculations only after HG006 is frozen and completed.

## Scientific boundary

No D003 output creates:

- target price;
- buy/sell/hold;
- ranking;
- ADO/PF001 eligibility;
- live-capital authorization.
