from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_announcements import normalize_announcement_payload
from marketlab.ss002_special_situations import (
    approved_attachment_url,
    classify_special_situation,
)

CENSUS_ID = "HG006-D001-v1"
SOURCE_START = date(2023, 1, 1)
INITIATION_END = date(2025, 12, 31)
SOURCE_END = date(2026, 9, 30)

DISCRETE_FAMILIES = frozenset(
    {
        "BUYBACK",
        "OPEN_OFFER_CONTROL",
        "DELISTING",
        "SCHEME_REORGANISATION",
        "RIGHTS_ISSUE",
        "PREFERENTIAL_WARRANT",
        "CAPITAL_REDUCTION",
        "OFFER_FOR_SALE",
        "TENDER_OFFER",
    }
)


def _expected_days(start: date, end: date) -> list[str]:
    if start > end:
        raise AlphaContractError("HG006 D001 source window is reversed")
    return [
        date.fromordinal(start.toordinal() + offset).isoformat()
        for offset in range((end - start).days + 1)
    ]


def _published_day(row: dict[str, Any]) -> date:
    raw = str(row.get("exchange_published_at_utc") or "")
    try:
        value = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise AlphaContractError(
            f"HG006 D001 invalid canonical announcement timestamp: {raw}"
        ) from exc
    if value.tzinfo is None:
        raise AlphaContractError("HG006 D001 announcement timestamp lacks timezone")
    return value.astimezone(UTC).date()


