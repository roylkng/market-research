"""HG009 P007: conservative source-bound 300-issuer action hazard audit.

Reuses H021's original NSE action parser, but an incomplete public API screen
can NEVER certify a clean, economically adjusted equity total return.
"""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.h021_corporate_action_guard import screen_h021_corporate_actions
from marketlab.hg009_controls import (
    load_hg009_inputs,
    verify_hg009_controls,
)

AUDIT_ID = "HG009-P007-300-NSE-ORIGINAL-ACTION-HAZARD-P1"
FIRST = "2026-10-15"
END_2026 = "2026-12-31"
SELECTED_SHA = "e904e5d69dc7a6c2a45ea3cf34933544bc2634f80e3666125185d475372864d5"
CONTROL_SHA = "8c8d9781adf7900addd28a1a60f1cfb33bed9a1e4985e6c410a010d2c819eef8"
CONTROL_PATH = Path(
    "research/hg009/hg009-p001-matched-300-company-controls-v1.json"
)
ARMS = ("SELECTED", "ONE_LANE", "ZERO_LANE")


def original_hg009_identities(
    original: dict, selected: dict, controls: dict
) -> dict[str, dict[str, str]]:
    verify_hg009_controls(controls, source=original, selected=selected)
    if (
        selected.get("cohort_sha256") != SELECTED_SHA
        or controls.get("manifest_sha256") != CONTROL_SHA
    ):
        raise AlphaContractError("P007 frozen 300-company source changed")
    by_arm = {
        "SELECTED": selected["selected"],
        "ONE_LANE": controls["controls"]["ONE_LANE"],
        "ZERO_LANE": controls["controls"]["ZERO_LANE"],
    }
    result = {}
    for arm in ARMS:
        if len(by_arm[arm]) != 100:
            raise AlphaContractError("P007 original arm denominator not 100")
        result[arm] = {
            row["symbol"]: row["isin"]
            for row in by_arm[arm]
        }
        if len(result[arm]) != 100:
            raise AlphaContractError("P007 duplicate original symbol/ISIN")
    all_names = {
        (sym, isin)
        for group in result.values()
        for sym, isin in group.items()
    }
    if len(all_names) != 300 or len({
        symbol for symbol, isin in all_names
    }) != 300:
        raise AlphaContractError("P007 source identities not unique")
    return result


def build_action_hazard_audit(
    *,
    original: dict,
    selected: dict,
    controls: dict,
    start_session: str,
    end_session: str,
    original_action_raw: bytes | None,
    action_receipt: dict[str, Any] | None,
    prepared_at_utc: str,
) -> dict[str, Any]:
    d1, d2 = date.fromisoformat(start_session), date.fromisoformat(end_session)
    if d1 < date.fromisoformat(FIRST) or d2 > date.fromisoformat(END_2026):
        raise AlphaContractError("P007 cannot extend original frozen action calendar")
    if d2 < d1:
        raise AlphaContractError("P007 action window reversed")
    arms = original_hg009_identities(original, selected, controls)
    combined = {
        symbol: isin
        for arm in ARMS
        for symbol, isin in arms[arm].items()
    }
    screened = screen_h021_corporate_actions(
        symbols_to_isins=combined,
        interval_start=start_session,
        interval_end=end_session,
        raw_source=original_action_raw,
        source_receipt=action_receipt,
        prepared_at_utc=prepared_at_utc,
    )
    by_symbol = {row["symbol"]: row for row in screened["symbol_states"]}
    if len(by_symbol) != 300:
        raise AlphaContractError("P007 H021 action screen lost original names")
    groups = []
    for arm in ARMS:
        for symbol, isin in sorted(arms[arm].items()):
            row = by_symbol[symbol]
            if (
                row["isin"] != isin
                or row["full_interval_corporate_action_coverage_verified"]
                is not False
                or row["raw_price_return_eligible"] is not False
            ):
                raise AlphaContractError("P007 a partial action screen granted clearance")
            groups.append({
                "arm": arm,
                "symbol": symbol,
                "isin": isin,
                "action_screen_state": row["state"],
                "original_action_source_hazards": row["source_reported_hazards"],
                "original_unknown_events": row["source_unknown_events"],
                "full_interval_coverage_verified": False,
                "share_entitlement_adjustments_verified": False,
                "dividend_total_return_adjustments_verified": False,
                "economic_total_return_eligible": False,
                "capital_eligible": False,
            })
    packet = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "interval_start": start_session,
        "interval_end": end_session,
        "frozen_selected_sha256": SELECTED_SHA,
        "frozen_controls_sha256": CONTROL_SHA,
        "screen_source_type": "ORIGINAL_NSE_CORPORATE_ACTION_API_NOT_EXHAUSTIVE",
        "underlying_H021_screen_packet_sha256": screened["packet_sha256"],
        "source_state": screened["source_state"],
        "source_sha256": screened["source_sha256"],
        "source_captured_at_utc": screened["source_captured_at_utc"],
        "prepared_at_utc": screened["prepared_at_utc"],
        "original_declared_identity_count": 300,
        "original_fixed_arm_counts": {arm: 100 for arm in ARMS},
        "observed_hazard_count": screened["corporate_event_hazard_count"],
        "observed_ambiguous_event_count": screened["unclassified_event_count"],
        "company_hazards": groups,
        "exhaustive_action_coverage_certified": False,
        "dividends_or_bonus_rights_returns_adjusted": False,
        "fully_action_adjusted_investable_equity_returns_count": 0,
        "empty_action_API_response_proves_no_event": False,
        "price_change_alone_is_issuer_total_return": False,
        "live_capital_allowed": False,
    }
    packet["packet_sha256"] = digest(packet)
    return packet


