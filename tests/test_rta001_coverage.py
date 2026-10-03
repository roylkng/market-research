import json
from pathlib import Path

import pytest
import yaml

from marketlab.rta001 import build_rta001_summary
from scripts.validate_rta001_coverage import (
    RTA001CoverageError,
    validate_repository_accounting,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _repo(tmp_path: Path) -> Path:
    root = tmp_path
    manifest = {
        "schema_version": 1,
        "accounting_id": "RTA001-v1",
        "as_of_date": "2026-10-03",
        "live_capital_allowed": False,
        "fdr_families": {
            "F1": {"alpha": 0.05},
        },
        "trials": [
            {
                "trial_id": "AE001-T001",
                "category": "ALPHA_FEATURE_DISCOVERY",
                "registration_mode": "PRE_REGISTERED_BEFORE_OUTCOMES",
                "result_path": "research/ae001-t001-result-v1.json",
                "result_state": "COMPLETE",
                "reported_primary_supported": False,
                "primary_endpoint": "TEST",
                "p_value_status": "SCALAR",
                "nominal_primary_p_value": 0.5,
                "fdr_accounting_p_value": 0.5,
                "fdr_family": "F1",
                "scientifically_preregistered_before_outcomes": True,
            },
            {
                "trial_id": "H001",
                "category": "MECHANISM_HYPOTHESIS",
                "registration_mode": "LEGACY_REPOSITORY_HYPOTHESIS",
                "result_state": "FROZEN",
                "reported_primary_supported": None,
                "primary_endpoint": "LEGACY",
                "p_value_status": "PENDING",
                "nominal_primary_p_value": None,
                "fdr_accounting_p_value": None,
                "fdr_family": None,
                "scientifically_preregistered_before_outcomes": True,
            },
        ],
        "source_feasibility_results": [
            "research/ae001-d001-result-v1.json"
        ],
    }
    _write_json(root / "research/rta001-trials-v1.json", manifest)
    _write_json(
        root / "research/rta001-summary-v1.json",
        build_rta001_summary(manifest),
    )
    _write_json(
        root / "research/ae001-t001-result-v1.json",
        {"live_capital_allowed": False},
    )
    _write_json(
        root / "research/ae001-d001-result-v1.json",
        {"live_capital_allowed": False},
    )
    _write_json(
        root / "research/ae001/trial-ledger.json",
        {
            "events": [
                {
                    "event_type": "TRIAL_REGISTERED",
                    "trial_id": "AE001-T001",
                }
            ]
        },
    )
    registry = {
        "version": 1,
        "live_capital_allowed": False,
        "hypotheses": [{"id": "H001"}],
    }
    path = root / "registry/hypotheses.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(registry), encoding="utf-8")
    return root


def test_repository_accounting_passes_when_all_surfaces_match(tmp_path):
    root = _repo(tmp_path)
    report = validate_repository_accounting(
        repo_root=root,
        manifest_path=Path("research/rta001-trials-v1.json"),
        summary_path=Path("research/rta001-summary-v1.json"),
    )
    assert report["coverage_complete"] is True
    assert report["research_result_artifact_count"] == 2
    assert report["ae001_registered_trial_count"] == 1
    assert report["canonical_hypothesis_count"] == 1


def test_unaccounted_result_artifact_fails_closed(tmp_path):
    root = _repo(tmp_path)
    _write_json(
        root / "research/new-result-v1.json",
        {"live_capital_allowed": False},
    )
    with pytest.raises(RTA001CoverageError, match="missing explicit RTA001"):
        validate_repository_accounting(
            repo_root=root,
            manifest_path=Path("research/rta001-trials-v1.json"),
            summary_path=Path("research/rta001-summary-v1.json"),
        )


def test_new_ae001_registration_requires_rta_entry(tmp_path):
    root = _repo(tmp_path)
    ledger_path = root / "research/ae001/trial-ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["events"].append(
        {
            "event_type": "TRIAL_REGISTERED",
            "trial_id": "AE001-T999",
        }
    )
    _write_json(ledger_path, ledger)
    with pytest.raises(RTA001CoverageError, match="AE001-T999"):
        validate_repository_accounting(
            repo_root=root,
            manifest_path=Path("research/rta001-trials-v1.json"),
            summary_path=Path("research/rta001-summary-v1.json"),
        )


def test_new_hypothesis_requires_rta_entry(tmp_path):
    root = _repo(tmp_path)
    registry_path = root / "registry/hypotheses.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    registry["hypotheses"].append({"id": "H999"})
    registry_path.write_text(yaml.safe_dump(registry), encoding="utf-8")
    with pytest.raises(RTA001CoverageError, match="H999"):
        validate_repository_accounting(
            repo_root=root,
            manifest_path=Path("research/rta001-trials-v1.json"),
            summary_path=Path("research/rta001-summary-v1.json"),
        )


def test_stale_summary_fails_closed(tmp_path):
    root = _repo(tmp_path)
    summary_path = root / "research/rta001-summary-v1.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["explicit_trial_count"] = 999
    _write_json(summary_path, summary)
    with pytest.raises(RTA001CoverageError, match="summary is stale"):
        validate_repository_accounting(
            repo_root=root,
            manifest_path=Path("research/rta001-trials-v1.json"),
            summary_path=Path("research/rta001-summary-v1.json"),
        )
