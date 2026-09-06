# H001 — Raw earnings acceleration

## Status

`REJECTED`

## Hypothesis

Among liquid non-financial Indian equities, stronger year-on-year sales growth, operating-profit growth, and operating-margin expansion should predict superior 20-session returns after the immediate earnings reaction.

## Frozen signal

```text
score = sales_yoy_pct + op_profit_yoy_pct + 5 * opm_change_pp
```

## Decision rule

- Do not trade the event day or first subsequent trading session.
- Enter at the open of the second trading session after the result.
- Hold exactly 20 trading sessions, exit at close.
- Compare with Nifty 50 and a simple momentum benchmark.

## Feasibility result

24 observations had independently verified delayed-entry/exit prices.

- Pearson correlation with 20-session Nifty excess return: **0.066**
- p-value: **0.758**
- Spearman correlation: **0.035**
- p-value: **0.872**

The signal had essentially no relationship with subsequent excess return.

## Why it failed

Raw accounting growth is not information surprise. A company can report very strong growth while still disappointing expectations already embedded in price. Valuation, consensus, positioning, and prior price behaviour matter.

## Decision

**Reject. Do not revive by adding arbitrary weights or filters.**

A materially different surprise-based formulation requires a new hypothesis ID/version.
