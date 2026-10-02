from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from marketlab.alpha import AlphaContractError
from marketlab.alpha_acquisition import acquire_historical_market_panel, http_fetcher
from marketlab.alpha_corporate_actions import (
    acquire_corporate_action_ledger,
    filter_feature_panel_for_corporate_actions,
)
from marketlab.alpha_history import (
    build_historical_feature_panel,
    canonical_gzip_json,
)
from marketlab.events import sha256_bytes
from marketlab.nse import NSEClient
from marketlab.rm001_size_panel import build_rm001_v2_size_panel
from marketlab.rm001_v2 import (
    build_rm001_v2_exposure_panel,
    build_rm001_v2_factor_history,
    build_rm001_v2_risk_state,
)
from marketlab.rm001_v3 import build_rm001_v3_risk_state
from marketlab.rm001_v3_prospective import (
    append_prospective_v3_state,
    find_sc001_attempt,
    latest_activation_target,
    seal_cutoff_utc,
    target_already_sealed,
    validate_prospective_v3_ledger,
)

SUPPORT_LOOKBACK_CALENDAR_DAYS = 420
MIN_COMPLETED_MARKET_SESSIONS = 200


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _load_exact_raw(path_text: str, expected_sha: str, name: str) -> bytes:
    path = Path(path_text)
    if not path.exists():
        raise AlphaContractError(f"{name} exact raw file is missing: {path}")
    raw = path.read_bytes()
    if sha256_bytes(raw) != expected_sha:
        raise AlphaContractError(f"{name} exact raw hash mismatch")
    return raw


