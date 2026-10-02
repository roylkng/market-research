from __future__ import annotations

import re
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import sha256_bytes

D009_DIAGNOSTIC_ID = "RM001-D009-v1"
SAMPLE_SYMBOLS = (
    "RELIANCE",
    "TCS",
    "HDFCBANK",
    "BHARTIARTL",
    "SUNPHARMA",
    "LT",
    "MARUTI",
    "HINDUNILVR",
    "TATASTEEL",
    "POWERGRID",
    "TITAN",
    "DIVISLAB",
    "BBOX",
    "WALCHANNAG",
    "DAMODARIND",
    "PIDILITIND",
)
MIN_FRACTION = 0.90


def _normalized_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _mapping_by_normalized_key(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in payload.items():
        normalized = _normalized_key(key)
        if normalized and normalized not in result:
            result[normalized] = value
    return result


def _first_nonempty(
    mapping: dict[str, Any],
    aliases: tuple[str, ...],
) -> str | None:
    for alias in aliases:
        value = mapping.get(alias)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def parse_quote_industry(
    payload: dict[str, Any],
    *,
    requested_symbol: str,
) -> dict[str, Any]:
    requested = requested_symbol.strip().upper()
    if not requested:
        raise AlphaContractError("D009 requested symbol is required")

    info_raw = payload.get("info")
    industry_raw = payload.get("industryInfo")
    if not isinstance(info_raw, dict):
        return {
            "requested_symbol": requested,
            "status": "MISSING_INFO_OBJECT",
            "returned_symbol": None,
            "isin": None,
            "classification": None,
            "industry_info_normalized_keys": [],
        }
    if not isinstance(industry_raw, dict):
        return {
            "requested_symbol": requested,
            "status": "MISSING_INDUSTRY_INFO_OBJECT",
            "returned_symbol": str(info_raw.get("symbol") or "").strip().upper() or None,
            "isin": str(info_raw.get("isin") or "").strip() or None,
            "classification": None,
            "industry_info_normalized_keys": [],
        }

    info = _mapping_by_normalized_key(info_raw)
    industry = _mapping_by_normalized_key(industry_raw)
    returned_symbol = _first_nonempty(
        info,
        ("symbol", "tradingsymbol", "tickersymbol"),
    )
    returned_symbol = returned_symbol.upper() if returned_symbol else None
    isin = _first_nonempty(info, ("isin", "isincode"))

    classification = {
        "macro_economic_sector": _first_nonempty(
            industry,
            (
                "macro",
                "macroeconomicsector",
                "macrosector",
                "macroeconomic",
            ),
        ),
        "sector": _first_nonempty(industry, ("sector",)),
        "industry": _first_nonempty(industry, ("industry",)),
        "basic_industry": _first_nonempty(
            industry,
            ("basicindustry", "basicind"),
        ),
    }
    missing_classification = [
        key for key, value in classification.items() if not value
    ]
    symbol_conflict = (
        returned_symbol is not None and returned_symbol != requested
    )

    if symbol_conflict:
        status = "SYMBOL_CONFLICT"
    elif returned_symbol is None:
        status = "MISSING_RETURNED_SYMBOL"
    elif isin is None:
        status = "MISSING_ISIN"
    elif missing_classification:
        status = "INCOMPLETE_CLASSIFICATION"
    else:
        status = "READY"

    return {
        "requested_symbol": requested,
        "status": status,
        "returned_symbol": returned_symbol,
        "symbol_identity_match": returned_symbol == requested,
        "isin": isin,
        "classification": classification,
        "missing_classification_fields": missing_classification,
        "industry_info_normalized_keys": sorted(industry),
    }


def build_d009_report(
    *,
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(observations) != len(SAMPLE_SYMBOLS):
        raise AlphaContractError(
            "D009 observation count differs from frozen sample"
        )
    requested = [str(row.get("requested_symbol") or "") for row in observations]
    if tuple(requested) != SAMPLE_SYMBOLS:
        raise AlphaContractError(
            "D009 observation order/symbols differ from frozen sample"
        )

    parseable = 0
    symbol_matches = 0
    isin_count = 0
    four_level_count = 0
    symbol_conflicts = 0
    successful_shapes: set[tuple[str, ...]] = set()

    for row in observations:
        status = str(row.get("status") or "")
        if status not in {"HTTP_ERROR", "ACQUISITION_ERROR"}:
            parseable += 1
        if row.get("symbol_identity_match") is True:
            symbol_matches += 1
        if str(row.get("isin") or "").strip():
            isin_count += 1
        classification = row.get("classification")
        if isinstance(classification, dict) and all(
            str(classification.get(field) or "").strip()
            for field in (
                "macro_economic_sector",
                "sector",
                "industry",
                "basic_industry",
            )
        ):
            four_level_count += 1
        if status == "SYMBOL_CONFLICT":
            symbol_conflicts += 1
        if status == "READY":
            keys = row.get("industry_info_normalized_keys")
            if isinstance(keys, list):
                successful_shapes.add(tuple(str(value) for value in keys))

    total = len(observations)
    parseable_fraction = parseable / total
    symbol_fraction = symbol_matches / total
    isin_fraction = isin_count / total
    classification_fraction = four_level_count / total
    stable_shape = len(successful_shapes) <= 1 and four_level_count > 0

    gates = {
        "parseable_fraction_pass": parseable_fraction >= MIN_FRACTION,
        "symbol_identity_fraction_pass": symbol_fraction >= MIN_FRACTION,
        "isin_fraction_pass": isin_fraction >= MIN_FRACTION,
        "four_level_classification_fraction_pass": (
            classification_fraction >= MIN_FRACTION
        ),
        "symbol_conflict_gate_pass": symbol_conflicts == 0,
        "stable_industry_info_semantics_pass": stable_shape,
    }
    passed = all(gates.values())

    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D009_DIAGNOSTIC_ID,
        "status": (
            "PASS_PROSPECTIVE_SOURCE_FEASIBILITY"
            if passed
            else "FAIL_SOURCE_FEASIBILITY"
        ),
        "evidence_class": "SOURCE_FEASIBILITY_NO_RETURN_OUTCOMES",
        "sample_size": total,
        "sample_symbols": list(SAMPLE_SYMBOLS),
        "parseable_count": parseable,
        "parseable_fraction": parseable_fraction,
        "symbol_identity_match_count": symbol_matches,
        "symbol_identity_fraction": symbol_fraction,
        "isin_count": isin_count,
        "isin_fraction": isin_fraction,
        "four_level_classification_count": four_level_count,
        "four_level_classification_fraction": classification_fraction,
        "symbol_conflict_count": symbol_conflicts,
        "successful_industry_info_shapes": [
            list(shape) for shape in sorted(successful_shapes)
        ],
        "promotion_gates": gates,
        "prospective_capture_design_authorized": passed,
        "historical_backfill_authorized": False,
        "return_labels_opened": False,
        "alpha_outcomes_opened": False,
        "risk_model_fit_performed": False,
        "observations": observations,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report


def raw_observation(
    *,
    requested_symbol: str,
    payload: dict[str, Any],
    raw: bytes,
    source_url: str,
) -> dict[str, Any]:
    parsed = parse_quote_industry(
        payload,
        requested_symbol=requested_symbol,
    )
    parsed["source_url"] = source_url
    parsed["raw_sha256"] = sha256_bytes(raw)
    parsed["raw_byte_count"] = len(raw)
    return parsed
