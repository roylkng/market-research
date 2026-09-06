from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy import stats

ALLOWED_STATUSES = {"PROPOSED", "FROZEN", "TESTING", "REJECTED", "INCONCLUSIVE", "PROMISING"}


class RegistryError(ValueError):
    """Raised when the research registry violates project invariants."""


@dataclass(frozen=True)
class SignalEvaluation:
    n: int
    pearson: float
    pearson_p_value: float
    spearman: float
    spearman_p_value: float

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


@dataclass(frozen=True)
class BinaryGroupEvaluation:
    positive_n: int
    negative_n: int
    positive_mean: float
    negative_mean: float
    spread: float
    positive_beat_rate: float
    negative_beat_rate: float
    welch_p_value: float
    fisher_p_value: float
    bootstrap_low: float
    bootstrap_high: float

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def load_yaml(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def validate_hypothesis_registry(document: dict[str, Any]) -> list[str]:
    """Return validation errors for a hypothesis-registry document.

    This intentionally enforces only invariants that should remain stable as the
    research schema evolves. A richer JSON/YAML schema can be introduced later.
    """

    errors: list[str] = []
    if not isinstance(document, dict):
        return ["registry root must be a mapping"]

    if document.get("live_capital_allowed") is not False:
        errors.append("registry must explicitly set live_capital_allowed: false")

    hypotheses = document.get("hypotheses")
    if not isinstance(hypotheses, list) or not hypotheses:
        errors.append("registry must contain a non-empty hypotheses list")
        return errors

    seen: set[str] = set()
    for index, hypothesis in enumerate(hypotheses):
        prefix = f"hypotheses[{index}]"
        if not isinstance(hypothesis, dict):
            errors.append(f"{prefix} must be a mapping")
            continue

        hypothesis_id = hypothesis.get("id")
        if not isinstance(hypothesis_id, str) or not hypothesis_id.startswith("H"):
            errors.append(f"{prefix}.id must be a string beginning with H")
        elif hypothesis_id in seen:
            errors.append(f"duplicate hypothesis id: {hypothesis_id}")
        else:
            seen.add(hypothesis_id)

        status = hypothesis.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{prefix}.status must be one of {sorted(ALLOWED_STATUSES)}")

        if hypothesis.get("live_capital") is not False:
            errors.append(f"{prefix}.live_capital must explicitly be false")

        if not hypothesis.get("mechanism"):
            errors.append(f"{prefix}.mechanism is required")

        signal = hypothesis.get("signal")
        if not isinstance(signal, dict) or not signal.get("formula"):
            errors.append(f"{prefix}.signal.formula is required")

        decision = hypothesis.get("decision")
        if not isinstance(decision, dict):
            errors.append(f"{prefix}.decision is required")
        else:
            if not isinstance(decision.get("entry_delay_sessions"), int):
                errors.append(f"{prefix}.decision.entry_delay_sessions must be an integer")
            if not isinstance(decision.get("holding_period_sessions"), int):
                errors.append(f"{prefix}.decision.holding_period_sessions must be an integer")

        benchmarks = hypothesis.get("benchmarks")
        if not isinstance(benchmarks, list) or not benchmarks:
            errors.append(f"{prefix}.benchmarks must be a non-empty list")

        if status == "PROMISING" and not hypothesis.get("next_action"):
            errors.append(f"{prefix}: PROMISING hypotheses must declare next_action")

    return errors


def require_valid_registry(path: str | Path) -> dict[str, Any]:
    document = load_yaml(path)
    errors = validate_hypothesis_registry(document)
    if errors:
        raise RegistryError("\n".join(errors))
    return document


def unexpected_earnings(
    eps_current: pd.Series,
    eps_year_ago: pd.Series,
    price_day_minus_2: pd.Series,
) -> pd.Series:
    """Literature-style seasonal unexpected earnings proxy.

    UE = (EPS_t - EPS_t-4) / price_day_minus_2
    """

    denominator = pd.to_numeric(price_day_minus_2, errors="coerce").replace(0, np.nan)
    return (
        pd.to_numeric(eps_current, errors="coerce")
        - pd.to_numeric(eps_year_ago, errors="coerce")
    ) / denominator


def evaluate_continuous_signal(
    frame: pd.DataFrame,
    *,
    signal_col: str,
    excess_return_col: str,
) -> SignalEvaluation:
    clean = frame[[signal_col, excess_return_col]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(clean) < 3:
        raise ValueError("at least three complete observations are required")

    pearson = stats.pearsonr(clean[signal_col], clean[excess_return_col])
    spearman = stats.spearmanr(clean[signal_col], clean[excess_return_col])
    return SignalEvaluation(
        n=len(clean),
        pearson=float(pearson.statistic),
        pearson_p_value=float(pearson.pvalue),
        spearman=float(spearman.statistic),
        spearman_p_value=float(spearman.pvalue),
    )


def _bootstrap_mean_spread(
    positive: np.ndarray,
    negative: np.ndarray,
    *,
    iterations: int,
    seed: int,
    confidence: float,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    spreads = np.empty(iterations, dtype=float)
    for index in range(iterations):
        positive_sample = rng.choice(positive, size=len(positive), replace=True)
        negative_sample = rng.choice(negative, size=len(negative), replace=True)
        spreads[index] = positive_sample.mean() - negative_sample.mean()

    alpha = 1.0 - confidence
    return (
        float(np.quantile(spreads, alpha / 2.0)),
        float(np.quantile(spreads, 1.0 - alpha / 2.0)),
    )


def evaluate_binary_groups(
    frame: pd.DataFrame,
    *,
    group_col: str,
    excess_return_col: str,
    positive_value: str = "Positive UE",
    negative_value: str = "Negative UE",
    beat_threshold: float = 0.0,
    bootstrap_iterations: int = 10_000,
    bootstrap_seed: int = 7,
    confidence: float = 0.95,
) -> BinaryGroupEvaluation:
    clean = frame[[group_col, excess_return_col]].copy()
    clean[excess_return_col] = pd.to_numeric(clean[excess_return_col], errors="coerce")
    clean = clean.dropna(subset=[group_col, excess_return_col])

    positive = clean.loc[clean[group_col] == positive_value, excess_return_col].to_numpy(dtype=float)
    negative = clean.loc[clean[group_col] == negative_value, excess_return_col].to_numpy(dtype=float)
    if len(positive) < 2 or len(negative) < 2:
        raise ValueError("each group requires at least two observations")

    welch = stats.ttest_ind(positive, negative, equal_var=False)
    table = np.array(
        [
            [(positive > beat_threshold).sum(), (positive <= beat_threshold).sum()],
            [(negative > beat_threshold).sum(), (negative <= beat_threshold).sum()],
        ]
    )
    fisher = stats.fisher_exact(table)
    low, high = _bootstrap_mean_spread(
        positive,
        negative,
        iterations=bootstrap_iterations,
        seed=bootstrap_seed,
        confidence=confidence,
    )

    return BinaryGroupEvaluation(
        positive_n=len(positive),
        negative_n=len(negative),
        positive_mean=float(positive.mean()),
        negative_mean=float(negative.mean()),
        spread=float(positive.mean() - negative.mean()),
        positive_beat_rate=float((positive > beat_threshold).mean()),
        negative_beat_rate=float((negative > beat_threshold).mean()),
        welch_p_value=float(welch.pvalue),
        fisher_p_value=float(fisher.pvalue),
        bootstrap_low=low,
        bootstrap_high=high,
    )


def winner_concentration(
    excess_returns: pd.Series,
    *,
    top_n: int = 2,
) -> dict[str, float | int]:
    values = pd.to_numeric(excess_returns, errors="coerce").dropna().sort_values(ascending=False)
    if len(values) <= top_n:
        raise ValueError("winner-concentration test needs more observations than top_n")

    full_mean = float(values.mean())
    stripped_mean = float(values.iloc[top_n:].mean())
    return {
        "n": len(values),
        "top_n": top_n,
        "full_mean": full_mean,
        "mean_without_top_n": stripped_mean,
        "mean_change": stripped_mean - full_mean,
    }
