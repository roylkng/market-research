# H012 — Regime-aware prior-60 full-market momentum

Frozen: 2026-09-08 before any H012 full-market cohort return was calculated on the 2024-12 through 2025-06 challenge window.

Status: **FROZEN HISTORICAL CHALLENGE. LIVE CAPITAL DISABLED.**

## Motivation

H011's primary 120-session momentum-with-skip score failed its frozen challenge. In those same active cohorts, the preregistered prior-60-session comparator produced higher mean Nifty 500 excess than H011. H012 promotes that simpler comparator into a new hypothesis without changing H011 or reusing H011's window as validation.

H012 removes earnings events and learned models entirely. It asks whether liquid NSE EQ stocks with the strongest previous 60-session returns continue to outperform over the next 60 sessions, but only while the Nifty 500 is itself in a supportive trend regime.

## Historical challenge window

Monthly decisions from **2024-12-01 through 2025-06-30**, using the last retained common NSE trading session of each calendar month. Exact market data may begin earlier to support lookbacks, and exits may extend through 2025-09-30.

This older corpus was previously used for event-conditioned H010, but H012's full-market monthly cohorts and their outcomes have not been calculated before this freeze. A pass remains historical evidence only and requires prospective paper validation.

## Universe

At each monthly decision:

- NSE cash-market `EQ` series stocks from retained official daily bhavcopy data.
- Complete stock bars on every common market session required by the 125-session auxiliary comparator lookback, prior-20 liquidity window, entry and 60-session holding window.
- Median traded value over the 20 sessions ending at the decision >= INR 2 crore.
- At least 200 eligible stocks for an active cohort.
- No unresolved structural corporate action from 125 common sessions before decision through the frozen exit.
- Flat/no-trade entry bars rejected.

No result-event, earnings, valuation, sector, market-cap or nominal-price filter.

## Regime rule

A monthly cohort is ACTIVE only if both are true on the decision session:

1. Nifty 500 close > its 120-common-session simple moving average, including the decision close.
2. Nifty 500 prior-60-session close return > 0.

If either is false, the month is `REGIME_OFF` and no stock is selected.

## Primary score

`momentum_60 = close[t] / close[t-60] - 1`

Rank descending within each active cohort. Break ties by symbol. Select exactly `ceil(10% * eligible_count)`, with minimum selection count 20.

There are no fitted parameters or tunable thresholds.

## Execution and outcome

- entry: next common NSE session open,
- exit: close of the 60th holding session, entry session counted as holding session 1,
- stock return: exit close / entry open - 1,
- benchmark: Nifty 500 open on the same entry session to Nifty 500 close on the same exit session,
- excess: stock return minus benchmark return,
- equal-weight cohort arithmetic means.

No transaction costs, taxes, slippage or financing are included in this first gross edge test.

## Frozen comparators

At matched selected count per active cohort:

1. prior-20-session stock momentum,
2. H011-style `close[t-5] / close[t-125] - 1`,
3. full eligible cohort,
4. deterministic matched random selections using seed `112` and 10,000 aggregate draws.

## Frozen gates

All must pass:

- at least 3 active monthly cohorts,
- at least 250 selected stock-observations,
- median active-cohort Nifty 500 excess > +2 pp,
- mean selected-stock Nifty 500 excess > +2 pp,
- median selected-stock Nifty 500 excess > 0,
- selected-stock Nifty 500 beat rate >=55%,
- at least two-thirds of active cohorts have positive equal-weight excess,
- H012 mean selected-stock excess >= prior-20 comparator mean excess +1 pp,
- H012 mean selected-stock excess >= H011-style 120/5 comparator mean excess,
- H012 mean selected-stock excess >= full eligible cohort mean excess +2 pp,
- one-sided fixed-seed matched-random empirical p-value for mean excess <=0.05,
- no single symbol contributes >15% of aggregate positive gross selected-stock return,
- no calendar quarter containing >=2 active cohorts has non-positive median active-cohort excess.

`PROMISING` additionally requires median active-cohort excess >= +4 pp and selected-stock beat rate >=60%.

## Audit rule

After the first H012 cohort outcome is calculated, the 60-session signal, regime filters, liquidity floor, top-decile operating point, 60-session holding horizon, comparators and gates cannot change under H012-v1. Failure retires H012-v1.
