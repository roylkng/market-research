"""Archive mutable original issuer daily buyback HTML and reconstruct rounded cash.

Actual wall-clock capture, no first-publication inference, no future price
signal. Absent/unverifiable source yields an immutable blocked receipt.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p025_nav_accretion import (
    REPORT_PATH,
    SOURCE_DIR,
    SOURCE_URL,
    build_cash_nav_sensitivity,
    pinned_prior_sources,
    signed_capture,
    validate_capture,
    validate_cash_nav_result,
)

def _write_once(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise AlphaContractError(f"P025 original source overwritten: {path}")
        return
    path.write_bytes(raw)


def _load(root: Path) -> tuple[dict, bytes, dict, dict, dict]:
    packet = json.loads((root / REPORT_PATH).read_text(encoding="utf-8"))
    receipt_dir = root / SOURCE_DIR / "receipts"
    items = []
    for path in sorted(receipt_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("receipt_sha256") == packet["issuer_page_receipt_sha256"]:
            items.append(data)
    if len(items) != 1:
        raise AlphaContractError("P025 archived original issuer HTML receipt ambiguous")
    receipt = items[0]
    raw = (root / receipt["original_issuer_raw_html_path"]).read_bytes()
    validate_capture(receipt, raw)
    prior, refs = pinned_prior_sources(root)
    validate_cash_nav_result(packet, raw=raw, receipt=receipt, prior=prior,
                             references=refs)
    return packet, raw, receipt, prior, refs


def _get_source(url: str) -> tuple[int, bytes | None]:
    if url != SOURCE_URL:
        raise AlphaContractError("P025 cannot access off-issuer source")
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"},
        timeout=35,
        allow_redirects=False,
    )
    return response.status_code, response.content if response.status_code == 200 else None


def run(root: Path, *, run_id: str, fetch=_get_source, now=None) -> dict:
    if not run_id or any(x in run_id for x in ("/", "\\", "..")):
        raise AlphaContractError("P025 unsafe source receipt name")
    if (root / REPORT_PATH).is_file():
        sealed, _, _, _, _ = _load(root)
        return {
            "state": "ORIGINAL_ISSUER_BUYBACK_HTML_ALREADY_VERIFIED",
            "report_sha256": sealed["report_sha256"],
            "new_source_capture": False,
            "live_capital_allowed": False,
        }
    clock = now or (lambda: datetime.now(UTC))
    captured = clock().astimezone(UTC).isoformat()
    status, raw, error = None, None, None
    try:
        status, raw = fetch(SOURCE_URL)
        captured = clock().astimezone(UTC).isoformat()
    except (requests.RequestException, OSError) as exc:
        captured = clock().astimezone(UTC).isoformat()
        error = type(exc).__name__
    attempt = {
        "schema_version": 1,
        "source_url": SOURCE_URL,
        "actual_retrieval_utc": captured,
        "http_status": status,
        "state": "BLOCKED_ISSUER_SOURCE_HTTP",
        "source_sha256": None,
        "signed_source_receipt": None,
        "source_error": error,
        "live_capital_allowed": False,
    }
    receipt = None
    if status == 200 and raw is not None:
        try:
            receipt = signed_capture(raw, observed_at_utc=captured)
        except (AlphaContractError, ValueError, UnicodeError) as exc:
            attempt["state"] = "BLOCKED_ISSUER_DAILY_ACTIVITY_VALIDATION"
            attempt["source_error"] = type(exc).__name__
        else:
            _write_once(root / receipt["original_issuer_raw_html_path"], raw)
            attempt.update({
                "state": "SOURCE_VALIDATED_RAW_BYTES_ARCHIVED",
                "source_sha256": receipt["source_sha256"],
                "signed_source_receipt": receipt["receipt_sha256"],
                "source_error": None,
            })
            _write_once(
                root / SOURCE_DIR / "receipts" / f"{run_id}.json",
                (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode(),
            )
    attempt["attempt_sha256"] = digest(attempt)
    _write_once(
        root / SOURCE_DIR / "attempts" / f"{run_id}.json",
        (json.dumps(attempt, indent=2, sort_keys=True) + "\n").encode(),
    )
    if receipt is None:
        return {
            "state": attempt["state"],
            "http_status": status,
            "source_error": error or attempt["source_error"],
            "report_created": False,
            "live_capital_allowed": False,
        }
    prior, refs = pinned_prior_sources(root)
    report = build_cash_nav_sensitivity(raw, receipt, prior, refs)
    validate_cash_nav_result(report, raw=raw, receipt=receipt, prior=prior,
                             references=refs)
    _write_once(
        root / REPORT_PATH,
        (json.dumps(report, indent=2, sort_keys=True) + "\n").encode(),
    )
    return {
        "state": "SIGNED_ORIGINAL_ISSUER_CASH_NAV_COUNTERFACTUAL_ARCHIVED",
        "report_sha256": report["report_sha256"],
        "source_sha256": receipt["source_sha256"],
        "september_cash_cr_rounded_average": report[
            "sep_estimated_cash_spend_cr_excluding_fees"
        ],
        "incremental_nav_per_share_inr_not_current": report[
            "only_counterfactual_const_NAV_no_other_cash_change"
        ]["sept_increment_inr_per_share_not_observed"],
        "live_capital_allowed": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--run-id", default="local")
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    if args.check:
        try:
            report, _, _, _, _ = _load(args.repo_root)
        except FileNotFoundError:
            print(json.dumps({
                "state": "P025_SOURCE_NOT_YET_SEALED",
                "live_capital_allowed": False,
            }))
            return 0
        print(json.dumps({
            "state": "ORIGINAL_ISSUER_SOURCE_NAV_ARITHMETIC_REPLAY_VERIFIED",
            "report_sha256": report["report_sha256"],
            "live_capital_allowed": False,
        }, sort_keys=True))
        return 0
    print(json.dumps(run(args.repo_root, run_id=args.run_id), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
