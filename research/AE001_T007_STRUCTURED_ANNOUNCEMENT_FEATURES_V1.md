# AE001 T007 Structured Corporate-Announcement Feature Family v1

Status: FROZEN BEFORE HISTORICAL OUTCOME MATERIALIZATION
Frozen: 2026-09-30
Live capital: DISABLED

## Objective

Test whether structured information extracted from official NSE corporate
announcement metadata adds short-horizon cross-sectional predictive information
beyond the frozen AE001 CORE27 price/liquidity/delivery feature set.

T007 uses the whole-market announcement source validated by AE001-D003.

T007 is not an LLM sentiment experiment. Event direction is learned from
out-of-sample return evidence rather than assigned by hand.

## Historical source

Official NSE corporate-announcement endpoint:

    /api/corporate-announcements

Historical acquisition uses one whole-market query per calendar date.

Source window:

    2025-09-01 through 2026-09-25 inclusive.

Every calendar date is queried. A successfully parsed empty response is a valid
zero-announcement date. A missing, blocked, parser-rejected or ambiguous daily
response fails the historical source panel closed. Missing days are not imputed.

The daily whole-market acquisition strategy is promoted by sealed D003:

    research/ae001-d003-result-v1.json

D003 report SHA-256:

    7f402beecaf90f054c93ca2ceeaa01f38fcc5cd8f7f8f6391f60791768f8a91f

## Announcement identity

Canonical event identity uses symbol, NSE seq_id, official exchange dissemination
timestamp, desc, attchmntText and attchmntFile.

Official timestamp fields follow the existing H003 parser: exchdisstime, an_dt,
sort_date and dt.

Rows missing symbol, seq_id or parseable official timestamp fail closed.

## Point-in-time symbol identity

Announcements provide NSE symbol but not ISIN.

For each mapped decision session, the announcement symbol is rebound to the exact
NSE EQ symbol + ISIN identity from that session's official UDiFF panel.

An announcement with no unique same-session EQ identity is excluded from feature
attribution and counted explicitly. Symbol-only historical identity is never
carried across an ISIN break.

## Frozen decision clock

Decision cutoff:

    18:30:00 Asia/Kolkata

Each announcement is assigned exactly once to the earliest completed NSE session
whose 18:30 IST decision cutoff is greater than or equal to the official exchange
dissemination timestamp.

This naturally maps:
- announcements before/equal 18:30 on a trading session to that session;
- announcements after 18:30 to the next completed session;
- weekend/holiday announcements to the next completed session.

The current-session event interval is previous completed-session 18:30 IST,
exclusive, through current completed-session 18:30 IST, inclusive.

No announcement may be backdated to an earlier decision.

## Frozen event taxonomy

Taxonomy is matched against normalized desc + attchmntText.

One announcement may match more than one category.

ORDER_CUSTOMER:
    order, orders, contract, contracts, bookings, customer win,
    letter of award, letter of acceptance

CAPACITY_INVESTMENT:
    capex, capacity, commission*, manufacturing facility, factory, invest*

RESULTS_GUIDANCE:
    earnings, quarter*, financial results, guidance, outlook, revenue, profit

PRODUCT_APPROVAL:
    launch*, approval, approved, patent*, new product, commercialisation

CAPITAL_TRANSACTION:
    merger, acqui*, divest*, disposal, buyback, share swap, rights issue,
    allotment, fund rais*

OWNERSHIP_CONTROL:
    stake sale, selling stake, entire/remaining stake, promoter stake,
    change of control, open offer

GOVERNANCE_RISK:
    fraud, default, resign*, auditor, investigation, insolvency, litigation

POLICY_REGULATION:
    regulat*, circular, tariff*, government, tax, subsid*, policy

An announcement matching at least one category is MATERIAL for T007.
An announcement matching none is ROUTINE_UNCLASSIFIED.

These names are semantic buckets, not bullish/bearish labels.

## Frozen T007 feature set

Sixteen features are added to CORE27:

1. ann_total_current
2. ann_material_current
3. ann_routine_current
4. ann_unique_topics_current
5. ann_after_close_material_current
6. ann_material_5
7. ann_material_20
8. ann_sessions_since_material_cap20
9. ann_order_customer_current
10. ann_capacity_investment_current
11. ann_results_guidance_current
12. ann_product_approval_current
13. ann_capital_transaction_current
14. ann_ownership_control_current
15. ann_governance_risk_current
16. ann_policy_regulation_current

after_close means official dissemination after 15:30 IST and no later than the
frozen 18:30 decision cutoff.

ann_material_5 and ann_material_20 include the current decision session.

ann_sessions_since_material_cap20 equals completed decision sessions since the
latest mapped material announcement, capped at 20. If no material announcement
exists in the available source history, value = 20.

No attachment body, LLM output, sentiment score, financial magnitude or manually
reviewed event label enters T007-v1.

## Base and challenger

Base CORE27:
- 18 price/liquidity features;
- nine T003 delivery/VWAP features.

Challenger CORE43:
    CORE27 + exact 16 T007 announcement features.

Base and challenger use exactly the same stock-session rows.

## Model

Both models:
- ridge regression;
- l2 = 1.0;
- within-session tie-aware percentile inputs;
- identical labels and folds;
- chronological purged training.

No hyperparameter search is permitted in T007-v1.

## Primary endpoint

Horizon: 1 completed NSE session.

Entry: next completed NSE session open.
Exit: same entry session close.
Target: stock return minus Nifty 500 return over the identical interval.

Frozen validation folds:
1. 2026-04-01 through 2026-06-30
2. 2026-07-01 through 2026-09-24

Paired Newey-West lag: 5.

Primary support requires BOTH:
1. CORE43 minus CORE27 mean daily rank IC > 0 with two-sided p < 0.05;
2. CORE43 minus CORE27 mean daily top-minus-bottom spread > 0 with two-sided
   p < 0.05.

Intersection rule. Failure of either means the primary endpoint is unsupported.

## Secondary endpoint

Horizon: 5 completed NSE sessions.

Frozen validation folds:
1. 2026-04-01 through 2026-06-30
2. 2026-07-01 through 2026-09-18

Paired Newey-West lag: 4.

Secondary support is reported but cannot rescue a failed 1D primary.

## No 20-session endpoint

T007-v1 does not test 20 sessions.

A medium-horizon event study requires a new trial ID.

## Common-row contract

The historical T007 comparison starts from the action-safe, delivery-complete
CORE27 panel.

Every CORE27 row receives announcement features because D003 promotes complete
daily whole-market source acquisition. Zero events are valid data only when all
calendar-day source queries needed for the source window are successfully
captured and parsed.

The announcement feature layer may not filter stocks based on whether an event
occurred.

## Trial accounting

T007 must be appended to research/ae001/trial-ledger.json before the first T007
return outcome is materialized.

Any failed pre-model/source run remains trial evidence but does not count as an
opened return outcome if model fitting or outcome metrics never begin.

## Interpretation

T007 can establish historical-development incremental information for structured
NSE announcement metadata.

It cannot establish complete semantic understanding of attachments, event
causality, calibrated trading profitability, prospective information content, or
live-capital readiness.

If historically supported, the next gate is a separately frozen prospective
confirmation and AB001 orthogonality study.

Live capital remains disabled.
