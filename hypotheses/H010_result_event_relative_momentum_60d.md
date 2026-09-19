# H010 — Result-event 60-session relative-momentum continuation

## Status

**FROZEN FOR INDEPENDENT HISTORICAL ROBUSTNESS TEST — 2026-09-08**

Live capital: **NO**

H010 is a new hypothesis. It was selected after the preregistered prior-60-session relative-momentum comparator was the strongest medium-horizon signal in both H008 design diagnostics and H009's April-May 2026 validation-era comparator table. Those 2026 outcomes are therefore design evidence only for H010.

No 60-session outcome from the 2024-10-01 through 2025-06-30 H010 robustness window has been opened in this continuation at freeze time.

## Hypothesis

> Among sufficiently liquid companies reporting results, strong stock performance relative to Nifty 500 over the 60 completed sessions before the result event identifies persistent business/market leadership that continues over the subsequent 60-session fixed holding period.

The signal is deliberately simple. H010 tests whether the market trend itself contains a durable medium-horizon company-selection edge. It does not claim that the result announcement causes the future return.

## Universe

One observation per NSE main-board EQ-series company-quarter result event.

- result publication must be retained from an official NSE result listing;
- median traded value over the 20 completed sessions ending at the pre-event session must be at least INR 2 crore;
- at least 61 completed stock bars must exist through the pre-event session;
- the exact 60-session forward holding window must exist without compressing missing stock bars;
- material unresolved structural corporate actions crossing the signal or holding window fail the observation closed;
- no nominal share-price filter;
- financial companies are not excluded.

For multiple result filings for one symbol and quarter, prefer consolidated basis when available, otherwise standalone, and use the earliest valid publication in that chosen basis. This selection is made without forward returns.

## Decision timing

Use the same conservative event timing as the H005-B/H008/H009 experiments for comparability.

- `first_publication` is the official result publication timestamp.
- The reaction session is the first complete NSE trading session after publication. If publication occurs before that session's open, that day may be the complete reaction session. A publication during or after the session makes the next market session the reaction session.
- Entry is the open of the immediately following eligible session.

The H010 signal uses no reaction-session price or volume information. Entry is deliberately not moved earlier after seeing the 2026 evidence.

## Signal

Let `pre_event_session` be the last fully observable stock session close before publication.

Let `pre60_start` be the stock/session-calendar observation exactly 60 market sessions before `pre_event_session`.

Using corporate-action-adjusted stock closes and official Nifty 500 closes over the identical two session dates:

`stock_prior_60_pct = 100 * (stock_pre_event_close / stock_pre60_start_close - 1)`

`nifty_prior_60_pct = 100 * (nifty_pre_event_close / nifty_pre60_start_close - 1)`

`H010_score = stock_prior_60_pct - nifty_prior_60_pct`

There are no fitted parameters, percentile transformations, sector adjustments, accounting variables, reaction variables, thresholds, winsorization or learned models. Rank descending by the raw score. Exact ties are broken by deterministic event identity.

## Target

Primary target:

`excess_60d_pp = stock_adjusted_session60_close_return_from_entry_open_pct - nifty500_same_dates_open_to_close_return_pct`

The forward holding window contains exactly 60 common market sessions including the entry session as session 1. `label_end_date` is session 60. Missing stock bars do not shorten the horizon.

Secondary diagnostics:

- raw stock 60-session close return;
- Nifty 500 beat rate;
- fraction with excess >= +5 percentage points;
- fraction with raw return >= +10%;
- maximum company contribution to aggregate positive gross close-return P&L.

## Independent historical robustness window

The frozen test period is result publications from **2024-10-01 through 2025-06-30**, Asia/Kolkata.

This period is chronologically earlier than the 2026 evidence that motivated H010. It is therefore a backward-time generalization test, not a claim that the signal was trained and traded contemporaneously in 2024-25. Its 60-session outcomes were not inspected when H010 was frozen.

No validation dates may be substituted after outcomes are opened. If source or market coverage is inadequate, report `ROBUSTNESS_COVERAGE_INSUFFICIENT`.

## Primary operating point

Top 10% of H010 scores within the completed evaluable robustness cohort. Top 5% and top 20% are diagnostics only and cannot replace the primary result.

Matched-count comparisons:

- prior-20-session stock return;
- unconditional cohort;
- first-complete-reaction-session tape composite, reported only as a comparator and not incorporated into H010;
- random matched-count prevalence/return distribution via a fixed deterministic bootstrap seed 101.

## Frozen robustness gate

H010 passes the historical robustness test only if all are true at top 10%:

- at least 1,000 evaluable result events in the full robustness cohort;
- at least 100 selected observations;
- median Nifty 500 60-session excess > +3.0 percentage points;
- mean Nifty 500 excess > +3.0 percentage points;
- Nifty 500 beat rate > 55%;
- median raw stock 60-session return > 0;
- at least 40% of selected observations have excess >= +5 percentage points;
- H010 median excess exceeds matched top-10% prior-20-session momentum;
- H010 median excess exceeds the unconditional cohort median by at least 3.0 percentage points;
- no single company contributes more than 20% of aggregate positive gross close-return P&L;
- among calendar-quarter cohorts with at least 20 selected observations, none has median excess below -2 percentage points;
- a fixed-seed 10,000-draw random matched-size test has empirical one-sided p < 0.05 for both selected-group median excess and mean excess.

No gate, percentile, horizon or signal definition may change after the first 2024-25 60-session outcome is computed.

## Evidence classification and next gate

A pass is `HISTORICAL_ROBUSTNESS_PASS`, not prospective validation. Because H010 was chosen after inspecting 2026 comparator performance, even a strong backward historical result is insufficient for live capital.

If and only if this robustness gate passes, freeze a prospective paper rule before the next unseen result cohort begins. That rule must define an online score threshold or rolling cross-sectional allocation that can be known at decision time, position sizing, maximum concurrent exposure, costs, exits and benchmark accounting. Live capital remains disabled until that prospective cohort independently passes its own predeclared gate.
