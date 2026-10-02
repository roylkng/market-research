from __future__ import annotations

import hashlib
import io
import posixpath
import re
import zipfile
from collections import Counter
from typing import Any
from xml.etree import ElementTree as ET

from marketlab.alpha import AlphaContractError, digest

D008_ID = "RM001-D008-v1"
_XLSX_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

IDENTITY_TOKENS = {
    "ISIN",
    "ISIN NUMBER",
    "SYMBOL",
    "TICKER",
    "TICKER SYMBOL",
    "SECURITY SYMBOL",
}
DESCRIPTOR_TOKENS = {
    "COMPANY",
    "COMPANY NAME",
    "SECURITY",
    "SECURITY NAME",
    "ISSUER",
    "ISSUER NAME",
    "NAME",
}
CLASSIFICATION_TOKENS = {
    "BASIC INDUSTRY",
    "INDUSTRY",
    "SECTOR",
    "MACRO ECONOMIC SECTOR",
    "INDUSTRY CLASSIFICATION",
}
HEADER_SCAN_NONEMPTY_ROWS = 75
MIN_CANDIDATE_DATA_ROWS = 500
MIN_CLASSIFICATION_COVERAGE = 0.90


def _normalize(value: object) -> str:
    text = str(value or "").strip().upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return " ".join(text.split())


def _column_index(reference: str) -> int:
    match = re.match(r"^([A-Z]+)", reference.upper())
    if match is None:
        raise AlphaContractError(f"D008 invalid XLSX cell reference: {reference}")
    result = 0
    for char in match.group(1):
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    name = "xl/sharedStrings.xml"
    if name not in archive.namelist():
        return []
    root = ET.fromstring(archive.read(name))
    values = []
    for item in root.findall(f"{{{_XLSX_MAIN_NS}}}si"):
        parts = [
            node.text or ""
            for node in item.iter(f"{{{_XLSX_MAIN_NS}}}t")
        ]
        values.append("".join(parts))
    return values


def _sheet_paths(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook_name = "xl/workbook.xml"
    rels_name = "xl/_rels/workbook.xml.rels"
    if workbook_name not in archive.namelist() or rels_name not in archive.namelist():
        raise AlphaContractError("D008 XLSX workbook metadata is missing")

    workbook = ET.fromstring(archive.read(workbook_name))
    rels = ET.fromstring(archive.read(rels_name))
    relationship_map = {
        str(node.attrib["Id"]): str(node.attrib["Target"])
        for node in rels.findall(f"{{{_PKG_REL_NS}}}Relationship")
    }

    result = []
    sheets = workbook.find(f"{{{_XLSX_MAIN_NS}}}sheets")
    if sheets is None:
        raise AlphaContractError("D008 XLSX workbook has no sheets")
    for node in sheets:
        name = str(node.attrib.get("name") or "").strip()
        rel_id = str(node.attrib.get(f"{{{_REL_NS}}}id") or "")
        target = relationship_map.get(rel_id)
        if not name or not target:
            raise AlphaContractError("D008 XLSX sheet relationship is malformed")
        if target.startswith("/"):
            path = target.lstrip("/")
        else:
            path = posixpath.normpath(posixpath.join("xl", target))
        if path not in archive.namelist():
            raise AlphaContractError(
                f"D008 XLSX sheet XML is missing: {name} -> {path}"
            )
        result.append((name, path))
    return result


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    cell_type = str(cell.attrib.get("t") or "")
    if cell_type == "inlineStr":
        inline = cell.find(f"{{{_XLSX_MAIN_NS}}}is")
        if inline is None:
            return ""
        return "".join(
            node.text or ""
            for node in inline.iter(f"{{{_XLSX_MAIN_NS}}}t")
        )
    value = cell.find(f"{{{_XLSX_MAIN_NS}}}v")
    if value is None or value.text is None:
        formula_string = cell.find(f"{{{_XLSX_MAIN_NS}}}f")
        return "" if formula_string is None else str(formula_string.text or "")
    raw = value.text
    if cell_type == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError) as exc:
            raise AlphaContractError("D008 invalid shared-string index") from exc
    if cell_type in {"str", "b", "e"}:
        return raw
    return raw


def _worksheet_rows(
    archive: zipfile.ZipFile,
    path: str,
    shared: list[str],
) -> list[tuple[int, dict[int, str]]]:
    rows: list[tuple[int, dict[int, str]]] = []
    root = ET.fromstring(archive.read(path))
    sheet_data = root.find(f"{{{_XLSX_MAIN_NS}}}sheetData")
    if sheet_data is None:
        return rows
    for row in sheet_data.findall(f"{{{_XLSX_MAIN_NS}}}row"):
        row_number = int(row.attrib.get("r") or len(rows) + 1)
        values: dict[int, str] = {}
        for cell in row.findall(f"{{{_XLSX_MAIN_NS}}}c"):
            reference = str(cell.attrib.get("r") or "")
            text = _cell_text(cell, shared).strip()
            if reference and text:
                values[_column_index(reference)] = text
        if values:
            rows.append((row_number, values))
    return rows


