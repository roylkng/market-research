from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from marketlab.alpha import AlphaContractError, digest

D010_ID = "RM001-D010-v1"

UTILITY_URL = (
    "https://nsearchives.nseindia.com/web/mediaattachment/2026-03/"
    "NSE_Business_Responsibility__Sustainability_Reporting_20260330194720.zip"
)
TAXONOMY_URL = (
    "https://nsearchives.nseindia.com/web/mediaattachment/2026-03/"
    "Taxonomy_BRSR_20260330194931.zip"
)
TAXONOMY_ARCHIVE_URL = (
    "https://nsearchives.nseindia.com/web/mediaattachment/2026-07/"
    "Taxonomy_Archives_20260731164437.zip"
)
FILINGS_PAGE = (
    "https://www.nseindia.com/companies-listing/"
    "corporate-filings-bussiness-sustainabilitiy-reports"
)
COMPLIANCE_PAGE = "https://www.nseindia.com/regulations/listing-compliance"

ALLOWED_HOSTS = {
    "www.nseindia.com",
    "nseindia.com",
    "nsearchives.nseindia.com",
    "www1.nseindia.com",
    "betanseapi.nseindia.com",
}

TEXT_SUFFIXES = {
    ".xml",
    ".xsd",
    ".xbrl",
    ".csv",
    ".txt",
    ".html",
    ".htm",
    ".json",
    ".js",
    ".rels",
}
NESTED_ZIP_SUFFIXES = {".zip", ".xlsx", ".xlsm", ".xltx", ".xltm"}

CONCEPT_PATTERNS = {
    "NIC": (
        re.compile(r"\bNIC\b", re.IGNORECASE),
        re.compile(r"NIC\s*CODE", re.IGNORECASE),
        re.compile(r"NATIONAL\s+INDUSTRIAL\s+CLASSIFICATION", re.IGNORECASE),
        re.compile(r"NICCODE", re.IGNORECASE),
    ),
    "CIN": (
        re.compile(r"\bCIN\b", re.IGNORECASE),
        re.compile(r"CORPORATE\s+IDENTITY\s+NUMBER", re.IGNORECASE),
        re.compile(r"CORPORATEIDENTITYNUMBER", re.IGNORECASE),
    ),
    "ISIN": (re.compile(r"\bISIN\b", re.IGNORECASE),),
    "NSE_SYMBOL": (
        re.compile(r"NSE\s+SYMBOL", re.IGNORECASE),
        re.compile(r"TICKER\s+SYMBOL", re.IGNORECASE),
    ),
    "REPORTING_YEAR": (
        re.compile(r"FINANCIAL\s+YEAR", re.IGNORECASE),
        re.compile(r"REPORTING\s+(?:YEAR|PERIOD)", re.IGNORECASE),
        re.compile(r"FINANCIALYEAR", re.IGNORECASE),
    ),
    "PRODUCT_SERVICE": (
        re.compile(r"PRODUCT", re.IGNORECASE),
        re.compile(r"SERVICE", re.IGNORECASE),
    ),
    "TURNOVER_SHARE": (
        re.compile(r"TURNOVER", re.IGNORECASE),
        re.compile(r"PERCENTAGE.*TURNOVER", re.IGNORECASE),
        re.compile(r"PERCENT.*TURNOVER", re.IGNORECASE),
    ),
}

FILE_URL_PATTERN = re.compile(
    r"""(?P<url>
        https?://[^"'\s<>]+
        |
        /[^"'\s<>]+
    )""",
    re.VERBOSE | re.IGNORECASE,
)
API_PATTERN = re.compile(r"/api/[A-Za-z0-9_./?=&%:+\-]+")


@dataclass(frozen=True)
class SourceBytes:
    label: str
    url: str
    raw: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.raw).hexdigest()


def _allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in ALLOWED_HOSTS


def _decode_text(raw: bytes) -> str | None:
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _concept_hits(text: str, *, member_path: str) -> list[dict[str, str]]:
    hits = []
    collapsed = re.sub(r"\s+", " ", text)
    for family, patterns in CONCEPT_PATTERNS.items():
        found = None
        for pattern in patterns:
            match = pattern.search(collapsed)
            if match:
                found = match
                break
        if found is None:
            continue
        start = max(0, found.start() - 100)
        end = min(len(collapsed), found.end() + 180)
        hits.append(
            {
                "family": family,
                "member_path": member_path,
                "matched_text": found.group(0),
                "context": collapsed[start:end],
            }
        )
    return hits


