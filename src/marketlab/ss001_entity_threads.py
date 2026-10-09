from __future__ import annotations

import math
import re
from datetime import date
from typing import Any
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest

PILOT_ID = "SS001-D007-E001-P0-v1"
LISTED_ISSUER = "INOXGREEN"
SOURCE_CUTOFF = "2026-10-01"
MEMO_PATH = "research/SS001_ILLUSTRATIVE_CASE_INOXGREEN_2026_10_09.md"

EXPECTED_ENTITIES = {"INOXGREEN", "IRSL", "WWIL", "INEL"}
EXPECTED_THREADS = {
    "IRSL_SHARE_DISTRIBUTION": "IRSL",
    "WWIL_OM_ACQUISITION": "WWIL",
    "INEL_IPP_ALLOCATION": "INEL",
}

EXPECTED_DOCUMENTS = {
    "fdb71181f35222345830993fd55fd276c967dabc9b77b17016540baf0c1779a1": {
        "source_url": (
            "https://nsearchives.nseindia.com/corporate/"
            "IGESL_22072026195858_IGESL_SE_intimation_regarding_NCLT_Record_date_dsc.pdf"
        ),
        "published_on": "2026-07-22",
        "pages": (1,),
    },
    "a5beaab91414cc22fbb09594ac5a03b49b8578dd0f39ffd4fb8e680c2ae24f09": {
        "source_url": (
            "https://nsearchives.nseindia.com/corporate/"
            "IGESL_24082026202300_IGESL_SE_intimation_Allotment_IRSL_24082026.pdf"
        ),
        "published_on": "2026-08-24",
        "pages": (1,),
    },
    "d01a30043c18bb25cda5848cc16cbac1e51451683c4162f005a71c48e4521440": {
        "source_url": (
            "https://nsearchives.nseindia.com/corporate/"
            "IGESL_28072026203453_IGESL_Reg30_WWILf.pdf"
        ),
        "published_on": "2026-07-28",
        "pages": (1,),
    },
    "268bedb3a32eaa48ef5726b26a9b88f7daff3be91d6b26ee75568439f4437e43": {
        "source_url": (
            "https://nsearchives.nseindia.com/corporate/"
            "IGESL_03082026201643_IGESL_Reg30_WWIL_CTC2026_dsc.pdf"
        ),
        "published_on": "2026-08-03",
        "pages": (1, 3, 4),
    },
}

FAMILIES = {
    "SCHEME_SHARE_ENTITLEMENT",
    "OPERATING_ASSET_ACQUISITION",
    "OTHER_GROUP_ASSET_ALLOCATION",
}
STAGES = {
    "PROPOSED",
    "COURT_OR_REGULATOR_APPROVED_PENDING_EXECUTION",
    "RECORD_DATE_FIXED",
    "SECURITIES_ALLOTTED_BY_SUBJECT_ENTITY",
    "EXECUTED_AND_CLOSED",
    "CANCELLED",
    "UNKNOWN",
}
SECURITY_EFFECTS = {
    "OTHER_ENTITY_SHARES",
    "NO_ISSUER_CHANGE_EVIDENCED",
    "DIRECT_ISSUER_CHANGE_REQUIRES_CAPITAL_RECONCILIATION",
    "UNRESOLVED",
}
QUALIFIERS = {
    "EXPLICIT_FINAL",
    "PROVISIONAL_UNAUDITED",
    "UPPER_BOUND_PROPOSED",
    "EXPECTED_NOT_COMPLETED",
    "CONDITIONAL_ORAL_APPROVAL",
    "DESCRIPTIVE",
}
UNITS = {
    "ISO_DATE",
    "SHARES",
    "RATIO_TEXT",
    "INR_CRORE",
    "GW",
    "MW",
    "TEXT",
}
CLOSED_FIELDS = (
    "full_d007_l002_coverage",
    "semantic_audit_complete",
    "share_action_clearance_proven",
    "market_capitalization_calculated",
    "expected_return_calculated",
    "portfolio_eligibility_allowed",
    "live_capital_allowed",
    "return_outcomes_opened",
)
_HEX64 = re.compile(r"^[a-f0-9]{64}$")