def _header_matches(values: dict[int, str]) -> dict[str, dict[int, str]]:
    normalized = {column: _normalize(value) for column, value in values.items()}
    identity = {
        column: value
        for column, value in normalized.items()
        if value in IDENTITY_TOKENS
        or value.endswith(" ISIN")
        or value.endswith(" SYMBOL")
    }
    descriptor = {
        column: value
        for column, value in normalized.items()
        if value in DESCRIPTOR_TOKENS
        or "COMPANY NAME" in value
        or "SECURITY NAME" in value
        or "ISSUER NAME" in value
    }
    classification = {
        column: value
        for column, value in normalized.items()
        if value in CLASSIFICATION_TOKENS
        or "BASIC INDUSTRY" in value
        or "INDUSTRY CLASSIFICATION" in value
        or value.endswith(" SECTOR")
    }
    return {
        "identity": identity,
        "descriptor": descriptor,
        "classification": classification,
        "normalized": normalized,
    }


def _identity_priority(matches: dict[int, str]) -> int | None:
    isin = [
        column
        for column, value in matches.items()
        if "ISIN" in value
    ]
    if isin:
        return min(isin)
    symbol = [
        column
        for column, value in matches.items()
        if "SYMBOL" in value or "TICKER" in value
    ]
    return min(symbol) if symbol else None


def _analyze_candidate(
    rows: list[tuple[int, dict[int, str]]],
    *,
    header_position: int,
    matches: dict[str, dict[int, str]],
) -> dict[str, Any]:
    header_row_number, header_values = rows[header_position]
    identity_column = _identity_priority(matches["identity"])
    classification_columns = sorted(matches["classification"])
    if identity_column is None or not classification_columns:
        raise AlphaContractError("D008 candidate header lacks required columns")

    data_rows = rows[header_position + 1 :]
    relevant_rows = []
    identities = []
    classification_nonempty = 0
    classification_counter: Counter[str] = Counter()

    for _, values in data_rows:
        identity = str(values.get(identity_column) or "").strip()
        classifications = [
            str(values.get(column) or "").strip()
            for column in classification_columns
        ]
        if not identity and not any(classifications):
            continue
        relevant_rows.append(values)
        if identity:
            identities.append(identity)
        nonempty_classifications = [value for value in classifications if value]
        if nonempty_classifications:
            classification_nonempty += 1
            classification_counter.update(nonempty_classifications)

    duplicate_identity_count = (
        len(identities) - len(set(identities))
        if identities
        else 0
    )
    coverage = (
        classification_nonempty / len(relevant_rows)
        if relevant_rows
        else 0.0
    )

    return {
        "header_row": header_row_number,
        "headers": {
            str(column): value
            for column, value in sorted(header_values.items())
        },
        "normalized_headers": {
            str(column): value
            for column, value in sorted(matches["normalized"].items())
        },
        "identity_headers": {
            str(column): value
            for column, value in sorted(matches["identity"].items())
        },
        "descriptor_headers": {
            str(column): value
            for column, value in sorted(matches["descriptor"].items())
        },
        "classification_headers": {
            str(column): value
            for column, value in sorted(matches["classification"].items())
        },
        "identity_column": identity_column,
        "identity_semantics": matches["identity"].get(identity_column),
        "data_row_count": len(relevant_rows),
        "classification_nonempty_row_count": classification_nonempty,
        "classification_coverage": coverage,
        "duplicate_identity_count": duplicate_identity_count,
        "unique_identity_count": len(set(identities)),
        "unique_classification_value_count": len(classification_counter),
        "classification_value_samples": [
            value
            for value, _ in classification_counter.most_common(25)
        ],
    }


