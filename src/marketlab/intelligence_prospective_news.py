"""Append-only prospective metadata ledger for company-intelligence discovery.

The ledger keeps only metadata needed to prove what MarketLab observed and when.
Raw feeds, articles and page bodies remain in workflow artifacts. Later entity
resolution improvements append new observations and never rewrite an earlier
capture's observed links.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from marketlab.intelligence_core import EvidenceError
from marketlab.intelligence_store import ResearchStore, digest, timestamp

SCHEMA_VERSION = 1


def empty_news_ledger() -> dict:
    base = {
        "schema_version": SCHEMA_VERSION,
        "captures": [],
        "observations": [],
        "live_capital_allowed": False,
    }
    return {**base, "ledger_sha256": digest(base)}


def _without_hash(ledger: dict) -> dict:
    return {key: value for key, value in ledger.items() if key != "ledger_sha256"}


def validate_news_ledger(ledger: dict) -> None:
    if ledger.get("schema_version") != SCHEMA_VERSION:
        raise EvidenceError("Unsupported prospective news-ledger schema")
    if ledger.get("ledger_sha256") != digest(_without_hash(ledger)):
        raise EvidenceError("Prospective news-ledger hash mismatch")
    captures = ledger.get("captures")
    observations = ledger.get("observations")
    if not isinstance(captures, list) or not isinstance(observations, list):
        raise EvidenceError("Prospective news-ledger arrays are required")
    capture_ids = [row.get("capture_id") for row in captures]
    observation_ids = [row.get("observation_id") for row in observations]
    if len(capture_ids) != len(set(capture_ids)) or None in capture_ids:
        raise EvidenceError("Duplicate or missing news capture identity")
    if len(observation_ids) != len(set(observation_ids)) or None in observation_ids:
        raise EvidenceError("Duplicate or missing news observation identity")
    capture_by_id = {row["capture_id"]: row for row in captures}
    for capture in captures:
        timestamp(capture["started_at"])
        timestamp(capture["captured_at"])
        if timestamp(capture["captured_at"]) < timestamp(capture["started_at"]):
            raise EvidenceError("Capture completion precedes start")
        if capture.get("discovery_status") not in {
            "DISCOVERY_CAPTURE_COMPLETE",
            "DISCOVERY_DEGRADED",
        }:
            raise EvidenceError("Capture discovery health is missing or invalid")
    for observation in observations:
        timestamp(observation["first_seen_at"])
        capture = capture_by_id.get(observation["capture_id"])
        if capture is None:
            raise EvidenceError("Observation references missing capture")
        if timestamp(observation["first_seen_at"]) > timestamp(capture["captured_at"]):
            raise EvidenceError("Observation first-seen time follows capture completion")
        if not observation.get("source_id") or not observation.get("item_id"):
            raise EvidenceError("Observation source and item identity are required")


def load_news_ledger(path: Path) -> dict:
    if not path.exists():
        return empty_news_ledger()
    ledger = json.loads(path.read_text(encoding="utf-8"))
    validate_news_ledger(ledger)
    return ledger


def _compact_mentions(value: dict) -> dict:
    return {
        key: sorted(set(value.get(key) or []))
        for key in (
            "panel_symbols",
            "official_nse_symbols",
            "unverified_nse_symbols",
            "bse_codes_for_review",
        )
    }


def capture_from_store(
    store: ResearchStore,
    *,
    identity_session: str,
    identity_raw_sha256: str,
) -> tuple[dict, list[dict]]:
    runs = store.records("news_run")
    if not runs:
        raise EvidenceError("No completed discovery run is available to seal")
    run = max(runs, key=lambda row: timestamp(row["completed_at"]))
    started = timestamp(run["started_at"])
    completed = timestamp(run["completed_at"])
    attempts = [
        row
        for row in store.records("news_attempt")
        if started <= timestamp(row["started_at"]) <= completed
    ]
    source_states: dict[str, list[str]] = {}
    discovery_source_states: dict[str, list[str]] = {}
    discovery_attempts = [row for row in attempts if row["stage"] == "DISCOVERY"]
    document_attempts = [row for row in attempts if row["stage"] == "DOCUMENT"]
    for attempt in attempts:
        source_states.setdefault(attempt["source_id"], []).append(attempt["status"])
        if attempt["stage"] == "DISCOVERY":
            discovery_source_states.setdefault(attempt["source_id"], []).append(attempt["status"])
    discovery_degraded = any(
        row["status"] in {"BLOCKED", "PARSE_FAILED"} for row in discovery_attempts
    )
    capture_core = {
        "started_at": run["started_at"],
        "captured_at": run["completed_at"],
        "run_id": run["run_id"],
        "run_status": run["status"],
        "discovery_status": (
            "DISCOVERY_DEGRADED" if discovery_degraded else "DISCOVERY_CAPTURE_COMPLETE"
        ),
        "identity_session": identity_session,
        "identity_raw_sha256": identity_raw_sha256,
        "source_status_counts": dict(sorted(Counter(row["status"] for row in attempts).items())),
        "discovery_source_status_counts": dict(
            sorted(Counter(row["status"] for row in discovery_attempts).items())
        ),
        "document_status_counts": dict(
            sorted(Counter(row["status"] for row in document_attempts).items())
        ),
        "source_states": {key: sorted(values) for key, values in sorted(source_states.items())},
        "discovery_source_states": {
            key: sorted(values) for key, values in sorted(discovery_source_states.items())
        },
        "full_market_coverage": False,
        "live_capital_allowed": False,
    }
    capture = {**capture_core, "capture_id": digest(capture_core)}
    observations = []
    for item in store.records("news_item"):
        first_seen = timestamp(item["first_seen_at"])
        if not started <= first_seen <= completed:
            continue
        semantic = {
            "source_id": item["source_id"],
            "source_class": item["source_class"],
            "item_id": item["item_id"],
            "resource_key": item["resource_key"],
            "publication": item["publication"],
            "title_sha256": digest(item.get("title", "")),
            "mentions": _compact_mentions(item.get("mentions") or {}),
            "topics": sorted(
                {
                    row.get("topic")
                    for row in item.get("topics") or []
                    if isinstance(row, dict) and row.get("topic")
                }
            ),
        }
        observations.append(
            {
                **semantic,
                "capture_id": capture["capture_id"],
                "first_seen_at": item["first_seen_at"],
                "observation_id": digest(semantic),
            }
        )
    observations.sort(key=lambda row: (row["first_seen_at"], row["observation_id"]))
    return capture, observations


def _semantic_observation(row: dict) -> dict:
    return {key: value for key, value in row.items() if key not in {"capture_id", "first_seen_at"}}


def merge_news_ledger(ledger: dict, capture: dict, observations: list[dict]) -> dict:
    validate_news_ledger(ledger)
    captures = list(ledger["captures"])
    existing_capture = {row["capture_id"]: row for row in captures}
    if capture["capture_id"] in existing_capture:
        if existing_capture[capture["capture_id"]] != capture:
            raise EvidenceError("Immutable prospective capture conflict")
    else:
        captures.append(capture)
    captures.sort(key=lambda row: (row["captured_at"], row["capture_id"]))

    existing = {row["observation_id"]: row for row in ledger["observations"]}
    for observation in observations:
        prior = existing.get(observation["observation_id"])
        if prior is None:
            existing[observation["observation_id"]] = observation
            continue
        if _semantic_observation(prior) != _semantic_observation(observation):
            raise EvidenceError("Immutable prospective observation conflict")
        if timestamp(observation["first_seen_at"]) < timestamp(prior["first_seen_at"]):
            raise EvidenceError("A later seal cannot backdate an existing observation")
        # Same semantic item seen again. Preserve its original observation and capture.
    merged_base = {
        "schema_version": SCHEMA_VERSION,
        "captures": captures,
        "observations": sorted(
            existing.values(), key=lambda row: (row["first_seen_at"], row["observation_id"])
        ),
        "live_capital_allowed": False,
    }
    merged = {**merged_base, "ledger_sha256": digest(merged_base)}
    validate_news_ledger(merged)
    return merged


def write_news_ledger(path: Path, ledger: dict) -> None:
    validate_news_ledger(ledger)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def observations_for_audit(ledger: dict, *, as_of: str) -> list[dict]:
    validate_news_ledger(ledger)
    cutoff = timestamp(as_of)
    return [row for row in ledger["observations"] if timestamp(row["first_seen_at"]) <= cutoff]


def captures_for_audit(ledger: dict, *, as_of: str) -> list[dict]:
    validate_news_ledger(ledger)
    cutoff = timestamp(as_of)
    return [row for row in ledger["captures"] if timestamp(row["captured_at"]) <= cutoff]
