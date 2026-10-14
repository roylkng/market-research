"""HG009 P009: archival custody for missing *original* NSE issuer documents.

No extracted financial numbers are promoted by this module. A fetch can
succeed but issuer/accounting-period validation still remains incomplete.
The program stores all allowed HTTP 200 bytes in content-addressed archives,
with their actual observation clock. HTTP 403/404/redirects remain failures.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from requests.exceptions import RequestException

from marketlab.alpha import AlphaContractError, digest

PROGRAM_ID = "HG009-P009-ORIGINAL-ISSUER-DOCUMENT-CUSTODY-v1"
ARCHIVE_ROOT = Path("research/hg009/p009-originals")
MAX_RAW_BYTES = 8_000_000
ALLOWED_HOST = "nsearchives.nseindia.com"
P003 = Path("research/hg009/hg009-p003-accounting-quality-redteam-v1.json")
P049 = Path("research/hg007/hg007-p049-datamatics-cash-hurdle-v1.json")
P008 = Path("registry/hg009_p008_fy26_nse_cash_facts.json")
ARCHIVE_DOCUMENTS = (
    ("MAYURUNIQ", "FY26_AUDITED_CONSOLIDATED", "html", "2026-05-20"),
    ("PIXTRANS", "Q1FY27_STANDALONE", "html", "2026-08-07"),
    ("PIXTRANS", "Q1FY26_STANDALONE", "html", "2025-08-08"),
    ("DATAMATICS", "FY26_AUDITED_CONSOLIDATED", "pdf", "2026-05-21"),
    ("POKARNA", "FY26_ORIGINAL_RESULT_PACKET", "pdf", "2026-05-28"),
)


def _load_original(path: Path, sha_field: str | None) -> dict[str, Any]:
    raw = path.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise AlphaContractError("P009 original parent document invalid")
    if sha_field:
        plain = dict(data)
        stored = plain.pop(sha_field, None)
        if stored != digest(plain):
            raise AlphaContractError("P009 original parent document hash drift")
    return data


def source_specifications(root: Path) -> list[dict[str, Any]]:
    p003 = _load_original(root / P003, "packet_sha256")
    p049 = _load_original(root / P049, "packet_sha256")
    p008 = _load_original(root / P008, None)
    if (
        p003.get("selected_case_count") != 100
        or p049.get("market_source", {}).get("symbol") != "DATAMATICS"
        or p008.get("registry_id")
        != "HG009-P008-FY26-NSE-ISSUER-FILING-FACTS-v1"
    ):
        raise AlphaContractError("P009 prior source register identity drift")
    pilots = p003["original_nse_iXBRL_manual_filing_pilots"]
    sources = {
        ("MAYURUNIQ", "FY26_AUDITED_CONSOLIDATED"): (
            pilots["MAYURUNIQ"]["source"]["source_url"],
            "INE040D01038",
        ),
        ("PIXTRANS", "Q1FY27_STANDALONE"): (
            pilots["PIXTRANS"]["source"]["current_source_url"],
            "INE751B01018",
        ),
        ("PIXTRANS", "Q1FY26_STANDALONE"): (
            pilots["PIXTRANS"]["source"]["prior_source_url"],
            "INE751B01018",
        ),
        ("DATAMATICS", "FY26_AUDITED_CONSOLIDATED"): (
            p049["source_page_refs"]["audited_exchange_fy26"]["url"],
            "INE365B01017",
        ),
        ("POKARNA", "FY26_ORIGINAL_RESULT_PACKET"): (
            p008["pokarna"]["original_url"],
            "INE637C01025",
        ),
    }
    result = []
    for symbol, period, kind, publication in ARCHIVE_DOCUMENTS:
        url, isin = sources[symbol, period]
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != ALLOWED_HOST
            or parsed.port is not None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or not parsed.path.startswith("/corporate/")
        ):
            raise AlphaContractError("P009 original issuer URL outside allowlist")
        if kind == "pdf" and not parsed.path.endswith(".pdf"):
            raise AlphaContractError("P009 original issuer PDF type mismatch")
        if kind == "html" and not parsed.path.endswith(".html"):
            raise AlphaContractError("P009 original issuer HTML type mismatch")
        result.append({
            "document_id": f"{symbol}-{period}",
            "symbol": symbol,
            "isin": isin,
            "source_url": url,
            "accounting_period": period,
            "file_type": kind,
            "original_issuer_publication_date": publication,
            "source_provenance_parent_sha256": (
                p003.get("packet_sha256")
                if symbol in ("MAYURUNIQ", "PIXTRANS")
                else p049.get("packet_sha256")
                if symbol == "DATAMATICS"
                else hashlib.sha256((root / P008).read_bytes()).hexdigest()
            ),
        })
    if len(result) != 5 or len({row["document_id"] for row in result}) != 5:
        raise AlphaContractError("P009 exact five original documents changed")
    return result


def _permitted_raw(raw: bytes, *, file_type: str) -> bool:
    if not 100 <= len(raw) <= MAX_RAW_BYTES:
        return False
    if file_type == "pdf":
        return raw.lstrip().startswith(b"%PDF-")
    lower = raw[:4096].lower()
    return (
        file_type == "html"
        and (b"<html" in lower or b"<!doctype html" in lower)
        and b"<" in raw
    )


def original_source_receipt(
    *,
    spec: dict[str, Any],
    fetch: Callable[[str], tuple[int, bytes | None]],
    recorded_at_utc: datetime,
    repo_root: Path,
) -> dict[str, Any]:
    if recorded_at_utc.tzinfo is None:
        raise AlphaContractError("P009 observation timestamp must be timezone-aware")
    recorded = recorded_at_utc.astimezone(UTC).isoformat()
    # Do not claim issuer publication was observed at its stated publication
    # date. Actual retrieval timestamp is always the current attempt.
    if recorded[:10] < spec["original_issuer_publication_date"]:
        raise AlphaContractError("P009 original document cannot be observed before filing")
    try:
        status, raw = fetch(spec["source_url"])
    except (OSError, RequestException) as exc:
        status, raw, err = None, None, type(exc).__name__
    else:
        err = None
    state = "BLOCKED_ORIGINAL_HTTP"
    source_sha = None
    archive_path = None
    if status == 200 and isinstance(raw, bytes):
        source_sha = hashlib.sha256(raw).hexdigest()
        if _permitted_raw(raw, file_type=spec["file_type"]):
            ext = ".pdf" if spec["file_type"] == "pdf" else ".html"
            target = repo_root / ARCHIVE_ROOT / spec["symbol"] / (
                source_sha + ext + ".gz"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            archive = gzip.compress(raw, mtime=0, compresslevel=9)
            if target.exists() and target.read_bytes() != archive:
                raise AlphaContractError("P009 content-addressed original collision")
            target.write_bytes(archive)
            archive_path = str(target.relative_to(repo_root))
            state = "RAW_ARCHIVED_NOT_YET_FINANCIALLY_OR_IDENTITY_VALIDATED"
        else:
            state = "BLOCKED_UNREADABLE_FORMAT_RAW_NOT_PROMOTED"
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "program_id": PROGRAM_ID,
        **spec,
        "actual_retrieved_at_utc": recorded,
        "http_status": status,
        "state": state,
        "error_class": err,
        "raw_sha256": source_sha,
        "raw_repo_path": archive_path,
        "issuer_and_period_content_verified": False,
        "cashflow_values_reconciled_to_original_bytes": False,
        "shareholder_normalized_owner_cash_verified": False,
        "issuer_equity_valuation_eligible": False,
        "live_capital_allowed": False,
    }
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def validate_original_receipt(
    receipt: dict[str, Any], *,
    root: Path,
) -> None:
    unsigned = dict(receipt)
    stored = unsigned.pop("receipt_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("P009 source receipt changed after sealing")
    if (
        receipt.get("program_id") != PROGRAM_ID
        or receipt.get("issuer_and_period_content_verified") is not False
        or receipt.get("cashflow_values_reconciled_to_original_bytes") is not False
        or receipt.get("shareholder_normalized_owner_cash_verified") is not False
        or receipt.get("issuer_equity_valuation_eligible") is not False
        or receipt.get("live_capital_allowed") is not False
    ):
        raise AlphaContractError("P009 raw bytes incorrectly promoted to valuation")
    path = receipt.get("raw_repo_path")
    if path is not None:
        archived = root / path
        if not archived.is_file() or not archived.resolve().is_relative_to(
            (root / ARCHIVE_ROOT).resolve()
        ):
            raise AlphaContractError("P009 original source archive path changed")
        raw = gzip.decompress(archived.read_bytes())
        if hashlib.sha256(raw).hexdigest() != receipt.get("raw_sha256"):
            raise AlphaContractError("P009 archived original byte hash mismatch")
        if not _permitted_raw(raw, file_type=receipt["file_type"]):
            raise AlphaContractError("P009 original format no longer valid")
