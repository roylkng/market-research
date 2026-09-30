from __future__ import annotations

import math
import re
from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, FeatureDefinition, digest
from marketlab.alpha_announcements import normalize_announcement_payload
from marketlab.alpha_market import DailyEquityObservation

T007_ID = "AE001-T007-v1"
SOURCE_START = date(2025, 9, 1)
SOURCE_END = date(2026, 9, 25)
IST = ZoneInfo("Asia/Kolkata")
DECISION_TIME = time(18, 30)
MARKET_CLOSE_TIME = time(15, 30)

TOPIC_PATTERNS = {
    "ORDER_CUSTOMER": re.compile(
        r"\b(?:order|orders|contract|contracts|bookings|customer win|"
        r"letter of (?:award|acceptance))\b",
        re.IGNORECASE,
    ),
    "CAPACITY_INVESTMENT": re.compile(
        r"\b(?:capex|capacity|commission\w*|manufacturing facility|"
        r"factory|invest\w*)\b",
        re.IGNORECASE,
    ),
    "RESULTS_GUIDANCE": re.compile(
        r"\b(?:earnings|quarter\w*|financial results|guidance|outlook|"
        r"revenue|profit)\b",
        re.IGNORECASE,
    ),
    "PRODUCT_APPROVAL": re.compile(
        r"\b(?:launch\w*|approval|approved|patent\w*|new product|"
        r"commercialisation)\b",
        re.IGNORECASE,
    ),
    "CAPITAL_TRANSACTION": re.compile(
        r"\b(?:merger|acqui\w*|divest\w*|disposal|buyback|share swap|"
        r"rights issue|allotment|fund\s*rais\w*)\b",
        re.IGNORECASE,
    ),
    "OWNERSHIP_CONTROL": re.compile(
        r"\b(?:stake sale|sell(?:ing)? (?:its |the )?(?:entire |remaining )?"
        r"stake|promoter stake|change of control|open offer)\b",
        re.IGNORECASE,
    ),
    "GOVERNANCE_RISK": re.compile(
        r"\b(?:fraud|default|resign\w*|auditor|investigation|insolvency|"
        r"litigation)\b",
        re.IGNORECASE,
    ),
    "POLICY_REGULATION": re.compile(
        r"\b(?:regulat\w*|circular|tariff\w*|government|tax|subsid\w*|"
        r"policy)\b",
        re.IGNORECASE,
    ),
}

_TOPIC_TO_FEATURE = {
    "ORDER_CUSTOMER": "ann_order_customer_current",
    "CAPACITY_INVESTMENT": "ann_capacity_investment_current",
    "RESULTS_GUIDANCE": "ann_results_guidance_current",
    "PRODUCT_APPROVAL": "ann_product_approval_current",
    "CAPITAL_TRANSACTION": "ann_capital_transaction_current",
    "OWNERSHIP_CONTROL": "ann_ownership_control_current",
    "GOVERNANCE_RISK": "ann_governance_risk_current",
    "POLICY_REGULATION": "ann_policy_regulation_current",
}

ANNOUNCEMENT_DEFINITIONS = [
    FeatureDefinition("ann_total_current", "announcement_events", "v1",
                      "Announcements mapped to current decision interval.", 1),
    FeatureDefinition("ann_material_current", "announcement_events", "v1",
                      "Current announcements matching at least one frozen topic.", 1),
    FeatureDefinition("ann_routine_current", "announcement_events", "v1",
                      "Current announcements matching no frozen topic.", 1),
    FeatureDefinition("ann_unique_topics_current", "announcement_events", "v1",
                      "Distinct frozen event topics in current interval.", 1),
    FeatureDefinition("ann_after_close_material_current", "announcement_events", "v1",
                      "Current material announcements disseminated after 15:30 IST.", 1),
    FeatureDefinition("ann_material_5", "announcement_events", "v1",
                      "Material announcement count over five decision sessions.", 5),
    FeatureDefinition("ann_material_20", "announcement_events", "v1",
                      "Material announcement count over twenty decision sessions.", 20),
    FeatureDefinition("ann_sessions_since_material_cap20", "announcement_events", "v1",
                      "Decision sessions since latest material event, capped at twenty.", 20),
]
for topic, feature in _TOPIC_TO_FEATURE.items():
    ANNOUNCEMENT_DEFINITIONS.append(
        FeatureDefinition(
            feature,
            "announcement_events",
            "v1",
            f"Current mapped announcements matching {topic}.",
            1,
        )
    )

