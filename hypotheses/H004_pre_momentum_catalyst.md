# H004 — Pre-momentum catalyst repricing

Status: **FROZEN FOR HISTORICAL REPLAY**  
Live capital: **NO**

## Question

Can public information available before obvious stock-level momentum identify Indian equities that subsequently make an investable explosive move?

The target is not generic momentum. The target is the **conditions that create momentum**: earnings inflection, operating turnaround, quantified corporate catalysts, sector support, valuation/expectation gaps, and balance-sheet capacity.

## Mechanism

Large short-horizon moves often begin when a material change in a company's earnings path or business trajectory is not yet fully reflected in price. A second class begins after a discrete public catalyst such as a control transaction, material order, commercial commissioning, regulatory approval, or quantified expansion. Stock-level price/volume behaviour is used only as an entry confirmation after a company has entered the information-driven watchlist.

## Two-stage signal

### Stage 1 — information watchlist

A company can enter the watchlist only through a non-price anchor:

1. **earnings inflection**, or
2. **operating turnaround**, or
3. **material quantified corporate catalyst**.

The watchlist ranking may use:

- revenue / operating-profit / PAT growth and acceleration,
- margin inflection,
- earnings quality and one-off detection,
- balance-sheet capacity,
- valuation versus sector / own history,
- sector breadth and fund-flow context,
- quantified orders, M&A/control changes, capacity commissioning, regulatory approvals, guidance revisions, or network expansion,
- expectation gap after an earnings event when the price has not already repriced materially.

Stock-level momentum is prohibited from Stage 1.

### Stage 2 — early execution trigger

Price and volume may be used only to decide **when** an already-qualified watchlist name is beginning to reprice. The trigger is deliberately early and may not use an upper-circuit close as a successful entry signal.

## Primary outcome

From the first eligible next-session execution price after the signal:

```text
explosive_20d_v1 = max_forward_20_session_return >= 25%
```

Secondary outcomes:

- `max_forward_10_session_return >= 20%`,
- `max_forward_20_session_return >= 40%`,
- excess return versus Nifty 500 and sector benchmark,
- maximum adverse excursion before the maximum favourable excursion.

## Pre-momentum requirement

At the Stage-1 decision timestamp, the stock must not already have obvious explosive momentum:

- prior 5-session close-to-close return < 10%,
- prior 20-session close-to-close return < 20%,
- no prior-session gain >= 8%.

Fresh after-hours catalysts are evaluated before the next trading session and therefore do not fail the pre-momentum rule because of a move that has not yet occurred.

## Universe and executability

No nominal share-price boundary is used.

Primary universe:

- NSE main-board common equity / EQ-series securities,
- no SME securities, ETFs, REITs, InvITs or suspended securities,
- median 20-session traded value >= ₹2 crore before the decision timestamp.

Secondary discovery tier:

- median 20-session traded value >= ₹25 lakh,
- paper-only and reported separately,
- never mixed with the primary executable result.

A signal is `NOT_EXECUTABLE` when the next-session entry cannot realistically be obtained because of one-sided circuit conditions or insufficient offered liquidity. Such cases remain in discovery recall statistics but not executable P&L.

## Evaluation

The primary research objective is **recall of future explosive movers with acceptable precision**, not merely average portfolio return.

Required metrics:

- recall of all future primary-universe `explosive_20d_v1` movers,
- precision of Stage-1 watchlist and Stage-2 triggers,
- median lead time before the first +10%, +20% and +25% move,
- executable hit rate,
- false-positive rate,
- missed-mover audit,
- mean and median 5/10/20-session return,
- max adverse excursion,
- sector- and Nifty-500-relative returns,
- comparison with earnings-only and momentum-only baselines.

## Leakage discipline

- public source timestamp must be <= decision timestamp,
- restated or later-tagged earnings quality cannot alter an earlier signal,
- no future price, volume, news or analyst recommendation may enter Stage 1,
- Stage-2 uses only tape information observed after Stage 1 and before entry,
- the August 31–September 7, 2026 recent-winner study is a **design set only** and may not be used as validation evidence,
- weights/thresholds frozen here cannot be optimized against that design set,
- all historical replay is labelled reconstructed, not prospective,
- the first true prospective cohort begins after this rule is frozen.

## Relationship to H001–H003

H004 is independent.

- H001 showed raw accounting growth alone was insufficient.
- H002 remains `EXPLORATORY_ONLY` and may not be imported into H004's primary signal.
- H003 remains a management-delivery experiment and unresolved commitments may not be used as evidence of execution.

H004 deliberately adds event semantics, earnings quality, expectation gap, and executability while keeping stock-level momentum out of the watchlist stage.
