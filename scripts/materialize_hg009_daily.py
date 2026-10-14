"""Materialize the next 300-name HG009 observation from original H021 NSE bytes.

The cohort and controls are already frozen before first planned entry. H021
retains full NSE cash + Nifty 500 originals. This derives a source-linked
300-symbol daily observation without making any return or trade claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError
from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.hg009_controls import load_hg009_inputs
from marketlab.hg009_daily import (
    FIRST_SESSION,
    H021_SOURCE_DIR,
    build_hg009_daily_source_observation,
    validate_hg009_daily_snapshot,
)

CALENDAR = Path(
    "research/prospective/calendars/FY27-Q2-2026-09-06/"
    "NSE-CM-FY27Q2-v1.json"
)
CONTROL = Path(
    "research/hg009/hg009-p001-matched-300-company-controls-v1.json"
)
DAILY_OUTPUT = Path("research/hg009/daily")


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"HG009 expected JSON source: {path}")
    return data


def _original_raw(
    root: Path, receipt: dict[str, Any], *, suffix: str
) -> bytes:
    sha = str(receipt["sha256"])
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise AlphaContractError("HG009 source SHA missing or malformed")
    file = root / H021_SOURCE_DIR / "raw" / "sha256" / f"{sha}{suffix}"
    if not file.is_file():
        raise AlphaContractError(f"HG009 original NSE source absent: {file}")
    raw = file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha or len(raw) != receipt[
        "byte_count"
    ]:
        raise AlphaContractError(f"HG009 original NSE byte mismatch: {file}")
    return raw


def _next_available_source(
    *,
    root: Path,
    now: datetime,
    calendar: Any,
    observations: Path,
) -> tuple[str | None, list[str]]:
    missing_prior = []
    for session in calendar.sessions:
        day = session.session_date
        if day < FIRST_SESSION:
            continue
        if datetime.fromisoformat(session.close_timestamp_utc).astimezone(UTC) > now:
            break
        source_path = root / H021_SOURCE_DIR / f"{day}-v1.json"
        derived_path = root / observations / f"{day}-v1.json"
        if derived_path.is_file():
            validate_hg009_daily_snapshot(_load_json(derived_path))
            continue
        if source_path.is_file():
            return day, missing_prior
        missing_prior.append(day)
    return None, missing_prior


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--calendar", type=Path, default=CALENDAR)
    p.add_argument("--control-manifest", type=Path, default=CONTROL)
    p.add_argument("--output-dir", type=Path, default=DAILY_OUTPUT)
    p.add_argument(
        "--session-date",
        help="Exact completed official NSE session, or omit for oldest ready source",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = args.repo_root
    calendar = load_calendar_snapshot(root / args.calendar)
    now = datetime.now(UTC)
    if args.session_date:
        day = args.session_date
        if day < FIRST_SESSION or not any(
            session.session_date == day
            and datetime.fromisoformat(
                session.close_timestamp_utc
            ).astimezone(UTC) <= now
            for session in calendar.sessions
        ):
            raise AlphaContractError("HG009 source date must be completed and future")
        missing_prior = []
    else:
        day, missing_prior = _next_available_source(
            root=root,
            now=now,
            calendar=calendar,
            observations=args.output_dir,
        )
        if day is None:
            print(json.dumps({
                "state": "NO_COMPLETED_H021_ORIGINAL_SOURCE_TO_DERIVE",
                "first_expected_session": FIRST_SESSION,
                "unobserved_prior_sessions": missing_prior,
                "changed": False,
                "live_capital_allowed": False,
            }, sort_keys=True))
            return 0
    source_path = root / H021_SOURCE_DIR / f"{day}-v1.json"
    if not source_path.is_file():
        print(json.dumps({
            "state": "WAITING_FOR_ORIGINAL_H021_NSE_SOURCE",
            "session": day,
            "changed": False,
            "live_capital_allowed": False,
        }, sort_keys=True))
        return 0

    h021 = _load_json(source_path)
    router, selected = load_hg009_inputs(root)
    controls = _load_json(root / args.control_manifest)
    original_market = _original_raw(
        root, h021["stock_source"], suffix=".zip"
    )
    original_index = _original_raw(
        root, h021["index_source"], suffix=".csv"
    )
    observation = build_hg009_daily_source_observation(
        h021_observation=h021,
        original_udiff_zip=original_market,
        original_index_csv=original_index,
        selected_manifest=selected,
        controls_manifest=controls,
        original_router=router,
        calendar=calendar,
        recorded_at_utc=datetime.now(UTC).isoformat(),
    )
    validate_hg009_daily_snapshot(observation)
    path = root / args.output_dir / f"{day}-v1.json"
    data = (
        json.dumps(
            observation, indent=2, sort_keys=True,
            ensure_ascii=False, allow_nan=False,
        )
        + "\n"
    )
    if path.exists():
        if path.read_text(encoding="utf-8") != data:
            # Timestamp differences are expected across reruns. Preserve the
            # earliest sealed original day, never rewrite a prior measurement.
            existing = _load_json(path)
            validate_hg009_daily_snapshot(existing)
            if existing["h021_original_daily_packet_sha256"] != h021[
                "packet_sha256"
            ]:
                raise AlphaContractError(
                    "HG009 previously sealed original source differs"
                )
        state = "ALREADY_SEALED"
        changed = False
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        state = "SOURCE_OBSERVATION_SEALED_LOCALLY_PENDING_REMOTE_COMMIT"
        changed = True
    print(json.dumps({
        "state": state,
        "session": day,
        "new_source_artifact": changed,
        "original_h021_source_sha256": h021["packet_sha256"],
        "manifest_sha256": observation["packet_sha256"],
        "observation_coverage": observation["arm_coverage"],
        "unobserved_prior_sessions": missing_prior,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
