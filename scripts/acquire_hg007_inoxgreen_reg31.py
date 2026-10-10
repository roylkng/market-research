"""Targeted original NSE Reg31 XBRL acquisition for INOXGREEN post-QIP risk.

Reuse existing H023 official NSE master/revision selection and GF001
governance semantics. The secondary 29 September pledge estimate is an
UNVERIFIED REVIEW LEAD, not an exchange-verified state or a stock score.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests

from marketlab.gf001_governance import GF001GovernanceError, parse_current_governance_xbrl
from marketlab.h023_acquisition import (
    H023AcquisitionError,
    discover_standard_quarter_sources,
    fetch_master,
    master_session,
    xbrl_session,
)
from marketlab.h023_prospective import validate_source

CAPTURE_ID = "HG007-P010-INOXGREEN-SEP2026-OFFICIAL-REG31-REVIEW-v1"
EXPECTED_SYMBOL = "INOXGREEN"
EXPECTED_ISIN = "INE510W01014"
EXPECTED_QUARTER = "2026-09-30"
MASTER_URL = "https://www.nseindia.com/api/corporate-share-holdings-master"
APPROVED_ORIGINAL_HOSTS = {"nsearchives.nseindia.com", "archives.nseindia.com"}
MAX_ORIGINAL_BYTES = 3_000_000
P008_PATH = Path(
    "research/hg007/inoxgreen-sep2026-qip/post-qip-market-cap-audit-v1.json"
)
P008_GIT_BLOB_SHA = "e31efd712fdfae378d7be8263883c521f1411d43"

# Secondary-only review lead; not original exchange evidence.
SECONDARY_LEAD = {
    "reported_as_of": "2026-09-29",
    "source": (
        "https://trendlyne.com/equity/share-holding/1127763/INOXGREEN/"
        "latest/inox-green-energy-services-ltd/"
    ),
    "source_classification": "THIRD_PARTY_UNCONFIRMED_GOVERNANCE_DISCOVERY",
    "reported_promoter_shares_unchanged_vs_june": 225_317_291,
    "reported_promoter_share_percentage": 53.70,
    "reported_promoter_pledged_shares": 4_900_000,
    "reported_authum_listed_issuer_shares": 6_018_368,
    "all_fields_original_nse_reg31_confirmed": False,
}


def _blob_sha(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _original_xbrl_allowed(url: str) -> bool:
    if not isinstance(url, str):
        return False
    try:
        p = urlsplit(url)
    except ValueError:
        return False
    return (
        p.scheme == "https"
        and p.hostname in APPROVED_ORIGINAL_HOSTS
        and p.username is None
        and p.password is None
        and p.port in (None, 443)
        and not p.fragment
        and p.path.lower().endswith((".xml", ".html", ".xhtml"))
    )


def _verified_qip(root: Path) -> dict[str, Any]:
    raw = (root / P008_PATH).read_bytes()
    if _blob_sha(raw) != P008_GIT_BLOB_SHA:
        raise ValueError("original QIP capitalization source changed")
    source = json.loads(raw)
    if (
        source.get("audit_id") != "HG007-P008-INOXGREEN-QIP-DATED-CAPITALIZATION-v1"
        or source.get("symbol") != EXPECTED_SYMBOL
        or source.get("original_september_2026_nse_qip", {}).get(
            "post_qip_issued_basic_shares"
        ) != 419_602_518
        or source.get("post_qip_fully_diluted_market_cap_authorized") is not False
        or source.get("live_capital_allowed") is not False
    ):
        raise ValueError("original QIP issuer sharecount/capital boundary changed")
    return source


def _source_selection(original_master: bytes) -> dict[str, Any] | None:
    try:
        payload = json.loads(original_master)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("original NSE master source is not JSON") from exc
    entries = discover_standard_quarter_sources(payload, symbol=EXPECTED_SYMBOL)
    september = [x for x in entries if x["report_date"] == EXPECTED_QUARTER]
    if not september:
        return None
    last_broadcast = max(x["broadcast_at_utc"] for x in september)
    latest = [x for x in september if x["broadcast_at_utc"] == last_broadcast]
    if len(latest) != 1:
        raise ValueError("conflicting latest original NSE September Reg31 revision")
    source = latest[0]
    validate_source(source)
    if not _original_xbrl_allowed(str(source["xbrl_url"])):
        raise ValueError("NSE shareholding original XBRL source URL not approved")
    return source


def _receipt(
    *,
    state: str,
    timestamp: str,
    master_bytes: bytes | None,
    selected: dict[str, Any] | None,
    xbrl_bytes: bytes | None,
    governance: dict[str, Any] | None,
    error: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "review_id": CAPTURE_ID,
        "classification": "INDEPENDENT_NSE_SHAREHOLDING_DISCOVERY_NOT_STOCK_SCORE",
        "symbol": EXPECTED_SYMBOL,
        "isin": EXPECTED_ISIN,
        "expected_official_report_date": EXPECTED_QUARTER,
        "capture_at_utc": timestamp,
        "capture_state": state,
        "master_source_url": MASTER_URL,
        "master_source_raw_sha256": (
            hashlib.sha256(master_bytes).hexdigest() if master_bytes is not None else None
        ),
        "master_source_byte_count": len(master_bytes) if master_bytes is not None else None,
        "selected_original_nse_reg31": selected,
        "original_xbrl_sha256": (
            hashlib.sha256(xbrl_bytes).hexdigest() if xbrl_bytes is not None else None
        ),
        "original_xbrl_byte_count": len(xbrl_bytes) if xbrl_bytes is not None else None,
        "issuer_governance_extracted_from_original_xbrl": governance,
        "unverified_third_party_pledge_research_lead": SECONDARY_LEAD,
        "june_2026_issuer_shareholding_source": (
            "https://www.inoxgreen.com/PDF/SHP_30JUNE2026R.html"
        ),
        "original_june_xbrl_historical_pledge_comparison_completed": False,
        "independently_confirmed_new_promoter_pledged_share_count": None,
        "original_exchange_pledge_boolean_verified": (
            governance is not None
            and governance.get("parser_status") == "CORE_READY"
            and isinstance(governance.get("promoter_encumbrance", {}).get("pledge"), bool)
        ),
        "full_current_esop_option_count_verified": False,
        "current_post_qip_fully_diluted_shares_verified": False,
        "conflict_of_interest_or_related_party_conclusion_authorized": False,
        "hg002_original_governance_clean_cohort_edited": False,
        "new_stock_investment_recommendation_authorized": False,
        "expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
        "error_or_blocker": error,
    }


def acquire_september_original(
    *,
    repo_root: Path,
    timeout: float = 18.0,
) -> tuple[dict[str, Any], bytes | None, bytes | None]:
    """One bounded official request per source: preserve 403, never substitute provider."""
    _verified_qip(repo_root)
    if not 0 < timeout <= 60:
        raise ValueError("NSE source timeout outside approved range")
    captured = _utc_now()
    try:
        master = master_session(timeout)
        response = fetch_master(
            master, symbol=EXPECTED_SYMBOL, timeout=timeout, attempts=1
        )
    except (H023AcquisitionError, requests.RequestException) as exc:
        return _receipt(
            state="OFFICIAL_NSE_MASTER_UNAVAILABLE",
            timestamp=captured,
            master_bytes=None, selected=None, xbrl_bytes=None,
            governance=None, error=f"{type(exc).__name__}: {exc}",
        ), None, None
    if response.status_code != 200 or getattr(response, "history", []):
        raise ValueError("unverified NSE master redirect/http source")
    original_master = response.content
    try:
        chosen = _source_selection(original_master)
    except (ValueError, TypeError, H023AcquisitionError) as exc:
        return _receipt(
            state="OFFICIAL_NSE_MASTER_INVALID_OR_CONFLICTING",
            timestamp=captured, master_bytes=original_master,
            selected=None, xbrl_bytes=None, governance=None,
            error=f"{type(exc).__name__}: {exc}",
        ), original_master, None
    if chosen is None:
        return _receipt(
            state="OFFICIAL_SEP2026_STANDARD_QUARTER_REG31_NOT_YET_DISCOVERED",
            timestamp=captured, master_bytes=original_master,
            selected=None, xbrl_bytes=None, governance=None,
            error="No unambiguous NSE 30-SEP-2026 standard-quarter original XBRL",
        ), original_master, None

    if datetime.fromisoformat(chosen["broadcast_at_utc"]) > datetime.now(UTC):
        raise ValueError("NSE future broadcast source not yet observationally eligible")
    url = str(chosen["xbrl_url"])
    try:
        response = xbrl_session().get(url, timeout=timeout, allow_redirects=False)
    except requests.RequestException as exc:
        return _receipt(
            state="OFFICIAL_NSE_REG31_SOURCE_FETCH_FAILED",
            timestamp=captured, master_bytes=original_master,
            selected=chosen, xbrl_bytes=None, governance=None,
            error=f"{type(exc).__name__}: {exc}",
        ), original_master, None
    if (
        response.status_code != 200
        or getattr(response, "url", url) != url
        or getattr(response, "history", [])
        or not response.content
    ):
        return _receipt(
            state="OFFICIAL_NSE_REG31_SOURCE_ACCESS_BLOCKED_OR_REDIRECTED",
            timestamp=captured, master_bytes=original_master,
            selected=chosen, xbrl_bytes=None, governance=None,
            error=f"HTTP_{response.status_code}_NO_ALTERNATE_OR_BYPASS",
        ), original_master, None
    original = response.content
    if len(original) > MAX_ORIGINAL_BYTES:
        return _receipt(
            state="OFFICIAL_NSE_REG31_SOURCE_TOO_LARGE",
            timestamp=captured, master_bytes=original_master,
            selected=chosen, xbrl_bytes=None, governance=None,
            error="original NSE XBRL oversized; cannot safely parse",
        ), original_master, None

    try:
        parsed = parse_current_governance_xbrl(
            original,
            symbol=EXPECTED_SYMBOL,
            report_date=EXPECTED_QUARTER,
            source_url=url,
        )
    except (GF001GovernanceError, ValueError, TypeError) as exc:
        return _receipt(
            state="OFFICIAL_NSE_REG31_PRESENT_GOVERNANCE_PARSE_FAILED",
            timestamp=captured, master_bytes=original_master,
            selected=chosen, xbrl_bytes=original, governance=None,
            error=f"{type(exc).__name__}: {exc}",
        ), original_master, original

    if (
        parsed.get("raw_sha256") != hashlib.sha256(original).hexdigest()
        or parsed.get("symbol") != EXPECTED_SYMBOL
        or parsed.get("report_date") != EXPECTED_QUARTER
        or parsed.get("source_url") != url
        or parsed.get("parser_status") != "CORE_READY"
    ):
        state = "OFFICIAL_NSE_REG31_PRESENT_GOVERNANCE_INCOMPLETE"
    else:
        state = "OFFICIAL_NSE_REG31_CORE_GOVERNANCE_EVIDENCE_READY"
    return _receipt(
        state=state,
        timestamp=captured, master_bytes=original_master,
        selected=chosen, xbrl_bytes=original, governance=parsed,
        error=None if state.endswith("READY") else "promoter/public or pledge source incomplete",
    ), original_master, original


def save_observation(
    root: Path,
    report: dict[str, Any],
    master_bytes: bytes | None,
    xbrl_bytes: bytes | None,
) -> None:
    if report.get("review_id") != CAPTURE_ID:
        raise ValueError("invalid official issuer governance receipt")
    root.mkdir(parents=True, exist_ok=True)
    for label, raw, key, ext in (
        ("master", master_bytes, "master_source_raw_sha256", ".json"),
        ("original_xbrl", xbrl_bytes, "original_xbrl_sha256", ".xml"),
    ):
        if raw is None:
            if report.get(key) is not None:
                raise ValueError("no original source but claimed source hash")
            continue
        sha = hashlib.sha256(raw).hexdigest()
        if report.get(key) != sha:
            raise ValueError("original NSE source SHA receipt mismatch")
        target = root / "raw" / label / f"{sha}{ext}"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != raw:
            raise ValueError("immutable original NSE shareholding source collision")
        target.write_bytes(raw)
    destination = root / "attempt.json"
    destination.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    receipt, master, xbrl = acquire_september_original(repo_root=args.repo_root)
    save_observation(args.out_dir, receipt, master, xbrl)
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
