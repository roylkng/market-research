#!/usr/bin/env python3
"""Run H010's frozen backward historical robustness test from official NSE sources."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import statistics
import time
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import numpy as np
import requests

from marketlab.marketdata import index_snapshot_url, udiff_url
from marketlab.nse import NSEClient, NSEEndpoint

IST = ZoneInfo("Asia/Kolkata")
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "Chrome/152.0 Safari/537.36"
)
LEGACY = NSEEndpoint(
    "legacy_financials",
    "https://www.nseindia.com/api/corporates-financial-results",
)
EVENT_START = date(2024, 10, 1)
EVENT_END = date(2025, 6, 30)
MARKET_START = date(2024, 6, 15)
MARKET_END = date(2025, 9, 30)
PRIMARY_TURNOVER = 20_000_000.0
RANDOM_SEED = 101
RANDOM_DRAWS = 10_000


@dataclass(frozen=True)
class Action:
    symbol: str
    ex_date: date
    factor: float | None
    subject: str
    unresolved: bool


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def retain(root: Path, raw: bytes, *, url: str, kind: str) -> dict[str, object]:
    if not raw:
        raise ValueError("cannot retain empty source")
    digest = sha256(raw)
    path = root / "raw" / digest
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("content-addressed source collision")
    else:
        path.write_bytes(raw)
    return {
        "url": url,
        "kind": kind,
        "sha256": digest,
        "bytes": len(raw),
        "raw_path": str(path.relative_to(root)),
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "status": "OK",
    }


def parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            parsed = time.strptime(text, fmt)
            return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
        except ValueError:
            continue
    return None


def parse_publication(value: object) -> datetime | None:
    text = str(value or "").strip()
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=IST)
        except ValueError:
            continue
    return None


def valid_archive_url(value: object) -> str | None:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return None
    if (parsed.hostname or "").lower() not in {
        "nsearchives.nseindia.com",
        "archives.nseindia.com",
    }:
        return None
    return url


def month_chunks(start: date, end: date):
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        if cursor.month == 12:
            next_month = date(cursor.year + 1, 1, 1)
        else:
            next_month = date(cursor.year, cursor.month + 1, 1)
        chunk_end = min(end, next_month - timedelta(days=1))
        yield max(start, cursor), chunk_end
        cursor = next_month


def acquire_result_events(root: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    client = NSEClient(timeout=20, attempts=4)
    manifests: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    for start, end in month_chunks(EVENT_START, EVENT_END):
        params = {
            "index": "equities",
            "period": "Quarterly",
            "from_date": start.strftime("%d-%m-%Y"),
            "to_date": end.strftime("%d-%m-%Y"),
        }
        payload, raw = client._json_get_with_raw(LEGACY, params=params)
        url = (
            f"{LEGACY.url}?index=equities&period=Quarterly"
            f"&from_date={params['from_date']}&to_date={params['to_date']}"
        )
        meta = retain(root, raw, url=url, kind="legacy-result-listing")
        manifests.append(meta)
        if not isinstance(payload, list):
            raise ValueError("legacy result listing must be a JSON list")
        for source in payload:
            if not isinstance(source, dict):
                continue
            symbol = str(source.get("symbol") or "").strip().upper()
            quarter_end = parse_date(source.get("toDate"))
            published = parse_publication(source.get("broadCastDate"))
            xbrl = valid_archive_url(source.get("xbrl"))
            series = str(source.get("series") or "EQ").strip().upper()
            if (
                not symbol
                or quarter_end is None
                or published is None
                or xbrl is None
                or series != "EQ"
                or not (EVENT_START <= published.date() <= EVENT_END)
            ):
                continue
            basis_token = str(source.get("consolidated") or "").strip().casefold()
            basis = "C" if basis_token == "consolidated" else "S"
            rows.append(
                {
                    "symbol": symbol,
                    "quarter_end": quarter_end.isoformat(),
                    "published": published.isoformat(),
                    "basis": basis,
                    "xbrl_url": xbrl,
                    "company": str(
                        source.get("companyName")
                        or source.get("smName")
                        or source.get("cmName")
                        or symbol
                    ),
                    "listing_source_sha256": meta["sha256"],
                }
            )
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["symbol"]), str(row["quarter_end"]))].append(row)

    events: list[dict[str, object]] = []
    for _, group in sorted(groups.items()):
        consolidated = [row for row in group if row["basis"] == "C"]
        pool = consolidated or group
        selected = min(pool, key=lambda row: (str(row["published"]), str(row["xbrl_url"])))
        event_id = "|".join(
            [
                str(selected["symbol"]),
                str(selected["quarter_end"]),
                str(selected["basis"]),
                str(selected["published"]),
            ]
        )
        selected = dict(selected)
        selected["event_id"] = event_id
        events.append(selected)
    return events, manifests


def fetch_public(
    url: str,
    *,
    kind: str,
    attempts: int = 4,
) -> tuple[bytes | None, dict[str, object]]:
    last_error: str | None = None
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
    for attempt in range(attempts):
        try:
            response = session.get(url, timeout=(8, 25), allow_redirects=True)
            host = (urlparse(response.url).hostname or "").lower()
            if host not in {"nsearchives.nseindia.com", "archives.nseindia.com"}:
                raise ValueError("archive redirected outside NSE hosts")
            if response.status_code == 404:
                return None, {"url": url, "kind": kind, "status": "HTTP_404"}
            if response.status_code in {403, 429} or response.status_code >= 500:
                last_error = f"HTTP {response.status_code}"
                if attempt + 1 < attempts:
                    time.sleep(0.5 * (2**attempt))
                    continue
            response.raise_for_status()
            if not response.content:
                raise ValueError("empty archive response")
            return response.content, {"url": url, "kind": kind, "status": "OK"}
        except (requests.RequestException, ValueError) as exc:
            last_error = str(exc)
            if attempt + 1 < attempts:
                time.sleep(0.5 * (2**attempt))
    return None, {"url": url, "kind": kind, "status": "FETCH_FAILED", "error": last_error}


def parse_udiff(raw_zip: bytes, session_date: date) -> dict[str, dict[str, object]]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
            names = archive.namelist()
            if len(names) != 1 or not names[0].lower().endswith(".csv"):
                raise ValueError("UDiFF archive must contain exactly one CSV")
            text = archive.read(names[0]).decode("utf-8-sig")
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid UDiFF archive: {exc}") from exc

    result: dict[str, dict[str, object]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        if (
            str(row.get("TradDt") or "").strip() != session_date.isoformat()
            or str(row.get("Sgmt") or "").strip().upper() != "CM"
            or str(row.get("Src") or "").strip().upper() != "NSE"
            or str(row.get("FinInstrmTp") or "").strip().upper() != "STK"
            or str(row.get("SctySrs") or "").strip().upper() != "EQ"
        ):
            continue
        symbol = str(row.get("TckrSymb") or "").strip().upper()
        if not symbol:
            continue
        try:
            values = {
                "open": float(row["OpnPric"]),
                "high": float(row["HghPric"]),
                "low": float(row["LwPric"]),
                "close": float(row["ClsPric"]),
                "volume": float(row.get("TtlTradgVol") or 0),
                "turnover": float(row.get("TtlTrfVal") or 0),
            }
        except (KeyError, TypeError, ValueError):
            continue
        if (
            not all(math.isfinite(value) for value in values.values())
            or min(values["open"], values["high"], values["low"], values["close"]) <= 0
            or values["volume"] < 0
            or values["turnover"] < 0
        ):
            continue
        if symbol in result:
            raise ValueError(f"duplicate EQ row for {symbol} on {session_date}")
        result[symbol] = {
            "date": session_date.isoformat(),
            "isin": str(row.get("ISIN") or "").strip(),
            **values,
        }
    if not result:
        raise ValueError(f"no EQ rows in UDiFF for {session_date}")
    return result


def parse_nifty500(raw_csv: bytes, session_date: date) -> dict[str, float]:
    try:
        text = raw_csv.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("index snapshot is not UTF-8") from exc
    matches: list[dict[str, str]] = []
    for row in csv.DictReader(io.StringIO(text)):
        name = " ".join(str(row.get("Index Name") or "").split())
        if name.casefold() != "nifty 500":
            continue
        raw_date = str(row.get("Index Date") or "").strip()
        parsed = parse_date(raw_date)
        if parsed == session_date:
            matches.append(row)
    if len(matches) != 1:
        raise ValueError(
            f"expected one Nifty 500 row on {session_date}; found {len(matches)}"
        )
    row = matches[0]
    try:
        opened = float(row["Open Index Value"])
        closed = float(row["Closing Index Value"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid Nifty 500 OHLC") from exc
    if not all(math.isfinite(value) and value > 0 for value in (opened, closed)):
        raise ValueError("nonpositive Nifty 500 OHLC")
    return {"open": opened, "close": closed}


def acquire_market(
    root: Path,
) -> tuple[
    list[date],
    dict[str, dict[date, dict[str, object]]],
    dict[date, dict[str, float]],
    list[dict[str, object]],
]:
    days = []
    cursor = MARKET_START
    while cursor <= MARKET_END:
        days.append(cursor)
        cursor += timedelta(days=1)

    def one(day: date):
        u_url = udiff_url(day)
        i_url = index_snapshot_url(day)
        u_raw, u_meta = fetch_public(u_url, kind="bhavcopy")
        i_raw, i_meta = fetch_public(i_url, kind="index")
        return day, u_raw, u_meta, i_raw, i_meta

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(one, day) for day in days]
        for number, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if number % 100 == 0:
                print(f"market requests {number}/{len(days)}", flush=True)

    by_symbol: dict[str, dict[date, dict[str, object]]] = defaultdict(dict)
    index: dict[date, dict[str, float]] = {}
    sessions: list[date] = []
    manifest: list[dict[str, object]] = []
    asymmetry = []
    parse_errors = []
    for day, u_raw, u_meta, i_raw, i_meta in sorted(results, key=lambda item: item[0]):
        for raw, meta in ((u_raw, u_meta), (i_raw, i_meta)):
            if raw is not None:
                retained = retain(root, raw, url=str(meta["url"]), kind=str(meta["kind"]))
                manifest.append(retained)
            else:
                manifest.append(meta)
        if (u_raw is None) != (i_raw is None):
            asymmetry.append(
                {
                    "date": day.isoformat(),
                    "bhavcopy_status": u_meta["status"],
                    "index_status": i_meta["status"],
                }
            )
            continue
        if u_raw is None and i_raw is None:
            continue
        try:
            equities = parse_udiff(u_raw, day)
            nifty = parse_nifty500(i_raw, day)
        except ValueError as exc:
            parse_errors.append({"date": day.isoformat(), "error": str(exc)})
            continue
        sessions.append(day)
        index[day] = nifty
        for symbol, bar in equities.items():
            by_symbol[symbol][day] = bar

    if asymmetry:
        raise ValueError(f"market/index archive asymmetry on {len(asymmetry)} dates")
    if parse_errors:
        raise ValueError(f"market parse errors on {len(parse_errors)} dates")
    if len(sessions) < 300:
        raise ValueError(f"insufficient market sessions: {len(sessions)}")
    return sessions, by_symbol, index, manifest


def parse_float_pair(subject: str) -> tuple[float, float] | None:
    lowered = subject.casefold()
    split = re.search(
        r"from\s+(?:rs|re)\s*([0-9]+(?:\.[0-9]+)?)"
        r".*?\bto\s+(?:rs|re)\s*([0-9]+(?:\.[0-9]+)?)",
        lowered,
    )
    if not split:
        return None
    old = float(split.group(1))
    new = float(split.group(2))
    if old <= 0 or new <= 0:
        return None
    return old, new


def parse_action(row: dict[str, object]) -> Action | None:
    if str(row.get("series") or "").strip().upper() != "EQ":
        return None
    symbol = str(row.get("symbol") or "").strip().upper()
    ex_date = parse_date(row.get("exDate"))
    subject = " ".join(str(row.get("subject") or "").split())
    if not symbol or ex_date is None or not subject:
        return None
    lowered = subject.casefold()

    unresolved_tokens = (
        "rights",
        "demerger",
        "scheme of arrangement",
        "amalgamation",
        "merger",
        "capital reduction",
    )
    if any(token in lowered for token in unresolved_tokens):
        return Action(symbol, ex_date, None, subject, True)

    if "bonus" in lowered:
        match = re.search(
            r"\bbonus\s+([0-9]+(?:\.[0-9]+)?):([0-9]+(?:\.[0-9]+)?)",
            lowered,
        )
        if match:
            added = float(match.group(1))
            held = float(match.group(2))
            if added >= 0 and held > 0:
                return Action(symbol, ex_date, (added + held) / held, subject, False)
        return Action(symbol, ex_date, None, subject, True)

    if "split" in lowered or "sub-division" in lowered or "subdivision" in lowered:
        pair = parse_float_pair(subject)
        if pair:
            old, new = pair
            return Action(symbol, ex_date, old / new, subject, False)
        return Action(symbol, ex_date, None, subject, True)

    if "consolidation" in lowered:
        pair = parse_float_pair(subject)
        if pair:
            old, new = pair
            return Action(symbol, ex_date, old / new, subject, False)
        return Action(symbol, ex_date, None, subject, True)

    return None


def acquire_actions(
    root: Path,
) -> tuple[dict[str, list[Action]], list[dict[str, object]]]:
    client = NSEClient(timeout=20, attempts=4)
    manifests: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    for start, end in month_chunks(MARKET_START, MARKET_END):
        params = {
            "index": "equities",
            "from_date": start.strftime("%d-%m-%Y"),
            "to_date": end.strftime("%d-%m-%Y"),
        }
        payload, raw = client._json_get_with_raw(
            client.CORPORATE_ACTION_ENDPOINT,
            params=params,
        )
        url = (
            f"{client.CORPORATE_ACTION_ENDPOINT.url}?index=equities"
            f"&from_date={params['from_date']}&to_date={params['to_date']}"
        )
        manifests.append(retain(root, raw, url=url, kind="corporate-actions"))
        if isinstance(payload, list):
            rows.extend(row for row in payload if isinstance(row, dict))
        elif isinstance(payload, dict):
            candidate = payload.get("data") or payload.get("records") or []
            if isinstance(candidate, list):
                rows.extend(row for row in candidate if isinstance(row, dict))

    deduped: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in rows:
        key = (
            str(row.get("symbol") or "").strip().upper(),
            str(row.get("exDate") or "").strip(),
            " ".join(str(row.get("subject") or "").split()),
        )
        deduped[key] = row

    actions: dict[str, list[Action]] = defaultdict(list)
    for row in deduped.values():
        action = parse_action(row)
        if action is not None:
            actions[action.symbol].append(action)
    for group in actions.values():
        group.sort(key=lambda action: (action.ex_date, action.subject))
    return actions, manifests


def factor_after(actions: list[Action], day: date, through: date) -> float:
    factor = 1.0
    for action in actions:
        if day < action.ex_date <= through:
            if action.unresolved or action.factor is None:
                raise ValueError("unresolved action cannot be adjusted")
            factor *= action.factor
    return factor


def adjusted_price(value: float, *, day: date, through: date, actions: list[Action]) -> float:
    return value / factor_after(actions, day, through)


def adjusted_volume(value: float, *, day: date, through: date, actions: list[Action]) -> float:
    return value * factor_after(actions, day, through)


def unresolved_crossing(actions: list[Action], start: date, end: date) -> list[str]:
    return [
        action.subject
        for action in actions
        if action.unresolved and start < action.ex_date <= end
    ]


def midcdf_scores(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    finite = np.isfinite(values)
    result = np.full(len(values), 0.5, dtype=float)
    if not finite.any():
        return result
    clean = values[finite]
    median = float(np.median(clean))
    filled = np.where(finite, values, median)
    order = np.argsort(filled, kind="stable")
    sorted_values = filled[order]
    ranks = np.zeros(len(filled), dtype=float)
    start = 0
    while start < len(sorted_values):
        end = start + 1
        while end < len(sorted_values) and sorted_values[end] == sorted_values[start]:
            end += 1
        midpoint = (start + 0.5 * (end - start)) / len(sorted_values)
        ranks[order[start:end]] = midpoint
        start = end
    return ranks


def top_mask(scores: np.ndarray, ids: np.ndarray, fraction: float = 0.10) -> np.ndarray:
    count = max(1, math.ceil(len(scores) * fraction))
    order = np.lexsort((ids, -np.asarray(scores, dtype=float)))
    mask = np.zeros(len(scores), dtype=bool)
    mask[order[:count]] = True
    return mask


def summarize_selection(
    rows: list[dict[str, object]],
    mask: np.ndarray,
) -> dict[str, object]:
    selected = [row for row, include in zip(rows, mask) if include]
    excess = np.asarray([float(row["excess_60d_pp"]) for row in selected], dtype=float)
    raw = np.asarray([float(row["stock_return_60d_pct"]) for row in selected], dtype=float)
    positives = np.maximum(raw, 0)
    total_positive = float(positives.sum())
    by_company: dict[str, float] = defaultdict(float)
    for row, value in zip(selected, positives):
        by_company[str(row["symbol"])] += float(value)
    concentration = (
        max(by_company.values()) / total_positive if total_positive > 0 and by_company else None
    )
    quarters: dict[str, dict[str, object]] = {}
    for quarter in sorted({str(row["publication_quarter"]) for row in selected}):
        q = [row for row in selected if str(row["publication_quarter"]) == quarter]
        q_excess = np.asarray([float(row["excess_60d_pp"]) for row in q])
        quarters[quarter] = {
            "selected": len(q),
            "median_excess_pp": float(np.median(q_excess)),
            "mean_excess_pp": float(np.mean(q_excess)),
            "beat_rate": float(np.mean(q_excess > 0)),
        }
    return {
        "selected": len(selected),
        "median_excess_pp": float(np.median(excess)),
        "mean_excess_pp": float(np.mean(excess)),
        "beat_rate": float(np.mean(excess > 0)),
        "median_raw_return_pct": float(np.median(raw)),
        "mean_raw_return_pct": float(np.mean(raw)),
        "excess_gte_5_rate": float(np.mean(excess >= 5.0)),
        "raw_gte_10_rate": float(np.mean(raw >= 10.0)),
        "max_company_positive_pnl_share": concentration,
        "by_publication_quarter": quarters,
    }


def random_test(
    rows: list[dict[str, object]],
    selected_count: int,
    observed: dict[str, object],
) -> dict[str, object]:
    excess = np.asarray([float(row["excess_60d_pp"]) for row in rows], dtype=float)
    rng = np.random.default_rng(RANDOM_SEED)
    medians = np.empty(RANDOM_DRAWS, dtype=float)
    means = np.empty(RANDOM_DRAWS, dtype=float)
    for draw in range(RANDOM_DRAWS):
        idx = rng.choice(len(excess), size=selected_count, replace=False)
        sample = excess[idx]
        medians[draw] = np.median(sample)
        means[draw] = np.mean(sample)
    observed_median = float(observed["median_excess_pp"])
    observed_mean = float(observed["mean_excess_pp"])
    return {
        "seed": RANDOM_SEED,
        "draws": RANDOM_DRAWS,
        "selected_count": selected_count,
        "median_empirical_one_sided_p": float(
            (1 + np.sum(medians >= observed_median)) / (RANDOM_DRAWS + 1)
        ),
        "mean_empirical_one_sided_p": float(
            (1 + np.sum(means >= observed_mean)) / (RANDOM_DRAWS + 1)
        ),
        "random_median_excess_median": float(np.median(medians)),
        "random_mean_excess_mean": float(np.mean(means)),
        "random_median_95_interval": [
            float(np.quantile(medians, 0.025)),
            float(np.quantile(medians, 0.975)),
        ],
        "random_mean_95_interval": [
            float(np.quantile(means, 0.025)),
            float(np.quantile(means, 0.975)),
        ],
    }


def publication_quarter(day: date) -> str:
    return f"{day.year}-Q{1 + (day.month - 1) // 3}"


def build_rows(
    events: list[dict[str, object]],
    sessions: list[date],
    bars: dict[str, dict[date, dict[str, object]]],
    index: dict[date, dict[str, float]],
    actions: dict[str, list[Action]],
) -> tuple[list[dict[str, object]], Counter]:
    session_index = {day: position for position, day in enumerate(sessions)}
    exclusions: Counter = Counter()
    rows: list[dict[str, object]] = []

    for event in events:
        symbol = str(event["symbol"])
        published = datetime.fromisoformat(str(event["published"]))
        stock = bars.get(symbol)
        if not stock:
            exclusions["missing_symbol_market_history"] += 1
            continue

        pub_day = published.date()
        if pub_day in session_index and published.time() >= dtime(15, 30):
            pre_pos = session_index[pub_day]
        elif pub_day in session_index:
            pre_pos = session_index[pub_day] - 1
        else:
            earlier = [position for position, day in enumerate(sessions) if day < pub_day]
            if earlier:
                pre_pos = earlier[-1]
            else:
                exclusions["no_pre_event_session"] += 1
                continue
        if pre_pos < 60:
            exclusions["insufficient_prior_market_sessions"] += 1
            continue
        pre_day = sessions[pre_pos]
        signal_start = sessions[pre_pos - 60]

        reaction_pos = None
        for position in range(max(0, pre_pos), len(sessions)):
            day = sessions[position]
            opened = datetime.combine(day, dtime(9, 15), tzinfo=IST)
            if opened > published:
                reaction_pos = position
                break
        if reaction_pos is None or reaction_pos + 1 >= len(sessions):
            exclusions["missing_reaction_or_entry_session"] += 1
            continue
        entry_pos = reaction_pos + 1
        label_end_pos = entry_pos + 59
        if label_end_pos >= len(sessions):
            exclusions["incomplete_forward_60_market_sessions"] += 1
            continue
        reaction_day = sessions[reaction_pos]
        entry_day = sessions[entry_pos]
        label_end = sessions[label_end_pos]

        required_pre = sessions[pre_pos - 60 : pre_pos + 1]
        required_forward = sessions[entry_pos : label_end_pos + 1]
        required_days = set(required_pre) | set(required_forward) | {reaction_day}
        if any(day not in stock for day in required_days):
            exclusions["missing_stock_bar_in_exact_window"] += 1
            continue

        prior20_days = sessions[pre_pos - 19 : pre_pos + 1]
        liquidity = statistics.median(float(stock[day]["turnover"]) for day in prior20_days)
        if liquidity < PRIMARY_TURNOVER:
            exclusions["below_primary_liquidity"] += 1
            continue

        stock_actions = actions.get(symbol, [])
        unresolved = unresolved_crossing(stock_actions, signal_start, label_end)
        if unresolved:
            exclusions["unresolved_structural_action"] += 1
            continue

        if (
            abs(float(stock[entry_day]["high"]) - float(stock[entry_day]["low"])) < 1e-12
            and abs(float(stock[entry_day]["close"]) - float(stock[entry_day]["high"])) < 1e-12
        ):
            exclusions["flat_entry_bar"] += 1
            continue

        try:
            stock_start = adjusted_price(
                float(stock[signal_start]["close"]),
                day=signal_start,
                through=label_end,
                actions=stock_actions,
            )
            stock_pre = adjusted_price(
                float(stock[pre_day]["close"]),
                day=pre_day,
                through=label_end,
                actions=stock_actions,
            )
            entry_open = adjusted_price(
                float(stock[entry_day]["open"]),
                day=entry_day,
                through=label_end,
                actions=stock_actions,
            )
            exit_close = adjusted_price(
                float(stock[label_end]["close"]),
                day=label_end,
                through=label_end,
                actions=stock_actions,
            )
            prior20_start = sessions[pre_pos - 20]
            prior20_price = adjusted_price(
                float(stock[prior20_start]["close"]),
                day=prior20_start,
                through=label_end,
                actions=stock_actions,
            )
            previous_reaction_day = sessions[reaction_pos - 1]
            reaction_previous_close = adjusted_price(
                float(stock[previous_reaction_day]["close"]),
                day=previous_reaction_day,
                through=label_end,
                actions=stock_actions,
            )
            reaction_close = adjusted_price(
                float(stock[reaction_day]["close"]),
                day=reaction_day,
                through=label_end,
                actions=stock_actions,
            )
        except ValueError:
            exclusions["action_adjustment_failure"] += 1
            continue

        nifty_start = index[signal_start]["close"]
        nifty_pre = index[pre_day]["close"]
        nifty_entry = index[entry_day]["open"]
        nifty_exit = index[label_end]["close"]

        stock_prior60 = 100 * (stock_pre / stock_start - 1)
        nifty_prior60 = 100 * (nifty_pre / nifty_start - 1)
        score = stock_prior60 - nifty_prior60
        prior20 = 100 * (stock_pre / prior20_price - 1)
        stock_return = 100 * (exit_close / entry_open - 1)
        nifty_return = 100 * (nifty_exit / nifty_entry - 1)
        excess = stock_return - nifty_return

        reaction_return = 100 * (reaction_close / reaction_previous_close - 1)
        prior_volume_days = sessions[reaction_pos - 20 : reaction_pos]
        adjusted_prior_volumes = [
            adjusted_volume(
                float(stock[day]["volume"]),
                day=day,
                through=label_end,
                actions=stock_actions,
            )
            for day in prior_volume_days
        ]
        reaction_volume = adjusted_volume(
            float(stock[reaction_day]["volume"]),
            day=reaction_day,
            through=label_end,
            actions=stock_actions,
        )
        median_volume = statistics.median(adjusted_prior_volumes)
        volume_ratio = reaction_volume / median_volume if median_volume > 0 else math.nan
        high = float(stock[reaction_day]["high"])
        low = float(stock[reaction_day]["low"])
        close = float(stock[reaction_day]["close"])
        close_location = (close - low) / (high - low) if high > low else math.nan

        row = dict(event)
        row.update(
            {
                "pre_event_date": pre_day.isoformat(),
                "signal_start_date": signal_start.isoformat(),
                "reaction_date": reaction_day.isoformat(),
                "entry_date": entry_day.isoformat(),
                "label_end_date": label_end.isoformat(),
                "median_20d_traded_value_inr": liquidity,
                "stock_prior_60_pct": stock_prior60,
                "nifty_prior_60_pct": nifty_prior60,
                "h010_score": score,
                "prior_20_return_pct": prior20,
                "reaction_1d_pct": reaction_return,
                "reaction_volume_ratio_20d": volume_ratio,
                "reaction_close_location": close_location,
                "stock_return_60d_pct": stock_return,
                "nifty_return_60d_pct": nifty_return,
                "excess_60d_pp": excess,
                "publication_quarter": publication_quarter(published.date()),
                "share_action_count": sum(
                    signal_start < action.ex_date <= label_end
                    for action in stock_actions
                    if not action.unresolved
                ),
            }
        )
        rows.append(row)

    return rows, exclusions


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def evaluate(rows: list[dict[str, object]]) -> dict[str, object]:
    if len(rows) < 1_000:
        return {
            "status": "ROBUSTNESS_COVERAGE_INSUFFICIENT",
            "evaluable_events": len(rows),
            "live_capital_allowed": False,
        }

    ids = np.asarray([str(row["event_id"]) for row in rows])
    scores = np.asarray([float(row["h010_score"]) for row in rows])
    prior20 = np.asarray([float(row["prior_20_return_pct"]) for row in rows])
    reaction_return = np.asarray([float(row["reaction_1d_pct"]) for row in rows])
    reaction_volume = np.asarray([float(row["reaction_volume_ratio_20d"]) for row in rows])
    reaction_location = np.asarray([float(row["reaction_close_location"]) for row in rows])

    primary_mask = top_mask(scores, ids)
    prior20_mask = top_mask(prior20, ids)
    tape_score = (
        midcdf_scores(reaction_return)
        + midcdf_scores(reaction_volume)
        + midcdf_scores(reaction_location)
    ) / 3
    tape_mask = top_mask(tape_score, ids)
    all_mask = np.ones(len(rows), dtype=bool)

    primary = summarize_selection(rows, primary_mask)
    baseline20 = summarize_selection(rows, prior20_mask)
    tape = summarize_selection(rows, tape_mask)
    unconditional = summarize_selection(rows, all_mask)
    random = random_test(rows, int(primary["selected"]), primary)

    quarter_ok = True
    for stats in primary["by_publication_quarter"].values():
        if int(stats["selected"]) >= 20 and float(stats["median_excess_pp"]) < -2.0:
            quarter_ok = False

    gates = {
        "evaluable_events_gte_1000": len(rows) >= 1_000,
        "selected_gte_100": int(primary["selected"]) >= 100,
        "median_excess_gt_3pp": float(primary["median_excess_pp"]) > 3.0,
        "mean_excess_gt_3pp": float(primary["mean_excess_pp"]) > 3.0,
        "beat_rate_gt_55pct": float(primary["beat_rate"]) > 0.55,
        "median_raw_return_positive": float(primary["median_raw_return_pct"]) > 0,
        "excess_gte_5_rate_gte_40pct": float(primary["excess_gte_5_rate"]) >= 0.40,
        "median_excess_beats_prior20": (
            float(primary["median_excess_pp"]) > float(baseline20["median_excess_pp"])
        ),
        "median_excess_beats_unconditional_by_3pp": (
            float(primary["median_excess_pp"])
            - float(unconditional["median_excess_pp"])
            >= 3.0
        ),
        "max_company_positive_pnl_share_lte_20pct": (
            primary["max_company_positive_pnl_share"] is not None
            and float(primary["max_company_positive_pnl_share"]) <= 0.20
        ),
        "quarter_stability": quarter_ok,
        "random_median_p_lt_005": float(random["median_empirical_one_sided_p"]) < 0.05,
        "random_mean_p_lt_005": float(random["mean_empirical_one_sided_p"]) < 0.05,
    }
    return {
        "status": (
            "HISTORICAL_ROBUSTNESS_PASS"
            if all(gates.values())
            else "HISTORICAL_ROBUSTNESS_FAIL"
        ),
        "evaluable_events": len(rows),
        "primary_top10": primary,
        "prior20_top10": baseline20,
        "tape_top10": tape,
        "unconditional": unconditional,
        "random_matched_test": random,
        "gates": gates,
        "all_gates_pass": all(gates.values()),
        "live_capital_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root = Path(args.out)
    root.mkdir(parents=True, exist_ok=True)

    events, listing_manifest = acquire_result_events(root)
    print(f"deduped result events={len(events)}", flush=True)
    sessions, bars, index, market_manifest = acquire_market(root)
    print(
        f"market sessions={len(sessions)} symbols={len(bars)} "
        f"market sources={len(market_manifest)}",
        flush=True,
    )
    actions, action_manifests = acquire_actions(root)
    rows, exclusions = build_rows(events, sessions, bars, index, actions)
    rows.sort(key=lambda row: (str(row["published"]), str(row["event_id"])))

    summary = evaluate(rows)
    summary.update(
        {
            "hypothesis": "H010",
            "signal": "prior_60_session_stock_minus_nifty500_return",
            "event_window": {"start": EVENT_START.isoformat(), "end": EVENT_END.isoformat()},
            "market_window": {"start": MARKET_START.isoformat(), "end": MARKET_END.isoformat()},
            "deduped_result_events": len(events),
            "market_sessions": len(sessions),
            "market_symbols": len(bars),
            "exclusions": dict(sorted(exclusions.items())),
            "listing_source_count": len(listing_manifest),
            "market_source_status": dict(
                Counter(str(item["status"]) for item in market_manifest)
            ),
            "corporate_action_source_sha256": [
                manifest["sha256"] for manifest in action_manifests
            ],
            "outcome_opened_at_utc": datetime.now(UTC).isoformat(),
            "evidence_classification": "BACKWARD_HISTORICAL_ROBUSTNESS_ONLY",
        }
    )

    ids = np.asarray([str(row["event_id"]) for row in rows])
    scores = np.asarray([float(row["h010_score"]) for row in rows])
    selected = top_mask(scores, ids) if rows else np.zeros(0, dtype=bool)
    for row, flag in zip(rows, selected):
        row["h010_top10_selected"] = bool(flag)

    dump(root / "robustness-summary.json", summary)
    dump(
        root / "source-manifest.json",
        listing_manifest + market_manifest + action_manifests,
    )
    dump(root / "result-events.json", events)
    write_csv(root / "robustness-predictions.csv", rows)
    write_csv(
        root / "h010-selected-top10.csv",
        [row for row in rows if row["h010_top10_selected"]],
    )
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
