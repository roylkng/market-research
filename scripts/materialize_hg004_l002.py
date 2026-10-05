from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg004_l002 import build_transaction_term_synthesis


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    output = build_transaction_term_synthesis(_load(args.run))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            output,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"synthesis={output['synthesis_id']} "
        f"ready={output['payoff_model_ready_symbol_count']} "
        f"partial={output['partial_terms_symbol_count']} "
        f"procedural={output['procedural_or_historical_symbol_count']}"
    )


if __name__ == "__main__":
    main()
