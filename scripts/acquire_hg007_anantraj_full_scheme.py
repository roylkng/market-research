"""Capture the exact official 48-page ANANTRAJ/Ashok Cloud composite scheme.

Only company-hosted link *actually discovered in immutable official
investor HTML* is eligible. Preserve complete original bytes/sha/page
provenance, not current scheme legal effectiveness or asset valuation.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import requests
from pypdf import PdfReader
from pypdf.errors import PdfReadError

SOURCE_ID = "HG007-P024-ANANTRAJ-AUG2026-FULL-SCHEME-ORIGINAL-PDF-v1"
PROBE_MANIFEST = Path(
    "research/hg007/anantraj-full-scheme-discovery/attempts/"
    "38111955811-1/discovery-v1.json"
)
PROBE_MANIFEST_BLOB = "4dd5950773d136b23e2ecc3af2d40e56a5527dc4"
EXACT_DISCOVERED_SOURCE = (
    "https://blob.anantrajlimited.com/anantraj/"
    "1785759469838-Composite Scheme of Arrangement.pdf"
)
EXACT_TRANSPORT_SOURCE = (
    "https://blob.anantrajlimited.com/anantraj/"
    "1785759469838-Composite%20Scheme%20of%20Arrangement.pdf"
)
EXPECTED_SCHEME_PAGE_COUNT = 48
MAX_PDF_BYTES = 65_000_000
SOURCE_STATES = frozenset({
    "OFFICIAL_ISSUER_SCHEME_PDF_BYTES_IDENTITY_VERIFIED_NOT_LEGALLY_APPROVED",
    "OFFICIAL_ORIGINAL_PDF_ACCESS_BLOCKED",
    "ORIGINAL_PDF_NOT_AVAILABLE",
    "ORIGINAL_PDF_REDIRECT_UNFOLLOWED",
    "ORIGINAL_PDF_INVALID_ENVELOPE_OR_ISSUER",
    "ORIGINAL_PDF_HTTP_OR_TRANSPORT_FAILURE",
})


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _validate_pdf_location(candidate: str) -> bool:
    if not isinstance(candidate, str):
        return False
    try:
        actual = urlsplit(candidate)
        original = urlsplit(EXACT_DISCOVERED_SOURCE)
    except ValueError:
        return False
    return (
        actual.scheme == "https"
        and actual.hostname == "blob.anantrajlimited.com"
        and actual.username is None
        and actual.password is None
        and actual.port in (None, 443)
        and actual.query == ""
        and actual.fragment == ""
        and unquote(actual.path) == original.path
    )


def load_verified_discovery(root: Path) -> dict[str, Any]:
    raw = (root / PROBE_MANIFEST).read_bytes()
    if _git_blob(raw) != PROBE_MANIFEST_BLOB:
        raise ValueError("original official investor HTML discovery receipt Git blob changed")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("probe_id") != (
        "HG007-P023-ANANTRAJ-AUG2026-COMPOSITE-SCHEME-SOURCE-DISCOVERY-v1"
    ):
        raise ValueError("original scheme link discovery protocol missing")
    if data.get("original_webpage_captured_count") != 2 or data.get(
        "aug17_35_58mb_scheme_pdf_original_bytes_retrieved"
    ) is not False:
        raise ValueError("P023 original evidence stage/coverage changed")
    sources = data.get("source_pages")
    if not isinstance(sources, list) or len(sources) != 2:
        raise ValueError("exact two original NSE/company page sources required")
    source = next(
        (row for row in sources if row.get("source_page_id") == "company_investor_scheme"),
        None,
    )
    if (
        not isinstance(source, dict)
        or source.get("source_state") != "OFFICIAL_PAGE_HTML_CAPTURED"
        or source.get("raw_html_sha256")
        != "25aa3328dd5964b8687eb4d3fff66b192fb2300228b94a8ae72107a688848aae"
    ):
        raise ValueError("original issuer-investor raw HTML source changed")
    links = source.get("link_discovery", {}).get(
        "candidate_pdf_urls_not_original_verified"
    )
    if not isinstance(links, list):
        raise TypeError("original official investor PDF link list missing")
    matching = [r for r in links if r.get("pdf_url") == EXACT_DISCOVERED_SOURCE]
    if (
        len(matching) != 1
        or matching[0].get("source_href_kind") != "OFFICIAL_HTML_ANCHOR"
        or matching[0].get("actual_pdf_bytes_fetched_and_sha_verified") is not False
    ):
        raise ValueError("full scheme PDF URL not proven by original primary HTML")
    return data


def _extract_verified_scheme_pages(raw: bytes) -> dict[str, Any]:
    if (
        not isinstance(raw, bytes)
        or not 20_000 <= len(raw) <= MAX_PDF_BYTES
        or not raw.startswith(b"%PDF-")
        or b"%%EOF" not in raw[-2048:]
    ):
        raise ValueError("full official composite scheme PDF byte envelope invalid")
    try:
        document = PdfReader(io.BytesIO(raw), strict=False)
        pages = list(document.pages)
    except (OSError, PdfReadError, ValueError, TypeError, KeyError) as exc:
        raise ValueError("full official scheme PDF structure invalid") from exc
    if len(pages) != EXPECTED_SCHEME_PAGE_COUNT:
        raise ValueError("unexpected original full composite scheme page count")
    text_info: list[dict[str, Any]] = []
    combined_first = ""
    for number, page in enumerate(pages, start=1):
        try:
            content = page.extract_text() or ""
        except (OSError, PdfReadError, ValueError, TypeError, KeyError):
            content = ""
        if number <= 6:
            combined_first += "\n" + content
        text_info.append({
            "pdf_page_number": number,
            "text_char_count": len(content),
            "text_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "mentions_demerger": "demerg" in content.casefold(),
            "mentions_assets": "asset" in content.casefold(),
            "mentions_liabilities": "liabilit" in content.casefold(),
            "mentions_undertaking": "undertaking" in content.casefold(),
            "text_extraction_is_independent_audited_fact": False,
        })
    intro = re.sub(r"\s+", " ", combined_first).casefold()
    if not all(text in intro for text in (
        "composite scheme of arrangement",
        "anant raj limited",
        "anant raj cloud private limited",
        "ashok cloud private limited",
        "amalgamat",
        "demerg",
    )):
        raise ValueError("downloaded 48-page PDF is not the original named issuer scheme")
    return {
        "page_count": EXPECTED_SCHEME_PAGE_COUNT,
        "pdf_byte_count": len(raw),
        "pdf_sha256": hashlib.sha256(raw).hexdigest(),
        "source_page_text_digest_provenance": text_info,
        "original_pdf_structure_readable": True,
        "original_pdf_page_visual_review_complete": False,
        "all_source_terms_semantically_approved": False,
    }


def _receipt(
    status: str,
    *,
    http_status: int | None,
    evidence: dict[str, Any] | None,
    reason: str,
) -> dict[str, Any]:
    if status not in SOURCE_STATES:
        raise ValueError("unrecognized official scheme source state")
    success = (
        status
        == "OFFICIAL_ISSUER_SCHEME_PDF_BYTES_IDENTITY_VERIFIED_NOT_LEGALLY_APPROVED"
    )
    if success != (evidence is not None):
        raise ValueError("scheme original source status/byte proof mismatch")
    return {
        "schema_version": 1,
        "source_id": SOURCE_ID,
        "symbol": "ANANTRAJ",
        "company_official_investor_page_url": "https://anantrajlimited.com/investors",
        "issuer_original_html_discovery_path": str(PROBE_MANIFEST),
        "issuer_original_html_discovery_git_blob": PROBE_MANIFEST_BLOB,
        "exact_issuer_pdf_discovered_href": EXACT_DISCOVERED_SOURCE,
        "original_pdf_transport_url": EXACT_TRANSPORT_SOURCE,
        "retrieved_at_utc": _utcnow(),
        "state": status,
        "http_status": http_status,
        "source_pdf": evidence,
        "unavailable_reason": reason if evidence is None else None,
        "original_pdf_bytes_acquired": success,
        "original_issuer_composite_scheme_document_identity_checked": success,
        "full_scheme_liabilities_assets_semantic_review_completed": False,
        "liability_values_and_assets_transferred_current_verified": False,
        "actual_demerged_undertaking_equity_fair_value_verified": False,
        "regulatory_approvals_effective_date_verified": False,
        "record_date_eligible_share_count_verified": False,
        "future_shareholder_distribution_completed": False,
        "case_completion_probabilities_published": False,
        "equity_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def acquire_exact_official_pdf() -> tuple[dict[str, Any], bytes | None]:
    url = EXACT_TRANSPORT_SOURCE
    if not _validate_pdf_location(url):
        raise ValueError("transport URL differs from verified official issuer PDF href")
    response = None
    try:
        response = requests.get(
            url,
            timeout=(20, 90),
            stream=True,
            allow_redirects=False,
            headers={
                "User-Agent": "marketlab-original-issuer-document-custody/1.0",
                "Accept": "application/pdf,application/octet-stream",
            },
        )
        status = response.status_code
        if not _validate_pdf_location(getattr(response, "url", url)):
            return _receipt(
                "ORIGINAL_PDF_REDIRECT_UNFOLLOWED", http_status=status,
                evidence=None, reason="SOURCE_URL_CHANGED_NO_BYPASS"
            ), None
        if status in (401, 403, 429):
            return _receipt(
                "OFFICIAL_ORIGINAL_PDF_ACCESS_BLOCKED", http_status=status,
                evidence=None, reason=f"HTTP_{status}_NO_ACCESS_BYPASS"
            ), None
        if status == 404:
            return _receipt(
                "ORIGINAL_PDF_NOT_AVAILABLE", http_status=status,
                evidence=None, reason="ORIGINAL_COMPANY_SCHEME_PDF_404"
            ), None
        if status != 200:
            return _receipt(
                "ORIGINAL_PDF_HTTP_OR_TRANSPORT_FAILURE", http_status=status,
                evidence=None, reason=f"HTTP_{status}"
            ), None
        declared_size = response.headers.get("content-length")
        if declared_size is not None:
            try:
                length = int(declared_size)
            except ValueError:
                length = -1
            if length < 0 or length > MAX_PDF_BYTES:
                return _receipt(
                    "ORIGINAL_PDF_INVALID_ENVELOPE_OR_ISSUER",
                    http_status=status, evidence=None,
                    reason="OFFICIAL_PDF_DECLARED_SIZE_OUTSIDE_LIMIT",
                ), None
        contents = bytearray()
        for part in response.iter_content(chunk_size=1_048_576):
            if not part:
                continue
            contents.extend(part)
            if len(contents) > MAX_PDF_BYTES:
                return _receipt(
                    "ORIGINAL_PDF_INVALID_ENVELOPE_OR_ISSUER", http_status=200,
                    evidence=None, reason="ORIGINAL_PDF_STREAM_SIZE_EXCEEDED",
                ), None
        raw = bytes(contents)
        try:
            evidence = _extract_verified_scheme_pages(raw)
        except ValueError as exc:
            return _receipt(
                "ORIGINAL_PDF_INVALID_ENVELOPE_OR_ISSUER", http_status=200,
                evidence=None, reason=str(exc),
            ), None
        return _receipt(
            "OFFICIAL_ISSUER_SCHEME_PDF_BYTES_IDENTITY_VERIFIED_NOT_LEGALLY_APPROVED",
            http_status=200, evidence=evidence,
            reason="SOURCE_PDF_ORIGINAL_BYTES_SHA_AND_PAGE_STRUCTURE_VERIFIED",
        ), raw
    except requests.RequestException as exc:
        return _receipt(
            "ORIGINAL_PDF_HTTP_OR_TRANSPORT_FAILURE",
            http_status=response.status_code if response is not None else None,
            evidence=None, reason=type(exc).__name__,
        ), None
    finally:
        if response is not None:
            response.close()


def retain_source(
    directory: Path, receipt: dict[str, Any], raw: bytes | None
) -> None:
    if receipt.get("source_id") != SOURCE_ID:
        raise ValueError("wrong composite scheme document identity")
    directory.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        if receipt.get("state") != (
            "OFFICIAL_ISSUER_SCHEME_PDF_BYTES_IDENTITY_VERIFIED_NOT_LEGALLY_APPROVED"
        ):
            raise ValueError("unverified original source bytes cannot be stored as accepted")
        current = _extract_verified_scheme_pages(raw)
        if receipt.get("source_pdf") != current:
            raise ValueError("original source PDF content/page digest differed on retention")
        target = directory / "raw" / "sha256" / f"{current['pdf_sha256']}.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != raw:
            raise ValueError("original source content-addressed PDF byte overwrite")
        target.write_bytes(raw)
        if hashlib.sha256(target.read_bytes()).hexdigest() != current["pdf_sha256"]:
            raise ValueError("source PDF persisted SHA-256 mismatch")
    elif receipt.get("source_pdf") is not None:
        raise ValueError("missing original PDF cannot carry source success proof")
    target = directory / "source-receipt-v1.json"
    encoded = json.dumps(
        receipt, indent=2, sort_keys=True, allow_nan=False
    ) + "\n"
    if target.exists() and target.read_text(encoding="utf-8") != encoded:
        raise ValueError("original scheme PDF source receipt is append-only")
    target.write_text(encoded, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    load_verified_discovery(args.repo_root)
    receipt, raw = acquire_exact_official_pdf()
    retain_source(args.out_dir, receipt, raw)
    print(json.dumps({
        "source_id": SOURCE_ID,
        "state": receipt["state"],
        "http_status": receipt["http_status"],
        "source_pdf_sha256": receipt["source_pdf"]["pdf_sha256"] if receipt["source_pdf"] else None,
        "page_count": receipt["source_pdf"]["page_count"] if receipt["source_pdf"] else None,
        "candidate_liability_text_pages": [
            r["pdf_page_number"]
            for r in (receipt["source_pdf"] or {}).get(
                "source_page_text_digest_provenance", []
            )
            if r["mentions_liabilities"]
        ],
        "scheme_effective": False,
        "valuation_authorized": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