def _dict(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AlphaContractError(f"E001 {label} must be an object")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise AlphaContractError(f"E001 {label} must be an array")
    return value


def _date(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise AlphaContractError(f"E001 {label} must be ISO YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise AlphaContractError(f"E001 invalid {label}") from exc
    if parsed.isoformat() != value:
        raise AlphaContractError(f"E001 {label} is noncanonical")
    return value


def _source_segments(doc_id: str, pages: tuple[int, ...]) -> set[str]:
    return {f"{doc_id}:pdf:page:{page:04d}" for page in pages}


def _validate_documents(raw_documents: object) -> dict[str, set[str]]:
    documents = _list(raw_documents, "documents")
    observed: dict[str, set[str]] = {}
    for document in documents:
        row = _dict(document, "document")
        if set(row) != {"document_id", "source_url", "published_on", "segment_ids"}:
            raise AlphaContractError("E001 unexpected source document fields")
        doc_id = row.get("document_id")
        if not isinstance(doc_id, str) or not _HEX64.fullmatch(doc_id):
            raise AlphaContractError("E001 invalid document SHA identity")
        if doc_id in observed:
            raise AlphaContractError("E001 duplicate document identity")
        expected = EXPECTED_DOCUMENTS.get(doc_id)
        if expected is None:
            raise AlphaContractError("E001 unregistered source document")
        if row.get("source_url") != expected["source_url"]:
            raise AlphaContractError("E001 official document URL mismatch")
        parsed = urlparse(row["source_url"])
        if parsed.scheme != "https" or parsed.hostname != "nsearchives.nseindia.com":
            raise AlphaContractError("E001 source must be official HTTPS NSE archive")
        published_on = _date(row.get("published_on"), "document published_on")
        if published_on != expected["published_on"] or published_on > SOURCE_CUTOFF:
            raise AlphaContractError("E001 document publication is not frozen")
        allowed = _source_segments(doc_id, expected["pages"])
        segments = _list(row.get("segment_ids"), "document segment_ids")
        if set(segments) != allowed or len(segments) != len(allowed):
            raise AlphaContractError("E001 document page evidence differs from memo")
        observed[doc_id] = allowed
    if set(observed) != set(EXPECTED_DOCUMENTS):
        raise AlphaContractError("E001 missing required official document")
    return observed


def _validate_entities(raw_entities: object) -> None:
    entities = _list(raw_entities, "entities")
    identifiers: set[str] = set()
    listed_count = 0
    for item in entities:
        row = _dict(item, "entity")
        if set(row) != {"entity_id", "legal_name", "is_listed_issuer"}:
            raise AlphaContractError("E001 unexpected entity fields")
        entity_id = row.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id:
            raise AlphaContractError("E001 entity_id must be nonempty")
        if entity_id in identifiers:
            raise AlphaContractError("E001 duplicate entity_id")
        identifiers.add(entity_id)
        if not isinstance(row.get("legal_name"), str) or not row["legal_name"]:
            raise AlphaContractError("E001 entity legal_name missing")
        listed = row.get("is_listed_issuer")
        if not isinstance(listed, bool):
            raise AlphaContractError("E001 entity listed-issuer flag must be boolean")
        if listed:
            listed_count += 1
            if entity_id != LISTED_ISSUER:
                raise AlphaContractError("E001 other entity cannot be listed issuer")
        if entity_id == LISTED_ISSUER and not listed:
            raise AlphaContractError("E001 anchor issuer not declared listed")
    if identifiers != EXPECTED_ENTITIES or listed_count != 1:
        raise AlphaContractError("E001 entity boundary differs from frozen case")


def _validate_fact(
    raw_fact: object,
    *,
    thread_id: str,
    subject_entity_id: str,
    allowed_segments: dict[str, set[str]],
) -> tuple[str, object, str]:
    row = _dict(raw_fact, f"fact in {thread_id}")
    if set(row) != {
        "field", "subject_entity_id", "value", "unit", "qualifier", "evidence"
    }:
        raise AlphaContractError("E001 fact has unexpected or missing keys")
    field = row.get("field")
    if not isinstance(field, str) or not field or not field.replace("_", "").isalnum():
        raise AlphaContractError("E001 fact field must be a simple identifier")
    if row.get("subject_entity_id") != subject_entity_id:
        raise AlphaContractError("E001 cross-entity fact attributed to wrong thread")
    unit, qualifier, value = row.get("unit"), row.get("qualifier"), row.get("value")
    if unit not in UNITS or qualifier not in QUALIFIERS:
        raise AlphaContractError("E001 unsupported fact unit or qualifier")
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise AlphaContractError("E001 fact must have explicit text or number")
    if isinstance(value, str) and not value.strip():
        raise AlphaContractError("E001 explicit fact text is blank")
    if isinstance(value, float) and not math.isfinite(value):
        raise AlphaContractError("E001 fact number is nonfinite")
    if unit == "ISO_DATE":
        _date(value, f"fact {field} date")
        if value > SOURCE_CUTOFF and qualifier != "EXPECTED_NOT_COMPLETED":
            raise AlphaContractError("E001 future date cannot be an observed outcome")
    elif unit == "SHARES":
        if not isinstance(value, int) or value < 0:
            raise AlphaContractError("E001 share count must be nonnegative integer")
    elif unit in {"INR_CRORE", "GW", "MW"}:
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise AlphaContractError("E001 numeric financial/capacity term required")
    elif not isinstance(value, str):
        raise AlphaContractError("E001 textual/ratio unit requires text value")
    if field.startswith("proposed_") and qualifier not in {
        "UPPER_BOUND_PROPOSED", "EXPECTED_NOT_COMPLETED"
    }:
        raise AlphaContractError("E001 proposal cannot become definitive by relabeling")
    evidence = _list(row.get("evidence"), f"fact {field} evidence")
    if not evidence:
        raise AlphaContractError("E001 every explicit fact needs source evidence")
    seen: set[tuple[str, str]] = set()
    for ref in evidence:
        item = _dict(ref, "fact source")
        if set(item) != {"document_id", "segment_id"}:
            raise AlphaContractError("E001 source reference fields differ")
        doc_id, segment_id = item.get("document_id"), item.get("segment_id")
        if doc_id not in allowed_segments or segment_id not in allowed_segments[doc_id]:
            raise AlphaContractError("E001 unsupported document page evidence")
        identity = (doc_id, segment_id)
        if identity in seen:
            raise AlphaContractError("E001 duplicate fact source evidence")
        seen.add(identity)
    return field, value, unit


def validate_entity_thread_pilot(payload: dict[str, Any]) -> dict[str, Any]:
    pack = _dict(payload, "pack")
    required_top_keys = {
        "schema_version", "pilot_id", "issuer_symbol", "source_cutoff_date",
        "source_memo_path", "entities", "documents", "threads", *CLOSED_FIELDS,
    }
    if set(pack) != required_top_keys or pack.get("schema_version") != 1:
        raise AlphaContractError("E001 top-level schema differs from frozen contract")
    if pack.get("pilot_id") != PILOT_ID:
        raise AlphaContractError("E001 pilot identity mismatch")
    if pack.get("issuer_symbol") != LISTED_ISSUER:
        raise AlphaContractError("E001 listed issuer identity mismatch")
    if pack.get("source_memo_path") != MEMO_PATH:
        raise AlphaContractError("E001 audited memo path mismatch")
    if _date(pack.get("source_cutoff_date"), "cutoff") != SOURCE_CUTOFF:
        raise AlphaContractError("E001 source cutoff mismatch")
    for field in CLOSED_FIELDS:
        if pack.get(field) is not False:
            raise AlphaContractError(f"E001 {field} must remain false")

    allowed_segments = _validate_documents(pack.get("documents"))
    _validate_entities(pack.get("entities"))
    threads = _list(pack.get("threads"), "threads")
    seen: set[str] = set()
    total_facts = 0
    for raw_thread in threads:
        thread = _dict(raw_thread, "thread")
        if set(thread) != {
            "thread_id", "economic_family", "transaction_stage",
            "subject_entity_id", "security_issuer_entity_id", "issuer_security_effect",
            "facts", "unresolved_questions",
        }:
            raise AlphaContractError("E001 thread schema differs from contract")
        thread_id, subject = thread.get("thread_id"), thread.get("subject_entity_id")
        if thread_id in seen or thread_id not in EXPECTED_THREADS:
            raise AlphaContractError("E001 thread must have unique frozen ID")
        seen.add(thread_id)
        if subject != EXPECTED_THREADS[thread_id]:
            raise AlphaContractError("E001 thread subject differs from frozen legal entity")
        if thread.get("economic_family") not in FAMILIES:
            raise AlphaContractError("E001 thread economic family unavailable")
        if thread.get("transaction_stage") not in STAGES:
            raise AlphaContractError("E001 transaction stage unsupported")
        effect = thread.get("issuer_security_effect")
        if effect not in SECURITY_EFFECTS:
            raise AlphaContractError("E001 listed issuer security-effect state unsupported")
        securities_issuer = thread.get("security_issuer_entity_id")
        if securities_issuer is not None and securities_issuer not in EXPECTED_ENTITIES:
            raise AlphaContractError("E001 unknown security issuer")
        if effect == "OTHER_ENTITY_SHARES" and (
            securities_issuer in {None, LISTED_ISSUER}
            or securities_issuer != subject
        ):
            raise AlphaContractError("E001 other-entity shares misattributed to listed issuer")
        if (
            effect == "DIRECT_ISSUER_CHANGE_REQUIRES_CAPITAL_RECONCILIATION"
            and securities_issuer != LISTED_ISSUER
        ):
            raise AlphaContractError("E001 direct share-change issuer is incorrect")
        if securities_issuer is None and effect in {
            "OTHER_ENTITY_SHARES", "DIRECT_ISSUER_CHANGE_REQUIRES_CAPITAL_RECONCILIATION"
        }:
            raise AlphaContractError("E001 share effect requires explicit security issuer")

        facts = _list(thread.get("facts"), f"{thread_id} facts")
        if not facts:
            raise AlphaContractError("E001 transaction thread has no evidence facts")
        fact_index: dict[str, tuple[object, str]] = {}
        for fact in facts:
            field, value, unit = _validate_fact(
                fact, thread_id=thread_id, subject_entity_id=subject,
                allowed_segments=allowed_segments,
            )
            if field in fact_index:
                raise AlphaContractError("E001 duplicate thread fact field")
            fact_index[field] = (value, unit)
        total_facts += len(facts)
        if (
            thread.get("transaction_stage") == "SECURITIES_ALLOTTED_BY_SUBJECT_ENTITY"
            and (
                securities_issuer != subject
                or not any(unit == "SHARES" for _, unit in fact_index.values())
            )
        ):
            raise AlphaContractError("E001 allotment must identify actual security issuer")
        if (
            thread.get("transaction_stage") == "EXECUTED_AND_CLOSED"
            and (
                "closing_date" not in fact_index
                or fact_index["closing_date"][1] != "ISO_DATE"
            )
        ):
            raise AlphaContractError("E001 executed stage needs disclosed closing date")
        questions = _list(thread.get("unresolved_questions"), "unresolved_questions")
        if not questions or not all(isinstance(q, str) and q.strip() for q in questions):
            raise AlphaContractError("E001 case must retain material unresolved questions")

    if seen != set(EXPECTED_THREADS):
        raise AlphaContractError("E001 all three legally distinct threads are required")

    # Source binding is mechanical, not independent semantic verification.
    result = {
        "schema_version": 1,
        "protocol_id": PILOT_ID,
        "classification": "ILLUSTRATIVE_ENTITY_BOUND_SOURCE_STRUCTURE_NOT_SHARE_CLEARANCE",
        "issuer_symbol": LISTED_ISSUER,
        "source_cutoff_date": SOURCE_CUTOFF,
        "source_pack_sha256": digest(payload),
        "document_count": len(allowed_segments),
        "entity_count": len(EXPECTED_ENTITIES),
        "thread_count": len(threads),
        "explicit_fact_count": total_facts,
        "structural_validation_pass": True,
        "source_text_independently_reverified_by_validator": False,
        "full_d007_l002_coverage": False,
        "semantic_audit_complete": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "expected_return_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
        "return_outcomes_opened": False,
    }
    result["result_sha256"] = digest(result)
    return result
