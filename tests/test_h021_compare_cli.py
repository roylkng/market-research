from __future__ import annotations

import gzip
import json
import subprocess
import sys
from pathlib import Path


def _snapshot(day: str, eps: float) -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "H021",
        "capture_date_ist": day,
        "captured_at_utc": f"{day}T12:00:00+00:00",
        "outcomes_opened": False,
        "live_capital_allowed": False,
        "observations": [
            {
                "symbol": "AAA",
                "fiscal_period": "FY27",
                "period_ending": "2027-03-31",
                "consensus_eps": eps,
                "eps_currency": "INR",
                "revenue_growth_forecast_pct": 10.0,
                "profit_growth_estimate_pct": 12.0,
                "analyst_count": 6,
                "target_price_inr": 100.0,
                "source_observed_market_date": day,
                "source_url": "https://stockanalysis.com/aaa",
                "source_status": "TEST",
            }
        ],
    }


def _write_snapshot_with_manifest(path: Path, snapshot: dict) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(snapshot, handle)
    base = path.name[: -len(".json.gz")]
    manifest = {
        "source_version": "source-v1",
        "universe_path": "research/prospective/universes/u001.json",
        "universe_git_blob_sha": "abc123",
    }
    path.with_name(f"{base}.manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def test_compare_cli_reads_gzip_and_manifest_identity(tmp_path: Path) -> None:
    prior = tmp_path / "2026-09-11-full-u001-v1.json.gz"
    current = tmp_path / "2026-10-11-full-u001-v1.json.gz"
    output = tmp_path / "comparison.json"
    _write_snapshot_with_manifest(prior, _snapshot("2026-09-11", 10.0))
    _write_snapshot_with_manifest(current, _snapshot("2026-10-11", 11.0))

    script = Path(__file__).resolve().parents[1] / "scripts" / "compare_h021_captures.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--prior",
            str(prior),
            "--current",
            str(current),
            "--out",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["capture_interval_days"] == 30
    assert result["primary_signal_available_count"] == 1
    assert result["primary_top_decile_count"] == 1
    assert result["primary_top_decile_symbols"] == ["AAA"]
    assert result["source_version"] == "source-v1"
    row = result["revision_observations"][0]
    assert row["period_ending_prior"] == "2027-03-31"
    assert row["period_ending_current"] == "2027-03-31"
    assert row["eps_currency_prior"] == "INR"
    assert row["eps_currency_current"] == "INR"
