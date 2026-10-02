from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import (
    AlphaContractError,
    FeatureDefinition,
    cross_sectional_percentile,
    digest,
)
from marketlab.calendar_snapshot import CalendarSnapshot
from marketlab.h021 import (
    RevisionObservation,
    compare_snapshots,
    select_primary_top_decile,
)

PANEL_ID = "AE001-H021-EXPECTATIONS-v1"
IST = ZoneInfo("Asia/Kolkata")
AE001_EOD_CUTOFF = time(18, 30)

H021_EXPECTATIONS_DEFINITIONS = [
    FeatureDefinition(
        name="h021_primary_eps_revision_30d_pct",
        family="expectations",
        version="v1",
        description=(
            "H021 28-35 day consensus EPS revision, populated only when the "
            "frozen H021 primary signal is eligible."
        ),
    ),
    FeatureDefinition(
        name="h021_primary_eps_revision_rank_pct",
        family="expectations",
        version="v1",
        description=(
            "Tie-aware percentile rank of eligible H021 primary EPS revision "
            "within the frozen U001 cross-section."
        ),
    ),
    FeatureDefinition(
        name="h021_revenue_growth_change_pp",
        family="expectations",
        version="v1",
        description=(
            "H021 same-period change in revenue-growth forecast, percentage points."
        ),
    ),
    FeatureDefinition(
        name="h021_profit_growth_change_pp",
        family="expectations",
        version="v1",
        description=(
            "H021 same-period change in profit-growth estimate, percentage points."
        ),
    ),
    FeatureDefinition(
        name="h021_target_price_revision_pct",
        family="expectations",
        version="v1",
        description="H021 same-period target-price revision percentage.",
    ),
    FeatureDefinition(
        name="h021_min_analyst_count",
        family="expectations",
        version="v1",
        description="Minimum explicit analyst count across prior/current H021 captures.",
    ),
    FeatureDefinition(
        name="h021_primary_coverage_flag",
        family="expectations",
        version="v1",
        description=(
            "One when analyst count is at least five in both H021 captures, else zero."
        ),
    ),
    FeatureDefinition(
        name="h021_primary_signal_available_flag",
        family="expectations",
        version="v1",
        description=(
            "One only when the frozen H021 primary signal reason is ELIGIBLE."
        ),
    ),
]


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise AlphaContractError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AlphaContractError(f"{field} is not an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise AlphaContractError(f"{field} must be timezone-aware")
    return parsed.astimezone(UTC)


def _capture_manifest_ref(manifest: dict[str, Any]) -> dict[str, Any]:
    required = (
        "logical_capture_id",
        "capture_date_ist",
        "captured_at_utc",
        "payload_gzip_sha256",
        "payload_uncompressed_sha256",
        "source_version",
        "universe_git_blob_sha",
    )
    for field in required:
        value = manifest.get(field)
        if not isinstance(value, str) or not value:
            raise AlphaContractError(
                f"H021 capture manifest requires non-empty {field}"
            )
    for field in ("payload_gzip_sha256", "payload_uncompressed_sha256"):
        if len(str(manifest[field])) != 64:
            raise AlphaContractError(
                f"H021 capture manifest {field} must be SHA-256"
            )
    return {
        "logical_capture_id": manifest["logical_capture_id"],
        "capture_date_ist": manifest["capture_date_ist"],
        "captured_at_utc": manifest["captured_at_utc"],
        "payload_gzip_sha256": manifest["payload_gzip_sha256"],
        "payload_uncompressed_sha256": manifest[
            "payload_uncompressed_sha256"
        ],
        "manifest_sha256": digest(manifest),
    }


def _validate_capture_manifest_binding(
    snapshot: dict[str, Any],
    manifest: dict[str, Any],
    *,
    label: str,
) -> None:
    for field in (
        "capture_date_ist",
        "captured_at_utc",
        "source_version",
        "universe_path",
        "universe_git_blob_sha",
    ):
        if snapshot.get(field) != manifest.get(field):
            raise AlphaContractError(
                f"{label} H021 snapshot/manifest {field} mismatch"
            )


def _next_execution_session(
    calendar: CalendarSnapshot,
    *,
    captured_at: datetime,
) -> tuple[str, str]:
    candidates = []
    for session in calendar.sessions:
        opened = _timestamp(
            session.open_timestamp_utc,
            "calendar.session.open_timestamp_utc",
        )
        if opened > captured_at:
            candidates.append((opened, session))
    if not candidates:
        raise AlphaContractError(
            "H021 expectations calendar has no execution session after capture"
        )
    candidates.sort(key=lambda item: item[0])
    opened, session = candidates[0]

    capture_date = captured_at.astimezone(IST).date()
    execution_date = date.fromisoformat(session.session_date)
    unresolved = [
        date.fromisoformat(value)
        for value in calendar.unresolved_special_dates
        if capture_date < date.fromisoformat(value) <= execution_date
    ]
    if unresolved:
        raise AlphaContractError(
            "H021 expectations execution path crosses unresolved NSE "
            f"special-session date(s): {[value.isoformat() for value in unresolved]}"
        )
    return session.session_date, opened.isoformat().replace("+00:00", "Z")


def _comparison_rows(
    comparison: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = comparison.get("revision_observations")
    if not isinstance(rows, list):
        raise AlphaContractError(
            "H021 comparison revision_observations must be a list"
        )
    return rows


def _validate_comparison(
    comparison: dict[str, Any],
    *,
    prior: dict[str, Any],
    current: dict[str, Any],
    revisions: list[RevisionObservation],
) -> list[str]:
    if comparison.get("outcomes_opened") is not False:
        raise AlphaContractError(
            "H021 comparison used by AE001 must have outcomes_opened=false"
        )
    if comparison.get("live_capital_allowed") is not False:
        raise AlphaContractError(
            "H021 comparison used by AE001 cannot allow live capital"
        )
    if comparison.get("hypothesis_id") != "H021":
        raise AlphaContractError("expectations adapter requires H021 comparison")
    if comparison.get("prior_capture_date_ist") != prior.get(
        "capture_date_ist"
    ):
        raise AlphaContractError("H021 comparison prior capture mismatch")
    if comparison.get("current_capture_date_ist") != current.get(
        "capture_date_ist"
    ):
        raise AlphaContractError("H021 comparison current capture mismatch")

    expected_rows = [asdict(row) for row in revisions]
    if _comparison_rows(comparison) != expected_rows:
        raise AlphaContractError(
            "H021 comparison rows do not reproduce frozen comparison logic"
        )
    selected = select_primary_top_decile(revisions)
    symbols = [row.symbol for row in selected]
    if comparison.get("primary_top_decile_symbols") != symbols:
        raise AlphaContractError(
            "H021 comparison top-decile symbols do not reproduce"
        )
    return symbols


def _universe_map(universe: dict[str, Any]) -> dict[str, dict[str, Any]]:
    members = universe.get("members")
    if not isinstance(members, list) or not members:
        raise AlphaContractError("H021 expectations universe members are required")
    mapping: dict[str, dict[str, Any]] = {}
    for row in members:
        if not isinstance(row, dict):
            raise AlphaContractError("H021 expectations universe row is invalid")
        symbol = str(row.get("symbol") or "").strip().upper()
        isin = str(row.get("isin") or "").strip()
        rank = row.get("rank")
        if (
            not symbol
            or not isin
            or not isinstance(rank, int)
            or isinstance(rank, bool)
            or rank <= 0
        ):
            raise AlphaContractError(
                "H021 expectations universe identity is invalid"
            )
        if symbol in mapping:
            raise AlphaContractError(
                f"H021 expectations duplicate universe symbol: {symbol}"
            )
        mapping[symbol] = row
    return mapping


def build_h021_expectations_panel(
    *,
    prior: dict[str, Any],
    current: dict[str, Any],
    prior_manifest: dict[str, Any],
    current_manifest: dict[str, Any],
    comparison: dict[str, Any],
    universe: dict[str, Any],
    calendar: CalendarSnapshot,
) -> dict[str, Any]:
    """Convert one sealed H021 comparison into a causal AE001 feature family."""

    _validate_capture_manifest_binding(
        prior,
        prior_manifest,
        label="prior",
    )
    _validate_capture_manifest_binding(
        current,
        current_manifest,
        label="current",
    )
    if prior.get("outcomes_opened") is not False:
        raise AlphaContractError("prior H021 capture has outcomes opened")
    if current.get("outcomes_opened") is not False:
        raise AlphaContractError("current H021 capture has outcomes opened")

    revisions = compare_snapshots(prior, current)
    primary_top_decile = _validate_comparison(
        comparison,
        prior=prior,
        current=current,
        revisions=revisions,
    )
    universe_by_symbol = _universe_map(universe)
    revision_symbols = {row.symbol for row in revisions}
    if revision_symbols != set(universe_by_symbol):
        raise AlphaContractError(
            "H021 comparison symbol set differs from frozen U001 universe"
        )

    captured_at = _timestamp(
        current.get("captured_at_utc"),
        "current.captured_at_utc",
    )
    current_date = date.fromisoformat(str(current["capture_date_ist"]))
    if captured_at.astimezone(IST).date() != current_date:
        raise AlphaContractError(
            "H021 current capture timestamp/date mismatch"
        )
    cutoff = datetime.combine(
        current_date,
        AE001_EOD_CUTOFF,
        tzinfo=IST,
    ).astimezone(UTC)
    same_day_eod_compatible = captured_at <= cutoff
    execution_session, execution_open = _next_execution_session(
        calendar,
        captured_at=captured_at,
    )

    definitions = [asdict(definition) for definition in H021_EXPECTATIONS_DEFINITIONS]
    for definition in H021_EXPECTATIONS_DEFINITIONS:
        definition.validate()
    feature_set_sha256 = digest(definitions)

    eligible_rank_input: dict[str, float | None] = {}
    for row in revisions:
        member = universe_by_symbol[row.symbol]
        key = f"{row.symbol}|{member['isin']}"
        eligible_rank_input[key] = (
            float(row.eps_revision_pct)
            if row.primary_signal_available
            and row.eps_revision_pct is not None
            else None
        )
    ranks = cross_sectional_percentile(eligible_rank_input)

    prior_rows = {
        str(row["symbol"]): row
        for row in prior["observations"]
    }
    current_rows = {
        str(row["symbol"]): row
        for row in current["observations"]
    }
    reason_counts: Counter[str] = Counter()
    rows = []

    for revision in sorted(revisions, key=lambda row: row.symbol):
        member = universe_by_symbol[revision.symbol]
        key = f"{revision.symbol}|{member['isin']}"
        reason_counts[revision.primary_signal_reason] += 1
        analyst_counts = (
            revision.analyst_count_prior,
            revision.analyst_count_current,
        )
        min_analyst_count = (
            float(min(analyst_counts))
            if all(isinstance(value, int) for value in analyst_counts)
            else None
        )
        primary_revision = (
            float(revision.eps_revision_pct)
            if revision.primary_signal_available
            and revision.eps_revision_pct is not None
            else None
        )
        rows.append(
            {
                "feature_session": current["capture_date_ist"],
                "symbol": revision.symbol,
                "isin": member["isin"],
                "universe_rank": member["rank"],
                "known_at_utc": captured_at.isoformat().replace("+00:00", "Z"),
                "primary_signal_reason": revision.primary_signal_reason,
                "prior_data_state": prior_rows[revision.symbol].get("data_state"),
                "current_data_state": current_rows[revision.symbol].get(
                    "data_state"
                ),
                "values": {
                    "h021_primary_eps_revision_30d_pct": primary_revision,
                    "h021_primary_eps_revision_rank_pct": ranks[key],
                    "h021_revenue_growth_change_pp": (
                        revision.revenue_growth_forecast_change_pp
                    ),
                    "h021_profit_growth_change_pp": (
                        revision.profit_growth_estimate_change_pp
                    ),
                    "h021_target_price_revision_pct": (
                        revision.target_price_revision_pct
                    ),
                    "h021_min_analyst_count": min_analyst_count,
                    "h021_primary_coverage_flag": (
                        1.0 if revision.primary_coverage else 0.0
                    ),
                    "h021_primary_signal_available_flag": (
                        1.0 if revision.primary_signal_available else 0.0
                    ),
                },
            }
        )

    prior_ref = _capture_manifest_ref(prior_manifest)
    current_ref = _capture_manifest_ref(current_manifest)
    panel: dict[str, Any] = {
        "schema_version": 1,
        "panel_id": PANEL_ID,
        "evidence_class": "PROSPECTIVE_SOURCE_ONLY_DERIVED_FEATURE",
        "source_hypothesis": "H021",
        "source_version": current["source_version"],
        "prior_capture": prior_ref,
        "current_capture": current_ref,
        "h021_comparison_sha256": digest(comparison),
        "universe_path": current["universe_path"],
        "universe_git_blob_sha": current["universe_git_blob_sha"],
        "universe_payload_sha256": str(universe.get("sha256") or ""),
        "calendar_version": calendar.version,
        "calendar_sha256": calendar.sha256,
        "capture_interval_days": revisions[0].capture_interval_days,
        "feature_known_at_utc": captured_at.isoformat().replace("+00:00", "Z"),
        "ae001_same_day_eod_1830_compatible": same_day_eod_compatible,
        "ae001_same_day_eod_cutoff_utc": cutoff.isoformat().replace(
            "+00:00",
            "Z",
        ),
        "earliest_execution_session": execution_session,
        "earliest_execution_open_utc": execution_open,
        "feature_definitions": definitions,
        "feature_set_sha256": feature_set_sha256,
        "row_count": len(rows),
        "primary_signal_available_count": sum(
            row.primary_signal_available for row in revisions
        ),
        "primary_signal_reason_counts": dict(sorted(reason_counts.items())),
        "primary_top_decile_symbols": primary_top_decile,
        "rows": rows,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel
