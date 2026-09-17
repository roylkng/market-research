"""Append-only local research store. No legacy ledger imports or trading writes."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.intelligence_core import EvidenceError, aware

FACETS = (
    "financials", "prospects", "execution", "expectations", "valuation",
    "market", "news", "exposures", "social",
)


def now_text() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def timestamp(value: str) -> datetime:
    try:
        return aware(datetime.fromisoformat(value)).astimezone(UTC)
    except (TypeError, ValueError) as exc:
        raise EvidenceError("Invalid timezone-aware timestamp") from exc


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class ResearchStore:
    """Single-node SQLite/WAL store with immutable records and hashed objects.

    Hashes detect changed bytes, not truth or a malicious database administrator.
    recorded_at and decision cutoff are separate from public source dates.
    """

    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.objects = self.directory / "objects"
        self.objects.mkdir(exist_ok=True)
        self.connection = sqlite3.connect(self.directory / "research.sqlite", timeout=30)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS records (
              kind TEXT NOT NULL, identifier TEXT NOT NULL, body TEXT NOT NULL,
              body_sha256 TEXT NOT NULL, recorded_at TEXT NOT NULL,
              PRIMARY KEY(kind, identifier));
            CREATE TRIGGER IF NOT EXISTS records_no_update BEFORE UPDATE ON records
              BEGIN SELECT RAISE(ABORT, 'append-only records'); END;
            CREATE TRIGGER IF NOT EXISTS records_no_delete BEFORE DELETE ON records
              BEGIN SELECT RAISE(ABORT, 'append-only records'); END;
        """)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        if self.connection.in_transaction:
            self.connection.rollback()
        self.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self.connection.close()

    def append(self, kind: str, identifier: str, body: dict) -> bool:
        if not kind or not identifier:
            raise EvidenceError("Record identity is required")
        text, hashed = canonical(body), digest(body)
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            prior = self.connection.execute(
                "SELECT body,body_sha256 FROM records WHERE kind=? AND identifier=?",
                (kind, identifier),
            ).fetchone()
            if prior:
                if prior != (text, hashed):
                    raise EvidenceError(f"Immutable record conflict: {kind}/{identifier}")
                return False
            self.connection.execute("INSERT INTO records VALUES (?,?,?,?,?)",
                                    (kind, identifier, text, hashed, now_text()))
        return True

    def records(self, kind: str) -> list[dict]:
        rows = self.connection.execute(
            "SELECT body,body_sha256 FROM records WHERE kind=? ORDER BY identifier", (kind,)
        ).fetchall()
        result = []
        for text, expected in rows:
            item = json.loads(text)
            if digest(item) != expected:
                raise EvidenceError("Stored record digest mismatch")
            result.append(item)
        return result

    def save_object(self, raw: bytes) -> str:
        key = sha256(raw)
        target = self.objects / key
        if target.exists():
            if sha256(target.read_bytes()) != key:
                raise EvidenceError("Stored object digest mismatch")
            return key
        fd, temporary = tempfile.mkstemp(dir=self.objects)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                if sha256(target.read_bytes()) != key:
                    raise EvidenceError("Concurrent object digest mismatch")
        finally:
            os.unlink(temporary)
        return key

    def read_object(self, key: str) -> bytes:
        if not re.fullmatch(r"[a-f0-9]{64}", key):
            raise EvidenceError("Invalid object identity")
        raw = (self.objects / key).read_bytes()
        if sha256(raw) != key:
            raise EvidenceError("Stored object digest mismatch")
        return raw

    def bootstrap_panel(self, raw: bytes, *, expected_blob: str,
                        source_path: str, panel_id: str) -> dict:
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if blob != expected_blob:
            raise EvidenceError("Panel source Git blob mismatch")
        seed = json.loads(raw)
        members = seed["members"]
        if len(members) != 100:
            raise EvidenceError("Bootstrap requires the exact 100-name source panel")
        cleaned = []
        for row in members:
            if not re.fullmatch(r"[A-Z0-9&_-]+", row["symbol"]):
                raise EvidenceError("Invalid company symbol")
            if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", row["isin"]):
                raise EvidenceError("Invalid company ISIN")
            if not row["company_name"] or row["series"] != "EQ":
                raise EvidenceError("Invalid company identity")
            cleaned.append({k: row[k] for k in (
                "symbol", "company_name", "isin", "constituent_industry")})
        if len({r["symbol"] for r in cleaned}) != 100 or len({r["isin"] for r in cleaned}) != 100:
            raise EvidenceError("Duplicate panel identity")
        panel = {"panel_id": panel_id, "source_path": source_path,
                 "source_git_blob": blob, "source_sha256": sha256(raw),
                 "membership_kind": "RESEARCH_BOOTSTRAP_NOT_RECOMMENDATIONS",
                 "limitation": "Inherited non-financial large-company bias. Not broad radar coverage.",
                 "members": sorted(cleaned, key=lambda r: r["symbol"]),
                 "legacy_experiments_modified": False, "live_capital_allowed": False}
        self.append("panel", panel_id, panel)
        return panel
