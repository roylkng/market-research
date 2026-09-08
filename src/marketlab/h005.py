from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

TARGET = "explosive_20d_v1"
DATE_COLUMN = "decision_date"
C_GRID = (0.01, 0.1, 1.0, 10.0)
TOP_FRACTION = 0.10

H005_A_FEATURES = (
    "revenue_yoy_pct",
    "operating_profit_yoy_pct",
    "pat_yoy_pct",
    "margin_change_pp",
    "quarterly_pat_crore",
    "revenue_scale_log",
    "nonoperating_share_of_pbt",
    "prior_1d_return_pct",
    "prior_5d_return_pct",
    "prior_20d_return_pct",
    "distance_to_60d_high_pct",
    "prior_20d_volatility_pct",
    "median_20d_traded_value_log",
    "loss_to_profit",
    "profit_to_loss",
    "tiny_base",
    "negative_pat",
    "quality_warning_nonoperating",
)

H005_B_EXTRA_FEATURES = (
    "reaction_1d_pct",
    "reaction_volume_ratio_20d",
    "reaction_traded_value_ratio_20d",
    "reaction_range_pct",
    "reaction_close_location",
    "reaction_nifty500_excess_pp",
)


class H005Error(ValueError):
    """Raised when an H005 dataset violates the frozen protocol."""


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

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class H005Evaluation:
    rows: int
    true_explosive: int
    selected_count: int
    hits: int
    recall: float
    precision: float
    prevalence: float
    prevalence_lift: float
    median_lead_sessions: float | None
    median_nifty500_excess_20d_pct: float | None

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
        bounded = _apply_bounds(frame.loc[:, self.selected_features], self.lower_bounds, self.upper_bounds)
        return self.pipeline.predict_proba(bounded)[:, 1]


def _features(variant: str) -> tuple[str, ...]:
    normalized = variant.strip().upper()
    if normalized == "H005-A":
        return H005_A_FEATURES
    if normalized == "H005-B":
        return H005_A_FEATURES + H005_B_EXTRA_FEATURES
    raise H005Error("variant must be H005-A or H005-B")


def _require_columns(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise H005Error(f"missing required columns: {', '.join(missing)}")


def _target(frame: pd.DataFrame) -> np.ndarray:
    _require_columns(frame, (TARGET,))
    values = frame[TARGET]
    if values.dtype == bool:
        target = values.to_numpy(dtype=int)
    else:
        normalized = values.astype(str).str.strip().str.lower()
        allowed = {"true": 1, "false": 0, "1": 1, "0": 0, "yes": 1, "no": 0}
        if not normalized.isin(allowed).all():
            raise H005Error("target contains invalid boolean values")
        target = normalized.map(allowed).to_numpy(dtype=int)
    if len(np.unique(target)) < 2:
        raise H005Error("training target must contain both positive and negative classes")
    return target


def _coerce_feature_frame(frame: pd.DataFrame, features: Iterable[str]) -> pd.DataFrame:
    result = pd.DataFrame(index=frame.index)
    for feature in features:
        series = frame[feature]
        if series.dtype == bool:
            result[feature] = series.astype(float)
            continue
        if series.dtype == object:
            normalized = series.astype(str).str.strip().str.lower()
            boolean_like = normalized.isin({"true", "false", "yes", "no", "1", "0", "nan", "none", ""})
            if boolean_like.all() and normalized.isin({"true", "false", "yes", "no"}).any():
                result[feature] = normalized.map(
                    {"true": 1.0, "yes": 1.0, "1": 1.0, "false": 0.0, "no": 0.0, "0": 0.0}
                )
                continue
        result[feature] = pd.to_numeric(series, errors="coerce")
    return result


def _training_bounds(frame: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
    lower: dict[str, float] = {}
    upper: dict[str, float] = {}
    for column in frame.columns:
        clean = pd.to_numeric(frame[column], errors="coerce").dropna()
        if clean.empty:
            continue
        lower[column] = float(clean.quantile(0.01))
        upper[column] = float(clean.quantile(0.99))
    return lower, upper


def _apply_bounds(
    frame: pd.DataFrame, lower: dict[str, float], upper: dict[str, float]
) -> pd.DataFrame:
    result = frame.copy()
    for column in result.columns:
        if column in lower and column in upper:
            result[column] = pd.to_numeric(result[column], errors="coerce").clip(
                lower=lower[column], upper=upper[column]
            )
    return result


def _pipeline(c_value: float) -> Pipeline:
    numeric = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler()),
        ]
    )
    transformer = ColumnTransformer(
        transformers=[("numeric", numeric, FunctionTransformer(validate=False))],
        remainder="drop",
    )
    return Pipeline(
        steps=[
            ("features", transformer),
            (
                "model",
                LogisticRegression(
                    C=c_value,
                    penalty="l2",
                    class_weight="balanced",
                    solver="liblinear",
                    max_iter=2000,
                    random_state=7,
                ),
            ),
        ]
    )


