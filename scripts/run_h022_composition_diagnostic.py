from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from marketlab.h022_composition_diagnostic import (
    build_diagnostic_panel,
    summarize_diagnostic,
)


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
    parser = argparse.ArgumentParser(description="Run H022 composition/sector diagnostic")
    parser.add_argument("--outcome-report", type=Path, required=True)
    parser.add_argument("--reconstruction", type=Path, required=True)
    parser.add_argument("--current-u001", type=Path, required=True)
    parser.add_argument("--panel-out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    args = parser.parse_args()

    panel = build_diagnostic_panel(
        _load_json(args.outcome_report),
        _load_json(args.reconstruction),
        _load_json(args.current_u001),
    )
    summary = summarize_diagnostic(panel)
    _write_json(args.panel_out, panel)
    _write_json(args.summary_out, summary)
    print(
        json.dumps(
            {
                "composition_classification": summary["composition"]["classification"],
                "industry_classification": summary["industry"]["classification"],
                "panel_sha256": panel["panel_sha256"],
                "summary_sha256": summary["summary_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
