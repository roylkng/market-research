"""Reconcile 28 outside-U001 hidden gems to already acquired GF001 full-market XBRL.

The original 4 October 2026 full-market artifact is the only source.
A H023 U001 source ledger is NEVER an authority for these 28 candidates.
An observed pledge boolean is NOT a number of pledged shares; absent MF
context is NOT zero ownership, and the report is NOT current 11 October.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha import digest
from marketlab.gf001_governance import parse_current_governance_xbrl

COHORT_PATH = Path("research/hg002-d001-result-v1.json")
COHORT_GIT_BLOB = "e4313bd333595fce068dc8fd0882dec16f2ec8b6"
U001_PATH = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")
U001_GIT_BLOB = "8026e81faee3e913d2fba1dba72d60603b69fa07"
GF001_RESULT_PATH = Path("research/gf001-d002-result-v1.json")
EXPECTED_GF001_PANEL_SHA256 = "dd338cd91f44396278300e27e8cdac1506dae11b63dd31ce827505fe62e8abe7"
EXPECTED_SS001_SOURCE_SHA256 = "214c1172491d58800dcded126303e7a2844967e75da57e0e6f666abc3b311293"
ARTIFACT_RUN_ID = 37202941712
ARTIFACT_ID = 11303742567
SS001_RUN_ID = 37198355430
SS001_ARTIFACT_ID = 11302177421
AUDIT_ID = "HG007-P038-28-COMPANY-OCT04-GOVERNANCE-SOURCE-v1"
FROZEN_CAPTURE_BEFORE_UTC = datetime(2026, 10, 6, tzinfo=UTC)


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_bytes())
    if not isinstance(obj, dict):
        raise TypeError(f"{path}: source must be a JSON mapping")
    return obj


def frozen_outside_u001(root: Path) -> tuple[list[str], dict[str, Any]]:
    raw = (root / COHORT_PATH).read_bytes()
    if _git_blob(raw) != COHORT_GIT_BLOB:
        raise ValueError("HG002 frozen original 28-company source changed")
    original = json.loads(raw)
    frozen = original.get("symbols")
    if (
        original.get("cohort_id") != "HG002-D001-v1"
        or original.get("cohort_count") != 28
        or not isinstance(frozen, list)
        or len(frozen) != 28
        or len(set(frozen)) != 28
        or original.get("live_capital_allowed") is not False
    ):
        raise ValueError("original HG002 28-name cohort identity invalid")
    u001_bytes = (root / U001_PATH).read_bytes()
    if _git_blob(u001_bytes) != U001_GIT_BLOB:
        raise ValueError("U001 original universe Git source changed")
    u001 = json.loads(u001_bytes)
    members = u001.get("members")
    if not isinstance(members, list) or len(members) != 100:
        raise ValueError("frozen U001 100-name membership changed")
    source_symbols = {m["symbol"] for m in members}
    if len(source_symbols) != 100 or not set(frozen).isdisjoint(source_symbols):
        raise ValueError("HG002 outside-U001 research overlap/source drift")
    return frozen, {
        "hg002_original_git_blob": COHORT_GIT_BLOB,
        "u001_original_git_blob": U001_GIT_BLOB,
        "hg002_count": 28,
        "u001_count": 100,
        "intersection_count": 0,
    }


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("original NSE filing time must be string")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("original NSE filing timestamp missing timezone")
    return parsed.astimezone(UTC)


def validate_original_full_market(
    census: dict[str, Any],
    panel: dict[str, Any],
    gf001_result: dict[str, Any],
) -> datetime:
    if (
        gf001_result.get("diagnostic_id") != "GF001-D002-v1"
        or gf001_result.get("panel_sha256") != EXPECTED_GF001_PANEL_SHA256
        or gf001_result.get("source_d002_census_sha256")
        != EXPECTED_SS001_SOURCE_SHA256
        or gf001_result.get("successful_run", {}).get("run_id") != ARTIFACT_RUN_ID
        or gf001_result.get("successful_run", {}).get("artifact_id") != ARTIFACT_ID
        or gf001_result.get("live_capital_allowed") is not False
    ):
        raise ValueError("GF001 original run/result identity changed")
    if (
        census.get("census_id") != "SS001-D002-v1"
        or census.get("census_sha256") != EXPECTED_SS001_SOURCE_SHA256
        or census.get("live_capital_allowed") is not False
        or census.get("identity_count") != 2319
    ):
        raise ValueError("SS001 original full-market shareholding census not verified")
    if (
        panel.get("panel_id") != "GF001-D002-v1"
        or panel.get("source_d002_census_sha256") != EXPECTED_SS001_SOURCE_SHA256
        or panel.get("panel_sha256") != EXPECTED_GF001_PANEL_SHA256
        or digest({k: v for k, v in panel.items() if k != "panel_sha256"})
        != EXPECTED_GF001_PANEL_SHA256
        or panel.get("live_capital_allowed") is not False
        or panel.get("portfolio_eligibility_allowed") is not False
        or panel.get("model_fitted") is not False
        or panel.get("identity_count") != 2319
        or panel.get("latest_core_ready_count") != 1999
    ):
        raise ValueError("GF001 original full-market panel SHA or status changed")
    captured = _timestamp(panel.get("captured_at_utc"))
    if captured >= FROZEN_CAPTURE_BEFORE_UTC:
        raise ValueError("GF001 snapshot was not captured during original Oct4 run")
    for obj, label in ((census, "SS001 census"), (panel, "GF001 panel")):
        rows = obj.get("rows")
        if not isinstance(rows, list) or len(rows) != 2319:
            raise ValueError(f"{label}: full 2319 identity accounting missing")
        symbols = [row.get("symbol") for row in rows if isinstance(row, dict)]
        if len(symbols) != 2319 or len(set(symbols)) != 2319:
            raise ValueError(f"{label}: duplicate or missing company identity")
    return captured


def _raw_original(
    raw_dir: Path,
    observed: dict[str, Any],
    *,
    symbol: str,
    original_source: dict[str, Any],
) -> tuple[bytes, str]:
    expected = observed.get("raw_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError(f"{symbol}: original GF001 raw XBRL SHA absent")
    original = raw_dir / "xbrl" / "sha256" / f"{expected}.xml"
    raw = original.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"{symbol}: original GF001 XBRL bytes changed")
    if (
        observed.get("symbol") != symbol
        or observed.get("report_date") != original_source.get("report_date")
        or observed.get("source_url") != original_source.get("xbrl_url")
        or observed.get("parser_status") != "CORE_READY"
    ):
        raise ValueError(f"{symbol}: original GF001 and NSE source identity conflict")
    reparsed = parse_current_governance_xbrl(
        raw, symbol=symbol,
        report_date=str(original_source["report_date"]),
        source_url=str(original_source["xbrl_url"]),
    )
    if reparsed != observed:
        raise ValueError(f"{symbol}: original XBRL parsed terms differ from frozen GF001")
    return raw, expected


def build_outside_u001_governance(
    *,
    symbols: list[str],
    census: dict[str, Any],
    panel: dict[str, Any],
    artifact_raw_root: Path,
    extracted_original_dir: Path,
    captured: datetime,
) -> dict[str, Any]:
    if len(symbols) != 28 or len(set(symbols)) != 28:
        raise ValueError("frozen 28-name HG002 identity required")
    by_census = {row["symbol"]: row for row in census["rows"]}
    by_panel = {row["symbol"]: row for row in panel["rows"]}
    if set(by_census) != set(by_panel):
        raise ValueError("full market GF001 / SS001 source universe mismatch")
    states: list[dict[str, Any]] = []
    copied: set[str] = set()
    for symbol in symbols:
        source = by_census[symbol]
        row = by_panel[symbol]
        if source.get("source_state") != row.get("source_state"):
            raise ValueError(f"{symbol}: frozen source availability state differs")
        metadata = source.get("latest")
        governance = row.get("latest")
        if source.get("source_state") == "READY":
            if not isinstance(metadata, dict):
                raise TypeError(f"{symbol}: original NSE latest source identity absent")
            if _timestamp(metadata.get("broadcast_at_utc")) > captured:
                raise ValueError(f"{symbol}: future filing leaks into earlier source snapshot")
        state = "ORIGINAL_OCT04_GOVERNANCE_SOURCE_UNAVAILABLE"
        latest_record = None
        if row.get("governance_state") == "CORE_READY":
            if not isinstance(governance, dict) or not isinstance(metadata, dict):
                raise TypeError(f"{symbol}: GF001 core ready without source evidence")
            raw, sha = _raw_original(
                artifact_raw_root, governance, symbol=symbol, original_source=metadata
            )
            to = extracted_original_dir / f"{sha}.xml"
            to.parent.mkdir(parents=True, exist_ok=True)
            if to.exists() and to.read_bytes() != raw:
                raise ValueError("source hash collision while copying original XBRL")
            to.write_bytes(raw)
            if hashlib.sha256(to.read_bytes()).hexdigest() != sha:
                raise ValueError("retained XBRL source SHA differs after write")
            copied.add(sha)
            enc = governance.get("promoter_encumbrance")
            if not isinstance(enc, dict) or any(type(value) is not bool for value in enc.values()):
                raise ValueError(f"{symbol}: official encumbrance flags not exact booleans")
            state = "OCT04_GOVERNANCE_FACTS_READY_NOT_CURRENT"
            latest_record = {
                "report_date": governance["report_date"],
                "source_broadcast_utc": metadata["broadcast_at_utc"],
                "source_xbrl_url": metadata["xbrl_url"],
                "source_xbrl_sha256": sha,
                "source_original_xbrl_retained": True,
                "promoter_group_pct": governance["promoter_percentage"],
                "public_pct": governance["public_percentage"],
                "mutual_fund_pct": governance["mutual_fund_percentage"] if governance.get("mutual_fund_state") == "READY" else None,
                "mutual_fund_state": governance.get("mutual_fund_state"),
                "promoter_encumbrance_boolean": enc,
                "pledged_share_count_verified_from_this_panel": False,
            }
        elif row.get("governance_state") not in ("CORE_PARSE_FAILED", "SOURCE_UNAVAILABLE"):
            raise ValueError(f"{symbol}: invalid full-market GF001 governance state")
        states.append({
            "symbol": symbol,
            "historical_source_state": state,
            "original_ss001_source_state": source.get("source_state"),
            "gf001_parser_state": row.get("governance_state"),
            "source_report_cutoff_asof_utc": captured.isoformat().replace("+00:00", "Z"),
            "latest_source": latest_record,
            "latest_source_unavailable_or_parser_failed": latest_record is None,
            "original_oct04_review_is_current_oct11_governance": False,
            "absence_of_pledge_on_later_date_proven": False,
            "governance_clean_recertified_for_oct11": False,
            "company_expected_returns_calculated": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        })
    ready = sum(item["historical_source_state"] == "OCT04_GOVERNANCE_FACTS_READY_NOT_CURRENT" for item in states)
    flags = [
        item["symbol"] for item in states
        if item["latest_source"] is not None
        and item["latest_source"]["promoter_encumbrance_boolean"].get("pledge") is True
    ]
    return {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "OUTSIDE_U001_28_COMPANY_ORIGINAL_GF001_GOVERNANCE_SNAPSHOT_NOT_ALPHA",
        "original_snapshot_cutoff_utc": captured.isoformat().replace("+00:00", "Z"),
        "historical_gf001_source_run": ARTIFACT_RUN_ID,
        "historical_gf001_artifact_id": ARTIFACT_ID,
        "historical_ss001_source_run": SS001_RUN_ID,
        "historical_ss001_artifact_id": SS001_ARTIFACT_ID,
        "full_market_panel_sha256": EXPECTED_GF001_PANEL_SHA256,
        "full_market_census_sha256": EXPECTED_SS001_SOURCE_SHA256,
        "selected_outside_u001_company_count": 28,
        "original_oct04_core_ready_count": ready,
        "original_oct04_source_unavailable_or_unready_count": 28 - ready,
        "original_oct04_pledge_boolean_true_symbols": flags,
        "original_xbrl_bytes_retained_unique_count": len(copied),
        "company_rows": states,
        "november_or_2027_current_governance_proven": False,
        "latest_oct11_pledge_quantities_verified": False,
        "case_specific_completion_probabilities_calculated": False,
        "equity_value_targets_calculated": False,
        "stock_recommendations_authorized": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
