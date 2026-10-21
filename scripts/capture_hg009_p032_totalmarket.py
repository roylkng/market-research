"""One official NSE Nifty Total Market CSV request, or honest blocked receipt."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p032_totalmarket import (
    SOURCE_URL,
    archive,
    replay_all,
)
from marketlab.nse import NSEAcquisitionError, NSEClient


def run(root: Path, *, check_only: bool = False) -> dict:
    verified = replay_all(root)
    if check_only:
        return verified
    if verified["original_evidence_count"]:
        return {**verified, "state": "ORIGINAL_CSV_ALREADY_ARCHIVED_NO_REDOWLOAD"}
    now = datetime.now(UTC)
    failure_dir = root / "research/hg009/p032-totalmarket/attempts"
    failure_dir.mkdir(parents=True, exist_ok=True)
    day = now.date().isoformat()
    if list(failure_dir.glob(f"{day}-*.json")):
        return {
            "state": "NSE_STATIC_ARCHIVE_ATTEMPT_ALREADY_RECORDED_TODAY",
            "original_evidence_count": 0,
            "live_capital_allowed": False,
        }
    raw: bytes | None = None
    try:
        raw = NSEClient(timeout=16, attempts=1).archive_bytes(SOURCE_URL)
        retrieved = datetime.now(UTC).isoformat()
        result = archive(
            root=root, raw=raw, first_retrieved_at_utc=retrieved,
        )
        return {
            "state": "OFFICIAL_NSE_STATIC_CSV_SOURCE_VERIFIED",
            "retrieved_at_utc": retrieved,
            "original_raw_sha256": result["source_sha256"],
            "frozen_300_exact_matches": result["exact_symbol_isin_matches"],
            "per_arm": result["per_arm"],
            "source_type": "PARTIAL_INDEX_SUBSET_SINGLE_INDUSTRY_ONLY",
            "source_proves_pre_oct15_industry": False,
            "new_cohort_eligible": False,
            "live_capital_allowed": False,
        }
    except (NSEAcquisitionError, AlphaContractError) as exc:
        observed = datetime.now(UTC).isoformat()
        # A structurally unexpected HTTP 200 NSE CSV is important research
        # evidence. Preserve its *actual* original bytes in quarantine, not
        # the failed/empty company-sector joins. Never call this verified.
        raw_sha = hashlib.sha256(raw).hexdigest() if raw else None
        quarantine_path = None
        if raw_sha is not None:
            quarantine = root / "research/hg009/p032-totalmarket/quarantine"
            quarantine.mkdir(parents=True, exist_ok=True)
            target = quarantine / f"{raw_sha}.csv.gz"
            encoded = gzip.compress(raw, mtime=0, compresslevel=9)
            if target.exists() and target.read_bytes() != encoded:
                raise AlphaContractError("P032 quarantine original bytes collision")
            target.write_bytes(encoded)
            quarantine_path = str(target.relative_to(root))
        error = {
            "state": "BLOCKED_OFFICIAL_NSE_ORIGINAL_CSV",
            "source_url": SOURCE_URL,
            "actual_attempt_at_utc": observed,
            "error_kind": type(exc).__name__,
            "error_summary": str(exc)[:350],
            "source_raw_sha256": raw_sha,
            "quarantine_raw_repo_path": quarantine_path,
            "original_response_bytes_retained_unverified": raw_sha is not None,
            "industry_cells_verified": 0,
            "live_capital_allowed": False,
        }
        marker = (
            day + "-" + observed[11:19].replace(":", "") + ".json"
        )
        path = failure_dir / marker
        if path.exists():
            raise AlphaContractError("P032 attempted to overwrite original failure")
        path.write_text(json.dumps(error, sort_keys=True, indent=2) + "\n")
        return error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.repo_root, check_only=args.check), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
