"""One issuer-only NSE shareholding source probe, including special QIP-date reports.

Reuses existing H023 source sessions with one fetch attempt per endpoint.
No alternate issuer, bypass, inferred pledged quantity or trading outcome.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.h023_acquisition import (
    H023AcquisitionError,
    fetch_master,
    fetch_xbrl,
    master_session,
    xbrl_session,
)
from marketlab.hg007_ownership_source import (
    AUDIT_ID,
    NSE_MASTER_URL,
    _archive_url,
    _nse_master_url,
    evaluate_source_xbrl,
    select_latest_dated_master_source,
    validated_receipt,
)

RECEIPT_ID = "HG007-P010-ORIGINAL-OWNERSHIP-SOURCE-CUSTODY-v1"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _receipt(
    state: str,
    *,
    reason: str,
    master: dict | None = None,
    latest: dict | None = None,
    reviewed: dict | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "receipt_id": RECEIPT_ID,
        "issuer_symbol": "INOXGREEN",
        "issuer_isin": "INE510W01014",
        "original_source_api": NSE_MASTER_URL,
        "attempt_recorded_utc": _now(),
        "state": state,
        "source_failure_or_limitation": reason,
        "master_source_receipt": master,
        "latest_original_master_record": latest,
        "dated_original_xbrl_result": reviewed,
        "current_fully_diluted_share_count_confirmed": False,
        "current_pledged_promoter_share_quantity_confirmed": False,
        "official_governance_pledge_flag_by_report_date_only": True,
        "independent_governance_review_complete": False,
        "returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def acquire_source(*, timeout: float = 18.0) -> tuple[dict, dict[str, bytes]]:
    if type(timeout) not in (int, float) or not 5 <= timeout <= 40:
        raise ValueError("official source timeout must be 5-40 seconds")
    try:
        session = master_session(timeout=timeout)
        response = fetch_master(session, symbol="INOXGREEN", timeout=timeout, attempts=1)
        if not _nse_master_url(response.url) or getattr(response, "history", None):
            raise ValueError("NSE master redirected away from approved exact endpoint")
        raw_master = response.content
        as_of = _now()
        latest = select_latest_dated_master_source(
            raw_master, captured_at_utc=as_of
        )
    except (requests.RequestException, H023AcquisitionError, ValueError, TypeError) as exc:
        return _receipt(
            "NSE_MASTER_SOURCE_UNAVAILABLE",
            reason=f"{type(exc).__name__}: {str(exc)[:300]}",
        ), {}
    master_receipt = {
        "url": response.url, "http_status": response.status_code,
        "captured_at_utc": as_of,
        "raw_sha256": _hash(raw_master), "raw_byte_count": len(raw_master),
    }
    if not latest["source_is_post_qip_as_of_report_date"]:
        return _receipt(
            "ONLY_PRE_QIP_SHAREHOLDING_SOURCE",
            reason="Original NSE master latest available report predates Sep 29 QIP",
            master=master_receipt, latest=latest,
        ), {"master.json": raw_master}
    selected_url = latest["selected_source"]["xbrl_url"]
    try:
        if not _archive_url(selected_url):
            raise ValueError("NSE XBRL source outside approved archives")
        document = fetch_xbrl(
            xbrl_session(), url=selected_url, timeout=timeout, attempts=1
        )
        if document.url != selected_url or getattr(document, "history", None):
            raise ValueError("NSE XBRL HTTP redirect not an original source")
        raw_xml = document.content
        audited = evaluate_source_xbrl(
            latest, raw_xml, xbrl_captured_at_utc=_now()
        )
        validated_receipt(audited)
    except (requests.RequestException, H023AcquisitionError, ValueError, TypeError) as exc:
        return _receipt(
            "POST_QIP_MASTER_FOUND_XBRL_UNAVAILABLE",
            reason=f"{type(exc).__name__}: {str(exc)[:300]}",
            master=master_receipt, latest=latest,
        ), {"master.json": raw_master}
    return _receipt(
        "ORIGINAL_POST_QIP_MASTER_XBRL_RETAINED",
        reason="Original report as-of date, not current FD/pledged-count certification",
        master=master_receipt, latest=latest, reviewed=audited,
    ), {"master.json": raw_master, "original-xbrl.xml": raw_xml}


def retain_original(out: Path, receipt: dict, files: dict[str, bytes]) -> None:
    if receipt.get("receipt_id") != RECEIPT_ID:
        raise ValueError("unrecognized NSE ownership original receipt")
    master = files.get("master.json")
    evidence = receipt.get("master_source_receipt")
    if master is not None and (
        not isinstance(evidence, dict) or _hash(master) != evidence.get("raw_sha256")
    ):
        raise ValueError("original NSE master hash not present or incorrect")
    xbrl = files.get("original-xbrl.xml")
    audited = receipt.get("dated_original_xbrl_result")
    if xbrl is not None:
        if (
            not isinstance(audited, dict)
            or audited.get("audit_id") != AUDIT_ID
            or _hash(xbrl) != audited.get("original_xbrl_sha256")
        ):
            raise ValueError("original source XBRL hash disagrees with report")
        validated_receipt(audited)
    elif audited is not None:
        raise ValueError("original source XBRL report without original bytes")
    out.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        if name not in ("master.json", "original-xbrl.xml"):
            raise ValueError("unknown source file")
        suffix = ".json" if name == "master.json" else ".xml"
        target = out / "raw" / "sha256" / f"{_hash(raw)}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != raw:
            raise ValueError("content addressed source already exists with different bytes")
        target.write_bytes(raw)
        if _hash(target.read_bytes()) != _hash(raw):
            raise ValueError("original retained NSE source SHA check failed")
    dest = out / "receipt.json"
    serialized = json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if dest.exists() and dest.read_text(encoding="utf-8") != serialized:
        raise ValueError("original receipt overwrite prohibited")
    dest.write_text(serialized, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=18.0)
    args = parser.parse_args()
    receipt, originals = acquire_source(timeout=args.timeout)
    retain_original(args.out_dir, receipt, originals)
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
