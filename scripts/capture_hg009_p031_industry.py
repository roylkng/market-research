"""Acquire original NSE four-tier issuer industry records for a NEXT cohort.

Conservative batch request budget: bounded count and delay, stop immediately
on denied/rate-limited NSE access. Failures are recorded, not imputed sectors.
Nothing here can rewrite the October 15 original HG009 study.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, date, datetime
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p031_industry import (
    METHOD_DATE,
    RECEIPTS,
    build_coverage_status,
    classify_raw_quote,
    frozen_members,
    load_verified_receipts,
    record_receipt,
)
from marketlab.nse import NSEAcquisitionError, NSEClient


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--max-symbols", type=int, default=5)
    p.add_argument("--timeout-seconds", type=float, default=10)
    p.add_argument("--attempts", type=int, default=1)
    p.add_argument("--pause-seconds", type=float, default=1.0)
    p.add_argument("--check", action="store_true")
    return p.parse_args()


def run(
    root: Path, *,
    max_symbols: int = 5,
    timeout_seconds: float = 10.0,
    attempts: int = 1,
    pause_seconds: float = 1.0,
    check_only: bool = False,
) -> dict:
    if (
        not 0 <= max_symbols <= 25
        or not 0 < timeout_seconds <= 40
        or not 1 <= attempts <= 2
        or not 0.75 <= pause_seconds <= 10
    ):
        raise AlphaContractError("P031 unsafe NSE request frequency/budget")
    members = frozen_members(root)
    existing, _failures = load_verified_receipts(root, members)
    if check_only:
        return {
            "state": "REPLAY_ONLY",
            "status": build_coverage_status(root),
            "attempted": [],
        }
    if datetime.now(UTC).date() < date.fromisoformat(METHOD_DATE):
        raise AlphaContractError("P031 acquisition cannot precede method date")

    # One attempt per symbol per real UTC day. Never hammer NSE on a repeated
    # runner dispatch. A failure elsewhere must not block other issuers forever.
    attempted_today = set()
    access_denied_today = False
    today = datetime.now(UTC).date().isoformat()
    for path in (root / RECEIPTS / today).glob("*.json"):
        receipt = json.loads(path.read_text(encoding="utf-8"))
        attempted_today.add(receipt["symbol"])
        if receipt.get("state") == "BLOCKED_NSE_ACCESS_OR_RATE_LIMIT":
            access_denied_today = True
    if access_denied_today:
        # One verified access-denial receipt blocks further issuer requests
        # that UTC day, across repeated GitHub schedule/dispatch attempts.
        # Do not route around exchange anti-bot/rate limits.
        return {
            "state": "NSE_ACCESS_DENIED_TODAY_NO_MORE_REQUESTS",
            "attempted": [],
            "status": build_coverage_status(root),
            "next_cohort_released": False,
            "live_capital_allowed": False,
        }
    remaining = [
        (symbol, expected[0])
        for symbol, expected in sorted(members.items())
        if symbol not in existing and symbol not in attempted_today
    ][:max_symbols]
    tried = []
    stop = False
    client = NSEClient(timeout=timeout_seconds, attempts=attempts)
    for index, (symbol, isin) in enumerate(remaining):
        if index:
            time.sleep(pause_seconds)
        captured = datetime.now(UTC).isoformat()
        try:
            _payload, raw = client.quote_equity_with_raw(symbol)
            captured = datetime.now(UTC).isoformat()
            source = classify_raw_quote(
                raw,
                symbol=symbol,
                isin=isin,
                captured_at_utc=captured,
            )
            record = {
                **source,
                "state": "VERIFIED_FOUR_TIER_NSE_EQ",
                "http_status": 200,
            }
            path = record_receipt(root, record, raw=raw)
            state = "VERIFIED_FOUR_TIER_NSE_EQ"
        except (NSEAcquisitionError, AlphaContractError, ValueError) as exc:
            reason = str(exc)[:260]
            access_denied = any(
                token in reason.lower()
                for token in ("403", "401", "429", "forbidden", "too many requests")
            )
            record = {
                "symbol": symbol,
                "isin": isin,
                "captured_at_utc": captured,
                "original_url": (
                    f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
                ),
                "state": (
                    "BLOCKED_NSE_ACCESS_OR_RATE_LIMIT"
                    if access_denied
                    else "BLOCKED_SOURCE_SCHEMA_OR_IDENTITY"
                ),
                "http_status": None,
                "source_error_type": type(exc).__name__,
                "source_error_excerpt": reason,
                "source_raw_sha256": None,
                "original_oct15_sector_feature_repaired": False,
                "live_capital_allowed": False,
            }
            path = record_receipt(root, record, raw=None)
            state = record["state"]
            if access_denied:
                stop = True
        tried.append({
            "symbol": symbol,
            "state": state,
            "receipt_path": str(path.relative_to(root)),
        })
        if stop:
            break

    status = build_coverage_status(root)
    latest = root / "research/hg009/p031-industry/latest-status.json"
    latest.parent.mkdir(parents=True, exist_ok=True)
    raw_status = json.dumps(
        status, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"
    # The status is derived from append-only source receipts; unlike those
    # receipts the *latest* pointer may advance as coverage accumulates.
    latest.write_text(raw_status, encoding="utf-8")
    return {
        "state": (
            "SOURCE_ACCESS_BLOCKED" if stop else "BATCH_EXECUTED_WITH_SOURCE_GATES"
        ),
        "attempted": tried,
        "remaining_unverified": status["unverified_original_issuer_count"],
        "verified_total": status["verified_original_NSE_issuer_four_tier_count"],
        "per_arm_verified": {
            arm: row["verified"]
            for arm, row in status["frozen_100_company_arm_coverage"].items()
        },
        "next_cohort_released": False,
        "live_capital_allowed": False,
    }


def main() -> int:
    args = _args()
    output = run(
        args.repo_root,
        max_symbols=args.max_symbols,
        timeout_seconds=args.timeout_seconds,
        attempts=args.attempts,
        pause_seconds=args.pause_seconds,
        check_only=args.check,
    )
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
