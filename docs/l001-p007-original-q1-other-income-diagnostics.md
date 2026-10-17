# L001 P007: Source-original Q1 earnings composition diagnostic

Dated October 18, 2026. Strictly *post-hoc accounting research*. No earnings-growth forecast, recommendation, or prospective alpha trial is created.

Original source: frozen 100-company HG009 P004 source bridge, SHA `97cd3432e3c779f48ad09c75d42b5c18b431e2f6e297cf10421a31055c92e82d`, 100 original NSE 2026-06-30 quarterly XBRL documents already hash authenticated and individually replayed. P007 independently re-reads their 7 signed OneD/INR XBRL concepts: revenue, other income, financing costs, PBT before exceptional, exceptional, PBT and PAT. Missing facts remain NULL and conflicting original concepts abort.

## Why this matters

A high cash-flow proxy and profitable quarter may not represent high recurring returns on the operating assets. Company-reported "other income" can include recurring interest, financial investments, realized capital gains and other non-operating items. All may have shareholder value, **but must not be counted twice** alongside net-cash/investments or automatically capitalized at the operating-business terminal multiple.

Selected official original Q1 FY27 (June 30, 2026) values:

| Issuer | Revenue (₹ cr) | Other income (₹ cr) | PBT (₹ cr) | Other income / PBT | Interpretation |
|---|---:|---:|---:|---:|---|
| HTMEDIA | 437.30 | 59.66 | 56.60 | 105.4% | Exceeds reported PBT, so income quality needs subsidiary and investment review |
| SARLAPOLY | 113.2643 | 27.8597 | 46.2975 | 60.2% | Material financial / non-operating component |
| MAHSEAMLES | 1,091.20 | 174.42 | 326.13 | 53.5% | H1 growth cannot be extrapolated solely from reported PAT |
| DATAMATICS | 513.91 | 18.22 | 91.99 | 19.8% | Acquisition and non-controlling claims still need separate scrutiny |
| SANDUMA | 1,374.78 | 14.74 | 281.07 | 5.2% | Lower other-income share, but mining/cyclical capex and minority economics unverified |
| MOL | 542.8295 | 11.9253 | 66.985 | 17.8% | Quarterly cash conversion and chemical business cycle still unverified |

The ratios are **mechanical original-source diagnostics**. They are NOT estimates of non-recurring earnings, normalized profit or mispricing. Profit attributable to parent is not independently reconstructed in this pipeline.

## Reject misleading extrapolation

One quarter cannot establish a durable franchise. For MAHSEAMLES the FY26 CFO-minus-PPE proxy from P004 is ₹763.5 crore, but the Q1 PAT headline is significantly influenced by ₹174.42 crore of other income. Without the annual report's note and cash/investment ownership, optimistic return assumptions would be speculative.

For HTMEDIA, non-operating income alone exceeds the period's total PBT. Its earnings must be separately valued with operating business and investment financial assets. Failure to do so can double count cash and recurring interest.

For SANDUMA, lower other-income share makes operating profit a more coherent *research question*, not an investment endorsement. Its production, realized commodity pricing, consolidation, investment and ownership changes remain unanswered.

## Implementation and controls

- `src/marketlab/l001_p007_earnings_components.py`: exact all-100 original source comparison with P004 SHA.
- `scripts/materialize_l001_p007_q1_earnings.py`: reproducible source-only 100-company Q1 original-value report.
- `tests/test_l001_p007_earnings_components.py`: rejects wrong unit, wrong period, missing and conflicting original values.
- `.github/workflows/l001-p007-original-q1-earnings.yml`: independent real-source replay using the immutable original P004 GitHub artifact.
- Interpret any 50% other-income/PBT "trigger" only as exploratory **post-hoc diligence triage**, never as a tuned alpha feature or rank.

Do not change H001–H004, HG009 original selected/control cohorts, original first-day return observations or L001 genuine prospective 1–3-year evaluation. Future full economic models require maintenance capex, interest income attribution, net shareholder-accessible cash, non-controlling claims, diluted equity and risk-adjusted valuations.
