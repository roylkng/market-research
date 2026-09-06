from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from marketlab.execution import PriceBar
from marketlab.events import sha256_bytes

UDIFF_URL_TEMPLATE = (
    "https://nsearchives.nseindia.com/content/cm/"
    "BhavCopy_NSE_CM_0_0_0_{yyyymmdd}_F_0000.csv.zip"
)
INDEX_SNAPSHOT_URL_TEMPLATE = (
    "https://archives.nseindia.com/content/indices/ind_close_all_{ddmmyyyy}.csv"
)
UNADJUSTED_PRICE_BASIS_VERSION = "NSE-RAW-UNADJUSTED-v1"
INDEX_NAMES = {
    "nifty_50": "Nifty 50",
    "nifty_200_momentum_30": "Nifty200 Momentum 30",
}


class MarketDataError(ValueError):
    """Raised when exact market-data files cannot be interpreted without guessing."""


@dataclass(frozen=True)
class MarketArtifact:
    schema_version: int
    artifact_id: str
    source_url: str
    captured_at_utc: str
    raw_sha256: str
    raw_path: str
    byte_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EquityDailyPrice:
    symbol: str
    isin: str
    series: str
    session_date: str
    open_price: float
    close_price: float


@dataclass(frozen=True)
class IndexDailyPrice:
    benchmark_id: str
    index_name: str
    session_date: str
    open_price: float
    close_price: float


@dataclass(frozen=True)
class PriceBasisAudit:
    status: str
    version: str | None
    relevant_actions: tuple[dict[str, str], ...]
    unresolved_actions: tuple[str, ...]
    raw_sha256: str


