"""Probe official NSE Total Market CSV once, with row-wise fail-closed evidence.

This is a NEW Oct21 source method, not P032's earlier all-or-none parser.
A blocked response is archived as a failed receipt, never as issuer industry.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p033_rowwise import (
    BASE,
    SOURCE,
    archive,
    replay_all,
)
from marketlab.nse import NSEAcquisitionError, NSEClient


def _verify_failures(root: Path) -> int:
    count = 0
    for path in sorted((root / BASE / "attempts").glob("*.json")):
        j = json.loads(path.read_text("utf-8"))
        if (
            j.get("protocol") != "HG009-P033-NSE-TOTALMARKET-ROWWISE-PROVENANCE-v1"
            or j.get("source_url") != SOURCE
            or j.get("state") != "ORIGINAL_NSE_SOURCE_UNVERIFIED"
            or j.get("industry_rows_admitted") != 0
            or j.get("live_capital_allowed") is not False
        ):
            raise AlphaContractError("P033 original source failure receipt modified")
        sha = j.get("raw_sha256")
        if sha is not None:
            raw_path = root / BASE / "quarantine" / f"{sha}.csv.gz"
            if (
                len(sha) != 64
                or j.get("raw_quarantine_path") != str(raw_path.relative_to(root))
                or not raw_path.exists()
                or hashlib.sha256(gzip.decompress(raw_path.read_bytes())).hexdigest()
                != sha
            ):
                raise AlphaContractError("P033 failed original response quarantine drift")
        elif j.get("raw_quarantine_path") is not None:
            raise AlphaContractError("P033 failed source invents raw evidence")
        count += 1
    return count


def run(root: Path, *, check: bool = False) -> dict:
    current = replay_all(root)
    failures = _verify_failures(root)
    if check:
        return {**current, "replayed_failure_receipts": failures}
    if current["source_replays_verified"] > 0:
        return {
            **current,
            "state": "ORIGINAL_NSE_INDEX_ALREADY_VERIFIED_NO_REDOWNLOAD",
        }
    now = datetime.now(UTC)
    today = now.date().isoformat()
    attempt_dir = root / BASE / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    if any(attempt_dir.glob(f"{today}-*.json")):
        return {
            "state": "ONE_SOURCE_PROBE_ALREADY_RECORDED_TODAY",
            "new_source_verified": False,
            "new_cohort_activated": False,
            "live_capital_allowed": False,
        }
    raw: bytes | None = None
    try:
        raw = NSEClient(timeout=20, attempts=1).archive_bytes(SOURCE)
        observed = datetime.now(UTC).isoformat()
        result = archive(root, raw=raw, first_observed_at_utc=observed)
        return {
            "state": "VERIFIED_OFFICIAL_NSE_TOTALMARKET_PARTIAL_SOURCE",
            "original_source_sha256": result["source_original_sha256"],
            "valid_EQ_industry_rows": result["source_unique_valid_EQ_rows"],
            "invalid_or_ambiguous_rows": result["source_rejected_rows"],
            "matched_frozen_300": result["frozen_300_exact_symbol_isin_matches"],
            "verified_by_arm": {
                arm: row["verified"] for arm, row in result["coverage_by_arm"].items()
            },
            "source_coverage_gate_met": result["one_tier_industry_source_coverage_ready"],
            "new_independent_trial_registration_ready": False,
            "live_capital_allowed": False,
        }
    except (NSEAcquisitionError, AlphaContractError) as exc:
        observed = datetime.now(UTC).isoformat()
        sha = hashlib.sha256(raw).hexdigest() if raw else None
        quarantine = None
        if sha is not None:
            source_path = root / BASE / "quarantine" / f"{sha}.csv.gz"
            source_path.parent.mkdir(parents=True, exist_ok=True)
            bytes_gz = gzip.compress(raw, mtime=0, compresslevel=9)
            if source_path.exists() and source_path.read_bytes() != bytes_gz:
                raise AlphaContractError("P033 failed source SHA collision")
            source_path.write_bytes(bytes_gz)
            quarantine = str(source_path.relative_to(root))
        receipt = {
            "protocol": "HG009-P033-NSE-TOTALMARKET-ROWWISE-PROVENANCE-v1",
            "state": "ORIGINAL_NSE_SOURCE_UNVERIFIED",
            "source_url": SOURCE,
            "attempt_recorded_at_utc": observed,
            "raw_sha256": sha,
            "raw_quarantine_path": quarantine,
            "error_class": type(exc).__name__,
            "error_reason": str(exc)[:240],
            "industry_rows_admitted": 0,
            "new_cohort_activated": False,
            "live_capital_allowed": False,
        }
        path = attempt_dir / (
            today + "-" + observed[11:19].replace(":", "") + ".json"
        )
        if path.exists():
            raise AlphaContractError("P033 cannot overwrite source failure receipt")
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", "utf-8")
        return receipt


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--check", action="store_true")
    opts = p.parse_args()
    print(json.dumps(run(opts.repo_root, check=opts.check), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
