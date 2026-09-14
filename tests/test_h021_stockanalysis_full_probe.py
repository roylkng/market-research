from __future__ import annotations

from marketlab.h021_stockanalysis_full_probe import (
    aggregate_shard_reports,
    build_batch_targets,
    summarize_probe_rows,
    validate_full_probe_config,
)


def _config() -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "H021-STOCKANALYSIS-FULL-U001-PROBE",
        "expected_total_symbols": 4,
        "batch_ids": ["B01", "B02"],
        "retain_raw_provider_html": False,
        "outcomes_opened": False,
        "live_capital_allowed": False,
        "timeout_seconds": 20,
        "sleep_seconds_between_requests": 4.0,
    }


def _universe() -> dict:
    return {
        "members": [
            {"symbol": "A", "rank": 1, "isin": "I1"},
            {"symbol": "B", "rank": 2, "isin": "I2"},
            {"symbol": "C", "rank": 3, "isin": "I3"},
            {"symbol": "D", "rank": 4, "isin": "I4"},
        ]
    }


def _anchor() -> dict:
    return {
        "observations": [
            {
                "symbol": symbol,
                "fiscal_period": "FY2027",
                "period_ending": "2027-03-31",
                "eps_currency": "INR",
                "consensus_eps": 10.0 + index,
            }
            for index, symbol in enumerate(["A", "B", "C", "D"])
        ]
    }


def _batches() -> dict:
    return {
        "batches": [
            {"batch_id": "B01", "rank_min": 1, "rank_max": 2},
            {"batch_id": "B02", "rank_min": 3, "rank_max": 4},
        ]
    }


def test_real_contract_requires_frozen_u001_size() -> None:
    config = _config()
    assert any("100" in error for error in validate_full_probe_config(config))
    config["expected_total_symbols"] = 100
    assert validate_full_probe_config(config) == []


def test_build_batch_targets_uses_anchor_semantics_and_rank_order() -> None:
    targets = build_batch_targets(_anchor(), _universe(), _batches(), "B02")
    assert [row["symbol"] for row in targets] == ["C", "D"]
    assert [row["rank"] for row in targets] == [3, 4]
    assert all(row["anchor_fiscal_period"] == "FY2027" for row in targets)
    assert all(row["anchor_period_ending"] == "2027-03-31" for row in targets)
    assert all(row["anchor_eps_currency"] == "INR" for row in targets)


def test_summarize_probe_rows_keeps_failures_visible() -> None:
    rows = [
        {
            "state": "PARSED",
            "probe_pass": True,
            "parser_pass": True,
            "semantic_match_pass": True,
            "parsed": {"eps_currency_source_url": "forecast"},
        },
        {
            "state": "PARSE_ERROR",
            "probe_pass": False,
            "parser_pass": False,
            "semantic_match_pass": False,
        },
    ]
    summary = summarize_probe_rows(rows)
    assert summary["total"] == 2
    assert summary["probe_pass"] == 1
    assert summary["state_counts"] == {"PARSED": 1, "PARSE_ERROR": 1}


def test_aggregate_requires_exact_batches_unique_symbols_and_all_rows() -> None:
    config = _config()
    config["expected_total_symbols"] = 4
    # Unit fixture intentionally uses four symbols; production config validation is
    # exercised separately, so aggregation receives the frozen shape through a copy.
    original_validate_size = config["expected_total_symbols"]
    assert original_validate_size == 4

    # Build reports using a production-sized config contract then override only inside
    # the report fixture is not allowed by aggregate. Use a 100-row fixture instead.
    config["expected_total_symbols"] = 100
    rows = []
    for rank in range(1, 101):
        rows.append(
            {
                "symbol": f"S{rank:03d}",
                "rank": rank,
                "state": "PARSED",
                "probe_pass": True,
                "parser_pass": True,
                "semantic_match_pass": True,
                "parsed": {"eps_currency_source_url": "forecast"},
            }
        )
    reports = [
        {
            "hypothesis_id": "H021-STOCKANALYSIS-FULL-U001-PROBE",
            "batch_id": "B01",
            "rows": rows[:50],
            "outcomes_opened": False,
            "live_capital_allowed": False,
        },
        {
            "hypothesis_id": "H021-STOCKANALYSIS-FULL-U001-PROBE",
            "batch_id": "B02",
            "rows": rows[50:],
            "outcomes_opened": False,
            "live_capital_allowed": False,
        },
    ]
    aggregate = aggregate_shard_reports(config, reports)
    assert aggregate["summary"]["total"] == 100
    assert aggregate["summary"]["probe_pass"] == 100
    assert aggregate["decision"]["full_u001_probe_pass_all"] is True
