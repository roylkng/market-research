from __future__ import annotations

import gzip
import json
from collections import defaultdict, deque
from dataclasses import asdict
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, cross_sectional_percentile, digest
from marketlab.alpha_market import (
    DailyEquityObservation,
    build_price_volume_features_from_history,
    eligible_history_for_ae001,
)
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS

IST = ZoneInfo("Asia/Kolkata")
HISTORICAL_EVIDENCE_CLASS = "HISTORICAL_RECONSTRUCTION_DEVELOPMENT"
AE001_HISTORICAL_PANEL_ID = "AE001-HISTORICAL-PRICE-VOLUME-v1"


def historical_decision_timestamp(session_date: str) -> str:
    """Frozen AE001 EOD development cutoff: 18:30 Asia/Kolkata."""

    day = datetime.fromisoformat(session_date).date()
    return datetime.combine(day, time(18, 30), IST).isoformat()


def historical_market_information_known_at(session_date: str) -> str:
    """Conservative EOD information timestamp for historical market values.

    This does not claim the archive bytes were captured in real time. Historical
    official archives are development evidence. The market values themselves are
    treated as known no later than 18:00 IST, still before AE001's 18:30 decision.
    """

    day = datetime.fromisoformat(session_date).date()
    return datetime.combine(day, time(18, 0), IST).isoformat()


