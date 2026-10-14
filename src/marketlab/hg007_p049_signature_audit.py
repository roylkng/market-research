"""P049 integrity: audit legacy Datamatics JSON self-hash without rewriting it.

Original Git blob identity remains the sole immutable historical source.
This new, separately signed audit records what modern canonical digest computes
and whether the old packet signature is valid.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest

SOURCE = Path("research/hg007/hg007-p049-datamatics-cash-hurdle-v1.json")
SOURCE_GIT_BLOB = "706c2dd100a49859b5054323baeddc345531fb59"
LEGACY_CLAIMED_SHA = "1b72056878c56f12f5c13b8f7d557d1fa8fa0e67c34fddd60621ffd890cfb278"
AUDIT_ID = "HG007-P049-LEGACY-SIGNATURE-CUSTODY-AUDIT-v2"


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode() + bytes((0,)) + raw,
        usedforsecurity=False,
    ).hexdigest()


def build_p049_signature_audit(root: Path) -> dict[str, Any]:
    raw = (root / SOURCE).read_bytes()
    if _git_blob(raw) != SOURCE_GIT_BLOB:
        raise AlphaContractError("P049 exact historical Git blob changed")
    packet = json.loads(raw)
    if not isinstance(packet, dict):
        raise AlphaContractError("P049 legacy original not a JSON object")
    if (
        packet.get("audit_id")
        != "HG007-P049-DATAMATICS-FY26-CASH-FLOW-REVERSE-HURDLE-v1"
        or packet.get("market_source", {}).get("symbol") != "DATAMATICS"
        or packet.get("market_source", {}).get("date") != "2026-10-13"
        or packet.get("expected_future_total_return") is not None
        or packet.get("live_capital_allowed") is not False
    ):
        raise AlphaContractError("P049 historical research identity drift")
    source = copy.deepcopy(packet)
    stated = source.pop("packet_sha256", None)
    recomputed = digest(source)
    if stated != LEGACY_CLAIMED_SHA:
        raise AlphaContractError("P049 observed legacy signature changed")
    result = {
        "schema_version": 2,
        "audit_id": AUDIT_ID,
        "audit_date": "2026-10-15",
        "historical_original_path": str(SOURCE),
        "historical_original_git_blob_sha1": SOURCE_GIT_BLOB,
        "historical_original_raw_sha256": hashlib.sha256(raw).hexdigest(),
        "legacy_packet_claimed_sha256": stated,
        "canonical_recomputed_without_claim_sha256": recomputed,
        "legacy_packet_sha_claim_matches_current_digest": stated == recomputed,
        "legacy_data_was_mutated": False,
        "legacy_report_facts_replaced": False,
        "legacy_report_market_price_day": "2026-10-13",
        "legacy_report_market_price_inr": packet[
            "market_source"
        ]["official_EQ_close_inr_not_current_quote"],
        "legacy_source_issuer": "DATAMATICS",
        "financial_statement_cashflow_newly_verified": False,
        "equity_target_price_approved": False,
        "issuer_return_prediction_published": False,
        "historical_research_was_outcome_blind": True,
        "original_git_blob_is_integrity_anchor_even_if_self_sha_inconsistent": True,
        "future_p049_source_use_requires_explicit_mismatch_status": True,
        "live_capital_allowed": False,
    }
    result["audit_sha256"] = digest(result)
    return result


def validate_p049_signature_audit(result: dict, root: Path) -> None:
    unsigned = dict(result)
    stated = unsigned.pop("audit_sha256", None)
    if stated != digest(unsigned):
        raise AlphaContractError("P049 new signature audit selfhash invalid")
    expected = build_p049_signature_audit(root)
    if result != expected:
        raise AlphaContractError("P049 original-source audit changed")
