from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


class H004ReplayError(ValueError):
    """Raised when H004 replay input is incomplete or internally inconsistent."""


REQUIRED_COLUMNS = {
    "symbol",
    "decision_date",
    "primary_universe",
    "stage1_eligible",
    "stage2_trigger",
    "explosive_20d_v1",
    "lead_sessions_to_25pct",
    "return_20d_pct",
    "nifty500_excess_20d_pct",
    "positive_pnl_20d_pct",
    "momentum_baseline_trigger",
}


@dataclass(frozen=True)
class H004ReplaySummary:
    observations: int
    primary_observations: int
    future_explosive_movers: int
    stage1_signals: int
    stage2_signals: int
    stage1_explosive_hits: int
    stage2_explosive_hits: int
    explosive_mover_recall: float
    stage1_precision: float
    stage2_precision: float
    median_lead_sessions: float | None
    median_20d_return_pct: float | None
    median_nifty500_excess_20d_pct: float | None
    momentum_baseline_signals: int
    momentum_baseline_hits: int
    momentum_baseline_recall: float
    comparable_signal_count_recall_delta: float | None
    largest_positive_pnl_contribution: float | None
    calendar_quarters_with_positive_median_excess: int
    gate_recall: bool
    gate_precision: bool
    gate_lead_time: bool
    gate_median_excess: bool
    gate_winner_concentration: bool
    gate_quarter_stability: bool
    gate_beats_momentum: bool
    promoted: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    normalized = series.astype(str).str.strip().str.lower()
    allowed = {"true", "false", "1", "0", "yes", "no"}
    invalid = ~normalized.isin(allowed)
    if invalid.any():
        values = sorted(normalized[invalid].unique().tolist())
        raise H004ReplayError(f"invalid boolean values: {values}")
    return normalized.isin({"true", "1", "yes"})


def _finite_numeric(series: pd.Series, name: str, *, allow_missing: bool = False) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if not allow_missing and numeric.isna().any():
        raise H004ReplayError(f"{name} contains missing/non-numeric values")
    finite = numeric.dropna()
    if not np.isfinite(finite).all():
        raise H004ReplayError(f"{name} contains non-finite values")
    return numeric


