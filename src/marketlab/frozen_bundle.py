from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.events import PROSPECTIVE, FinancialEvent
from marketlab.expectations import (
    FROZEN_SIGNAL_RULE_SHA256,
    ExpectationCaptureRecord,
    FrozenExpectationManifest,
    _manifest_from_dict,
    _record_from_dict,
)
from marketlab.universe import UniverseSnapshot

EXPECTED_BUNDLE_SHA256 = "33ecb6496f02adc9d856aeeeee1e624df83e03d9e00a204c0c6ace26ee06b3b3"
EXPECTED_MANIFEST_ID = "dc7757f4577f0b97a63bb86145429045c190522470ce64cfddff6059ccd07b80"


class FrozenBundleError(ValueError):
    """Raised when frozen H002 expectation evidence is inconsistent or too late."""


@dataclass(frozen=True)
class FrozenBundleView:
    bundle_sha256: str
    cohort_id: str
    universe_snapshot_sha256: str
    signal_rule_sha256: str
    generated_at_utc: str
    manifest: FrozenExpectationManifest
    records_by_symbol: dict[str, ExpectationCaptureRecord]
    anchored_at_utc: str
    anchor_source_commit_sha: str
    anchor_workflow_run_id: str

    def resolve_for_event(self, event: FinancialEvent) -> ExpectationCaptureRecord:
        if event.mode != PROSPECTIVE:
            raise FrozenBundleError("actual event must be PROSPECTIVE")
        provenance = event.provenance
        if provenance.cohort_id != self.cohort_id:
            raise FrozenBundleError("event cohort does not match frozen bundle")
        if provenance.universe_snapshot_sha256 != self.universe_snapshot_sha256:
            raise FrozenBundleError("event universe hash does not match frozen bundle")
        if not provenance.exchange_published_at_utc:
            raise FrozenBundleError("prospective event is missing exchange publication timestamp")

        publication = _timestamp(provenance.exchange_published_at_utc, "event publication")
        anchor = _timestamp(self.anchored_at_utc, "bundle anchor")
        manifest_frozen = _timestamp(self.manifest.frozen_at_utc, "manifest frozen_at")
        if anchor >= publication:
            raise FrozenBundleError(
                "expectation bundle was not externally anchored before publication"
            )
        if manifest_frozen >= publication:
            raise FrozenBundleError("expectation manifest was not frozen before publication")

        symbol = event.symbol.upper()
        try:
            record = self.records_by_symbol[symbol]
        except KeyError as exc:
            raise FrozenBundleError(f"no frozen expectation record for {symbol}") from exc
        captured = _timestamp(record.captured_at_utc, "expectation captured_at")
        if captured >= publication:
            raise FrozenBundleError("expectation record was not captured before publication")

        expectation = record.expectation
        if expectation.symbol.upper() != symbol:
            raise FrozenBundleError("expectation symbol does not match event")
        if _period(event.reporting_period_end) != expectation.target_period_end:
            raise FrozenBundleError("expectation target period does not match event")
        if (
            (event.reporting_quarter or "").strip().casefold()
            != expectation.target_quarter.strip().casefold()
        ):
            raise FrozenBundleError("expectation reporting quarter does not match event")
        if (
            event.accounting_basis.strip().casefold()
            != expectation.accounting_basis.strip().casefold()
        ):
            raise FrozenBundleError("expectation accounting basis does not match event")
        return record


def _canonical_hash(payload: Any) -> str:
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FrozenBundleError("bundle payload must contain finite JSON values") from exc
    return hashlib.sha256(encoded).hexdigest()


