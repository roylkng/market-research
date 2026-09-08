#!/usr/bin/env python3
from __future__ import annotations

import argparse
import calendar
import csv
import io
import json
import math
import statistics
import time
import xml.etree.ElementTree as ET
import zipfile
from bisect import bisect_left
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests

from marketlab.marketdata import udiff_url
from marketlab.nse import NSEClient

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "Chrome/151.0 Safari/537.36"
)
PRIMARY_TURNOVER = 20_000_000.0
DISCOVERY_TURNOVER = 2_500_000.0
STAGE1_VALID_SESSIONS = 10


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--event-start", default="2025-07-01")
    p.add_argument("--event-end", default="2026-07-31")
    p.add_argument("--price-start", default="2025-03-01")
    p.add_argument("--price-end", default="2026-08-31")
    p.add_argument("--out-dir", required=True)
    return p.parse_args()


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag.split(":", 1)[-1]


def fnum(text: str | None) -> float | None:
    if text is None:
        return None
    s = " ".join(text.replace("\xa0", " ").split()).strip()
    if not s or s.lower() in {"na", "n/a", "null", "-"}:
        return None
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    s = s.replace(",", "").replace("₹", "")
    try:
        value = float(s)
    except ValueError:
        return None
    return -value if neg else value


def pct_growth(cur: float | None, prior: float | None) -> float | None:
    if cur is None or prior is None or prior <= 0:
        return None
    return (cur / prior - 1.0) * 100.0


def safe_pct(a: float, b: float) -> float:
    if b == 0:
        return math.nan
    return (a / b - 1.0) * 100.0


