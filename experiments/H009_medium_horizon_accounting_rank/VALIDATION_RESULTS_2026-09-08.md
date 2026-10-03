# H009 one-shot forward historical validation

Recorded: 2026-09-08

Status: **FAILED. LIVE CAPITAL DISABLED.**

H009 was frozen before the April-May 2026 60-session outcomes were computed. The validation cohort used result publications from 2026-04-01 through 2026-05-31, H005-B execution timing, exact retained market sessions, corporate-action conventions and a fixed 60-session close-return target relative to Nifty 500.

The reconstruction produced 1,133 evaluable events from 1,145 candidate rows. The primary top-10% selection contains 114 events.

## H009 primary result

- median Nifty 500 60-session excess: **+0.43 percentage points**
- mean Nifty 500 excess: **+4.87 percentage points**
- Nifty 500 beat rate: **50.88%**
- median raw stock return: **+4.08%**
- excess >= +5 percentage points: **39.47%**
- maximum company contribution to aggregate positive gross close-return P&L: **9.74%**

The frozen gate required median excess above +3 pp, mean excess above +3 pp, beat rate above 55%, positive median raw return, at least 35% of selections above +5 pp excess, superiority to matched prior-20 momentum and first-session tape, and concentration below 20%.

H009 fails because median excess is too low, the beat rate is below 55%, and its median excess does not exceed the matched first-session tape comparator. No threshold, date, feature weight or operating percentile is changed after observing this result.

The selected-group bootstrap 95% interval for median excess spans approximately -2.63 to +4.89 pp. Its mean-excess interval is approximately +0.89 to +9.22 pp. Random matched-size subsets reach at least H009's observed median about 28% of the time and at least its observed mean about 13% of the time. The result is therefore not statistically persuasive despite the positive mean.

## Frozen comparator results

The preregistered matched-count comparators were:

| Ranker | Median excess | Mean excess | Beat rate | Median raw return | Excess >= +5 pp |
|---|---:|---:|---:|---:|---:|
| H009 accounting rank | +0.43 pp | +4.87 pp | 50.88% | +4.08% | 39.47% |
| prior-20-session momentum | -2.14 pp | +2.49 pp | 45.61% | +1.19% | lower than H009 |
| first-session tape | +0.90 pp | +5.32 pp | 51.75% | +4.08% | 45.61% |
| prior-60-session relative momentum | **+5.60 pp** | **+7.50 pp** | **55.26%** | **+7.77%** | **51.75%** |

The prior-60-session relative-momentum comparator also has low single-company positive-P&L concentration, approximately 8.17%.

That comparator was frozen before H009 validation was opened, so its result is legitimate diagnostic evidence. However, because it was selected for further study after viewing this validation result, April-May 2026 becomes design evidence for any new momentum hypothesis and cannot validate that new hypothesis.

## Decision

Reject H009. Promote only the simple prior-60-session stock-minus-Nifty-500 momentum mechanism into a new separately frozen hypothesis. Its next test must use outcomes that were not inspected when selecting that mechanism.