def validate_action_hazard_audit(value: dict[str, Any]) -> None:
    unsigned = copy.deepcopy(value)
    stored = unsigned.pop("packet_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("P007 original hazard packet hash changed")
    if (
        value.get("audit_id") != AUDIT_ID
        or value.get("original_declared_identity_count") != 300
        or len(value.get("company_hazards", [])) != 300
        or value.get("exhaustive_action_coverage_certified") is not False
        or value.get("fully_action_adjusted_investable_equity_returns_count") != 0
        or value.get("live_capital_allowed") is not False
    ):
        raise AlphaContractError("P007 source screening improperly promoted to return")
    expected_arms = {arm: 100 for arm in ARMS}
    if value.get("original_fixed_arm_counts") != expected_arms:
        raise AlphaContractError("P007 original three-arm count drift")
    if (
        value.get("dividends_or_bonus_rights_returns_adjusted") is not False
        or value.get("empty_action_API_response_proves_no_event") is not False
        or value.get("price_change_alone_is_issuer_total_return") is not False
    ):
        raise AlphaContractError("P007 insufficient action proof was promoted")
    source_rows = value["company_hazards"]
    seen_symbols: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    seen_by_arm = {arm: 0 for arm in ARMS}
    for row in source_rows:
        arm = row.get("arm")
        sym, isin = row.get("symbol"), row.get("isin")
        if (
            arm not in seen_by_arm
            or not isinstance(sym, str)
            or not sym
            or not isinstance(isin, str)
            or len(isin) != 12
            or sym in seen_symbols
            or (sym, isin) in seen_pairs
        ):
            raise AlphaContractError("P007 duplicated or changed original issuer identity")
        for key in (
            "full_interval_coverage_verified",
            "share_entitlement_adjustments_verified",
            "dividend_total_return_adjustments_verified",
            "economic_total_return_eligible",
            "capital_eligible",
        ):
            if row.get(key) is not False:
                raise AlphaContractError("P007 issuer not cleared for action-adjusted return")
        if not isinstance(row.get("original_action_source_hazards"), list):
            raise AlphaContractError("P007 action hazard evidence list invalid")
        if not isinstance(row.get("original_unknown_events"), list):
            raise AlphaContractError("P007 ambiguous event evidence list invalid")
        seen_symbols.add(sym)
        seen_pairs.add((sym, isin))
        seen_by_arm[arm] += 1
    if seen_by_arm != expected_arms:
        raise AlphaContractError("P007 original per-arm denominator changed")


def load_original_hg009_sources(repo_root: Path) -> tuple[dict, dict, dict]:
    original, selected = load_hg009_inputs(repo_root)
    controls = json.loads((repo_root / CONTROL_PATH).read_text("utf-8"))
    return original, selected, controls
