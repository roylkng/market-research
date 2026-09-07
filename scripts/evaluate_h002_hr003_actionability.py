from __future__ import annotations

import argparse
import json
import tempfile
from argparse import Namespace
from pathlib import Path

import evaluate_h002_hr002_actionability as frozen_gate_evaluator

EXPERIMENT_ID = "H002-HR003"
SOURCE_GATE_EXPERIMENT_ID = "H002-HR002"
SOURCE_GATE_ID = "H002-HR002-OUTCOME-GATE-V1"


class PitGateError(ValueError):
    pass


def run(args: argparse.Namespace) -> dict:
    phase_b_path = Path(args.phase_b)
    phase_b = json.loads(phase_b_path.read_text(encoding="utf-8"))
    if not isinstance(phase_b, dict):
        raise PitGateError("HR003 outcome manifest root must be an object")
    if phase_b.get("replay_rule_id") != EXPERIMENT_ID:
        raise PitGateError("outcome manifest is not H002-HR003")
    if phase_b.get("live_capital_allowed") is not False:
        raise PitGateError("historical HR003 outcome manifest unexpectedly authorizes capital")

    # Do not fork or duplicate the pre-registered gate implementation.  Feed the
    # exact HR003 records/summary into the original HR002 evaluator with only the
    # experiment identity translated for its pre-existing identity guard.
    compatibility_view = dict(phase_b)
    compatibility_view["replay_rule_id"] = SOURCE_GATE_EXPERIMENT_ID

    with tempfile.TemporaryDirectory(prefix="h002-hr003-gate-") as temporary:
        temporary_root = Path(temporary)
        compatibility_path = temporary_root / "phase-b-compatibility-view.json"
        result_path = temporary_root / "gate-result.json"
        compatibility_path.write_text(
            json.dumps(compatibility_view, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        frozen_gate_evaluator.run(
            Namespace(
                gate=args.gate,
                phase_b=str(compatibility_path),
                output=str(result_path),
            )
        )
        result = json.loads(result_path.read_text(encoding="utf-8"))

    if result.get("gate_id") != SOURCE_GATE_ID:
        raise PitGateError("frozen actionability evaluator returned an unexpected gate")
    if result.get("phase_b_manifest_sha256") != phase_b.get("manifest_sha256"):
        raise PitGateError("gate verdict is not bound to the actual HR003 Phase-B manifest")
    result["gate_application"] = {
        "experiment_id": EXPERIMENT_ID,
        "source_gate_experiment_id": SOURCE_GATE_EXPERIMENT_ID,
        "source_gate_id": SOURCE_GATE_ID,
        "threshold_changes": False,
        "identity_translation_only": True,
    }
    result["CAPITAL_READY"] = {
        "passed": False,
        "reason": "prospective_H002_FY27Q2_not_completed",
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": result["verdict"],
                "watchlist": result["WATCHLIST_FILTER"]["passed"],
                "avoidance": result["ACTIONABLE_AVOIDANCE"]["passed"],
                "long_alpha": result["LONG_ALPHA_CANDIDATE"]["passed"],
                "threshold_changes": False,
            },
            sort_keys=True,
        )
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply the unchanged HR002 actionability gate to H002-HR003"
    )
    parser.add_argument(
        "--gate",
        default="registry/h002_hr002_outcome_gate.yaml",
    )
    parser.add_argument(
        "--phase-b",
        default="research/historical/h002/H002-HR003/phase-b/point-in-time-nifty200-outcomes.json",
    )
    parser.add_argument(
        "--output",
        default="research/historical/h002/H002-HR003/phase-b/actionability-gate-v1.json",
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
