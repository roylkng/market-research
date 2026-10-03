# H011 first historical challenge result

Status: **FAILED. LIVE CAPITAL DISABLED.**

Frozen before H011 cohort outcomes were calculated. Source window used retained official NSE UDiFF EQ prices, Nifty 500 daily index snapshots and retained corporate-action records from the source-complete H005 corpus.

Challenge decisions: 2025-10 through 2026-05 month ends.

Only October, November and December 2025 satisfied the frozen Nifty 500 regime rule. January through May 2026 were correctly classified `REGIME_OFF`. The active cohorts contained 1,015, 1,019 and 982 eligible liquid stocks respectively and selected 102, 102 and 99 names.

Aggregate H011 top-decile 120-session-with-5-session-skip results across 303 selected observations:

- mean Nifty 500 excess: **+5.41 pp**
- median Nifty 500 excess: **-2.00 pp**
- selected-stock beat rate: **48.18%**
- median raw stock return: **-8.52%**
- median active-cohort equal-weight excess: **+5.78 pp**
- active-cohort positive rate: **100%**
- matched-random one-sided empirical p-value for mean excess: **0.00010**
- max single-symbol share of aggregate positive gross selected return: **5.62%**

Frozen comparators:

- prior-20 momentum mean excess: -2.28 pp
- prior-60 momentum mean excess: **+7.36 pp**
- full eligible cohort mean excess: -3.48 pp

H011 failed the active-cohort-count gate, median selected-stock excess gate, selected-stock beat-rate gate and superiority-to-prior-60 gate. The positive mean is real within this reconstruction but is too right-tail dependent to qualify as a reliable company-selection edge under the frozen rules.

The preregistered prior-60 comparator motivated H012. H011 itself remains failed and is not retuned.