def _summary_hash(summary: dict) -> str:
    stored = str(summary.get("summary_sha256") or "")
    unsigned = dict(summary)
    unsigned.pop("summary_sha256", None)
    from marketlab.alpha import digest

    observed = digest(unsigned)
    if stored != observed:
        raise AlphaContractError(
            "prospective RM001-v3 readiness summary hash mismatch"
        )
    return stored


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build one prospective RM001-v3 next-session risk state"
    )
    parser.add_argument("--sc001-ledger", type=Path, required=True)
    parser.add_argument("--size-ledger", type=Path, required=True)
    parser.add_argument("--readiness-summary", type=Path, required=True)
    parser.add_argument("--risk-ledger", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sc001_ledger = _load_json(args.sc001_ledger)
    size_ledger = _load_json(args.size_ledger)
    readiness = _load_json(args.readiness_summary)
    risk_ledger = _load_json(args.risk_ledger)
    validate_prospective_v3_ledger(risk_ledger)
    readiness_sha = _summary_hash(readiness)

    size_attempt = latest_activation_target(
        size_ledger=size_ledger,
        readiness_summary=readiness,
    )
    if size_attempt is None:
        print(
            json.dumps(
                {
                    "state": "WAITING_FOR_SIZE_TIMING_GATE",
                    "ready_count": readiness[
                        "distinct_ready_before_cutoff_session_count"
                    ],
                    "required_count": readiness[
                        "minimum_ready_sessions_for_prospective_size"
                    ],
                    "changed": False,
                },
                sort_keys=True,
            )
        )
        return 0

    target_session = str(size_attempt["target_session_date"])
    observation_date = str(size_attempt["observation_date"])
    if target_already_sealed(risk_ledger, target_session):
        print(
            json.dumps(
                {
                    "state": "TARGET_ALREADY_SEALED",
                    "target_session_date": target_session,
                    "observation_date": observation_date,
                    "changed": False,
                },
                sort_keys=True,
            )
        )
        return 0

    sc001_attempt = find_sc001_attempt(
        sc001_ledger=sc001_ledger,
        attempt_sha256=str(size_attempt["sc001_attempt_sha256"]),
    )
    market_meta = sc001_attempt["market"]
    current_market_raw = _load_exact_raw(
        str(market_meta["raw_repo_path"]),
        str(market_meta["raw_sha256"]),
        "RM001-v3 target market",
    )
    current_security_raw = _load_exact_raw(
        str(size_attempt["raw_repo_path"]),
        str(size_attempt["raw_sha256"]),
        "RM001-v3 target Security File",
    )

    target_day = date.fromisoformat(target_session)
    support_start = target_day - timedelta(
        days=SUPPORT_LOOKBACK_CALENDAR_DAYS
    )
    args.work_dir.mkdir(parents=True, exist_ok=True)
    base_fetch = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )

    target_market_url = str(market_meta["source_url"])

    def market_fetch(url: str):
        if url == target_market_url:
            return current_market_raw
        return base_fetch(url)

    captured = datetime.now(UTC)
    market = acquire_historical_market_panel(
        start_date=support_start,
        end_date=target_day,
        fetcher=market_fetch,
        store_root=args.work_dir / "market-store",
        captured_at_utc=captured,
        pause_seconds=0.0,
    )
    if int(market["session_count"]) < MIN_COMPLETED_MARKET_SESSIONS:
        raise AlphaContractError(
            "prospective RM001-v3 support has too few completed market sessions"
        )
    if str(market["sessions"][-1]["session_date"]) != target_session:
        raise AlphaContractError(
            "prospective RM001-v3 market support does not end on target"
        )
    if str(market["sessions"][-1]["udiff_sha256"]) != str(
        market_meta["raw_sha256"]
    ):
        raise AlphaContractError(
            "prospective RM001-v3 market panel did not bind exact target bytes"
        )

    features = build_historical_feature_panel(
        sessions=market["sessions"]
    )

    action_client = NSEClient(
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )

    def action_fetch(from_date: str, to_date: str):
        payload, raw = action_client.corporate_actions_with_raw(
            None,
            from_date=from_date,
            to_date=to_date,
        )
        query = urlencode(
            {
                "index": "equities",
                "from_date": from_date,
                "to_date": to_date,
            }
        )
        return (
            payload,
            raw,
            f"{action_client.CORPORATE_ACTION_ENDPOINT.url}?{query}",
        )

    actions = acquire_corporate_action_ledger(
        start_date=date.fromisoformat(str(market["sessions"][0]["session_date"])),
        end_date=target_day,
        fetcher=action_fetch,
        raw_dir=args.work_dir / "corporate-actions",
        chunk_days=31,
    )
    action_safe = filter_feature_panel_for_corporate_actions(
        feature_panel=features,
        market_panel=market,
        action_ledger=actions,
        lookback_sessions=60,
    )

    target_security_url = str(size_attempt["source_url"])

    def size_fetch(url: str):
        if url == target_security_url:
            return current_security_raw
        return base_fetch(url)

    sizes = build_rm001_v2_size_panel(
        market_panel=market,
        fetcher=size_fetch,
        store_root=args.work_dir / "size-store",
        captured_at_utc=datetime.now(UTC),
    )
    target_size_rows = [
        row
        for row in sizes["sessions"]
        if str(row["session_date"]) == target_session
    ]
    if len(target_size_rows) != 1:
        raise AlphaContractError(
            "prospective RM001-v3 target size session missing"
        )
    if target_size_rows[0]["raw_sha256"] != size_attempt["raw_sha256"]:
        raise AlphaContractError(
            "prospective RM001-v3 size panel did not bind exact target bytes"
        )

    exposures = build_rm001_v2_exposure_panel(
        feature_panel=action_safe,
        market_panel=market,
        action_ledger=actions,
        size_panel=sizes,
    )
    history = build_rm001_v2_factor_history(
        exposure_panel=exposures,
        market_panel=market,
        action_ledger=actions,
    )
    v2_state = build_rm001_v2_risk_state(
        exposure_panel=exposures,
        factor_history=history,
        as_of_session=target_session,
    )
    v3_state = build_rm001_v3_risk_state(
        v2_risk_state=v2_state,
        v2_factor_history=history,
    )

    support = {
        "market_panel_sha256": market["panel_sha256"],
        "feature_panel_sha256": features["panel_sha256"],
        "corporate_action_ledger_sha256": actions["ledger_sha256"],
        "action_safe_feature_panel_sha256": action_safe["panel_sha256"],
        "size_panel_sha256": sizes["panel_sha256"],
        "size_source_ledger_sha256": size_ledger["ledger_sha256"],
        "size_readiness_summary_sha256": readiness_sha,
        "sc001_source_ledger_sha256": sc001_ledger["ledger_sha256"],
    }

    # Persist full support only as workflow evidence. This is diagnostic if late.
    for filename, payload in (
        ("market-panel.json.gz", market),
        ("feature-panel.json.gz", features),
        ("corporate-action-ledger.json.gz", actions),
        ("action-safe-feature-panel.json.gz", action_safe),
        ("size-panel.json.gz", sizes),
        ("v2-exposure-panel.json.gz", exposures),
        ("v2-factor-history.json.gz", history),
        ("v2-risk-state.json.gz", v2_state),
        ("v3-risk-state.json.gz", v3_state),
    ):
        (args.work_dir / filename).write_bytes(canonical_gzip_json(payload))

    sealed = datetime.now(UTC)
    cutoff = seal_cutoff_utc(observation_date)
    if sealed > cutoff:
        result = {
            "state": "MISSED_0905_SEAL_CUTOFF",
            "target_session_date": target_session,
            "observation_date": observation_date,
            "sealed_at_utc": sealed.isoformat(),
            "seal_cutoff_utc": cutoff.isoformat(),
            "v3_risk_state_sha256": v3_state["state_sha256"],
            "support_hashes": support,
            "changed": False,
            "live_capital_allowed": False,
        }
        _write_json(args.work_dir / "late-result.json", result)
        print(json.dumps(result, sort_keys=True))
        return 0

    state_bytes = canonical_gzip_json(v3_state)
    state_path = args.state_dir / f"{target_session}-v1.json.gz"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    if state_path.exists() and state_path.read_bytes() != state_bytes:
        raise AlphaContractError(
            f"prospective RM001-v3 state path collision: {state_path}"
        )
    state_path.write_bytes(state_bytes)

    updated = append_prospective_v3_state(
        risk_ledger,
        target_session_date=target_session,
        observation_date=observation_date,
        size_attempt=size_attempt,
        sc001_attempt=sc001_attempt,
        v2_exposure_panel_sha256=exposures["panel_sha256"],
        v2_factor_history_sha256=history["history_sha256"],
        v2_risk_state_sha256=v2_state["state_sha256"],
        v3_risk_state=v3_state,
        state_artifact_path=str(state_path),
        state_artifact_bytes=state_bytes,
        support_hashes=support,
        sealed_at_utc=sealed.isoformat(),
    )
    _write_json(args.risk_ledger, updated)
    validate_prospective_v3_ledger(updated)

    result = {
        "state": "SEALED",
        "target_session_date": target_session,
        "observation_date": observation_date,
        "sealed_at_utc": sealed.isoformat(),
        "risk_ledger_sha256": updated["ledger_sha256"],
        "v2_risk_state_sha256": v2_state["state_sha256"],
        "v3_risk_state_sha256": v3_state["state_sha256"],
        "v3_state_artifact_sha256": sha256_bytes(state_bytes),
        "security_count": v3_state["security_count"],
        "complete_statistical_identity_count": v3_state[
            "complete_statistical_identity_count"
        ],
        "support_hashes": support,
        "changed": True,
        "live_capital_allowed": False,
    }
    _write_json(args.work_dir / "sealed-result.json", result)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