def _calendar_quarter_count(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    dates = pd.to_datetime(frame["decision_date"], errors="coerce")
    if dates.isna().any():
        raise H004ReplayError("decision_date contains invalid dates")
    work = frame.copy()
    work["quarter"] = dates.dt.to_period("Q")
    medians = work.groupby("quarter", observed=True)["nifty500_excess_20d_pct"].median()
    return int((medians > 0).sum())


def _largest_positive_contribution(frame: pd.DataFrame) -> float | None:
    positive = frame.loc[frame["positive_pnl_20d_pct"] > 0, ["symbol", "positive_pnl_20d_pct"]]
    if positive.empty:
        return None
    by_company = positive.groupby("symbol", observed=True)["positive_pnl_20d_pct"].sum()
    total = float(by_company.sum())
    if total <= 0:
        return None
    return float(by_company.max() / total)


def evaluate_h004_replay(frame: pd.DataFrame) -> H004ReplaySummary:
    """Evaluate frozen H004 on a complete point-in-time replay table.

    The caller is responsible for constructing one row per eligible company/day
    using only information available at that decision timestamp. This function
    deliberately refuses winner-only samples by requiring both positive and
    negative future labels in the primary universe.
    """

    missing = sorted(REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        raise H004ReplayError(f"replay missing required columns: {', '.join(missing)}")
    if frame.empty:
        raise H004ReplayError("replay is empty")

    work = frame.copy()
    for column in (
        "primary_universe",
        "stage1_eligible",
        "stage2_trigger",
        "explosive_20d_v1",
        "momentum_baseline_trigger",
    ):
        work[column] = _as_bool(work[column])

    for column in (
        "return_20d_pct",
        "nifty500_excess_20d_pct",
        "positive_pnl_20d_pct",
    ):
        work[column] = _finite_numeric(work[column], column)
    work["lead_sessions_to_25pct"] = _finite_numeric(
        work["lead_sessions_to_25pct"], "lead_sessions_to_25pct", allow_missing=True
    )

    primary = work.loc[work["primary_universe"]].copy()
    if primary.empty:
        raise H004ReplayError("replay has no primary-universe observations")
    labels = set(primary["explosive_20d_v1"].unique().tolist())
    if labels != {False, True}:
        raise H004ReplayError(
            "primary replay must contain both explosive movers and non-movers; "
            "winner-only or loser-only samples are invalid"
        )

    explosive = primary["explosive_20d_v1"]
    stage1 = primary["stage1_eligible"]
    stage2 = primary["stage2_trigger"]
    momentum = primary["momentum_baseline_trigger"]

    future_movers = int(explosive.sum())
    stage1_signals = int(stage1.sum())
    stage2_signals = int(stage2.sum())
    stage1_hits = int((stage1 & explosive).sum())
    stage2_hits = int((stage2 & explosive).sum())
    momentum_signals = int(momentum.sum())
    momentum_hits = int((momentum & explosive).sum())

    recall = stage1_hits / future_movers if future_movers else 0.0
    stage1_precision = stage1_hits / stage1_signals if stage1_signals else 0.0
    stage2_precision = stage2_hits / stage2_signals if stage2_signals else 0.0
    momentum_recall = momentum_hits / future_movers if future_movers else 0.0

    stage2_hits_frame = primary.loc[stage2 & explosive].copy()
    lead = stage2_hits_frame["lead_sessions_to_25pct"].dropna()
    median_lead = float(lead.median()) if not lead.empty else None

    triggered = primary.loc[stage2].copy()
    median_return = float(triggered["return_20d_pct"].median()) if not triggered.empty else None
    median_excess = (
        float(triggered["nifty500_excess_20d_pct"].median()) if not triggered.empty else None
    )
    concentration = _largest_positive_contribution(triggered)
    positive_quarters = _calendar_quarter_count(triggered)

    comparable_delta: float | None = None
    if stage1_signals == momentum_signals:
        comparable_delta = recall - momentum_recall

    gate_recall = recall >= 0.50
    gate_precision = stage2_precision >= 0.20
    gate_lead = median_lead is not None and median_lead >= 2.0
    gate_excess = median_excess is not None and median_excess > 0.0
    gate_concentration = concentration is not None and concentration <= 0.20
    gate_quarters = positive_quarters >= 4
    gate_momentum = comparable_delta is not None and comparable_delta > 0.0

    promoted = all(
        (
            gate_recall,
            gate_precision,
            gate_lead,
            gate_excess,
            gate_concentration,
            gate_quarters,
            gate_momentum,
        )
    )

    return H004ReplaySummary(
        observations=len(work),
        primary_observations=len(primary),
        future_explosive_movers=future_movers,
        stage1_signals=stage1_signals,
        stage2_signals=stage2_signals,
        stage1_explosive_hits=stage1_hits,
        stage2_explosive_hits=stage2_hits,
        explosive_mover_recall=recall,
        stage1_precision=stage1_precision,
        stage2_precision=stage2_precision,
        median_lead_sessions=median_lead,
        median_20d_return_pct=median_return,
        median_nifty500_excess_20d_pct=median_excess,
        momentum_baseline_signals=momentum_signals,
        momentum_baseline_hits=momentum_hits,
        momentum_baseline_recall=momentum_recall,
        comparable_signal_count_recall_delta=comparable_delta,
        largest_positive_pnl_contribution=concentration,
        calendar_quarters_with_positive_median_excess=positive_quarters,
        gate_recall=gate_recall,
        gate_precision=gate_precision,
        gate_lead_time=gate_lead,
        gate_median_excess=gate_excess,
        gate_winner_concentration=gate_concentration,
        gate_quarter_stability=gate_quarters,
        gate_beats_momentum=gate_momentum,
        promoted=promoted,
    )