def _chronological_folds(frame: pd.DataFrame, folds: int = 4) -> list[tuple[np.ndarray, np.ndarray]]:
    _require_columns(frame, (DATE_COLUMN,))
    dates = pd.to_datetime(frame[DATE_COLUMN], errors="coerce")
    if dates.isna().any():
        raise H005Error("decision_date contains invalid dates")
    order = np.argsort(dates.to_numpy())
    blocks = [block for block in np.array_split(order, folds + 1) if len(block)]
    result: list[tuple[np.ndarray, np.ndarray]] = []
    for index in range(1, len(blocks)):
        train = np.concatenate(blocks[:index])
        valid = blocks[index]
        result.append((train, valid))
    if len(result) < 2:
        raise H005Error("insufficient rows for blocked chronological cross-validation")
    return result


def _top_fraction_mask(scores: np.ndarray, fraction: float = TOP_FRACTION) -> np.ndarray:
    if len(scores) == 0:
        return np.zeros(0, dtype=bool)
    count = max(1, int(np.ceil(len(scores) * fraction)))
    order = np.argsort(-scores, kind="stable")
    mask = np.zeros(len(scores), dtype=bool)
    mask[order[:count]] = True
    return mask


def _recall_at_top(scores: np.ndarray, target: np.ndarray) -> float:
    positives = int(target.sum())
    if positives == 0:
        return 0.0
    mask = _top_fraction_mask(scores)
    return float(target[mask].sum() / positives)


def fit_h005(frame: pd.DataFrame, *, variant: str = "H005-B") -> FrozenH005Model:
    requested = _features(variant)
    _require_columns(frame, requested + (TARGET, DATE_COLUMN))
    y = _target(frame)
    raw = _coerce_feature_frame(frame, requested)

    missing_rate = raw.isna().mean()
    dropped = tuple(sorted(missing_rate[missing_rate > 0.40].index.tolist()))
    selected = tuple(feature for feature in requested if feature not in dropped)
    if not selected:
        raise H005Error("all H005 features exceeded the frozen missingness limit")
    x = raw.loc[:, selected]

    lower, upper = _training_bounds(x)
    bounded = _apply_bounds(x, lower, upper)
    folds = _chronological_folds(frame)

    candidates: list[tuple[float, float, float, tuple[float, ...], tuple[float, ...]]] = []
    for c_value in C_GRID:
        aps: list[float] = []
        recalls: list[float] = []
        for train_idx, valid_idx in folds:
            y_train = y[train_idx]
            y_valid = y[valid_idx]
            if len(np.unique(y_train)) < 2:
                continue
            model = _pipeline(c_value)
            model.fit(bounded.iloc[train_idx], y_train)
            scores = model.predict_proba(bounded.iloc[valid_idx])[:, 1]
            if y_valid.sum() > 0:
                aps.append(float(average_precision_score(y_valid, scores)))
                recalls.append(_recall_at_top(scores, y_valid))
        if not aps:
            raise H005Error("chronological folds contain no evaluable positive validation blocks")
        candidates.append((float(np.mean(aps)), float(np.mean(recalls)), c_value, tuple(aps), tuple(recalls)))

    candidates.sort(key=lambda item: (-round(item[0], 3), -item[1], item[2]))
    best_ap, best_recall, selected_c, fold_aps, fold_recalls = candidates[0]
    del best_ap, best_recall

    pipeline = _pipeline(selected_c)
    pipeline.fit(bounded, y)
    summary = H005ModelSummary(
        variant=variant.upper(),
        selected_c=selected_c,
        training_rows=len(frame),
        positive_rows=int(y.sum()),
        selected_features=selected,
        dropped_high_missing_features=dropped,
        fold_average_precision=fold_aps,
        fold_top_decile_recall=fold_recalls,
    )
    return FrozenH005Model(
        variant=variant.upper(),
        selected_c=selected_c,
        selected_features=selected,
        dropped_high_missing_features=dropped,
        lower_bounds=lower,
        upper_bounds=upper,
        pipeline=pipeline,
        summary=summary,
    )


def evaluate_h005_predictions(
    frame: pd.DataFrame,
    scores: np.ndarray,
    *,
    top_fraction: float = TOP_FRACTION,
) -> H005Evaluation:
    if len(frame) != len(scores):
        raise H005Error("prediction count does not match evaluation rows")
    y = _target(frame)
    mask = _top_fraction_mask(np.asarray(scores, dtype=float), top_fraction)
    selected = int(mask.sum())
    positives = int(y.sum())
    hits = int(y[mask].sum())
    recall = hits / positives if positives else 0.0
    precision = hits / selected if selected else 0.0
    prevalence = positives / len(y) if len(y) else 0.0
    lift = precision / prevalence if prevalence > 0 else 0.0

    lead = None
    if "lead_sessions_to_25pct" in frame.columns:
        values = pd.to_numeric(frame.loc[mask & (y == 1), "lead_sessions_to_25pct"], errors="coerce").dropna()
        if not values.empty:
            lead = float(values.median())

    excess = None
    if "nifty500_excess_20d_pct" in frame.columns:
        values = pd.to_numeric(frame.loc[mask, "nifty500_excess_20d_pct"], errors="coerce").dropna()
        if not values.empty:
            excess = float(values.median())

    return H005Evaluation(
        rows=len(frame),
        true_explosive=positives,
        selected_count=selected,
        hits=hits,
        recall=recall,
        precision=precision,
        prevalence=prevalence,
        prevalence_lift=lift,
        median_lead_sessions=lead,
        median_nifty500_excess_20d_pct=excess,
    )
