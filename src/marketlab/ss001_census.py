from __future__ import annotations

import csv
import io
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_market import DailyEquityObservation
from marketlab.events import sha256_bytes

CENSUS_ID = "SS001-D001-v1"
SECURITY_MASTER_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
FINANCIAL_START = "2026-04-01"
FINANCIAL_END = "2026-10-04"
ACTION_START = "2025-10-05"
ACTION_END = "2026-10-04"
CURRENT_SESSION = "2026-10-01"
LIQUIDITY_SESSION_COUNT = 20

_REQUIRED_MASTER = {
    "SYMBOL",
    "NAME OF COMPANY",
    "SERIES",
    "DATE OF LISTING",
    "ISIN NUMBER",
}


@dataclass(frozen=True)
class ListedEquity:
    symbol: str
    company_name: str
    series: str
    listing_date: str | None
    paid_up_value: float | None
    market_lot: int | None
    isin: str
    face_value: float | None


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _parse_date(value: object) -> str | None:
    raw = _clean(value)
    if not raw:
        return None
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d-%B-%Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC).date().isoformat()
        except ValueError:
            continue
    return None


def _finite_float(value: object) -> float | None:
    raw = _clean(value).replace(",", "")
    if not raw:
        return None
    try:
        parsed = float(raw)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _positive_int(value: object) -> int | None:
    parsed = _finite_float(value)
    if parsed is None or parsed <= 0 or not parsed.is_integer():
        return None
    return int(parsed)


def parse_equity_security_master(raw_csv: bytes) -> list[ListedEquity]:
    try:
        text = raw_csv.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AlphaContractError("SS001 security master is not UTF-8") from exc

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise AlphaContractError("SS001 security master has no header")
    fields = {_clean(field).upper() for field in reader.fieldnames}
    missing = _REQUIRED_MASTER - fields
    if missing:
        raise AlphaContractError(
            f"SS001 security master missing required columns: {sorted(missing)}"
        )

    rows: list[ListedEquity] = []
    seen_symbols: set[str] = set()
    seen_isins: set[str] = set()
    for row in reader:
        normalized = {_clean(key).upper(): value for key, value in row.items()}
        series = _clean(normalized.get("SERIES")).upper()
        if series != "EQ":
            continue
        symbol = _clean(normalized.get("SYMBOL")).upper()
        isin = _clean(normalized.get("ISIN NUMBER")).upper()
        company = _clean(normalized.get("NAME OF COMPANY"))
        if not symbol or not isin or not company:
            raise AlphaContractError("SS001 EQ master row lacks symbol/ISIN/company")
        if symbol in seen_symbols:
            raise AlphaContractError(f"SS001 duplicate EQ symbol: {symbol}")
        if isin in seen_isins:
            raise AlphaContractError(f"SS001 duplicate EQ ISIN: {isin}")
        seen_symbols.add(symbol)
        seen_isins.add(isin)

        rows.append(
            ListedEquity(
                symbol=symbol,
                company_name=company,
                series=series,
                listing_date=_parse_date(normalized.get("DATE OF LISTING")),
                paid_up_value=_finite_float(normalized.get("PAID UP VALUE")),
                market_lot=_positive_int(normalized.get("MARKET LOT")),
                isin=isin,
                face_value=_finite_float(normalized.get("FACE VALUE")),
            )
        )

    if not rows:
        raise AlphaContractError("SS001 security master contains no EQ rows")
    return sorted(rows, key=lambda row: row.symbol)


