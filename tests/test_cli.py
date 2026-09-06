import json
from datetime import UTC, datetime

from typer.testing import CliRunner

from marketlab.cli import app
from marketlab.universe import build_universe_snapshot

runner = CliRunner()


def _ccl_universe_file(tmp_path):
    snapshot = build_universe_snapshot(
        {"timestamp": "x", "data": [{"symbol": "CCL", "ffmc": 100}]},
        lambda _: {
            "info": {"isin": "INE421D01022", "listingDate": "01-Jan-2000"},
            "industryInfo": {
                "macro": "Consumer Discretionary",
                "sector": "Consumer",
                "industry": "Coffee",
                "basicIndustry": "Coffee",
            },
        },
        cohort_id="FY27-Q1-TEST",
        selection_size=1,
        captured_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    path = tmp_path / "universe.json"
    path.write_text(json.dumps(snapshot.to_dict()), encoding="utf-8")
    return path


def test_evaluate_signal_runs_against_published_fixture():
    result = runner.invoke(
        app,
        [
            "evaluate-signal",
            "data/fixtures/h002_feasibility.csv",
            "--signal-col",
            "ue",
            "--excess-col",
            "excess_vs_nifty",
        ],
    )
    assert result.exit_code == 0, result.output
    assert '"n": 24' in result.output
    assert '"pearson"' in result.output
    assert '"spearman"' in result.output


def test_evaluate_binary_runs_against_published_fixture():
    result = runner.invoke(
        app,
        [
            "evaluate-binary",
            "data/fixtures/h002_feasibility.csv",
            "--group-col",
            "ue_sign",
            "--excess-col",
            "excess_vs_nifty",
        ],
    )
    assert result.exit_code == 0, result.output
    assert '"positive_n": 16' in result.output
    assert '"negative_n": 8' in result.output
    assert '"winner_concentration"' in result.output


def test_missing_csv_has_concise_actionable_error():
    result = runner.invoke(
        app,
        [
            "evaluate-signal",
            "observations.csv",
            "--signal-col",
            "ue",
            "--excess-col",
            "excess_vs_nifty",
        ],
    )
    assert result.exit_code == 2
    assert "input CSV not found: observations.csv" in result.output
    assert "data/fixtures/h002_feasibility.csv" in result.output
    assert "Traceback" not in result.output


def test_missing_column_has_concise_error(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("ue,other\n0.1,1\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "evaluate-signal",
            str(path),
            "--signal-col",
            "ue",
            "--excess-col",
            "excess_vs_nifty",
        ],
    )
    assert result.exit_code == 2
    assert "missing required column(s): excess_vs_nifty" in result.output
    assert "available columns: ue, other" in result.output
    assert "Traceback" not in result.output


def test_reconstruct_event_is_runnable_and_historical_only(tmp_path):
    fixture = "data/fixtures/filings/ccl_fy27_q1_consolidated_source_derived.html"
    result = runner.invoke(
        app,
        [
            "reconstruct-event",
            fixture,
            "--source-url",
            "https://example.invalid/ccl",
            "--store",
            str(tmp_path / "store"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert '"symbol": "CCL"' in result.output
    assert '"mode": "HISTORICAL_RECONSTRUCTION"' in result.output
    assert '"created": true' in result.output

    second = runner.invoke(
        app,
        [
            "reconstruct-event",
            fixture,
            "--source-url",
            "https://example.invalid/ccl",
            "--store",
            str(tmp_path / "store"),
        ],
    )
    assert second.exit_code == 0, second.output
    assert '"created": false' in second.output


def test_capture_prospective_event_records_universe_and_discovery_provenance(tmp_path):
    source = "data/fixtures/filings/ccl_fy27_q1_consolidated_source_derived.html"
    discovery = tmp_path / "discovery.json"
    discovery.write_text('{"symbol":"CCL","source":"fixture"}', encoding="utf-8")
    universe = _ccl_universe_file(tmp_path)
    result = runner.invoke(
        app,
        [
            "capture-prospective-event",
            source,
            str(discovery),
            str(universe),
            "--source-url",
            "https://example.invalid/ccl",
            "--published-at",
            "2026-07-27T14:56:14Z",
            "--store",
            str(tmp_path / "store"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert '"mode": "PROSPECTIVE"' in result.output
    assert '"cohort_id": "FY27-Q1-TEST"' in result.output
    assert '"discovery_sha256"' in result.output
    assert '"universe_snapshot_sha256"' in result.output
    assert '"created": true' in result.output


def test_validate_universe_detects_valid_snapshot(tmp_path):
    universe = _ccl_universe_file(tmp_path)
    result = runner.invoke(app, ["validate-universe", str(universe)])
    assert result.exit_code == 0, result.output
    assert "universe valid: cohort=FY27-Q1-TEST" in result.output


def test_delivery_report_runs_for_source_grounded_claim_ledger():
    result = runner.invoke(
        app,
        [
            "delivery-report",
            "research/company-intelligence/claims_v1.yaml",
            "--symbol",
            "SHAILY",
        ],
    )
    assert result.exit_code == 0, result.output
    assert '"symbol": "SHAILY"' in result.output
    assert '"LATE": 1' in result.output
    assert '"met_rate_resolved": 0.0' in result.output


def test_delivery_report_rejects_unknown_symbol():
    result = runner.invoke(
        app,
        [
            "delivery-report",
            "research/company-intelligence/claims_v1.yaml",
            "--symbol",
            "DOESNOTEXIST",
        ],
    )
    assert result.exit_code == 2
    assert "no claims found for symbol" in result.output


def test_delivery_feature_default_minimum_yields_no_signal_for_single_claim_history():
    result = runner.invoke(
        app,
        [
            "delivery-feature",
            "research/company-intelligence/claims_v1.yaml",
            "--symbol",
            "CCL",
            "--as-of",
            "2026-09-06",
        ],
    )
    assert result.exit_code == 0, result.output
    assert '"resolved_count": 1' in result.output
    assert '"minimum_resolved_claims": 3' in result.output
    assert '"signal_state": "NO_SIGNAL"' in result.output
    assert '"value": null' in result.output


def test_delivery_feature_as_of_does_not_see_future_outcome():
    result = runner.invoke(
        app,
        [
            "delivery-feature",
            "research/company-intelligence/claims_v1.yaml",
            "--symbol",
            "CCL",
            "--as-of",
            "2025-05-05",
            "--min-resolved-claims",
            "1",
        ],
    )
    assert result.exit_code == 0, result.output
    assert '"resolved_count": 0' in result.output
    assert '"signal_state": "NO_SIGNAL"' in result.output

    after = runner.invoke(
        app,
        [
            "delivery-feature",
            "research/company-intelligence/claims_v1.yaml",
            "--symbol",
            "CCL",
            "--as-of",
            "2025-05-06",
            "--min-resolved-claims",
            "1",
        ],
    )
    assert after.exit_code == 0, after.output
    assert '"resolved_count": 1' in after.output
    assert '"signal_state": "ELIGIBLE"' in after.output
    assert '"value": 1.0' in after.output
