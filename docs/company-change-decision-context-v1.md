# CC001 P008: decision context and historical evidence integrity

The resumed P007 code is already merged. This change closes two substantive gaps
found against its retained live workspace and combines history, cash and price
in one research view. It does not introduce a stock-return model or trade policy.

## Corrections to actual failures

Historical AEROPLANE filings use the old symbol AMIRCHAND while retaining the same
ISIN. We do not rewrite those bytes or simply ignore symbol mismatches. A direct
old/new/effective-date match from the official NSE symbol-change registry is
required, in addition to the unchanged ISIN and accounting-scope checks. An old
filing must predate the change and the registry must have been observed. The
original symbol, canonical symbol, registry hash, source row and current
observation clock are all retained. Fuzzy aliases, multiple-hop chains, ISIN
changes, ambiguous rows and undocumented mappings continue to fail. No symbol
mapping is treated as proof of unchanged capital or EPS comparability.

A second issue was that context valuation could consume profit-attribution facts
which the cash-review layer would reject. Owner plus minority profit is now
checked against total group profit using declared source rounding, including
when a historical context record is re-evaluated. A failure or unresolvable
rounding mismatch withholds affected owner/minority comparisons and trailing
calculations. A failed annual attribution also blocks its price/EPS sensitivity.
The reported zero or conflicting amount stays in the source evidence. It is not
replaced by group profit. Revenue and cash flow remain available when their own
inputs are unaffected. A missing attribution input stays missing, not zero.

These are accounting/data-quality review conditions, not allegations about the
issuer. They require reconciliation to the full original financial statements.

## A single decision-context view

The new `company_change_decisions` module reads the latest retained context per
issuer/ISIN/scope. It checks record hashes and observation clocks, reruns source
quality and freshness rules, and displays:

- dated exchange price and reported annual-EPS reference multiple
- exact matching-period reported revenue and owner-profit changes
- trailing operating cash minus specified PPE/intangible/development purchases
- required EPS growth for the explicit price-return hurdle
- hypothesis-dependent entry prices under several declared assumptions
- the next material diligence question rather than a generic research queue

A later failed context does not silently revive an older successful one. Failed
or rejected evidence blocks affected sensitivities. Negative source purchase
signs do not become extra free cash flow. All raw financial facts are retained.

Default sensitivities use five years, a 15% annualized price-return hurdle, a 15x
exit P/E, 10/15/20% annual EPS growth and 80/100% retention of reported annual EPS.
These are unvalidated illustrative ranges, not learned forecasts or supported
normalization adjustments. The 80% case is a hypothetical haircut, not a claim
that 20% of earnings are nonrecurring. Dividends, taxes and costs are excluded.

Categories such as HURDLE_EXCEEDS_ILLUSTRATIVE_GROWTH_RANGE, FUNDING_DILIGENCE,
CASH_BASIS_REVIEW and EVIDENCE_BLOCKED describe the supplied case, not a ranked
portfolio or universal judgment about the company. No category authorizes a buy.
A different defensible exit multiple or earnings case can change the conclusion.

## Run and persistence

```bash
python -m marketlab.company_change_decisions \
  --workspace .marketlab/cc001 \
  --output-prefix .marketlab/cc001-exports/decision-context
```

Existing daily research now exports decision-context.json/html for all retained
issuer contexts. Context enrichment is still bounded to three issuers, source
intake to 40 documents, and the existing daily cadence is unchanged. Decision
export failure cannot prevent checkpointing original data. Failure status is
reported after persistence and the status/hash is cleared instead of suggesting
an older export is fresh. No new recurring task is created.

The separate read-only smoke restores a copy of the actual workspace. It checks
CONCOR/KRSNAA/UPL as prior valuation regressions, AEROPLANE for the documented
symbol transition, and ARE&M for inconsistent owner-profit attribution. Those
are test cases selected for specific failure modes, not investment picks.

## Verification boundaries

Tests cover retained-source immutability, identical-ISIN alias gating, ambiguity,
publication/effective/observation clocks, actual rounding, nonfinite inputs,
withheld attribution, negative/missing cash purchases, stale prices, context
hashes and rejected evidence. Software tests and a live-source self-audit do not
establish independent semantic accuracy or investment performance.

No model endpoint, API key, paid inference, broker connection or hosted commercial
service is added. All results retain live_capital_allowed=false and
validated_predictive_edge=false. Existing H-series/HG009/AE001 contracts, cohorts,
return outcomes and source schedules are unchanged.

Primary references:
- https://nsearchives.nseindia.com/content/equities/symbolchange.csv
- https://www.ifrs.org/issued-standards/list-of-standards/ias-33-earnings-per-share.html/