def _payload_rows(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if data is None:
            return []
        if not isinstance(data, list):
            raise AlphaContractError("SS001 payload.data must be a list")
        return [row for row in data if isinstance(row, dict)]
    raise AlphaContractError("SS001 source payload must be list or object")


def financial_rows(payloads: list[object]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for payload in payloads:
        rows.extend(_payload_rows(payload))
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity = digest(row)
        unique[identity] = row
    return list(unique.values())


def _financial_index(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        row_type = _clean(row.get("type")).casefold()
        if row_type and row_type != "integrated filing- financials":
            continue
        symbol = _clean(row.get("symbol")).upper()
        if symbol:
            result[symbol].append(row)
    return result


def classify_action_subject(subject: object) -> str:
    text = _clean(subject).casefold()
    if not text:
        return "other"
    if "dividend" in text:
        return "dividend"
    if any(token in text for token in ("sub-division", "sub division", "split", "consolidation")):
        return "split_or_consolidation"
    if "bonus" in text:
        return "bonus"
    if "right" in text:
        return "rights"
    if any(token in text for token in ("merger", "demerger", "amalgamation", "scheme of arrangement", "spin-off", "spin off")):
        return "scheme_or_reorganisation"
    if "buyback" in text or "buy back" in text:
        return "buyback"
    if "delist" in text:
        return "delisting"
    return "other"


def action_rows(payloads: list[object]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for payload in payloads:
        rows.extend(_payload_rows(payload))
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        unique[digest(row)] = row
    return list(unique.values())


def _action_index(rows: list[dict[str, Any]]) -> dict[str, Counter]:
    result: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        series = _clean(row.get("series") or row.get("Series")).upper()
        if series and series != "EQ":
            continue
        symbol = _clean(
            row.get("symbol") or row.get("Symbol") or row.get("SYMBOL")
        ).upper()
        if not symbol:
            continue
        subject = (
            row.get("subject")
            or row.get("purpose")
            or row.get("Purpose")
            or row.get("SUBJECT")
        )
        result[symbol]["all"] += 1
        result[symbol][classify_action_subject(subject)] += 1
    return result


def _financial_context(rows: list[dict[str, Any]]) -> dict[str, Any]:
    periods = []
    timestamps = []
    for row in rows:
        period = _parse_date(row.get("qe_Date") or row.get("toDate"))
        if period:
            periods.append(period)
        raw_time = _clean(
            row.get("broadcast_Date")
            or row.get("broadcastDate")
            or row.get("broadCastDate")
        )
        if raw_time:
            timestamps.append(raw_time)
    return {
        "financial_filing_row_count": len(rows),
        "has_integrated_financial_filing": bool(rows),
        "latest_reported_period_end": max(periods) if periods else None,
        "latest_filing_timestamp_raw": max(timestamps) if timestamps else None,
    }


def _market_context(
    observations: list[DailyEquityObservation],
    *,
    expected_session_count: int,
) -> dict[str, Any]:
    ordered = sorted(observations, key=lambda row: row.session_date)
    turnovers = [row.turnover_inr for row in ordered]
    volumes = [row.volume for row in ordered]
    trades = [row.trade_count for row in ordered]
    first = ordered[0] if ordered else None
    last = ordered[-1] if ordered else None
    raw_return = None
    if first is not None and last is not None and first.close_price > 0:
        raw_return = last.close_price / first.close_price - 1.0
    return {
        "observed_session_count": len(ordered),
        "expected_session_count": expected_session_count,
        "traded_all_sessions": len(ordered) == expected_session_count,
        "positive_turnover_session_count": sum(value > 0 for value in turnovers),
        "first_observed_session": first.session_date if first else None,
        "last_observed_session": last.session_date if last else None,
        "first_close": first.close_price if first else None,
        "last_close": last.close_price if last else None,
        "raw_window_return": raw_return,
        "median_daily_turnover_inr": (
            statistics.median(turnovers) if turnovers else None
        ),
        "median_daily_volume": statistics.median(volumes) if volumes else None,
        "median_daily_trade_count": statistics.median(trades) if trades else None,
    }


def build_full_market_census(
    *,
    security_master_raw: bytes,
    market_sessions: list[dict[str, Any]],
    integrated_payloads: list[object],
    corporate_action_payloads: list[object],
    existing_u001_symbols: set[str],
    source_metadata: dict[str, Any],
) -> dict[str, Any]:
    securities = parse_equity_security_master(security_master_raw)
    if len(market_sessions) != LIQUIDITY_SESSION_COUNT:
        raise AlphaContractError(
            f"SS001 requires exactly {LIQUIDITY_SESSION_COUNT} market sessions"
        )

    market_by_identity: dict[tuple[str, str], list[DailyEquityObservation]] = defaultdict(list)
    session_dates: list[str] = []
    for session in market_sessions:
        session_date = _clean(session.get("session_date"))
        rows = session.get("equities")
        if not session_date or not isinstance(rows, list):
            raise AlphaContractError("SS001 market session is malformed")
        session_dates.append(session_date)
        for row in rows:
            if isinstance(row, DailyEquityObservation):
                obs = row
            elif isinstance(row, dict):
                obs = DailyEquityObservation(**row)
            else:
                raise TypeError("SS001 market observation must be object")
            market_by_identity[(obs.symbol, obs.isin)].append(obs)

    if session_dates != sorted(session_dates) or len(set(session_dates)) != len(session_dates):
        raise AlphaContractError("SS001 market sessions are not canonical")
    if session_dates[-1] != CURRENT_SESSION:
        raise AlphaContractError("SS001 market window must end on 2026-10-01")

    fin_rows = financial_rows(integrated_payloads)
    fin_index = _financial_index(fin_rows)
    corp_rows = action_rows(corporate_action_payloads)
    corp_index = _action_index(corp_rows)

    census_rows = []
    current_session_count = 0
    at_least_15_count = 0
    financial_count = 0
    in_u001_count = 0

    for security in securities:
        market = _market_context(
            market_by_identity.get((security.symbol, security.isin), []),
            expected_session_count=LIQUIDITY_SESSION_COUNT,
        )
        current_observed = market["last_observed_session"] == CURRENT_SESSION
        if current_observed:
            current_session_count += 1
        if market["observed_session_count"] >= 15:
            at_least_15_count += 1

        fin = _financial_context(fin_index.get(security.symbol, []))
        if fin["has_integrated_financial_filing"]:
            financial_count += 1

        actions = corp_index.get(security.symbol, Counter())
        in_u001 = security.symbol in existing_u001_symbols
        if in_u001:
            in_u001_count += 1

        census_rows.append(
            {
                **asdict(security),
                "listing_age_days_at_2026_10_01": (
                    (date.fromisoformat(CURRENT_SESSION) - date.fromisoformat(security.listing_date)).days
                    if security.listing_date
                    else None
                ),
                "market": market,
                "financial_source": fin,
                "corporate_actions_1y": {
                    "all": int(actions["all"]),
                    "dividend": int(actions["dividend"]),
                    "split_or_consolidation": int(actions["split_or_consolidation"]),
                    "bonus": int(actions["bonus"]),
                    "rights": int(actions["rights"]),
                    "scheme_or_reorganisation": int(actions["scheme_or_reorganisation"]),
                    "buyback": int(actions["buyback"]),
                    "delisting": int(actions["delisting"]),
                    "other": int(actions["other"]),
                },
                "in_existing_u001": in_u001,
                "return_outcomes_opened": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    count = len(securities)
    current_ratio = current_session_count / count
    history_ratio = at_least_15_count / count
    financial_ratio = financial_count / count

    threshold_passes = {
        "minimum_eq_identity_count": count >= 1500,
        "minimum_current_udiff_coverage": current_ratio >= 0.85,
        "minimum_15_of_20_session_coverage": history_ratio >= 0.70,
        "minimum_integrated_financial_coverage": financial_ratio >= 0.60,
        "all_corporate_action_chunks_acquired": bool(
            source_metadata.get("all_corporate_action_chunks_acquired")
        ),
    }

    output = {
        "schema_version": 1,
        "census_id": CENSUS_ID,
        "classification": "FULL_MARKET_SOURCE_CENSUS_NOT_ALPHA",
        "as_of_completed_session": CURRENT_SESSION,
        "liquidity_session_dates": session_dates,
        "universe_source_url": SECURITY_MASTER_URL,
        "universe_raw_sha256": sha256_bytes(security_master_raw),
        "eq_identity_count": count,
        "current_udiff_identity_count": current_session_count,
        "current_udiff_coverage_ratio": current_ratio,
        "at_least_15_of_20_session_count": at_least_15_count,
        "at_least_15_of_20_session_coverage_ratio": history_ratio,
        "integrated_financial_coverage_count": financial_count,
        "integrated_financial_coverage_ratio": financial_ratio,
        "corporate_action_row_count": len(corp_rows),
        "integrated_filing_row_count": len(fin_rows),
        "existing_u001_overlap_count": in_u001_count,
        "outside_existing_u001_count": count - in_u001_count,
        "source_metadata": source_metadata,
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_next_source_layers": all(threshold_passes.values()),
        "rows": census_rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["census_sha256"] = digest(output)
    return output
