# AE001-T012: prospective pre-open same-session futures confirmation

Frozen registration date: **2026-10-13**. Status: **prospective, awaiting first eligible decision**. Live capital: **DISABLED**.

## Mechanism, not an investment recommendation

AE001-T005 reported nominal historical information gain from ten stock-futures features versus a 27-feature price/liquidity/delivery model. However, the multiple-testing-adjusted historical result is **not statistically robust** under RTA001. AE001-T006 was blocked because same-day futures files arrived after its 18:30 IST decision deadline. AE001-T011's lagged-futures historical challenge failed its primary endpoint.

AE001-T012 is a distinct, preregistered prospective test of the same-session-D futures information set with a causal **next-trading-morning** cutoff. It neither changes T005/T006/T011 nor retroactively rescues their outcomes.

## Source and calendar readiness observed before freeze

- Frozen NSE CM calendar: \`NSE-CM-FY27Q2-v1\`, hash \`2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce\`.
- AE001-SC003 official F&O source first available before the following trading morning's 08:30 IST cutoff for **three distinct target sessions: October 1, 5, 12, 2026**.
- These three observations test timing only. None may become a retrospective T012 prediction.
- First permitted new **feature/target session D: 2026-10-15**. First possible entry **N: 2026-10-16**, conditional on all source, model, delivery, corporate-action, and common-stock gates. No schedule assures eligibility.

## Frozen decision clock

1. D is a **completed official NSE trading session**, not a calendar-day approximation.
2. Official D NSE cash UDiFF and delivery data must have been captured and passed SC001's unchanged D **18:30 IST** cutoff.
3. Official D NSE stock-futures UDiFF must be captured and sealed under SC003 after D close and no later than **08:30 IST on the *next frozen trading session N***.
4. SC003's source attempt must be linked to the **same exact SC001 attempt SHA** and D.
5. Fixed CORE27 and FULL37 model scores are computed from the same action-safe D equity identities and 37 features. The immutable T006 model artifact and its training-source hashes are reused exactly. Model fitting, tuning, coefficient changes, and imputation are prohibited.
6. Decision artifact and immutable source manifest must be sealed no later than N **08:30 IST**, before the **N 09:15 IST open**.
7. Every missing/late/unverifiable source, less than 100 common complete stocks, incomplete 60-market/21-delivery history, unresolved corporate action, or missing futures contract means **SKIP**. A later source appearance cannot repair a missed decision.

**Source availability** and **a valid prediction** are separate gates. Three successful SC003 timing observations do not establish three valid T012 decisions.

## Frozen statistical test

Primary: one five-completed-session N-open to holding-session-five-close stock-minus-Nifty-500 return. Paired daily incremental FULL37-minus-CORE27 rank IC and paired top-minus-bottom decile spread, **both positive with two-sided Newey-West p < 0.05**, lag four. Require 60 eligible sessions, 50 valid paired IC sessions, and matured five-session outcomes for every tested decision. One-session secondary cannot rescue the primary.

The global RTA001 \`ALPHA_FEATURE_DISCOVERY_V1\` multiple-testing family counts T012 as a pending trial. Do not report a significant edge before the confirmatory tests, multiplicity accounting and actual execution cost challenge. All decisions and future outcomes must be append-only and independently reproducible. No live capital is authorized.

## Separation of responsibilities

\`src/marketlab/alpha_t012_preopen.py\` enforces trial registration and source/timestamp admission **without opening return labels or creating fills**. A separate sealed scorer, append-only decision/outcome machinery and scheduler are required for prospective evaluation. Until those operate and pass integrity tests, the trial remains registered but not producing predictions. This distinction is intentional rather than counting an unexecuted experiment as success.
