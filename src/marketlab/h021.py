from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

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
    analyst_count_prior: int | None
    analyst_count_current: int | None
    eps_revision_pct: float | None
    revenue_growth_forecast_change_pp: float | None
    profit_growth_estimate_change_pp: float | None
    target_price_revision_pct: float | None
    primary_signal_available: bool


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

    seen: set[tuple[str, str]] = set()
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

        key = (str(symbol), str(fiscal_period))
        if key in seen:
            errors.append(f"duplicate observation key: {key}")
        seen.add(key)

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


def compare_snapshots(prior: dict, current: dict) -> list[RevisionObservation]:
    prior_errors = validate_snapshot(prior)
    current_errors = validate_snapshot(current)
    if prior_errors or current_errors:
        raise ValueError({"prior_errors": prior_errors, "current_errors": current_errors})

    prior_date = prior["capture_date_ist"]
    current_date = current["capture_date_ist"]
    if date.fromisoformat(current_date) <= date.fromisoformat(prior_date):
        raise ValueError("current capture date must be later than prior capture date")

    prior_map = {
        (row["symbol"], row["fiscal_period"]): row for row in prior["observations"]
    }
    current_map = {
        (row["symbol"], row["fiscal_period"]): row for row in current["observations"]
    }

    results: list[RevisionObservation] = []
    for key in sorted(prior_map.keys() & current_map.keys()):
        before = prior_map[key]
        after = current_map[key]
        eps_revision = _pct_revision(after.get("consensus_eps"), before.get("consensus_eps"))
        results.append(
            RevisionObservation(
                symbol=key[0],
                fiscal_period=key[1],
                prior_capture_date=prior_date,
                current_capture_date=current_date,
                analyst_count_prior=before.get("analyst_count"),
                analyst_count_current=after.get("analyst_count"),
                eps_revision_pct=eps_revision,
                revenue_growth_forecast_change_pp=_pp_change(
                    after.get("revenue_growth_forecast_pct"),
                    before.get("revenue_growth_forecast_pct"),
                ),
                profit_growth_estimate_change_pp=_pp_change(
                    after.get("profit_growth_estimate_pct"),
                    before.get("profit_growth_estimate_pct"),
                ),
                target_price_revision_pct=_pct_revision(
                    after.get("target_price_inr"), before.get("target_price_inr")
                ),
                primary_signal_available=eps_revision is not None,
            )
        )
    return results
