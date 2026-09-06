from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class UniverseError(ValueError):
    """Raised when a research-universe snapshot cannot be built deterministically."""


@dataclass(frozen=True)
class UniverseMember:
    rank: int
    source_rank: int
    symbol: str
    isin: str
    ffmc: float
    company_name: str
    constituent_industry: str
    series: str


@dataclass(frozen=True)
class UniverseSnapshot:
    schema_version: int
    rule_version: str
    cohort_id: str
    captured_at_utc: str
    index_name: str
    index_timestamp: str | None
    selection_size: int
    source_urls: dict[str, str]
    source_hashes: dict[str, str]
    members: list[UniverseMember]
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "rule_version": self.rule_version,
            "cohort_id": self.cohort_id,
            "captured_at_utc": self.captured_at_utc,
            "index_name": self.index_name,
            "index_timestamp": self.index_timestamp,
            "selection_size": self.selection_size,
            "source_urls": self.source_urls,
            "source_hashes": self.source_hashes,
            "members": [asdict(member) for member in self.members],
            "sha256": self.sha256,
        }

    def contains(self, symbol: str) -> bool:
        wanted = symbol.strip().upper()
        return any(member.symbol.upper() == wanted for member in self.members)


def _as_float(value: Any) -> float:
    if isinstance(value, str):
        value = value.replace(",", "").strip()
    return float(value)


def _candidate_rows(index_payload: dict[str, Any], *, index_name: str) -> list[dict[str, Any]]:
    rows = index_payload.get("data")
    if not isinstance(rows, list):
        raise UniverseError("NSE index payload must contain a data list")

    candidates: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").strip()
        if not symbol or symbol.casefold() == index_name.casefold():
            continue
        try:
            ffmc = _as_float(row["ffmc"])
        except (KeyError, TypeError, ValueError) as exc:
            raise UniverseError(f"missing/invalid ffmc for {symbol or '<unknown>'}") from exc
        candidates.append({"symbol": symbol, "ffmc": ffmc})

    if not candidates:
        raise UniverseError("NSE index payload contains no usable constituents")
    candidates.sort(key=lambda row: (-row["ffmc"], row["symbol"]))
    return candidates


def _constituent_rows(raw_csv: bytes) -> dict[str, dict[str, str]]:
    try:
        text = raw_csv.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
    except UnicodeDecodeError as exc:
        raise UniverseError(f"constituent CSV is not UTF-8: {exc}") from exc

    required = {"Company Name", "Industry", "Symbol", "Series", "ISIN Code"}
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise UniverseError(
            f"constituent CSV missing required columns: {sorted(required - set(reader.fieldnames or []))}"
        )

    rows: dict[str, dict[str, str]] = {}
    for row in reader:
        symbol = str(row.get("Symbol") or "").strip().upper()
        if not symbol:
            continue
        if symbol in rows:
            raise UniverseError(f"duplicate symbol in constituent CSV: {symbol}")
        rows[symbol] = {key: str(value or "").strip() for key, value in row.items()}
    if len(rows) != 200:
        raise UniverseError(f"expected 200 Nifty 200 constituent rows, found {len(rows)}")
    return rows


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _bytes_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _snapshot_hash_payload(snapshot: UniverseSnapshot) -> dict[str, Any]:
    payload = snapshot.to_dict()
    payload.pop("sha256", None)
    return payload