ANNOUNCEMENT_TAXONOMY_SHA256 = digest(
    {
        topic: pattern.pattern
        for topic, pattern in sorted(TOPIC_PATTERNS.items())
    }
)
ANNOUNCEMENT_FEATURE_DEFINITION_SHA256 = digest(
    sorted(
        (asdict(definition) for definition in ANNOUNCEMENT_DEFINITIONS),
        key=lambda row: row["name"],
    )
)


def _calendar_days(start: date, end: date) -> list[date]:
    if start > end:
        raise AlphaContractError("announcement source window is reversed")
    return [
        date.fromordinal(start.toordinal() + offset)
        for offset in range((end - start).days + 1)
    ]


def classify_topics(row: dict[str, Any]) -> tuple[str, ...]:
    text = " ".join(
        str(row.get(field) or "").strip()
        for field in ("desc", "attchmntText")
    )
    return tuple(
        topic
        for topic, pattern in TOPIC_PATTERNS.items()
        if pattern.search(text)
    )


def build_announcement_source_panel(
    *,
    daily_payloads: dict[str, Any],
    daily_raw_sha256: dict[str, str],
) -> dict[str, Any]:
    expected = [day.isoformat() for day in _calendar_days(SOURCE_START, SOURCE_END)]
    if sorted(daily_payloads) != expected:
        raise AlphaContractError(
            "T007 announcement payload dates do not exactly cover frozen source window"
        )
    if sorted(daily_raw_sha256) != expected:
        raise AlphaContractError(
            "T007 announcement raw hashes do not exactly cover frozen source window"
        )

    sessions = []
    all_ids: set[str] = set()
    total = 0
    for day_text in expected:
        day = date.fromisoformat(day_text)
        rows = normalize_announcement_payload(
            daily_payloads[day_text],
            requested_start=day,
            requested_end=day,
        )
        normalized = []
        for row in rows:
            identity = str(row["announcement_id"])
            if identity in all_ids:
                raise AlphaContractError(
                    f"T007 announcement identity repeated across daily sources: {identity}"
                )
            all_ids.add(identity)
            topics = classify_topics(row)
            normalized.append(
                {
                    **row,
                    "topics": list(topics),
                    "material": bool(topics),
                }
            )
        sessions.append(
            {
                "calendar_date": day_text,
                "raw_sha256": daily_raw_sha256[day_text],
                "announcement_count": len(normalized),
                "announcements": normalized,
            }
        )
        total += len(normalized)

    panel: dict[str, Any] = {
        "schema_version": 1,
        "panel_id": "AE001-T007-HISTORICAL-ANNOUNCEMENTS-v1",
        "trial_id": T007_ID,
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "source_start": SOURCE_START.isoformat(),
        "source_end": SOURCE_END.isoformat(),
        "daily_source_count": len(sessions),
        "announcement_count": total,
        "sessions": sessions,
        "market_return_outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _verify_panel(panel: dict[str, Any], *, name: str) -> None:
    stored = str(panel.get("panel_sha256") or "")
    unsigned = dict(panel)
    unsigned.pop("panel_sha256", None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError(f"{name} panel hash mismatch")


def _cutoff(day_text: str) -> datetime:
    day = date.fromisoformat(day_text)
    return datetime.combine(day, DECISION_TIME, IST).astimezone(UTC)


def augment_feature_panel_with_announcements(
    *,
    feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    announcement_panel: dict[str, Any],
) -> dict[str, Any]:
    _verify_panel(feature_panel, name="T007 base feature")
    _verify_panel(market_panel, name="T007 market")
    _verify_panel(announcement_panel, name="T007 announcement")
    if feature_panel.get("outcomes_attached") is not False:
        raise AlphaContractError("T007 feature panel must be outcome-free")
    if announcement_panel.get("market_return_outcomes_attached") is not False:
        raise AlphaContractError("T007 announcement panel contains outcomes")
    expected_source_dates = [
        day.isoformat() for day in _calendar_days(SOURCE_START, SOURCE_END)
    ]
    observed_source_dates = [
        str(row.get("calendar_date") or "")
        for row in announcement_panel.get("sessions", [])
    ]
    if (
        announcement_panel.get("panel_id")
        != "AE001-T007-HISTORICAL-ANNOUNCEMENTS-v1"
        or announcement_panel.get("source_start") != SOURCE_START.isoformat()
        or announcement_panel.get("source_end") != SOURCE_END.isoformat()
        or announcement_panel.get("daily_source_count") != len(expected_source_dates)
        or observed_source_dates != expected_source_dates
    ):
        raise AlphaContractError(
            "T007 announcement source panel does not exactly cover frozen calendar window"
        )

    market_sessions = market_panel.get("sessions")
    if not isinstance(market_sessions, list) or not market_sessions:
        raise AlphaContractError("T007 market sessions are required")
    session_dates = [str(row["session_date"]) for row in market_sessions]
    if session_dates != sorted(session_dates):
        raise AlphaContractError("T007 market sessions must be chronological")
    cutoffs = [_cutoff(day) for day in session_dates]

    identity_by_session_symbol: list[dict[str, tuple[str, str]]] = []
    for session in market_sessions:
        mapping: dict[str, tuple[str, str]] = {}
        for raw in session.get("equities", []):
            row = (
                raw
                if isinstance(raw, DailyEquityObservation)
                else DailyEquityObservation(**raw)
            )
            if row.symbol in mapping:
                raise AlphaContractError(
                    f"{row.session_date}: duplicate T007 market symbol"
                )
            mapping[row.symbol] = (row.symbol, row.isin)
        identity_by_session_symbol.append(mapping)

    current_counts: dict[tuple[int, tuple[str, str]], Counter[str]] = defaultdict(Counter)
    material_counts: dict[tuple[str, str], list[int]] = defaultdict(
        lambda: [0] * len(session_dates)
    )
    excluded_no_identity = 0
    excluded_after_last_cutoff = 0
    mapped_event_count = 0

    for source_session in announcement_panel["sessions"]:
        for event in source_session["announcements"]:
            published = datetime.fromisoformat(
                str(event["exchange_published_at_utc"])
            ).astimezone(UTC)
            index = bisect_left(cutoffs, published)
            if index >= len(cutoffs):
                excluded_after_last_cutoff += 1
                continue
            symbol = str(event["symbol"]).upper()
            identity = identity_by_session_symbol[index].get(symbol)
            if identity is None:
                excluded_no_identity += 1
                continue
            topics = tuple(str(value) for value in event.get("topics", []))
            key = (index, identity)
            counts = current_counts[key]
            counts["total"] += 1
            if topics:
                counts["material"] += 1
                material_counts[identity][index] += 1
                local = published.astimezone(IST)
                if local.time() > MARKET_CLOSE_TIME:
                    counts["after_close_material"] += 1
                for topic in topics:
                    counts[f"topic:{topic}"] += 1
            else:
                counts["routine"] += 1
            mapped_event_count += 1

    prefixes: dict[tuple[str, str], list[int]] = {}
    last_material: dict[tuple[str, str], list[int | None]] = {}
    for identity, values in material_counts.items():
        running = [0]
        latest: int | None = None
        latest_by_session: list[int | None] = []
        for index, value in enumerate(values):
            running.append(running[-1] + value)
            if value > 0:
                latest = index
            latest_by_session.append(latest)
        prefixes[identity] = running
        last_material[identity] = latest_by_session

    base_definitions = feature_panel.get("feature_definitions")
    if not isinstance(base_definitions, list):
        raise AlphaContractError("T007 base feature definitions are missing")
    definitions = list(base_definitions) + [
        asdict(definition) for definition in ANNOUNCEMENT_DEFINITIONS
    ]
    names = [str(row["name"]) for row in definitions]
    if len(names) != len(set(names)):
        raise AlphaContractError("T007 feature names collide with base features")
    definitions.sort(key=lambda row: row["name"])
    feature_set_sha256 = digest(definitions)
    index_by_date = {day: index for index, day in enumerate(session_dates)}

    rows = []
    per_session: dict[str, int] = defaultdict(int)
    for base in feature_panel.get("rows", []):
        day = str(base["feature_session"])
        index = index_by_date.get(day)
        if index is None:
            raise AlphaContractError(
                f"T007 base feature session absent from market panel: {day}"
            )
        identity = (str(base["symbol"]), str(base["isin"]))
        counts = current_counts.get((index, identity), Counter())
        topics_present = {
            topic
            for topic in TOPIC_PATTERNS
            if counts.get(f"topic:{topic}", 0) > 0
        }
        prefix = prefixes.get(identity)
        if prefix is None:
            material_5 = 0
            material_20 = 0
            since = 20
        else:
            material_5 = prefix[index + 1] - prefix[max(0, index - 4)]
            material_20 = prefix[index + 1] - prefix[max(0, index - 19)]
            latest = last_material[identity][index]
            since = 20 if latest is None else min(20, index - latest)

        new_values: dict[str, float] = {
            "ann_total_current": float(counts.get("total", 0)),
            "ann_material_current": float(counts.get("material", 0)),
            "ann_routine_current": float(counts.get("routine", 0)),
            "ann_unique_topics_current": float(len(topics_present)),
            "ann_after_close_material_current": float(
                counts.get("after_close_material", 0)
            ),
            "ann_material_5": float(material_5),
            "ann_material_20": float(material_20),
            "ann_sessions_since_material_cap20": float(since),
        }
        for topic, feature in _TOPIC_TO_FEATURE.items():
            new_values[feature] = float(counts.get(f"topic:{topic}", 0))

        updated = {
            **base,
            "feature_set_sha256": feature_set_sha256,
            "values": {**base["values"], **new_values},
        }
        rows.append(updated)
        per_session[day] += 1

    panel: dict[str, Any] = {
        **{
            key: value
            for key, value in feature_panel.items()
            if key not in {
                "panel_sha256",
                "feature_definitions",
                "feature_set_sha256",
                "rows",
                "sessions",
                "feature_row_count",
                "session_count",
            }
        },
        "panel_id": "AE001-T007-CORE43-v1",
        "base_feature_panel_sha256": feature_panel["panel_sha256"],
        "announcement_panel_sha256": announcement_panel["panel_sha256"],
        "feature_definitions": definitions,
        "feature_set_sha256": feature_set_sha256,
        "announcement_feature_count": len(ANNOUNCEMENT_DEFINITIONS),
        "announcement_mapped_event_count": mapped_event_count,
        "announcement_excluded_no_same_session_eq_identity": excluded_no_identity,
        "announcement_excluded_after_last_decision_cutoff": (
            excluded_after_last_cutoff
        ),
        "session_count": len(per_session),
        "feature_row_count": len(rows),
        "sessions": [
            {"session_date": day, "eligible_count": count}
            for day, count in sorted(per_session.items())
        ],
        "rows": rows,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel
