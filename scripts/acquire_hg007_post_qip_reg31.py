"""Acquire one original post-QIP INOXGREEN NSE Reg31 master + XBRL source.

Reuse normal H023 NSE filing session setup, with no proxy/alternate host or
403 bypass. An unavailable September post-allotment filing stays blocked.
No brokerage orders, portfolio eligibility or target price is produced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from marketlab.h023_acquisition import master_session, xbrl_session
from marketlab.hg007_reg31_check import (
    MASTER_URL,
    MAX_MASTER_BYTES,
    MAX_XBRL_BYTES,
    _official_xbrl_url,
    build_post_qip_shareholding_evidence,
    choose_post_qip_filing,
)

USER_AGENT = "marketlab-hg007-source-only/1.0"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _get_exact(session: requests.Session, url: str, *, params: dict | None,
               max_bytes: int) -> tuple[bytes | None, str, str]:
    try:
        response = session.get(
            url, params=params, timeout=28, allow_redirects=False
        )
    except requests.RequestException as exc:
        return None, "FETCH_FAILED", type(exc).__name__
    if response.status_code in (401, 403, 429):
        return None, "BLOCKED", f"HTTP_{response.status_code}_NO_ACCESS_BYPASS"
    if response.status_code != 200:
        return None, "FETCH_FAILED", f"HTTP_{response.status_code}_OR_UNFOLLOWED_REDIRECT"
    if getattr(response, "url", url) not in (
        url,
        "https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol=INOXGREEN",
    ):
        return None, "FETCH_FAILED", "EXACT_ORIGINAL_SOURCE_HOST_URL_MISMATCH"
    data = response.content
    if not isinstance(data, bytes) or len(data) == 0 or len(data) > max_bytes:
        return None, "FETCH_FAILED", "ORIGINAL_RESPONSE_TOO_LARGE_OR_EMPTY"
    return data, "OK", "HTTP_200_ORIGINAL_BYTES_OBSERVED"


def acquire_exact_reg31() -> tuple[dict, bytes | None, bytes | None]:
    try:
        master = master_session(timeout=12)
    except requests.RequestException as exc:
        result = build_post_qip_shareholding_evidence(
            master_raw=None, xbrl_raw=None,
            master_status="BLOCKED", xbrl_status="NOT_ATTEMPTED",
            observed_at_utc=_now(),
            source_message=f"NSE_MASTER_SESSION_INITIALIZATION_{type(exc).__name__}",
        )
        return result, None, None
    raw_master, master_status, message = _get_exact(
        master, MASTER_URL,
        params={"index":"equities","symbol":"INOXGREEN"},
        max_bytes=MAX_MASTER_BYTES,
    )
    raw_xml = None
    xml_status = "NOT_ATTEMPTED"
    if raw_master is not None:
        try:
            chosen = choose_post_qip_filing(
                raw_master, observed_at_utc=_now()
            )
        except (TypeError, ValueError) as exc:
            # Source may be HTTP 200 HTML or an unrecognized schema; never
            # relabel source as a verified, empty official filing list.
            message = f"NSE_MASTER_SCHEMA_REJECTED_{type(exc).__name__}"
            raw_master = None
            master_status = "FETCH_FAILED"
        else:
            if chosen is not None:
                link = chosen["xbrl_url"]
                if not _official_xbrl_url(link):
                    raise ValueError("NSE XBRL link host was not independently approved")
                archive = xbrl_session()
                raw_xml, xml_status, source_reason = _get_exact(
                    archive, link, params=None, max_bytes=MAX_XBRL_BYTES
                )
                message = f"{message}; XBRL_{source_reason}"
    result = build_post_qip_shareholding_evidence(
        master_raw=raw_master, xbrl_raw=raw_xml,
        master_status=master_status, xbrl_status=xml_status,
        observed_at_utc=_now(), source_message=message,
    )
    return result, raw_master, raw_xml


def write_source_receipt(root: Path, report: dict, master: bytes | None,
                         xbrl: bytes | None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, raw, expected in (
        ("master", master, report["master_original_raw_sha256"]),
        ("xbrl", xbrl, report["xbrl_original_raw_sha256"]),
    ):
        if raw is None:
            if expected is not None:
                raise ValueError(f"{name}: original SHA without observed bytes")
            continue
        sha = hashlib.sha256(raw).hexdigest()
        if sha != expected:
            raise ValueError(f"{name}: original bytes digest mismatch")
        extension = ".json" if name == "master" else ".xml"
        path = root / "raw" / "sha256" / f"{sha}{extension}"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("immutable NSE Reg31 raw-byte collision")
        path.write_bytes(raw)
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError("NSE Reg31 raw byte retention failed")
    (root/"observation-v1.json").write_text(
        json.dumps(report, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)+"\n",
        encoding="utf-8",
    )
    (root/"run-receipt-v1.json").write_text(json.dumps({
        "report_id":report["report_id"],
        "observed_at_utc":report["observed_at_utc"],
        "capture_source_status":report["evidence_status"],
        "master_raw_sha256":report["master_original_raw_sha256"],
        "xbrl_raw_sha256":report["xbrl_original_raw_sha256"],
        "workflow_run_id":os.environ.get("GITHUB_RUN_ID"),
        "workflow_attempt":os.environ.get("GITHUB_RUN_ATTEMPT"),
        "live_capital_allowed":False,
    },sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir",type=Path,required=True)
    args=parser.parse_args()
    report, master, xbrl=acquire_exact_reg31()
    write_source_receipt(args.out_dir,report,master,xbrl)
    print(json.dumps({
        "report_id":report["report_id"],
        "source_state":report["evidence_status"],
        "reported_share_counts":report["reported_share_counts"],
        "reported_governance_state":(
            report["reported_promoter_and_pledge_context"]["parser_status"]
            if report["reported_promoter_and_pledge_context"] else None
        ),
        "master_raw_sha256":report["master_original_raw_sha256"],
        "xbrl_raw_sha256":report["xbrl_original_raw_sha256"],
        "live_capital_allowed":False,
    },sort_keys=True))


if __name__ == "__main__":
    main()
