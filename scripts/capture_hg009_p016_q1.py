"""Capture and independently replay actual NSE Q1 FY27 original issuer HTML.

The two ACE and ACUTAAS sources are standalone unaudited Q1 financial tables,
not October 15 fully diluted stock capitalizations.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p016_q1_originals import (
    ALLOWED_HOST_PREFIX,
    ATTEMPT_DIR,
    capture_one_q1,
    original_q1_registry,
    verify_q1_receipt,
)

SUMMARY = Path("research/hg009/hg009-p016-q1-source-attestation-v1.json")


def _fetch(url: str) -> tuple[int, bytes | None]:
    if (
        not url.startswith(ALLOWED_HOST_PREFIX)
        or "?" in url
        or ".." in url
    ):
        raise AlphaContractError("P016 fetch only original NSE ixbrl URLs")
    result = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
        },
        timeout=25,
        allow_redirects=False,
    )
    return result.status_code, result.content if result.status_code == 200 else None


def _load(path: Path) -> dict:
    obj = json.loads(path.read_text("utf-8"))
    if not isinstance(obj, dict):
        raise AlphaContractError(f"P016 source receipt malformed {path}")
    return obj


def _first_verified(
    *,
    root: Path,
    issuers: list[dict],
) -> list[dict]:
    results = []
    for issuer in issuers:
        for path in sorted((root / ATTEMPT_DIR).glob(f"*-{issuer['symbol']}.json")):
            receipt = _load(path)
            if receipt.get("symbol") != issuer["symbol"]:
                raise AlphaContractError("P016 original filename/issuer mismatch")
            verify_q1_receipt(receipt, issuer=issuer, root=root)
            if receipt.get("source_verified") is True:
                results.append({
                    "symbol": issuer["symbol"],
                    "isin": issuer["isin"],
                    "receipt_path": str(path.relative_to(root)),
                    "receipt_sha256": receipt["receipt_sha256"],
                    "archived_original_source_path": receipt["archive_path"],
                    "archived_original_source_sha256": receipt["original_raw_sha256"],
                    "observed_actual_capture_utc": receipt["captured_at_utc"],
                    "replayed_source_field_count": len(
                        receipt["verified_statement_fields"]
                    ),
                    "June_basic_share_count_is_not_October_diluted": True,
                })
                break
    return results


def verify_all(root: Path) -> dict:
    registry, sha = original_q1_registry(root)
    issuers = registry["issuer_rows"]
    verified = _first_verified(root=root, issuers=issuers)
    if len({r["symbol"] for r in verified}) != len(verified):
        raise AlphaContractError("P016 original issuer duplicate attestation")
    report = {
        "schema_version": 1,
        "attestation_id": "HG009-P016-Q1FY27-NSE-ORIGINAL-SHARE-AND-INCOME-v1",
        "original_p015_issuer_registry_sha256": sha,
        "original_p015_issuer_registry_git_blob": (
            "eab274ece7d40e65cf1cb69db7632c1e92206f69"
        ),
        "historical_reporting_basis": "STANDALONE_UNAUDITED_Q1FY27",
        "historical_period_end": "2026-06-30",
        "original_issuer_count": len(issuers),
        "original_NSE_HTML_verified_issuer_count": len(verified),
        "original_NSE_HTML_unverified_issuer_count": len(issuers)-len(verified),
        "first_verified_original_sources": verified,
        "not_verified_current_october_diluted_capital": True,
        "current_shareholder_owner_cashflow_not_verified": True,
        "future_return_or_investment_price_target_created": False,
        "live_capital_allowed": False,
    }
    report["attestation_sha256"] = digest(report)
    path = root / SUMMARY
    if path.is_file():
        saved = _load(path)
        if saved != report:
            raise AlphaContractError("P016 original archived attestation immutable drift")
        state = "PREVIOUS_ORIGINAL_SOURCE_VERIFIED"
    elif len(verified) == len(issuers):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        state = "ORIGINAL_SOURCES_ATTESTED_LOCALLY_PENDING_GIT_ANCHOR"
    else:
        state = "INCOMPLETE_ORIGINAL_SOURCE_ATTESTATION"
    return {
        "state": state,
        "verified_issuer_count": len(verified),
        "required_issuer_count": len(issuers),
        "attestation_sha256_if_complete": (
            report["attestation_sha256"] if len(verified) == len(issuers) else None
        ),
        "not_current_diluted_equity": True,
        "live_capital_allowed": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--run-id", required=True)
    p.add_argument("--verify-only", action="store_true")
    args = p.parse_args()
    root = args.repo_root
    registry, _ = original_q1_registry(root)
    if not args.verify_only:
        if not args.run_id.replace("-", "").isalnum():
            raise AlphaContractError("P016 attempt run-id unsafe")
        folder = root / ATTEMPT_DIR
        folder.mkdir(parents=True, exist_ok=True)
        for issuer in registry["issuer_rows"]:
            record = capture_one_q1(
                issuer, fetch=_fetch,
                observe_now=lambda: datetime.now(UTC),
                root=root,
            )
            path = folder / f"{args.run_id}-{issuer['symbol']}.json"
            if path.exists():
                raise AlphaContractError("P016 cannot replace original attempt receipt")
            path.write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    print(json.dumps(verify_all(root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
