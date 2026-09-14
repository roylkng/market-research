from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h022_dependence_diagnostic import (
    build_dependence_panel,
    summarize_dependence,
)


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run frozen H022-D004 dependence diagnostic")
    parser.add_argument("--outcome-report", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    report = _load_json(args.outcome_report)
    panel = build_dependence_panel(report)
    summary = summarize_dependence(panel)

    _write_json(args.out_dir / "diagnostic-panel.json", panel)
    _write_json(args.out_dir / "diagnostic-summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
