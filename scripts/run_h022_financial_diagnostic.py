from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from marketlab.h022_financial_diagnostic import summarize_financial_composition


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run H022 financial-composition diagnostic")
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    args = parser.parse_args()

    summary = summarize_financial_composition(_load_json(args.panel))
    _write_json(args.summary_out, summary)
    print(
        json.dumps(
            {
                "additional_nonfinancial_recovery_classification": summary[
                    "additional_nonfinancial_recovery_classification"
                ],
                "summary_sha256": summary["summary_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
