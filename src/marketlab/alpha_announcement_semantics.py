from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from bisect import bisect_left
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, FeatureDefinition, digest
from marketlab.alpha_announcement_features import SOURCE_END, SOURCE_START
from marketlab.alpha_market import DailyEquityObservation

T012_ID = "AE001-T012-v1"
HASH_DIMENSIONS = 64
IST = ZoneInfo("Asia/Kolkata")
MARKET_CLOSE_TIME = time(15, 30)
DECISION_TIME = time(18, 30)
TOKEN_RE = re.compile(r"[a-z0-9]+")
EXPECTED_ANNOUNCEMENT_PANEL_SHA256 = (
    "fc3be48ce09905b8d2ebef1ad0e75a7ed22815202abbd7d7b328fe6dfcd3957d"
)

SEMANTIC_DEFINITIONS = [
    FeatureDefinition(
        name=f"annsem_hash_{index:02d}",
        family="announcement_events",
        version="v1",
        description=(
            "Signed SHA256 hashed post-close announcement text semantic "
            f"dimension {index:02d}."
        ),
        lookback_sessions=1,
    )
    for index in range(HASH_DIMENSIONS)
]
SEMANTIC_DEFINITION_SHA256 = digest(
    sorted(
        (asdict(definition) for definition in SEMANTIC_DEFINITIONS),
        key=lambda row: row["name"],
    )
)


