# H019 corporate-action valuation audit decision

Recorded: 2026-09-09

Status: **VALUATION ACTION RULE MAY PROCEED. RETURN OUTCOMES UNOPENED. SCORE NOT YET FROZEN.**

The pre-outcome corporate-action audit queried and retained exact official NSE action responses for 2020-2023, then intersected those actions with every H019 liquidity-eligible candidate between the candidate's latest reported quarter end and its decision date.

Audit population:

- 3,658 candidate observations across the seven input cohorts;
- 9,603 raw NSE action rows, 9,600 after exact deduplication;
- 596 candidate observations with at least one crossing action;
- 45 crossing events with an already-tested explicit split/bonus/consolidation factor;
- 16 crossing events already classified unresolved by the repository action parser;
- 561 crossing events not parsed by that parser.

The 561 genuinely unparsed events were reviewed by exact subject text. Every unparsed event was either:

1. an ordinary/interim/final/special dividend or dividend combined with a general-meeting record;
2. a general-meeting record; or
3. one of 26 buyback records (`Buy Back` / `Buyback`).

No other unparsed capital-sensitive action class occurred in the audited candidate crossing set.

## Frozen H019 valuation-action rule

For each candidate, between latest reported quarter end and decision date:

1. Apply the existing deterministic factor for every parsed, resolved split, bonus or consolidation.
2. If the existing action parser marks any crossing action unresolved, valuation features are unavailable.
3. If an unparsed crossing action contains `dividend` or denotes a general meeting, it is benign for share-count adjustment and is ignored for this purpose.
4. Any other unparsed crossing action is valuation-unsafe. In the audited 2020-2023 H019 universe this means buybacks. Valuation features are unavailable for that candidate.
5. Do not infer a buyback share-count factor from announcement text, price, or later filings.
6. This safety rule affects only market-cap-derived valuation features. Reported operating features remain available.

The rule is fail-closed and was fixed before any H019 score, selection or return outcome.