def canonical_gzip_json(payload: Any) -> bytes:
    raw = (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode()
    return gzip.compress(raw, compresslevel=9, mtime=0)


def load_canonical_gzip_json(raw: bytes) -> Any:
    try:
        decoded = gzip.decompress(raw).decode("utf-8")
        return json.loads(decoded)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AlphaContractError("invalid canonical gzip JSON artifact") from exc


def build_historical_feature_panel(
    *,
    sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Materialize scalable AE001 price/volume features from ordered daily sessions.

    Each session record must contain:
      session_date, udiff_sha256, benchmark_sha256, equities.
    Historical archive retrieval is explicitly development evidence, not prospective
    capture evidence.
    """

    if not sessions:
        raise AlphaContractError("historical sessions cannot be empty")
    ordered = sorted(sessions, key=lambda row: str(row["session_date"]))
    if [row["session_date"] for row in sessions] != [
        row["session_date"] for row in ordered
    ]:
        raise AlphaContractError("historical sessions must be strictly chronological")
    if len({str(row["session_date"]) for row in ordered}) != len(ordered):
        raise AlphaContractError("historical sessions contain duplicate dates")

    feature_definitions = [asdict(definition) for definition in PRICE_VOLUME_DEFINITIONS]
    feature_definitions.sort(key=lambda row: row["name"])
    feature_set_sha256 = digest(feature_definitions)

    histories: dict[
        tuple[str, str], deque[DailyEquityObservation]
    ] = defaultdict(lambda: deque(maxlen=61))
    source_sha_by_session: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    session_records: list[dict[str, Any]] = []

    for session in ordered:
        session_date = str(session["session_date"])
        udiff_sha = str(session.get("udiff_sha256") or "").strip().lower()
        benchmark_sha = str(session.get("benchmark_sha256") or "").strip().lower()
        if len(udiff_sha) != 64 or len(benchmark_sha) != 64:
            raise AlphaContractError(
                f"{session_date}: source hashes must be SHA-256 hex strings"
            )
        source_sha_by_session[session_date] = udiff_sha
        equities = session.get("equities")
        if not isinstance(equities, list) or not equities:
            raise AlphaContractError(f"{session_date}: equities must be a non-empty list")

        current_identities: list[tuple[str, str]] = []
        current_rows: list[DailyEquityObservation] = []
        seen: set[tuple[str, str]] = set()
        for raw_row in equities:
            if isinstance(raw_row, DailyEquityObservation):
                observation = raw_row
            elif isinstance(raw_row, dict):
                try:
                    observation = DailyEquityObservation(**raw_row)
                except TypeError as exc:
                    raise AlphaContractError(
                        f"{session_date}: malformed equity observation"
                    ) from exc
            else:
                raise AlphaContractError(
                    f"{session_date}: equity observations must be objects"
                )
            if observation.session_date != session_date:
                raise AlphaContractError(
                    f"{session_date}: equity observation session mismatch"
                )
            identity = (observation.symbol, observation.isin)
            if identity in seen:
                raise AlphaContractError(
                    f"{session_date}: duplicate equity identity {identity}"
                )
            seen.add(identity)
            current_identities.append(identity)
            current_rows.append(observation)

        for observation in current_rows:
            histories[(observation.symbol, observation.isin)].append(observation)

        eligible: list[tuple[str, str]] = []
        for identity in sorted(current_identities):
            history = list(histories[identity])
            if eligible_history_for_ae001(history):
                eligible.append(identity)

        universe_sha256 = digest(
            [{"symbol": symbol, "isin": isin} for symbol, isin in eligible]
        )
        information_known_at = historical_market_information_known_at(session_date)
        decision_timestamp = historical_decision_timestamp(session_date)

        for symbol, isin in eligible:
            history = list(histories[(symbol, isin)])
            values = build_price_volume_features_from_history(history)
            source_window = [
                {
                    "session_date": observation.session_date,
                    "udiff_sha256": source_sha_by_session[observation.session_date],
                }
                for observation in history
            ]
            source_window_sha256 = digest(source_window)
            rows.append(
                {
                    "feature_session": session_date,
                    "decision_timestamp": decision_timestamp,
                    "symbol": symbol,
                    "isin": isin,
                    "universe_sha256": universe_sha256,
                    "feature_set_sha256": feature_set_sha256,
                    "values": values,
                    "known_at": information_known_at,
                    "source_window_sha256": source_window_sha256,
                    "outcomes_attached": False,
                }
            )

        session_records.append(
            {
                "session_date": session_date,
                "eligible_count": len(eligible),
                "universe_sha256": universe_sha256,
                "udiff_sha256": udiff_sha,
                "benchmark_sha256": benchmark_sha,
            }
        )

    panel: dict[str, Any] = {
        "schema_version": 1,
        "panel_id": AE001_HISTORICAL_PANEL_ID,
        "engine_id": "AE001-v1-DEVELOPMENT",
        "evidence_class": HISTORICAL_EVIDENCE_CLASS,
        "historical_archives_captured_prospectively": False,
        "feature_set_sha256": feature_set_sha256,
        "feature_definitions": feature_definitions,
        "session_count": len(session_records),
        "feature_row_count": len(rows),
        "sessions": session_records,
        "rows": rows,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def cross_sectionalize_panel(panel: dict[str, Any]) -> dict[str, Any]:
    """Replace raw feature values with tie-aware within-session percentiles."""

    if panel.get("outcomes_attached") is not False:
        raise AlphaContractError("historical feature panel must not contain outcomes")
    definitions = panel.get("feature_definitions")
    if not isinstance(definitions, list) or not definitions:
        raise AlphaContractError("historical panel feature definitions are missing")
    feature_names = [str(row["name"]) for row in definitions]

    rows = panel.get("rows")
    if not isinstance(rows, list):
        raise AlphaContractError("historical feature panel rows must be a list")
    by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_session[str(row["feature_session"])].append(row)

    ranked_rows: list[dict[str, Any]] = []
    for session_date in sorted(by_session):
        session_rows = by_session[session_date]
        ranked_by_feature: dict[str, dict[str, float | None]] = {}
        for feature in feature_names:
            values = {
                f"{row['symbol']}|{row['isin']}": row["values"].get(feature)
                for row in session_rows
            }
            ranked_by_feature[feature] = cross_sectional_percentile(values)

        for row in sorted(
            session_rows, key=lambda candidate: (candidate["symbol"], candidate["isin"])
        ):
            key = f"{row['symbol']}|{row['isin']}"
            ranked_rows.append(
                {
                    **{field: value for field, value in row.items() if field != "values"},
                    "values": {
                        feature: ranked_by_feature[feature][key]
                        for feature in feature_names
                    },
                }
            )

    ranked = {
        **{field: value for field, value in panel.items() if field not in {"rows", "panel_sha256"}},
        "transform": "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1",
        "rows": ranked_rows,
    }
    ranked["panel_sha256"] = digest(ranked)
    return ranked
