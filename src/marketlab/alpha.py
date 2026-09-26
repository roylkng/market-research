from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

AE001_ENGINE_ID = "AE001-v1-DEVELOPMENT"
ALLOWED_FEATURE_FAMILIES = {
    "price_trend",
    "volatility_liquidity",
    "fundamental",
    "expectations",
    "corporate_event",
    "ownership_informed_capital",
    "derivatives_flows",
    "regime",
}
_FEATURE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class AlphaContractError(ValueError):
    """Raised when an AE001 artifact would violate point-in-time research rules."""


@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    family: str
    version: str
    description: str
    lookback_sessions: int = 0
    availability_lag_sessions: int = 0

    def validate(self) -> None:
        if not _FEATURE_NAME.fullmatch(self.name):
            raise AlphaContractError(f"invalid feature name: {self.name}")
        if self.family not in ALLOWED_FEATURE_FAMILIES:
            raise AlphaContractError(f"unsupported feature family: {self.family}")
        if not self.version.strip():
            raise AlphaContractError("feature version is required")
        if not self.description.strip():
            raise AlphaContractError("feature description is required")
        if type(self.lookback_sessions) is not int or self.lookback_sessions < 0:
            raise AlphaContractError("lookback_sessions must be a non-negative integer")
        if (
            type(self.availability_lag_sessions) is not int
            or self.availability_lag_sessions < 0
        ):
            raise AlphaContractError(
                "availability_lag_sessions must be a non-negative integer"
            )


def _canonical_bytes(payload: Any) -> bytes:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise AlphaContractError("artifact must contain finite canonical JSON values") from exc


