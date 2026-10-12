"""Reconcile frozen H021 dividend warning with later original NSE document custody.

The Oct 8 dividend was first published *before* H021's Oct 12 open.
Its exact original PDF bytes were captured only afterward. Preserve
both timelines; do not overwrite the original P011 research alert,
change original H021 selections, infer cash receipts, or open returns.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from marketlab.h021_entry_observation import EXPECTED_SELECTION
from marketlab.h021_first_entry_intent import git_blob_sha
from scripts.acquire_h021_vedl_dividend_original import (
    SOURCE_ID,
    verify_original_dividend_pdf,
    verify_receipt,
)

RECONCILIATION_ID = "H021-P013-ORIGINAL-VEDL-DIVIDEND-RISK-DELTA-v1"
P011_PATH = Path(
    "research/prospective/h021/pre-entry-risk/2026-10-09-vedl-dividend-alert-v1.json"
)
P011_BLOB_SHA = "968ade0e2275107b0e5ab760ba111110497224a6"
P012_PATH = Path(
    "research/prospective/h021/dividend-evidence/vedl-2026-10-08/source-receipt-v1.json"
)
P012_BLOB_SHA = "de2d9889ec303067404ba62c136cd221288ac0ad"
P012_PDF_SHA = "abdd026339469b9e51ab75fb2a37551be23812dcc037c875759cd79a8e6cb364"
P012_PDF_RELATIVE = Path(
    "research/prospective/h021/dividend-evidence/vedl-2026-10-08/original/sha256"
) / f"{P012_PDF_SHA}.pdf"
P003_PATH = Path("research/prospective/h021/intents/2026-10-09-primary-entry-intent-v1.json")
P003_BLOB_SHA = "e25f77e1c845456473e624899d4748e306b1225b"


def _pinned_json(root: Path, path: Path, sha: str) -> dict[str, Any]:
    raw = (root / path).read_bytes()
    if git_blob_sha(raw) != sha:
        raise ValueError(f"frozen H021 source content Git blob mismatch: {path}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TypeError(f"frozen H021 source must be an object: {path}")
    return value


def load_original_sources(root: Path) -> tuple[dict, dict, dict, dict]:
    risk = _pinned_json(root, P011_PATH, P011_BLOB_SHA)
    receipt = _pinned_json(root, P012_PATH, P012_BLOB_SHA)
    intent = _pinned_json(root, P003_PATH, P003_BLOB_SHA)
    pdf = (root / P012_PDF_RELATIVE).read_bytes()
    if hashlib.sha256(pdf).hexdigest() != P012_PDF_SHA:
        raise ValueError("original VEDL PDF bytes changed from sealed source")
    verify_receipt(receipt, pdf)
    if verify_original_dividend_pdf(pdf) != receipt["issuer_reported_dividend_terms"]:
        raise ValueError("original issuer dividend statement no longer reproduces")
    provenance = {
        "frozen_p011_secondary_risk_git_blob": P011_BLOB_SHA,
        "original_p012_dividend_receipt_git_blob": P012_BLOB_SHA,
        "original_p012_pdf_sha256": P012_PDF_SHA,
        "frozen_p003_entry_intent_git_blob": P003_BLOB_SHA,
    }
    return risk, receipt, intent, provenance


def build_vedl_source_delta(
    risk: dict[str, Any],
    receipt: dict[str, Any],
    intent: dict[str, Any],
    provenance: dict,
) -> dict[str, Any]:
    if (
        risk.get("risk_id") != "H021-P011-FIRST-ENTRY-KNOWN-DIVIDEND-BOUNDARY-v1"
        or risk.get("source_selection_date_ist") != "2026-10-09"
        or risk.get("stock_total_return_basis_approved") is not False
        or risk.get("original_exchange_filing_pdfs_verified_for_dividends") is not False
        or risk.get("portfolio_eligibility_allowed") is not False
    ):
        raise ValueError("P011 original pre-entry source-risk contract changed")
    if intent.get("intent_id") != "H021-P003-2026-10-09-FIRST-COHORT-v1":
        raise ValueError("frozen H021 entry intention changed")
    members = intent.get("selected_observations")
    if (
        not isinstance(members, list)
        or tuple(item.get("symbol") for item in members) != EXPECTED_SELECTION
        or intent.get("live_capital_allowed") is not False
        or intent.get("no_position_orders_created") is not True
    ):
        raise ValueError("original H021 ten selected identities/order or capital changed")
    if (
        risk.get("frozen_selected_symbols") != list(EXPECTED_SELECTION)
        or risk.get("planned_observation_entry_session") != "2026-10-12"
        or risk.get("original_h021_selection_unchanged") is not True
    ):
        raise ValueError("frozen H021 P011 holdings/intention unexpectedly changed")
    rows = risk.get("source_risk_rows")
    if not isinstance(rows, list) or len(rows) != len(EXPECTED_SELECTION):
        raise ValueError("original pre-entry measurement hazards are incomplete")
    if [row.get("symbol") for row in rows] != list(EXPECTED_SELECTION):
        raise ValueError("VEDL corporate-action alert does not preserve cohort order")
    if sum(row.get("known_preentry_dividend_event") is not None for row in rows) != 1:
        raise ValueError("frozen source alert must have exactly one VEDL cash event")
    event = rows[0].get("known_preentry_dividend_event")
    if (
        not isinstance(event, dict)
        or event.get("symbol") != "VEDL"
        or event.get("issuer_reported_per_share_inr") != 5.0
        or event.get("reported_record_date_ist") != "2026-10-14"
        or event.get("reported_ex_date_ist") != "2026-10-14"
        or event.get("cash_payment_and_shareholder_entitlement_verified") is not False
        or risk.get("actual_dividend_entitlement_calculated") is not False
    ):
        raise ValueError("original secondary dividend risk differs from sealed declaration")

    if (
        receipt.get("source_id") != SOURCE_ID
        or receipt.get("state") != (
            "OFFICIAL_PDF_BYTES_AND_ISSUER_TEXT_CAPTURED_NOT_ENTITLEMENT_AUDITED"
        )
        or receipt.get("original_pdf_sha256") != P012_PDF_SHA
        or receipt.get("original_pdf_size") != 464755
        or receipt.get("return_outcomes_opened") is not False
        or receipt.get("portfolio_eligibility_allowed") is not False
        or receipt.get("live_capital_allowed") is not False
    ):
        raise ValueError("only successful source-only P012 original VEDL PDF is admissible")
    facts = receipt.get("issuer_reported_dividend_terms")
    first_seen = receipt.get("first_original_announcement_provenance")
    if not isinstance(facts, dict) or not isinstance(first_seen, dict):
        raise TypeError("NSE VEDL original facts and first-seen metadata required")
    if (
        facts.get("issuer_reported_dividend_per_share_inr") != 5.0
        or facts.get("issuer_reported_record_date_ist") != "2026-10-14"
        or facts.get("issuer_reported_board_declaration_date") != "2026-10-08"
        or facts.get("issuer_reported_board_approval_time_ist") != "13:00"
        or facts.get("ex_date_confirmed_by_this_pdf") is not False
        or first_seen.get("source_was_public_before_oct12_planned_entry") is not True
        or first_seen.get("source_public_broadcast_at_utc") != "2026-10-08T07:41:56Z"
    ):
        raise ValueError("source-verified issuer VEDL terms contradict frozen risk")

    updated_rows = deepcopy(rows)
    updated_rows[0]["new_original_pdf_declaration_evidence"] = {
        "source_authority": "EXACT_NSE_ORIGINAL_PDF_AND_ARCHIVED_PREENTRY_FIRST_SEEN",
        "original_pdf_sha256": P012_PDF_SHA,
        "source_announcement_publication_utc": first_seen[
            "source_public_broadcast_at_utc"
        ],
        "actual_pdf_retrieval_utc": receipt["original_pdf_fetched_at_utc"],
        "original_pdf_declared_cash_per_share_inr": 5.0,
        "original_pdf_issuer_record_date_ist": "2026-10-14",
        "dividend_declaration_and_record_date_source_verified": True,
        "ex_date_independently_verified_by_this_board_pdf": False,
        "actual_paper_trade_fill_or_entitlement_verified": False,
        "dividend_paid_or_cash_received_verified": False,
        "total_return_basis_verified": False,
    }

    result: dict[str, Any] = {
        "schema_version": 1,
        "evidence_delta_id": RECONCILIATION_ID,
        "classification": (
            "ADDITIVE_POST_ENTRY_ORIGINAL_SOURCE_REVIEW_NOT_PREENTRY_REWRITE_OR_RETURN"
        ),
        "source_provenance": provenance,
        "original_p011_risk_alert_unchanged": True,
        "original_p003_selected_names_unchanged": True,
        "frozen_selected_count": 10,
        "frozen_symbols": list(EXPECTED_SELECTION),
        "dividend_declaration_original_source_confirmed_count": 1,
        "source_verified_dividend_symbols": ["VEDL"],
        "source_issuer_fact_scope": "VEDL_5INR_DECLARATION_OCT14_RECORD_DATE_ONLY",
        "remaining_nine_companies_whole_horizon_actions_not_audited": True,
        "VEDL_ex_date_original_exchange_action_census_complete": False,
        "cash_entitlement_and_payment_calculated": False,
        "actual_entry_trade_filled": False,
        "nifty500_price_to_total_return_basis_reconciled": False,
        "november8_muhurat_session_resolved": False,
        "official_2027_calendar_verified": False,
        "twenty_or_sixty_session_returns_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
        "source_risk_rows_with_additive_p012_evidence": updated_rows,
    }
    return result


def require_total_return_permission(report: dict[str, Any]) -> None:
    if report.get("evidence_delta_id") != RECONCILIATION_ID:
        raise ValueError("unrecognized H021 first-cohort dividend measurement source")
    raise ValueError(
        "Original issuer dividend/record-date evidence is not a complete "
        "trade entitlement, ex-date, corporate action or TRI return audit"
    )
