from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from marketlab.evaluation import (
    evaluate_binary_groups,
    evaluate_continuous_signal,
    winner_concentration,
)
from marketlab.h002 import H002SignalResult

PHASE_A_ID = "A_SIGNAL_CAPTURE_ONLY"
PHASE_B_ID = "B_OUTCOME_RECONSTRUCTION"
REPLAY_RULE_ID = "H002-HR001"
SOURCE_SIGNAL_RULE_ID = "H002-R001"
BENCHMARK_IDS = ("nifty_50", "nifty_200_momentum_30")


class HistoricalOutcomeError(ValueError):
    """Raised when historical outcome evaluation violates a frozen evidence boundary."""


def canonical_hash(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HistoricalOutcomeError("historical outcome payload must be finite JSON") from exc
    return hashlib.sha256(raw).hexdigest()


def load_phase_a_manifest(
    path: str | Path,
    *,
    expected_sha256: str,
) -> dict[str, Any]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HistoricalOutcomeError(f"could not load phase-A manifest: {exc}") from exc
    if not isinstance(document, dict):
        raise HistoricalOutcomeError("phase-A manifest root must be an object")
    declared = document.get("manifest_sha256")
    if declared != expected_sha256:
        raise HistoricalOutcomeError(
            f"phase-A manifest identity changed: expected={expected_sha256}, observed={declared}"
        )
    unsigned = dict(document)
    unsigned.pop("manifest_sha256", None)
    actual = canonical_hash(unsigned)
    if actual != declared:
        raise HistoricalOutcomeError(
            f"phase-A manifest hash mismatch: declared={declared}, recomputed={actual}"
        )
    if document.get("phase") != PHASE_A_ID:
        raise HistoricalOutcomeError("historical outcomes require the frozen phase-A signal manifest")
    if document.get("outcome_data_included") is not False:
        raise HistoricalOutcomeError("phase-A manifest unexpectedly contains outcome data")
    if document.get("replay_rule_id") != REPLAY_RULE_ID:
        raise HistoricalOutcomeError("unexpected historical replay rule")
    if document.get("source_signal_rule_id") != SOURCE_SIGNAL_RULE_ID:
        raise HistoricalOutcomeError("historical replay no longer references H002-R001")
    if int(document.get("status_counts", {}).get("ERROR", 0)):
        raise HistoricalOutcomeError("phase-A manifest contains unresolved ERROR observations")
    return document


def adapt_signal_for_execution(record: dict[str, Any]) -> H002SignalResult:
    if record.get("status") != "SIGNAL":
        raise HistoricalOutcomeError("only phase-A SIGNAL records can be executed")
    historical = record.get("signal")
    target_event = record.get("target_event")
    if not isinstance(historical, dict) or not isinstance(target_event, dict):
        raise HistoricalOutcomeError("signal record is missing historical signal or target event")
    provenance = target_event.get("provenance")
    if not isinstance(provenance, dict):
        raise HistoricalOutcomeError("target event provenance is missing")
    publication = provenance.get("exchange_published_at_utc")
    if not isinstance(publication, str) or not publication:
        raise HistoricalOutcomeError("target event publication timestamp is missing")
    if historical.get("replay_rule_id") != REPLAY_RULE_ID:
        raise HistoricalOutcomeError("historical signal replay-rule identity changed")
    if historical.get("source_signal_rule_id") != SOURCE_SIGNAL_RULE_ID:
        raise HistoricalOutcomeError("historical signal source-rule identity changed")
    bucket = historical.get("bucket")
    if bucket not in {"POSITIVE", "ZERO", "NEGATIVE"}:
        raise HistoricalOutcomeError(f"non-executable historical signal bucket: {bucket}")
    return H002SignalResult(
        schema_version=1,
        rule_id=SOURCE_SIGNAL_RULE_ID,
        signal_version=str(historical["signal_version"]),
        event_id=str(historical["event_id"]),
        event_version_id=str(historical["event_version_id"]),
        expectation_id=str(historical["expectation_id"]),
        symbol=str(historical["symbol"]),
        # This is an explicitly simulated historical decision timestamp. The signal
        # inputs were frozen pre-filing and actual EPS becomes available at publication.
        # Using the official publication timestamp is conservative and still strictly
        # precedes the frozen second-session entry.
        scored_at_utc=publication,
        actual_basic_eps=historical.get("actual_basic_eps"),
        expected_eps=historical.get("expected_eps"),
        surprise_eps=historical.get("surprise_eps"),
        price_day_minus_2=historical.get("price_day_minus_2"),
        ue=historical.get("ue"),
        bucket=bucket,
        no_signal_reason=None,
    )


def _benchmark_rows(records: list[dict[str, Any]], benchmark_id: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in records:
        if record.get("status") != "COMPLETED":
            continue
        for benchmark in record.get("benchmarks", []):
            if (
                isinstance(benchmark, dict)
                and benchmark.get("benchmark_id") == benchmark_id
                and benchmark.get("status") == "COMPLETE"
            ):
                rows.append(
                    {
                        "symbol": record.get("symbol"),
                        "quarter_id": record.get("quarter_id"),
                        "bucket": record.get("signal_bucket"),
                        "ue": record.get("signal_ue"),
                        "gross_return_pct": record.get("gross_return_pct"),
                        "benchmark_return_pct": benchmark.get("return_pct"),
                        "excess_return_pct": benchmark.get("excess_return_pct"),
                    }
                )
                break
    return pd.DataFrame(rows)


def _cluster_bootstrap_spread(
    frame: pd.DataFrame,
    *,
    iterations: int = 10_000,
    seed: int = 19,
    confidence: float = 0.95,
) -> dict[str, Any]:
    clean = frame[["symbol", "bucket", "excess_return_pct"]].copy()
    clean["excess_return_pct"] = pd.to_numeric(clean["excess_return_pct"], errors="coerce")
    clean = clean.dropna()
    symbols = sorted(clean["symbol"].unique())
    if len(symbols) < 3:
        raise HistoricalOutcomeError("company-cluster bootstrap requires at least three companies")
    by_symbol = {
        symbol: clean.loc[clean["symbol"] == symbol, ["bucket", "excess_return_pct"]]
        for symbol in symbols
    }
    rng = np.random.default_rng(seed)
    spreads: list[float] = []
    for _ in range(iterations):
        selected = rng.choice(symbols, size=len(symbols), replace=True)
        positive: list[float] = []
        negative: list[float] = []
        for symbol in selected:
            block = by_symbol[str(symbol)]
            positive.extend(
                block.loc[block["bucket"] == "POSITIVE", "excess_return_pct"].tolist()
            )
            negative.extend(
                block.loc[block["bucket"] == "NEGATIVE", "excess_return_pct"].tolist()
            )
        if positive and negative:
            spreads.append(float(np.mean(positive) - np.mean(negative)))
    if len(spreads) < iterations * 0.9:
        raise HistoricalOutcomeError("too many cluster-bootstrap samples lacked both signal groups")
    alpha = 1.0 - confidence
    return {
        "cluster_unit": "symbol",
        "unique_companies": len(symbols),
        "iterations_requested": iterations,
        "iterations_used": len(spreads),
        "seed": seed,
        "confidence": confidence,
        "low": float(np.quantile(spreads, alpha / 2.0)),
        "high": float(np.quantile(spreads, 1.0 - alpha / 2.0)),
    }


def _leave_one_company_out(frame: pd.DataFrame) -> dict[str, Any]:
    clean = frame[["symbol", "bucket", "excess_return_pct"]].copy()
    clean["excess_return_pct"] = pd.to_numeric(clean["excess_return_pct"], errors="coerce")
    clean = clean.dropna()
    values: list[tuple[str, float]] = []
    for symbol in sorted(clean["symbol"].unique()):
        sample = clean.loc[clean["symbol"] != symbol]
        positive = sample.loc[sample["bucket"] == "POSITIVE", "excess_return_pct"]
        negative = sample.loc[sample["bucket"] == "NEGATIVE", "excess_return_pct"]
        if len(positive) and len(negative):
            values.append((str(symbol), float(positive.mean() - negative.mean())))
    if not values:
        raise HistoricalOutcomeError("leave-one-company-out spread could not be computed")
    lowest = min(values, key=lambda item: item[1])
    highest = max(values, key=lambda item: item[1])
    return {
        "company_count": len(values),
        "min_spread": lowest[1],
        "min_spread_excluding": lowest[0],
        "max_spread": highest[1],
        "max_spread_excluding": highest[0],
    }


def _group_evaluation(frame: pd.DataFrame) -> dict[str, Any]:
    binary = evaluate_binary_groups(
        frame,
        group_col="bucket",
        excess_return_col="excess_return_pct",
        positive_value="POSITIVE",
        negative_value="NEGATIVE",
    )
    continuous = evaluate_continuous_signal(
        frame,
        signal_col="ue",
        excess_return_col="excess_return_pct",
    )
    positive_returns = frame.loc[frame["bucket"] == "POSITIVE", "excess_return_pct"]
    winner = winner_concentration(positive_returns, top_n=2) if len(positive_returns) > 2 else None
    return {
        "observation_level_binary": binary.to_dict(),
        "continuous_ue": continuous.to_dict(),
        "company_cluster_bootstrap": _cluster_bootstrap_spread(frame),
        "leave_one_company_out": _leave_one_company_out(frame),
        "positive_group_winner_concentration": winner,
    }


def summarize_phase_b(records: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for record in records:
        status = str(record.get("status"))
        status_counts[status] = status_counts.get(status, 0) + 1

    by_benchmark: dict[str, Any] = {}
    for benchmark_id in BENCHMARK_IDS:
        frame = _benchmark_rows(records, benchmark_id)
        if frame.empty:
            by_benchmark[benchmark_id] = {"n": 0, "evaluation": None, "by_quarter": {}}
            continue
        by_quarter: dict[str, Any] = {}
        for quarter_id, quarter_frame in frame.groupby("quarter_id"):
            positive_n = int((quarter_frame["bucket"] == "POSITIVE").sum())
            negative_n = int((quarter_frame["bucket"] == "NEGATIVE").sum())
            if positive_n >= 2 and negative_n >= 2:
                by_quarter[str(quarter_id)] = _group_evaluation(quarter_frame)
            else:
                by_quarter[str(quarter_id)] = {
                    "n": len(quarter_frame),
                    "positive_n": positive_n,
                    "negative_n": negative_n,
                    "evaluation": None,
                }
        by_benchmark[benchmark_id] = {
            "n": len(frame),
            "evaluation": _group_evaluation(frame),
            "by_quarter": by_quarter,
        }

    completed = [record for record in records if record.get("status") == "COMPLETED"]
    return {
        "phase": PHASE_B_ID,
        "live_capital_allowed": False,
        "completed_count": len(completed),
        "status_counts": dict(sorted(status_counts.items())),
        "by_benchmark": by_benchmark,
    }


def phase_b_manifest(
    *,
    phase_a_manifest_sha256: str,
    generated_at_utc: str,
    records: list[dict[str, Any]],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    summary = summarize_phase_b(records)
    document = {
        "schema_version": 1,
        "phase": PHASE_B_ID,
        "replay_rule_id": REPLAY_RULE_ID,
        "source_signal_rule_id": SOURCE_SIGNAL_RULE_ID,
        "phase_a_manifest_sha256": phase_a_manifest_sha256,
        "generated_at_utc": generated_at_utc,
        "outcome_data_included": True,
        "live_capital_allowed": False,
        "cohort_bias_label": "SURVIVORSHIP_SENSITIVE_FIXED_2026_COHORT",
        "records": records,
        "summary": summary,
        "evidence": evidence,
    }
    document["manifest_sha256"] = canonical_hash(document)
    return document