def previous_year(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:
        return d.replace(year=d.year - 1, day=28)


def get_bytes(url: str, attempts: int = 4, timeout: float = 20.0) -> bytes | None:
    host = (urlparse(url).hostname or "").lower()
    if host not in {"nsearchives.nseindia.com", "archives.nseindia.com"}:
        raise RuntimeError(f"unsupported archive host: {url}")
    last = None
    for attempt in range(attempts):
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            if r.status_code == 404:
                return None
            if r.status_code in {429, 500, 502, 503, 504}:
                time.sleep(0.5 * (2**attempt))
                continue
            r.raise_for_status()
            return r.content
        except requests.RequestException as exc:
            last = exc
            time.sleep(0.5 * (2**attempt))
    raise RuntimeError(f"archive fetch failed: {url}: {last}")


def iter_weekdays(start: date, end: date):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def load_prices(start: date, end: date) -> tuple[list[date], dict[str, list[dict]]]:
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    sessions: list[date] = []
    failures: list[str] = []
    for n, d in enumerate(iter_weekdays(start, end), 1):
        raw = get_bytes(udiff_url(d))
        if raw is None:
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                names = zf.namelist()
                if len(names) != 1:
                    raise RuntimeError("unexpected UDiFF archive")
                text = zf.read(names[0]).decode("utf-8-sig")
        except Exception as exc:
            failures.append(f"{d}:{exc}")
            continue
        reader = csv.DictReader(io.StringIO(text))
        day_had_rows = False
        for row in reader:
            if (
                (row.get("Sgmt") or "").upper() != "CM"
                or (row.get("Src") or "").upper() != "NSE"
                or (row.get("FinInstrmTp") or "").upper() != "STK"
                or (row.get("SctySrs") or "").upper() != "EQ"
            ):
                continue
            symbol = (row.get("TckrSymb") or "").strip().upper()
            if not symbol:
                continue
            try:
                rec = {
                    "date": d,
                    "open": float(row["OpnPric"]),
                    "high": float(row["HghPric"]),
                    "low": float(row["LwPric"]),
                    "close": float(row["ClsPric"]),
                    "volume": float(row.get("TtlTradgVol") or 0),
                    "turnover": float(row.get("TtlTrfVal") or 0),
                    "isin": (row.get("ISIN") or "").strip(),
                }
            except (KeyError, TypeError, ValueError):
                continue
            if min(rec["open"], rec["high"], rec["low"], rec["close"]) <= 0:
                continue
            by_symbol[symbol].append(rec)
            day_had_rows = True
        if day_had_rows:
            sessions.append(d)
        if n % 40 == 0:
            print(f"price progress weekdays={n} sessions={len(sessions)} symbols={len(by_symbol)}")
    for rows in by_symbol.values():
        rows.sort(key=lambda x: x["date"])
    if failures:
        print("price parse failures", failures[:20])
    return sessions, by_symbol


def month_chunks(start: date, end: date):
    cur = date(start.year, start.month, 1)
    while cur <= end:
        last = date(cur.year, cur.month, calendar.monthrange(cur.year, cur.month)[1])
        yield max(cur, start), min(last, end)
        cur = (last + timedelta(days=1)).replace(day=1)


def fetch_filings(client: NSEClient, start: date, end: date) -> list[dict]:
    all_rows: list[dict] = []
    for a, b in month_chunks(start, end):
        page = 1
        chunk: list[dict] = []
        total = None
        while True:
            payload = client.integrated_filings(
                from_date=a.strftime("%d-%m-%Y"),
                to_date=b.strftime("%d-%m-%Y"),
                page=page,
                size=200,
            )
            if not isinstance(payload, dict):
                raise RuntimeError("integrated filing response is not an object")
            data = payload.get("data") or []
            if not isinstance(data, list):
                raise RuntimeError("integrated filing data is not a list")
            chunk.extend(data)
            total = int(payload.get("totalCount") or len(chunk))
            if not data or len(chunk) >= total:
                break
            page += 1
            if page > 100:
                raise RuntimeError(f"filing pagination runaway {a} {b} total={total}")
            time.sleep(0.08)
        print(f"filings {a}..{b}: {len(chunk)}/{total}")
        all_rows.extend(chunk)
    return all_rows


def dedupe_filings(rows: list[dict]) -> list[dict]:
    candidates: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        qe = str(row.get("qe_Date") or "").strip().upper()
        xbrl = str(row.get("xbrl") or "").strip()
        broadcast = str(row.get("broadcast_Date") or "").strip()
        if not symbol or not qe or not xbrl or not broadcast:
            continue
        candidates[(symbol, qe)].append(row)
    selected: list[dict] = []
    for _, group in candidates.items():
        originals = [r for r in group if str(r.get("type_Sub") or "").lower() == "original"] or group
        consolidated = [
            r for r in originals if str(r.get("consolidated") or "").lower() == "consolidated"
        ]
        pool = consolidated or originals
        pool.sort(key=lambda r: str(r.get("broadcast_Date") or ""))
        selected.append(pool[0])
    return selected


def parse_broadcast(value: str) -> datetime:
    return datetime.strptime(value, "%d-%b-%Y %H:%M:%S")


def first_session_on_or_after(sessions: list[date], target: date) -> date | None:
    i = bisect_left(sessions, target)
    return sessions[i] if i < len(sessions) else None


def decision_session(sessions: list[date], broadcast: datetime) -> date | None:
    d = broadcast.date()
    i = bisect_left(sessions, d)
    if i >= len(sessions):
        return None
    if sessions[i] != d:
        return sessions[i]
    if broadcast.time() <= datetime.strptime("20:00:00", "%H:%M:%S").time():
        return d
    return sessions[i + 1] if i + 1 < len(sessions) else None


def row_index(rows: list[dict], d: date) -> int | None:
    dates = [r["date"] for r in rows]
    i = bisect_left(dates, d)
    if i < len(rows) and rows[i]["date"] == d:
        return i
    return None


def pre_event_features(rows: list[dict], idx: int) -> dict | None:
    if idx < 60:
        return None
    close = rows[idx]["close"]
    prior20 = rows[idx - 20 : idx]
    return {
        "prior_1d_return_pct": safe_pct(close, rows[idx - 1]["close"]),
        "prior_5d_return_pct": safe_pct(close, rows[idx - 5]["close"]),
        "prior_20d_return_pct": safe_pct(close, rows[idx - 20]["close"]),
        "median_20d_traded_value_inr": statistics.median(r["turnover"] for r in prior20),
        "median_20d_volume": statistics.median(r["volume"] for r in prior20),
        "prior_60d_high": max(r["high"] for r in rows[idx - 60 : idx]),
        "close": close,
    }


def facts_and_contexts(raw: bytes):
    root = ET.fromstring(raw)
    contexts: dict[str, dict] = {}
    for elem in root.iter():
        if local(elem.tag) != "context":
            continue
        cid = elem.attrib.get("id")
        if not cid:
            continue
        start = end = instant = None
        dimensional = False
        for child in elem.iter():
            name = local(child.tag)
            txt = (child.text or "").strip()
            if name == "startDate" and txt:
                start = txt
            elif name == "endDate" and txt:
                end = txt
            elif name == "instant" and txt:
                instant = txt
            elif name in {"explicitMember", "typedMember"}:
                dimensional = True
        contexts[cid] = {"start": start, "end": end, "instant": instant, "dimensional": dimensional}
    facts: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for elem in root.iter():
        ctx = elem.attrib.get("contextRef")
        txt = (elem.text or "").strip()
        if ctx and txt:
            facts[local(elem.tag)].append((ctx, txt))
    return facts, contexts


def fact(facts: dict, names: list[str], ctx: str) -> float | None:
    for name in names:
        vals = [fnum(v) for c, v in facts.get(name, []) if c == ctx]
        vals = [v for v in vals if v is not None]
        if vals:
            return vals[0]
    return None


def text_fact(facts: dict, names: list[str], ctx: str) -> str | None:
    for name in names:
        vals = [v for c, v in facts.get(name, []) if c == ctx and v]
        if vals:
            return vals[0]
    return None


def primary_context(facts: dict) -> str | None:
    vals = [(c, v) for c, v in facts.get("Symbol", []) if c and v]
    if not vals:
        return None
    return vals[0][0]


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def comparison_context(facts: dict, contexts: dict, primary: str) -> str | None:
    meta = contexts.get(primary) or {}
    pstart = parse_iso_date(meta.get("start"))
    pend = parse_iso_date(meta.get("end"))
    if not pstart or not pend:
        return None
    target_start = previous_year(pstart)
    target_end = previous_year(pend)
    candidates: list[tuple[int, bool, str]] = []
    revenue_contexts = {c for c, _ in facts.get("RevenueFromOperations", [])}
    for cid, cm in contexts.items():
        if cid == primary or cid not in revenue_contexts:
            continue
        cstart = parse_iso_date(cm.get("start"))
        cend = parse_iso_date(cm.get("end"))
        if not cstart or not cend:
            continue
        score = abs((cstart - target_start).days) + abs((cend - target_end).days)
        duration_delta = abs(((cend - cstart) - (pend - pstart)).days)
        score += duration_delta * 3
        candidates.append((score, bool(cm.get("dimensional")), cid))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    return candidates[0][2] if candidates[0][0] <= 12 else None


def to_crore(value: float | None, rounding: str | None) -> float | None:
    if value is None:
        return None
    token = (rounding or "").lower()
    if "crore" in token:
        return value
    if "lakh" in token:
        return value / 100.0
    if "million" in token:
        return value / 10.0
    if "thousand" in token:
        return value / 10000.0
    if "actual" in token or "unit" in token:
        return value / 10_000_000.0
    return None


def financial_metrics(raw: bytes) -> dict | None:
    try:
        facts, contexts = facts_and_contexts(raw)
    except ET.ParseError:
        return None
    cur = primary_context(facts)
    if not cur:
        return None
    prior = comparison_context(facts, contexts, cur)
    if not prior:
        return None
    rev_names = ["RevenueFromOperations"]
    pbei_names = ["ProfitBeforeExceptionalItemsAndTax", "ProfitBeforeExceptionalItemsAndTaxShareOfProfitLossOfAssociatesJointVentures"]
    finance_names = ["FinanceCosts"]
    dep_names = ["DepreciationDepletionAndAmortisationExpense", "DepreciationAndAmortisationExpense", "DepreciationExpense"]
    pat_names = ["ProfitLossForPeriod", "ProfitLossForPeriodFromContinuingOperations"]
    other_names = ["OtherIncome"]
    exceptional_names = ["ExceptionalItemsBeforeTax", "ExceptionalItems"]
    pbt_names = ["ProfitBeforeTax"]

    def metrics(ctx: str) -> dict:
        rev = fact(facts, rev_names, ctx)
        pbei = fact(facts, pbei_names, ctx)
        finance = fact(facts, finance_names, ctx)
        dep = fact(facts, dep_names, ctx)
        pat = fact(facts, pat_names, ctx)
        ebitda = None
        if pbei is not None and finance is not None and dep is not None:
            ebitda = pbei + finance + dep
        margin = ebitda / rev * 100.0 if ebitda is not None and rev not in (None, 0) else None
        return {
            "revenue": rev,
            "pbei": pbei,
            "finance": finance,
            "depreciation": dep,
            "ebitda_proxy": ebitda,
            "ebitda_margin_pct": margin,
            "pat": pat,
            "other_income": fact(facts, other_names, ctx),
            "exceptional": fact(facts, exceptional_names, ctx),
            "pbt": fact(facts, pbt_names, ctx),
        }

    current = metrics(cur)
    previous = metrics(prior)
    rounding = text_fact(facts, ["LevelOfRounding", "LevelOfRoundingUsedInFinancialResults"], cur)
    pat_crore = to_crore(current["pat"], rounding)
    revenue_yoy = pct_growth(current["revenue"], previous["revenue"])
    ebitda_yoy = pct_growth(current["ebitda_proxy"], previous["ebitda_proxy"])
    pat_yoy = pct_growth(current["pat"], previous["pat"])
    margin_change = (
        current["ebitda_margin_pct"] - previous["ebitda_margin_pct"]
        if current["ebitda_margin_pct"] is not None and previous["ebitda_margin_pct"] is not None
        else None
    )
    if None in (revenue_yoy, ebitda_yoy, pat_yoy, margin_change):
        anchor = False
    else:
        anchor = (
            revenue_yoy >= 20.0
            and ebitda_yoy >= 30.0
            and pat_yoy >= 40.0
            and margin_change >= 1.0
        )
    if pat_crore is not None and pat_crore < 2.0:
        anchor = False
    warning = False
    if current["pbt"] not in (None, 0):
        numerator = abs(current["other_income"] or 0) + abs(current["exceptional"] or 0)
        warning = numerator / abs(current["pbt"]) >= 0.30
    return {
        "current": current,
        "prior": previous,
        "rounding": rounding,
        "quarterly_pat_crore": pat_crore,
        "revenue_yoy_pct": revenue_yoy,
        "ebitda_yoy_pct": ebitda_yoy,
        "pat_yoy_pct": pat_yoy,
        "margin_change_pp": margin_change,
        "earnings_anchor": anchor,
        "quality_warning_nonoperating": warning,
        "primary_context": cur,
        "comparison_context": prior,
    }


def tape_trigger(rows: list[dict], start_idx: int) -> tuple[int | None, list[str]]:
    stop = min(len(rows) - 2, start_idx + STAGE1_VALID_SESSIONS)
    for idx in range(start_idx + 1, stop + 1):
        if idx < 60:
            continue
        prior20 = rows[idx - 20 : idx]
        prior5_return = safe_pct(rows[idx]["close"], rows[idx - 5]["close"])
        if prior5_return >= 15.0:
            break
        conditions: list[str] = []
        one_day = safe_pct(rows[idx]["close"], rows[idx - 1]["close"])
        if 2.0 <= one_day <= 8.0:
            conditions.append("EARLY_PRICE_RECOGNITION")
        medvol = statistics.median(r["volume"] for r in prior20)
        if medvol > 0 and rows[idx]["volume"] / medvol >= 2.0:
            conditions.append("ABNORMAL_VOLUME")
        high60 = max(r["high"] for r in rows[idx - 60 : idx])
        if rows[idx]["close"] >= 0.95 * high60:
            conditions.append("NEAR_60D_HIGH")
        flat_circuit_proxy = (
            abs(rows[idx]["high"] - rows[idx]["low"]) < 1e-9
            and abs(rows[idx]["close"] - rows[idx]["high"]) < 1e-9
            and one_day >= 4.9
        )
        if len(conditions) >= 2 and not flat_circuit_proxy:
            return idx, conditions
    return None, []


def outcome_from_entry(rows: list[dict], entry_idx: int) -> dict | None:
    if entry_idx >= len(rows) or entry_idx + 19 >= len(rows):
        return None
    entry = rows[entry_idx]["open"]
    forward = rows[entry_idx : entry_idx + 20]
    max_high = max(r["high"] for r in forward)
    max_ret = max_high / entry - 1.0
    first_hit = None
    for offset, r in enumerate(forward):
        if r["high"] / entry - 1.0 >= 0.25:
            first_hit = offset
            break
    return {
        "entry_date": rows[entry_idx]["date"].isoformat(),
        "entry_open": entry,
        "max_20d_return_pct": max_ret * 100.0,
        "explosive_20d": max_ret >= 0.25,
        "lead_sessions_to_25pct": first_hit,
        "close_20d_return_pct": (forward[-1]["close"] / entry - 1.0) * 100.0,
    }


def event_reference_outcome(rows: list[dict], decision_idx: int) -> dict | None:
    return outcome_from_entry(rows, decision_idx + 1)


def quarter_key(d: date) -> str:
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def summarize(records: list[dict]) -> dict:
    evaluable = [r for r in records if r.get("reference_outcome")]
    future = [r for r in evaluable if r["reference_outcome"]["explosive_20d"]]
    stage1 = [r for r in evaluable if r["earnings_anchor"]]
    stage2 = [r for r in stage1 if r.get("h004_trigger_outcome")]
    stage2_hits = [r for r in stage2 if r["h004_trigger_outcome"]["explosive_20d"]]
    baseline = [r for r in evaluable if r.get("baseline_trigger_outcome")]
    baseline_hits = [r for r in baseline if r["baseline_trigger_outcome"]["explosive_20d"]]
    future_stage1 = [r for r in future if r["earnings_anchor"]]
    future_stage2 = [r for r in future if r.get("h004_trigger_outcome")]
    future_baseline = [r for r in future if r.get("baseline_trigger_outcome")]
    leads = [r["h004_trigger_outcome"]["lead_sessions_to_25pct"] for r in stage2_hits]
    leads = [x for x in leads if x is not None]
    quarters = {}
    for q in sorted({r["quarter"] for r in evaluable}):
        qrows = [r for r in evaluable if r["quarter"] == q]
        qfuture = [r for r in qrows if r["reference_outcome"]["explosive_20d"]]
        qsig = [r for r in qrows if r.get("h004_trigger_outcome")]
        qhit = [r for r in qsig if r["h004_trigger_outcome"]["explosive_20d"]]
        quarters[q] = {
            "events": len(qrows),
            "future_explosive_events": len(qfuture),
            "stage2_signals": len(qsig),
            "stage2_hits": len(qhit),
            "stage2_precision": len(qhit) / len(qsig) if qsig else None,
            "stage2_recall": len([r for r in qfuture if r.get("h004_trigger_outcome")]) / len(qfuture) if qfuture else None,
        }
    return {
        "schema_version": 1,
        "experiment": "H004-HR002-EARNINGS-SUBENGINE",
        "status": "HISTORICAL_RECONSTRUCTION_NOT_OUT_OF_SAMPLE",
        "live_capital_allowed": False,
        "stage1_valid_sessions": STAGE1_VALID_SESSIONS,
        "counts": {
            "evaluable_result_events": len(evaluable),
            "future_explosive_result_events": len(future),
            "stage1_earnings_anchors": len(stage1),
            "stage2_signals": len(stage2),
            "stage2_hits": len(stage2_hits),
            "momentum_baseline_triggers": len(baseline),
            "momentum_baseline_hits": len(baseline_hits),
        },
        "metrics": {
            "stage1_recall_of_future_explosive_result_events": len(future_stage1) / len(future) if future else None,
            "stage2_recall_of_future_explosive_result_events": len(future_stage2) / len(future) if future else None,
            "stage2_precision": len(stage2_hits) / len(stage2) if stage2 else None,
            "momentum_baseline_recall": len(future_baseline) / len(future) if future else None,
            "momentum_baseline_precision": len(baseline_hits) / len(baseline) if baseline else None,
            "median_lead_sessions_to_25pct": statistics.median(leads) if leads else None,
            "median_stage2_max_20d_return_pct": statistics.median(r["h004_trigger_outcome"]["max_20d_return_pct"] for r in stage2) if stage2 else None,
            "median_stage2_close_20d_return_pct": statistics.median(r["h004_trigger_outcome"]["close_20d_return_pct"] for r in stage2) if stage2 else None,
        },
        "by_calendar_quarter": quarters,
    }


def main() -> None:
    args = parse_args()
    event_start = date.fromisoformat(args.event_start)
    event_end = date.fromisoformat(args.event_end)
    price_start = date.fromisoformat(args.price_start)
    price_end = date.fromisoformat(args.price_end)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sessions, prices = load_prices(price_start, price_end)
    print(f"loaded sessions={len(sessions)} symbols={len(prices)}")
    client = NSEClient(timeout=20, attempts=4)
    filings = dedupe_filings(fetch_filings(client, event_start, event_end))
    print(f"deduped financial events={len(filings)}")

    records: list[dict] = []
    xbrl_attempts = xbrl_parsed = 0
    for n, filing in enumerate(filings, 1):
        symbol = str(filing.get("symbol") or "").strip().upper()
        rows = prices.get(symbol)
        if not rows:
            continue
        try:
            broadcast = parse_broadcast(str(filing["broadcast_Date"]))
        except Exception:
            continue
        decision = decision_session(sessions, broadcast)
        if not decision or decision < event_start or decision > event_end:
            continue
        idx = row_index(rows, decision)
        if idx is None:
            continue
        pre = pre_event_features(rows, idx)
        if not pre:
            continue
        if pre["median_20d_traded_value_inr"] < DISCOVERY_TURNOVER:
            continue
        pre_momentum = (
            pre["prior_5d_return_pct"] < 10.0
            and pre["prior_20d_return_pct"] < 20.0
            and pre["prior_1d_return_pct"] < 8.0
        )
        if not pre_momentum:
            continue
        reference = event_reference_outcome(rows, idx)
        if reference is None:
            continue

        baseline_idx, baseline_conditions = tape_trigger(rows, idx)
        baseline_outcome = outcome_from_entry(rows, baseline_idx + 1) if baseline_idx is not None else None

        xbrl_attempts += 1
        raw = get_bytes(str(filing["xbrl"]))
        if not raw:
            continue
        metrics = financial_metrics(raw)
        if not metrics:
            continue
        xbrl_parsed += 1
        anchor = bool(metrics["earnings_anchor"])
        hidx = None
        hconditions: list[str] = []
        houtcome = None
        if anchor:
            hidx, hconditions = tape_trigger(rows, idx)
            if hidx is not None:
                houtcome = outcome_from_entry(rows, hidx + 1)

        rec = {
            "symbol": symbol,
            "company": filing.get("cmName") or filing.get("smName"),
            "quarter_end": filing.get("qe_Date"),
            "basis": filing.get("consolidated"),
            "broadcast": filing.get("broadcast_Date"),
            "decision_date": decision.isoformat(),
            "quarter": quarter_key(decision),
            "primary_universe": pre["median_20d_traded_value_inr"] >= PRIMARY_TURNOVER,
            "median_20d_traded_value_inr": pre["median_20d_traded_value_inr"],
            "prior_1d_return_pct": pre["prior_1d_return_pct"],
            "prior_5d_return_pct": pre["prior_5d_return_pct"],
            "prior_20d_return_pct": pre["prior_20d_return_pct"],
            "earnings_anchor": anchor,
            "quality_warning_nonoperating": metrics["quality_warning_nonoperating"],
            "revenue_yoy_pct": metrics["revenue_yoy_pct"],
            "ebitda_yoy_pct": metrics["ebitda_yoy_pct"],
            "pat_yoy_pct": metrics["pat_yoy_pct"],
            "margin_change_pp": metrics["margin_change_pp"],
            "quarterly_pat_crore": metrics["quarterly_pat_crore"],
            "reference_outcome": reference,
            "baseline_trigger_date": rows[baseline_idx]["date"].isoformat() if baseline_idx is not None else None,
            "baseline_trigger_conditions": baseline_conditions,
            "baseline_trigger_outcome": baseline_outcome,
            "h004_trigger_date": rows[hidx]["date"].isoformat() if hidx is not None else None,
            "h004_trigger_conditions": hconditions,
            "h004_trigger_outcome": houtcome,
            "xbrl_url": filing.get("xbrl"),
        }
        records.append(rec)
        if n % 250 == 0:
            print(f"event progress {n}/{len(filings)} records={len(records)} xbrl={xbrl_parsed}/{xbrl_attempts}")

    primary_records = [r for r in records if r["primary_universe"]]
    discovery_records = [r for r in records if not r["primary_universe"]]
    summary = summarize(primary_records)
    summary["event_window"] = {"start": event_start.isoformat(), "end": event_end.isoformat()}
    summary["price_window"] = {"start": price_start.isoformat(), "end": price_end.isoformat()}
    summary["xbrl"] = {"attempted": xbrl_attempts, "parsed": xbrl_parsed}
    summary["discovery_event_count"] = len(discovery_records)

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out_dir / "events.json").write_text(json.dumps(primary_records, indent=2, sort_keys=True, default=str) + "\n")
    (out_dir / "discovery-events.json").write_text(json.dumps(discovery_records, indent=2, sort_keys=True, default=str) + "\n")

    headline = [
        "# H004-HR002 earnings subengine replay",
        "",
        "Status: **historical reconstruction, not out-of-sample validation**",
        "",
        "This replay uses the frozen H004 earnings thresholds, official NSE Integrated Filing XBRL publication timestamps, and official NSE UDiFF market data. It does not include corporate-catalyst-only signals, sector-relative triggers, or delivery-volume triggers.",
        "",
        "```json",
        json.dumps(summary, indent=2, sort_keys=True),
        "```",
        "",
        "The full H004 success gate remains closed unless the complete signal family and future prospective cohorts satisfy the frozen requirements.",
    ]
    (out_dir / "RESULTS.md").write_text("\n".join(headline) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
