"""Reproduce source-bound Oct19 reverse-value research, never price targets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.l001_p017_reverse_falsification import (
    materialize_l001_p017,
    validate_l001_p017,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path,
        default=Path("research/l001/l001-p017-three-reverse-value-gates-v1.json"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = materialize_l001_p017(args.repo_root)
    validate_l001_p017(result, root=args.repo_root)
    text = (
        json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
    output = args.repo_root / args.output
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != text:
            raise SystemExit("P017 independent dated source replay disagrees")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists() and output.read_text(encoding="utf-8") != text:
            raise SystemExit("P017 immutable research report cannot be overwritten")
        output.write_text(text, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "ORIGINAL_SOURCE_REPORT_MATERIALIZED",
        "report_sha256": result["report_sha256"],
        "priced_dated_companies": len(result["dated_original_close_observations"]),
        "risk_adjusted_expected_return": None,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
