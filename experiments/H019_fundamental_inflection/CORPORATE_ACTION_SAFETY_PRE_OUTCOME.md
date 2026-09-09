# H019 share-count corporate-action safety, pre-outcome

Status: **FROZEN BEFORE ANY H019 SCORE, SELECTION OR RETURN OUTCOME**

H019's official XBRL filings expose `PaidUpValueOfEquityShareCapital` and `FaceValueOfEquityShareCapital`; their ratio is a filing-period-end share-count primitive. H019's decision price is later. Using period-end share count directly at the decision date would misstate market capitalization when the security undergoes a split, bonus, consolidation or other capital-changing corporate action between the latest reported quarter end and the decision date.

## Frozen rule

For valuation features only:

1. Start from the strict XBRL share count `paid_up_equity_share_capital / face_value_per_share` at the latest reported quarter end.
2. Query only official NSE corporate-action records available through the repository's existing NSE endpoint.
3. Consider actions whose ex-date satisfies `latest_quarter_end < ex_date <= decision_date`.
4. Reuse the repository's already-tested action parser for:
   - bonus issues with an explicit ratio;
   - stock splits/sub-divisions with explicit old/new face values;
   - consolidations with explicit old/new face values.
5. Multiply period-end share count by the product of those resolved factors to obtain decision-date adjusted share count.
6. If any crossing action is classified unresolved by the existing parser, including rights, merger, demerger, scheme of arrangement, amalgamation or capital reduction, valuation features are unavailable for that candidate. Do not guess an adjustment.
7. Ordinary dividends and other actions that do not alter share count are ignored by this share-count rule.
8. The adjustment affects only market-cap-derived valuation features. It does not alter reported revenue, PAT, EPS, margins or the point-in-time filing history.

No action factor or exclusion may be chosen from H019 future-return outcomes.

## Scope

This rule does not claim to reconstruct every possible capital issuance. It handles the exchange corporate-action classes for which the repository already has explicit, deterministic factors and fails closed on materially ambiguous share-changing actions. Exact-factor coverage will be measured before H019-v1 scoring is frozen.
