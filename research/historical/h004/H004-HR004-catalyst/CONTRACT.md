# H004-HR004 corporate-catalyst reconstruction contract

Status: **FROZEN BEFORE CANDIDATE OUTPUT INSPECTION**  
Live capital: **NO**

Purpose: reconstruct the non-earnings H004 Stage-1 catalyst information set from exchange announcements without using subsequent stock returns.

## Window

- announcement timestamp window: 2025-10-01 through 2026-07-31
- design-set week 2026-08-31 through 2026-09-07 remains excluded
- official source: NSE corporate-announcement API and original NSE attachments

## Candidate extraction

A public announcement enters the semantic review queue when its exchange description or attachment summary contains one or more of these predeclared families:

1. **ORDER_CONTRACT**: order, contract, letter of award, LOA, work order, purchase order, preferred/L1 bidder, tender award.
2. **CAPACITY_COMMISSIONING**: capacity expansion, commissioning, commercial production/operation, new plant/facility/line, brownfield/greenfield expansion.
3. **REGULATORY_MARKET_OPENING**: regulatory approval, licence/license, product approval, certification or authorization that may open a material market.
4. **MNA_CONTROL**: acquisition, strategic investment, merger, demerger, change in control, sale/purchase of a material business.
5. **GUIDANCE_RAMP**: quantified guidance revision, quantified customer/product/network ramp, first commercial operation of a material new business.

Routine governance, meeting, trading-window, newspaper, investor-meeting, shareholder-voting, dividend, director appointment, routine litigation, monitoring-agency and generic update disclosures are not candidates unless the announcement text independently contains one of the above catalyst families.

## Candidate evidence

For every candidate retain only information observable at the exchange timestamp:

- `candidate_id` = SHA-256 of canonical source identity,
- NSE symbol and company name for later joining,
- exchange timestamp,
- description,
- exchange attachment summary text,
- original NSE attachment URL when available,
- extracted candidate family terms,
- source row identity / seq_id.

The extraction stage does **not** assign catalyst grade 3/4 and does not inspect returns.

## Semantic catalyst grading

Candidate grade is decided from source context only, before joining to returns.

Grade 4:
- change of control / strategic acquisition that is material to the company,
- regulatory approval opening a material new market,
- order value >=25% of TTM revenue,
- commercial commissioning or quantified capacity addition >=25% of existing capacity,
- explicit management guidance increase >=20% for a material metric.

Grade 3:
- order value 10% to <25% of TTM revenue,
- quantified capacity/network expansion 10% to <25%,
- first commercial operation of a material new business,
- quantified new product/customer ramp with a near-term financial horizon.

Grade 0–2 cannot independently create H004 Stage 1.

If source evidence does not permit the denominator needed for a materiality ratio, the reviewer must mark `INSUFFICIENT_FOR_GRADE` rather than infer materiality from absolute rupee value.

## Leakage guardrails

- no future returns, future market reaction or later company outcome may be included in the semantic review payload,
- the candidate extractor may use only exchange fields timestamped at or before the candidate timestamp,
- search keywords only nominate candidates and are never treated as catalyst grade,
- no catalyst threshold may be changed after the queue is generated,
- duplicate/restated announcements collapse to the earliest materially equivalent source.

## Evaluation after grading

Only after grading is frozen may Grade-3/4 catalysts be joined to HR003 full-market episodes and market data.

Report:
- candidate coverage,
- Grade-3/4 signal count,
- Stage-1 pre-momentum eligibility,
- Stage-2 executable trigger count,
- full-market explosive-episode recall,
- precision and lead time,
- incremental recall over earnings-only H004,
- overlap with earnings anchors,
- false positives and missed catalyst-driven episodes.

This reconstruction is historical feasibility evidence, not prospective validation.
