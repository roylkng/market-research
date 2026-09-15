# H013 independent robustness protocol — 2023 to 2024

Frozen: 2026-09-08 before any H013 cohort outcome from this period was calculated.

Status: **FROZEN INDEPENDENT HISTORICAL ROBUSTNESS. LIVE CAPITAL DISABLED.**

## Purpose

H013 passed two historical challenge windows whose raw-momentum behavior influenced the hypothesis path. This additional replay tests the already frozen H013 rule on an earlier market period not previously used to calculate H013 scores or H013 portfolio outcomes.

The H013 signal, regime rule, universe, top-decile operating point, 60-session horizon and execution convention are unchanged.

## Market source window

Acquire official NSE cash-market end-of-day data from **2022-06-01 through 2024-06-30** so the first decision has the full 125-session signal history and the last decision has the full 60-session holding window.

Primary legacy equity bhavcopy source convention:

`https://archives.nseindia.com/content/historical/EQUITIES/YYYY/MON/cmDDMONYYYYbhav.csv.zip`

Daily Nifty index source convention:

`https://archives.nseindia.com/content/indices/ind_close_all_DDMMYYYY.csv`

Retain exact downloaded bytes and SHA-256. A trading session exists only when the official EQ bhavcopy is available and parseable. Every retained trading session must have a matching parseable Nifty 500 index snapshot. Missing index data on a bhavcopy trading day fails the replay rather than compressing the calendar.

Retain NSE corporate-action responses covering the complete source window. Structural share-basis actions remain conservative exclusions as in H013's prior challenges.

## Decision window

Monthly decisions from **2023-01 through 2024-03**, using the last retained common trading session of each calendar month.

No result-event or earnings filter.

## Frozen H013 rule

Cohort is active only when:

1. Nifty 500 close > its 120-common-session simple moving average including decision close.
2. Nifty 500 prior-60-session close return > 0.

Universe:

- EQ series,
- complete common-session stock bars from t-125 through exit,
- median prior-20-session traded value >= INR 2 crore,
- at least 200 eligible names,
- unresolved structural corporate actions excluded,
- flat entry bars excluded.

Primary score is unchanged:

`(close[t-5] / close[t-125] - 1) / (sample_std(120 daily log returns t-125..t-5) * sqrt(120))`

Select exactly top 10%, tie by symbol. Enter next common-session open and exit the 60th holding-session close.

## Comparators

Matched count per active cohort:

- raw 120/5 momentum,
- prior-60 momentum,
- prior-20 momentum,
- full eligible cohort,
- deterministic matched random draws, seed `1313`, 10,000 draws.

## Frozen independent robustness gates

All must pass:

- at least 5 active monthly cohorts,
- at least 500 selected stock-observations,
- mean selected-stock Nifty 500 excess > +2 pp,
- median selected-stock excess > 0,
- selected-stock beat rate >=52%,
- at least two-thirds of active cohorts have positive equal-weight excess,
- H013 mean excess >= raw 120/5 comparator mean excess,
- H013 mean excess >= prior-60 comparator mean excess,
- H013 mean excess >= full eligible cohort mean excess +2 pp,
- one-sided matched-random empirical p-value for mean excess <=0.05,
- no single symbol contributes >15% of aggregate positive gross selected return,
- no calendar quarter containing >=2 active cohorts has non-positive median active-cohort excess.

If this replay passes, H013 may be classified `HISTORICALLY_ROBUST_PENDING_PROSPECTIVE`. It still cannot enable live capital. Prospective paper validation remains mandatory.