def _inspect_zip_recursive(
    raw: bytes,
    *,
    logical_path: str,
    depth: int,
    members: list[dict[str, Any]],
    concept_hits: list[dict[str, str]],
) -> None:
    if depth > 2:
        return
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise AlphaContractError(f"D010 invalid ZIP: {logical_path}") from exc

    for info in archive.infolist():
        if info.is_dir():
            continue
        member_raw = archive.read(info.filename)
        child_path = f"{logical_path}!/{info.filename}"
        suffix = PurePosixPath(info.filename).suffix.lower()
        members.append(
            {
                "path": child_path,
                "size_bytes": len(member_raw),
                "sha256": hashlib.sha256(member_raw).hexdigest(),
                "suffix": suffix,
                "depth": depth,
            }
        )
        if suffix in TEXT_SUFFIXES or (
            not suffix and len(member_raw) <= 10_000_000
        ):
            decoded = _decode_text(member_raw)
            if decoded is not None:
                concept_hits.extend(
                    _concept_hits(decoded, member_path=child_path)
                )
        if suffix in NESTED_ZIP_SUFFIXES and depth < 2:
            try:
                _inspect_zip_recursive(
                    member_raw,
                    logical_path=child_path,
                    depth=depth + 1,
                    members=members,
                    concept_hits=concept_hits,
                )
            except AlphaContractError:
                # Some legacy XLS/XLSM-like members are not ZIP containers.
                pass


def inspect_brsr_zip(source: SourceBytes) -> dict[str, Any]:
    members: list[dict[str, Any]] = []
    hits: list[dict[str, str]] = []
    _inspect_zip_recursive(
        source.raw,
        logical_path=source.label,
        depth=0,
        members=members,
        concept_hits=hits,
    )
    counts: dict[str, int] = {}
    for member in members:
        suffix = member["suffix"] or "<none>"
        counts[suffix] = counts.get(suffix, 0) + 1

    families: dict[str, list[dict[str, str]]] = {}
    for hit in hits:
        families.setdefault(hit["family"], []).append(hit)

    return {
        "label": source.label,
        "url": source.url,
        "raw_sha256": source.sha256,
        "size_bytes": len(source.raw),
        "member_count": len(members),
        "member_suffix_counts": dict(sorted(counts.items())),
        "members": members,
        "concept_evidence": {
            family: rows[:25]
            for family, rows in sorted(families.items())
        },
        "concept_families_found": sorted(families),
    }


def phase_a_taxonomy_report(
    *,
    utility: SourceBytes,
    taxonomy: SourceBytes,
    taxonomy_archive: SourceBytes,
) -> dict[str, Any]:
    reports = [
        inspect_brsr_zip(utility),
        inspect_brsr_zip(taxonomy),
        inspect_brsr_zip(taxonomy_archive),
    ]
    families = {
        family
        for report in reports
        for family in report["concept_families_found"]
    }
    stable_identity = bool({"CIN", "ISIN", "NSE_SYMBOL"} & families)
    passed = (
        "NIC" in families
        and stable_identity
        and "REPORTING_YEAR" in families
    )
    return {
        "phase": "A_TAXONOMY_SCHEMA",
        "status": "PASS" if passed else "FAIL",
        "explicit_nic_concept_found": "NIC" in families,
        "stable_identity_concept_found": stable_identity,
        "identity_families_found": sorted(
            {"CIN", "ISIN", "NSE_SYMBOL"} & families
        ),
        "reporting_year_concept_found": "REPORTING_YEAR" in families,
        "product_service_concept_found": "PRODUCT_SERVICE" in families,
        "turnover_share_concept_found": "TURNOVER_SHARE" in families,
        "source_reports": reports,
    }


def _candidate_context(element: Any) -> str:
    parent = element.find_parent("tr")
    if parent is None:
        parent = element.parent
    text = parent.get_text(" ", strip=True) if parent is not None else ""
    return re.sub(r"\s+", " ", text)


def html_link_inventory(
    *,
    page_url: str,
    html_bytes: bytes,
) -> dict[str, Any]:
    decoded = _decode_text(html_bytes)
    if decoded is None:
        raise AlphaContractError(f"D010 page is not decodable: {page_url}")
    soup = BeautifulSoup(decoded, "html.parser")
    links = []
    script_urls = []
    for anchor in soup.find_all("a"):
        href = str(anchor.get("href") or "").strip()
        if not href or href.lower().startswith(("javascript:", "#")):
            continue
        url = urljoin(page_url, href)
        if not _allowed_url(url):
            continue
        links.append(
            {
                "url": url,
                "anchor_text": re.sub(
                    r"\s+",
                    " ",
                    anchor.get_text(" ", strip=True),
                ),
                "context": _candidate_context(anchor),
            }
        )
    for script in soup.find_all("script"):
        src = str(script.get("src") or "").strip()
        if not src:
            continue
        url = urljoin(page_url, src)
        if _allowed_url(url):
            script_urls.append(url)
    return {
        "page_url": page_url,
        "page_sha256": hashlib.sha256(html_bytes).hexdigest(),
        "link_count": len(links),
        "links": links,
        "script_urls": sorted(set(script_urls)),
    }


