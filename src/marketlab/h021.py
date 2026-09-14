from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from math import ceil
from urllib.parse import urlsplit

MIN_REVISION_INTERVAL_DAYS = 28
MAX_REVISION_INTERVAL_DAYS = 35
TARGET_REVISION_INTERVAL_DAYS = 30
PRIMARY_MIN_ANALYST_COUNT = 5
PRIMARY_DECILE_FRACTION = 0.10

REQUIRED_OBSERVATION_FIELDS = {
    "symbol",
    "fiscal_period",
    "consensus_eps",
    "revenue_growth_forecast_pct",
    "profit_growth_estimate_pct",
    "analyst_count",
    "target_price_inr",
    "source_url",
    "source_status",
}


@dataclass(frozen=True)
class RevisionObservation:
    symbol: str
    fiscal_period: str
    prior_capture_date: str
    current_capture_date: str
    capture_interval_days: int
    analyst_count_prior: int | None
    analyst_count_current: int | None
    eps_revision_pct: float | None
    revenue_growth_forecast_change_pp: float | None
    profit_growth_estimate_change_pp: float | None
    target_price_revision_pct: float | None
    source_compatible: bool
    primary_coverage: bool
    primary_signal_available: bool
    primary_signal_reason: str


def _number_or_none(value: object) -> bool:
    return value is None or (
        isinstance(value, (int, float)) and not isinstance(value, bool)
    )


def _parse_iso_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_snapshot(snapshot: dict) -> list[str]:
    errors: list[str] = []
    if snapshot.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if snapshot.get("hypothesis_id") != "H021":
        errors.append("hypothesis_id must equal H021")
    if snapshot.get("outcomes_opened") is not False:
        errors.append("outcomes_opened must be false for prospective capture")
    if snapshot.get("live_capital_allowed") is not False:
        errors.append("live_capital_allowed must be false")

    capture_date_raw = snapshot.get("capture_date_ist")
    try:
        capture_date = date.fromisoformat(capture_date_raw)
    except (TypeError, ValueError):
        errors.append("capture_date_ist must be ISO YYYY-MM-DD")
        capture_date = None

    captured_at = _parse_iso_timestamp(snapshot.get("captured_at_utc"))
    if captured_at is None:
        errors.append("captured_at_utc must be an offset-aware ISO timestamp")

    for optional_identity_field in (
        "source_version",
        "universe_path",
        "universe_git_blob_sha",
    ):
        if optional_identity_field in snapshot and not _nonempty_string(
            snapshot.get(optional_identity_field)
        ):
            errors.append(f"{optional_identity_field} must be a non-empty string")

    seen_keys: set[tuple[str, str]] = set()
    seen_symbols: set[str] = set()
    observations = snapshot.get("observations")
    if not isinstance(observations, list) or not observations:
        return errors + ["observations must be a non-empty list"]

    for index, row in enumerate(observations):
        if not isinstance(row, dict):
            errors.append(f"observation[{index}] must be an object")
            continue

        missing = REQUIRED_OBSERVATION_FIELDS - row.keys()
        if missing:
            errors.append(f"observation[{index}] missing fields: {sorted(missing)}")

        symbol = row.get("symbol")
        fiscal_period = row.get("fiscal_period")
        if not isinstance(symbol, str) or not symbol.strip():
            errors.append(f"observation[{index}] invalid symbol")
        if not isinstance(fiscal_period, str) or not fiscal_period.strip():
            errors.append(f"observation[{index}] invalid fiscal_period")

        normalized_symbol = str(symbol)
        key = (normalized_symbol, str(fiscal_period))
        if key in seen_keys:
            errors.append(f"duplicate observation key: {key}")
        seen_keys.add(key)
        if normalized_symbol in seen_symbols:
            errors.append(f"duplicate observation symbol: {normalized_symbol}")
        seen_symbols.add(normalized_symbol)

        numeric_fields = (
            "consensus_eps",
            "revenue_growth_forecast_pct",
            "profit_growth_estimate_pct",
            "target_price_inr",
        )
        for field in numeric_fields:
            if not _number_or_none(row.get(field)):
                errors.append(f"observation[{index}] {field} must be numeric or null")

        analyst_count = row.get("analyst_count")
        if analyst_count is not None and (
            not isinstance(analyst_count, int)
            or isinstance(analyst_count, bool)
            or analyst_count < 0
        ):
            errors.append(
                f"observation[{index}] analyst_count must be non-negative integer or null"
            )

        source_url = row.get("source_url")
        if not isinstance(source_url, str) or not source_url.startswith("https://"):
            errors.append(f"observation[{index}] source_url must be https URL")

        source_status = row.get("source_status")
        if not _nonempty_string(source_status):
            errors.append(f"observation[{index}] source_status must be non-empty string")

        source_date_raw = row.get("source_observed_market_date")
        if source_date_raw is not None:
            try:
                source_date = date.fromisoformat(source_date_raw)
            except (TypeError, ValueError):
                errors.append(f"observation[{index}] source_observed_market_date invalid")
            else:
                if capture_date is not None and source_date > capture_date:
                    errors.append(f"observation[{index}] source date is after capture date")

    return errors


