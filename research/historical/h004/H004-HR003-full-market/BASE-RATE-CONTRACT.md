# H004-HR003 candidate-day base-rate diagnostic

Status: **FROZEN BEFORE DIAGNOSTIC OUTPUT INSPECTION**

For every primary-universe daily snapshot in the HR003 window with at least 60 prior symbol observations and 20 forward observations, report:

1. total primary liquid candidate-days,
2. candidate-days satisfying the frozen H004 pre-momentum conditions (`1d<8%`, `5d<10%`, `20d<20%`),
3. within those pre-momentum candidate-days, the fraction whose next-session-open maximum high over the following 20 symbol sessions reaches +25%,
4. the same base rate by calendar quarter,
5. median forward maximum and 20-session close return for all pre-momentum candidate-days.

This is a descriptive base-rate diagnostic only. It does not modify H004 thresholds or the HR003 episode denominator.
