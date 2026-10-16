"""Versioned, non-destructive repair record for HG007 Datamatics P049 SHA.

Original v1 bytes, original prices and original signatures are NEVER rewritten.
A deterministic discrepancy receipt binds historical Git objects and the
project's canonical digest implementation. No price targets or investable
expected returns are authorized.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest

REPAIR_ID = "HG007-P049-LEGACY-CANONICAL-SHA-DISCREPANCY-v2"
OLD_PATH = Path("research/hg007/hg007-p049-datamatics-cash-hurdle-v1.json")
OLD_GIT_BLOB = "706c2dd100a49859b5054323baeddc345531fb59"
OLD_CLAIMED_SHA = "1b72056878c56f12f5c13b8f7d557d1fa8fa0e67c34fddd60621ffd890cfb278"
P047_PATH = Path("research/hg007/hg007-p047-oct13-28-official-nse-source-v1.json")
P047_GIT_BLOB = "5e495c980985e0c42c112868cb04bfffb27807dd"
RESEARCH_DATE = "2026-10-16"


def _blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _read_original(root: Path, path: Path, blob: str) -> tuple[dict, str]:
    raw = (root / path).read_bytes()
    if _blob(raw) != blob:
        raise AlphaContractError(f"P049 repair source Git object drifted: {path}")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise AlphaContractError("P049 repair source requires JSON object")
    return parsed, hashlib.sha256(raw).hexdigest()


def build_p049_sha_repair(root: Path) -> dict[str, Any]:
    legacy, old_sha = _read_original(root, OLD_PATH, OLD_GIT_BLOB)
    market, market_sha = _read_original(root, P047_PATH, P047_GIT_BLOB)
    old_signed = legacy.get("packet_sha256")
    if old_signed != OLD_CLAIMED_SHA:
        raise AlphaContractError("P049 repair expected legacy signed value changed")
    old_unsigned = copy.deepcopy(legacy)
    old_unsigned.pop("packet_sha256", None)
    recomputed = digest(old_unsigned)
    if recomputed == old_signed:
        raise AlphaContractError(
            "P049 legacy signature now matches, no discrepancy remains"
        )
    if (
        legacy.get("audit_id")
        != "HG007-P049-DATAMATICS-FY26-CASH-FLOW-REVERSE-HURDLE-v1"
        or legacy.get("live_capital_allowed") is not False
        or legacy.get("portfolio_eligibility_allowed") is not False
        or legacy.get("expected_future_total_return") is not None
        or legacy.get("probability_weighted_fair_value_inr") is not None
    ):
        raise AlphaContractError("P049 original historical research state changed")
    market_unsigned = copy.deepcopy(market)
    market_claimed = market_unsigned.pop("packet_sha256", None)
    if market_claimed != digest(market_unsigned):
        raise AlphaContractError("P049 parent original NSE market self-signature invalid")
    observed = [
        row for row in market.get("company_source_observations", [])
        if row.get("symbol") == "DATAMATICS"
    ]
    if (
        len(observed) != 1
        or observed[0].get("frozen_isin") != "INE365B01017"
        or market.get("market_session_ist") != "2026-10-13"
        or observed[0].get("reported_EQ_close_inr") != 777.9
        or legacy["market_source"].get(
            "frozen_original_28_case_packet_sha256"
        ) != market_claimed
        or legacy["market_source"].get(
            "official_EQ_close_inr_not_current_quote"
        ) != observed[0]["reported_EQ_close_inr"]
        or legacy["market_source"].get("isin") != observed[0]["frozen_isin"]
    ):
        raise AlphaContractError("P049 source P047 October13 EQ/share lineage drift")

    return_packet = {
        "schema_version": 2,
        "repair_id": REPAIR_ID,
        "research_date": RESEARCH_DATE,
        "status": "KNOWN_LEGACY_PACKET_SELF_SHA_MISMATCH_NOT_SILENT_REWRITE",
        "legacy_original_json_repo_path": str(OLD_PATH),
        "legacy_original_json_git_blob_sha": OLD_GIT_BLOB,
        "legacy_original_json_raw_sha256": old_sha,
        "legacy_original_claimed_packet_sha256": old_signed,
        "recomputed_original_canonical_body_sha256": recomputed,
        "legacy_original_self_signature_matches_canonical_digest": False,
        "numeric_serialization_mismatch_root_cause_independently_proven": False,
        "source_byte_identity_preserved": True,
        "original_values_or_share_count_recomputed_from_new_information": False,
        "original_v1_packet_modified": False,
        "parent_original_nse_market_path": str(P047_PATH),
        "parent_original_nse_market_git_blob_sha": P047_GIT_BLOB,
        "parent_original_nse_market_raw_sha256": market_sha,
        "parent_original_nse_market_packet_sha256": market_claimed,
        "frozen_market_session": "2026-10-13",
        "frozen_exchange_symbol": "DATAMATICS",
        "frozen_original_isin": "INE365B01017",
        "frozen_original_oct13_eq_close_inr_not_current": 777.9,
        "legacy_reported_cashflow_proxy_is_not_owner_cash": True,
        "current_oct16_fully_diluted_share_count_verified": False,
        "new_expected_returns_or_probability_published": False,
        "new_investment_recommendations": False,
        "live_capital_allowed": False,
    }
    return_packet["repair_packet_sha256"] = digest(return_packet)
    return return_packet


def verify_repair_artifact(packet: dict, *, root: Path) -> None:
    unsigned = copy.deepcopy(packet)
    sha = unsigned.pop("repair_packet_sha256", None)
    if sha != digest(unsigned):
        raise AlphaContractError("P049 v2 signed discrepancy record altered")
    if packet != build_p049_sha_repair(root):
        raise AlphaContractError("P049 v2 does not match pinned original historical sources")