def normalize_text(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", str(text or "")).lower()
    return TOKEN_RE.findall(normalized)


def announcement_ngrams(*, desc: str, attachment_text: str) -> tuple[str, ...]:
    tokens = normalize_text(f"{desc or ''} {attachment_text or ''}")
    terms = {f"u:{token}" for token in tokens}
    terms.update(
        f"b:{left}_{right}"
        for left, right in zip(tokens, tokens[1:], strict=False)
    )
    return tuple(sorted(terms))


def hashed_semantic_vector(
    *,
    desc: str,
    attachment_text: str,
) -> tuple[float, ...]:
    values = [0.0] * HASH_DIMENSIONS
    for term in announcement_ngrams(
        desc=desc,
        attachment_text=attachment_text,
    ):
        raw = hashlib.sha256(term.encode("utf-8")).digest()
        bucket = int.from_bytes(raw[:8], "big") % HASH_DIMENSIONS
        sign = 1.0 if (raw[8] & 1) == 0 else -1.0
        values[bucket] += sign

    norm = math.sqrt(sum(value * value for value in values))
    if norm > 0.0:
        values = [value / norm for value in values]
    return tuple(values)


def _verify_panel(
    panel: dict[str, Any],
    *,
    name: str,
    expected_sha256: str | None = None,
) -> None:
    stored = str(panel.get("panel_sha256") or "")
    unsigned = dict(panel)
    unsigned.pop("panel_sha256", None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError(f"{name} panel hash mismatch")
    if expected_sha256 is not None and stored != expected_sha256:
        raise AlphaContractError(
            f"{name} differs from frozen source SHA-256"
        )


def _calendar_days(start: date, end: date) -> list[str]:
    return [
        date.fromordinal(start.toordinal() + offset).isoformat()
        for offset in range((end - start).days + 1)
    ]


def _cutoff(day_text: str) -> datetime:
    day = date.fromisoformat(day_text)
    return datetime.combine(day, DECISION_TIME, IST).astimezone(UTC)


def augment_feature_panel_with_hashed_semantics(
    *,
    feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    announcement_panel: dict[str, Any],
) -> dict[str, Any]:
    """Add frozen T012 hashed post-close semantic features to CORE27 rows."""

    _verify_panel(feature_panel, name="T012 base feature")
    _verify_panel(market_panel, name="T012 market")
    _verify_panel(
        announcement_panel,
        name="T012 announcement",
        expected_sha256=EXPECTED_ANNOUNCEMENT_PANEL_SHA256,
    )
    if feature_panel.get("outcomes_attached") is not False:
        raise AlphaContractError("T012 base feature panel contains outcomes")
    if announcement_panel.get("market_return_outcomes_attached") is not False:
        raise AlphaContractError("T012 announcement panel contains outcomes")
    if announcement_panel.get("panel_id") != (
        "AE001-T007-HISTORICAL-ANNOUNCEMENTS-v1"
    ):
        raise AlphaContractError("T012 announcement source identity changed")

    expected_dates = _calendar_days(SOURCE_START, SOURCE_END)
    observed_dates = [
        str(row.get("calendar_date") or "")
        for row in announcement_panel.get("sessions", [])
    ]
    if observed_dates != expected_dates:
        raise AlphaContractError(
            "T012 announcement source does not cover frozen daily window"
        )

    market_sessions = market_panel.get("sessions")
    if not isinstance(market_sessions, list) or not market_sessions:
        raise AlphaContractError("T012 market sessions are required")
    session_dates = [str(row["session_date"]) for row in market_sessions]
    if session_dates != sorted(session_dates):
        raise AlphaContractError("T012 market sessions must be chronological")
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
                    f"{row.session_date}: duplicate T012 market symbol"
                )
            mapping[row.symbol] = (row.symbol, row.isin)
        identity_by_session_symbol.append(mapping)

    vectors: dict[
        tuple[int, tuple[str, str]],
        list[float],
    ] = defaultdict(lambda: [0.0] * HASH_DIMENSIONS)
    eligible_events = 0
    zero_token_events = 0
    excluded_preclose = 0
    excluded_non_same_trading_day = 0
    excluded_no_identity = 0
    excluded_after_last_cutoff = 0

    for source_session in announcement_panel["sessions"]:
        for event in source_session["announcements"]:
            published = datetime.fromisoformat(
                str(event["exchange_published_at_utc"])
            ).astimezone(UTC)
            index = bisect_left(cutoffs, published)
            if index >= len(cutoffs):
                excluded_after_last_cutoff += 1
                continue

            local = published.astimezone(IST)
            decision_day = session_dates[index]
            if local.date().isoformat() != decision_day:
                excluded_non_same_trading_day += 1
                continue
            if not (
                local.time() > MARKET_CLOSE_TIME
                and local.time() <= DECISION_TIME
            ):
                excluded_preclose += 1
                continue

            symbol = str(event["symbol"]).upper()
            identity = identity_by_session_symbol[index].get(symbol)
            if identity is None:
                excluded_no_identity += 1
                continue

            vector = hashed_semantic_vector(
                desc=str(event.get("desc") or ""),
                attachment_text=str(event.get("attchmntText") or ""),
            )
            if not any(value != 0.0 for value in vector):
                zero_token_events += 1
            target = vectors[(index, identity)]
            for bucket, value in enumerate(vector):
                target[bucket] += value
            eligible_events += 1

    base_definitions = feature_panel.get("feature_definitions")
    if not isinstance(base_definitions, list):
        raise AlphaContractError("T012 base feature definitions are missing")
    definitions = list(base_definitions) + [
        asdict(definition) for definition in SEMANTIC_DEFINITIONS
    ]
    names = [str(row["name"]) for row in definitions]
    if len(names) != len(set(names)):
        raise AlphaContractError("T012 semantic features collide with base")
    definitions.sort(key=lambda row: row["name"])
    feature_set_sha256 = digest(definitions)

    index_by_date = {
        session_date: index
        for index, session_date in enumerate(session_dates)
    }
    rows = []
    per_session: dict[str, int] = defaultdict(int)
    semantic_nonzero_rows = 0
    for base in feature_panel.get("rows", []):
        day = str(base["feature_session"])
        index = index_by_date.get(day)
        if index is None:
            raise AlphaContractError(
                f"T012 base feature session absent from market panel: {day}"
            )
        identity = (str(base["symbol"]), str(base["isin"]))
        vector = vectors.get(
            (index, identity),
            [0.0] * HASH_DIMENSIONS,
        )
        if any(value != 0.0 for value in vector):
            semantic_nonzero_rows += 1
        semantic_values = {
            f"annsem_hash_{bucket:02d}": float(vector[bucket])
            for bucket in range(HASH_DIMENSIONS)
        }
        rows.append(
            {
                **base,
                "feature_set_sha256": feature_set_sha256,
                "values": {
                    **base["values"],
                    **semantic_values,
                },
            }
        )
        per_session[day] += 1

    panel: dict[str, Any] = {
        **{
            key: value
            for key, value in feature_panel.items()
            if key
            not in {
                "panel_sha256",
                "feature_definitions",
                "feature_set_sha256",
                "rows",
                "sessions",
                "feature_row_count",
                "session_count",
            }
        },
        "panel_id": "AE001-T012-CORE91-v1",
        "trial_id": T012_ID,
        "base_feature_panel_sha256": feature_panel["panel_sha256"],
        "announcement_panel_sha256": announcement_panel["panel_sha256"],
        "feature_definitions": definitions,
        "feature_set_sha256": feature_set_sha256,
        "semantic_feature_definition_sha256": SEMANTIC_DEFINITION_SHA256,
        "semantic_hash_dimensions": HASH_DIMENSIONS,
        "semantic_eligible_event_count": eligible_events,
        "semantic_zero_token_event_count": zero_token_events,
        "semantic_nonzero_feature_row_count": semantic_nonzero_rows,
        "semantic_excluded_preclose_count": excluded_preclose,
        "semantic_excluded_non_same_trading_day_count": (
            excluded_non_same_trading_day
        ),
        "semantic_excluded_no_identity_count": excluded_no_identity,
        "semantic_excluded_after_last_cutoff_count": (
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
