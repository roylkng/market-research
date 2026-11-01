"""Version-pinned H021 weekly calendar selection, without rewriting the original v1.

Only official NSE circular NSE/CMTR/76941 and H021-P023 may supersede the
previously unresolved Sunday session. The source calendar remains immutable.
No prices, returns, or consensus observations are synthesized here.
"""

from __future__ import annotations

from datetime import date
from typing import Any

BASE_VERSION = "NSE-CM-FY27Q2-v1"
NOV08_VERSION = "NSE-CM-FY27Q2-v2-Nov08-Muhurat"
NOV08_EFFECTIVE_FROM = date(2026, 11, 2)
BASE_SHA256 = "2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce"
NOV08_SHA256 = "d3de65ceb2038f8ea96d455afb272a9d72f4a411af7d76d6b5bf1941c2bb5266"
BASE_GIT_BLOB = "9ac614820a67b0f7b20d8170d15b84df3c996b62"
NOV08_GIT_BLOB = "fd151df6ad8fcee88fff6d9c3ac700c0d38c9153"
NOV08_CIRCULAR_SHA256 = "ce94ee1c54d98eccdf3c30fa0673ae2b6a49ea4ed4a72fb83d826f4359f71d58"
NOV08_AMENDMENT_SHA256 = "618f143a76696cae500dec137db834c040fb861851998e2257d8f53bcc43f783"
NOV08_CIRCULAR_URL = "https://nsearchives.nseindia.com/content/circulars/CMTR76941.pdf"

BASE_PATH = (
    "research/prospective/calendars/FY27-Q2-2026-09-06/"
    "NSE-CM-FY27Q2-v1.json"
)
NOV08_PATH = (
    "research/prospective/calendars/FY27-Q2-2026-09-06/"
    "NSE-CM-FY27Q2-v2-Nov08-Muhurat.json"
)


def _expected(capture_date_ist: str) -> tuple[str, str, str]:
    day = date.fromisoformat(capture_date_ist)
    if day >= NOV08_EFFECTIVE_FROM:
        return NOV08_VERSION, NOV08_SHA256, NOV08_GIT_BLOB
    return BASE_VERSION, BASE_SHA256, BASE_GIT_BLOB


def expected_calendar_path(capture_date_ist: str) -> str:
    """Choose an effective calendar by actual IST date, never by returns."""
    return NOV08_PATH if date.fromisoformat(capture_date_ist) >= NOV08_EFFECTIVE_FROM else BASE_PATH


def expected_calendar_git_blob(capture_date_ist: str) -> str:
    return _expected(capture_date_ist)[2]


def validate_effective_h021_calendar(
    calendar: dict[str, Any], *, capture_date_ist: str
) -> None:
    """Validate the *immutable* identity of the calendar used for a new capture."""
    version, sha, _ = _expected(capture_date_ist)
    if calendar.get("version") != version or calendar.get("sha256") != sha:
        raise ValueError("H021 weekly calendar version/digest differs from reviewed effective calendar")
    if version != NOV08_VERSION:
        return
    provenance = calendar.get("supersession")
    if not isinstance(provenance, dict):
        raise TypeError("H021 November calendar supersession provenance missing")
    required = {
        "effective_from_ist": NOV08_EFFECTIVE_FROM.isoformat(),
        "immutable_base_calendar_sha256": BASE_SHA256,
        "immutable_base_calendar_git_blob_sha": BASE_GIT_BLOB,
        "official_circular_id": "NSE/CMTR/76941",
        "original_circular_pdf_sha256": NOV08_CIRCULAR_SHA256,
        "reviewed_h021_source_amendment_sha256": NOV08_AMENDMENT_SHA256,
        "individual_CAS_price_basis_verified": False,
        "no_consensus_or_price_outcomes_opened": True,
    }
    if any(provenance.get(key) != value for key, value in required.items()):
        raise ValueError("H021 Nov 8 calendar provenance differs from reviewed NSE circular")
    special = calendar.get("special_sessions")
    expected_special = {
        "session_date": "2026-11-08",
        "open_timestamp_utc": "2026-11-08T08:50:00Z",
        "close_timestamp_utc": "2026-11-08T10:05:00Z",
        "source_url": NOV08_CIRCULAR_URL,
    }
    if special != [expected_special]:
        raise ValueError("H021 Nov 8 special-session clock or official source changed")
    if calendar.get("unresolved_special_dates") != []:
        raise ValueError("H021 November calendar still has unresolved special sessions")
