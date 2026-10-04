# FQ001-S001 Accounting Quality Research Score v1

Status: **FROZEN BEFORE SCORE MATERIALIZATION**
Frozen: 2026-10-04
Return outcomes opened: no
Portfolio eligibility: disabled
Live capital: disabled

## Purpose

FQ001-S001 converts the already-passed FQ001-D001-P2 accounting-quality source panel
into a transparent cross-sectional research-quality score.

This is not an alpha model and is not fitted to stock returns.

Authoritative source input:

- diagnostic: `FQ001-D001-P2-v1`;
- workflow run: `37183221019`;
- artifact ID: `11295493835`;
- source panel SHA-256:
  `0112a61cdb928c35ecf0c55a6f8a95ccb3ebc8a137ee3d8f31c1816c89134ee4`;
- frozen U001 universe SHA-256:
  `cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb`;
- complete six-metric source rows: 88.

No alternative source panel may be substituted under S001-v1.

## Scoring eligibility

A source-complete company receives an S001 score only when all of the following are
true:

1. all six FQ001 source metrics are complete;
2. target profit after tax is strictly positive;
3. target total equity is strictly positive;
4. average capital employed is strictly positive;
5. target revenue is strictly positive.

A company that fails one of these prerequisites receives no score. No value is imputed.

A U001 company absent from the P2 source panel receives `SOURCE_UNAVAILABLE`.

## Percentile transform

For each scored metric separately, use only S001-eligible companies.

Midpoint empirical percentile:

`percentile = (count_less + 0.5 * count_equal) / N`

Each percentile is multiplied by 100.

No winsorization, z-score, clipping, logarithm or sector adjustment is used.

## Four equally weighted pillars

### 1. Capital efficiency, 25%

Higher is better:

`capital_efficiency = percentile(ROCE_proxy)`

### 2. Cash conversion, 25%

Two equally weighted sub-signals:

- higher `CFO_to_PAT` is better;
- lower `accruals_to_avg_assets` is better.

`cash_conversion = 0.5 * percentile(CFO_to_PAT) + 0.5 * percentile(-accruals_to_avg_assets)`

This makes each cash sub-signal 12.5% of the total quality score.

### 3. Self-funded reinvestment, 25%

Higher is better:

`self_funded_reinvestment = percentile(CFO_minus_PPE_to_PAT)`

### 4. Balance-sheet quality, 25%

Lower net borrowings relative to equity are better:

`balance_sheet = percentile(-net_borrowings_to_equity)`

## Final score

`quality_score = mean(capital_efficiency, cash_conversion, self_funded_reinvestment, balance_sheet)`

The score therefore lies between 0 and 100.

A deterministic display rank sorts by:

1. quality score descending;
2. symbol ascending.

The score, not the ordinal rank, is the primary output.

## PPE capital intensity

`ppe_capex_to_revenue` remains in the output as context only.

It is deliberately not a fifth score component because:

- `CFO_minus_PPE_to_PAT` already incorporates the cash burden of PPE investment;
- directly penalizing high capex again would double-count reinvestment burden;
- high capital intensity can represent productive growth investment rather than poor
  business quality.

## Interpretation

S001 measures accounting quality across the currently scoreable U001 names. It does not
claim that a high score predicts future stock returns.

It may be used as an additional research lens alongside RR001 and DR001.

It may **not**:

- alter H021's frozen EPS-revision experiment;
- automatically promote a company into an Analyst Decision Object;
- change PF001 eligibility;
- authorize live capital;
- be blended into a return-prediction model without a separately frozen prospective or
  historical trial.

## Future changes

Any change to:

- pillar definitions;
- weights;
- percentile transform;
- prerequisite rules;
- sector normalization;
- inclusion of PPE capex intensity;
- additional quality facts;

requires a new score version frozen before its output is inspected for investment
outcomes.
