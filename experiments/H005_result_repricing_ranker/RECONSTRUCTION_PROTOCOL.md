# H005 source reconstruction and baseline conventions

Recorded 2026-09-08 before the first real-market H005 model fit in this continuation. The frozen hypothesis and SPEC are unchanged. The 2024-10-01 through 2025-06-30 holdout return labels have not been opened.

## Evidence status

The repaired H005 library is distinct from research evidence. The new reconstruction will first produce DESIGN diagnostics from the frozen 2025-10-01 through 2026-07-31 event window. Any partial-source fit remains explicitly partial and cannot serve as a final model freeze or validation pass. Acquisition, parser repairs and this predeclared baseline specification must not be selected using model performance.

## Baselines fixed before fitting

Each numerical baseline is fitted without using labels or forward returns. For each feature, transform a value to its training empirical mid-CDF: (number of training values strictly below it + half the number equal to it) / number of finite training values. Use the training median for missing values. A completely unavailable training feature contributes a constant 0.5.

- First-session tape: equal mean of reaction return, reaction volume ratio against the prior 20-session median, and reaction close location. H005-B only. No later reaction is allowed.
- Accounting growth: equal mean of revenue growth, operating-profit growth, PAT growth and operating-margin change.
- Pre-event momentum: the prior 20-session return.
- Numeric H004 earnings anchor: revenue growth >=20%, operating-profit growth >=30%, PAT growth >=40%, margin change >=1 percentage point or loss-to-profit, and current PAT >=2 crore. This is only a numeric-anchor diagnostic, not the full qualitative H004 model. Report its natural signal count separately rather than inventing non-anchor trades to pad it to a decile.

Ranked baseline comparisons use exactly the model's retrospective signal count at top 5%, 10% and 20%. Break ties by event identity. Report fold-specific and aggregate out-of-fold metrics. The selected regularization strength was chosen using those same cross-validation folds, so these are tuning diagnostics, not independent validation. No numerical baseline can certify execution.

## Source and accounting conventions

Retain original NSE listing responses, original native XBRL or explicitly exchange-listed display documents, original daily UDiFF bhavcopies, original Nifty index snapshots and corporate-action records. Verify their SHA-256 hashes before reconstruction. Rebuild prices from original bhavcopy ZIPs rather than trusting a derived price table. Verify normalized publication metadata against the original listing rows.

Use exact symbol, reporting basis and explicit quarter period. Native INR monetary facts require an INR unit. Display tables require an explicit presentation currency and scale. Never divide annual facts by four. Never assume missing finance costs, depreciation, exceptional items or other income are zero. If a legacy context's period dates disagree with that same context's explicit reporting-period date facts, reject that context rather than mixing quarter and year-to-date figures.

Only total-period PAT is a total-profit observation. Continuing-operations profit alone is not substituted for total PAT. A current document with no usable explicit quarterly monetary facts is retained as an exclusion, not admitted with a wholly imputed accounting vector. Missing prior-year fields remain missing and use the frozen model's fold-local missingness policy.

Operating-profit proxy is profit before exceptional items and tax, minus other income, plus finance costs and depreciation, only when the components are present. Tiny-base flag means absolute prior-quarter PAT below 2 crore. Nonoperating-share diagnostic uses absolute other income plus absolute exceptional items, divided by absolute nonzero PBT, only with all required facts available.

## Time and price conventions

The design calendar must match NSE circulars and the exact common set of retained bhavcopy and index dates. Include the October 21, 2025 special session and February 1, 2026 Sunday session. Apply the January 15, 2026 holiday amendment. Retain the original circulars. No missing whole-market day or missing stock bar may compress a 20-session horizon.

Use only fully observable pre-publication closes. The first complete post-publication session determines the B reaction, with the exact immediately preceding exchange-session close. Variant A enters at the next eligible open. Variant B enters at the open after its first complete reaction session. An entry day counts as session one of the forward 20-session window. Purging uses the end of the entire label window, even when +25% is touched earlier.

Apply only parsed, source-backed split/bonus/consolidation share-basis changes. Do not invent adjustments for unresolved rights, demergers or other unknown actions. Reject flat/no-trade entry bars instead of assigning impossible fills. Cash dividends, transaction costs and portfolio constraints are not included in gross price-return diagnostics.

## Limits that remain explicit

Integrated-filing publication has not independently been proven to be the first results-announcement timestamp. Its use must be labelled, and an earliest-announcement audit remains a promotion blocker. A daily high is a maximum-excursion label, not realized profit. OHLC open/close fills remain execution proxies. Equal-notional positive gross return concentration is not a capital-constrained portfolio P&L statistic.

The original H004 design count of 2,182 events and 77 movers was not recovered exactly. Reachable retained versions contain 2,221/80 and 1,845/76. Their overlap is consistent, but they have acquisition coverage differences and a five-event April-June 2026 gap. New source coverage must be reported independently rather than relabelling the old count.

Live capital remains disabled. A design fit, a tuning-CV success or a successful data acquisition workflow does not authorize a historical validation pass or an investment recommendation.
