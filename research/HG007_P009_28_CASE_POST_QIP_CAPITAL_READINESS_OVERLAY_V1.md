# HG007-P009: Propagate Stale QIP Share-Count Warning Across Hidden Gems

Status: **RESEARCH DATA INTEGRITY ONLY**, frozen 10 October 2026 IST.
No updated security price targets, forecasts, current fully diluted
shareholding or buy/sell ranking has been created.

## Why

The mechanically selected outside-U001 28-company HG002 / HG007
research cohort is still valuable, but its original INOXGREEN entry
carried a **1 October market cap using the 31 March 2026 fully
diluted share count**. This basis omits the completed 29 September
QIP share issuance, which adds 18,110,473 basic equity shares.

The original work must stay immutable for replication, but a consumer
must no longer mistake it for an approved current valuation reference.

## Sources

This overlay re-generates the original 28-name casework from the same
seven immutable Git blob-checked sources as HG007-P001. It separately
pins the exact original NSE Sep29 QIP and 1Oct/9Oct price arithmetic
contained in the already source-audited HG007-P008:

research/hg007/inoxgreen-sep2026-qip/post-qip-market-cap-audit-v1.json

HG007-P008 corrected references:

- 1 Oct: old March FD count 403,959,665 at INR159 => INR 6422.96 cr.
- 1 Oct: Sep29 post-QIP basic count 419,602,518 at INR159
  => **INR 6671.68 cr**.
- 9 Oct: Sep29 post-QIP basic count 419,602,518 at INR128.92
  => **INR 5409.52 cr**.

The latter two are share-price reference arithmetic, not
independently certified **current fully diluted** equity valuations.

## Safeguards

The new source-only overlay:

- retains **all original 28 companies**, their exact frozen
  investment-research sourcing, catalyst stage and payoff facts;
- marks INOXGREEN's pre-QIP March FD denominator
  STALE_MARCH_FD_DENOMINATOR_AFTER_SEPTEMBER_QIP;
- attaches source-verified dated basic-share reference values;
- keeps all other 27 names marked
  NOT_REEVALUATED_UNDER_HG007_P009, which is NOT endorsement of
  their current share counts, cash or corporate-action adjustments;
- blocks new EV, adjusted earnings multiples and actionable
  per-share upside until current options, shares, QIP cash, external
  debt, minority interest and WWIL earnings are verified;
- preserves **zero publishable** survivor-conditioned case
  probabilities and **zero investment recommendations**.

The prior HG007-P001 result is not overwritten. Downstream
screening can consume P009 and still reproduce the historical
original source state.

## Implementation

- src/marketlab/hg007_capital_readiness.py
- scripts/build_hg007_capital_readiness.py
- tests/test_hg007_capital_readiness.py
- .github/workflows/hg007-capital-readiness.yml

Generated append-only after main merge:

research/hg007/hg007-p009-28-case-capital-readiness-overlay-v1.json

## Remaining true missing pieces

1. Original current as-of-Sep29-or-later Reg31 shareholding,
   including outstanding ESOP and option series.
2. Post-QIP full share issues and corporate-action adjustments.
3. Consolidated cash use, new QIP fee/deployment, original
   Inox Green net debt and Vibhav intercompany-elimination bridge.
4. WWIL cash generation, third-party financing, completed transfer
   and minority rights.
5. Independent post-transaction invested capital and downside.
6. Actual prospective event family base-rate evidence after
   survivor conditioning. The existing HG006 probability sample
   does not meet its preregistered threshold.

This overlay corrects an integrity risk. It does not create alpha
or authorize portfolio/live-capital deployment.
