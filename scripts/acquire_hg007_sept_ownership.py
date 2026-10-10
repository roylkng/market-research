"""Bounded official September 2026 INOXGREEN NSE shareholding acquisition.

No paid provider or third-party vendor data can fill missing official NSE
source. The published output remains reporting-quarter evidence, not proof
of the 10 October FD share count or exact 4.9m pledge quantity.
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
from marketlab.hg007_sept_ownership import (
    NSE_MASTER_URL,
    build_ownership_snapshot,
    select_official_asof_master,
    validate_ownership_snapshot,
)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _acquire(*, timeout: float) -> tuple[dict, bytes | None, bytes | None]:
    if timeout <= 0 or timeout > 60:
        raise ValueError("official NSE source timeout must be in (0,60]")
    master = None
    xbrl = None
    master_failure = None
    xbrl_failure = None
    observed = _now()

    try:
        session = master_session(timeout)
        response = fetch_master(session, symbol="INOXGREEN", timeout=timeout, attempts=1)
        if not response.url.startswith(NSE_MASTER_URL.split("?")[0]):
            raise H023AcquisitionError("NSE master final response URL changed")
        master = response.content
        observed = _now()
        source, _summary = select_official_asof_master(
            master, captured_at_utc=observed
        )
    except (requests.RequestException, H023AcquisitionError) as exc:
        master_failure = f"{type(exc).__name__}: {exc}"
        source = None
    if master is not None and source is not None:
        try:
            archive = xbrl_session()
            response = fetch_xbrl(
                archive,
                url=source["xbrl_url"],
                timeout=timeout,
                attempts=1,
            )
            if response.url != source["xbrl_url"]:
                raise H023AcquisitionError("NSE XBRL redirected; no alternate source accepted")
            xbrl = response.content
        except (requests.RequestException, H023AcquisitionError) as exc:
            xbrl_failure = f"{type(exc).__name__}: {exc}"

    snapshot = build_ownership_snapshot(
        master_raw=master,
        xbrl_raw=xbrl,
        observed_at_utc=observed,
        master_failure=master_failure,
        xbrl_failure=xbrl_failure,
    )
    validate_ownership_snapshot(snapshot)
    return snapshot, master, xbrl


def _retain(
    out: Path,
    snapshot: dict,
    master: bytes | None,
    xbrl: bytes | None,
) -> None:
    validate_ownership_snapshot(snapshot)
    out.mkdir(parents=True, exist_ok=True)
    for label, raw, suffix in (
        ("master", master, ".json"),
        ("xbrl", xbrl, ".xml"),
    ):
        if raw is None:
            continue
        digest = hashlib.sha256(raw).hexdigest()
        if label == "master" and digest != snapshot["original_official_master_receipt"]["master_original_sha256"]:
            raise ValueError("original NSE master bytes do not match receipt")
        if label == "xbrl" and digest != snapshot["original_official_xbrl_sha256"]:
            raise ValueError("original NSE XBRL bytes do not match receipt")
        target = out / "raw" / label / "sha256" / f"{digest}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != raw:
            raise ValueError("content-addressed original source file collision")
        target.write_bytes(raw)
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("original source failed retention digest verification")
    (out / "sept-2026-source-observation-v1.json").write_text(
        json.dumps(snapshot, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=25)
    args = parser.parse_args()
    report, master, xbrl = _acquire(timeout=args.timeout)
    _retain(args.out_dir, report, master, xbrl)
    print(json.dumps({
        "snapshot_id": report["snapshot_id"],
        "state": report["current_state"],
        "observed_at_utc": report["observed_at_utc"],
        "report_date": report["selected_report_date"],
        "reported_share_counts": report["share_counts_as_of_report_date"],
        "promoter_pledge_boolean": (
            report["governance_as_of_report_date"]["promoter_encumbrance"]["pledge"]
            if report["governance_as_of_report_date"] is not None else None
        ),
        "current_fd_shares_verified": False,
        "pledged_promoter_shares_4900000_verified": False,
        "live_capital_allowed": False,
    }, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
