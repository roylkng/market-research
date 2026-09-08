# H004 design-set audit — recent explosive movers

Date: 2026-09-08  
Status: **DESIGN SET ONLY — EXCLUDED FROM VALIDATION**  
Live capital: **NO**

This document records the cases used to discover failure modes before H004 was frozen. None of these observations may be counted as evidence that H004 works.

## Objective

The previous research path was too concentrated on liquid large-cap fundamentals and post-event momentum. The design-set question was different:

> What information was actually public before or very early in recent 20%–50%+ Indian equity moves, and which of those moves were realistically executable?

## Design cases

### Bodal Chemicals — earnings inflection + delayed repricing

Observed design pattern:

- Q1 FY27 revenue rose roughly 56% YoY.
- PAT rose roughly 219% YoY and PBT roughly 213%.
- The result-day price reaction was only a few percent rather than an immediate explosive repricing.
- The major price acceleration occurred later.

H004 implication:

- Intended to enter Stage 1 through `EARNINGS_INFLECTION`.
- The small event-to-decision move motivated the `expectation_gap` feature.
- Later price/volume expansion belongs only in Stage 2.

### Cyber Media — strong headline result with non-recurring warning

Observed design pattern:

- Q1 revenue and PAT rose sharply.
- Management indicated that unusual project activity contributed to the quarter and was not necessarily sustainable.
- The stock later experienced a large price/volume breakout.

H004 implication:

- Raw growth alone is insufficient.
- `management_says_non_recurring` invalidates the earnings anchor.
- If no independent Grade 3/4 catalyst exists, H004 should accept missing this mover rather than learn from a potentially non-repeatable quarter.

### AKI India — tiny-profit base effect

Observed design pattern:

- Very high YoY revenue and PAT growth percentages.
- Absolute quarterly PAT remained around only half a crore rupees.
- The stock later entered repeated high-percentage moves/circuits.

H004 implication:

- This motivated the `SPECULATIVE_BASE_EFFECT` classification.
- Absolute quarterly PAT below ₹2 crore cannot independently create the primary-universe earnings anchor.
- Such names can remain in the secondary discovery tier when another material catalyst exists.

### Tribhovandas Bhimji Zaveri — change-of-control catalyst

Observed design pattern:

- Q1 operating performance was positive.
- A controlling-stake transaction was the much stronger explanatory event for the explosive move.

H004 implication:

- Change of control is a Grade 4 `CORPORATE_CATALYST`.
- Corporate events must be modeled independently from earnings.

### Jindal Worldwide — headline PAT quality failure + genuine business catalyst

Observed design pattern:

- Headline Q1 PAT growth was very large, but operating revenue growth was modest and non-operating/deconsolidation effects mattered.
- Separately, the EV subsidiary disclosed a quantified dealership/showroom expansion plan and operating production footprint before a later sharp move.

H004 implication:

- Deconsolidation/other one-off gains invalidate the earnings anchor.
- A separately timestamped, sufficiently material quantified business expansion can still qualify through `CORPORATE_CATALYST`.
- H004 therefore avoids treating a bad earnings feature as good merely because a different catalyst later worked.

### ICDS — unexplained move

Observed design pattern:

- Exchange query/clarification did not identify a material undisclosed company event explaining the move.

H004 implication:

- This is an acceptable miss for an information-first model.
- The research objective is not to predict every speculative price discontinuity.
- Unexplained moves remain in the missed-mover taxonomy so recall is not overstated.

### Divyashakti — weak executability

Observed design pattern:

- Very low pre-move liquidity and sharp later price movement.

H004 implication:

- A paper backtest must not claim a successful entry when the quoted price was not realistically available.
- Primary liquidity rules and `NOT_EXECUTABLE` circuit/no-offer handling are mandatory.

### Hikal — turnaround rather than conventional earnings beat

Observed design pattern:

- Revenue growth was modest.
- EBITDA growth and margin expansion were much stronger while bottom-line profitability remained weak.

H004 implication:

- This motivated a separate `TURNAROUND` anchor.
- Requiring high PAT growth would systematically miss early operating recoveries.

## What was deliberately not learned from the design set

H004 does **not** optimize thresholds to maximize catches in these examples.

The following values were frozen as interpretable priors before broad replay:

- Stage-1 prior 5-day return <10%,
- Stage-1 prior 20-day return <20%,
- previous-session return <8%,
- primary traded-value floor ₹2 crore median per session,
- discovery floor ₹25 lakh,
- earnings inflection tests of 20% revenue / 30% operating profit / 40% PAT / +1pp margin or loss-to-profit,
- primary absolute quarterly PAT floor ₹2 crore,
- Stage-2 volume confirmation 2x prior-20-session median,
- primary explosive outcome +25% maximum forward return within 20 sessions.

Changing these thresholds after measuring design-set performance would contaminate the experiment.

## Research consequence

H004 is intentionally two-stage:

1. **Information creates the watchlist.**
2. **Early tape behaviour controls execution timing.**

The model is allowed to miss speculative/unexplained moves. It is not allowed to count impossible upper-circuit entries, one-off accounting gains, or already-explosive stocks as successful pre-momentum predictions.
