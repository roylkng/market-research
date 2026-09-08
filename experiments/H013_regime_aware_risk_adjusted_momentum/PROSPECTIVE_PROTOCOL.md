# H013 prospective paper protocol

Frozen: 2026-09-08

Status: **PROSPECTIVE PAPER ONLY. LIVE CAPITAL DISABLED.**

## Objective

Test the already frozen H013 rule on decisions whose 60-session outcomes were unknown when the candidate lists were created. Historical H013 parameters, regime thresholds, score, liquidity floor, top-decile selection and 60-session horizon may not change.

## Start

First eligible monthly decision after this protocol freeze. The first possible decision is the final NSE trading session of September 2026.

## Decision capture

After 20:00 Asia/Kolkata on every NSE trading session that could be the final trading session of a calendar month:

1. retain exact official NSE daily EQ bhavcopy bytes,
2. retain exact Nifty 500 daily index source bytes,
3. retain the corporate-action source evidence required by the H013 lookback,
4. determine from the retained NSE session calendar whether this is the final trading session of the month,
5. compute the frozen H013 regime flag and score using only data available through that session,
6. if regime is off, retain a `REGIME_OFF` monthly record and no stock list,
7. if regime is active, freeze the complete eligible universe and exact top-decile candidate list with source hashes before the next session opens.

A candidate list created after the next session open is invalid prospective evidence.

## Frozen H013 signal

Unchanged:

`risk_adjusted_momentum = (close[t-5] / close[t-125] - 1) / (sample_std(120 daily log returns) * sqrt(120))`

Regime must satisfy:

- Nifty 500 close > 120-session SMA,
- Nifty 500 prior-60-session return > 0.

Universe remains EQ series, complete required common-session bars, median prior-20-session traded value >= INR 2 crore, >=200 eligible names, unresolved structural actions excluded, flat entry bars excluded.

Select exact top 10%, tie by symbol.

## Paper execution

- entry: official next common NSE session open,
- exit: official close of the 60th holding session, entry session counted as 1,
- benchmark: Nifty 500 same entry open to same exit close,
- gross excess: stock return minus Nifty 500 return.

## Conservative friction diagnostic

In addition to gross returns, report a frozen **0.50% round-trip execution-friction deduction per selected stock**. This is deliberately conservative relative to direct statutory charges alone and is intended to absorb brokerage/exchange charges plus modest open/close slippage. It is not an investor-specific tax model.

`net_paper_stock_return = gross_stock_return - 0.005`

`net_paper_excess = net_paper_stock_return - nifty500_return`

No later choice of a lower cost estimate may rescue a failed cohort.

## Prospective checkpoints

Do not promote from a single cohort.

### EARLY_SIGNAL checkpoint

After at least:

- 3 ACTIVE monthly cohorts,
- 250 selected stock observations,
- all corresponding 60-session exits complete.

Required simultaneously:

- mean net paper Nifty 500 excess > +1.5 pp,
- median net paper excess > 0,
- selected-stock net beat rate >=52%,
- at least 2 of 3 active cohorts positive equal-weight net excess,
- no single symbol >15% of aggregate positive net paper return.

Classification if passed: `PROSPECTIVE_EARLY_SIGNAL`. Still no live capital.

### PROMOTION checkpoint

After at least:

- 6 ACTIVE monthly cohorts,
- 500 selected observations,
- at least two distinct calendar quarters with >=2 active cohorts,
- all corresponding exits complete.

Required simultaneously:

- mean net paper Nifty 500 excess > +2.0 pp,
- median net paper excess > +0.5 pp,
- selected-stock net beat rate >=55%,
- >=75% of active cohorts positive equal-weight net excess,
- every quarter with >=2 active cohorts has positive median cohort net excess,
- max single-symbol positive-return contribution <=15%,
- matched-count random-selection one-sided empirical p-value <=0.05 using fixed seed `13130` and 10,000 draws.

Historical H013 evidence must remain separately passing. If these gates pass, H013 may be classified `PAPER_VALIDATED_CANDIDATE` for a separate capital-allocation review. The research harness itself still does not automatically authorize live capital.

## Failure / mutation rule

If the prospective gates fail, H013-v1 is not tuned. Any change to lookback, volatility estimator, regime threshold, operating percentile, liquidity floor, holding horizon or execution rule becomes a new hypothesis and starts a new prospective clock.
