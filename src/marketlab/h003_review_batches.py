from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

OUTCOME_RULE_ID = "H003-O001"
OUTCOME_RULE_SHA256 = "36cd0dab185a8f73bc3233cf16bc1685dc9ae9e25c27eb35b305343b1ea028b1"
BLIND_PACKAGE_SHA256 = "a21efa55f8d72f3d2ac6ceef56d57b9897232f25f2e4c8f13d6449481ad77cfb"
EXPECTED_PACKET_COUNT = 869
BATCH_SIZE = 20

PRIVATE_KEYS = frozenset(
    {
        "symbol",
        "company_name",
        "claim_id",
        "claim_hash",
        "candidate_id",
        "original_source_id",
        "source_bindings",
        "selected_passage_ids",
    }
)


class H003ReviewBatchError(ValueError):
    """Raised when frozen H003 blind packets cannot be safely sharded."""


def canonical_hash(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise H003ReviewBatchError("payload must contain finite JSON values") from exc
    return hashlib.sha256(raw).hexdigest()


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _assert_no_private_keys(value: Any, *, location: str = "root") -> None:
    if isinstance(value, dict):
        leaked = PRIVATE_KEYS.intersection(value)
        if leaked:
            raise H003ReviewBatchError(
                f"private binding key leaked at {location}: {sorted(leaked)}"
            )
        for key, item in value.items():
            _assert_no_private_keys(item, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_private_keys(item, location=f"{location}[{index}]")


def validate_packet(packet: dict[str, Any]) -> str:
    if not isinstance(packet, dict):
        raise H003ReviewBatchError("blind packet must be an object")
    if packet.get("schema_version") != 1:
        raise H003ReviewBatchError("blind packet schema changed")
    if packet.get("outcome_rule_id") != OUTCOME_RULE_ID:
        raise H003ReviewBatchError("blind packet outcome rule id changed")
    if packet.get("outcome_rule_sha256") != OUTCOME_RULE_SHA256:
        raise H003ReviewBatchError("blind packet outcome rule hash changed")
    packet_id = packet.get("packet_id")
    if not isinstance(packet_id, str) or not packet_id.startswith("H003O-"):
        raise H003ReviewBatchError("blind packet id is invalid")
    declared = packet.get("payload_sha256")
    unsigned = dict(packet)
    unsigned.pop("payload_sha256", None)
    if not isinstance(declared, str) or declared != canonical_hash(unsigned):
        raise H003ReviewBatchError(f"blind packet payload hash mismatch: {packet_id}")
    evidence = packet.get("evidence")
    if not isinstance(evidence, list):
        raise H003ReviewBatchError(f"blind packet evidence must be a list: {packet_id}")
    _assert_no_private_keys(packet, location=packet_id)
    return packet_id


def validate_source_document(
    document: dict[str, Any],
    public_manifest: dict[str, Any],
    *,
    expected_packet_count: int = EXPECTED_PACKET_COUNT,
) -> list[dict[str, Any]]:
    if not isinstance(document, dict) or not isinstance(public_manifest, dict):
        raise H003ReviewBatchError("source package and manifest must be objects")
    if document.get("schema_version") != 1:
        raise H003ReviewBatchError("blind package schema changed")
    if document.get("outcome_rule_id") != OUTCOME_RULE_ID:
        raise H003ReviewBatchError("blind package outcome rule id changed")
    if document.get("outcome_rule_sha256") != OUTCOME_RULE_SHA256:
        raise H003ReviewBatchError("blind package outcome rule hash changed")
    if document.get("market_outcomes_included") is not False:
        raise H003ReviewBatchError("blind package unexpectedly contains market outcomes")
    if document.get("live_capital_allowed") is not False:
        raise H003ReviewBatchError("blind package must keep live capital disabled")

    declared_package = document.get("package_sha256")
    unsigned = dict(document)
    unsigned.pop("package_sha256", None)
    recomputed_package = canonical_hash(unsigned)
    if declared_package != recomputed_package:
        raise H003ReviewBatchError("blind package canonical hash mismatch")
    if expected_packet_count == EXPECTED_PACKET_COUNT and declared_package != BLIND_PACKAGE_SHA256:
        raise H003ReviewBatchError("blind package is not the frozen H003-O001 package")

    if public_manifest.get("manifest_sha256"):
        manifest_unsigned = dict(public_manifest)
        declared_manifest = manifest_unsigned.pop("manifest_sha256")
        if declared_manifest != canonical_hash(manifest_unsigned):
            raise H003ReviewBatchError("public packet manifest hash mismatch")
    if public_manifest.get("outcome_rule_id") != OUTCOME_RULE_ID:
        raise H003ReviewBatchError("public packet manifest outcome rule id changed")
    if public_manifest.get("outcome_rule_sha256") != OUTCOME_RULE_SHA256:
        raise H003ReviewBatchError("public packet manifest outcome rule hash changed")
    if public_manifest.get("blind_package_sha256") != declared_package:
        raise H003ReviewBatchError("public manifest does not bind the blind package")
    if public_manifest.get("outcome_data_accessed") is not False:
        raise H003ReviewBatchError("public manifest reports outcome-data access")
    if public_manifest.get("market_outcomes_included") is not False:
        raise H003ReviewBatchError("public manifest reports market outcomes")
    if public_manifest.get("live_capital_allowed") is not False:
        raise H003ReviewBatchError("public manifest must keep live capital disabled")

    packets = document.get("packets")
    if not isinstance(packets, list):
        raise H003ReviewBatchError("blind package packets must be a list")
    if document.get("packet_count") != len(packets):
        raise H003ReviewBatchError("blind package packet_count mismatch")
    if public_manifest.get("packet_count") != len(packets):
        raise H003ReviewBatchError("public manifest packet_count mismatch")
    if len(packets) != expected_packet_count:
        raise H003ReviewBatchError(
            f"expected {expected_packet_count} blind packets, found {len(packets)}"
        )

    packet_ids = [validate_packet(packet) for packet in packets]
    if len(packet_ids) != len(set(packet_ids)):
        raise H003ReviewBatchError("duplicate blind packet id")
    return sorted(packets, key=lambda packet: str(packet["packet_id"]))


def shard_blind_packets(
    *,
    blind_packet_path: str | Path,
    public_manifest_path: str | Path,
    output_dir: str | Path,
    expected_packet_count: int = EXPECTED_PACKET_COUNT,
    batch_size: int = BATCH_SIZE,
) -> dict[str, Any]:
    if batch_size != BATCH_SIZE:
        raise H003ReviewBatchError(f"H003-O001 review batch size is frozen at {BATCH_SIZE}")
    source_path = Path(blind_packet_path)
    public_path = Path(public_manifest_path)
    try:
        document = json.loads(source_path.read_text(encoding="utf-8"))
        public_manifest = json.loads(public_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise H003ReviewBatchError(f"could not read frozen blind package: {exc}") from exc

    packets = validate_source_document(
        document,
        public_manifest,
        expected_packet_count=expected_packet_count,
    )
    source_file_sha256 = file_sha256(source_path)
    output = Path(output_dir)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    entries: list[dict[str, Any]] = []
    seen_ids: list[str] = []
    for zero_index in range(0, len(packets), batch_size):
        batch_number = zero_index // batch_size + 1
        chunk = packets[zero_index : zero_index + batch_size]
        packet_ids = [str(packet["packet_id"]) for packet in chunk]
        unsigned_batch = {
            "schema_version": 1,
            "outcome_rule_id": OUTCOME_RULE_ID,
            "outcome_rule_sha256": OUTCOME_RULE_SHA256,
            "source_blind_package_sha256": document["package_sha256"],
            "source_blind_file_sha256": source_file_sha256,
            "batch_number": batch_number,
            "packet_count": len(chunk),
            "packets": chunk,
            "private_binding_accessed": False,
            "market_outcomes_included": False,
            "live_capital_allowed": False,
        }
        batch_document = {
            **unsigned_batch,
            "batch_sha256": canonical_hash(unsigned_batch),
        }
        filename = f"batch-{batch_number:04d}.json"
        path = output / filename
        path.write_text(
            json.dumps(batch_document, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        entries.append(
            {
                "filename": filename,
                "batch_number": batch_number,
                "packet_count": len(chunk),
                "first_packet_id": packet_ids[0],
                "last_packet_id": packet_ids[-1],
                "packet_ids_sha256": canonical_hash(packet_ids),
                "batch_sha256": batch_document["batch_sha256"],
                "file_sha256": file_sha256(path),
            }
        )
        seen_ids.extend(packet_ids)

    expected_ids = [str(packet["packet_id"]) for packet in packets]
    if seen_ids != expected_ids or len(seen_ids) != len(set(seen_ids)):
        raise H003ReviewBatchError("review batch union does not exactly cover source packet ids")

    manifest_unsigned = {
        "schema_version": 1,
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "source_blind_package_sha256": document["package_sha256"],
        "source_blind_file_sha256": source_file_sha256,
        "source_public_manifest_sha256": public_manifest["manifest_sha256"],
        "packet_count": len(packets),
        "packet_ids_sha256": canonical_hash(expected_ids),
        "batch_size": batch_size,
        "batch_count": len(entries),
        "batches": entries,
        "private_binding_accessed": False,
        "market_outcomes_included": False,
        "live_capital_allowed": False,
    }
    manifest = {**manifest_unsigned, "manifest_sha256": canonical_hash(manifest_unsigned)}
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest
