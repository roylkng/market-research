"""H005 ranker. Fitting and retrospective ranking are not validation approval."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from sklearn.impute import MissingIndicator, SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import StandardScaler

TARGET = "explosive_20d_v1"
DATE_COLUMN = "decision_date"
LABEL_END_COLUMN = "label_end_date"
ID_COLUMN = "event_id"
C_GRID = (0.01, 0.1, 1.0, 10.0)
TOP_FRACTION = 0.10
AP_TIE_TOLERANCE = 0.005

H005_A_FEATURES = (
    "revenue_yoy_pct", "operating_profit_yoy_pct", "pat_yoy_pct", "margin_change_pp",
    "quarterly_pat_crore", "revenue_scale_log", "nonoperating_share_of_pbt",
    "prior_1d_return_pct", "prior_5d_return_pct", "prior_20d_return_pct",
    "distance_to_60d_high_pct", "prior_20d_volatility_pct", "median_20d_traded_value_log",
    "loss_to_profit", "profit_to_loss", "tiny_base", "negative_pat",
    "quality_warning_nonoperating",
)
H005_FLAG_FEATURES = H005_A_FEATURES[-5:]
H005_B_EXTRA_FEATURES = (
    "reaction_1d_pct", "reaction_volume_ratio_20d", "reaction_traded_value_ratio_20d",
    "reaction_range_pct", "reaction_close_location", "reaction_nifty500_excess_pp",
)


class H005Error(ValueError):
    """An input violates the frozen protocol or cannot be evaluated safely."""


@dataclass(frozen=True)
class H005ModelSummary:
    variant: str
    selected_c: float
    training_rows: int
    positive_rows: int
    selected_features: tuple[str, ...]
    dropped_high_missing_features: tuple[str, ...]
    fold_average_precision: tuple[float, ...]
    fold_top_decile_recall: tuple[float, ...]
    fold_audit: tuple[dict[str, object], ...]
    candidate_audit: tuple[dict[str, object], ...]
    training_frame_sha256: str
    evidence_classification: str = "DESIGN_TRAINING_ONLY"
    live_capital_allowed: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class H005Evaluation:
    rows: int
    true_explosive: int
    selected_count: int
    hits: int
    recall: float | None
    precision: float | None
    prevalence: float | None
    prevalence_lift: float | None
    median_lead_sessions: float | None
    median_nifty500_excess_20d_pct: float | None
    evidence_classification: str = "RETROSPECTIVE_RANKING_DIAGNOSTIC_ONLY"
    live_capital_allowed: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class FrozenH005Model:
    variant: str
    selected_c: float
    selected_features: tuple[str, ...]
    dropped_high_missing_features: tuple[str, ...]
    lower_bounds: dict[str, float]
    upper_bounds: dict[str, float]
    pipeline: Pipeline
    summary: H005ModelSummary

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        _require_columns(frame, self.selected_features)
        raw = _coerce_feature_frame(frame, self.selected_features)
        if frame.empty:
            return np.empty(0, dtype=float)
        bounded = _apply_bounds(raw, self.lower_bounds, self.upper_bounds)
        return self.pipeline.predict_proba(bounded)[:, 1]

    def to_dict(self) -> dict[str, object]:
        """Export numerical state, not pickle. Scores are not calibrated probabilities."""
        features = dict(self.pipeline.named_steps["features"].transformer_list)
        scaler = self.pipeline.named_steps["scaler"]
        estimator = self.pipeline.named_steps["model"]
        payload = {
            "schema": "H005-FROZEN-MODEL-1",
            "variant": self.variant,
            "selected_c": self.selected_c,
            "selected_features": list(self.selected_features),
            "lower_bounds": self.lower_bounds.copy(),
            "upper_bounds": self.upper_bounds.copy(),
            "imputation_medians": features["values"].statistics_.tolist(),
            "missing_indicator_features": list(self.selected_features),
            "scaler_mean": scaler.mean_.tolist(),
            "scaler_scale": scaler.scale_.tolist(),
            "coefficients": estimator.coef_[0].tolist(),
            "intercept": float(estimator.intercept_[0]),
            "summary": self.summary.to_dict(),
            "score_semantics": "UNCALIBRATED_CLASS_WEIGHTED_RANKING_SCORE",
            "live_capital_allowed": False,
        }
        payload["parameters_sha256"] = _json_sha256(payload)
        return payload


def _json_sha256(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _features(variant: str) -> tuple[str, ...]:
    if not isinstance(variant, str):
        raise H005Error("variant must be H005-A or H005-B")
    normalized = variant.strip().upper()
    if normalized == "H005-A":
        return H005_A_FEATURES
    if normalized == "H005-B":
        return H005_A_FEATURES + H005_B_EXTRA_FEATURES
    raise H005Error("variant must be H005-A or H005-B")


def _require_columns(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    if not frame.columns.is_unique:
        raise H005Error("duplicate column names are not allowed")
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise H005Error(f"missing required columns: {', '.join(missing)}")


def _event_ids(frame: pd.DataFrame) -> np.ndarray:
    _require_columns(frame, (ID_COLUMN,))
    ids = frame[ID_COLUMN].astype("string").str.strip()
    if ids.isna().any() or ids.eq("").any() or ids.duplicated().any():
        raise H005Error("event_id must be nonempty and unique")
    return ids.to_numpy(dtype=str)


def _target(frame: pd.DataFrame, *, training: bool = False) -> np.ndarray:
    _require_columns(frame, (TARGET,))
    normalized = frame[TARGET].astype("string").str.strip().str.lower()
    allowed = {"true": 1, "false": 0, "1": 1, "0": 0, "1.0": 1, "0.0": 0,
               "yes": 1, "no": 0}
    if normalized.isna().any() or not normalized.isin(allowed).all():
        raise H005Error("target contains invalid boolean values")
    target = normalized.map(allowed).to_numpy(dtype=int)
    if training and len(np.unique(target)) < 2:
        raise H005Error("training target must contain both positive and negative classes")
    return target


def _coerce_feature_frame(frame: pd.DataFrame, features: Iterable[str]) -> pd.DataFrame:
    result = pd.DataFrame(index=frame.index)
    boolean_values = {"true": "1", "yes": "1", "false": "0", "no": "0"}
    for feature in features:
        series = frame[feature]
        if feature in H005_FLAG_FEATURES:
            normalized = series.astype("string").str.strip().str.lower()
            series = normalized.replace(boolean_values)
        numeric = pd.to_numeric(series, errors="coerce").astype(float)
        # Genuine nulls are missing. Malformed values and infinities are not data.
        missing_input = frame[feature].isna() | frame[feature].astype("string").str.strip().eq("")
        if (numeric.isna() & ~missing_input.fillna(True)).any():
            raise H005Error(f"invalid numeric value in {feature}")
        if np.isinf(numeric.to_numpy()).any():
            raise H005Error(f"non-finite numeric value in {feature}")
        if feature in H005_FLAG_FEATURES and not numeric.dropna().isin([0, 1]).all():
            raise H005Error(f"binary flag must be 0 or 1: {feature}")
        result[feature] = numeric
    return result


def _dates(frame: pd.DataFrame, column: str) -> pd.Series:
    _require_columns(frame, (column,))
    parsed = pd.to_datetime(frame[column], errors="coerce", utc=True, format="mixed")
    if parsed.isna().any():
        raise H005Error(f"{column} contains invalid dates")
    return parsed.dt.tz_convert("Asia/Kolkata").dt.normalize().dt.tz_localize(None)


def _training_bounds(frame: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
    lower, upper = {}, {}
    for column in frame.columns:
        if column in H005_FLAG_FEATURES:
            continue
        clean = frame[column].dropna()
        if not clean.empty:
            lower[column] = float(clean.quantile(0.01))
            upper[column] = float(clean.quantile(0.99))
    return lower, upper


def _apply_bounds(frame: pd.DataFrame, lower: dict[str, float],
                  upper: dict[str, float]) -> pd.DataFrame:
    result = frame.copy()
    for column in result.columns:
        if column in lower and column in upper:
            result[column] = result[column].clip(lower=lower[column], upper=upper[column])
    return result


def _prepare_training(raw: pd.DataFrame):
    missing_rate = raw.isna().mean()
    dropped = tuple(sorted(missing_rate[missing_rate > 0.40].index.tolist()))
    selected = tuple(column for column in raw.columns if column not in dropped)
    if not selected:
        raise H005Error("all H005 features exceeded the frozen missingness limit")
    x = raw.loc[:, selected]
    lower, upper = _training_bounds(x)
    return selected, dropped, lower, upper, _apply_bounds(x, lower, upper)


def _pipeline(c_value: float) -> Pipeline:
    return Pipeline(steps=[
        ("features", FeatureUnion([
            ("values", SimpleImputer(strategy="median")),
            ("missing", MissingIndicator(features="all")),
        ])),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(C=c_value, class_weight="balanced",
                                     solver="liblinear", max_iter=2000, random_state=7)),
    ])


def _chronological_folds(frame: pd.DataFrame, folds: int = 4):
    """Group decision dates and purge labels not complete before the next block."""
    dates = _dates(frame, DATE_COLUMN)
    ends = _dates(frame, LABEL_END_COLUMN)
    if (ends < dates).any():
        raise H005Error("label_end_date cannot precede decision_date")
    unique_dates = np.sort(dates.unique())
    if len(unique_dates) < folds + 1:
        raise H005Error("insufficient distinct dates for blocked chronological cross-validation")
    blocks = np.array_split(unique_dates, folds + 1)
    result = []
    for block in blocks[1:]:
        valid = np.flatnonzero(dates.isin(block).to_numpy())
        train = np.flatnonzero(((dates < block[0]) & (ends < block[0])).to_numpy())
        result.append((train, valid))
    return result


def _top_fraction_mask(scores: np.ndarray, fraction: float = TOP_FRACTION,
                       *, event_ids: np.ndarray | None = None) -> np.ndarray:
    if isinstance(fraction, (bool, np.bool_)) or not np.isfinite(fraction) or not 0 < fraction <= 1:
        raise H005Error("top_fraction must be finite and in (0, 1]")
    scores = np.asarray(scores, dtype=float)
    if scores.ndim != 1 or not np.isfinite(scores).all():
        raise H005Error("scores must be a one-dimensional finite array")
    if ((scores < 0) | (scores > 1)).any():
        raise H005Error("probability scores must lie in [0, 1]")
    ids = np.asarray(event_ids) if event_ids is not None else np.arange(len(scores))
    if ids.shape != scores.shape:
        raise H005Error("event ID count does not match scores")
    mask = np.zeros(len(scores), dtype=bool)
    if len(scores):
        count = max(1, int(np.ceil(len(scores) * fraction)))
        mask[np.lexsort((ids, -scores))[:count]] = True
    return mask


def _recall_at_top(scores: np.ndarray, target: np.ndarray, ids: np.ndarray) -> float:
    positives = int(target.sum())
    mask = _top_fraction_mask(scores, event_ids=ids)
    return float(target[mask].sum() / positives) if positives else 0.0


def _select_candidate(candidates):
    best_ap = max(candidate[0] for candidate in candidates)
    tied = [candidate for candidate in candidates
            if best_ap - candidate[0] <= AP_TIE_TOLERANCE + 1e-12]
    return min(tied, key=lambda candidate: (-candidate[1], candidate[2]))


def fit_h005(frame: pd.DataFrame, *, variant: str = "H005-B") -> FrozenH005Model:
    requested = _features(variant)
    _require_columns(frame, requested + (TARGET, DATE_COLUMN, LABEL_END_COLUMN, ID_COLUMN))
    ids = _event_ids(frame)
    dates = _dates(frame, DATE_COLUMN)
    frame = frame.iloc[np.lexsort((ids, dates.to_numpy()))].reset_index(drop=True)
    ids = _event_ids(frame)
    y = _target(frame, training=True)
    raw = _coerce_feature_frame(frame, requested)
    dates = _dates(frame, DATE_COLUMN)
    ends = _dates(frame, LABEL_END_COLUMN)
    prepared_folds, audits = [], []
    for train_idx, valid_idx in _chronological_folds(frame):
        start = dates.iloc[valid_idx].min()
        audit = {
            "validation_start": start.date().isoformat(),
            "validation_end": dates.iloc[valid_idx].max().date().isoformat(),
            "training_rows": len(train_idx), "validation_rows": len(valid_idx),
            "purged_rows": int((dates < start).sum()) - len(train_idx),
            "training_label_end_max": (ends.iloc[train_idx].max().date().isoformat()
                                       if len(train_idx) else None),
        }
        if len(np.unique(y[train_idx])) < 2:
            audit["status"] = "SKIPPED_TRAINING_REQUIRES_TWO_CLASSES"
            audits.append(audit)
            continue
        selected, dropped, lower, upper, x_train = _prepare_training(raw.iloc[train_idx])
        x_valid = _apply_bounds(raw.iloc[valid_idx].loc[:, selected], lower, upper)
        audit.update(status="EVALUATED", selected_features=list(selected),
                     dropped_high_missing_features=list(dropped),
                     lower_bounds=lower, upper_bounds=upper)
        audits.append(audit)
        prepared_folds.append((x_train, x_valid, y[train_idx], y[valid_idx], ids[valid_idx]))
    if len(prepared_folds) < 2:
        raise H005Error("fewer than two evaluable purged chronological folds")
    if not any(y_valid.sum() for _, _, _, y_valid, _ in prepared_folds):
        raise H005Error("chronological validation blocks contain no positive outcomes")

    candidates = []
    for c_value in C_GRID:
        aps, recalls = [], []
        for x_train, x_valid, y_train, y_valid, valid_ids in prepared_folds:
            model = _pipeline(c_value)
            model.fit(x_train, y_train)
            scores = model.predict_proba(x_valid)[:, 1]
            # A zero-positive block is retained, not silently removed from the mean.
            aps.append(float(average_precision_score(y_valid, scores)) if y_valid.sum() else 0.0)
            recalls.append(_recall_at_top(scores, y_valid, valid_ids))
        candidates.append((float(np.mean(aps)), float(np.mean(recalls)), c_value,
                           tuple(aps), tuple(recalls)))
    _, _, selected_c, fold_aps, fold_recalls = _select_candidate(candidates)
    selected, dropped, lower, upper, bounded = _prepare_training(raw)
    pipeline = _pipeline(selected_c)
    pipeline.fit(bounded, y)
    normalized = frame.loc[:, (ID_COLUMN, DATE_COLUMN, LABEL_END_COLUMN, TARGET)].copy()
    for feature in requested:
        normalized[feature] = raw[feature]
    digest = hashlib.sha256(normalized.to_csv(index=False).encode("utf-8")).hexdigest()
    summary = H005ModelSummary(
        variant=variant.strip().upper(), selected_c=selected_c,
        training_rows=len(frame), positive_rows=int(y.sum()), selected_features=selected,
        dropped_high_missing_features=dropped, fold_average_precision=fold_aps,
        fold_top_decile_recall=fold_recalls, fold_audit=tuple(audits),
        candidate_audit=tuple({"c": c, "mean_average_precision": ap,
                               "mean_top_decile_recall": recall,
                               "fold_average_precision": aps, "fold_top_decile_recall": recalls}
                              for ap, recall, c, aps, recalls in candidates),
        training_frame_sha256=digest,
    )
    return FrozenH005Model(summary.variant, selected_c, selected, dropped,
                           lower, upper, pipeline, summary)


def predict_frozen_h005(frame: pd.DataFrame, payload: dict[str, object]) -> np.ndarray:
    """Reproduce scores from the JSON export without deserializing executable objects."""
    state = dict(payload)
    digest = state.pop("parameters_sha256", None)
    if digest != _json_sha256(state) or state.get("schema") != "H005-FROZEN-MODEL-1":
        raise H005Error("frozen model checksum or schema mismatch")
    features = tuple(state["selected_features"])
    _require_columns(frame, features)
    raw = _coerce_feature_frame(frame, features)
    x = _apply_bounds(raw, state["lower_bounds"], state["upper_bounds"]).to_numpy()
    missing = np.isnan(x)
    x = np.where(missing, np.asarray(state["imputation_medians"]), x)
    expanded = np.column_stack([x, missing.astype(float)])
    scaled = (expanded - np.asarray(state["scaler_mean"])) / np.asarray(state["scaler_scale"])
    logits = scaled @ np.asarray(state["coefficients"]) + state["intercept"]
    return np.exp(-np.logaddexp(0, -logits))


def evaluate_h005_predictions(frame: pd.DataFrame, scores: np.ndarray,
                              *, top_fraction: float = TOP_FRACTION) -> H005Evaluation:
    """Retrospective top-fraction diagnostic, not an executable online selection rule."""
    ids = _event_ids(frame)
    scores = np.asarray(scores, dtype=float)
    if scores.ndim != 1 or len(frame) != len(scores):
        raise H005Error("prediction count or shape does not match evaluation rows")
    mask = _top_fraction_mask(scores, top_fraction, event_ids=ids)
    y = _target(frame)
    selected, positives, hits = int(mask.sum()), int(y.sum()), int(y[mask].sum())
    recall = hits / positives if positives else None
    precision = hits / selected if selected else None
    prevalence = positives / len(y) if len(y) else None
    lift = precision / prevalence if prevalence and precision is not None else None

    def complete_median(column: str, included: np.ndarray) -> float | None:
        if column not in frame.columns or not included.any():
            return None
        values = pd.to_numeric(frame.loc[included, column], errors="coerce").to_numpy(dtype=float)
        # Partial outcome coverage must not silently improve the reported median.
        return float(np.median(values)) if np.isfinite(values).all() else None

    status = "RETROSPECTIVE_RANKING_DIAGNOSTIC_ONLY"
    if not len(y):
        status = "NO_OBSERVATIONS"
    elif not positives:
        status = "NO_POSITIVES_RECALL_UNDEFINED"
    return H005Evaluation(
        rows=len(frame), true_explosive=positives, selected_count=selected, hits=hits,
        recall=recall, precision=precision, prevalence=prevalence, prevalence_lift=lift,
        median_lead_sessions=complete_median("lead_sessions_to_25pct", mask & (y == 1)),
        median_nifty500_excess_20d_pct=complete_median("nifty500_excess_20d_pct", mask),
        evidence_classification=status,
    )
