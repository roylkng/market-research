# AE001-T012 Outcome and Evaluation Protocol P1

Status: **frozen October 14, 2026, before T012's first eligible October 15 feature session**. Live capital disabled.

This supplements but **does not alter** the registered T012 five-session primary, one-session non-rescuing secondary, frozen T006 model coefficients, or decision clock. H021, H022, and the separate hidden-gem HG-series remain unaffected.

## Immutable time and source basis

T012's forecast for complete market session D is sealed before **08:30 IST on the next frozen NSE cash trading session N**. Only predictions actually committed to GitHub before their deadline enter this evaluation. A simulated or hypothetical 09:15 exchange open is **not a fill**.

Primary return = stock official exit close / stock official entry open - 1, minus Nifty 500 **price-index** official exit close / price-index official entry open - 1. Entry is N open, exit is holding session five close with N counted as session one. Exactly the frozen exchange calendar determines all intervening sessions. Corporate action and identity change invalidate affected stock observations rather than manufacturing adjusted returns. Nifty 500 price-index excess is not a total-return excess claim. Brokerage, spread, market impact and fill feasibility remain a separate gate.

The official original NSE CM equity UDiFF, Nifty 500 index snapshot, and corporate-action source must be retrieved at **real observation time**, no earlier than the final observed market close. Raw market and index source bytes are content-addressed and retained with published outcome artifacts. An original 404 or missing index/price must remain missing until a genuinely later official observation succeeds. A late outcome source is acceptable because it was not used in the already-sealed prediction. A late decision source is **never** acceptable.

The evaluator must reject a five-session outcome if **any** frozen intermediate trading session is missing, no matter whether a later session has data. This blocks accidental horizon extension in an apparently contiguous list of downloaded exchange files.

## Confirmatory cohort and inference

Primary is the **smallest chronological prefix** of real source-qualified T012 decisions containing:
- at least 60 unique decisions,
- fully observed H5 outcomes for every included decision,
- at least 50 valid paired cross-sectional rank-IC sessions.

Compute paired FULL37 minus CORE27 Newey-West (lag 4) daily rank IC and top-minus-bottom-decile spread on exactly the same eligible stock identities. Both deltas must be positive with **two-sided p < 0.05**. Other diagnostics cannot rescue a failed primary. Report the global RTA001 multiple-testing adjustment separately. H1 one-session secondary uses the identical primary cohort and lag 5. All outcomes and analyses are append-only.

A scientific result remains unproven until the future data mature. Merely implementing this contract creates neither expected-return estimates nor trading authorization.
