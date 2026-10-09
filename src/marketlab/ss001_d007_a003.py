from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss001_l001_batch import SOURCE_QUEUE_SHA

LEDGER_ID = "SS001-D007-A003-v1"
A002_AUDIT_ID = "SS001-D007-A002-v1"
EXPECTED_SELECTION_SHA = "79e106f1d0b27810d06bd1c9e1bd192b967ef185393690ba0608354a698bbe86"
SELECTED_PAGE_COUNT = 229
SELECTED_DOCUMENT_COUNT = 70
SELECTED_ISSUER_COUNT = 12

FINDING_CATEGORIES = frozenset(
    {
        "UNSUPPORTED_EXPLICIT_CLAIM",
        "OMITTED_MATERIAL_TERM",
        "ENTITY_CONFUSION",
        "STAGE_MISCLASSIFICATION",
        "CONTRADICTORY_TERMS",
        "SOURCE_PAGE_UNREADABLE",
        "OTHER",
    }
)
FINDING_SEVERITIES = frozenset({"CRITICAL", "MATERIAL", "MINOR", "INFO"})
FORBIDDEN_TRUE = (
    "independent_semantic_audit_complete",
    "share_action_clearance_proven",
    "market_capitalization_calculated",
    "return_outcomes_opened",
    "portfolio_eligibility_allowed",
    "live_capital_allowed",
)


def _require_closed(payload: dict[str, Any], label: str) -> None:
    for field in FORBIDDEN_TRUE:
        if payload.get(field) is not False:
            raise AlphaContractError(f"A003 {label} requires {field}=false")


def _normalized_text(value: str) -> str:
    return " ".join(value.split())