def analyze_monthly_workbook(
    raw_xlsx: bytes,
    *,
    month: str,
    source_url: str,
) -> dict[str, Any]:
    if not raw_xlsx:
        raise AlphaContractError("D008 workbook bytes are required")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw_xlsx))
    except zipfile.BadZipFile as exc:
        raise AlphaContractError("D008 source is not a valid XLSX ZIP") from exc

    with archive:
        shared = _shared_strings(archive)
        sheets = _sheet_paths(archive)
        sheet_reports = []
        all_keyword_hits = []

        for sheet_name, path in sheets:
            rows = _worksheet_rows(archive, path, shared)
            candidates = []
            keyword_hits = []
            nonempty_seen = 0
            for position, (row_number, values) in enumerate(rows):
                matches = _header_matches(values)
                normalized_values = list(matches["normalized"].values())
                if any(
                    token in value
                    for value in normalized_values
                    for token in (
                        "INDUSTRY",
                        "SECTOR",
                        "ISIN",
                        "SYMBOL",
                        "COMPANY",
                        "SECURITY",
                    )
                ):
                    keyword_hits.append(
                        {
                            "row": row_number,
                            "values": {
                                str(column): value
                                for column, value in sorted(values.items())
                            },
                        }
                    )
                nonempty_seen += 1
                if nonempty_seen > HEADER_SCAN_NONEMPTY_ROWS:
                    break
                if (
                    matches["identity"]
                    and matches["descriptor"]
                    and matches["classification"]
                ):
                    candidates.append(
                        _analyze_candidate(
                            rows,
                            header_position=position,
                            matches=matches,
                        )
                    )

            sheet_report = {
                "sheet_name": sheet_name,
                "worksheet_path": path,
                "nonempty_row_count": len(rows),
                "candidate_count": len(candidates),
                "candidates": candidates,
                "keyword_hits_first_75": keyword_hits[:40],
            }
            sheet_reports.append(sheet_report)
            for hit in keyword_hits[:40]:
                all_keyword_hits.append(
                    {
                        "sheet_name": sheet_name,
                        **hit,
                    }
                )

    candidate_reports = [
        {
            "sheet_name": sheet["sheet_name"],
            **candidate,
        }
        for sheet in sheet_reports
        for candidate in sheet["candidates"]
    ]
    passing_candidates = [
        candidate
        for candidate in candidate_reports
        if candidate["data_row_count"] >= MIN_CANDIDATE_DATA_ROWS
        and candidate["classification_coverage"]
        >= MIN_CLASSIFICATION_COVERAGE
        and candidate["duplicate_identity_count"] == 0
    ]

    result: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D008_ID,
        "month": month,
        "source_url": source_url,
        "source_sha256": hashlib.sha256(raw_xlsx).hexdigest(),
        "sheet_count": len(sheet_reports),
        "sheet_names": [sheet["sheet_name"] for sheet in sheet_reports],
        "candidate_count": len(candidate_reports),
        "passing_candidate_count": len(passing_candidates),
        "candidates": candidate_reports,
        "keyword_hits_first_75": all_keyword_hits[:120],
        "source_candidate_pass": bool(passing_candidates),
        "live_capital_allowed": False,
    }
    result["result_sha256"] = digest(result)
    return result


def summarize_d008(
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(reports) != 4:
        raise AlphaContractError("D008 requires exactly four frozen sample reports")
    months = [str(report["month"]) for report in reports]
    if len(set(months)) != 4:
        raise AlphaContractError("D008 sample months must be unique")

    all_pass = all(report["source_candidate_pass"] for report in reports)
    selected = []
    for report in reports:
        candidates = [
            candidate
            for candidate in report["candidates"]
            if candidate["data_row_count"] >= MIN_CANDIDATE_DATA_ROWS
            and candidate["classification_coverage"]
            >= MIN_CLASSIFICATION_COVERAGE
            and candidate["duplicate_identity_count"] == 0
        ]
        candidates.sort(
            key=lambda candidate: (
                -candidate["classification_coverage"],
                -candidate["data_row_count"],
                candidate["sheet_name"],
                candidate["header_row"],
            )
        )
        selected.append(candidates[0] if candidates else None)

    semantics = {
        tuple(
            sorted(candidate["classification_headers"].values())
        )
        if candidate is not None
        else ()
        for candidate in selected
    }
    stable_semantics = all_pass and len(semantics) == 1

    direct_isin = all(
        candidate is not None
        and "ISIN" in str(candidate["identity_semantics"] or "")
        for candidate in selected
    )

    full_scan_authorized = all_pass and stable_semantics
    direct_promotion_authorized = full_scan_authorized and direct_isin
    status = (
        "PASS_DIRECT_POINT_IN_TIME_SOURCE_CANDIDATE"
        if direct_promotion_authorized
        else (
            "PASS_SUCCESSOR_JOIN_DIAGNOSTIC_AUTHORIZED"
            if full_scan_authorized
            else "FAIL_SOURCE_FEASIBILITY"
        )
    )

    summary: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D008_ID,
        "status": status,
        "evidence_class": "SOURCE_FEASIBILITY_NO_RETURN_OUTCOMES",
        "sample_months": months,
        "all_four_have_passing_candidate": all_pass,
        "classification_semantics_stable": stable_semantics,
        "all_four_direct_isin": direct_isin,
        "full_historical_scan_authorized": full_scan_authorized,
        "direct_point_in_time_sector_promotion_authorized": (
            direct_promotion_authorized
        ),
        "selected_candidates": selected,
        "source_reports": [
            {
                "month": report["month"],
                "source_url": report["source_url"],
                "source_sha256": report["source_sha256"],
                "result_sha256": report["result_sha256"],
                "sheet_names": report["sheet_names"],
                "candidate_count": report["candidate_count"],
                "passing_candidate_count": report[
                    "passing_candidate_count"
                ],
            }
            for report in reports
        ],
        "return_labels_opened": False,
        "model_fit_performed": False,
        "live_capital_allowed": False,
    }
    summary["summary_sha256"] = digest(summary)
    return summary
