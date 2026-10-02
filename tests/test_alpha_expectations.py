from dataclasses import asdict

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_expectations import build_h021_expectations_panel
from marketlab.calendar_snapshot import CalendarSnapshot
from marketlab.execution import TradingSession
from marketlab.h021 import compare_snapshots, select_primary_top_decile

SOURCE_VERSION = "source-v1"
UNIVERSE_PATH = "research/prospective/universes/test-u001.json"
UNIVERSE_BLOB = "u" * 40


def _snapshot(
    day: str,
    *,
    captured_at_utc: str,
    eps_values: tuple[float, ...],
    analyst_counts: tuple[int, ...] | None = None,
) -> dict:
    counts = analyst_counts or tuple(6 for _ in eps_values)
    observations = []
    for index, (eps, analysts) in enumerate(
        zip(eps_values, counts, strict=True)
    ):
        symbol = f"S{index:02d}"
        observations.append(
            {
                "symbol": symbol,
                "isin": f"INE{index:09d}",
                "universe_rank": index + 1,
                "batch_id": "B01",
                "fiscal_period": "FY27",
                "period_ending": "2027-03-31",
                "consensus_eps": eps,
                "eps_currency": "INR",
                "revenue_growth_forecast_pct": 10.0 + index,
                "profit_growth_estimate_pct": 12.0 + index,
                "analyst_count": analysts,
                "target_price_inr": 100.0 + index,
                "source_observed_market_date": day,
                "source_url": f"https://stockanalysis.com/stocks/{symbol.lower()}/forecast/",
                "source_status": "TEST",
                "data_state": "PARTIAL",
            }
        )
    return {
        "schema_version": 1,
        "hypothesis_id": "H021",
        "logical_capture_id": f"{day}-full-u001-v1",
        "capture_date_ist": day,
        "captured_at_utc": captured_at_utc,
        "source_version": SOURCE_VERSION,
        "universe_path": UNIVERSE_PATH,
        "universe_git_blob_sha": UNIVERSE_BLOB,
        "outcomes_opened": False,
        "live_capital_allowed": False,
        "observations": observations,
    }


def _manifest(snapshot: dict, marker: str) -> dict:
    return {
        "logical_capture_id": snapshot["logical_capture_id"],
        "capture_date_ist": snapshot["capture_date_ist"],
        "captured_at_utc": snapshot["captured_at_utc"],
        "source_version": snapshot["source_version"],
        "universe_path": snapshot["universe_path"],
        "universe_git_blob_sha": snapshot["universe_git_blob_sha"],
        "payload_gzip_sha256": marker * 64,
        "payload_uncompressed_sha256": marker.upper() * 64,
    }


def _universe(count: int) -> dict:
    return {
        "schema_version": 2,
        "sha256": "f" * 64,
        "members": [
            {
                "symbol": f"S{index:02d}",
                "isin": f"INE{index:09d}",
                "rank": index + 1,
            }
            for index in range(count)
        ],
    }


def _comparison(prior: dict, current: dict) -> dict:
    revisions = compare_snapshots(prior, current)
    selected = select_primary_top_decile(revisions)
    return {
        "schema_version": 1,
        "hypothesis_id": "H021",
        "prior_capture_date_ist": prior["capture_date_ist"],
        "current_capture_date_ist": current["capture_date_ist"],
        "revision_observations": [asdict(row) for row in revisions],
        "primary_top_decile_symbols": [row.symbol for row in selected],
        "outcomes_opened": False,
        "live_capital_allowed": False,
    }


def _calendar(
    sessions: list[str],
    *,
    unresolved: tuple[str, ...] = (),
) -> CalendarSnapshot:
    return CalendarSnapshot(
        schema_version=1,
        sha256="c" * 64,
        version="TEST-CALENDAR-v1",
        build_rule="nse-cm-weekday-minus-official-holidays-v1",
        captured_at_utc="2026-09-01T00:00:00Z",
        source_url="https://www.nseindia.com/api/holiday-master?type=trading",
        source_sha256="d" * 64,
        start_date=min(sessions),
        end_date=max(sessions),
        sessions=tuple(
            TradingSession(
                session_date=day,
                open_timestamp_utc=f"{day}T03:45:00Z",
                close_timestamp_utc=f"{day}T10:00:00Z",
            )
            for day in sessions
        ),
        holidays=(),
        unresolved_special_dates=unresolved,
        special_sessions=(),
    )


def test_expectations_adapter_preserves_full_u001_and_primary_rank() -> None:
    prior = _snapshot(
        "2026-09-11",
        captured_at_utc="2026-09-11T12:30:00+00:00",
        eps_values=(10.0, 10.0, 10.0, 10.0),
    )
    current = _snapshot(
        "2026-10-09",
        captured_at_utc="2026-10-09T12:30:00+00:00",
        eps_values=(12.0, 11.0, 10.0, 9.0),
    )
    panel = build_h021_expectations_panel(
        prior=prior,
        current=current,
        prior_manifest=_manifest(prior, "a"),
        current_manifest=_manifest(current, "b"),
        comparison=_comparison(prior, current),
        universe=_universe(4),
        calendar=_calendar(["2026-10-09", "2026-10-12"]),
    )

    assert panel["row_count"] == 4
    assert panel["primary_signal_available_count"] == 4
    assert panel["primary_top_decile_symbols"] == ["S00"]
    assert panel["ae001_same_day_eod_1830_compatible"] is True
    assert panel["earliest_execution_session"] == "2026-10-12"
    assert panel["earliest_execution_open_utc"] == "2026-10-12T03:45:00Z"
    assert len(panel["panel_sha256"]) == 64

    by_symbol = {row["symbol"]: row for row in panel["rows"]}
    assert by_symbol["S00"]["isin"] == "INE000000000"
    assert by_symbol["S00"]["values"][
        "h021_primary_eps_revision_30d_pct"
    ] == pytest.approx(20.0)
    assert by_symbol["S00"]["values"][
        "h021_primary_eps_revision_rank_pct"
    ] == pytest.approx(1.0)
    assert by_symbol["S03"]["values"][
        "h021_primary_eps_revision_rank_pct"
    ] == pytest.approx(0.0)


