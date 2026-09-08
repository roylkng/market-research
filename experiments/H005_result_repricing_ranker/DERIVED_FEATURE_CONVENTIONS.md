# H005 derived feature and label conventions

Recorded: 2026-09-08 before the first source-complete real-market H005 fit in this continuation.

The frozen H005 hypothesis, feature families, C grid, operating percentiles and success gates are unchanged. These conventions resolve implementation details that were not numerically specified in the original hypothesis. They must not be changed after model outcomes are inspected under H005-v1.

## Quarterly accounting extraction

A monetary accounting observation is usable only from the exact requested reporting basis and an explicit quarterly context whose reporting-period end equals the candidate quarter end and whose start-to-end duration is 70 through 110 calendar days. The same context must contain the reporting-period dates. Monetary facts must resolve to INR units. Annual, half-year and year-to-date contexts are never divided or prorated into quarters.

If the current filing has no usable explicit quarterly monetary context, the event is excluded from the accounting ranker rather than admitted through wholesale imputation. A missing prior-year filing, missing prior-year field, or unavailable individual current/prior accounting component stays missing and is handled only by H005's frozen fold-local missingness policy.

Total-period PAT is `ProfitLossForPeriod`. Continuing-operations profit alone is not substituted for total PAT. Operating profit proxy is direct profit before exceptional items and tax, minus other income, plus finance costs and depreciation, and is available only when all of those components are present. It is not reconstructed by dividing annual values.

YoY revenue growth is reported only when prior-year revenue is positive. YoY operating-profit growth and PAT growth are reported only when their respective prior-year comparator is positive. Loss-to-profit and profit-to-loss flags retain sign transitions that percentage growth cannot represent. `tiny_base` means absolute prior-year same-quarter PAT below INR 2 crore. `negative_pat` refers to current-quarter PAT below zero.

`revenue_scale_log = ln(current quarterly revenue in INR)` for positive revenue. `median_20d_traded_value_log = ln(median prior-20-session traded value in INR)` for positive traded value. `nonoperating_share_of_pbt = (abs(other income) + abs(exceptional items)) / abs(PBT)` only when all three components exist and PBT is nonzero. `quality_warning_nonoperating` is true at a ratio of at least 0.30.

## Pre-event market features

All pre-event features end at the last fully observable session close before the result publication timestamp. For publications before market close, the same day's final bar is not used. For publications after market close, that session's completed bar may be used.

- prior 1/5/20-session returns are close-to-close percentage returns ending at the pre-event close;
- distance to 60-session high is `100 * (pre-event close / max high over the last 60 completed sessions including the pre-event session - 1)`;
- prior-20-session volatility is the sample standard deviation, in percentage points, of the 20 one-session close returns ending at the pre-event close;
- liquidity is the median traded value of the 20 completed sessions ending at the pre-event session.

At least 60 completed sessions plus the data needed to form 20 daily returns are required. A whole-market missing session never compresses these windows.

## H005-B first-session reaction

The reaction session is the first complete NSE trading session after publication. It is never a partial publication-day session. H005-B may use exactly that one complete session and no later information.

- `reaction_1d_pct` is reaction-session close versus the immediately preceding exchange-session close;
- volume ratio and traded-value ratio use the reaction session divided by the median of the immediately preceding 20 completed sessions;
- `reaction_range_pct = 100 * (high - low) / open`;
- `reaction_close_location = (close - low) / (high - low)`, missing for a zero-range bar;
- `reaction_nifty500_excess_pp` is reaction close-to-close percentage return minus the Nifty 500 close-to-close return over the identical sessions.

## Corporate actions

Only source-backed EQ-series share-basis actions are mechanically adjusted. The ex-date change applies from that session's open.

- face-value split from old face value to new face value: share factor `old / new`;
- consolidation from old face value to new face value: share factor `old / new`;
- bonus `A:B`: share factor `(A + B) / B`.

For a consistent later share basis, pre-action prices are divided by the cumulative future share factor and pre-action volumes are multiplied by it. Traded value is not mechanically adjusted. Multiple unambiguous actions compound.

If a required pre-event, reaction or label window crosses a material share-basis action that cannot be deterministically parsed from the retained exchange record, the event is excluded. Cash dividends are not price-adjusted. Rights issues, demergers, mergers and other unresolved structural events are not guessed.

## Entries and forward labels

H005-A enters at the open of the first complete trading session after publication. H005-B observes that complete reaction session and enters at the next eligible session open. An entry bar with zero range is treated as non-executable with daily OHLC evidence and is excluded rather than assigned a favorable fill.

The forward window contains exactly 20 exchange sessions including the entry session as session 1. `label_end_date` is session 20 even when +25% was reached earlier, and that full date is used for CV purging.

`explosive_20d_v1` is true when the maximum corporate-action-adjusted high in those 20 sessions is at least 25% above the corporate-action-adjusted entry open. `lead_sessions_to_25pct` is one-based, so a threshold touch on the entry session has lead 1. The 20-session close return is entry open to session-20 close.

Nifty 500 20-session return is index open on the stock entry date to index close on the same label-end date. Stock minus index return, in percentage points, is the broad-market excess diagnostic.

A maximum intraday high label remains a maximum-excursion target, not a realized portfolio profit. OHLC entry/exit values are execution proxies. No transaction-cost or portfolio-capacity claim is implied.

## Determinism and evidence classification

Event identity is the deterministic combination of symbol, quarter end, reporting basis, first publication timestamp and H005 variant. Equal model or baseline scores are broken by event identity. Source hashes, parser status, exclusions, entry date and label-end date are retained for every row.

Top-5/10/20-percent whole-window ranking remains a retrospective discrimination diagnostic. It is not silently reclassified as an online allocation rule. Historical design diagnostics, the frozen untouched holdout and future prospective paper evidence remain separate evidence classes. Live capital remains disabled.
