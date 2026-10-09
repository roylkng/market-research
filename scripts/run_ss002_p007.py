from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from marketlab.marketdata import udiff_url
from marketlab.nse import NSEClient
from marketlab.ss002_p007_payoff import PRICE_SESSION, build_p007_price_scenarios


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p006-packet", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    packet = json.loads(args.p006_packet.read_text(encoding="utf-8"))
    if not isinstance(packet, dict):
        raise TypeError("P006 packet must be a JSON object")
    source_url = udiff_url(date.fromisoformat(PRICE_SESSION))
    raw = NSEClient(timeout=args.timeout_seconds, attempts=4).archive_bytes(source_url)
    raw_sha = hashlib.sha256(raw).hexdigest()
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = args.raw_dir / f"{raw_sha}.zip"
    if raw_path.exists() and raw_path.read_bytes() != raw:
        raise RuntimeError("P007 UDiFF content-addressed source mismatch")
    raw_path.write_bytes(raw)

    result = build_p007_price_scenarios(packet, udiff_raw=raw)
    result["source_url"] = source_url
    result["source_raw_path"] = str(raw_path)
    # Recompute panel SHA when source-provenance metadata is attached.
    from marketlab.alpha import digest
    result["panel_sha256"] = digest({k: v for k, v in result.items() if k != "panel_sha256"})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "panel_sha256": result["panel_sha256"],
        "official_bhavcopy_sha256": result["official_bhavcopy_sha256"],
        "matched_price_count": result["matched_price_count"],
        "mechanical_scenario_count": result["mechanical_scenario_count"],
        "feasibility_pass": result["feasibility_pass"],
        "case_prices_and_scenario_states": [
            {
                "symbol": row["symbol"],
                "official_close_inr": row["official_close_inr"],
                "price_state": row["price_state"],
                "scenario_family": row["scenario_family"],
            }
            for row in result["rows"]
        ],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
