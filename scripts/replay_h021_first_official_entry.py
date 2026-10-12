"""Verify sealed NSE Oct12 H021 entry prices against archived original bytes.

Requires the original source-complete market packet and both original
content-addressed files. Never retrieves new prices, orders stock, adjusts
dividends, or opens 20/60-session forward performance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from marketlab.h021_entry_replay import (
    replay_first_h021_entry,
    validate_first_h021_replay,
)
from scripts.acquire_h021_first_entry import load_and_verify_sources

ORIGINAL_ROOT = Path("research/prospective/h021/entry-observations")
ORIGINAL_PACKET_PATH = ORIGINAL_ROOT / "2026-10-12-first-entry-v1.json"


def _json_object(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path}: original H021 record must be a JSON object")
    return data


def _replay_raw(root: Path, source: dict, kind: str, suffix: str) -> bytes:
    if not isinstance(source, dict):
        raise TypeError(f"{kind}: source receipt unavailable")
    digest = source.get("raw_sha256")
    if (
        not isinstance(digest, str) or len(digest) != 64
        or any(x not in "0123456789abcdef" for x in digest)
    ):
        raise ValueError(f"{kind}: NSE original raw SHA invalid")
    raw = (root / "raw" / "sha256" / f"{digest}{suffix}").read_bytes()
    if not raw or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"{kind}: original NSE source bytes changed or disappeared")
    return raw


def reproduce_entry(
    root: Path, *, packet_path: Path | None = None,
) -> dict:
    frozen_intent, frozen_universe = load_and_verify_sources()
    actual_path = packet_path if packet_path is not None else root / (
        "2026-10-12-first-entry-v1.json"
    )
    original = _json_object(actual_path)
    receipts = original.get("source_receipts")
    if not isinstance(receipts, dict):
        raise TypeError("H021 first-entry raw source receipts missing")
    stock_zip = _replay_raw(root, receipts.get("udiff"), "udiff", ".zip")
    index_csv = _replay_raw(root, receipts.get("index"), "index", ".csv")
    result = replay_first_h021_entry(
        original_packet=original,
        frozen_intent=frozen_intent,
        frozen_universe=frozen_universe,
        stock_udiff_zip=stock_zip,
        nifty500_index_csv=index_csv,
    )
    validate_first_h021_replay(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-dir", type=Path, default=ORIGINAL_ROOT)
    parser.add_argument("--original-packet", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    reproduced = reproduce_entry(
        args.original_dir, packet_path=args.original_packet
    )
    encoded = json.dumps(
        reproduced, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False,
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("sealed original NSE source replay changed")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as f:
                f.write(encoded)
    print(json.dumps({
        "replay_id": reproduced["replay_id"],
        "original_nse_source_sha": reproduced["source_receipts"]["stock_udiff"]["raw_sha256"],
        "nifty500_source_sha": reproduced["source_receipts"]["index_csv"]["raw_sha256"],
        "replayed_symbol_count": reproduced["selected_stock_source_count"],
        "research_entry_source_observed": True,
        "verified_actual_trade_fill": False,
        "dividends_and_cash_action_return_basis_verified": False,
        "return_outcomes_opened": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
