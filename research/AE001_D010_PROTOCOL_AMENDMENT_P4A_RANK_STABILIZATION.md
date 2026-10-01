# AE001 D010 Protocol Amendment P4A: Sparse-History Rank Stabilization

Frozen: 2026-10-01
Status: FROZEN AFTER SOURCE-ONLY P4 MATERIALIZATION, BEFORE ANY RETURN LABEL OR MODEL FIT
Live capital: DISABLED

## Trigger

The first frozen P4 feature-only materialization completed successfully in
workflow run 36888897172.

It opened:

- zero stock-return labels;
- zero predictive models;
- zero IC/spread metrics.

The source-only feature audit exposed numerical instability in the two frozen
20-session z-score fields:

- short_volume_share_zscore_20 maximum:
  2,520,587.355708879;
- slb_outstanding_zscore_20 minimum:
  -10,449,995.788199367;
- slb_outstanding_zscore_20 maximum:
  682,465.4011821161.

The cause is sparse positioning histories with extremely small but non-zero
prior standard deviation.

This is a feature-definition problem, not an alpha result.

## Frozen repair principle

Do NOT:

- choose a return-optimized clipping threshold;
- winsorize using future cross-sectional outcomes;
- add an arbitrary epsilon to standard deviation;
- retain the unstable z-scores alongside replacements under the same trial.

Instead replace each unstable time-series z-score with a bounded, deterministic
tie-aware empirical percentile against the prior 20 source-valid observations.

For current value x and prior observations p_1..p_20:

    percentile_20 =
        (count(p_i < x) + 0.5 * count(p_i == x)) / 20

Properties:

- bounded in [0, 1];
- no variance denominator;
- deterministic under repeated zeros;
- current value is NOT included in the reference window;
- no future information;
- same 20-session continuity/source-gap contract as P4.

## Replaced features

REMOVE:

- short_volume_share_zscore_20
- slb_outstanding_zscore_20

ADD:

### short_volume_share_percentile_20

Tie-aware empirical percentile of current lagged short-volume share versus the
prior 20 source-valid publication sessions for the same ISIN.

### slb_outstanding_percentile_20

Tie-aware empirical percentile of current total SLB outstanding quantity versus
the prior 20 source-valid publication sessions for the same ISIN.

## Unchanged features

- short_volume_share_lag1
- short_volume_share_change_1
- slb_outstanding_days_volume20
- slb_outstanding_change_days_volume20
- slb_active_series_count

## Feature count

Still exactly:

    18 base + 7 D010 = 25

No additional feature is introduced.

## Audit gate

The rematerialized P4A panel must satisfy all original P4 structural gates plus:

- both percentile fields have no non-null value outside [0, 1];
- neither removed z-score feature exists in definitions or row values;
- no return outcome is attached;
- no model fit is performed.

## Scientific boundary

P4A is frozen using source-only feature-distribution diagnostics.

No stock-return label, model coefficient, IC, decile spread, or P&L was observed
before this amendment.

A later T010 trial must use ONLY the P4A feature panel.

The original P4 feature artifact remains historical diagnostic evidence and must
not be silently relabeled as P4A.

No live-capital implication.