def test_low_coverage_row_is_preserved_with_null_primary_but_diagnostics() -> None:
    prior = _snapshot(
        "2026-09-11",
        captured_at_utc="2026-09-11T12:30:00+00:00",
        eps_values=(10.0, 10.0),
        analyst_counts=(6, 6),
    )
    current = _snapshot(
        "2026-10-09",
        captured_at_utc="2026-10-09T12:30:00+00:00",
        eps_values=(11.0, 12.0),
        analyst_counts=(6, 4),
    )
    current["observations"][1]["revenue_growth_forecast_pct"] = 14.0
    prior["observations"][1]["revenue_growth_forecast_pct"] = 11.0

    panel = build_h021_expectations_panel(
        prior=prior,
        current=current,
        prior_manifest=_manifest(prior, "a"),
        current_manifest=_manifest(current, "b"),
        comparison=_comparison(prior, current),
        universe=_universe(2),
        calendar=_calendar(["2026-10-09", "2026-10-12"]),
    )
    by_symbol = {row["symbol"]: row for row in panel["rows"]}
    row = by_symbol["S01"]
    assert row["primary_signal_reason"] == "ANALYST_COVERAGE_LT_5"
    assert row["values"]["h021_primary_eps_revision_30d_pct"] is None
    assert row["values"]["h021_primary_eps_revision_rank_pct"] is None
    assert row["values"]["h021_revenue_growth_change_pp"] == pytest.approx(3.0)
    assert row["values"]["h021_primary_coverage_flag"] == pytest.approx(0.0)
    assert row["values"][
        "h021_primary_signal_available_flag"
    ] == pytest.approx(0.0)
    assert panel["row_count"] == 2


def test_late_capture_is_not_same_day_ae001_eod_information() -> None:
    prior = _snapshot(
        "2026-09-11",
        captured_at_utc="2026-09-11T12:30:00+00:00",
        eps_values=(10.0,),
    )
    current = _snapshot(
        "2026-10-09",
        captured_at_utc="2026-10-09T13:05:00+00:00",
        eps_values=(11.0,),
    )
    panel = build_h021_expectations_panel(
        prior=prior,
        current=current,
        prior_manifest=_manifest(prior, "a"),
        current_manifest=_manifest(current, "b"),
        comparison=_comparison(prior, current),
        universe=_universe(1),
        calendar=_calendar(["2026-10-09", "2026-10-12"]),
    )
    assert panel["ae001_same_day_eod_1830_compatible"] is False
    assert panel["feature_known_at_utc"] == "2026-10-09T13:05:00Z"
    assert panel["earliest_execution_session"] == "2026-10-12"


def test_unresolved_special_session_blocks_execution_path() -> None:
    prior = _snapshot(
        "2026-10-09",
        captured_at_utc="2026-10-09T12:30:00+00:00",
        eps_values=(10.0,),
    )
    current = _snapshot(
        "2026-11-06",
        captured_at_utc="2026-11-06T12:30:00+00:00",
        eps_values=(11.0,),
    )
    with pytest.raises(AlphaContractError, match="unresolved NSE special"):
        build_h021_expectations_panel(
            prior=prior,
            current=current,
            prior_manifest=_manifest(prior, "a"),
            current_manifest=_manifest(current, "b"),
            comparison=_comparison(prior, current),
            universe=_universe(1),
            calendar=_calendar(
                ["2026-11-06", "2026-11-09"],
                unresolved=("2026-11-08",),
            ),
        )


def test_tampered_h021_comparison_is_rejected() -> None:
    prior = _snapshot(
        "2026-09-11",
        captured_at_utc="2026-09-11T12:30:00+00:00",
        eps_values=(10.0,),
    )
    current = _snapshot(
        "2026-10-09",
        captured_at_utc="2026-10-09T12:30:00+00:00",
        eps_values=(11.0,),
    )
    comparison = _comparison(prior, current)
    comparison["revision_observations"][0]["eps_revision_pct"] = 999.0

    with pytest.raises(AlphaContractError, match="do not reproduce"):
        build_h021_expectations_panel(
            prior=prior,
            current=current,
            prior_manifest=_manifest(prior, "a"),
            current_manifest=_manifest(current, "b"),
            comparison=comparison,
            universe=_universe(1),
            calendar=_calendar(["2026-10-09", "2026-10-12"]),
        )


def test_manifest_binding_is_fail_closed() -> None:
    prior = _snapshot(
        "2026-09-11",
        captured_at_utc="2026-09-11T12:30:00+00:00",
        eps_values=(10.0,),
    )
    current = _snapshot(
        "2026-10-09",
        captured_at_utc="2026-10-09T12:30:00+00:00",
        eps_values=(11.0,),
    )
    current_manifest = _manifest(current, "b")
    current_manifest["captured_at_utc"] = "2026-10-09T12:31:00+00:00"

    with pytest.raises(AlphaContractError, match="snapshot/manifest"):
        build_h021_expectations_panel(
            prior=prior,
            current=current,
            prior_manifest=_manifest(prior, "a"),
            current_manifest=current_manifest,
            comparison=_comparison(prior, current),
            universe=_universe(1),
            calendar=_calendar(["2026-10-09", "2026-10-12"]),
        )
