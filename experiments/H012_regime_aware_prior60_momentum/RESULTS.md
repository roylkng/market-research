# H012 older-period historical challenge result

Status: **FAILED. LIVE CAPITAL DISABLED.**

H012 was frozen before full-market monthly prior-60 momentum cohorts were calculated on the older retained 2024-12 through 2025-06 market corpus.

The source reconstruction used official NSE daily EQ bhavcopies, Nifty 500 index snapshots and retained corporate-action responses. December 2024 through March 2025 were `REGIME_OFF`. April, May and June 2025 were active.

Across the three active cohorts, 310 selected stock-observations were produced.

Primary H012 results:

- median active-cohort Nifty 500 excess: **+2.56 pp**
- mean selected-stock Nifty 500 excess: **+3.60 pp**
- median selected-stock Nifty 500 excess: **-0.71 pp**
- selected-stock beat rate: **47.42%**
- active-cohort positive rate: **100%**
- median raw selected-stock return: **+1.88%**
- fixed-seed matched-random p-value for mean excess: **0.338**
- max single-symbol share of aggregate positive selected return: **5.85%**

Frozen comparators:

- prior-20 momentum mean excess: +2.82 pp
- H011-style 120-session / 5-session-skip momentum mean excess: **+5.46 pp**
- full eligible cohort mean excess: +3.24 pp

H012 failed the median-stock, beat-rate, prior-20 superiority, 120/5 superiority, full-cohort lift and random-significance gates. It therefore does not establish a reliable company-selection edge.

H011 and H012 together show the same failure mode: raw momentum can improve equal-weight cohort means through a positive tail while leaving the median stock and hit rate weak. That motivates a separately frozen risk-adjusted momentum hypothesis rather than threshold tuning.