class MarketArtifactStore:
    """Content-addressed exact market-data evidence with immutable metadata."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def retain(
        self,
        raw: bytes,
        *,
        source_url: str,
        captured_at: datetime,
        suffix: str,
    ) -> MarketArtifact:
        if not raw:
            raise MarketDataError("market artifact bytes are empty")
        if captured_at.tzinfo is None:
            raise MarketDataError("market artifact captured_at must include timezone")
        digest = sha256_bytes(raw)
        raw_path = self.root / "market-data" / "raw" / "sha256" / f"{digest}{suffix}"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        if raw_path.exists():
            if raw_path.read_bytes() != raw:
                raise MarketDataError("content-addressed market-data hash collision")
        else:
            raw_path.write_bytes(raw)
        captured = captured_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        identity = {
            "source_url": source_url,
            "captured_at_utc": captured,
            "raw_sha256": digest,
            "byte_count": len(raw),
        }
        artifact_id = _canonical_hash(identity)
        metadata = MarketArtifact(
            schema_version=1,
            artifact_id=artifact_id,
            source_url=source_url,
            captured_at_utc=captured,
            raw_sha256=digest,
            raw_path=str(raw_path),
            byte_count=len(raw),
        )
        metadata_path = self.root / "market-data" / "artifacts" / f"{artifact_id}.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        content = (json.dumps(metadata.to_dict(), indent=2, sort_keys=True) + "\n").encode()
        try:
            fd = os.open(metadata_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            if metadata_path.read_bytes() != content:
                raise MarketDataError("market artifact metadata collision")
        else:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        return metadata


def _canonical_hash(payload: Any) -> str:
    try:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    except (TypeError, ValueError) as exc:
        raise MarketDataError("market-data payload must contain finite JSON values") from exc
    return hashlib.sha256(encoded).hexdigest()


def _positive_float(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise MarketDataError(f"{field} must be a finite positive number")
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise MarketDataError(f"invalid {field}: {value}") from exc
    if not math.isfinite(result) or result <= 0:
        raise MarketDataError(f"{field} must be a finite positive number")
    return result


def udiff_url(session_date: date) -> str:
    return UDIFF_URL_TEMPLATE.format(yyyymmdd=session_date.strftime("%Y%m%d"))


def index_snapshot_url(session_date: date) -> str:
    return INDEX_SNAPSHOT_URL_TEMPLATE.format(ddmmyyyy=session_date.strftime("%d%m%Y"))


def parse_udiff_equity(
    raw_zip: bytes,
    *,
    symbol: str,
    session_date: date,
    series: str = "EQ",
    expected_isin: str | None = None,
) -> EquityDailyPrice:
    try:
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
            names = archive.namelist()
            if len(names) != 1 or not names[0].lower().endswith(".csv"):
                raise MarketDataError("UDiFF archive must contain exactly one CSV")
            raw_csv = archive.read(names[0])
    except (zipfile.BadZipFile, KeyError) as exc:
        raise MarketDataError(f"invalid UDiFF bhavcopy ZIP: {exc}") from exc

    try:
        text = raw_csv.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MarketDataError("UDiFF CSV is not UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    required = {
        "TradDt",
        "Sgmt",
        "Src",
        "FinInstrmTp",
        "ISIN",
        "TckrSymb",
        "SctySrs",
        "OpnPric",
        "ClsPric",
    }
    if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
        raise MarketDataError("UDiFF CSV header does not match frozen parser contract")

    wanted_symbol = symbol.strip().upper()
    wanted_series = series.strip().upper()
    day = session_date.isoformat()
    matches: list[dict[str, str]] = []
    for row in reader:
        if (
            str(row.get("TradDt") or "").strip() == day
            and str(row.get("Sgmt") or "").strip().upper() == "CM"
            and str(row.get("Src") or "").strip().upper() == "NSE"
            and str(row.get("FinInstrmTp") or "").strip().upper() == "STK"
            and str(row.get("TckrSymb") or "").strip().upper() == wanted_symbol
            and str(row.get("SctySrs") or "").strip().upper() == wanted_series
        ):
            matches.append(row)
    if len(matches) != 1:
        raise MarketDataError(
            f"expected exactly one UDiFF row for {wanted_symbol}/{wanted_series} on {day}; "
            f"found {len(matches)}"
        )
    row = matches[0]
    isin = str(row.get("ISIN") or "").strip()
    if not isin:
        raise MarketDataError("UDiFF row is missing ISIN")
    if expected_isin and isin != expected_isin:
        raise MarketDataError(
            f"UDiFF ISIN mismatch for {wanted_symbol}: expected={expected_isin}, observed={isin}"
        )
    return EquityDailyPrice(
        symbol=wanted_symbol,
        isin=isin,
        series=wanted_series,
        session_date=day,
        open_price=_positive_float(row.get("OpnPric"), "UDiFF open price"),
        close_price=_positive_float(row.get("ClsPric"), "UDiFF close price"),
    )


def parse_index_snapshot(
    raw_csv: bytes,
    *,
    benchmark_id: str,
    session_date: date,
) -> IndexDailyPrice:
    try:
        text = raw_csv.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MarketDataError("index snapshot CSV is not UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    required = {"Index Name", "Index Date", "Open Index Value", "Closing Index Value"}
    if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
        raise MarketDataError("index snapshot header does not match frozen parser contract")
    try:
        expected_name = INDEX_NAMES[benchmark_id]
    except KeyError as exc:
        raise MarketDataError(f"unsupported benchmark id: {benchmark_id}") from exc

    matches = []
    for row in reader:
        name = " ".join(str(row.get("Index Name") or "").split())
        raw_date = str(row.get("Index Date") or "").strip()
        if name.casefold() != expected_name.casefold():
            continue
        parsed_date: date | None = None
        for fmt in ("%d-%m-%Y", "%d-%b-%Y", "%Y-%m-%d"):
            try:
                parsed_date = datetime.strptime(raw_date, fmt).date()
                break
            except ValueError:
                continue
        if parsed_date == session_date:
            matches.append(row)
    if len(matches) != 1:
        raise MarketDataError(
            f"expected exactly one index row for {benchmark_id} on {session_date}; "
            f"found {len(matches)}"
        )
    row = matches[0]
    return IndexDailyPrice(
        benchmark_id=benchmark_id,
        index_name=expected_name,
        session_date=session_date.isoformat(),
        open_price=_positive_float(row.get("Open Index Value"), "index open"),
        close_price=_positive_float(row.get("Closing Index Value"), "index close"),
    )


def equity_price_bar(
    price: EquityDailyPrice,
    *,
    source_url: str,
    source_timestamp_utc: str,
) -> PriceBar:
    return PriceBar(
        instrument_id=price.symbol,
        session_date=price.session_date,
        open_price=price.open_price,
        close_price=price.close_price,
        source=source_url,
        source_timestamp_utc=source_timestamp_utc,
        tradable_at_open=True,
        tradable_at_close=True,
        corporate_action_version=UNADJUSTED_PRICE_BASIS_VERSION,
    )


def index_price_bar(
    price: IndexDailyPrice,
    *,
    source_url: str,
    source_timestamp_utc: str,
) -> PriceBar:
    return PriceBar(
        instrument_id=price.benchmark_id,
        session_date=price.session_date,
        open_price=price.open_price,
        close_price=price.close_price,
        source=source_url,
        source_timestamp_utc=source_timestamp_utc,
        tradable_at_open=True,
        tradable_at_close=True,
        corporate_action_version=None,
    )


_SHARE_ACTION_TOKENS = (
    "bonus",
    "split",
    "sub-division",
    "subdivision",
    "consolidation",
    "rights",
)


def audit_price_basis_actions(
    payload: Any,
    *,
    raw_payload: bytes,
    symbol: str,
    start_date: date,
    end_date: date,
) -> PriceBasisAudit:
    if start_date > end_date:
        raise MarketDataError("price-basis action start date exceeds end date")
    rows: list[dict[str, Any]]
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        candidate = payload.get("data") or payload.get("records") or []
        rows = (
            [row for row in candidate if isinstance(row, dict)]
            if isinstance(candidate, list)
            else []
        )
    else:
        rows = []

    relevant: list[dict[str, str]] = []
    unresolved: list[str] = []
    for row in rows:
        if str(row.get("symbol") or "").strip().upper() != symbol.upper():
            continue
        subject = str(row.get("subject") or row.get("purpose") or "").strip()
        if not subject or not any(token in subject.casefold() for token in _SHARE_ACTION_TOKENS):
            continue
        raw_date = row.get("exDate") or row.get("ex_date")
        try:
            action_date = _parse_action_date(raw_date)
        except MarketDataError:
            unresolved.append(subject)
            continue
        if not (start_date <= action_date <= end_date):
            continue
        relevant.append({"subject": subject, "ex_date": action_date.isoformat()})
        if "rights" in subject.casefold():
            unresolved.append(subject)

    relevant.sort(key=lambda item: (item["ex_date"], item["subject"]))
    unresolved = sorted(set(unresolved))
    raw_hash = sha256_bytes(raw_payload)
    if unresolved:
        return PriceBasisAudit(
            status="UNRESOLVED",
            version=None,
            relevant_actions=tuple(relevant),
            unresolved_actions=tuple(unresolved),
            raw_sha256=raw_hash,
        )
    version = "PB-" + _canonical_hash(
        {
            "schema": 1,
            "symbol": symbol.upper(),
            "basis_contract": UNADJUSTED_PRICE_BASIS_VERSION,
            "start_date": start_date.isoformat(),
            "relevant_actions": relevant,
        }
    )[:24]
    return PriceBasisAudit(
        status="READY",
        version=version,
        relevant_actions=tuple(relevant),
        unresolved_actions=(),
        raw_sha256=raw_hash,
    )


def _parse_action_date(value: Any) -> date:
    if not isinstance(value, str):
        raise MarketDataError("corporate-action exDate is required")
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise MarketDataError(f"unsupported corporate-action exDate: {value}")
