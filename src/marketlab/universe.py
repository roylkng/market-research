from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable


class UniverseError(ValueError):
    """Raised when a research-universe snapshot cannot be built deterministically."""


@dataclass(frozen=True)
class UniverseMember:
    rank: int
    source_rank: int
    symbol: str
    isin: str | None
    ffmc: float
    listing_date: str | None
    macro: str
    sector: str | None
    industry: str | None
    basic_industry: str | None


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
            "members": [asdict(member) for member in self.members],
            "sha256": self.sha256,
        }


def _normalise_macro(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _extract_industry_info(quote: dict[str, Any]) -> dict[str, Any]:
    value = quote.get("industryInfo")
    return value if isinstance(value, dict) else {}


def _extract_info(quote: dict[str, Any]) -> dict[str, Any]:
    value = quote.get("info")
    return value if isinstance(value, dict) else {}


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
            ffmc = float(row["ffmc"])
        except (KeyError, TypeError, ValueError) as exc:
            raise UniverseError(f"missing/invalid ffmc for {symbol or '<unknown>'}") from exc
        candidates.append({"symbol": symbol, "ffmc": ffmc})

    if not candidates:
        raise UniverseError("NSE index payload contains no usable constituents")
    candidates.sort(key=lambda row: (-row["ffmc"], row["symbol"]))
    return candidates


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_universe_snapshot(
    index_payload: dict[str, Any],
    quote_loader: Callable[[str], dict[str, Any]],
    *,
    cohort_id: str,
    selection_size: int = 100,
    index_name: str = "NIFTY 200",
    captured_at: datetime | None = None,
) -> UniverseSnapshot:
    """Build v1: top-N non-financial Nifty 200 constituents by NSE FFMC.

    Metadata failure is fatal while scanning the ranked source population. We do
    not skip an unclassified company because doing so can alter membership.
    """

    if selection_size <= 0:
        raise UniverseError("selection_size must be positive")

    captured_at = captured_at or datetime.now(timezone.utc)
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    captured_at_utc = captured_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    members: list[UniverseMember] = []
    candidates = _candidate_rows(index_payload, index_name=index_name)
    for source_rank, candidate in enumerate(candidates, start=1):
        quote = quote_loader(candidate["symbol"])
        if not isinstance(quote, dict):
            raise UniverseError(f"invalid quote metadata for {candidate['symbol']}")
        industry = _extract_industry_info(quote)
        info = _extract_info(quote)
        macro = str(industry.get("macro") or "").strip()
        if not macro:
            raise UniverseError(f"missing NSE macro-sector metadata for {candidate['symbol']}")
        if _normalise_macro(macro) == "financial services":
            continue

        members.append(
            UniverseMember(
                rank=len(members) + 1,
                source_rank=source_rank,
                symbol=candidate["symbol"],
                isin=(str(info.get("isin")).strip() if info.get("isin") else None),
                ffmc=candidate["ffmc"],
                listing_date=(
                    str(info.get("listingDate")).strip() if info.get("listingDate") else None
                ),
                macro=macro,
                sector=(str(industry.get("sector")).strip() if industry.get("sector") else None),
                industry=(
                    str(industry.get("industry")).strip() if industry.get("industry") else None
                ),
                basic_industry=(
                    str(industry.get("basicIndustry")).strip()
                    if industry.get("basicIndustry")
                    else None
                ),
            )
        )
        if len(members) == selection_size:
            break

    if len(members) != selection_size:
        raise UniverseError(
            f"could select only {len(members)} non-financial companies; expected {selection_size}"
        )

    source_urls = {
        "index": "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20200",
        "quote_template": "https://www.nseindia.com/api/quote-equity?symbol=<SYMBOL>",
    }
    unsigned = {
        "schema_version": 1,
        "rule_version": "U001-nifty200-top100-nonfinancial-ffmc-v1",
        "cohort_id": cohort_id,
        "captured_at_utc": captured_at_utc,
        "index_name": index_name,
        "index_timestamp": index_payload.get("timestamp"),
        "selection_size": selection_size,
        "source_urls": source_urls,
        "members": [asdict(member) for member in members],
    }
    return UniverseSnapshot(**unsigned, sha256=_canonical_hash(unsigned))