def _load_object(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FrozenBundleError(f"could not read frozen evidence {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FrozenBundleError(f"frozen evidence root must be an object: {path}")
    return payload


def _timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise FrozenBundleError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise FrozenBundleError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _period(value: str | None) -> str:
    if not value:
        raise FrozenBundleError("event reporting period end is required")
    from datetime import date
    import time

    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        pass
    for fmt in ("%d-%m-%Y", "%d-%b-%Y"):
        try:
            parsed = time.strptime(value, fmt)
            return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday).isoformat()
        except ValueError:
            continue
    raise FrozenBundleError(f"unsupported event reporting period: {value}")


def load_frozen_bundle(
    bundle_path: str | Path,
    anchor_metadata_path: str | Path,
    *,
    universe: UniverseSnapshot,
) -> FrozenBundleView:
    document = _load_object(bundle_path)
    declared = document.get("bundle_sha256")
    if not isinstance(declared, str) or len(declared) != 64:
        raise FrozenBundleError("bundle must declare a SHA-256")
    unsigned = dict(document)
    unsigned.pop("bundle_sha256", None)
    actual = _canonical_hash(unsigned)
    if actual != declared:
        raise FrozenBundleError(f"bundle hash mismatch: declared={declared}, recomputed={actual}")
    if declared != EXPECTED_BUNDLE_SHA256:
        raise FrozenBundleError("bundle does not match the externally anchored FY27-Q2 artifact")
    if document.get("cohort_id") != universe.cohort_id:
        raise FrozenBundleError("bundle cohort does not match universe")
    if document.get("universe_snapshot_sha256") != universe.sha256:
        raise FrozenBundleError("bundle universe hash does not match universe")
    if document.get("signal_rule_sha256") != FROZEN_SIGNAL_RULE_SHA256:
        raise FrozenBundleError("bundle signal-rule hash does not match H002-R001")

    manifest_payload = document.get("expectation_manifest")
    records_payload = document.get("expectations")
    if not isinstance(manifest_payload, dict) or not isinstance(records_payload, list):
        raise FrozenBundleError("bundle is missing manifest or expectation records")
    manifest = _manifest_from_dict(manifest_payload)
    if manifest.manifest_id != EXPECTED_MANIFEST_ID:
        raise FrozenBundleError("bundle manifest id does not match external anchor")
    if manifest.cohort_id != universe.cohort_id:
        raise FrozenBundleError("manifest cohort does not match universe")
    if manifest.universe_snapshot_sha256 != universe.sha256:
        raise FrozenBundleError("manifest universe hash does not match universe")
    if manifest.signal_rule_sha256 != FROZEN_SIGNAL_RULE_SHA256:
        raise FrozenBundleError("manifest signal-rule hash does not match H002-R001")
    if manifest.uncovered_symbols:
        raise FrozenBundleError("complete FY27-Q2 bundle cannot contain uncovered symbols")

    records: dict[str, ExpectationCaptureRecord] = {}
    by_record_id: dict[str, ExpectationCaptureRecord] = {}
    for payload in records_payload:
        if not isinstance(payload, dict):
            raise FrozenBundleError("expectation record must be an object")
        record = _record_from_dict(payload)
        symbol = record.expectation.symbol.upper()
        if symbol in records:
            raise FrozenBundleError(f"duplicate frozen expectation symbol: {symbol}")
        records[symbol] = record
        by_record_id[record.record_id] = record

    expected_symbols = {member.symbol.upper() for member in universe.members}
    if set(records) != expected_symbols:
        missing = sorted(expected_symbols - set(records))
        extra = sorted(set(records) - expected_symbols)
        raise FrozenBundleError(f"bundle coverage mismatch; missing={missing}, extra={extra}")
    if len(manifest.records) != len(records):
        raise FrozenBundleError("manifest record count does not match expectation bundle")
    for entry in manifest.records:
        record = by_record_id.get(entry.record_id)
        if record is None:
            raise FrozenBundleError(f"manifest references missing record: {entry.record_id}")
        if entry.symbol.upper() != record.expectation.symbol.upper():
            raise FrozenBundleError("manifest symbol does not match expectation record")
        if (
            entry.slot_id != record.slot_id
            or entry.expectation_id != record.expectation.expectation_id
        ):
            raise FrozenBundleError("manifest entry identity does not match expectation record")

    metadata = _load_object(anchor_metadata_path)
    if metadata.get("cohort_id") != universe.cohort_id:
        raise FrozenBundleError("anchor metadata cohort does not match universe")
    if metadata.get("expectation_bundle_present") is not True:
        raise FrozenBundleError("anchor metadata does not attest an expectation bundle")
    if metadata.get("expectation_bundle_sha256") != declared:
        raise FrozenBundleError("anchor metadata bundle hash mismatch")
    if metadata.get("expectation_manifest_id") != manifest.manifest_id:
        raise FrozenBundleError("anchor metadata manifest id mismatch")
    if metadata.get("freeze_ready") is not True:
        raise FrozenBundleError("anchor metadata is not freeze-ready")
    if (
        metadata.get("captured_count") != len(universe.members)
        or metadata.get("member_count") != len(universe.members)
    ):
        raise FrozenBundleError("anchor metadata coverage count mismatch")
    anchored_at = metadata.get("anchored_at_utc")
    source_commit = metadata.get("source_commit_sha")
    run_id = metadata.get("workflow_run_id")
    if not isinstance(anchored_at, str):
        raise FrozenBundleError("anchor metadata timestamp is required")
    _timestamp(anchored_at, "bundle anchor")
    if not isinstance(source_commit, str) or len(source_commit) < 7:
        raise FrozenBundleError("anchor source commit SHA is required")
    if not isinstance(run_id, str) or not run_id:
        raise FrozenBundleError("anchor workflow run id is required")

    return FrozenBundleView(
        bundle_sha256=declared,
        cohort_id=universe.cohort_id,
        universe_snapshot_sha256=universe.sha256,
        signal_rule_sha256=FROZEN_SIGNAL_RULE_SHA256,
        generated_at_utc=str(document.get("generated_at_utc") or ""),
        manifest=manifest,
        records_by_symbol=records,
        anchored_at_utc=anchored_at,
        anchor_source_commit_sha=source_commit,
        anchor_workflow_run_id=run_id,
    )
