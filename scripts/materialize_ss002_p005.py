from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss002_p005_readiness import build_transaction_readiness


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p004-result", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    source = json.loads(args.p004_result.read_text(encoding="utf-8"))
    output = build_transaction_readiness(source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(
        f"gate={output['gate_id']} "
        f"all_cases={output['case_count']} "
        f"active_research={output['active_transaction_research_lens_count']} "
        f"underwriting_ready={output['underwriting_ready_count']}"
    )


if __name__ == "__main__":
    main()
