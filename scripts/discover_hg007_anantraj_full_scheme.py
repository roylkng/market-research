"""Source-only discovery of the published ANANTRAJ composite scheme PDF URLs.

The NSE public scheme index lists an Aug 17 2026 ~35.58 MB document.
The issuer website lists Composite Scheme of Arrangement. This probe
preserves *original HTML responses* and candidate direct public PDF URLs,
never invents an archive filename or represents the proposal as effective.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

PROBE_ID = "HG007-P023-ANANTRAJ-AUG2026-COMPOSITE-SCHEME-SOURCE-DISCOVERY-v1"
PRIMARY_PAGES = {
    "company_investor_scheme": "https://anantrajlimited.com/investors",
    "official_nse_scheme_listing": (
        "https://www.nseindia.com/companies-listing/"
        "corporate-filings-scheme-document"
    ),
}
APPROVED_PDF_HOSTS = frozenset({
    "blob.anantrajlimited.com",
    "anantrajlimited.com",
    "www.anantrajlimited.com",
    "nsearchives.nseindia.com",
    "archives.nseindia.com",
    "www.nseindia.com",
    "www.bseindia.com",
})
MAX_SOURCE_HTML_BYTES = 6_000_000
MAX_CANDIDATES = 80
SOURCE_STATES = frozenset({
    "OFFICIAL_PAGE_HTML_CAPTURED",
    "OFFICIAL_PAGE_ACCESS_BLOCKED",
    "OFFICIAL_PAGE_MISSING",
    "OFFICIAL_PAGE_REDIRECT_UNFOLLOWED",
    "OFFICIAL_PAGE_WRONG_CONTENT",
    "OFFICIAL_PAGE_FETCH_FAILED",
})
CASE_TERMS = ("scheme", "arrangement", "composite", "ashok cloud", "anant raj")


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _source_ok(page_id: str, url: str) -> None:
    if page_id not in PRIMARY_PAGES or PRIMARY_PAGES[page_id] != url:
        raise ValueError("source page must be an exact approved official webpage")


def _candidate_pdf(href: str, *, base: str) -> str | None:
    if not isinstance(href, str) or not href.strip():
        return None
    cleaned = html.unescape(href.strip()).replace("\\/", "/")
    if cleaned.startswith(("javascript:", "data:", "file:")):
        return None
    candidate = urljoin(base, cleaned)
    try:
        parts = urlsplit(candidate)
    except ValueError:
        return None
    if (
        parts.scheme != "https"
        or parts.hostname not in APPROVED_PDF_HOSTS
        or parts.username is not None
        or parts.password is not None
        or parts.port not in (None, 443)
        or not unquote(parts.path).casefold().endswith(".pdf")
        or parts.fragment
    ):
        return None
    return candidate


def discover_official_pdf_candidates(
    page_id: str, url: str, raw_html: bytes
) -> dict[str, Any]:
    _source_ok(page_id, url)
    if not isinstance(raw_html, bytes) or not 80 <= len(raw_html) <= MAX_SOURCE_HTML_BYTES:
        raise ValueError("official HTML source missing or outside size bound")
    source = raw_html.decode("utf-8", errors="replace")
    soup = BeautifulSoup(source, "html.parser")
    document_text = " ".join(soup.stripped_strings).casefold()
    # These booleans are only HTML discovery hints, not verified source
    # uploads and never evidence of an effective scheme.
    issuer_mentioned = "anant raj" in document_text
    listing_says_scheme = (
        "scheme" in document_text and "arrangement" in document_text
    )
    candidates: dict[str, dict[str, Any]] = {}
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        found = _candidate_pdf(href, base=url)
        if found is None:
            continue
        label = " ".join(anchor.stripped_strings)[:450]
        surrounding = " ".join(anchor.parent.stripped_strings)[:900]
        tokens = f"{label} {surrounding} {found}".casefold()
        if not any(term in tokens for term in CASE_TERMS):
            continue
        candidates[found] = {
            "pdf_url": found,
            "source_page_id": page_id,
            "source_href_kind": "OFFICIAL_HTML_ANCHOR",
            "source_link_label": label,
            "source_link_context": surrounding,
            "scheme_specific_file_identity_verified": False,
            "actual_pdf_bytes_fetched_and_sha_verified": False,
        }
    # Some listed-company sites embed file URLs in server-rendered JSON
    # rather than <a> links. These are unapproved candidate URLs only.
    pattern = re.compile(r"https?://[^\"'\s<>\\]{1,1500}?\.pdf(?:\?[^\"'\s<>\\]{0,400})?", re.I)
    for match in pattern.finditer(source):
        found = _candidate_pdf(match.group(), base=url)
        if found is None or found in candidates:
            continue
        context = html.unescape(source[max(0, match.start() - 320):match.end() + 320])
        context = re.sub(r"<[^>]+>", " ", context)
        normalized = " ".join(context.split())[:800]
        if not any(term in normalized.casefold() for term in CASE_TERMS):
            continue
        candidates[found] = {
            "pdf_url": found,
            "source_page_id": page_id,
            "source_href_kind": "SERVER_EMBEDDED_LITERAL_PDF_URL",
            "source_link_label": None,
            "source_link_context": normalized,
            "scheme_specific_file_identity_verified": False,
            "actual_pdf_bytes_fetched_and_sha_verified": False,
        }
    if len(candidates) > MAX_CANDIDATES:
        raise ValueError("official scheme source contains excessive ambiguous PDF links")
    return {
        "original_source_html_sha256": hashlib.sha256(raw_html).hexdigest(),
        "original_html_bytes": len(raw_html),
        "issuer_name_mentioned_in_current_html": issuer_mentioned,
        "scheme_terms_visible_in_current_html": listing_says_scheme,
        "candidate_direct_pdf_url_count": len(candidates),
        "candidate_pdf_urls_not_original_verified": [
            candidates[key] for key in sorted(candidates)
        ],
        "client_side_loaded_source_links_could_be_missing": True,
        "composite_scheme_uploaded_aug17_original_pdf_acquired": False,
    }


def fetch_official_page(page_id: str) -> tuple[dict[str, Any], bytes | None]:
    if page_id not in PRIMARY_PAGES:
        raise ValueError("unregistered original discovery webpage")
    url = PRIMARY_PAGES[page_id]
    http_status: int | None = None
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "marketlab-issuer-document-research/1.0",
                "Accept": "text/html",
            },
            timeout=25,
            allow_redirects=False,
        )
        http_status = response.status_code
        if getattr(response, "url", url) != url or 300 <= http_status < 400:
            status, reason, raw = (
                "OFFICIAL_PAGE_REDIRECT_UNFOLLOWED",
                "REDIRECT_OR_URL_CHANGED_NO_BYPASS",
                None,
            )
        elif http_status in (401, 403, 429):
            status, reason, raw = (
                "OFFICIAL_PAGE_ACCESS_BLOCKED",
                f"HTTP_{http_status}_NO_ACCESS_BYPASS",
                None,
            )
        elif http_status == 404:
            status, reason, raw = (
                "OFFICIAL_PAGE_MISSING",
                "OFFICIAL_PAGE_HTTP_404",
                None,
            )
        elif http_status != 200:
            status, reason, raw = (
                "OFFICIAL_PAGE_FETCH_FAILED",
                f"HTTP_{http_status}",
                None,
            )
        else:
            raw = response.content
            if (
                not isinstance(raw, bytes)
                or not 80 <= len(raw) <= MAX_SOURCE_HTML_BYTES
                or b"<html" not in raw[:6000].lower()
            ):
                status, reason, raw = (
                    "OFFICIAL_PAGE_WRONG_CONTENT",
                    "HTML_ENVELOPE_OR_SIZE_INVALID",
                    None,
                )
            else:
                status, reason = "OFFICIAL_PAGE_HTML_CAPTURED", "ORIGINAL_HTML_CAPTURED"
    except requests.RequestException as exc:
        status, reason, raw = (
            "OFFICIAL_PAGE_FETCH_FAILED", type(exc).__name__, None,
        )

    assert status in SOURCE_STATES
    receipt = {
        "source_page_id": page_id,
        "exact_official_page_url": url,
        "source_capture_at_utc": _now(),
        "source_state": status,
        "http_status": http_status,
        "blocked_reason": reason if raw is None else None,
        "raw_html_sha256": hashlib.sha256(raw).hexdigest() if raw else None,
        "raw_html_bytes": len(raw) if raw else None,
    }
    return receipt, raw


def retain_discovery_run(
    output_dir: Path, sources: dict[str, tuple[dict, bytes | None]]
) -> dict[str, Any]:
    if set(sources) != set(PRIMARY_PAGES):
        raise ValueError("both exact official source webpages must be accounted for")
    output_dir.mkdir(parents=True, exist_ok=True)
    receipts = []
    for page_id in PRIMARY_PAGES:
        receipt, raw = sources[page_id]
        if receipt.get("source_page_id") != page_id:
            raise ValueError("cross-page official source receipt mismatch")
        if raw is None:
            if (
                receipt.get("source_state") == "OFFICIAL_PAGE_HTML_CAPTURED"
                or receipt.get("raw_html_sha256") is not None
            ):
                raise ValueError("unavailable official HTML cannot claim captured source")
            candidates = None
        else:
            if receipt.get("source_state") != "OFFICIAL_PAGE_HTML_CAPTURED":
                raise ValueError("captured HTML may not be reported as unavailable")
            candidates = discover_official_pdf_candidates(
                page_id, PRIMARY_PAGES[page_id], raw
            )
            digest = hashlib.sha256(raw).hexdigest()
            if digest != receipt.get("raw_html_sha256"):
                raise ValueError("source page original byte SHA-256 mismatch")
            target = output_dir / "raw" / "sha256" / f"{digest}.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != raw:
                raise ValueError("source original HTML custody overwritten")
            target.write_bytes(raw)
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError("official HTML retained content differs")
        receipts.append({**receipt, "link_discovery": candidates})

    all_candidates = {
        row["pdf_url"]
        for receipt in receipts
        if isinstance(receipt["link_discovery"], dict)
        for row in receipt["link_discovery"]["candidate_pdf_urls_not_original_verified"]
    }
    result = {
        "schema_version": 1,
        "probe_id": PROBE_ID,
        "classification": "OFFICIAL_SOURCE_LISTING_DISCOVERY_ONLY_NOT_APPROVED_SCHEME_PDF",
        "original_webpage_count": len(PRIMARY_PAGES),
        "original_webpage_captured_count": sum(
            receipt["source_state"] == "OFFICIAL_PAGE_HTML_CAPTURED" for receipt in receipts
        ),
        "source_pages": receipts,
        "unique_candidate_pdf_url_count": len(all_candidates),
        "candidate_pdf_urls_not_original_verified": sorted(all_candidates),
        "aug17_nse_public_listing_exists_from_separately_observed_index": True,
        "aug17_35_58mb_scheme_pdf_original_bytes_retrieved": False,
        "scheme_schedules_assets_liabilities_reconciled": False,
        "nclt_effective_scheme_verified": False,
        "newco_record_date_capital_verified": False,
        "equity_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    (output_dir / "discovery-v1.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    sources = {page_id: fetch_official_page(page_id) for page_id in PRIMARY_PAGES}
    result = retain_discovery_run(args.out_dir, sources)
    print(json.dumps({
        "probe_id": result["probe_id"],
        "official_page_captured_count": result["original_webpage_captured_count"],
        "candidate_pdf_urls": result["candidate_pdf_urls_not_original_verified"],
        "aug17_full_scheme_pdf_retrieved": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
