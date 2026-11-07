"""CC001 extraction scoring and controlled A/B/C evaluation using existing ridge code.

This module reads outcomes only in evaluation. It never writes a frozen experiment.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import asdict
from datetime import date
from pathlib import Path

from marketlab.company_change import ChangeError, canonical_hash, finite, strict_keys, timestamp
from marketlab.company_change_store import loads_unique, now_utc, writable_workspace


def score_extraction(report: dict, gold: dict) -> dict:
    """Gold is an independent input, not passed to the original-document extractor."""
    strict_keys(gold, {"schema_version", "label_provenance", "cases"}, "gold labels")
    if type(gold.get("schema_version")) is not int or gold["schema_version"] != 1:
        raise ChangeError("unsupported gold schema")
    if not isinstance(gold.get("label_provenance"), str) or not gold["label_provenance"].strip():
        raise ChangeError("gold requires label provenance")
    cases = gold.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ChangeError("gold requires nonempty cases")
    observed = {}
    for result in report["snapshot"]["active"]:
        key = canonical_hash([result["source_id"], result["raw_sha256"], result["selector"]])
        if key in observed:
            raise ChangeError("ambiguous extracted document")
        observed[key] = result
    counts = {"expected_present": 0, "emitted": 0, "correct": 0,
              "wrong": 0, "abstained": 0, "unexpected": 0, "documents_missing": 0}
    details, seen = [], set()
    for case in cases:
        strict_keys(case, {"source_id", "raw_sha256", "selector", "facts"}, "gold case")
        key = canonical_hash([case["source_id"], case["raw_sha256"], case["selector"]])
        if key in seen:
            raise ChangeError("duplicate gold case")
        seen.add(key)
        result = observed.get(key)
        actual = result["facts"] if result else {}
        counts["documents_missing"] += int(result is None)
        checks = []
        for name, expected in case["facts"].items():
            if expected is not None:
                strict_keys(expected, {"value", "unit", "absolute_tolerance"}, "gold fact")
                if set(expected) != {"value", "unit", "absolute_tolerance"}:
                    raise ChangeError("gold facts require value, unit and absolute_tolerance")
                finite(expected["value"], "gold value")
                finite(expected["absolute_tolerance"], "tolerance", minimum=0)
                counts["expected_present"] += 1
            found = actual.get(name)
            if found is None:
                if expected is not None:
                    counts["abstained"] += 1
                status = "ABSTAIN" if expected is not None else "CORRECT_ABSENCE"
            else:
                counts["emitted"] += 1
                if expected is None:
                    counts["unexpected"] += 1
                    status = "UNEXPECTED"
                else:
                    passed = (found["unit"] == expected["unit"] and math.isclose(
                        finite(found["value"], "extracted value"), expected["value"],
                        rel_tol=0, abs_tol=expected["absolute_tolerance"]))
                    counts["correct" if passed else "wrong"] += 1
                    status = "CORRECT" if passed else "WRONG"
            checks.append({"field": name, "status": status})
        extras = set(actual) - set(case["facts"])
        counts["unexpected"] += len(extras)
        counts["emitted"] += len(extras)
        checks.extend({"field": k, "status": "UNLABELLED_EMISSION"} for k in sorted(extras))
        details.append({"source_id": case["source_id"], "checks": checks})
    result = {"counts": counts, "cases": details,
              "precision": counts["correct"] / counts["emitted"] if counts["emitted"] else None,
              "recall": counts["correct"] / counts["expected_present"] if counts["expected_present"] else None,
              "coverage": (counts["expected_present"] - counts["abstained"]) / counts["expected_present"]
              if counts["expected_present"] else None,
              "gold_sha256": canonical_hash(gold), "report_sha256": canonical_hash(report),
              "label_provenance": gold["label_provenance"],
              "independent_labelling_verified": False, "live_capital_allowed": False}
    result["evaluation_sha256"] = canonical_hash(result)
    return result


def validate_dataset(dataset: dict, spec: dict) -> tuple[list, dict, dict]:
    strict_keys(spec, {"feature_groups", "folds", "l2", "minimum_training_rows", "as_of"}, "ABC spec")
    strict_keys(dataset, {"features", "labels", "evidence_class"}, "ABC dataset")
    groups = spec["feature_groups"]
    if not isinstance(groups, dict) or set(groups) != {"baseline", "sentiment", "events"}:
        raise ChangeError("baseline, sentiment and events feature groups are required")
    if not all(isinstance(names, list) for names in groups.values()):
        raise ChangeError("feature groups must be explicit name lists")
    all_names = [n for names in groups.values() for n in names]
    if not all(groups.values()) or len(all_names) != len(set(all_names)):
        raise ChangeError("feature groups must be nonempty and disjoint")
    if not all(isinstance(n, str) and n for n in all_names):
        raise ChangeError("invalid feature name")
    finite(spec["l2"], "l2", minimum=0.000001)
    if type(spec["minimum_training_rows"]) is not int or spec["minimum_training_rows"] < 3:
        raise ChangeError("minimum_training_rows must be at least three")
    as_of = timestamp(spec["as_of"])
    seen, event_keys, features = set(), set(), []
    for row in dataset["features"]:
        strict_keys(row, {"id", "symbol", "isin", "decision_at", "entry_at", "horizon_sessions",
                          "features", "known_at", "cost_bps", "cost_known_at"}, "feature row")
        if row["id"] in seen:
            raise ChangeError("duplicate feature row")
        seen.add(row["id"])
        event_key = (row["symbol"], row["isin"], row["decision_at"])
        if event_key in event_keys:
            raise ChangeError("duplicate company decision observation")
        event_keys.add(event_key)
        decision, entry = timestamp(row["decision_at"]), timestamp(row["entry_at"])
        if entry <= decision or decision > as_of:
            raise ChangeError("invalid decision or entry clock")
        if set(row["features"]) != set(all_names) or set(row["known_at"]) != set(all_names):
            raise ChangeError("features and individual clocks must match the frozen groups")
        for name, value in row["features"].items():
            if value is not None:
                finite(value, name)
            if timestamp(row["known_at"][name]) > decision:
                raise ChangeError("feature leaks future information")
        finite(row["cost_bps"], "cost_bps", minimum=0, maximum=10000)
        if timestamp(row["cost_known_at"]) > decision:
            raise ChangeError("execution-cost assumption was not known at decision")
        if type(row["horizon_sessions"]) is not int or row["horizon_sessions"] < 1:
            raise ChangeError("invalid horizon")
        features.append(row)
    if not features or len({r["horizon_sessions"] for r in features}) != 1:
        raise ChangeError("one nonempty horizon per controlled comparison is required")
    labels = {}
    for row in dataset["labels"]:
        strict_keys(row, {"id", "exit_at", "available_at", "target_excess_return"}, "label")
        if row["id"] in labels or row["id"] not in seen:
            raise ChangeError("duplicate or unmatched label")
        exit_at, available = timestamp(row["exit_at"]), timestamp(row["available_at"])
        if available < exit_at or available > as_of:
            raise ChangeError("unmatured or invalid label availability")
        feature = next(f for f in features if f["id"] == row["id"])
        if exit_at <= timestamp(feature["entry_at"]):
            raise ChangeError("label exits before entry")
        finite(row["target_excess_return"], "target_excess_return")
        labels[row["id"]] = row
    if not isinstance(spec["folds"], list) or not spec["folds"]:
        raise ChangeError("at least one explicit test fold is required")
    end_previous = None
    for fold in spec["folds"]:
        strict_keys(fold, {"test_start", "test_end"}, "fold")
        begin, end = timestamp(fold["test_start"]), timestamp(fold["test_end"])
        if end < begin or (end_previous and begin <= end_previous):
            raise ChangeError("test folds overlap or are reversed")
        end_previous = end
    return features, labels, groups


def run_abc(dataset: dict, spec: dict) -> dict:
    # This is the existing implementation, not a replacement prediction framework.
    features, labels, groups = validate_dataset(dataset, spec)
    from marketlab.alpha_model import ModelExample, fit_ridge, predict_ridge
    names = {"A": groups["baseline"], "B": groups["baseline"] + groups["sentiment"],
             "C": groups["baseline"] + groups["events"]}
    output, models, folds = [], [], []
    for fold_no, fold in enumerate(spec["folds"]):
        start, end = timestamp(fold["test_start"]), timestamp(fold["test_end"])
        train = [r for r in features if r["id"] in labels and
                 timestamp(r["decision_at"]) < start and
                 timestamp(labels[r["id"]]["available_at"]) < start and
                 timestamp(labels[r["id"]]["exit_at"]) < start]
        test = [r for r in features if start <= timestamp(r["decision_at"]) <= end]
        if len(train) < spec["minimum_training_rows"] or not test:
            folds.append({"fold": fold_no, "status": "INSUFFICIENT_DATA", "train": len(train), "test": len(test)})
            continue
        folds.append({"fold": fold_no, "status": "EVALUATED", "train": len(train), "test": len(test)})
        for arm, feature_names in names.items():
            def example(row, target, feature_names=feature_names):
                label = labels.get(row["id"])
                return ModelExample(symbol=row["symbol"], isin=row["isin"],
                    feature_session=timestamp(row["decision_at"]).date().isoformat(),
                    entry_session=timestamp(row["entry_at"]).date().isoformat(),
                    exit_session=timestamp(label["exit_at"]).date().isoformat() if label else "9999-12-31",
                    horizon_sessions=row["horizon_sessions"],
                    features={n: row["features"][n] for n in feature_names}, target_excess_return=target)
            model = fit_ridge([example(r, labels[r["id"]]["target_excess_return"]) for r in train],
                              feature_names=feature_names, l2=spec["l2"], model_id=f"CC001-{arm}-{fold_no}")
            # Test labels are deliberately not handed to the prediction routine.
            predictions = predict_ridge(model, [example(r, 0.0) for r in test], prediction_role="OOS")
            artifact = {"fold": fold_no, "arm": arm, "model": asdict(model),
                        "frozen_at": now_utc(), "training_ids": [r["id"] for r in train]}
            artifact["artifact_sha256"] = canonical_hash(artifact)
            models.append(artifact)
            for row, prediction in zip(test, predictions, strict=True):
                label = labels.get(row["id"])
                output.append({"id": row["id"], "fold": fold_no, "arm": arm,
                    "prediction": prediction["prediction"], "decision_at": row["decision_at"],
                    "target": label["target_excess_return"] if label else None,
                    "assumed_cost_bps": row["cost_bps"], "model_sha256": model.model_sha256})
    metrics = {}
    for arm in names:
        rows = [r for r in output if r["arm"] == arm and r["target"] is not None]
        by_day = defaultdict(list)
        for row in rows:
            by_day[timestamp(row["decision_at"]).date().isoformat()].append(row)
        selected = [max(items, key=lambda r: (r["prediction"], r["id"])) for items in by_day.values()]
        metrics[arm] = {"scored_rows": len(rows),
            "mse": sum((r["prediction"] - r["target"]) ** 2 for r in rows) / len(rows) if rows else None,
            "top_one_per_date_mean_net_excess_diagnostic": sum(
                r["target"] - r["assumed_cost_bps"] / 10000 for r in selected) / len(selected)
            if selected else None}
    result = {"engine": "CC001-ABC-v1", "spec_sha256": canonical_hash(spec),
        "dataset_sha256": canonical_hash(dataset), "evidence_class": dataset["evidence_class"],
        "folds": folds, "models": models, "predictions": output, "metrics": metrics,
        "live_capital_allowed": False, "validated_predictive_edge": False,
        "limitations": ["Costs are supplied assumptions, not verified execution.",
            "Overlapping holding periods mean the selection diagnostic is not portfolio PnL.",
            "Historical LLM features may contain model-knowledge leakage despite clock checks.",
            "No probability calibration, significance claim, annualization or capital approval."]}
    result["report_sha256"] = canonical_hash(result)
    return result


def predict_frozen(artifact: dict, rows: list[dict]) -> list[dict]:
    """Score new feature rows without accepting outcome labels."""
    from marketlab.alpha_model import ModelExample, RidgeModel, predict_ridge
    allowed = {"symbol", "isin", "decision_at", "features", "known_at"}
    if artifact["artifact_sha256"] != canonical_hash({k: v for k, v in artifact.items() if k != "artifact_sha256"}):
        raise ChangeError("frozen model artifact integrity failure")
    data = artifact["model"]
    model = RidgeModel(**data)
    if model.model_sha256 != canonical_hash({k: v for k, v in data.items() if k != "model_sha256"}):
        raise ChangeError("model artifact hash mismatch")
    examples = []
    for row in rows:
        strict_keys(row, allowed, "unlabelled prediction row")
        cutoff = timestamp(row["decision_at"])
        if timestamp(artifact["frozen_at"]) > cutoff:
            raise ChangeError("model artifact did not exist at decision cutoff")
        if date.fromisoformat(model.training_last_exit_session) >= cutoff.date():
            raise ChangeError("model training label horizon overlaps prediction")
        if set(row["features"]) != set(model.feature_names) or set(row["known_at"]) != set(model.feature_names):
            raise ChangeError("prediction features do not match model")
        for key, value in row["features"].items():
            if value is not None:
                finite(value, key)
            if timestamp(row["known_at"][key]) > cutoff:
                raise ChangeError("future feature in prediction")
        day = cutoff.date().isoformat()
        examples.append(ModelExample(row["symbol"], row["isin"], day, day, day, 1, row["features"], 0.0))
    predictions = predict_ridge(model, examples, prediction_role="OOS")
    return [{"symbol": p["symbol"], "isin": p["isin"], "prediction": p["prediction"],
             "model_sha256": p["model_sha256"], "live_capital_allowed": False} for p in predictions]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("extraction", "abc", "predict"))
    parser.add_argument("input", type=Path)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    first = loads_unique(args.input.read_text(encoding="utf-8"))
    second = loads_unique(args.contract.read_text(encoding="utf-8"))
    if args.mode == "extraction":
        result = score_extraction(first, second)
    elif args.mode == "abc":
        result = run_abc(first, second)
    else:
        result = {"predictions": predict_frozen(second, first), "live_capital_allowed": False}
    folder = writable_workspace(args.out)
    digest = canonical_hash(result)
    path = folder / f"{digest}.json"
    raw = json.dumps(result, indent=2, allow_nan=False).encode()
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ChangeError("evaluation artifact conflict")
    print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
