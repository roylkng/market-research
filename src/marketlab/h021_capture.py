from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from marketlab.h021 import validate_snapshot

ALLOWED_CAPTURE_STATES = frozenset(
    {
        "OBSERVED",
        "PARTIAL",
        "NO_COVERAGE",
        "SOURCE_BLOCKED",
        "IDENTITY_UNRESOLVED",
    }
)
NON_OBSERVATION_STATES = frozenset(
    {"NO_COVERAGE", "SOURCE_BLOCKED", "IDENTITY_UNRESOLVED"}
)
CANONICAL_SOURCE_VERSION = "H021-public-stockanalysis-spgi-plus-trendlyne-secondary-v1"
CANONICAL_UNIVERSE_PATH = "research/prospective/universes/FY27-Q2-2026-09-06.json"
CANONICAL_UNIVERSE_BLOB_SHA = "8026e81faee3e913d2fba1dba72d60603b69fa07"
CANONICAL_PROTOCOL_PATH = "research/H021_PROSPECTIVE_PROTOCOL_V1.md"
CANONICAL_COMPARISON_CONTRACT_PATH = "research/H021_COMPARISON_CONTRACT_V1.md"
CANONICAL_BATCH_SPEC_PATH = "research/prospective/h021/capture-batches-v1.json"
SEALER_VERSION = "H021_CAPTURE_SEALER_V2"
CAPTURE_ID_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})-full-u001-v(?P<version>[1-9]\d*)$"
)
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class CaptureArtifacts:
    logical_capture_id: str
    payload_json: bytes
    payload_gzip: bytes
    manifest: dict
    report_markdown: str


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(payload: dict) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")


def deterministic_gzip(payload: bytes) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0, compresslevel=9) as out:
        out.write(payload)
    return buffer.getvalue()


def _parse_utc_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        return None
    return parsed.astimezone(UTC)


def _valid_iso_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return parsed.isoformat() == value


def _valid_currency(value: object) -> bool:
    return isinstance(value, str) and CURRENCY_RE.fullmatch(value) is not None


def _universe_members(universe: dict) -> list[dict]:
    members = universe.get("members")
    if not isinstance(members, list) or not members:
        raise ValueError("universe members must be a non-empty list")
    return members


def _batch_for_rank(batch_spec: dict, rank: int) -> str | None:
    batches = batch_spec.get("batches")
    if not isinstance(batches, list):
        return None
    matches = [
        batch.get("batch_id")
        for batch in batches
        if isinstance(batch, dict)
        and isinstance(batch.get("rank_min"), int)
        and isinstance(batch.get("rank_max"), int)
        and batch["rank_min"] <= rank <= batch["rank_max"]
    ]
    if len(matches) != 1 or not isinstance(matches[0], str):
        return None
    return matches[0]


def validate_capture_inputs(universe: dict, batch_spec: dict) -> list[str]:
    errors: list[str] = []
    members = universe.get("members")
    if not isinstance(members, list):
        return ["universe members must be a list"]

    expected_count = batch_spec.get("expected_member_count")
    if (
        not isinstance(expected_count, int)
        or isinstance(expected_count, bool)
        or expected_count <= 0
    ):
        errors.append("batch expected_member_count must be a positive integer")
    elif len(members) != expected_count:
        errors.append(
            f"universe member count {len(members)} does not equal batch expected count "
            f"{expected_count}"
        )

    symbols: list[str] = []
    ranks: list[int] = []
    for index, member in enumerate(members):
        if not isinstance(member, dict):
            errors.append(f"universe member[{index}] must be an object")
            continue
        symbol = member.get("symbol")
        rank = member.get("rank")
        isin = member.get("isin")
        if not isinstance(symbol, str) or not symbol:
            errors.append(f"universe member[{index}] invalid symbol")
        else:
            symbols.append(symbol)
        if not isinstance(rank, int) or isinstance(rank, bool) or rank <= 0:
            errors.append(f"universe member[{index}] invalid rank")
        else:
            ranks.append(rank)
            if _batch_for_rank(batch_spec, rank) is None:
                errors.append(f"universe rank {rank} belongs to no unique frozen batch")
        if not isinstance(isin, str) or not isin:
            errors.append(f"universe member[{index}] invalid isin")

    if len(symbols) != len(set(symbols)):
        errors.append("universe contains duplicate symbols")
    if len(ranks) != len(set(ranks)):
        errors.append("universe contains duplicate ranks")
    if isinstance(expected_count, int) and sorted(ranks) != list(range(1, expected_count + 1)):
        errors.append("universe ranks must cover 1..expected_member_count exactly once")

    if batch_spec.get("universe_path") != CANONICAL_UNIVERSE_PATH:
        errors.append("batch spec universe_path does not match frozen H021 universe")
    if batch_spec.get("universe_git_blob_sha") != CANONICAL_UNIVERSE_BLOB_SHA:
        errors.append("batch spec universe_git_blob_sha does not match frozen H021 universe")
    if batch_spec.get("hypothesis_id") != "H021":
        errors.append("batch spec hypothesis_id must equal H021")
    return errors


