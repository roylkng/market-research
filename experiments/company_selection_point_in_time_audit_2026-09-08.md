# Company-selection point-in-time integrity audit

Recorded: 2026-09-08

Status: **H011-H014 historical ranking results are not valid point-in-time company-selection proof. Live capital remains disabled.**

## Material defect

The full-market H011-H014 reconstruction code built the historical eligible universe by requiring stock bars not only through the decision timestamp but also through the future 60-session holding window. For example, the independent robustness runner constructed `required = sessions[i - 125 : i + 61]` and rejected a symbol if any date in that future-inclusive set was absent before ranking.

That means future information affected historical selection:

- a company that later suspended or delisted could be removed from the signal universe before the historical decision,
- a company with any future missing bar could be removed even though the absence was unknowable at decision time,
- future structural corporate actions were also used as pre-ranking exclusions in the local H011-H014 evaluators,
- apparent performance can therefore benefit from survivorship and future-tradability leakage.

This is separate from H013's ETF contamination. Even a company-only `INE` filter does not repair future-aware eligibility.

## Scientific consequence

H011, H012, H013 and H014 results remain useful diagnostics for mechanism discovery, but none may be represented as a valid point-in-time company-selection backtest. H013's prior historical pass is doubly invalid for the project's company-selection goal because it also admitted ETF/unit securities.

No existing favorable result is repaired by deleting future failures after the fact. The next hypothesis starts from a clean point-in-time contract.

## Required point-in-time separation

For every future historical or prospective company-selection experiment:

### Selection layer

May use only information observable through the decision timestamp:

- security identity and series at decision,
- market bars through decision only,
- historical liquidity through decision only,
- historical corporate actions effective on or before decision,
- benchmark and breadth state through decision only.

The selection layer may not inspect whether the security will trade tomorrow, whether an exit bar exists, or whether a future structural action occurs.

### Execution/outcome layer

Runs only after the candidate list is frozen:

- next-session non-fill does not remove the candidate from the historical list,
- later suspension/delisting/missing exit does not remove the candidate,
- source-backed splits/bonuses/consolidations may adjust realized return after selection,
- unresolved future merger/demerger/rights/delisting outcomes receive the separately frozen conservative outcome treatment,
- all execution failures and unresolved outcomes remain in the denominator.

## Workflow integrity finding

The first 2023-2024 independent-robustness workflow also piped the Python runner into `tee` without shell `pipefail`. The Python process raised `ValueError: market/index archive asymmetry on 13 dates`, but the workflow step was reported successful because `tee` returned zero. The uploaded result artifact therefore contained only a run log and no result summary.

Future scientific workflows must use `set -o pipefail` or otherwise propagate the research runner's exit status. A green job without the required result files is never evidence of a successful experiment.

## Next hypothesis boundary

The next full-market hypothesis must therefore be new. It will combine:

- explicit operating-company equity identity (`EQ` plus `INE` ISIN),
- point-in-time-only eligibility,
- the already studied risk-adjusted momentum score,
- a separately frozen market-breadth confirmation rule motivated by the H014 failure diagnostics,
- conservative post-selection execution/outcome accounting.

The H011-H014 windows become design evidence only for that successor. Its first claim of robustness must come from a period whose company-only point-in-time outcomes have not been used to set the successor's rules.
