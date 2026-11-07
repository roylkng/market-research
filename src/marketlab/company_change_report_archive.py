"""Lossless history for generated reports, separate from the active evidence checkpoint.

Only derived reports are moved. Original source blobs and SQLite records are
untouched. Every byte is verified in an immutable archive before originals move.
This is bounded pilot storage, not an unlimited or multi-tenant object store.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_store import loads_unique, writable_workspace

FORMAT = "CC001-GENERATED-REPORT-HISTORY-v1"
MAX_PART_BYTES = 32 * 1024 * 1024
MAX_RUN_BYTES = 128 * 1024 * 1024
MAX_HISTORY_BYTES = 256 * 1024 * 1024
MAX_FILES = 25000
MANIFEST_LIMIT = 5 * 1024 * 1024


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            result.update(block)
    return result.hexdigest()


def report_path(name: str) -> PurePosixPath:
    if not isinstance(name, str):
        raise ChangeError("report path must be a string")
    path = PurePosixPath(name)
    if (path.as_posix() != name or "\\" in name or path.is_absolute()
            or ".." in path.parts or len(path.parts) < 2 or path.parts[0] != "reports"
            or path.suffix not in {".json", ".html"}):
        raise ChangeError("archive member is not a generated JSON/HTML report")
    return path


def verify_part(path: Path, expected_hash: str | None = None) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_PART_BYTES + MANIFEST_LIMIT:
        raise ChangeError("invalid report-history part size or type")
    actual_hash = digest(path)
    if expected_hash is not None and actual_hash != expected_hash:
        raise ChangeError("report-history archive hash mismatch")
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            names = [m.filename for m in members]
            if (not members or len(members) > MAX_FILES + 1
                    or len(names) != len(set(names)) or "manifest.json" not in names):
                raise ChangeError("duplicate, missing or excessive report-history members")
            if sum(m.file_size for m in members) > MAX_PART_BYTES + MANIFEST_LIMIT:
                raise ChangeError("report-history expanded-size limit exceeded")
            for member in members:
                if member.is_dir() or ((member.external_attr >> 16) & 0o170000) == 0o120000:
                    raise ChangeError("report-history directories and symlinks are forbidden")
                if member.filename != "manifest.json":
                    report_path(member.filename)
                elif member.file_size > MANIFEST_LIMIT:
                    raise ChangeError("report-history manifest is oversized")
            manifest = loads_unique(archive.read("manifest.json"))
            if (set(manifest) != {"format", "files", "expanded_bytes"}
                    or manifest["format"] != FORMAT or not isinstance(manifest["files"], dict)
                    or set(manifest["files"]) != set(names) - {"manifest.json"}):
                raise ChangeError("report-history manifest mismatch")
            total = 0
            for name, evidence in manifest["files"].items():
                if (not isinstance(evidence, dict) or set(evidence) != {"sha256", "size"}
                        or type(evidence["size"]) is not int or evidence["size"] < 0
                        or not re.fullmatch(r"[0-9a-f]{64}", str(evidence["sha256"]))):
                    raise ChangeError("invalid report-history member evidence")
                raw = archive.read(name)
                if len(raw) != evidence["size"] or hashlib.sha256(raw).hexdigest() != evidence["sha256"]:
                    raise ChangeError("report-history content integrity failure")
                total += len(raw)
            if total != manifest["expanded_bytes"] or total > MAX_PART_BYTES:
                raise ChangeError("report-history expanded total mismatch")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ChangeError("invalid report-history ZIP") from exc
    return {"sha256": actual_hash, "files": manifest["files"], "expanded_bytes": total}


def publish_bytes(raw: bytes, destination: Path) -> None:
    """Publish one immutable receipt, never replace differing bytes."""
    try:
        with destination.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if destination.read_bytes() != raw:
            raise ChangeError("report-history receipt conflict")


def archive_reports(workspace: Path, destination: Path) -> dict:
    root = writable_workspace(workspace)
    target = writable_workspace(destination)
    if target.is_relative_to(root) or root.is_relative_to(target):
        raise ChangeError("report history must be outside the active workspace")
    report_root = root / "reports"
    if report_root.is_symlink():
        raise ChangeError("report directory cannot be a symlink")
    paths = []
    for path in sorted(report_root.rglob("*")):
        if path.is_symlink():
            raise ChangeError("generated-report symlinks cannot be archived")
        if path.is_file():
            name = path.relative_to(root).as_posix()
            report_path(name)
            if path.stat().st_size > MAX_PART_BYTES:
                raise ChangeError("single generated report exceeds the part limit")
            paths.append((name, path))
    total = sum(p.stat().st_size for _, p in paths)
    if len(paths) > MAX_FILES or total > MAX_RUN_BYTES:
        raise ChangeError("generated-report batch exceeds archival limit")
    existing_files = list(target.iterdir())
    if any(p.is_symlink() or not p.is_file() for p in existing_files):
        raise ChangeError("unexpected report-history storage entry")
    stored = sum(p.stat().st_size for p in existing_files)
    if stored > MAX_HISTORY_BYTES:
        raise ChangeError("report-history pilot storage limit reached")
    if not paths:
        return {"format": FORMAT, "archived_reports": 0, "expanded_bytes": 0, "parts": []}
    batches, batch, size = [], [], 0
    for name, path in paths:
        item_size = path.stat().st_size
        if batch and size + item_size > MAX_PART_BYTES:
            batches.append(batch)
            batch, size = [], 0
        batch.append((name, path))
        size += item_size
    if batch:
        batches.append(batch)
    parts, all_files = [], {}
    for batch in batches:
        files = {name: {"sha256": digest(path), "size": path.stat().st_size} for name, path in batch}
        manifest = {"format": FORMAT, "files": files,
                    "expanded_bytes": sum(v["size"] for v in files.values())}
        with tempfile.NamedTemporaryFile(dir=target, prefix=".staging-", delete=False) as stream:
            temporary = Path(stream.name)
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, path in batch:
                    info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                    archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
                info = zipfile.ZipInfo("manifest.json", date_time=(2026, 1, 1, 0, 0, 0))
                archive.writestr(info, json.dumps(manifest, sort_keys=True), compress_type=zipfile.ZIP_DEFLATED)
            checked = verify_part(temporary)
            final = target / (checked["sha256"] + ".zip")
            additional = 0 if final.exists() else temporary.stat().st_size
            if stored + additional > MAX_HISTORY_BYTES:
                raise ChangeError("report-history pilot storage limit reached")
            try:
                os.link(temporary, final)  # Same-directory atomic creation, never overwrite.
            except FileExistsError:
                verify_part(final, checked["sha256"])
            stored += additional
            parts.append({"filename": final.name, "sha256": checked["sha256"],
                          "expanded_bytes": checked["expanded_bytes"], "file_count": len(files)})
            all_files.update({name: {**value, "part": final.name} for name, value in files.items()})
        finally:
            temporary.unlink(missing_ok=True)
    receipt = {"format": FORMAT, "archived_reports": len(paths), "expanded_bytes": total,
               "parts": parts, "files": all_files, "source_blobs_moved": 0, "database_modified": False}
    receipt["receipt_sha256"] = canonical_hash(receipt)
    serialized = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    if stored + len(serialized) > MAX_HISTORY_BYTES:
        raise ChangeError("report-history receipt exceeds pilot storage limit")
    receipt_path = target / (receipt["receipt_sha256"] + ".json")
    publish_bytes(serialized, receipt_path)
    # Check the completed immutable archive and every still-present original
    # before removing any active copy. A failure retains originals for recovery.
    for part in parts:
        verify_part(target / part["filename"], part["sha256"])
    for name, path in paths:
        if path.is_symlink() or digest(path) != all_files[name]["sha256"]:
            raise ChangeError("generated report changed during archival")
    for _, path in paths:
        path.unlink()
    return receipt


def restore_reports(receipt_path: Path, destination: Path) -> dict:
    if receipt_path.is_symlink() or not receipt_path.is_file() or receipt_path.stat().st_size > MANIFEST_LIMIT:
        raise ChangeError("invalid report-history receipt size or type")
    receipt = loads_unique(receipt_path.read_bytes())
    if receipt.get("format") != FORMAT or canonical_hash({k: v for k, v in receipt.items() if k != "receipt_sha256"}) != receipt.get("receipt_sha256"):
        raise ChangeError("report-history receipt integrity failure")
    if (len(receipt["files"]) > MAX_FILES or receipt["expanded_bytes"] > MAX_RUN_BYTES
            or len(receipt["files"]) != receipt["archived_reports"]):
        raise ChangeError("report-history restore limit or count mismatch")
    root = writable_workspace(destination)
    if any(root.iterdir()):
        raise ChangeError("report restoration requires an empty destination")
    checked_files = {}
    for part in receipt["parts"]:
        if (not re.fullmatch(r"[0-9a-f]{64}", str(part["sha256"]))
                or part["filename"] != part["sha256"] + ".zip"):
            raise ChangeError("unsafe report-history part reference")
        verified = verify_part(receipt_path.parent / part["filename"], part["sha256"])
        for name, value in verified["files"].items():
            if name in checked_files:
                raise ChangeError("duplicate report in history receipt")
            checked_files[name] = {**value, "part": part["filename"]}
    if checked_files != receipt["files"] or sum(v["size"] for v in checked_files.values()) != receipt["expanded_bytes"]:
        raise ChangeError("report-history receipt and parts disagree")
    # Every part has passed checks before any original path is recreated.
    for part in receipt["parts"]:
        with zipfile.ZipFile(receipt_path.parent / part["filename"]) as archive:
            for name, evidence in checked_files.items():
                if evidence["part"] != part["filename"]:
                    continue
                path = root / report_path(name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.read(name))
    return {"restored_reports": len(checked_files), "format": FORMAT}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("archive", "restore"))
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    args = parser.parse_args(argv)
    result = (archive_reports(args.workspace, args.history) if args.mode == "archive"
              else restore_reports(args.history, args.workspace))
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
