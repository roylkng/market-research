from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.paperfund import mark_session, new_fund, process_entry_batch
from marketlab.paperfund_state import state_sha256, validate_fund_state

DEFAULT_POLICY_FROZEN_AT = "2026-09-11T18:46:13Z"


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Advance one PF001 paper-fund session")
    parser.add_argument("--session-date", required=True)
    parser.add_argument("--bars", required=True, help="JSON mapping symbol to daily OHLC")
    parser.add_argument("--out", required=True)
    parser.add_argument("--state", help="Existing PF001 state JSON. Omit to initialize.")
    parser.add_argument("--decisions", help="JSON list of sealed Analyst Decision Objects")
    parser.add_argument(
        "--book",
        choices=("DEVELOPMENT", "PROSPECTIVE_VALIDATION"),
        default="PROSPECTIVE_VALIDATION",
    )
    parser.add_argument("--policy-frozen-at", default=DEFAULT_POLICY_FROZEN_AT)
    args = parser.parse_args()

    bars_payload = _load_json(Path(args.bars))
    if not isinstance(bars_payload, dict):
        raise TypeError("bars payload must be an object keyed by symbol")
    bars: dict[str, dict[str, float]] = {}
    for symbol, bar in bars_payload.items():
        if not isinstance(symbol, str) or not isinstance(bar, dict):
            raise TypeError("bars must map string symbols to OHLC objects")
        bars[symbol] = bar

    if args.state:
        state_payload = _load_json(Path(args.state))
        if not isinstance(state_payload, dict):
            raise TypeError("state payload must be an object")
        state = state_payload
        state_errors = validate_fund_state(state)
        if state_errors:
            raise ValueError({"state_errors": state_errors})
        if state.get("book") != args.book:
            raise ValueError("existing state book does not match --book")
    else:
        state = new_fund(book=args.book, policy_frozen_at=args.policy_frozen_at)

    decisions: list[dict] = []
    if args.decisions:
        decisions_payload = _load_json(Path(args.decisions))
        if not isinstance(decisions_payload, list):
            raise TypeError("decisions payload must be a list")
        if any(not isinstance(item, dict) for item in decisions_payload):
            raise TypeError("every decision must be an object")
        decisions = decisions_payload

    if decisions:
        open_prices = {
            symbol: float(bar["open"])
            for symbol, bar in bars.items()
            if bar.get("open") is not None
        }
        state = process_entry_batch(
            state,
            decisions,
            session_date=args.session_date,
            open_prices=open_prices,
        )

    state = mark_session(state, session_date=args.session_date, bars=bars)
    state_errors = validate_fund_state(state)
    if state_errors:
        raise ValueError({"state_errors": state_errors})
    state["state_sha256"] = state_sha256(state)
    _write_json(Path(args.out), state)


if __name__ == "__main__":
    main()