def load_universe_snapshot(path: str | Path) -> UniverseSnapshot:
    """Load a frozen U001 v2 snapshot and verify count plus canonical SHA-256."""

    path = Path(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UniverseError(f"could not load universe snapshot {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise UniverseError("universe snapshot root must be an object")
    try:
        member_docs = document.pop("members")
        members = [UniverseMember(**member) for member in member_docs]
        snapshot = UniverseSnapshot(**document, members=members)
    except (KeyError, TypeError) as exc:
        raise UniverseError(f"invalid universe snapshot schema: {exc}") from exc
    if snapshot.selection_size != len(snapshot.members):
        raise UniverseError(
            f"universe selection_size={snapshot.selection_size} but has {len(snapshot.members)} members"
        )
    expected = _canonical_hash(_snapshot_hash_payload(snapshot))
    if snapshot.sha256 != expected:
        raise UniverseError(
            f"universe snapshot hash mismatch: expected {expected}, found {snapshot.sha256}"
        )
    symbols = [member.symbol.upper() for member in snapshot.members]
    if len(symbols) != len(set(symbols)):
        raise UniverseError("universe snapshot contains duplicate symbols")
    if any(member.constituent_industry.casefold() == "financial services" for member in snapshot.members):
        raise UniverseError("universe snapshot contains Financial Services member")
    return snapshot


def build_universe_snapshot(
    index_payload: dict[str, Any],
    constituent_csv: bytes,
    *,
    cohort_id: str,
    selection_size: int = 100,
    index_name: str = "NIFTY 200",
    captured_at: datetime | None = None,
) -> UniverseSnapshot:
    """Build U001 v2 from two official NSE sources.

    The live Nifty 200 payload supplies free-float market capitalization. The
    official Nifty 200 constituent CSV supplies membership, ISIN and its broad
    `Industry` classification. In NSE's classification taxonomy, the financial
    macro economic sector has sector label `Financial Services`; the official
    constituent CSV uses that same label for all financial constituents.
    """

    if selection_size <= 0:
        raise UniverseError("selection_size must be positive")

    captured_at = captured_at or datetime.now(UTC)
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=UTC)
    captured_at_utc = captured_at.astimezone(UTC).isoformat().replace("+00:00", "Z")

    classification = _constituent_rows(constituent_csv)
    candidates = _candidate_rows(index_payload, index_name=index_name)
    candidate_symbols = {candidate["symbol"].upper() for candidate in candidates}
    missing_from_csv = sorted(candidate_symbols - classification.keys())
    missing_from_index = sorted(classification.keys() - candidate_symbols)
    if missing_from_csv or missing_from_index:
        raise UniverseError(
            "Nifty 200 source mismatch: "
            f"index_only={missing_from_csv[:10]}, csv_only={missing_from_index[:10]}"
        )

    members: list[UniverseMember] = []
    for source_rank, candidate in enumerate(candidates, start=1):
        symbol = candidate["symbol"].upper()
        meta = classification[symbol]
        industry = meta["Industry"]
        if not industry:
            raise UniverseError(f"missing official Industry classification for {symbol}")
        if industry.casefold() == "financial services":
            continue
        isin = meta["ISIN Code"]
        if not isin:
            raise UniverseError(f"missing ISIN for {symbol}")
        members.append(
            UniverseMember(
                rank=len(members) + 1,
                source_rank=source_rank,
                symbol=symbol,
                isin=isin,
                ffmc=candidate["ffmc"],
                company_name=meta["Company Name"],
                constituent_industry=industry,
                series=meta["Series"],
            )
        )
        if len(members) == selection_size:
            break

    if len(members) != selection_size:
        raise UniverseError(
            f"could select only {len(members)} non-financial companies; expected {selection_size}"
        )

    source_urls = {
        "index_ffmc": "https://www.nseindia.com/api/equity-stock-indices?index=NIFTY%20200",
        "constituents": "https://archives.nseindia.com/content/indices/ind_nifty200list.csv",
    }
    source_hashes = {
        "index_canonical_json_sha256": _canonical_hash(index_payload),
        "constituents_raw_sha256": _bytes_hash(constituent_csv),
    }
    hash_payload = {
        "schema_version": 2,
        "rule_version": "U001-nifty200-top100-nonfinancial-ffmc-v2",
        "cohort_id": cohort_id,
        "captured_at_utc": captured_at_utc,
        "index_name": index_name,
        "index_timestamp": index_payload.get("timestamp"),
        "selection_size": selection_size,
        "source_urls": source_urls,
        "source_hashes": source_hashes,
        "members": [asdict(member) for member in members],
    }
    return UniverseSnapshot(
        schema_version=2,
        rule_version="U001-nifty200-top100-nonfinancial-ffmc-v2",
        cohort_id=cohort_id,
        captured_at_utc=captured_at_utc,
        index_name=index_name,
        index_timestamp=index_payload.get("timestamp"),
        selection_size=selection_size,
        source_urls=source_urls,
        source_hashes=source_hashes,
        members=members,
        sha256=_canonical_hash(hash_payload),
    )
