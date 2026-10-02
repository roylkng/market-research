from __future__ import annotations

import hashlib
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
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


XLSX_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XLSX_REL_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

PHASE_C_GENERAL_REQUIRED = {
    "appid",
    "tlasubmitteddt",
    "symbsymbol",
    "nameofthecompany",
    "corporateidentitynumbercinofthelistedentity",
    "currentfinancialyearstartdate",
    "currentfinancialyearenddate",
}
PHASE_C_PRODUCT_REQUIRED = {
    "appid",
    "symbsymbol",
    "productservicesoldbytheentity",
    "niccodesoldbytheentity",
    "percentageoftotalturnovercontributedsoldbytheentity",
}


def _normalize_header(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _normalize_identifier(value: object) -> str:
    raw = str(value or "").strip()
    if re.fullmatch(r"\d+\.0+", raw):
        raw = raw.split(".", 1)[0]
    return raw


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    namespace = f"{{{XLSX_MAIN_NS}}}"
    values = []
    for item in root.findall(f"{namespace}si"):
        values.append(
            "".join(
                node.text or ""
                for node in item.iter(f"{namespace}t")
            )
        )
    return values


def _xlsx_export_sheet_path(archive: zipfile.ZipFile) -> str:
    namespace = f"{{{XLSX_MAIN_NS}}}"
    relation_attribute = f"{{{XLSX_REL_NS}}}id"
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationship_id = None
    for sheet in workbook.iter(f"{namespace}sheet"):
        if str(sheet.attrib.get("name") or "") == "Export Worksheet":
            relationship_id = sheet.attrib.get(relation_attribute)
            break
    if not relationship_id:
        raise AlphaContractError(
            "D010 XLSX lacks frozen Export Worksheet sheet"
        )

    relationships = ET.fromstring(
        archive.read("xl/_rels/workbook.xml.rels")
    )
    target = None
    relationship_tag = f"{{{PACKAGE_REL_NS}}}Relationship"
    for relationship in relationships.iter(relationship_tag):
        if relationship.attrib.get("Id") == relationship_id:
            target = relationship.attrib.get("Target")
            break
    if not target:
        raise AlphaContractError(
            "D010 XLSX Export Worksheet relationship is missing"
        )
    normalized = str(target).lstrip("/")
    if not normalized.startswith("xl/"):
        normalized = f"xl/{normalized}"
    if normalized not in archive.namelist():
        raise AlphaContractError(
            f"D010 XLSX Export Worksheet member missing: {normalized}"
        )
    return normalized


def _xlsx_column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    if not letters:
        raise AlphaContractError(
            f"D010 XLSX cell reference has no column: {reference}"
        )
    value = 0
    for character in letters.upper():
        value = value * 26 + (ord(character) - ord("A") + 1)
    return value - 1


def _xlsx_export_rows(raw: bytes) -> list[list[str | None]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise AlphaContractError("D010 annual member is not valid XLSX") from exc

    with archive:
        shared = _xlsx_shared_strings(archive)
        sheet_path = _xlsx_export_sheet_path(archive)
        root = ET.fromstring(archive.read(sheet_path))
        namespace = f"{{{XLSX_MAIN_NS}}}"
        rows = []
        for row in root.iter(f"{namespace}row"):
            cells: dict[int, str | None] = {}
            max_index = -1
            for cell in row.findall(f"{namespace}c"):
                reference = str(cell.attrib.get("r") or "")
                index = _xlsx_column_index(reference)
                max_index = max(max_index, index)
                cell_type = cell.attrib.get("t")
                value: str | None = None
                if cell_type == "inlineStr":
                    inline = cell.find(f"{namespace}is")
                    if inline is not None:
                        value = "".join(
                            node.text or ""
                            for node in inline.iter(f"{namespace}t")
                        )
                else:
                    node = cell.find(f"{namespace}v")
                    if node is not None and node.text is not None:
                        raw_value = node.text
                        if cell_type == "s":
                            try:
                                value = shared[int(raw_value)]
                            except (ValueError, IndexError) as exc:
                                raise AlphaContractError(
                                    "D010 XLSX shared-string index invalid"
                                ) from exc
                        else:
                            value = raw_value
                cells[index] = value
            if max_index < 0:
                rows.append([])
            else:
                rows.append(
                    [cells.get(index) for index in range(max_index + 1)]
                )
    return rows


def _xlsx_table(raw: bytes) -> tuple[list[str], list[dict[str, str | None]]]:
    rows = _xlsx_export_rows(raw)
    if not rows:
        raise AlphaContractError("D010 XLSX Export Worksheet is empty")
    headers = [_normalize_header(value) for value in rows[0]]
    if not any(headers):
        raise AlphaContractError("D010 XLSX header row is empty")
    records = []
    for raw_row in rows[1:]:
        values = [
            None if value is None else str(value).strip()
            for value in raw_row
        ]
        if not any(value not in (None, "") for value in values):
            continue
        record: dict[str, str | None] = {}
        for index, header in enumerate(headers):
            if not header:
                continue
            record[header] = values[index] if index < len(values) else None
        records.append(record)
    return headers, records


def _annual_member(
    archive: zipfile.ZipFile,
    *,
    kind: str,
) -> str:
    candidates = []
    for name in archive.namelist():
        if not name.lower().endswith(".xlsx"):
            continue
        basename = PurePosixPath(name).name.casefold()
        if basename.startswith("~$"):
            continue
        if kind == "general":
            stem = PurePosixPath(basename).stem.strip()
            if re.fullmatch(r"brsr_general(?:\s+\d+)?", stem):
                candidates.append(name)
        elif kind == "product":
            if "brsr_general_product_services_sold" in basename:
                candidates.append(name)
        else:
            raise AlphaContractError(f"unsupported D010 annual table: {kind}")
    if len(candidates) != 1:
        raise AlphaContractError(
            f"D010 expected one {kind} workbook, found {candidates}"
        )
    return candidates[0]


def _parse_float(value: object) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = float(raw)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _phase_c_year_report(
    *,
    year: str,
    general_headers: list[str],
    general_rows: list[dict[str, str | None]],
    product_headers: list[str],
    product_rows: list[dict[str, str | None]],
) -> dict[str, Any]:
    general_header_set = set(general_headers)
    product_header_set = set(product_headers)
    missing_general = sorted(PHASE_C_GENERAL_REQUIRED - general_header_set)
    missing_product = sorted(PHASE_C_PRODUCT_REQUIRED - product_header_set)
    if missing_general:
        raise AlphaContractError(
            f"D010 {year} general headers missing: {missing_general}"
        )
    if missing_product:
        raise AlphaContractError(
            f"D010 {year} product headers missing: {missing_product}"
        )

    filing_count = len(general_rows)
    if filing_count == 0:
        raise AlphaContractError(f"D010 {year} has no entity filing records")

    entity_app_ids: dict[str, set[str]] = defaultdict(set)
    stable_count = 0
    cin_count = 0
    symbol_count = 0
    reporting_year_count = 0
    submitted_timestamp_count = 0
    app_to_identity: dict[str, str] = {}

    for row in general_rows:
        app_id = _normalize_identifier(row.get("appid"))
        cin = str(
            row.get("corporateidentitynumbercinofthelistedentity") or ""
        ).strip().upper()
        symbol = str(row.get("symbsymbol") or "").strip().upper()
        stable_identity = (
            f"CIN:{cin}"
            if cin
            else (f"SYMBOL:{symbol}" if symbol else "")
        )
        if stable_identity:
            stable_count += 1
            if app_id:
                entity_app_ids[stable_identity].add(app_id)
                existing = app_to_identity.get(app_id)
                if existing is not None and existing != stable_identity:
                    raise AlphaContractError(
                        f"D010 {year} APP_ID maps to multiple identities: {app_id}"
                    )
                app_to_identity[app_id] = stable_identity
        if cin:
            cin_count += 1
        if symbol:
            symbol_count += 1
        if (
            str(row.get("currentfinancialyearstartdate") or "").strip()
            and str(row.get("currentfinancialyearenddate") or "").strip()
        ):
            reporting_year_count += 1
        if str(row.get("tlasubmitteddt") or "").strip():
            submitted_timestamp_count += 1

    identity_counts: dict[str, int] = defaultdict(int)
    for row in general_rows:
        cin = str(
            row.get("corporateidentitynumbercinofthelistedentity") or ""
        ).strip().upper()
        symbol = str(row.get("symbsymbol") or "").strip().upper()
        stable_identity = (
            f"CIN:{cin}"
            if cin
            else (f"SYMBOL:{symbol}" if symbol else "")
        )
        if stable_identity:
            identity_counts[stable_identity] += 1
    duplicate_count = sum(max(count - 1, 0) for count in identity_counts.values())

    nic_by_identity: dict[str, set[str]] = defaultdict(set)
    nic_rows_by_identity: dict[str, list[tuple[str, float | None]]] = defaultdict(list)
    orphan_product_rows = 0
    explicit_nic_row_count = 0
    turnover_parseable_nic_row_count = 0

    for row in product_rows:
        app_id = _normalize_identifier(row.get("appid"))
        identity = app_to_identity.get(app_id)
        if identity is None:
            orphan_product_rows += 1
            continue
        nic = _normalize_identifier(row.get("niccodesoldbytheentity"))
        if not nic:
            continue
        explicit_nic_row_count += 1
        turnover = _parse_float(
            row.get("percentageoftotalturnovercontributedsoldbytheentity")
        )
        if turnover is not None:
            turnover_parseable_nic_row_count += 1
        nic_by_identity[identity].add(nic)
        nic_rows_by_identity[identity].append((nic, turnover))

    unique_entities = len(entity_app_ids)
    nic_entity_count = sum(
        1 for identity in entity_app_ids if nic_by_identity.get(identity)
    )
    multiple_nic_entities = sum(
        1
        for identity in entity_app_ids
        if len(nic_by_identity.get(identity, set())) > 1
    )
    turnover_weight_complete_multi = sum(
        1
        for identity in entity_app_ids
        if len(nic_by_identity.get(identity, set())) > 1
        and nic_rows_by_identity.get(identity)
        and all(value is not None for _, value in nic_rows_by_identity[identity])
    )

    def fraction(numerator: int, denominator: int) -> float:
        return 0.0 if denominator == 0 else numerator / denominator

    metrics = {
        "year": year,
        "general_data_row_count": filing_count,
        "product_data_row_count": len(product_rows),
        "unique_entity_count": unique_entities,
        "stable_identity_record_count": stable_count,
        "stable_identity_coverage": fraction(stable_count, filing_count),
        "cin_record_count": cin_count,
        "cin_coverage": fraction(cin_count, filing_count),
        "nse_symbol_record_count": symbol_count,
        "nse_symbol_coverage": fraction(symbol_count, filing_count),
        "reporting_year_record_count": reporting_year_count,
        "reporting_year_coverage": fraction(reporting_year_count, filing_count),
        "submission_timestamp_record_count": submitted_timestamp_count,
        "submission_timestamp_coverage": fraction(
            submitted_timestamp_count,
            filing_count,
        ),
        "duplicate_stable_identity_count": duplicate_count,
        "duplicate_identity_rate": fraction(duplicate_count, filing_count),
        "explicit_nic_row_count": explicit_nic_row_count,
        "explicit_nic_entity_count": nic_entity_count,
        "explicit_nic_coverage": fraction(nic_entity_count, unique_entities),
        "multiple_nic_entity_count": multiple_nic_entities,
        "turnover_weight_complete_multi_nic_entity_count": (
            turnover_weight_complete_multi
        ),
        "turnover_parseable_nic_row_count": turnover_parseable_nic_row_count,
        "orphan_product_row_count": orphan_product_rows,
        "general_required_headers_present": True,
        "product_required_headers_present": True,
    }
    metrics["gates"] = {
        "minimum_unique_entities_500": unique_entities >= 500,
        "minimum_nic_coverage_90pct": metrics["explicit_nic_coverage"] >= 0.90,
        "minimum_stable_identity_coverage_90pct": (
            metrics["stable_identity_coverage"] >= 0.90
        ),
        "maximum_duplicate_identity_rate_1pct": (
            metrics["duplicate_identity_rate"] <= 0.01
        ),
        "minimum_reporting_year_coverage_99pct": (
            metrics["reporting_year_coverage"] >= 0.99
        ),
    }
    metrics["year_gates_pass"] = all(metrics["gates"].values())
    return metrics


def parse_d010_annual_archive(
    *,
    year: str,
    raw: bytes,
) -> dict[str, Any]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise AlphaContractError(f"D010 {year} annual archive is invalid") from exc
    with archive:
        general_name = _annual_member(archive, kind="general")
        product_name = _annual_member(archive, kind="product")
        general_raw = archive.read(general_name)
        product_raw = archive.read(product_name)

    general_headers, general_rows = _xlsx_table(general_raw)
    product_headers, product_rows = _xlsx_table(product_raw)
    report = _phase_c_year_report(
        year=year,
        general_headers=general_headers,
        general_rows=general_rows,
        product_headers=product_headers,
        product_rows=product_rows,
    )
    report.update(
        {
            "annual_archive_sha256": hashlib.sha256(raw).hexdigest(),
            "general_workbook_path": general_name,
            "general_workbook_sha256": hashlib.sha256(general_raw).hexdigest(),
            "product_workbook_path": product_name,
            "product_workbook_sha256": hashlib.sha256(product_raw).hexdigest(),
            "general_headers": general_headers,
            "product_headers": product_headers,
        }
    )
    return report


def build_d010_phase_c_report(
    *,
    fy2023_24_raw: bytes,
    fy2024_25_raw: bytes,
) -> dict[str, Any]:
    year_reports = {
        "FY2023-24": parse_d010_annual_archive(
            year="FY2023-24",
            raw=fy2023_24_raw,
        ),
        "FY2024-25": parse_d010_annual_archive(
            year="FY2024-25",
            raw=fy2024_25_raw,
        ),
    }
    semantic_headers_compatible = all(
        report["product_required_headers_present"]
        for report in year_reports.values()
    )
    equal_required_year_entity_counts = (
        year_reports["FY2023-24"]["general_data_row_count"]
        == year_reports["FY2024-25"]["general_data_row_count"]
    )
    coverage_pass = (
        semantic_headers_compatible
        and all(report["year_gates_pass"] for report in year_reports.values())
    )
    failure_reasons = []
    for year, report in year_reports.items():
        for gate, passed in report["gates"].items():
            if not passed:
                failure_reasons.append(f"{year}:{gate}")
    if not semantic_headers_compatible:
        failure_reasons.append("NIC_TABLE_SEMANTICS_INCOMPATIBLE")

    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": "RM001-D010-PHASE-C-v1",
        "evidence_class": "SOURCE_FEASIBILITY_NO_RETURN_OUTCOMES",
        "parent_phase_ab_run_id": 37007303564,
        "parent_phase_ab_result_sha256": (
            "64a0ec350f76ba3413d037fc8b3bd234dd9389be915032a5048f9526cd3e444b"
        ),
        "parent_c0_run_id": 37008138534,
        "frozen_archive_sha256": {
            "FY2023-24": (
                "f287b4137b662a2f1cdba54f8d3858f84f09f43e1f0702ad5b2299cde5fb16ef"
            ),
            "FY2024-25": (
                "c5209af34ec21dd76f621f50ca6f8f5f5e07d6d09fb3591a9a636a59e4af0b42"
            ),
        },
        "year_reports": year_reports,
        "nic_semantics_compatible": semantic_headers_compatible,
        "equal_required_year_entity_counts": equal_required_year_entity_counts,
        "fixed_cap_gate_status": (
            "UNRESOLVED_EQUAL_ENTITY_TABLE_COUNTS"
            if equal_required_year_entity_counts
            else "NO_EQUAL_COUNT_PATTERN"
        ),
        "coverage_gates_pass": coverage_pass,
        "failure_reasons": failure_reasons,
        "status": (
            "PASS_SOURCE_FEASIBILITY"
            if coverage_pass and not equal_required_year_entity_counts
            else "FAIL_SOURCE_FEASIBILITY"
        ),
        "historical_factor_authorized": False,
        "d011_authorized": bool(
            coverage_pass and not equal_required_year_entity_counts
        ),
        "return_labels_opened": False,
        "risk_model_fit_performed": False,
        "portfolio_fit_performed": False,
        "live_capital_allowed": False,
    }
    report["result_sha256"] = digest(report)
    return report
