# India earnings-edge feasibility pilot — 2026-09-06

## Question

Can a simple earnings-information signal identify liquid Indian equities that outperform after the immediate result reaction?

## Design

A 25-company late-July-2025 result cohort was selected before inspecting post-event holding-period returns. Exact delayed-entry/exit prices were independently verified for 24 names.

Execution convention:

- ignore result day and first subsequent session
- enter at the open of the second trading session after the result
- hold exactly 20 trading sessions
- exit at close
- compare with Nifty and momentum exposure over matching windows

This is a historical feasibility pilot. It is not a production-grade point-in-time backtest.

## H001 — raw earnings acceleration

Frozen score:

```text
sales_yoy_pct + op_profit_yoy_pct + 5 * opm_change_pp
```

Result:

- Pearson correlation with subsequent Nifty excess return: 0.066, p = 0.758
- Spearman correlation: 0.035, p = 0.872

**Verdict: REJECTED.**

Raw growth does not measure market surprise. Strong growth can disappoint high expectations and weak growth can beat depressed expectations.

## H002 — unexpected earnings / PEAD

Literature-style UE:

```text
(EPS_t - EPS_t-4) / price_day_minus_2
```

Ranked magnitude result:

- Pearson: 0.214, p = 0.315
- Spearman: 0.230, p = 0.281
- highest-UE quintile excess: -2.58 pp
- lowest-UE quintile excess: -1.80 pp

No clean ranked PEAD replication appeared at the 20-session horizon.

The implementable sign split was more interesting:

- positive UE: +1.99 pp average excess vs Nifty, 62.5% beat rate, n=16
- negative UE: -1.17 pp average excess, 37.5% beat rate, n=8
- spread: +3.16 pp
- p = 0.233
- bootstrap 95% CI: -1.67 pp to +7.96 pp

Winner-removal tests materially weaken the spread.

**Verdict: INCONCLUSIVE.** No live capital.

## Other failed intuition

The first post-result price reaction did not predict the subsequent 20-session excess return in this pilot. Chasing result-day gainers therefore has no support from this sample.

## External prior

Indian PEAD evidence exists in larger historical studies, so this pilot does not disprove the anomaly. Relevant references include:

- NSE/IGIDR working paper: https://nsearchives.nseindia.com/research/content/NSE-IGIDR-WP4-14-15.pdf
- NSE research on insider trading and PEAD: https://nsearchives.nseindia.com/research/content/1516_BS3.pdf
- Sen (2009), Journal of Contemporary Accounting & Economics: https://www.sciencedirect.com/science/article/abs/pii/S1815566909000034
- recent BSE 500 event study: https://eelet.org.uk/index.php/journal/article/view/4174

## Data limitation

Historical consolidated quarterly tables were viewed after the fact. They may incorporate later restatements or presentation changes. A prospective test must capture original exchange filings and consensus snapshots at release time.

## Decision

1. H001 is permanently rejected unless a materially new hypothesis is registered.
2. H002 receives a prospective paper test only.
3. No live capital is authorized.
4. Complexity is not allowed to outrun evidence.
