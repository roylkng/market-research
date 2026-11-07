"""Official session-close evidence. No guessed prices, intraday times or calendar."""
from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from datetime import date, timedelta
from pathlib import PurePosixPath
from zoneinfo import ZoneInfo

from marketlab.company_change import ChangeError, finite, timestamp
from marketlab.company_change_pipeline import fetch_original

IST = ZoneInfo("Asia/Kolkata")
HOSTS = {"nsearchives.nseindia.com"}
MAX_EXPANDED = 32 * 1024 * 1024


def quote_session(quote: dict) -> date:
    if quote.get("session_date") is not None:
        session = date.fromisoformat(quote["session_date"])
    elif quote.get("quoted_at") is not None:
        session = timestamp(quote["quoted_at"]).astimezone(IST).date()
    else:
        raise ChangeError("price has no session date or source timestamp")
    if session > timestamp(quote["observed_at"]).astimezone(IST).date():
        raise ChangeError("price session is after observation")
    return session


def parse_bhavcopy(raw: bytes, identity: dict, session: date, observed_at: str) -> dict:
    if not raw or len(raw) > 16 * 1024 * 1024:
        raise ChangeError("invalid price archive size")
    observed = timestamp(observed_at)
    if not 0 <= (observed.astimezone(IST).date() - session).days <= 7:
        raise ChangeError("price session is future or stale")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            files = archive.infolist()
            if len(files) != 1 or files[0].is_dir() or files[0].file_size > MAX_EXPANDED:
                raise ChangeError("unexpected price archive members or expanded size")
            member = files[0]
            path = PurePosixPath(member.filename)
            expected = f"BhavCopy_NSE_CM_0_0_0_{session:%Y%m%d}_F_0000.csv"
            if path.is_absolute() or ".." in path.parts or path.name != expected:
                raise ChangeError("price archive filename/session mismatch")
            csv_raw = archive.read(member)
    except zipfile.BadZipFile as exc:
        raise ChangeError("price source is not a valid ZIP") from exc
    reader = csv.DictReader(io.StringIO(csv_raw.decode("utf-8-sig", errors="strict")))
    required = {"TradDt", "ISIN", "TckrSymb", "SctySrs", "Sgmt", "Src", "FinInstrmTp", "ClsPric", "TtlTradgVol"}
    if not required <= set(reader.fieldnames or []):
        raise ChangeError("price archive lacks required UDiFF columns")
    matches = []
    for line, row in enumerate(reader, 2):
        if row.get("TradDt") != session.isoformat():
            raise ChangeError("price-file content date differs from requested session")
        if row.get("TckrSymb") == identity["symbol"] and row.get("SctySrs") == "EQ":
            if row.get("ISIN") != identity["isin"] or row.get("Sgmt") != "CM" or row.get("Src") != "NSE" or row.get("FinInstrmTp") != "STK":
                raise ChangeError("price identity/market/instrument mismatch")
            literal = row["ClsPric"]
            if not re.fullmatch(r"\d+(?:\.\d+)?", literal):
                raise ChangeError("invalid closing-price literal")
            price = finite(float(literal), "official close", minimum=0.000001)
            if not re.fullmatch(r"\d+(?:\.0+)?", row["TtlTradgVol"]) or float(row["TtlTradgVol"]) <= 0:
                raise ChangeError("no positive trading volume for price reference")
            matches.append((price, line, row))
    if len(matches) != 1:
        raise ChangeError("expected one exact EQ security in the latest retrieved file")
    price, line, row = matches[0]
    return {"price": price, "currency": "INR", "quoted_at": None,
            "session_date": session.isoformat(), "timestamp_precision": "SESSION_DATE_ONLY_NO_INVENTED_INTRADAY_TIME",
            "observed_at": observed.isoformat(), "identity": identity,
            "price_type": "OFFICIAL_SESSION_CLOSE_NOT_EXECUTABLE_QUOTE", "stale": False,
            "raw_sha256": hashlib.sha256(raw).hexdigest(), "csv_sha256": hashlib.sha256(csv_raw).hexdigest(),
            "source_line": line, "source_row": row, "live_capital_allowed": False}


def archive_close(store, identity: dict, *, fetcher=fetch_original) -> dict:
    observed = timestamp(store.clock())
    attempts = []
    for offset in range(8):
        session = observed.astimezone(IST).date() - timedelta(days=offset)
        url = f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{session:%Y%m%d}_F_0000.csv.zip"
        try:
            raw, final_url = fetcher(url, HOSTS)
        except (ValueError, RuntimeError, OSError) as exc:
            attempts.append({"url": url, "result": str(exc)})
            continue
        capture = store.capture(raw, {"url": url, "final_url": final_url,
            "origin": "HTTP_RESPONSE_BYTES", "lane": "CC001-SESSION-CLOSE-v1"})
        # A retrieved but invalid file is a failure, not permission to search
        # older files until one happens to contain an attractive/matching price.
        quote = parse_bhavcopy(raw, identity, session, capture["captured_at"])
        quote["source_url"] = url
        quote["archive_probes"] = attempts
        quote["coverage"] = "MOST_RECENT_RETRIEVED_FILE_WITHIN_7_DAYS_NOT_VERIFIED_TRADING_CALENDAR"
        return quote
    raise ChangeError("no verified official session-close archive within seven days")
