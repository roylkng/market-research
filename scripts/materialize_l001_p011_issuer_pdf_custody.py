"""L001 P011: re-acquire six dated issuer PDF originals with immutable receipts.

This is an archival *2026-10-18 retrieval*, NOT proof the raw bytes were first
available as of the earlier historical research decision. Original issuer
publication dates are attributed claims. Issuer financial figures remain
economically unverified until they reconcile to original accounts.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from pypdf import PdfReader

SOURCE_SPEC = (
    (
        "zuari_q1_fy27_issuer_investor_deck",
        "https://www.zuariindustries.in/storage/uploads/images/1786947593.pdf",
        "2026-08-14",
        ("4,223", "Chambal"),
    ),
    (
        "zuari_q1_fy27_issuer_conference_transcript",
        "https://www.zuariindustries.in/storage/uploads/images/1787307585.pdf",
        "2026-08-21",
        ("900", "Dubai", "142"),
    ),
    (
        "zuari_agro_sep18_icd_partial_repayment",
        "https://www.zuari.in/assets/files/"
        "ZACLDisclosureunderReg30-RepaymentofICDs-18-09-2026.pdf",
        "2026-09-18",
        ("214.50", "258.50"),
    ),
    (
        "zuari_agro_sep30_icd_full_repayment",
        "https://www.zuari.in/assets/files/Reg30RepaymentofICDsdtd30.09.2026.pdf",
        "2026-09-30",
        ("44", "258.50", "Nil"),
    ),
    (
        "geship_q1_fy27_original_investor_deck",
        "https://greatship.com/upload/latest_announcements/"
        "Q1FY27_Updates_Presentation.pdf_(1).pdf",
        "2026-08-04",
        ("1,862", "1,911"),
    ),
    (
        "geship_oct13_original_first_buyback_extinguishment_certificate",
        "https://greatship.com/upload/investors/buyback_2026/"
        "1st_Lot_Buyback_Extinguishment_Certificate.pdf",
        "2026-10-13",
        ("18,58,941", "14,09,08,220"),
    ),
)
ALLOWED_HOSTS = frozenset({
    "www.zuariindustries.in", "www.zuari.in", "greatship.com", "www.greatship.com"
})
MAX_BYTES = 16 * 1024 * 1024


def _policy(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname in ALLOWED_HOSTS
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
    )


def _normalized(value: str) -> str:
    # Text may place commas/spaces inside PDF-extracted numeric tokens. We
    # retain both exact tokens and compact alphanumeric presentation.
    return re.sub(r"[^a-z0-9.]+", "", value.casefold())


def _claims(text: str, claims: tuple[str, ...]) -> list[str]:
    compact = _normalized(text)
    return [token for token in claims if _normalized(token) not in compact]


def _pdf_text(data: bytes) -> tuple[int, str]:
    if not data.startswith(b"%PDF-") or len(data) < 500:
        raise ValueError("issuer original is not nonempty PDF bytes")
    try:
        pdf = PdfReader(io.BytesIO(data), strict=True)
        count = len(pdf.pages)
        if count < 1 or count > 500:
            raise ValueError("issuer PDF page count out of bounds")
        text = "\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception as exc:
        raise ValueError("issuer original PDF structurally unreadable") from exc
    if len(text) < 100:
        raise ValueError("issuer PDF has no meaningful text layer")
    return count, text


def materialize_sources(
    *,
    fetcher=requests.get,
) -> tuple[dict, dict[str, bytes]]:
    rows = []
    sources = {}
    for label, url, claimed_date, tokens in SOURCE_SPEC:
        if not _policy(url) or label in sources:
            raise ValueError("source URL or label not permissible")
        response = fetcher(
            url,
            headers={"User-Agent": "MarketLabOriginalSourceAudit/1.0"},
            allow_redirects=True,
            timeout=25,
        )
        response.raise_for_status()
        actual_url = response.url
        if not _policy(actual_url):
            raise ValueError("original PDF redirected to unapproved host")
        raw = response.content
        if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
            raise ValueError("original PDF exceeded size or missing raw bytes")
        pages, extracted = _pdf_text(raw)
        missing = _claims(extracted, tokens)
        if missing:
            raise ValueError(f"{label}: required original numeric/text not extracted: {missing}")
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        digest = hashlib.sha256(raw).hexdigest()
        sources[label] = raw
        rows.append({
            "source_id": label,
            "original_issuer_url": url,
            "final_download_url": actual_url,
            "source_date_claimed_by_issuer": claimed_date,
            "actual_first_verified_capture_utc": now,
            "original_pdf_sha256": digest,
            "original_pdf_size_bytes": len(raw),
            "page_count": pages,
            "verified_selected_extracted_tokens": list(tokens),
            "entire_source_pdf_semantics_independently_audited": False,
            "historical_decision_date_original_byte_custody_proven": False,
        })
    return {
        "schema_version": 1,
        "audit_id": "L001-P011-ORIGINAL-ISSUER-PDF-CUSTODY-v1",
        "source_count": len(rows),
        "claimed_issuer_publication_dates_are_not_first_seen_timestamps": True,
        "no_retrospective_lookahead_claims": True,
        "no_financial_valuation_or_return_predictions": True,
        "investment_authorized": False,
        "sources": rows,
    }, sources


def _archive(destination: Path, manifest: dict, sources: dict[str, bytes]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Deterministic file ordering; manifest contains real capture time.
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr(
            "verified-original-source-manifest.json",
            json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        )
        for key, raw in sorted(sources.items()):
            output.writestr(f"original_pdf/{key}.pdf", raw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--original-zip", required=True, type=Path)
    args = parser.parse_args()
    manifest, sources = materialize_sources()
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    _archive(args.original_zip, manifest, sources)
    print(json.dumps({
        "pdfs_verified": manifest["source_count"],
        "archive_sha256": hashlib.sha256(args.original_zip.read_bytes()).hexdigest(),
        "source_shas": {
            row["source_id"]: row["original_pdf_sha256"] for row in manifest["sources"]
        },
        "historical_source_first_seen_proven": False,
        "investment_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
