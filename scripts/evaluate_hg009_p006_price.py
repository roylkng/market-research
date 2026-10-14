"""Independently replay frozen HG009 H1/H5 original-source price diagnostics.

H1/H5 only. Never infer missing NSE source, corporate actions, total returns or
investable alpha. H20 and H60 are blocked by the original frozen calendar.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.hg009_daily import (
    build_hg009_daily_source_observation,
    validate_hg009_daily_snapshot,
)
from marketlab.hg009_daily_io import (
    H021_SOURCE_DIR,
    load_json_source,
    original_source_bytes,
)
from marketlab.hg009_p004_clock import (
    load_p004_inputs,
    validate_hg009_outcome_clock,
)
from marketlab.hg009_p006_price import (
    HORIZONS,
    build_hg009_price_only_diagnostic,
    validate_hg009_price_only_diagnostic,
)

PROTOCOL = Path("research/hg009/hg009-p004-2026-outcome-clock-v1.json")
CONTROL = Path("research/hg009/hg009-p001-matched-300-company-controls-v1.json")
SOURCE_DAILY = Path("research/hg009/daily")
OUTPUT = Path("research/hg009/price-diagnostics")


def _original_replay(
    root: Path,
    *,
    day: str,
    calendar,
    original: dict,
    selected: dict,
    controls: dict,
) -> dict:
    """Prove every frozen price against H021 original NSE ZIP/CSV, not JSON alone."""
    candidate_path = root / SOURCE_DAILY / f"{day}-v1.json"
    observed = load_json_source(candidate_path)
    validate_hg009_daily_snapshot(observed)
    if observed.get("date_ist") != day:
        raise AlphaContractError("HG009 P006 source filename/day mismatch")
    expected_path = H021_SOURCE_DIR / f"{day}-v1.json"
    if observed.get("h021_original_daily_packet_path") != str(expected_path):
        raise AlphaContractError("HG009 P006 original H021 reference was replaced")
    h021 = load_json_source(root / expected_path)
    stock = original_source_bytes(
        root, h021["stock_source"], suffix=".zip"
    )
    index = original_source_bytes(
        root, h021["index_source"], suffix=".csv"
    )
    again = build_hg009_daily_source_observation(
        h021_observation=h021,
        original_udiff_zip=stock,
        original_index_csv=index,
        selected_manifest=selected,
        controls_manifest=controls,
        original_router=original,
        calendar=calendar,
        recorded_at_utc=observed["observed_recorded_at_utc"],
    )
    if again != observed:
        raise AlphaContractError(
            f"HG009 P006 original {day} NSE ZIP/CSV replay differs"
        )
    return observed


def build_or_verify_all(
    root: Path,
    *,
    output_dir: Path = OUTPUT,
    check_only: bool = False,
    as_of_utc: datetime | None = None,
) -> dict:
    now = as_of_utc or datetime.now(UTC)
    if now.tzinfo is None:
        raise AlphaContractError("HG009 P006 evaluation now must have UTC offset")
    now = now.astimezone(UTC)
    calendar, original, selected, controls = load_p004_inputs(root)
    frozen = load_json_source(root / PROTOCOL)
    validate_hg009_outcome_clock(
        frozen,
        calendar=calendar,
        original=original,
        selected=selected,
        controls=controls,
    )
    ready = []
    pending = []
    for horizon in HORIZONS:
        plan = frozen["planned_horizon_status"][str(horizon)]
        if plan["state"] != "FROZEN_TRADING_DAY_SEQUENCE_READY_TO_COLLECT_SOURCE":
            raise AlphaContractError("HG009 P006 future horizon not frozen")
        days = plan["date_scoped_holding_sessions"]
        exit_close = next(
            session.close_timestamp_utc for session in calendar.sessions
            if session.session_date == days[-1]
        )
        if now < datetime.fromisoformat(exit_close).astimezone(UTC):
            pending.append({
                "horizon": horizon,
                "state": "EXIT_SESSION_NOT_YET_CLOSED",
                "exit_session": days[-1],
            })
            continue
        missing = [
            day for day in days
            if not (root / SOURCE_DAILY / f"{day}-v1.json").is_file()
        ]
        if missing:
            pending.append({
                "horizon": horizon,
                "state": "MISSING_ORIGINAL_NSE_SOURCE_NO_BACKFILL",
                "missing_source_sessions": missing,
            })
            continue
        originals = [
            _original_replay(
                root,
                day=day,
                calendar=calendar,
                original=original,
                selected=selected,
                controls=controls,
            )
            for day in days
        ]
        path = root / output_dir / f"HG009-P006-H{horizon}-20261015-v1.json"
        if path.exists():
            existing = load_json_source(path)
            validate_hg009_price_only_diagnostic(
                existing,
                horizon_sessions=horizon,
                protocol=frozen,
                calendar=calendar,
                original=original,
                selected=selected,
                controls=controls,
                market_snapshots=originals,
            )
            status = "ORIGINAL_SOURCE_REPLAY_VERIFIED"
            changed = False
            item = existing
        elif check_only:
            pending.append({
                "horizon": horizon,
                "state": "MATURE_SOURCES_UNSCORED_REPORT_NOT_SEALED",
                "eligible_source_sessions": days,
            })
            continue
        else:
            item = build_hg009_price_only_diagnostic(
                horizon_sessions=horizon,
                protocol=frozen,
                calendar=calendar,
                original=original,
                selected=selected,
                controls=controls,
                market_snapshots=originals,
                evaluated_at_utc=now.isoformat(),
            )
            payload = (
                json.dumps(
                    item, indent=2, sort_keys=True,
                    ensure_ascii=False, allow_nan=False,
                ) + "\n"
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            # No earlier result is ever overwritten, even if market source
            # publication is delayed or the observation is inconvenient.
            if path.exists():
                raise AlphaContractError("HG009 P006 immutable artifact collision")
            path.write_text(payload, encoding="utf-8")
            status = "SOURCE_BOUND_PRICE_DIAGNOSTIC_SEALED_LOCALLY"
            changed = True
        ready.append({
            "horizon": horizon,
            "state": status,
            "changed": changed,
            "source_date": item["first_entry_date"],
            "exit_date": item["official_exit_date"],
            "original_denominator_per_arm": 100,
            "coverage": {
                arm: item["arm_descriptive_statistics"][arm][
                    "priced_observation_count"
                ]
                for arm in ("SELECTED", "ONE_LANE", "ZERO_LANE")
            },
            "sha256": item["evaluation_sha256"],
        })

    result = {
        "schema_version": 1,
        "state": (
            "SOURCE_ONLY_DIAGNOSTICS_AVAILABLE" if ready
            else "WAITING_FOR_GENUINE_FUTURE_EXCHANGE_SOURCES"
        ),
        "ready": ready,
        "pending": pending,
        "first_entry": frozen["first_eligible_entry_session"],
        "H20_unresolved_special_calendar": True,
        "H60_requires_2027_calendar": True,
        "economic_total_returns_computed": False,
        "scientific_causal_alpha_claim": False,
        "live_capital_allowed": False,
    }
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    result = build_or_verify_all(
        args.repo_root,
        check_only=args.check,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
