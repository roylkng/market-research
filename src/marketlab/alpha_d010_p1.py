from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_d010_sources import (
    PROBE_DATES,
    ProbeResponse,
    inspect_csv_response,
)

D010_P1_ID = "AE001-D010-P1-v1"
SHORT_ARCHIVE_PATTERN = (
    "https://nsearchives.nseindia.com/archives/equities/shortSelling/"
    "shortselling_{ddmmyyyy}.csv"
)
DAILY_REPORT_KEYS = ("CM", "SLB", "SLBS")
ALLOWED_METADATA_URL_HOSTS = {
    "www.nseindia.com",
    "nsearchives.nseindia.com",
    "archives.nseindia.com",
}
METADATA_FIELDS = (
    "fileKey",
    "filePath",
    "fileActlName",
    "displayName",
    "tradingDate",
)


@dataclass(frozen=True)
class MetadataProbe:
    key: str
    raw_sha256: str
    payload: object


def short_archive_url(session_date: date) -> str:
    return SHORT_ARCHIVE_PATTERN.format(
        ddmmyyyy=session_date.strftime("%d%m%Y")
    )


def _iter_mappings(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_mappings(child)


def _selected_metadata(row: dict[str, Any]) -> dict[str, str | None]:
    return {
        field: (
            None
            if row.get(field) is None
            else str(row.get(field)).strip()
        )
        for field in METADATA_FIELDS
    }


def _combined_text(row: dict[str, str | None]) -> str:
    return " ".join(
        value
        for value in row.values()
        if isinstance(value, str) and value
    ).casefold()


def _explicit_download_url(
    row: dict[str, str | None],
) -> str | None:
    path = str(row.get("filePath") or "").strip()
    actual = str(row.get("fileActlName") or "").strip()
    if not path:
        return None

    if path.startswith(("https://", "http://")):
        if actual and not path.rstrip("/").endswith(actual):
            candidate = path.rstrip("/") + "/" + actual.lstrip("/")
        else:
            candidate = path
    else:
        return None

    parsed = urlparse(candidate)
    if parsed.scheme != "https":
        return None
    if parsed.hostname not in ALLOWED_METADATA_URL_HOSTS:
        return None
    return candidate


def extract_daily_report_metadata(
    probe: MetadataProbe,
) -> dict[str, Any]:
    if probe.key not in DAILY_REPORT_KEYS:
        raise AlphaContractError(
            f"D010 P1 unexpected daily-reports key: {probe.key}"
        )
    if len(probe.raw_sha256) != 64:
        raise AlphaContractError("D010 P1 metadata raw SHA-256 is required")

    discovered = []
    seen: set[str] = set()
    for mapping in _iter_mappings(probe.payload):
        if not any(field in mapping for field in METADATA_FIELDS):
            continue
        selected = _selected_metadata(mapping)
        key = digest(selected)
        if key in seen:
            continue
        seen.add(key)
        text = _combined_text(selected)
        short_match = ("short" in text and "sell" in text)
        slb_match = (
            "slb" in text
            and ("open" in text or "position" in text)
        )
        if not short_match and not slb_match:
            continue
        discovered.append(
            {
                "metadata": selected,
                "short_selling_match": short_match,
                "slb_open_position_match": slb_match,
                "explicit_download_url": _explicit_download_url(
                    selected
                ),
            }
        )

    return {
        "key": probe.key,
        "raw_sha256": probe.raw_sha256,
        "matched_object_count": len(discovered),
        "matches": discovered,
    }


def summarize_p1(
    *,
    short_attempts: list[dict[str, Any]],
    metadata_results: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_dates = {value.isoformat() for value in PROBE_DATES}
    observed_dates = {
        str(row.get("session_date") or "")
        for row in short_attempts
    }
    if observed_dates != expected_dates:
        raise AlphaContractError(
            "D010 P1 short archive attempts do not cover frozen dates"
        )
    if len(short_attempts) != len(PROBE_DATES):
        raise AlphaContractError(
            "D010 P1 short archive attempts must be one per frozen date"
        )

    short_ready = [
        row
        for row in short_attempts
        if row["response"]["status"] == "READY"
    ]
    short_status = (
        "PROMOTE_P2_HISTORICAL_COVERAGE"
        if len(short_ready) == len(PROBE_DATES)
        else "SHORT_ARCHIVE_NOT_READY_ALL_FROZEN_SESSIONS"
    )

    metadata_keys = [str(row.get("key") or "") for row in metadata_results]
    if sorted(metadata_keys) != sorted(DAILY_REPORT_KEYS):
        raise AlphaContractError(
            "D010 P1 metadata results must cover exact frozen key set"
        )

    short_metadata_matches = []
    slb_metadata_matches = []
    for result in metadata_results:
        for match in result.get("matches", []):
            annotated = {
                "query_key": result["key"],
                **match,
            }
            if match["short_selling_match"]:
                short_metadata_matches.append(annotated)
            if match["slb_open_position_match"]:
                slb_metadata_matches.append(annotated)

    slb_urls = sorted(
        {
            str(row["explicit_download_url"])
            for row in slb_metadata_matches
            if row.get("explicit_download_url")
        }
    )
    if len(slb_urls) == 1:
        slb_status = "UNIQUE_EXPLICIT_METADATA_DOWNLOAD_URL"
    elif not slb_urls:
        slb_status = "NO_EXPLICIT_METADATA_DOWNLOAD_URL"
    else:
        slb_status = "AMBIGUOUS_MULTIPLE_METADATA_DOWNLOAD_URLS"

    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D010_P1_ID,
        "evidence_class": "SOURCE_DISCOVERY_NO_RETURN_OUTCOMES",
        "p0_report_sha256": (
            "eee104e4c41a28170f20fbfdd4f0821a865ccef9404b69a6b0ada0e52b5a0363"
        ),
        "short_selling": {
            "archive_pattern": SHORT_ARCHIVE_PATTERN,
            "probe_count": len(short_attempts),
            "ready_count": len(short_ready),
            "status": short_status,
            "attempts": short_attempts,
            "metadata_match_count": len(short_metadata_matches),
            "metadata_matches": short_metadata_matches,
        },
        "daily_reports_metadata": {
            "query_keys": list(DAILY_REPORT_KEYS),
            "results": metadata_results,
        },
        "slb_open_positions": {
            "metadata_match_count": len(slb_metadata_matches),
            "metadata_matches": slb_metadata_matches,
            "explicit_download_urls": slb_urls,
            "status": slb_status,
            "historical_archive_pattern_promoted": False,
        },
        "return_labels_opened": False,
        "model_fit_performed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report


def metadata_probe_from_raw(
    *,
    key: str,
    raw: bytes,
    payload: object,
) -> MetadataProbe:
    if not raw:
        raise AlphaContractError("D010 P1 metadata raw bytes are empty")
    return MetadataProbe(
        key=key,
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        payload=payload,
    )
