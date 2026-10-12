"""Source VEDL October 14 ex-date from the official NSE corporate-action API.

The original issuer PDF already establishes INR5 and Oct14 RECORD date.
This collector does not claim a real stock fill, shareholder entitlement
or adjusted H021 20/60-session outcome.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from marketlab.h021_vedl_exdate import (
    EXACT_NSE_API,
    build_official_vedl_exdate_packet,
)

PUBLIC_NSE_PAGE = (
    "https://www.nseindia.com/companies-listing/"
    "corporate-filings-actions?symbol=VEDL&tabIndex=equity"
)


def _utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _failure(url: str, status: str, http: int | None, reason: str) -> dict:
    return {
        "url": url,
        "status": status,
        "http_status": http,
        "captured_at_utc": _utc(),
        "raw_sha256": None,
        "error": reason,
    }


def probe_public_nse_actions() -> tuple[dict[str, Any], bytes | None]:
    """Public-site session init only. No 403 retry, redirect, or proxy bypass."""
    headers = {
        "User-Agent": "marketlab-h021-original-nse-event-research/1.0",
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    }
    with requests.Session() as session:
        session.headers.update(headers)
        try:
            initial = session.get(
                PUBLIC_NSE_PAGE, allow_redirects=False, timeout=25
            )
            if initial.status_code != 200:
                http = initial.status_code
                status = (
                    "ACCESS_BLOCKED" if http in (401, 403, 429)
                    else "NOT_PUBLISHED" if http == 404 else "FETCH_FAILED"
                )
                return (
                    _failure(
                        EXACT_NSE_API, status, http,
                        f"PUBLIC_NSE_COOKIE_SESSION_HTTP_{http}_NO_ACCESS_BYPASS",
                    ),
                    None,
                )
            response = session.get(
                EXACT_NSE_API, allow_redirects=False, timeout=25
            )
            http = response.status_code
            if getattr(response, "url", EXACT_NSE_API) != EXACT_NSE_API:
                return (
                    _failure(
                        EXACT_NSE_API, "FETCH_FAILED", http,
                        "OFFICIAL_ACTION_URL_REDIRECTED_OR_CHANGED",
                    ),
                    None,
                )
            if http == 200 and response.content:
                original = response.content
                return ({
                    "url": EXACT_NSE_API,
                    "status": "OK",
                    "http_status": http,
                    "captured_at_utc": _utc(),
                    "raw_sha256": hashlib.sha256(original).hexdigest(),
                    "error": None,
                }, original)
            status = (
                "ACCESS_BLOCKED" if http in (401, 403, 429)
                else "NOT_PUBLISHED" if http == 404 else "FETCH_FAILED"
            )
            return (_failure(
                EXACT_NSE_API, status, http,
                f"OFFICIAL_CORPORATE_ACTION_HTTP_{http}_NO_SOURCE_SUBSTITUTION",
            ), None)
        except requests.RequestException as exc:
            return (
                _failure(
                    EXACT_NSE_API, "FETCH_FAILED", None,
                    f"ORIGINAL_NSE_REQUEST_{type(exc).__name__}",
                ),
                None,
            )


def save_attempt(
    *,
    root: Path,
    source_receipt: dict[str, Any],
    raw: bytes | None,
    report: dict[str, Any],
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        sha = hashlib.sha256(raw).hexdigest()
        if report.get("source_raw_sha256") != sha:
            raise ValueError("NSE original event bytes differ from research report")
        location = root / "raw" / "sha256" / f"{sha}.json"
        location.parent.mkdir(parents=True, exist_ok=True)
        if location.exists() and location.read_bytes() != raw:
            raise ValueError("NSE original action raw source SHA collision")
        location.write_bytes(raw)
    if (
        report.get("live_capital_allowed") is not False
        or report.get("dividend_cash_entitlement_assessed_or_paid") is not False
        or report.get("twenty_sixty_session_outcomes_opened") is not False
    ):
        raise ValueError("source probe cannot authorize capital, entitlement or returns")
    (root / "source-receipt.json").write_text(
        json.dumps(source_receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (root / "event-date-screen.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    source, raw = probe_public_nse_actions()
    report = build_official_vedl_exdate_packet(
        root=args.repo_root, raw=raw, source_receipt=source
    )
    save_attempt(root=args.out_dir, source_receipt=source, raw=raw, report=report)
    print(json.dumps({
        "review_id": report["review_id"],
        "source_state": report["source_state"],
        "source_sha256": report["source_raw_sha256"],
        "original_exchange_ex_date_verified": report[
            "original_exchange_ex_date_verified"
        ],
        "ex_date": (
            report["official_matching_row"]["exchange_ex_date"]
            if report["official_matching_row"] else None
        ),
        "retrieved_before_ex_open": report["source_retrieved_before_oct14_ex_open"],
        "hypothetical_entitlement_assessed": report[
            "dividend_cash_entitlement_assessed_or_paid"
        ],
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
