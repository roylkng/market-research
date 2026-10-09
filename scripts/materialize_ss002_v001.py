from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.ss002_v001_visual import build_visual_fallback_queue, build_visual_prompt


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("V001 input JSON must be object")
    return value


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p009-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    root = args.p009_root.resolve()
    p009 = _load(root / "ss002-p009-legibility.json")
    visual = _load(root / "ss002-p009-visual-manifest.json")
    queue = build_visual_fallback_queue(p009, visual)
    image_copy_count = 0

    for row in queue["requests"]:
        source = (root / row["relative_image_path"]).resolve()
        if root not in source.parents or not source.is_file():
            raise AlphaContractError("V001 visual image path missing or outside source root")
        raw = source.read_bytes()
        actual_sha = hashlib.sha256(raw).hexdigest()
        if actual_sha != row["image_sha256"]:
            raise AlphaContractError("V001 page image content SHA mismatch")
        if raw[:3] != bytes((255, 216, 255)) or raw[-2:] != bytes((255, 217)):
            raise AlphaContractError("V001 source image is not a complete JPEG")
        destination = args.out / "images" / f"{row['request_id']}.jpg"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        prompt = build_visual_prompt(row)
        if prompt["prompt_sha256"] != row["prompt_sha256"]:
            raise AlphaContractError("V001 prompt reproducibility mismatch")
        _write(args.out / "prompts" / f"{row['request_id']}.json", prompt)
        image_copy_count += 1

    if image_copy_count != 6:
        raise AlphaContractError("V001 must materialize exactly six page images")
    _write(args.out / "ss002-v001-queue.json", queue)
    summary = {
        "queue_id": queue["queue_id"],
        "queue_sha256": queue["queue_sha256"],
        "source_p009_pack_sha256": queue["source_p009_pack_sha256"],
        "source_p009_visual_manifest_sha256": queue[
            "source_p009_visual_manifest_sha256"
        ],
        "request_count": queue["request_count"],
        "sha_verified_image_count": image_copy_count,
        "symbols": sorted({row["symbol"] for row in queue["requests"]}),
        "page_numbers": [row["page_number"] for row in queue["requests"]],
        "model_inference_completed": False,
        "independent_semantic_audit_complete": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    _write(args.out / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
