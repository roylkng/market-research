# SS002-P007 Official Oct-09 Price and Conditional Tender/Rights Economics v1

Status: **FROZEN BEFORE 2026-10-09 PRICE SOURCE OPENED**
Frozen: 2026-10-10 (Asia/Kolkata)
Investment advice / expected return / capital authorization: DISABLED.

## Objective

Measure whether the economic terms disclosed by the eight P004 source documents
offer meaningful *mechanical* payoffs when paired with the most recent completed NSE
EQ close. Specifically implement:

- VRLLOG tender buyback acceptance/residual-price sensitivities;
- OLAELEC fully-paid rights theoretical ex-rights price (TERP).

All eight frozen cases remain in the panel and receive dated source status.
No other event is valued on a proxy multiple.

## Frozen sources

- SS002-P006-v1, packet SHA
  `e4ff14a24c204471ad6fee037fe93afbddce66e9f46119707f4d9f4fdb8603e7`,
  workflow run 37997329162, artifact 11648081026.
- SS002-P004-NATIVE-8DOC-v1, pilot SHA
  `03d8ae16dd642e8e107b62bdb03eb9dc7e178d0327d742586bc35b65de943ff3`,
  workflow run 37985254672.
- Official NSE CM UDiFF EQ ZIP for exactly completed session **2026-10-09**
  through the repo's existing frozen UDiFF parser.

The market file is content-addressed and SHA bound. Match EQ identity by **both**
symbol and ISIN from P006; no fuzzy matching, corporate-action guessing or substitute
close.

## Event-vs-price timing disclosure

The eight documents concern NSE announcements during October 5–8, 2026.
An October 9 close is *after* these announcements. P007 is an **as-of-October-10
investment research snapshot**, never a backtest claiming a prediction made before
the October 9 price.

The first available price is used for contemporaneous scenario math only.
No future holding-period return is observed or used.

## VRLLOG tender buyback

Only P004 EXPLICIT `offer_price_per_share` with unit INR_PER_SHARE and
`maximum_securities` enter math. Do not infer acceptance from the maximum offered
share count or 15% statutory small-shareholder reservation.

For each frozen grid:

- acceptance fractions: 0, 0.25, 0.50, 0.75, 1.00;
- residual-sale price multipliers on October 9 close: 0.70, 0.85, 1.00;
- fees/taxes: zero only for a **gross pre-cost sensitivity**, never a net return.

Conditional gross proceeds per one originally owned share:

`gross_proceeds = acceptance * buyback_price + (1-acceptance) * residual_price`

Conditional gross price change:

`(gross_proceeds - oct09_close) / oct09_close`

This is **not an expected return**, because acceptance is not a probability and
residual price is illustrative, not forecast.

When `buyback_price > residual_price`, compute break-even acceptance:

`(oct09_close - residual_price)/(buyback_price - residual_price)`

Report NONE_REQUIRED, WITHIN_UNIT_INTERVAL or IMPOSSIBLE_WITHIN_UNIT_INTERVAL
according to the calculated acceptance threshold.

Do not annualize: buyback settlement and tender eligibility remain unverified.

## OLAELEC partly paid rights

Only P004 EXPLICIT:

- issue price per full rights share: ₹27;
- entitlement numerator: 2;
- denominator: 25

enter the theoretical formula.

`TERP = (old_shares * cum_right_price + new_shares * issue_price) /
         (old_shares + new_shares)`

for a hypothetical full subscription and fully paid issue with unchanged enterprise
value and zero fees.

Retain both theoretical rights value per existing share and the fully-paid new share
spread to theoretical ex-rights value.

Do **not** claim that partly paid rights immediately trade like fully paid shares.
Upfront application cash and future calls have not been independently source-verified
under L001 and therefore remain explicitly `SOURCE_PENDING`.

When issue price is above/equal to cum-rights price, report no positive theoretical
exercise value rather than generating fictitious negative-rights arbitrage.

## Other six cases

Keep priced security identity, original P005 lane and mandatory evidence requirements.

No generic P/E target or expected return is attached to a completed, procedural,
unreadable, acquisition or merger event.

## Feasibility gates

1. All eight frozen P006 identities retained.
2. At least 6/8 have exact EQ symbol+ISIN matched October 9 closes.
3. Exact P004 source SHA and term identities match.
4. VRLLOG and OLAELEC mechanically evaluated only if exact-price + explicit terms.
5. No independent semantic audit, share-count clearance or outcome probability is
   fabricated.
6. No portfolio or live-capital permission.

Passing authorizes **dated research context and conditional sensitivity analysis only**.

## Publication controls

Output must retain `post_announcement_price_observed=true`,
`future_holding_period_return_outcomes_opened=false`,
`model_fitted=false`, `underwriting_ready=false`,
`portfolio_eligibility_allowed=false`, `live_capital_allowed=false`.

Every displayed percentage must be labeled gross hypothetical/conditional and before
fees, taxes, settlement risk, rights calls and slippage.