def digest(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _timestamp(value: str, field: str) -> datetime:
    if not isinstance(value, str):
        raise AlphaContractError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise AlphaContractError(f"{field} is not an ISO timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise AlphaContractError(f"{field} must be timezone-aware")
    return parsed


def _feature_set(definitions: list[FeatureDefinition]) -> tuple[list[dict[str, Any]], str]:
    if not definitions:
        raise AlphaContractError("at least one feature definition is required")
    names: set[str] = set()
    rows = []
    for definition in definitions:
        definition.validate()
        if definition.name in names:
            raise AlphaContractError(f"duplicate feature definition: {definition.name}")
        names.add(definition.name)
        rows.append(asdict(definition))
    rows.sort(key=lambda row: row["name"])
    return rows, digest(rows)


def new_feature_snapshot(
    *,
    session_date: str,
    decision_timestamp: str,
    universe_id: str,
    universe_sha256: str,
    definitions: list[FeatureDefinition],
) -> dict[str, Any]:
    _timestamp(decision_timestamp, "decision_timestamp")
    try:
        datetime.fromisoformat(session_date)
    except ValueError as exc:
        raise AlphaContractError("session_date must be ISO YYYY-MM-DD") from exc
    if not universe_id.strip() or not universe_sha256.strip():
        raise AlphaContractError("universe identity and hash are required")
    feature_definitions, feature_set_sha256 = _feature_set(definitions)
    snapshot = {
        "schema_version": 1,
        "engine_id": AE001_ENGINE_ID,
        "research_class": "EXPLORATORY_MODEL_RESEARCH",
        "session_date": session_date,
        "decision_timestamp": decision_timestamp,
        "universe_id": universe_id,
        "universe_sha256": universe_sha256,
        "feature_definitions": feature_definitions,
        "feature_set_sha256": feature_set_sha256,
        "rows": [],
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    snapshot["snapshot_sha256"] = _snapshot_hash(snapshot)
    return snapshot


def _snapshot_hash(snapshot: dict[str, Any]) -> str:
    payload = dict(snapshot)
    payload.pop("snapshot_sha256", None)
    return digest(payload)


def validate_feature_snapshot(snapshot: dict[str, Any]) -> None:
    if snapshot.get("engine_id") != AE001_ENGINE_ID:
        raise AlphaContractError("unexpected AE001 engine_id")
    if snapshot.get("outcomes_attached") is not False:
        raise AlphaContractError("feature snapshot must not contain outcomes")
    if snapshot.get("live_capital_allowed") is not False:
        raise AlphaContractError("AE001 development cannot allow live capital")
    decision = _timestamp(str(snapshot.get("decision_timestamp")), "decision_timestamp")
    definitions = snapshot.get("feature_definitions")
    if not isinstance(definitions, list) or not definitions:
        raise AlphaContractError("feature_definitions must be a non-empty list")
    feature_names = [str(row.get("name")) for row in definitions if isinstance(row, dict)]
    if len(feature_names) != len(definitions) or len(feature_names) != len(set(feature_names)):
        raise AlphaContractError("feature definitions are malformed or duplicated")
    if digest(sorted(definitions, key=lambda row: row["name"])) != snapshot.get(
        "feature_set_sha256"
    ):
        raise AlphaContractError("feature definition hash mismatch")

    seen: set[tuple[str, str]] = set()
    for row in snapshot.get("rows", []):
        if not isinstance(row, dict):
            raise AlphaContractError("feature rows must be objects")
        symbol = str(row.get("symbol") or "").strip().upper()
        isin = str(row.get("isin") or "").strip()
        if not symbol or not isin:
            raise AlphaContractError("feature row requires symbol and ISIN")
        key = (symbol, isin)
        if key in seen:
            raise AlphaContractError(f"duplicate feature row identity: {symbol}/{isin}")
        seen.add(key)

        values = row.get("values")
        known_at = row.get("known_at")
        sources = row.get("source_refs")
        if not isinstance(values, dict) or set(values) != set(feature_names):
            raise AlphaContractError(f"{symbol}: feature values do not match definition set")
        if not isinstance(known_at, dict) or set(known_at) != set(feature_names):
            raise AlphaContractError(f"{symbol}: known_at does not match definition set")
        if not isinstance(sources, dict) or set(sources) != set(feature_names):
            raise AlphaContractError(f"{symbol}: source_refs do not match definition set")

        for feature in feature_names:
            value = values[feature]
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise AlphaContractError(f"{symbol}/{feature}: value must be numeric or null")
                if not math.isfinite(float(value)):
                    raise AlphaContractError(f"{symbol}/{feature}: value must be finite")
            observed = _timestamp(known_at[feature], f"{symbol}/{feature}.known_at")
            if observed > decision:
                raise AlphaContractError(
                    f"{symbol}/{feature}: feature became known after decision cutoff"
                )
            refs = sources[feature]
            if not isinstance(refs, list) or not refs:
                raise AlphaContractError(f"{symbol}/{feature}: at least one source ref is required")
            for ref in refs:
                if not isinstance(ref, dict):
                    raise AlphaContractError(f"{symbol}/{feature}: source ref must be an object")
                source_sha = str(ref.get("sha256") or "").strip()
                source_timestamp = str(ref.get("known_at") or "").strip()
                if not source_sha or not source_timestamp:
                    raise AlphaContractError(
                        f"{symbol}/{feature}: source ref requires sha256 and known_at"
                    )
                if _timestamp(
                    source_timestamp, f"{symbol}/{feature}.source.known_at"
                ) > decision:
                    raise AlphaContractError(
                        f"{symbol}/{feature}: source became known after decision cutoff"
                    )

    expected = _snapshot_hash(snapshot)
    if snapshot.get("snapshot_sha256") != expected:
        raise AlphaContractError("feature snapshot hash mismatch")


def append_feature_row(
    snapshot: dict[str, Any],
    *,
    symbol: str,
    isin: str,
    industry: str | None,
    values: dict[str, float | int | None],
    known_at: dict[str, str],
    source_refs: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    updated = json.loads(json.dumps(snapshot))
    updated.pop("snapshot_sha256", None)
    updated.setdefault("rows", []).append(
        {
            "symbol": symbol.strip().upper(),
            "isin": isin.strip(),
            "industry": industry,
            "values": values,
            "known_at": known_at,
            "source_refs": source_refs,
        }
    )
    updated["rows"].sort(key=lambda row: (row["symbol"], row["isin"]))
    updated["snapshot_sha256"] = _snapshot_hash(updated)
    validate_feature_snapshot(updated)
    return updated


def cross_sectional_percentile(values: dict[str, float | None]) -> dict[str, float | None]:
    """Return tie-aware percentiles in [0, 1], preserving missing values."""

    observed = sorted((float(value), key) for key, value in values.items() if value is not None)
    result: dict[str, float | None] = {key: None for key in values}
    if not observed:
        return result
    if len(observed) == 1:
        result[observed[0][1]] = 0.5
        return result

    index = 0
    while index < len(observed):
        end = index + 1
        while end < len(observed) and observed[end][0] == observed[index][0]:
            end += 1
        average_rank = (index + (end - 1)) / 2.0
        percentile = average_rank / (len(observed) - 1)
        for _, key in observed[index:end]:
            result[key] = percentile
        index = end
    return result