def _identity_maps(universe: dict) -> tuple[dict[str, dict], set[str]]:
    members = _universe_members(universe)
    by_symbol = {member["symbol"]: member for member in members}
    return by_symbol, set(by_symbol)


def _validate_capture_id(snapshot: dict) -> list[str]:
    logical_capture_id = snapshot.get("logical_capture_id")
    if not isinstance(logical_capture_id, str):
        return ["logical_capture_id must match YYYY-MM-DD-full-u001-vN"]

    match = CAPTURE_ID_RE.fullmatch(logical_capture_id)
    if match is None:
        return ["logical_capture_id must match YYYY-MM-DD-full-u001-vN"]

    errors: list[str] = []
    capture_date = snapshot.get("capture_date_ist")
    if match.group("date") != capture_date:
        errors.append("logical_capture_id date must equal capture_date_ist")

    version = int(match.group("version"))
    if version > 1:
        reason = snapshot.get("correction_reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append("capture versions greater than v1 require a correction_reason")
    return errors


def _validate_primary_eps_semantics(row: dict, index: int) -> list[str]:
    if row.get("consensus_eps") is None:
        return []
    errors: list[str] = []
    if not _valid_iso_date(row.get("period_ending")):
        errors.append(
            f"observation[{index}] primary EPS requires ISO period_ending YYYY-MM-DD"
        )
    if not _valid_currency(row.get("eps_currency")):
        errors.append(
            f"observation[{index}] primary EPS requires uppercase 3-letter eps_currency"
        )
    return errors


def validate_full_capture(snapshot: dict, universe: dict, batch_spec: dict) -> list[str]:
    errors = list(validate_snapshot(snapshot))
    errors.extend(validate_capture_inputs(universe, batch_spec))
    errors.extend(_validate_capture_id(snapshot))

    if snapshot.get("source_version") != CANONICAL_SOURCE_VERSION:
        errors.append("source_version does not match frozen H021 source version")
    if snapshot.get("universe_path") != CANONICAL_UNIVERSE_PATH:
        errors.append("universe_path does not match frozen H021 universe")
    if snapshot.get("universe_git_blob_sha") != CANONICAL_UNIVERSE_BLOB_SHA:
        errors.append("universe_git_blob_sha does not match frozen H021 universe")
    if snapshot.get("protocol_path") != CANONICAL_PROTOCOL_PATH:
        errors.append("protocol_path does not match frozen H021 prospective protocol")
    if snapshot.get("comparison_contract_path") != CANONICAL_COMPARISON_CONTRACT_PATH:
        errors.append("comparison_contract_path does not match frozen H021 comparison contract")
    if snapshot.get("batch_spec_path") != CANONICAL_BATCH_SPEC_PATH:
        errors.append("batch_spec_path does not match frozen H021 batch spec")

    captured_at = _parse_utc_timestamp(snapshot.get("captured_at_utc"))
    capture_date_raw = snapshot.get("capture_date_ist")
    try:
        capture_date = date.fromisoformat(capture_date_raw)
    except (TypeError, ValueError):
        capture_date = None
    if captured_at is None:
        errors.append("captured_at_utc must be an explicit UTC timestamp")
    elif capture_date is not None and captured_at.astimezone(IST).date() != capture_date:
        errors.append("capture_date_ist must equal the India date of captured_at_utc")

    observations = snapshot.get("observations")
    if not isinstance(observations, list):
        return errors

    expected_count = batch_spec.get("expected_member_count")
    if isinstance(expected_count, int) and len(observations) != expected_count:
        errors.append(
            f"capture has {len(observations)} observations; expected {expected_count} frozen symbols"
        )

    universe_by_symbol, universe_symbols = _identity_maps(universe)
    observed_symbols = {
        symbol
        for row in observations
        if isinstance(row, dict)
        for symbol in [row.get("symbol")]
        if isinstance(symbol, str) and symbol
    }
    missing_symbols = sorted(universe_symbols - observed_symbols)
    extra_symbols = sorted(observed_symbols - universe_symbols)
    if missing_symbols or extra_symbols:
        errors.append(
            "capture symbol set differs from frozen U001; "
            f"missing={missing_symbols} extra={extra_symbols}"
        )

    for index, row in enumerate(observations):
        if not isinstance(row, dict):
            continue
        symbol = row.get("symbol")
        member = universe_by_symbol.get(symbol)
        state = row.get("data_state")
        if state not in ALLOWED_CAPTURE_STATES:
            errors.append(f"observation[{index}] invalid data_state: {state!r}")
        notes = row.get("retrieval_notes")
        if not isinstance(notes, str) or not notes.strip():
            errors.append(f"observation[{index}] retrieval_notes must be a non-empty string")
        errors.extend(_validate_primary_eps_semantics(row, index))
        if member is None:
            continue

        if row.get("isin") != member.get("isin"):
            errors.append(f"observation[{index}] ISIN mismatch for {symbol}")
        if row.get("universe_rank") != member.get("rank"):
            errors.append(f"observation[{index}] universe_rank mismatch for {symbol}")
        expected_batch = _batch_for_rank(batch_spec, member["rank"])
        if row.get("batch_id") != expected_batch:
            errors.append(f"observation[{index}] batch_id mismatch for {symbol}")

        if state in NON_OBSERVATION_STATES:
            forbidden_values = {
                field: row.get(field)
                for field in (
                    "period_ending",
                    "consensus_eps",
                    "eps_currency",
                    "revenue_growth_forecast_pct",
                    "profit_growth_estimate_pct",
                    "analyst_count",
                    "target_price_inr",
                )
                if row.get(field) is not None
            }
            if forbidden_values:
                errors.append(
                    f"observation[{index}] {state} must not carry forward forecast values: "
                    f"{sorted(forbidden_values)}"
                )

    return errors


def coverage_summary(snapshot: dict) -> dict:
    observations = snapshot["observations"]
    states = Counter(row["data_state"] for row in observations)
    analyst_counts = [row.get("analyst_count") for row in observations]
    explicit_eps = sum(row.get("consensus_eps") is not None for row in observations)
    period_count = sum(_valid_iso_date(row.get("period_ending")) for row in observations)
    currency_count = sum(_valid_currency(row.get("eps_currency")) for row in observations)
    semantic_complete = sum(
        row.get("consensus_eps") is not None
        and _valid_iso_date(row.get("period_ending"))
        and _valid_currency(row.get("eps_currency"))
        for row in observations
    )
    return {
        "total": len(observations),
        **{state: states.get(state, 0) for state in sorted(ALLOWED_CAPTURE_STATES)},
        "current_analyst_count_ge_5": sum(
            isinstance(value, int) and value >= 5 for value in analyst_counts
        ),
        "current_analyst_count_2_to_4": sum(
            isinstance(value, int) and 2 <= value <= 4 for value in analyst_counts
        ),
        "current_analyst_count_lt_2_or_null": sum(
            value is None or (isinstance(value, int) and value < 2) for value in analyst_counts
        ),
        "explicit_consensus_eps": explicit_eps,
        "explicit_period_ending": period_count,
        "explicit_eps_currency": currency_count,
        "primary_eps_semantics_complete": semantic_complete,
    }


def batch_summary(snapshot: dict, batch_spec: dict) -> list[dict]:
    observations = snapshot["observations"]
    summaries: list[dict] = []
    for batch in batch_spec["batches"]:
        batch_id = batch["batch_id"]
        rows = [row for row in observations if row.get("batch_id") == batch_id]
        state_counts = Counter(row["data_state"] for row in rows)
        summaries.append(
            {
                "batch_id": batch_id,
                "rank_min": batch["rank_min"],
                "rank_max": batch["rank_max"],
                "processed": len(rows),
                "state_counts": {
                    state: state_counts.get(state, 0) for state in sorted(ALLOWED_CAPTURE_STATES)
                },
            }
        )
    return summaries


def _report(snapshot: dict, summary: dict, batches: list[dict], payload_sha: str) -> str:
    rows = [
        f"# H021 full U001 consensus capture — {snapshot['capture_date_ist']}",
        "",
        "Research only. Live capital disabled. Return outcomes unopened.",
        "",
        "## Capture identity",
        "",
        f"- Logical capture: `{snapshot['logical_capture_id']}`",
        f"- Captured at UTC: `{snapshot['captured_at_utc']}`",
        f"- Source version: `{snapshot['source_version']}`",
        f"- Frozen universe blob: `{snapshot['universe_git_blob_sha']}`",
        f"- Canonical payload SHA-256: `{payload_sha}`",
        "",
        "## Coverage",
        "",
        "| State | Count |",
        "|---|---:|",
    ]
    for state in sorted(ALLOWED_CAPTURE_STATES):
        rows.append(f"| {state} | {summary[state]} |")
    rows.extend(
        [
            "",
            f"Explicit consensus EPS: **{summary['explicit_consensus_eps']} / {summary['total']}**",
            (
                "Primary EPS semantics complete: "
                f"**{summary['primary_eps_semantics_complete']} / "
                f"{summary['explicit_consensus_eps']} EPS rows**"
            ),
            "",
            f"Analyst count >=5: **{summary['current_analyst_count_ge_5']}**",
            f"Analyst count 2-4: **{summary['current_analyst_count_2_to_4']}**",
            (
                "Analyst count <2 or unavailable: "
                f"**{summary['current_analyst_count_lt_2_or_null']}**"
            ),
            "",
            "## Frozen batches",
            "",
        ]
    )
    for batch in batches:
        rows.append(
            f"- {batch['batch_id']} ranks {batch['rank_min']}-{batch['rank_max']}: "
            f"{batch['processed']} processed"
        )
    rows.extend(
        [
            "",
            (
                "No price, return, H013, H019, H020, PF001, valuation, or outcome input is "
                "part of this capture artifact."
            ),
            "",
        ]
    )
    return "\n".join(rows)


def build_capture_artifacts(snapshot: dict, universe: dict, batch_spec: dict) -> CaptureArtifacts:
    errors = validate_full_capture(snapshot, universe, batch_spec)
    if errors:
        raise ValueError({"capture_errors": errors})

    payload_json = canonical_json_bytes(snapshot)
    payload_gzip = deterministic_gzip(payload_json)
    logical_capture_id = snapshot["logical_capture_id"]
    summary = coverage_summary(snapshot)
    batches = batch_summary(snapshot, batch_spec)
    payload_path = f"research/prospective/h021/captures/{logical_capture_id}.json.gz"

    manifest = {
        "schema_version": 2,
        "hypothesis_id": "H021",
        "sealer_version": SEALER_VERSION,
        "logical_capture_id": logical_capture_id,
        "capture_date_ist": snapshot["capture_date_ist"],
        "captured_at_utc": snapshot["captured_at_utc"],
        "universe_path": CANONICAL_UNIVERSE_PATH,
        "universe_git_blob_sha": CANONICAL_UNIVERSE_BLOB_SHA,
        "protocol_path": CANONICAL_PROTOCOL_PATH,
        "comparison_contract_path": CANONICAL_COMPARISON_CONTRACT_PATH,
        "batch_spec_path": CANONICAL_BATCH_SPEC_PATH,
        "source_version": CANONICAL_SOURCE_VERSION,
        "payload_path": payload_path,
        "payload_encoding": "gzip",
        "payload_canonical_json": True,
        "payload_uncompressed_sha256": _sha256(payload_json),
        "payload_uncompressed_bytes": len(payload_json),
        "payload_gzip_sha256": _sha256(payload_gzip),
        "payload_gzip_bytes": len(payload_gzip),
        "coverage_summary": summary,
        "batch_summary": batches,
        "outcomes_opened": False,
        "live_capital_allowed": False,
    }
    if "correction_reason" in snapshot:
        manifest["correction_reason"] = snapshot["correction_reason"]
    report = _report(snapshot, summary, batches, manifest["payload_uncompressed_sha256"])
    return CaptureArtifacts(
        logical_capture_id=logical_capture_id,
        payload_json=payload_json,
        payload_gzip=payload_gzip,
        manifest=manifest,
        report_markdown=report,
    )


def verify_artifact_bytes(payload_gzip: bytes, manifest: dict) -> dict:
    errors: list[str] = []
    if manifest.get("schema_version") != 2:
        errors.append("manifest schema_version must equal 2")
    if manifest.get("hypothesis_id") != "H021":
        errors.append("manifest hypothesis_id must equal H021")
    if manifest.get("sealer_version") != SEALER_VERSION:
        errors.append("manifest sealer_version does not match H021 capture sealer")
    if manifest.get("payload_gzip_bytes") != len(payload_gzip):
        errors.append("gzip byte count does not match manifest")
    if manifest.get("payload_gzip_sha256") != _sha256(payload_gzip):
        errors.append("gzip SHA-256 does not match manifest")
    try:
        payload_json = gzip.decompress(payload_gzip)
    except (OSError, EOFError) as exc:
        raise ValueError("payload is not valid gzip") from exc
    if manifest.get("payload_uncompressed_bytes") != len(payload_json):
        errors.append("uncompressed byte count does not match manifest")
    if manifest.get("payload_uncompressed_sha256") != _sha256(payload_json):
        errors.append("uncompressed SHA-256 does not match manifest")
    try:
        snapshot = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise ValueError("payload is not valid JSON") from exc
    if not isinstance(snapshot, dict):
        errors.append("payload JSON must be an object")
    else:
        if payload_json != canonical_json_bytes(snapshot):
            errors.append("payload JSON is not canonical")
        if payload_gzip != deterministic_gzip(payload_json):
            errors.append("payload gzip is not deterministic sealer output")
        for field in (
            "logical_capture_id",
            "capture_date_ist",
            "captured_at_utc",
            "source_version",
            "universe_path",
            "universe_git_blob_sha",
            "protocol_path",
            "comparison_contract_path",
            "batch_spec_path",
        ):
            if snapshot.get(field) != manifest.get(field):
                errors.append(f"payload/manifest {field} mismatch")
    if errors:
        raise ValueError({"artifact_errors": errors})
    return snapshot


def verify_capture_bundle(
    payload_gzip: bytes,
    manifest: dict,
    universe: dict,
    batch_spec: dict,
) -> dict:
    snapshot = verify_artifact_bytes(payload_gzip, manifest)
    errors = validate_full_capture(snapshot, universe, batch_spec)
    if manifest.get("coverage_summary") != coverage_summary(snapshot):
        errors.append("manifest coverage_summary does not match payload")
    if manifest.get("batch_summary") != batch_summary(snapshot, batch_spec):
        errors.append("manifest batch_summary does not match payload")
    expected_path = (
        "research/prospective/h021/captures/"
        f"{snapshot['logical_capture_id']}.json.gz"
    )
    if manifest.get("payload_path") != expected_path:
        errors.append("manifest payload_path does not match logical_capture_id")
    if errors:
        raise ValueError({"capture_bundle_errors": errors})
    return snapshot
