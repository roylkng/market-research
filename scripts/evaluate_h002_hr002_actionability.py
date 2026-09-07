from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

PRIMARY = "nifty_50"
MOMENTUM = "nifty_200_momentum_30"


class GateError(ValueError):
    pass


def _benchmark(record: dict[str, Any], benchmark_id: str) -> dict[str, Any] | None:
    for item in record.get("benchmarks", []):
        if isinstance(item, dict) and item.get("benchmark_id") == benchmark_id:
            return item
    return None


def _completed_rows(records: list[dict[str, Any]], benchmark_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        if record.get("status") != "COMPLETED":
            continue
        benchmark = _benchmark(record, benchmark_id)
        if not benchmark or benchmark.get("status") != "COMPLETE":
            continue
        rows.append(
            {
                "symbol": str(record.get("symbol")),
                "quarter_id": str(record.get("quarter_id")),
                "bucket": str(record.get("signal_bucket")),
                "gross_return_pct": float(record["gross_return_pct"]),
                "cost50_return_pct": float(record["cost_stressed_return_pct"]["50"]),
                "benchmark_return_pct": float(benchmark["return_pct"]),
                "excess_return_pct": float(benchmark["excess_return_pct"]),
            }
        )
    return rows


def _mean(values: list[float]) -> float:
    if not values:
        raise GateError("cannot compute mean of empty group")
    return sum(values) / len(values)


def _spread(rows: list[dict[str, Any]]) -> float:
    positive = [row["excess_return_pct"] for row in rows if row["bucket"] == "POSITIVE"]
    negative = [row["excess_return_pct"] for row in rows if row["bucket"] == "NEGATIVE"]
    return _mean(positive) - _mean(negative)


def _positive_cost50_excess(rows: list[dict[str, Any]]) -> float:
    values = [
        row["cost50_return_pct"] - row["benchmark_return_pct"]
        for row in rows
        if row["bucket"] == "POSITIVE"
    ]
    return _mean(values)


def _negative_excess(rows: list[dict[str, Any]]) -> float:
    return _mean([row["excess_return_pct"] for row in rows if row["bucket"] == "NEGATIVE"])


def _quarter_groups(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["quarter_id"]].append(row)
    return dict(sorted(grouped.items()))


def _eligible_quarter_spreads(rows: list[dict[str, Any]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for quarter, group in _quarter_groups(rows).items():
        positive = sum(row["bucket"] == "POSITIVE" for row in group)
        negative = sum(row["bucket"] == "NEGATIVE" for row in group)
        if positive >= 2 and negative >= 2:
            result[quarter] = _spread(group)
    return result


def _leave_one_quarter_out(rows: list[dict[str, Any]]) -> dict[str, float]:
    quarters = sorted({row["quarter_id"] for row in rows})
    result: dict[str, float] = {}
    for omitted in quarters:
        sample = [row for row in rows if row["quarter_id"] != omitted]
        positive = sum(row["bucket"] == "POSITIVE" for row in sample)
        negative = sum(row["bucket"] == "NEGATIVE" for row in sample)
        if positive >= 2 and negative >= 2:
            result[omitted] = _spread(sample)
    return result


def _condition(name: str, passed: bool, value: Any, requirement: str) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "value": value,
        "requirement": requirement,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    gate = yaml.safe_load(Path(args.gate).read_text(encoding="utf-8"))
    if gate.get("gate_id") != "H002-HR002-OUTCOME-GATE-V1":
        raise GateError("unexpected H002-HR002 actionability gate")
    if gate.get("live_capital_allowed") is not False:
        raise GateError("historical gate must keep live capital disabled")

    phase_b = json.loads(Path(args.phase_b).read_text(encoding="utf-8"))
    if phase_b.get("replay_rule_id") != "H002-HR002":
        raise GateError("outcome manifest is not H002-HR002")
    if phase_b.get("live_capital_allowed") is not False:
        raise GateError("historical outcome manifest unexpectedly authorizes live capital")

    records = phase_b.get("records")
    if not isinstance(records, list):
        raise GateError("outcome manifest has no records")
    status = phase_b["summary"]["status_counts"]
    primary_summary = phase_b["summary"]["by_benchmark"][PRIMARY]
    momentum_summary = phase_b["summary"]["by_benchmark"][MOMENTUM]
    if not primary_summary.get("evaluation") or not momentum_summary.get("evaluation"):
        raise GateError("both frozen benchmarks require pooled evaluation")

    primary_rows = _completed_rows(records, PRIMARY)
    momentum_rows = _completed_rows(records, MOMENTUM)
    primary_quarters = _eligible_quarter_spreads(primary_rows)
    momentum_quarters = _eligible_quarter_spreads(momentum_rows)
    loo_quarter = _leave_one_quarter_out(primary_rows)

    completed = int(phase_b["summary"]["completed_count"])
    positive_n = sum(row["bucket"] == "POSITIVE" for row in primary_rows)
    negative_n = sum(row["bucket"] == "NEGATIVE" for row in primary_rows)
    represented_quarters = len({row["quarter_id"] for row in primary_rows})

    primary_eval = primary_summary["evaluation"]
    momentum_eval = momentum_summary["evaluation"]
    primary_binary = primary_eval["observation_level_binary"]
    momentum_binary = momentum_eval["observation_level_binary"]

    sample_conditions = [
        _condition("completed_observations", completed >= 250, completed, ">=250"),
        _condition("represented_quarters", represented_quarters >= 4, represented_quarters, ">=4"),
        _condition("positive_observations", positive_n >= 100, positive_n, ">=100"),
        _condition("negative_observations", negative_n >= 40, negative_n, ">=40"),
        _condition("unresolved_outcome_errors", int(status.get("ERROR", 0)) == 0, int(status.get("ERROR", 0)), "=0"),
    ]
    sample_pass = all(item["passed"] for item in sample_conditions)

    watch_conditions = [
        _condition("minimum_sample", sample_pass, sample_pass, "all minimum-sample conditions pass"),
        _condition("pooled_nifty50_spread_gt_0", float(primary_binary["spread"]) > 0, float(primary_binary["spread"]), ">0"),
        _condition(
            "pooled_nifty50_company_cluster_ci_low_gt_0",
            float(primary_eval["company_cluster_bootstrap"]["low"]) > 0,
            float(primary_eval["company_cluster_bootstrap"]["low"]),
            ">0",
        ),
        _condition(
            "leave_one_company_out_min_nifty50_spread_gt_0",
            float(primary_eval["leave_one_company_out"]["min_spread"]) > 0,
            float(primary_eval["leave_one_company_out"]["min_spread"]),
            ">0",
        ),
        _condition(
            "positive_spread_in_at_least_3_represented_quarters",
            sum(value > 0 for value in primary_quarters.values()) >= 3,
            {"positive_quarters": sum(value > 0 for value in primary_quarters.values()), "spreads": primary_quarters},
            ">=3 quarters",
        ),
    ]
    watch_pass = all(item["passed"] for item in watch_conditions)

    negative_momentum_quarters = {
        quarter: _negative_excess(group)
        for quarter, group in _quarter_groups(momentum_rows).items()
        if sum(row["bucket"] == "NEGATIVE" for row in group) >= 2
    }
    actionable_conditions = [
        _condition("WATCHLIST_FILTER_passed", watch_pass, watch_pass, "true"),
        _condition("pooled_momentum30_spread_gt_0", float(momentum_binary["spread"]) > 0, float(momentum_binary["spread"]), ">0"),
        _condition(
            "pooled_momentum30_company_cluster_ci_low_gt_0",
            float(momentum_eval["company_cluster_bootstrap"]["low"]) > 0,
            float(momentum_eval["company_cluster_bootstrap"]["low"]),
            ">0",
        ),
        _condition(
            "negative_ue_mean_excess_vs_momentum30_lt_0",
            float(momentum_binary["negative_mean"]) < 0,
            float(momentum_binary["negative_mean"]),
            "<0",
        ),
        _condition(
            "negative_ue_underperforms_momentum30_in_at_least_4_represented_quarters",
            sum(value < 0 for value in negative_momentum_quarters.values()) >= 4,
            {"underperforming_quarters": sum(value < 0 for value in negative_momentum_quarters.values()), "negative_means": negative_momentum_quarters},
            ">=4 quarters",
        ),
        _condition(
            "leave_one_quarter_out_nifty50_spread_gt_0_for_every_eligible_omission",
            bool(loo_quarter) and all(value > 0 for value in loo_quarter.values()),
            loo_quarter,
            "all >0",
        ),
    ]
    actionable_pass = all(item["passed"] for item in actionable_conditions)

    positive_cost50_primary_by_quarter = {
        quarter: _positive_cost50_excess(group)
        for quarter, group in _quarter_groups(primary_rows).items()
        if sum(row["bucket"] == "POSITIVE" for row in group) >= 2
    }
    positive_cost50_primary = _positive_cost50_excess(primary_rows)
    positive_cost50_momentum = _positive_cost50_excess(momentum_rows)
    winner_without_top2 = float(
        primary_eval["positive_group_winner_concentration"]["mean_without_top_n"]
    )
    long_conditions = [
        _condition("WATCHLIST_FILTER_passed", watch_pass, watch_pass, "true"),
        _condition(
            "positive_ue_pooled_mean_excess_vs_nifty50_after_50bps_gt_0",
            positive_cost50_primary > 0,
            positive_cost50_primary,
            ">0",
        ),
        _condition(
            "positive_ue_mean_excess_vs_nifty50_after_50bps_gt_0_in_at_least_4_represented_quarters",
            sum(value > 0 for value in positive_cost50_primary_by_quarter.values()) >= 4,
            {"positive_quarters": sum(value > 0 for value in positive_cost50_primary_by_quarter.values()), "means": positive_cost50_primary_by_quarter},
            ">=4 quarters",
        ),
        _condition(
            "positive_ue_pooled_mean_excess_vs_momentum30_after_50bps_gt_0",
            positive_cost50_momentum > 0,
            positive_cost50_momentum,
            ">0",
        ),
        _condition(
            "positive_group_result_not_reversed_after_removing_top_2_winners",
            winner_without_top2 > 0,
            winner_without_top2,
            ">0 vs Nifty 50",
        ),
    ]
    long_pass = all(item["passed"] for item in long_conditions)

    verdict = "EXPLORATORY_ONLY"
    if watch_pass:
        verdict = "WATCHLIST_FILTER"
    if actionable_pass:
        verdict = "ACTIONABLE_AVOIDANCE"
    if long_pass and not actionable_pass:
        verdict = "LONG_ALPHA_CANDIDATE"
    if long_pass and actionable_pass:
        verdict = "ACTIONABLE_AVOIDANCE_AND_LONG_ALPHA_CANDIDATE"

    result = {
        "schema_version": 1,
        "gate_id": gate["gate_id"],
        "phase_b_manifest_sha256": phase_b.get("manifest_sha256"),
        "live_capital_allowed": False,
        "verdict": verdict,
        "minimum_sample": {"passed": sample_pass, "conditions": sample_conditions},
        "WATCHLIST_FILTER": {"passed": watch_pass, "conditions": watch_conditions},
        "ACTIONABLE_AVOIDANCE": {"passed": actionable_pass, "conditions": actionable_conditions},
        "LONG_ALPHA_CANDIDATE": {"passed": long_pass, "conditions": long_conditions},
        "CAPITAL_READY": {
            "passed": False,
            "reason": "prospective_H002_FY27Q2_not_completed",
        },
        "diagnostics": {
            "primary_quarter_spreads": primary_quarters,
            "momentum_quarter_spreads": momentum_quarters,
            "leave_one_quarter_out_nifty50_spreads": loo_quarter,
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "watchlist": watch_pass, "avoidance": actionable_pass, "long_alpha": long_pass}, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate frozen H002-HR002 actionability gate")
    parser.add_argument(
        "--gate",
        default="registry/h002_hr002_outcome_gate.yaml",
    )
    parser.add_argument(
        "--phase-b",
        default="research/historical/h002/H002-HR002/phase-b/fixed-u001-six-quarter-outcomes.json",
    )
    parser.add_argument(
        "--output",
        default="research/historical/h002/H002-HR002/phase-b/actionability-gate-v1.json",
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
