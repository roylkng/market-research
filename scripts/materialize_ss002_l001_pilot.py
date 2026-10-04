from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha import digest
from marketlab.ss002_l001_pilot import build_selected_prompt, select_pilot_sample


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p2-census", type=Path, required=True)
    parser.add_argument("--d003-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    p2 = _load(args.p2_census)
    d003 = _load(args.d003_root / "ss002-d003-text-corpus.json")
    sample = select_pilot_sample(p2=p2, d003=d003)

    args.output.mkdir(parents=True, exist_ok=True)
    prompts_dir = args.output / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    d3_by_id = {str(row["document_id"]): row for row in d003["documents"]}
    prompt_rows = []
    for selection in sample["selections"]:
        doc_id = str(selection["document_id"])
        meta = d3_by_id[doc_id]
        artifact_path = args.d003_root / str(meta["text_artifact_path"])
        doc = _load(artifact_path)
        prompt = build_selected_prompt(
            selection=selection,
            d003_document=doc,
        )
        filename = (
            f"{selection['family_rank']:02d}-"
            f"{selection['family']}-"
            f"{selection['symbol']}-"
            f"{doc_id[:12]}.json"
        )
        path = prompts_dir / filename
        path.write_text(
            json.dumps(
                prompt,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
        prompt_rows.append(
            {
                "family": selection["family"],
                "family_rank": selection["family_rank"],
                "symbol": selection["symbol"],
                "announcement_id": selection["announcement_id"],
                "document_id": doc_id,
                "prompt_path": f"prompts/{filename}",
                "prompt_sha256": prompt["prompt_sha256"],
                "segment_manifest_sha256": selection[
                    "segment_manifest_sha256"
                ],
                "segment_count": selection["segment_count"],
            }
        )

    sample_path = args.output / "ss002-l001-p1-sample.json"
    sample_path.write_text(
        json.dumps(
            sample,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "pilot_id": sample["pilot_id"],
        "sample_sha256": sample["sample_sha256"],
        "prompt_count": len(prompt_rows),
        "prompts": prompt_rows,
        "return_outcomes_opened": False,
        "model_inference_executed": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    manifest["manifest_sha256"] = digest(manifest)
    (args.output / "pilot-input-manifest.json").write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "sample_sha256": sample["sample_sha256"],
                "manifest_sha256": manifest["manifest_sha256"],
                "selected_document_count": sample["selected_document_count"],
                "family_counts": sample["family_counts"],
                "symbols": {
                    family: [
                        row["symbol"]
                        for row in sample["selections"]
                        if row["family"] == family
                    ]
                    for family in sample["families"]
                },
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
