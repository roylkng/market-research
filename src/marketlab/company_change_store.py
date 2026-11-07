"""CC001 append-only local evidence store. SQLite is for one research workspace."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.company_change import ChangeError, canonical_hash, timestamp


def now_utc() -> str:
    return datetime.now(UTC).isoformat()


def loads_unique(raw: str | bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ChangeError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise ChangeError(f"nonfinite JSON constant: {value}")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def writable_workspace(path: Path) -> Path:
    root = path.resolve()
    protected = {"hypotheses", "registry", "experiments", "prospective"}
    if any(p.casefold() in protected or re.fullmatch(r"(?:h|hg|ae)\d+", p, re.IGNORECASE)
           for p in root.parts):
        raise ChangeError("workspace cannot be inside a frozen research namespace")
    root.mkdir(parents=True, exist_ok=True)
    return root


class EvidenceStore:
    """Original bytes and immutable capture/extraction/review records.

    The database is not a multi-tenant approval system. Review identities are
    local operator attestations. No caller-provided observation time is accepted.
    """

    def __init__(self, root: Path, *, clock=now_utc):
        self.root = writable_workspace(root)
        self.clock = clock
        self.db = sqlite3.connect(self.root / "evidence.sqlite3", timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT OR IGNORE INTO meta VALUES ('schema_version', '1');
            CREATE TABLE IF NOT EXISTS captures (
                id TEXT PRIMARY KEY, source_key TEXT NOT NULL, raw_sha256 TEXT NOT NULL,
                captured_at TEXT NOT NULL, metadata TEXT NOT NULL,
                UNIQUE(source_key, raw_sha256));
            CREATE TABLE IF NOT EXISTS extractions (
                id TEXT PRIMARY KEY, capture_id TEXT NOT NULL REFERENCES captures(id),
                recipe_sha256 TEXT NOT NULL, known_at TEXT NOT NULL,
                event_key TEXT NOT NULL, result TEXT NOT NULL,
                UNIQUE(capture_id, recipe_sha256));
            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY, extraction_id TEXT NOT NULL REFERENCES extractions(id),
                recorded_at TEXT NOT NULL, reviewer TEXT NOT NULL,
                verdict TEXT NOT NULL, rationale TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY, recorded_at TEXT NOT NULL,
                source_id TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY, recorded_at TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS extraction_events ON extractions(event_key, known_at);
        """)
        version = self.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        if version != "1":
            self.db.close()
            raise ChangeError("unsupported evidence-store schema")
        self.db.commit()

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def put_blob(self, raw: bytes) -> str:
        digest = hashlib.sha256(raw).hexdigest()
        path = self.root / "blobs" / digest[:2] / digest
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as stream:
                stream.write(raw)
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ChangeError("original-byte store integrity failure")
        return digest

    def read_blob(self, digest: str) -> bytes:
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ChangeError("invalid original-byte digest")
        raw = (self.root / "blobs" / digest[:2] / digest).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ChangeError("original-byte store integrity failure")
        return raw

    def capture(self, raw: bytes, metadata: dict) -> dict:
        digest = self.put_blob(raw)
        # Include declared source semantics so a changed identity is not a cache hit.
        source_key = canonical_hash(metadata)
        identity = canonical_hash({"source": source_key, "raw": digest})
        captured = timestamp(self.clock()).isoformat()
        timestamp(captured)
        with self.transaction():
            self.db.execute("INSERT OR IGNORE INTO captures VALUES (?,?,?,?,?)", (
                identity, source_key, digest, captured,
                json.dumps(metadata, sort_keys=True, allow_nan=False)))
        return self.get_capture(identity)

    def get_capture(self, identity: str) -> dict:
        row = self.db.execute("SELECT * FROM captures WHERE id=?", (identity,)).fetchone()
        if row is None:
            raise ChangeError("unknown capture")
        result = dict(row)
        result["metadata"] = loads_unique(result["metadata"])
        self.read_blob(result["raw_sha256"])
        return result

    def cached(self, capture_id: str, recipe: str) -> dict | None:
        row = self.db.execute(
            "SELECT result FROM extractions WHERE capture_id=? AND recipe_sha256=?",
            (capture_id, recipe)).fetchone()
        return loads_unique(row[0]) if row else None

    def record_extraction(self, capture: dict, recipe: str, result: dict) -> dict:
        known = timestamp(self.clock()).isoformat()
        if timestamp(known) < timestamp(capture["captured_at"]):
            raise ChangeError("extraction clock precedes capture")
        identity = canonical_hash({"capture": capture["id"], "recipe": recipe})
        payload = {**result, "extraction_id": identity, "capture_id": capture["id"],
                   "raw_sha256": capture["raw_sha256"], "known_at": known,
                   "recipe_sha256": recipe, "live_capital_allowed": False}
        payload["result_sha256"] = canonical_hash(payload)
        event_key = canonical_hash(result["identity"])
        with self.transaction():
            existing = self.cached(capture["id"], recipe)
            if existing is not None:
                return existing
            self.db.execute("INSERT INTO extractions VALUES (?,?,?,?,?,?)", (
                identity, capture["id"], recipe, known, event_key,
                json.dumps(payload, sort_keys=True, allow_nan=False)))
        return payload

    def attempt(self, source_id: str, status: str, detail: str):
        with self.transaction():
            self.db.execute("INSERT INTO attempts(recorded_at,source_id,status,detail) VALUES (?,?,?,?)",
                            (self.clock(), source_id, status, detail[:1000]))

    def review(self, extraction_id: str, reviewer: str, verdict: str, rationale: str) -> str:
        if verdict not in {"ACCEPT", "REJECT"} or not reviewer.strip() or not rationale.strip():
            raise ChangeError("review requires ACCEPT/REJECT, reviewer and rationale")
        row = self.db.execute("SELECT known_at FROM extractions WHERE id=?", (extraction_id,)).fetchone()
        if row is None:
            raise ChangeError("unknown extraction")
        recorded = timestamp(self.clock()).isoformat()
        if timestamp(recorded) < timestamp(row[0]):
            raise ChangeError("review predates extraction")
        identity = canonical_hash([extraction_id, recorded, reviewer, verdict, rationale])
        with self.transaction():
            self.db.execute("INSERT OR IGNORE INTO reviews VALUES (?,?,?,?,?,?)",
                            (identity, extraction_id, recorded, reviewer, verdict, rationale))
        return identity

    def snapshot(self, as_of: str | None = None) -> dict:
        cutoff = timestamp(as_of or self.clock())
        history, active = [], {}
        for row in self.db.execute("SELECT * FROM extractions ORDER BY known_at, id"):
            result = loads_unique(row["result"])
            if timestamp(result["known_at"]) > cutoff:
                continue
            digest = result.pop("result_sha256")
            if canonical_hash(result) != digest:
                raise ChangeError("extraction record integrity failure")
            result["result_sha256"] = digest
            capture = self.get_capture(result["capture_id"])
            metadata = capture["metadata"]
            published = metadata.get("published_at") or metadata.get("spec", {}).get("published_at")
            result["issuer_published_at"] = timestamp(published).isoformat() if published else None
            reviews = [dict(r) for r in self.db.execute(
                "SELECT * FROM reviews WHERE extraction_id=? ORDER BY recorded_at,id", (row["id"],))
                if timestamp(r["recorded_at"]) <= cutoff]
            result["review"] = reviews[-1] if reviews else None
            previous = active.get(row["event_key"])
            stale = bool(previous and result["issuer_published_at"] and previous.get("issuer_published_at")
                         and timestamp(result["issuer_published_at"]) < timestamp(previous["issuer_published_at"]))
            result["supersedes_extraction_id"] = previous["extraction_id"] if previous and not stale else None
            result["changed"] = bool(previous and not stale and previous["facts_sha256"] != result["facts_sha256"])
            result["review_status"] = reviews[-1]["verdict"] if reviews else "UNREVIEWED"
            result["older_source_observed_late"] = stale
            history.append(result)
            # Retried old documents must not displace a later issuer revision. This
            # preserves observation clocks without mistaking receipt order for event order.
            # A rejected newest revision remains visible instead of reviving old approval.
            if not stale:
                active[row["event_key"]] = result
        result = {"as_of": cutoff.isoformat(), "active": list(active.values()), "history": history,
                  "live_capital_allowed": False, "trained_predictor": False}
        result["snapshot_sha256"] = canonical_hash(result)
        return result

    def decision(self, payload: dict) -> str:
        if payload.get("live_capital_allowed") is not False:
            raise ChangeError("only research decisions can be recorded")
        digest = canonical_hash(payload)
        with self.transaction():
            self.db.execute("INSERT OR IGNORE INTO decisions VALUES (?,?,?)",
                            (digest, self.clock(), json.dumps(payload, sort_keys=True, allow_nan=False)))
        return digest