def _verify_packet(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if packet.get("schema_version") != 1 or packet.get("audit_id") != A002_AUDIT_ID:
        raise AlphaContractError("A003 requires an A002 review packet")
    if packet.get("classification") != "INDEPENDENT_REVIEW_WORK_PACKET_NOT_AUDIT_VERDICT":
        raise AlphaContractError("A003 packet classification is invalid")
    if packet.get("source_queue_sha256") != SOURCE_QUEUE_SHA:
        raise AlphaContractError("A003 queue SHA mismatch")
    if packet.get("selection_sha256") != EXPECTED_SELECTION_SHA:
        raise AlphaContractError("A003 frozen selection SHA mismatch")
    if packet.get("selected_page_count") != SELECTED_PAGE_COUNT:
        raise AlphaContractError("A003 selected page count changed")
    if not isinstance(packet.get("packet_sha256"), str):
        raise AlphaContractError("A003 packet SHA unavailable")
    original = {key: value for key, value in packet.items() if key != "packet_sha256"}
    if digest(original) != packet["packet_sha256"]:
        raise AlphaContractError("A003 review packet content SHA mismatch")
    _require_closed(packet, "source packet")

    rows = packet.get("rows")
    if not isinstance(rows, list) or len(rows) != SELECTED_PAGE_COUNT:
        raise AlphaContractError("A003 source packet selected rows unavailable")
    indexed: dict[str, dict[str, Any]] = {}
    documents: set[str] = set()
    issuers: set[str] = set()
    missing = 0
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("A003 source page row must be an object")
        request_id = row.get("request_id")
        document_id = row.get("document_id")
        symbol = row.get("symbol")
        segment_id = row.get("segment_id")
        text = row.get("source_page_text")
        if not all(isinstance(value, str) and value for value in (
            request_id, document_id, symbol, segment_id,
        )):
            raise AlphaContractError("A003 source page identity is incomplete")
        if request_id in indexed:
            raise AlphaContractError("A003 duplicate source request ID")
        if not isinstance(text, str):
            raise AlphaContractError("A003 source page text missing")
        observed_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if row.get("source_page_text_sha256") != observed_sha:
            raise AlphaContractError("A003 source page text SHA mismatch")

        response_status = row.get("response_status")
        extraction_sha = row.get("validated_extraction_sha256")
        if response_status == "MISSING_INFERENCE":
            missing += 1
            if extraction_sha is not None:
                raise AlphaContractError("A003 missing inference cannot have extraction SHA")
        elif response_status == "PENDING_INDEPENDENT_REVIEW":
            if not isinstance(extraction_sha, str) or len(extraction_sha) != 64:
                raise AlphaContractError("A003 source extraction SHA unavailable")
        else:
            raise AlphaContractError("A003 unsupported source response status")
        indexed[request_id] = row
        documents.add(document_id)
        issuers.add(symbol)

    if len(documents) != SELECTED_DOCUMENT_COUNT or len(issuers) != SELECTED_ISSUER_COUNT:
        raise AlphaContractError("A003 frozen document/issuer coverage mismatch")
    if packet.get("pending_selected_response_count") != missing:
        raise AlphaContractError("A003 pending inference count mismatch")
    if packet.get("selected_model_response_count") != SELECTED_PAGE_COUNT - missing:
        raise AlphaContractError("A003 validated response count mismatch")
    if packet.get("response_coverage_complete") is not (missing == 0):
        raise AlphaContractError("A003 response completeness flag mismatch")
    return indexed


def _review_time(value: object) -> str:
    if not isinstance(value, str):
        raise AlphaContractError("A003 review timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise AlphaContractError("A003 review timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise AlphaContractError("A003 review timestamp must be timezone-aware")
    return parsed.isoformat()


def _validate_finding(finding: Any, *, row: dict[str, Any]) -> None:
    if not isinstance(finding, dict):
        raise TypeError("A003 finding must be an object")
    required = {
        "category",
        "severity",
        "segment_id",
        "source_excerpt",
        "explanation",
        "field_path",
    }
    if set(finding) != required:
        raise AlphaContractError("A003 finding keys differ from contract")
    if finding.get("category") not in FINDING_CATEGORIES:
        raise AlphaContractError("A003 unknown finding category")
    if finding.get("severity") not in FINDING_SEVERITIES:
        raise AlphaContractError("A003 unknown finding severity")
    if finding.get("segment_id") != row["segment_id"]:
        raise AlphaContractError("A003 finding segment ID mismatch")
    excerpt = finding.get("source_excerpt")
    if not isinstance(excerpt, str) or len(excerpt) > 1000:
        raise AlphaContractError("A003 finding source excerpt invalid")
    if not excerpt.strip():
        if finding["category"] != "SOURCE_PAGE_UNREADABLE":
            raise AlphaContractError("A003 finding requires literal source excerpt")
    elif _normalized_text(excerpt) not in _normalized_text(row["source_page_text"]):
        raise AlphaContractError("A003 finding excerpt not found in frozen page")
    explanation = finding.get("explanation")
    if not isinstance(explanation, str) or len(explanation.strip()) < 10:
        raise AlphaContractError("A003 finding explanation too short")
    field_path = finding.get("field_path")
    if field_path is not None and (
        not isinstance(field_path, str) or not field_path.strip()
    ):
        raise AlphaContractError("A003 finding fact field path invalid")


def build_independent_review_ledger(
    packet: dict[str, Any],
    annotations: dict[str, Any],
) -> dict[str, Any]:
    indexed = _verify_packet(packet)
    if annotations.get("schema_version") != 1 or annotations.get("audit_id") != LEDGER_ID:
        raise AlphaContractError("A003 annotation contract identity mismatch")
    if annotations.get("source_packet_sha256") != packet["packet_sha256"]:
        raise AlphaContractError("A003 annotation source packet SHA mismatch")
    reviews = annotations.get("reviews")
    if not isinstance(reviews, list):
        raise TypeError("A003 review annotations must be a list")

    by_request: dict[str, dict[str, Any]] = {}
    category_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    for review in reviews:
        if not isinstance(review, dict):
            raise TypeError("A003 review record must be an object")
        required = {
            "request_id",
            "reviewer_id",
            "reviewer_attests_independence",
            "reviewed_at_utc",
            "source_page_text_sha256",
            "validated_extraction_sha256",
            "verdict",
            "findings",
        }
        if set(review) != required:
            raise AlphaContractError("A003 review record keys differ from contract")
        request_id = review.get("request_id")
        if not isinstance(request_id, str) or request_id not in indexed:
            raise AlphaContractError("A003 unknown review request ID")
        if request_id in by_request:
            raise AlphaContractError("A003 duplicate review request ID")
        row = indexed[request_id]
        if row["response_status"] != "PENDING_INDEPENDENT_REVIEW":
            raise AlphaContractError("A003 cannot review missing inference")
        reviewer_id = review.get("reviewer_id")
        if not isinstance(reviewer_id, str) or len(reviewer_id.strip()) < 3:
            raise AlphaContractError("A003 reviewer identifier missing")
        if review.get("reviewer_attests_independence") is not True:
            raise AlphaContractError("A003 independent reviewer attestation missing")
        _review_time(review.get("reviewed_at_utc"))
        if review.get("source_page_text_sha256") != row["source_page_text_sha256"]:
            raise AlphaContractError("A003 review page SHA mismatch")
        if review.get("validated_extraction_sha256") != row["validated_extraction_sha256"]:
            raise AlphaContractError("A003 review extraction SHA mismatch")
        verdict = review.get("verdict")
        findings = review.get("findings")
        if verdict not in {"PASS", "ISSUES_FOUND"}:
            raise AlphaContractError("A003 review verdict is invalid")
        if not isinstance(findings, list):
            raise TypeError("A003 review findings must be a list")
        if verdict == "PASS" and findings:
            raise AlphaContractError("A003 PASS cannot carry findings")
        if verdict == "ISSUES_FOUND" and not findings:
            raise AlphaContractError("A003 failure must record a finding")
        for finding in findings:
            _validate_finding(finding, row=row)
            category_counts[finding["category"]] += 1
            severity_counts[finding["severity"]] += 1
        by_request[request_id] = review

    missing_inference = packet["pending_selected_response_count"]
    unreviewed_available = (
        packet["selected_model_response_count"] - len(by_request)
    )
    failed_pages = sum(review["verdict"] == "ISSUES_FOUND" for review in reviews)
    passed_pages = len(reviews) - failed_pages

    if missing_inference:
        state = "SOURCE_INFERENCE_MISSING"
    elif unreviewed_available:
        state = "REVIEW_INCOMPLETE"
    elif failed_pages:
        state = "ISSUES_RECORDED_REMEDIATION_REQUIRED"
    else:
        state = "REVIEWER_RECORDED_PASS_PENDING_INDEPENDENCE_VERIFICATION"

    rows = []
    for row in packet["rows"]:
        review = by_request.get(row["request_id"])
        rows.append({
            "request_id": row["request_id"],
            "document_id": row["document_id"],
            "symbol": row["symbol"],
            "segment_id": row["segment_id"],
            "source_page_text_sha256": row["source_page_text_sha256"],
            "validated_extraction_sha256": row["validated_extraction_sha256"],
            "review_status": (
                "MISSING_INFERENCE"
                if row["response_status"] == "MISSING_INFERENCE"
                else ("REVIEWED" if review is not None else "NOT_REVIEWED")
            ),
            "review_verdict": review["verdict"] if review is not None else None,
            "reviewer_id": review["reviewer_id"] if review is not None else None,
            "review_record_sha256": digest(review) if review is not None else None,
            "finding_count": len(review["findings"]) if review is not None else 0,
        })

    output = {
        "schema_version": 1,
        "ledger_id": LEDGER_ID,
        "classification": "REVIEWER_ATTESTATION_LEDGER_NOT_SEMANTIC_CERTIFICATE",
        "source_queue_sha256": SOURCE_QUEUE_SHA,
        "source_selection_sha256": EXPECTED_SELECTION_SHA,
        "source_packet_sha256": packet["packet_sha256"],
        "selected_page_count": SELECTED_PAGE_COUNT,
        "available_inference_page_count": packet["selected_model_response_count"],
        "missing_inference_page_count": missing_inference,
        "reviewed_page_count": len(reviews),
        "passed_page_count": passed_pages,
        "issues_found_page_count": failed_pages,
        "unreviewed_available_page_count": unreviewed_available,
        "finding_category_counts": dict(sorted(category_counts.items())),
        "finding_severity_counts": dict(sorted(severity_counts.items())),
        "reviewer_recorded_status": state,
        "reviewer_recorded_sample_complete": (
            missing_inference == 0 and unreviewed_available == 0 and failed_pages == 0
        ),
        "human_independence_verified_by_code": False,
        "rows": rows,
        "review_annotations_sha256": digest(annotations),
        "independent_semantic_audit_complete": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["ledger_sha256"] = digest(output)
    return output
