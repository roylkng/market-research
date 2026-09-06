from typer.testing import CliRunner

from marketlab.cli import app

runner = CliRunner()


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
