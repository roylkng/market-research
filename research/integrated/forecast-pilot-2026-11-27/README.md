# 27 November 2026 | Prospective fundamental-forecast pilot and competitive watch

## What changes
The earlier convergence audit found no demonstrated selection edge. A new EPSBench paper (28 October 2026, https://arxiv.org/abs/2610.38293) supplies a more measurable model: predict accounting drivers, use deterministic arithmetic, score realized results. Its 149 US firm-quarters across 86 companies compare six models with consensus; three show no detectable paired error difference, three worse. Nominal 80% intervals cover 37–70% among returned intervals. Its tasks are preannouncement nowcasts after the quarter ends, whereas ours are earlier forecasts before Dec31. No claim of directly comparable difficulty or Indian alpha.

## Actual pilot
Four already researched issuers, not a new market screen. Target is first reported Dec31 2026 quarter PAT at each frozen scope, including exceptional items. Four baselines plus an assisted-driver forecast. Normalize identified old costs using disclosed tax (INFY) or historical effective tax as a simple proxy. Do not assume future one-offs cannot occur. All forecasts fixed before target end. No actual result yet.

| Symbol | Prior-year Q3 | Latest Q2 | Raw YoY trend | Adjusted YoY trend | Driver-based |
|---|---:|---:|---:|---:|---:|
| TCS | 10657.00 | 13884.00 | 12253.56 | 14213.87 | 13918.22 |
| INFY | 6654.00 | 7823.00 | 7068.75 | 8100.27 | 7910.81 |
| HDFCBANK | 18650.00 | 19509.96 | 19519.09 | 20162.75 | 19556.89 |
| ICICIBANK | 11318.00 | 14843.00 | 13592.77 | 14904.29 | 14891.81 |

INR crore. HDFC prior Q3 from issuer rounded deck. IT uses IFRS consolidated owner profit; banks standalone Indian GAAP PAT. Original references and every driver are in forecast_register.json. Prior TCS Q3 pretax exceptional expenses total 3391; prior Q2 reskilling 1135. INFY actual disclosed adjustment is 971 after tax. HDFC prior new Labour Code cost 800; ICICI prior 1283 PSL provision and 145 labour cost. No assumption of release of historic ICICI provision stock. Driver estimates are analyst choices, not consensus. Simple adjusted trend and assisted forecast differ only ~0–3% across these four, so use this stronger comparison instead of a strawman raw forecast. This does not show which is more accurate.

The deterministic evaluator was exercised in this session on the actual forecast inputs and synthetic zero-error/missing/wrong-scope/duplicate/wrong-period/early-release/non-numeric checks: {"forecast_arithmetic":5,"missing_case":1,"synthetic_partial_case":1,"rejection_cases":5,"actual_observations":0}. Source metadata validation is not original-source authentication. The pure JS calculation functions were executed in the tool isolate, not a full repository CI or independent forecast review. Node wrapper is supplied for repeatability, not claimed executed in a separate runtime. At first official release, save an actuals JSON array with symbol, scope, period_end, first_release_date, source_url and actual_pat_cr. Run node calculate_forecasts.mjs actuals.json. No result until observed, no edit to frozen H/PF/HG/AE or seven-name forward comparison. Do not claim improvement until paired errors measured; selected small sample and no independent model arms, calibrated probability, consensus snapshot or stock-return inference.

## Competitive watch
See competitive_watch.json. New direct Indian comparators Cofacto (formerly CompoundingAI per its public description), Algoagent, Factfolio and FinSight AI, plus Qlib/RD-Agent. Track releases, provenance, point-in-time data, management guidance/driver forecasts, costs/licensing and forward evaluation. Public self-descriptions only; no installation, paid subscription, benchmark, or claim that no rival can perform this task. Reuse rather than rebuild if evidence and license permit. No changes to market research permissions.

## Current market and existing work
Reported 27 November close Nifty50 25607.20 (-1.07%), Sensex83339.26 (-1.17%), Nifty IT -1.88%, Midcap100 +0.10%, Bank -0.78% (https://economictimes.indiatimes.com/markets/7.cms; https://marketdly.com/india/). Secondary context, no new individual buy or exact current repricing in this pilot. Latest scheduled watch independently assessed Supriya and Mahanadi; preserve that work. Broader point-in-time factor-vs-LLM return test, independent held-out model evaluation, seven-name entry marks and original-byte/official quote archive remain incomplete. Prior review dates retained.
