from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from marketlab.po001_s001 import evaluate_po001_s001_reports


def _load(path: Path) -> dict:
    return json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate frozen three-replica PO001 S001 stability study"
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    paths = sorted(args.root.rglob("replica-report.json.gz"))
    reports = [_load(path) for path in paths]
    result = evaluate_po001_s001_reports(reports)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    if not result["promotion"]["po001_v4_numerical_stability_established"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