def _looks_brsr(text: str) -> bool:
    folded = text.casefold()
    return (
        "brsr" in folded
        or "business responsibility" in folded
        or "sustainability report" in folded
    )


def discover_brsr_candidates(
    *,
    page_inventories: list[dict[str, Any]],
    script_sources: list[SourceBytes],
) -> dict[str, Any]:
    direct = []
    for inventory in page_inventories:
        for row in inventory["links"]:
            haystack = f"{row['url']} {row['anchor_text']} {row['context']}"
            if _looks_brsr(haystack):
                direct.append(
                    {
                        "discovery_source": inventory["page_url"],
                        **row,
                    }
                )

    script_candidates = []
    api_candidates = []
    for source in script_sources:
        text = _decode_text(source.raw)
        if text is None:
            continue
        for match in FILE_URL_PATTERN.finditer(text):
            raw_url = match.group("url")
            context = text[max(0, match.start() - 250):match.end() + 250]
            if not _looks_brsr(f"{raw_url} {context}"):
                continue
            url = urljoin(source.url, raw_url)
            if _allowed_url(url):
                script_candidates.append(
                    {
                        "discovery_source": source.url,
                        "url": url,
                        "context": re.sub(r"\s+", " ", context)[:700],
                    }
                )
        for match in API_PATTERN.finditer(text):
            context = text[max(0, match.start() - 250):match.end() + 250]
            if not _looks_brsr(context):
                continue
            url = urljoin(source.url, match.group(0))
            if _allowed_url(url):
                api_candidates.append(
                    {
                        "discovery_source": source.url,
                        "url": url,
                        "context": re.sub(r"\s+", " ", context)[:700],
                    }
                )

    def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = set()
        result = []
        for row in rows:
            key = row["url"]
            if key in seen:
                continue
            seen.add(key)
            result.append(row)
        return sorted(result, key=lambda row: row["url"])

    return {
        "direct_brsr_links": dedupe(direct),
        "script_brsr_links": dedupe(script_candidates),
        "api_candidates": dedupe(api_candidates),
        "script_source_count": len(script_sources),
        "script_sources": [
            {
                "url": source.url,
                "raw_sha256": source.sha256,
                "size_bytes": len(source.raw),
            }
            for source in script_sources
        ],
    }


def annual_link_selection(
    discovery: dict[str, Any],
) -> dict[str, Any]:
    rows = [
        *discovery["direct_brsr_links"],
        *discovery["script_brsr_links"],
    ]
    selected = {}
    year_patterns = {
        "FY2023-24": (
            "23-24",
            "2023-24",
            "fy23",
            "fy_23",
            "2023_24",
        ),
        "FY2024-25": (
            "24-25",
            "2024-25",
            "fy24",
            "fy_24",
            "2024_25",
        ),
    }
    for year, patterns in year_patterns.items():
        matches = []
        for row in rows:
            haystack = " ".join(
                str(value)
                for value in row.values()
                if isinstance(value, str)
            ).casefold()
            if any(pattern in haystack for pattern in patterns):
                matches.append(row)
        selected[year] = matches
    return selected


def build_d010_phase_ab_report(
    *,
    utility: SourceBytes,
    taxonomy: SourceBytes,
    taxonomy_archive: SourceBytes,
    compliance_html: SourceBytes,
    filings_html: SourceBytes,
    script_sources: list[SourceBytes],
) -> dict[str, Any]:
    phase_a = phase_a_taxonomy_report(
        utility=utility,
        taxonomy=taxonomy,
        taxonomy_archive=taxonomy_archive,
    )
    inventories = [
        html_link_inventory(
            page_url=compliance_html.url,
            html_bytes=compliance_html.raw,
        ),
        html_link_inventory(
            page_url=filings_html.url,
            html_bytes=filings_html.raw,
        ),
    ]
    discovery = discover_brsr_candidates(
        page_inventories=inventories,
        script_sources=script_sources,
    )
    annual = annual_link_selection(discovery)
    phase_b_pass = all(
        len(annual[year]) >= 1
        for year in ("FY2023-24", "FY2024-25")
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D010_ID,
        "evidence_class": "SOURCE_FEASIBILITY_NO_RETURN_OUTCOMES",
        "phase_a": phase_a,
        "page_inventories": inventories,
        "discovery": discovery,
        "annual_link_candidates": annual,
        "phase_b": {
            "status": "PASS_URL_DISCOVERY" if phase_b_pass else "FAIL_URL_DISCOVERY",
            "fy2023_24_candidate_count": len(annual["FY2023-24"]),
            "fy2024_25_candidate_count": len(annual["FY2024-25"]),
        },
        "phase_c_authorized": bool(
            phase_a["status"] == "PASS" and phase_b_pass
        ),
        "return_labels_opened": False,
        "risk_model_fit_performed": False,
        "portfolio_fit_performed": False,
        "live_capital_allowed": False,
    }
    report["result_sha256"] = digest(report)
    return report