def build_historical_event_census(
    *,
    daily_payloads: dict[str, object],
    daily_raw_sha256: dict[str, str],
    generated_at_utc: str,
    source_start: date = SOURCE_START,
    initiation_end: date = INITIATION_END,
    source_end: date = SOURCE_END,
) -> dict[str, Any]:
    if not source_start <= initiation_end < source_end:
        raise AlphaContractError("HG006 D001 frozen date ordering is invalid")

    expected_days = _expected_days(source_start, source_end)
    if sorted(daily_payloads) != expected_days:
        raise AlphaContractError("HG006 D001 daily payload coverage is incomplete")
    if sorted(daily_raw_sha256) != expected_days:
        raise AlphaContractError("HG006 D001 daily raw hash coverage is incomplete")

    generated = datetime.fromisoformat(generated_at_utc)
    if generated.tzinfo is None:
        raise AlphaContractError("HG006 D001 generated_at_utc must include timezone")

    all_announcement_ids: set[str] = set()
    source_row_count = 0
    retained_events: list[dict[str, Any]] = []
    category_event_counts: Counter[str] = Counter()
    daily_source_counts: dict[str, int] = {}
    daily_retained_counts: dict[str, int] = {}

    chronology_events: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for day_text in expected_days:
        day = date.fromisoformat(day_text)
        rows = normalize_announcement_payload(
            daily_payloads[day_text],
            requested_start=day,
            requested_end=day,
        )
        daily_source_counts[day_text] = len(rows)
        source_row_count += len(rows)
        retained_for_day = 0

        for row in rows:
            announcement_id = str(row["announcement_id"])
            if announcement_id in all_announcement_ids:
                raise AlphaContractError(
                    f"HG006 D001 duplicate canonical announcement: {announcement_id}"
                )
            all_announcement_ids.add(announcement_id)

            categories = [
                category
                for category in classify_special_situation(row)
                if category in DISCRETE_FAMILIES
            ]
            if not categories:
                continue

            published_day = _published_day(row)
            if published_day != day:
                raise AlphaContractError(
                    f"HG006 D001 canonical day mismatch: {announcement_id}"
                )
            symbol = str(row.get("symbol") or "").strip().upper()
            if not symbol:
                raise AlphaContractError("HG006 D001 retained event lacks symbol")

            attachment = approved_attachment_url(row.get("attchmntFile"))
            event = {
                **row,
                "historical_discrete_families": sorted(categories),
                "source_day": day_text,
                "source_raw_sha256": daily_raw_sha256[day_text],
                "approved_attachment_url": attachment,
                "in_initiation_window": published_day <= initiation_end,
                "return_outcomes_opened": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
            retained_events.append(event)
            retained_for_day += 1
            for category in categories:
                category_event_counts[category] += 1
                chronology_events[(symbol, category)].append(event)

        daily_retained_counts[day_text] = retained_for_day

    chronologies: list[dict[str, Any]] = []
    historical_counts: Counter[str] = Counter()
    historical_attachment_ready = 0

    for (symbol, family), events in sorted(chronology_events.items()):
        ordered = sorted(
            events,
            key=lambda row: (
                str(row["exchange_published_at_utc"]),
                str(row["announcement_id"]),
            ),
        )
        initiation_rows = [
            row for row in ordered if bool(row["in_initiation_window"])
        ]
        if not initiation_rows:
            continue

        historical_counts[family] += 1
        has_attachment = any(
            row.get("approved_attachment_url") is not None for row in ordered
        )
        if has_attachment:
            historical_attachment_ready += 1

        chronologies.append(
            {
                "chronology_id": digest(
                    {
                        "symbol": symbol,
                        "family": family,
                        "source_start": source_start.isoformat(),
                        "initiation_end": initiation_end.isoformat(),
                        "source_end": source_end.isoformat(),
                    }
                ),
                "symbol": symbol,
                "family": family,
                "first_observed_at_utc": ordered[0]["exchange_published_at_utc"],
                "last_observed_at_utc": ordered[-1]["exchange_published_at_utc"],
                "first_initiation_window_at_utc": initiation_rows[0][
                    "exchange_published_at_utc"
                ],
                "event_count": len(ordered),
                "initiation_window_event_count": len(initiation_rows),
                "followup_event_count": len(ordered) - len(initiation_rows),
                "has_approved_attachment": has_attachment,
                "announcement_ids": [
                    str(row["announcement_id"]) for row in ordered
                ],
                "right_censored_at": source_end.isoformat(),
                "terminal_state_assigned": False,
                "return_outcomes_opened": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    chronology_count = len(chronologies)
    attachment_ratio = (
        historical_attachment_ready / chronology_count
        if chronology_count
        else 0.0
    )
    threshold_passes = {
        "complete_daily_source_coverage": True,
        "canonical_identity_unique_across_days": (
            len(all_announcement_ids) == source_row_count
        ),
        "retained_rows_use_frozen_discrete_families": all(
            set(row["historical_discrete_families"]).issubset(DISCRETE_FAMILIES)
            for row in retained_events
        ),
        "minimum_scheme_chronologies_30": (
            historical_counts["SCHEME_REORGANISATION"] >= 30
        ),
        "minimum_preferential_chronologies_30": (
            historical_counts["PREFERENTIAL_WARRANT"] >= 30
        ),
        "minimum_total_historical_chronologies_150": chronology_count >= 150,
        "minimum_chronology_attachment_coverage_90pct": attachment_ratio >= 0.90,
    }

    output = {
        "schema_version": 1,
        "census_id": CENSUS_ID,
        "classification": "HISTORICAL_DISCRETE_EVENT_BASE_RATE_SOURCE_CENSUS_NOT_PROBABILITY",
        "generated_at_utc": generated.astimezone(UTC).isoformat().replace(
            "+00:00", "Z"
        ),
        "source_window": {
            "start": source_start.isoformat(),
            "end": source_end.isoformat(),
            "calendar_day_count": len(expected_days),
        },
        "initiation_window": {
            "start": source_start.isoformat(),
            "end": initiation_end.isoformat(),
        },
        "right_censoring_cutoff": source_end.isoformat(),
        "frozen_families": sorted(DISCRETE_FAMILIES),
        "source_row_count": source_row_count,
        "retained_event_count": len(retained_events),
        "retained_symbol_count": len(
            {str(row["symbol"]) for row in retained_events}
        ),
        "category_event_counts": dict(sorted(category_event_counts.items())),
        "historical_chronology_count": chronology_count,
        "historical_chronology_counts_by_family": dict(
            sorted(historical_counts.items())
        ),
        "historical_attachment_ready_chronology_count": historical_attachment_ready,
        "historical_attachment_ready_chronology_ratio": attachment_ratio,
        "daily_source_row_counts": daily_source_counts,
        "daily_retained_event_counts": daily_retained_counts,
        "daily_raw_sha256": dict(sorted(daily_raw_sha256.items())),
        "events": sorted(
            retained_events,
            key=lambda row: (
                str(row["exchange_published_at_utc"]),
                str(row["symbol"]),
                str(row["announcement_id"]),
            ),
        ),
        "chronologies": chronologies,
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_historical_stage_extraction": all(
            threshold_passes.values()
        ),
        "completion_probabilities_assigned": False,
        "expected_returns_calculated": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["census_sha256"] = digest(output)
    return output
