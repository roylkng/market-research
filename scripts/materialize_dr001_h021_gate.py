from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from marketlab.dr001_h021_gate import build_tier_a_h021_gate


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dossiers", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    dossiers = _load_json(args.dossiers)
    comparison = _load_json(args.comparison)
    output = build_tier_a_h021_gate(
        dossiers,
        comparison,
        dossier_path=str(args.dossiers),
        comparison_path=str(args.comparison),
        dossier_sha256=_sha256(args.dossiers),
        comparison_sha256=_sha256(args.comparison),
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        f"gate={output['gate_id']} "
        f"current={output['current_capture_date_ist']} "
        f"advance={output['action_counts'].get('ADVANCE_TO_VALUATION_AND_RED_TEAM', 0)} "
        f"watch={len(output['companies']) - output['action_counts'].get('ADVANCE_TO_VALUATION_AND_RED_TEAM', 0)}"
    )


if __name__ == "__main__":
    main()
