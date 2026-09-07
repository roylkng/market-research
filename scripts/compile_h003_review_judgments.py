from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from marketlab.h003_review import (
    REVIEW_RULE_ID,
    REVIEW_RULE_SHA256,
    H003ReviewError,
    NormalizedClaimDraft,
    build_review_decision,
)


class JudgmentCompileError(ValueError):
    pass


def _canonical_hash(payload: Any) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JudgmentCompileError(f"could not read JSON {path}: {exc}") from exc


def _validate_batch_manifest(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(document, dict):
        raise JudgmentCompileError("batch manifest root must be an object")
    unsigned = dict(document)
    declared = unsigned.pop("manifest_sha256", None)
    if not isinstance(declared, str) or declared != _canonical_hash(unsigned):
        raise JudgmentCompileError("batch manifest hash mismatch")
    entries = document.get("batches")
    if not isinstance(entries, list) or not entries:
        raise JudgmentCompileError("batch manifest contains no batches")
    by_file: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise JudgmentCompileError("batch manifest entry must be an object")
        filename = str(entry.get("file") or "")
        if not filename or filename in by_file:
            raise JudgmentCompileError(f"invalid/duplicate batch filename: {filename!r}")
        by_file[filename] = entry
    if int(document.get("batch_count", -1)) != len(by_file):
        raise JudgmentCompileError("batch manifest batch_count mismatch")
    return by_file


def _validate_blind_payloads(document: Any) -> dict[str, str]:
    if not isinstance(document, list):
        raise JudgmentCompileError("blind payload root must be a list")
    result: dict[str, str] = {}
    for item in document:
        if not isinstance(item, dict):
            raise JudgmentCompileError("blind payload item must be an object")
        candidate_id = str(item.get("candidate_id") or "")
        payload_sha = str(item.get("payload_sha256") or "")
        if not candidate_id or candidate_id in result:
            raise JudgmentCompileError(f"invalid/duplicate blind candidate: {candidate_id!r}")
        unsigned = dict(item)
        unsigned.pop("payload_sha256", None)
        if (
            item.get("schema_version") != 1
            or item.get("review_rule_id") != REVIEW_RULE_ID
            or item.get("review_rule_sha256") != REVIEW_RULE_SHA256
            or len(payload_sha) != 64
            or payload_sha != _canonical_hash(unsigned)
        ):
            raise JudgmentCompileError(f"invalid blind payload identity/hash: {candidate_id}")
        result[candidate_id] = payload_sha
    return result


def _normalized_claim(value: Any) -> NormalizedClaimDraft | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise JudgmentCompileError("normalized_claim must be an object or null")
    try:
        return NormalizedClaimDraft(**value)
    except TypeError as exc:
        raise JudgmentCompileError(f"invalid normalized claim: {exc}") from exc


def compile_batch(
    *,
    judgment_document: dict[str, Any],
    source_batch: list[dict[str, Any]],
    expected_batch_file: str,
    expected_batch_sha256: str,
    blind_payload_sha_by_candidate: dict[str, str],
    reviewed_at_utc: str,
) -> list[dict[str, Any]]:
    if not isinstance(judgment_document, dict):
        raise JudgmentCompileError("judgment document root must be an object")
    if judgment_document.get("schema_version") != 1:
        raise JudgmentCompileError("unsupported judgment schema")
    if judgment_document.get("batch_file") != expected_batch_file:
        raise JudgmentCompileError("judgment batch_file does not match manifest")
    if judgment_document.get("batch_sha256") != expected_batch_sha256:
        raise JudgmentCompileError("judgment batch_sha256 does not match manifest")
    if _canonical_hash(source_batch) != expected_batch_sha256:
        raise JudgmentCompileError("source batch bytes/content do not match manifest hash")

    reviewer_version = judgment_document.get("reviewer_version")
    if not isinstance(reviewer_version, str) or not reviewer_version.strip():
        raise JudgmentCompileError("reviewer_version is required")
    judgments = judgment_document.get("judgments")
    if not isinstance(judgments, list):
        raise JudgmentCompileError("judgments must be a list")

    expected_ids = [str(item.get("candidate_id") or "") for item in source_batch]
    observed_ids = [
        str(item.get("candidate_id") or "") if isinstance(item, dict) else ""
        for item in judgments
    ]
    if observed_ids != expected_ids:
        raise JudgmentCompileError("judgment candidate order/coverage differs from frozen batch")
    if len(observed_ids) != len(set(observed_ids)):
        raise JudgmentCompileError("judgment batch contains duplicate candidate ids")

    decisions: list[dict[str, Any]] = []
    for source_item, item in zip(source_batch, judgments, strict=True):
        if not isinstance(item, dict):
            raise JudgmentCompileError("judgment item must be an object")
        candidate_id = str(item["candidate_id"])
        source_payload_sha = str(source_item.get("payload_sha256") or "")
        frozen_payload_sha = blind_payload_sha_by_candidate.get(candidate_id)
        if not frozen_payload_sha or frozen_payload_sha != source_payload_sha:
            raise JudgmentCompileError(
                f"blind payload binding mismatch for candidate {candidate_id}"
            )
        disposition = item.get("disposition")
        reason_code = item.get("reason_code")
        if disposition not in {"ACCEPTED", "REJECTED"}:
            raise JudgmentCompileError(f"invalid disposition for {candidate_id}: {disposition}")
        if not isinstance(reason_code, str):
            raise JudgmentCompileError(f"missing reason_code for {candidate_id}")
        note = item.get("note")
        if note is not None and not isinstance(note, str):
            raise JudgmentCompileError(f"note must be string/null for {candidate_id}")
        duplicate = item.get("duplicate_of_candidate_id")
        if duplicate is not None and not isinstance(duplicate, str):
            raise JudgmentCompileError(
                f"duplicate_of_candidate_id must be string/null for {candidate_id}"
            )
        try:
            decision = build_review_decision(
                candidate_id=candidate_id,
                blind_payload_sha256=frozen_payload_sha,
                disposition=disposition,
                reason_code=reason_code,
                reviewer_version=reviewer_version,
                reviewed_at_utc=reviewed_at_utc,
                note=note,
                duplicate_of_candidate_id=duplicate,
                normalized_claim=_normalized_claim(item.get("normalized_claim")),
            )
        except H003ReviewError as exc:
            raise JudgmentCompileError(
                f"invalid semantic judgment for {candidate_id}: {exc}"
            ) from exc
        decisions.append(decision.to_dict())
    return decisions


def _git_add_timestamp(path: Path, repo_root: Path) -> str:
    try:
        relative = path.resolve().relative_to(repo_root.resolve())
    except ValueError as exc:
        raise JudgmentCompileError(f"judgment file is outside repo root: {path}") from exc
    try:
        output = subprocess.check_output(
            [
                "git",
                "log",
                "--diff-filter=A",
                "--format=%aI",
                "--",
                relative.as_posix(),
            ],
            cwd=repo_root,
            text=True,
        ).strip().splitlines()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise JudgmentCompileError(
            f"could not resolve judgment creation commit for {relative}: {exc}"
        ) from exc
    if len(output) != 1:
        raise JudgmentCompileError(
            f"expected exactly one creation commit for {relative}, found {len(output)}"
        )
    timestamp = output[0]
    return timestamp[:-6] + "Z" if timestamp.endswith("+00:00") else timestamp


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile blind H003 semantic judgments into hash-bound ReviewDecision files."
    )
    parser.add_argument("--batch-manifest", type=Path, required=True)
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--blind-payloads", type=Path, required=True)
    parser.add_argument("--judgments-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    manifest = _load_json(args.batch_manifest)
    by_file = _validate_batch_manifest(manifest)
    blind_map = _validate_blind_payloads(_load_json(args.blind_payloads))
    args.out_dir.mkdir(parents=True, exist_ok=True)

    compiled_entries: list[dict[str, Any]] = []
    total_decisions = 0
    missing: list[str] = []
    for filename, entry in sorted(
        by_file.items(), key=lambda pair: int(pair[1].get("batch_index", -1))
    ):
        judgment_path = args.judgments_dir / filename
        if not judgment_path.exists():
            missing.append(filename)
            continue
        source_path = args.batch_dir / filename
        source_batch = _load_json(source_path)
        if not isinstance(source_batch, list):
            raise JudgmentCompileError(f"source batch must be a list: {source_path}")
        judgment_document = _load_json(judgment_path)
        reviewed_at = _git_add_timestamp(judgment_path, args.repo_root)
        decisions = compile_batch(
            judgment_document=judgment_document,
            source_batch=source_batch,
            expected_batch_file=filename,
            expected_batch_sha256=str(entry.get("batch_sha256") or ""),
            blind_payload_sha_by_candidate=blind_map,
            reviewed_at_utc=reviewed_at,
        )
        target = args.out_dir / filename
        target.write_text(
            json.dumps(decisions, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        compiled_entries.append(
            {
                "batch_index": int(entry["batch_index"]),
                "file": filename,
                "candidate_count": len(decisions),
                "source_batch_sha256": entry["batch_sha256"],
                "judgment_file_sha256": hashlib.sha256(judgment_path.read_bytes()).hexdigest(),
                "reviewed_at_utc": reviewed_at,
                "decision_list_sha256": _canonical_hash(decisions),
            }
        )
        total_decisions += len(decisions)

    if args.require_complete and missing:
        raise JudgmentCompileError(
            f"semantic judgments incomplete; missing {len(missing)} batches: {missing[:10]}"
        )
    unsigned = {
        "schema_version": 1,
        "review_rule_id": REVIEW_RULE_ID,
        "review_rule_sha256": REVIEW_RULE_SHA256,
        "source_batch_manifest_sha256": manifest["manifest_sha256"],
        "source_batch_count": int(manifest["batch_count"]),
        "compiled_batch_count": len(compiled_entries),
        "compiled_candidate_count": total_decisions,
        "missing_batch_count": len(missing),
        "missing_batches": missing,
        "complete": not missing,
        "entries": compiled_entries,
    }
    compiled_manifest = {**unsigned, "manifest_sha256": _canonical_hash(unsigned)}
    (args.out_dir / "manifest.json").write_text(
        json.dumps(compiled_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(compiled_manifest, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
