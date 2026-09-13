from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import date
from typing import Any

import yaml

RULE_ID = "H022-UH001"
HYPOTHESIS_ID = "H022"
DEFAULT_REQUIRED_COLUMNS = (
    "Company Name",
    "Industry",
    "Symbol",
    "Series",
    "ISIN Code",
)


class HistoricalUniverseError(ValueError):
    """Raised when H022 historical membership cannot be reconstructed safely."""


def _canonical_hash(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HistoricalUniverseError(
            "historical-universe payload must contain finite JSON values"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def load_rule(raw_yaml: str) -> dict[str, Any]:
    document = yaml.safe_load(raw_yaml)
    if not isinstance(document, dict):
        raise HistoricalUniverseError("historical-universe rule root must be a mapping")
    if document.get("id") != RULE_ID or document.get("hypothesis_id") != HYPOTHESIS_ID:
        raise HistoricalUniverseError("unexpected historical-universe rule identity")
    if document.get("status") != "FROZEN_HISTORICAL_UNIVERSE_RECONSTRUCTION":
        raise HistoricalUniverseError("historical-universe rule must remain frozen")
    if document.get("live_capital_allowed") is not False:
        raise HistoricalUniverseError("historical-universe rule must keep live capital disabled")
    periodic = document.get("periodic_reconstitution")
    if not isinstance(periodic, dict):
        raise HistoricalUniverseError("periodic reconstitution contract is required")
    excluded = periodic.get("excluded")
    included = periodic.get("included")
    if not isinstance(excluded, list) or not isinstance(included, list):
        raise HistoricalUniverseError("periodic included/excluded lists are required")
    if len(excluded) != periodic.get("expected_excluded_count"):
        raise HistoricalUniverseError("periodic excluded count changed")
    if len(included) != periodic.get("expected_included_count"):
        raise HistoricalUniverseError("periodic included count changed")
    if len(excluded) != len(included):
        raise HistoricalUniverseError("periodic reconstitution must preserve base constituent count")
    return document


def parse_anchor_csv(raw_csv: bytes, rule: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    if not raw_csv:
        raise HistoricalUniverseError("official Nifty 200 anchor CSV is empty")
    try:
        text = raw_csv.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HistoricalUniverseError("official Nifty 200 CSV is not UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    anchor = rule.get("anchor")
    if not isinstance(anchor, dict):
        raise HistoricalUniverseError("anchor rule is missing")
    required = tuple(anchor.get("required_columns") or DEFAULT_REQUIRED_COLUMNS)
    if reader.fieldnames is None or not set(required).issubset(set(reader.fieldnames)):
        raise HistoricalUniverseError(
            f"Nifty 200 CSV header mismatch: expected at least {required}, got {reader.fieldnames}"
        )
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in reader:
        symbol = str(row.get("Symbol") or "").strip().upper()
        if not symbol:
            raise HistoricalUniverseError("Nifty 200 CSV row has empty symbol")
        if symbol in seen:
            raise HistoricalUniverseError(f"duplicate Nifty 200 symbol: {symbol}")
        seen.add(symbol)
        company_name = str(row.get("Company Name") or "").strip()
        industry = str(row.get("Industry") or "").strip()
        series = str(row.get("Series") or "").strip().upper()
        isin = str(row.get("ISIN Code") or "").strip()
        if not company_name or not industry or not series or not isin:
            raise HistoricalUniverseError(f"incomplete Nifty 200 anchor row: {symbol}")
        records.append(
            {
                "symbol": symbol,
                "company_name": company_name,
                "industry": industry,
                "series": series,
                "isin": isin,
                "identity_source": "ANCHOR_CSV",
            }
        )
    expected = int(anchor.get("expected_constituent_count") or 0)
    if len(records) != expected:
        raise HistoricalUniverseError(
            f"anchor constituent count mismatch: expected={expected}, observed={len(records)}"
        )
    return tuple(sorted(records, key=lambda item: item["symbol"]))


def _periodic_maps(rule: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    periodic = rule["periodic_reconstitution"]
    excluded: dict[str, str] = {}
    included: dict[str, str] = {}
    for key, target in (("excluded", excluded), ("included", included)):
        for row in periodic[key]:
            if not isinstance(row, dict):
                raise HistoricalUniverseError(f"periodic {key} row must be a mapping")
            symbol = str(row.get("symbol") or "").strip().upper()
            company = str(row.get("company_name") or "").strip()
            if not symbol or not company or symbol in target:
                raise HistoricalUniverseError(f"invalid/duplicate periodic {key} symbol: {symbol}")
            target[symbol] = company
    return excluded, included


def _load_u001_symbols(universe_payload: object) -> set[str]:
    if not isinstance(universe_payload, dict) or not isinstance(universe_payload.get("members"), list):
        raise HistoricalUniverseError("current U001 payload is invalid")
    symbols: set[str] = set()
    for row in universe_payload["members"]:
        if not isinstance(row, dict):
            raise HistoricalUniverseError("U001 member must be an object")
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol or symbol in symbols:
            raise HistoricalUniverseError(f"invalid/duplicate U001 symbol: {symbol}")
        symbols.add(symbol)
    return symbols


def reconstruct_historical_membership(
    raw_anchor_csv: bytes,
    *,
    rule: dict[str, Any],
    current_u001_payload: object,
) -> dict[str, Any]:
    anchor_records = parse_anchor_csv(raw_anchor_csv, rule)
    anchor_by_symbol = {row["symbol"]: row for row in anchor_records}
    anchor_symbols = set(anchor_by_symbol)
    excluded, included = _periodic_maps(rule)
    excluded_symbols = set(excluded)
    included_symbols = set(included)

    missing_included = sorted(included_symbols - anchor_symbols)
    if missing_included:
        raise HistoricalUniverseError(
            f"March-2026 included symbols missing from Aug-2026 anchor: {missing_included}"
        )
    still_present_excluded = sorted(excluded_symbols & anchor_symbols)
    if still_present_excluded:
        raise HistoricalUniverseError(
            "March-2026 excluded symbols unexpectedly remain in Aug-2026 anchor: "
            f"{still_present_excluded}"
        )

    pre_march_symbols = (anchor_symbols - included_symbols) | excluded_symbols
    expected_count = int(rule["anchor"]["expected_constituent_count"])
    if len(pre_march_symbols) != expected_count:
        raise HistoricalUniverseError(
            f"reverse-reconstructed pre-March membership has {len(pre_march_symbols)} symbols; "
            f"expected {expected_count}"
        )

    u001_symbols = _load_u001_symbols(current_u001_payload)
    not_in_anchor = sorted(u001_symbols - anchor_symbols)
    if not_in_anchor:
        raise HistoricalUniverseError(
            f"current U001 contains symbols outside Nifty 200 anchor: {not_in_anchor}"
        )

    union_symbols = anchor_symbols | pre_march_symbols
    expected_union = int(rule["expanded_universe"]["expected_union_members_if_no_other_permanent_substitutions"])
    if len(union_symbols) != expected_union:
        raise HistoricalUniverseError(
            f"expanded union count mismatch: expected={expected_union}, observed={len(union_symbols)}"
        )

    members: list[dict[str, Any]] = []
    for symbol in sorted(union_symbols):
        if symbol in anchor_by_symbol:
            members.append(dict(anchor_by_symbol[symbol]))
        else:
            members.append(
                {
                    "symbol": symbol,
                    "company_name": excluded[symbol],
                    "industry": None,
                    "series": "EQ",
                    "isin": None,
                    "identity_source": "MARCH_2026_EXCLUSION_RELEASE",
                }
            )

    intervals = rule.get("base_membership_intervals")
    if not isinstance(intervals, list) or len(intervals) != 2:
        raise HistoricalUniverseError("exactly two base membership intervals are required in v1")
    interval_payloads = [
        {
            "interval_id": intervals[0]["interval_id"],
            "start": intervals[0]["start"],
            "end": intervals[0]["end"],
            "member_count": len(pre_march_symbols),
            "symbols": sorted(pre_march_symbols),
        },
        {
            "interval_id": intervals[1]["interval_id"],
            "start": intervals[1]["start"],
            "end": intervals[1]["end"],
            "member_count": len(anchor_symbols),
            "symbols": sorted(anchor_symbols),
        },
    ]
    if date.fromisoformat(str(interval_payloads[0]["end"])) >= date.fromisoformat(
        str(interval_payloads[1]["start"])
    ):
        raise HistoricalUniverseError("historical membership intervals overlap")

    document: dict[str, Any] = {
        "schema_version": 1,
        "rule_id": RULE_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "evidence_class": "HISTORICAL_MEMBERSHIP_RECONSTRUCTION",
        "anchor_as_of": rule["anchor"]["expected_as_of"],
        "anchor_source_url": rule["anchor"]["source_url"],
        "anchor_raw_sha256": hashlib.sha256(raw_anchor_csv).hexdigest(),
        "anchor_member_count": len(anchor_symbols),
        "pre_march_member_count": len(pre_march_symbols),
        "expanded_union_member_count": len(union_symbols),
        "expanded_union_members": members,
        "membership_intervals": interval_payloads,
        "current_u001_member_count": len(u001_symbols),
        "current_u001_in_expanded_union_count": len(u001_symbols & union_symbols),
        "expanded_union_additional_vs_current_u001_count": len(union_symbols - u001_symbols),
        "expanded_union_additional_vs_current_u001_symbols": sorted(union_symbols - u001_symbols),
        "temporary_demerger_constituents": rule["temporary_demerger_constituents"],
        "ad_hoc_base_membership_audit_status": rule["ad_hoc_base_membership_audit"]["status"],
        "historical_u001_reconstructed": False,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    document["reconstruction_sha256"] = _canonical_hash(document)
    return document


def validate_reconstruction(document: dict[str, Any]) -> None:
    stored = document.get("reconstruction_sha256")
    unsigned = dict(document)
    unsigned.pop("reconstruction_sha256", None)
    if stored != _canonical_hash(unsigned):
        raise HistoricalUniverseError("historical membership reconstruction hash mismatch")
    if document.get("rule_id") != RULE_ID:
        raise HistoricalUniverseError("historical membership reconstruction rule changed")
    if document.get("outcome_data_attached") is not False:
        raise HistoricalUniverseError("historical membership reconstruction contains outcomes")
    if document.get("historical_u001_reconstructed") is not False:
        raise HistoricalUniverseError("v1 must not claim historical U001 reconstruction")
    if document.get("live_capital_allowed") is not False:
        raise HistoricalUniverseError("historical membership cannot authorize live capital")
