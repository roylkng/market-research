from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from marketlab.alpha import (
    AlphaContractError,
    FeatureDefinition,
    append_feature_row,
    digest,
    new_feature_snapshot,
)
from marketlab.alpha_market import (
    DailyEquityObservation,
    build_dynamic_universe,
    build_price_volume_features,
)

AE001_UNIVERSE_ID = "AE001-U001-DYNAMIC"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


PRICE_VOLUME_DEFINITIONS = [
    FeatureDefinition(
        "momentum_1",
        "price_trend",
        "v1",
        "One completed-session close-to-close momentum.",
        1,
    ),
    FeatureDefinition(
        "momentum_3",
        "price_trend",
        "v1",
        "Three completed-session close-to-close momentum.",
        3,
    ),
    FeatureDefinition(
        "momentum_5",
        "price_trend",
        "v1",
        "Five completed-session close-to-close momentum.",
        5,
    ),
    FeatureDefinition(
        "momentum_10",
        "price_trend",
        "v1",
        "Ten completed-session close-to-close momentum.",
        10,
    ),
    FeatureDefinition(
        "momentum_20",
        "price_trend",
        "v1",
        "Twenty completed-session close-to-close momentum.",
        20,
    ),
    FeatureDefinition(
        "momentum_60",
        "price_trend",
        "v1",
        "Sixty completed-session close-to-close momentum.",
        60,
    ),
    FeatureDefinition(
        "realized_vol_20",
        "volatility_liquidity",
        "v1",
        "Population standard deviation of twenty daily close returns.",
        20,
    ),
    FeatureDefinition(
        "realized_vol_60",
        "volatility_liquidity",
        "v1",
        "Population standard deviation of sixty daily close returns.",
        60,
    ),
    FeatureDefinition(
        "distance_from_high_20",
        "price_trend",
        "v1",
        "Close relative to the trailing twenty-session high.",
        20,
    ),
    FeatureDefinition(
        "distance_from_high_60",
        "price_trend",
        "v1",
        "Close relative to the trailing sixty-session high.",
        60,
    ),
    FeatureDefinition(
        "overnight_gap",
        "price_trend",
        "v1",
        "Current session open relative to official previous close.",
        1,
    ),
    FeatureDefinition(
        "open_to_close",
        "price_trend",
        "v1",
        "Current session close relative to current session open.",
        1,
    ),
    FeatureDefinition(
        "intraday_range",
        "volatility_liquidity",
        "v1",
        "Current high-low range divided by official previous close.",
        1,
    ),
    FeatureDefinition(
        "turnover_inr",
        "volatility_liquidity",
        "v1",
        "Current NSE traded value in INR.",
        1,
    ),
    FeatureDefinition(
        "turnover_surprise_20",
        "volatility_liquidity",
        "v1",
        "Current traded value divided by prior twenty-session median.",
        20,
    ),
    FeatureDefinition(
        "volume_surprise_20",
        "volatility_liquidity",
        "v1",
        "Current traded volume divided by prior twenty-session median.",
        20,
    ),
    FeatureDefinition(
        "trade_count_surprise_20",
        "volatility_liquidity",
        "v1",
        "Current trade count divided by prior twenty-session median.",
        20,
    ),
    FeatureDefinition(
        "amihud_20_scaled",
        "volatility_liquidity",
        "v1",
        "Mean absolute return over traded value, scaled by one billion.",
        20,
    ),
]


def _parse_timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise AlphaContractError(f"{field} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise AlphaContractError(f"{field} must be timezone-aware")
    return parsed


def build_market_source_manifest(
    sources: list[dict[str, str]],
    *,
    decision_timestamp: str,
) -> dict[str, Any]:
    if not sources:
        raise AlphaContractError("at least one market source is required")
    decision = _parse_timestamp(decision_timestamp, "decision_timestamp")
    seen_sessions: set[str] = set()
    normalized = []
    latest_known_at: datetime | None = None
    for source in sources:
        session_date = str(source.get("session_date") or "").strip()
        sha256 = str(source.get("sha256") or "").strip().lower()
        known_at = str(source.get("known_at") or "").strip()
        if not session_date or session_date in seen_sessions:
            raise AlphaContractError("market sources require unique session dates")
        seen_sessions.add(session_date)
        if not _SHA256.fullmatch(sha256):
            raise AlphaContractError(f"invalid market source sha256 for {session_date}")
        observed = _parse_timestamp(known_at, f"{session_date}.known_at")
        if observed > decision:
            raise AlphaContractError(
                f"{session_date}: market source became known after decision cutoff"
            )
        latest_known_at = observed if latest_known_at is None else max(latest_known_at, observed)
        normalized.append(
            {
                "session_date": session_date,
                "sha256": sha256,
                "known_at": known_at,
            }
        )
    normalized.sort(key=lambda row: row["session_date"])
    manifest = {
        "schema_version": 1,
        "source_kind": "OFFICIAL_NSE_UDIFF_EQ_DAILY_PANEL",
        "sources": normalized,
        "outcomes_attached": False,
    }
    manifest["manifest_sha256"] = digest(manifest)
    manifest["latest_known_at"] = latest_known_at.isoformat()
    return manifest


def build_price_volume_snapshot(
    observations: list[DailyEquityObservation],
    *,
    current_session: str,
    decision_timestamp: str,
    sources: list[dict[str, str]],
    industry_by_identity: dict[tuple[str, str], str] | None = None,
) -> dict[str, Any]:
    manifest = build_market_source_manifest(
        sources,
        decision_timestamp=decision_timestamp,
    )
    universe = build_dynamic_universe(
        observations,
        current_session=current_session,
    )
    universe_sha256 = digest(
        [{"symbol": symbol, "isin": isin} for symbol, isin in universe]
    )
    snapshot = new_feature_snapshot(
        session_date=current_session,
        decision_timestamp=decision_timestamp,
        universe_id=AE001_UNIVERSE_ID,
        universe_sha256=universe_sha256,
        definitions=PRICE_VOLUME_DEFINITIONS,
    )
    source_ref = [
        {
            "sha256": manifest["manifest_sha256"],
            "known_at": manifest["latest_known_at"],
        }
    ]
    known_at = {
        definition.name: manifest["latest_known_at"]
        for definition in PRICE_VOLUME_DEFINITIONS
    }
    source_refs = {
        definition.name: source_ref
        for definition in PRICE_VOLUME_DEFINITIONS
    }
    industries = industry_by_identity or {}
    for symbol, isin in universe:
        values = build_price_volume_features(
            observations,
            symbol=symbol,
            isin=isin,
            current_session=current_session,
        )
        snapshot = append_feature_row(
            snapshot,
            symbol=symbol,
            isin=isin,
            industry=industries.get((symbol, isin)),
            values=values,
            known_at=known_at,
            source_refs=source_refs,
        )
    snapshot["market_source_manifest"] = manifest
    snapshot["snapshot_sha256"] = _rehash(snapshot)
    return snapshot


def _rehash(snapshot: dict[str, Any]) -> str:
    payload = dict(snapshot)
    payload.pop("snapshot_sha256", None)
    return digest(payload)