def _pct_revision(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None or prior == 0:
        return None
    return (current / prior - 1.0) * 100.0


def _pp_change(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None:
        return None
    return current - prior


def _source_host(row: dict) -> str | None:
    source_url = row.get("source_url")
    if not isinstance(source_url, str):
        return None
    return urlsplit(source_url).hostname


def _primary_coverage(row: dict) -> bool:
    analyst_count = row.get("analyst_count")
    return isinstance(analyst_count, int) and analyst_count >= PRIMARY_MIN_ANALYST_COUNT


def _comparison_identity(snapshot: dict, field: str) -> str:
    value = snapshot.get(field)
    if not _nonempty_string(value):
        raise ValueError(f"{field} is required for H021 primary comparison")
    return value


def _validate_comparison_contract(prior: dict, current: dict) -> int:
    prior_date = date.fromisoformat(prior["capture_date_ist"])
    current_date = date.fromisoformat(current["capture_date_ist"])
    interval_days = (current_date - prior_date).days
    if interval_days <= 0:
        raise ValueError("current capture date must be later than prior capture date")
    if not MIN_REVISION_INTERVAL_DAYS <= interval_days <= MAX_REVISION_INTERVAL_DAYS:
        raise ValueError(
            "H021 primary comparison requires capture interval between "
            f"{MIN_REVISION_INTERVAL_DAYS} and {MAX_REVISION_INTERVAL_DAYS} days"
        )

    for field in ("source_version", "universe_path", "universe_git_blob_sha"):
        prior_value = _comparison_identity(prior, field)
        current_value = _comparison_identity(current, field)
        if prior_value != current_value:
            raise ValueError(f"H021 comparison requires matching {field}")

    prior_symbols = {row["symbol"] for row in prior["observations"]}
    current_symbols = {row["symbol"] for row in current["observations"]}
    if prior_symbols != current_symbols:
        missing = sorted(prior_symbols - current_symbols)
        added = sorted(current_symbols - prior_symbols)
        raise ValueError(
            "H021 comparison requires identical frozen symbol sets; "
            f"missing={missing} added={added}"
        )

    return interval_days


def _primary_signal_reason(
    *,
    same_period: bool,
    source_compatible: bool,
    eps_revision_pct: float | None,
    primary_coverage: bool,
) -> str:
    if not same_period:
        return "FISCAL_PERIOD_MISMATCH"
    if not source_compatible:
        return "EPS_SOURCE_CHANGED"
    if eps_revision_pct is None:
        return "EPS_REVISION_UNAVAILABLE"
    if not primary_coverage:
        return "ANALYST_COVERAGE_LT_5"
    return "ELIGIBLE"


def compare_snapshots(prior: dict, current: dict) -> list[RevisionObservation]:
    prior_errors = validate_snapshot(prior)
    current_errors = validate_snapshot(current)
    if prior_errors or current_errors:
        raise ValueError({"prior_errors": prior_errors, "current_errors": current_errors})

    interval_days = _validate_comparison_contract(prior, current)
    prior_date = prior["capture_date_ist"]
    current_date = current["capture_date_ist"]

    prior_map = {row["symbol"]: row for row in prior["observations"]}
    current_map = {row["symbol"]: row for row in current["observations"]}

    results: list[RevisionObservation] = []
    for symbol in sorted(current_map):
        before = prior_map[symbol]
        after = current_map[symbol]
        same_period = before["fiscal_period"] == after["fiscal_period"]
        source_compatible = _source_host(before) == _source_host(after)
        primary_coverage = _primary_coverage(before) and _primary_coverage(after)

        eps_revision = (
            _pct_revision(after.get("consensus_eps"), before.get("consensus_eps"))
            if same_period
            else None
        )
        revenue_change = (
            _pp_change(
                after.get("revenue_growth_forecast_pct"),
                before.get("revenue_growth_forecast_pct"),
            )
            if same_period
            else None
        )
        profit_change = (
            _pp_change(
                after.get("profit_growth_estimate_pct"),
                before.get("profit_growth_estimate_pct"),
            )
            if same_period
            else None
        )
        target_revision = (
            _pct_revision(after.get("target_price_inr"), before.get("target_price_inr"))
            if same_period
            else None
        )
        reason = _primary_signal_reason(
            same_period=same_period,
            source_compatible=source_compatible,
            eps_revision_pct=eps_revision,
            primary_coverage=primary_coverage,
        )
        results.append(
            RevisionObservation(
                symbol=symbol,
                fiscal_period=after["fiscal_period"],
                prior_capture_date=prior_date,
                current_capture_date=current_date,
                capture_interval_days=interval_days,
                analyst_count_prior=before.get("analyst_count"),
                analyst_count_current=after.get("analyst_count"),
                eps_revision_pct=eps_revision,
                revenue_growth_forecast_change_pp=revenue_change,
                profit_growth_estimate_change_pp=profit_change,
                target_price_revision_pct=target_revision,
                source_compatible=source_compatible,
                primary_coverage=primary_coverage,
                primary_signal_available=reason == "ELIGIBLE",
                primary_signal_reason=reason,
            )
        )
    return results


def select_primary_top_decile(
    revisions: list[RevisionObservation],
) -> list[RevisionObservation]:
    eligible = [
        row
        for row in revisions
        if row.primary_signal_available and row.eps_revision_pct is not None
    ]
    if not eligible:
        return []

    ranked = sorted(
        eligible,
        key=lambda row: (-float(row.eps_revision_pct), row.symbol),
    )
    minimum_count = max(1, ceil(len(ranked) * PRIMARY_DECILE_FRACTION))
    cutoff = ranked[minimum_count - 1].eps_revision_pct
    return [row for row in ranked if row.eps_revision_pct >= cutoff]


def select_prior_snapshot(current: dict, candidates: list[dict]) -> dict:
    current_errors = validate_snapshot(current)
    if current_errors:
        raise ValueError({"current_errors": current_errors})

    current_date = date.fromisoformat(current["capture_date_ist"])
    source_version = _comparison_identity(current, "source_version")
    universe_path = _comparison_identity(current, "universe_path")
    universe_sha = _comparison_identity(current, "universe_git_blob_sha")

    eligible: list[tuple[int, date, dict]] = []
    for candidate in candidates:
        if validate_snapshot(candidate):
            continue
        candidate_date = date.fromisoformat(candidate["capture_date_ist"])
        interval_days = (current_date - candidate_date).days
        if not MIN_REVISION_INTERVAL_DAYS <= interval_days <= MAX_REVISION_INTERVAL_DAYS:
            continue
        if candidate.get("source_version") != source_version:
            continue
        if candidate.get("universe_path") != universe_path:
            continue
        if candidate.get("universe_git_blob_sha") != universe_sha:
            continue
        candidate_symbols = {row["symbol"] for row in candidate["observations"]}
        current_symbols = {row["symbol"] for row in current["observations"]}
        if candidate_symbols != current_symbols:
            continue
        eligible.append((interval_days, candidate_date, candidate))

    if not eligible:
        raise ValueError("no compatible H021 prior capture exists in the 28-35 day window")

    eligible.sort(
        key=lambda item: (
            abs(item[0] - TARGET_REVISION_INTERVAL_DAYS),
            item[1],
        )
    )
    return eligible[0][2]
