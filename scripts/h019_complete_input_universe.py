"""Materialize H019's complete outcome-blind input universe from retained sources."""

from __future__ import annotations

import argparse
import io
import json
import re
import statistics
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import run_h015_independent_challenge as h15
from acquire_h005_corpus import dump

IST = ZoneInfo("Asia/Kolkata")
DECISIONS = (
    date(2020, 12, 31),
    date(2021, 6, 30),
    date(2021, 12, 31),
    date(2022, 6, 30),
    date(2022, 12, 31),
    date(2023, 6, 30),
    date(2023, 12, 31),
)
LIQUIDITY_FLOOR = 20_000_000.0
LOOKBACK_DAYS = 45
EXPECTED_LIQUIDITY_COUNTS = (385, 504, 564, 448, 506, 572, 679)
_BHAVCOPY_NAME = re.compile(
    r"^cm(?P<day>\d{2})(?P<month>[A-Z]{3})(?P<year>\d{4})bhav\.csv$", re.IGNORECASE
)


class H019InputError(ValueError):
    """Retained H019 source material violates the pre-outcome input contract."""


def legacy_bhavcopy_source_date(raw_zip: bytes) -> date:
    """Derive the authoritative session date from the legacy NSE ZIP member name."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile as exc:
        raise H019InputError("invalid retained legacy bhavcopy ZIP") from exc
    if len(names) != 1:
        raise H019InputError("legacy bhavcopy ZIP must contain exactly one member")
    member = Path(names[0]).name
    match = _BHAVCOPY_NAME.fullmatch(member)
    if match is None:
        raise H019InputError(f"unexpected legacy bhavcopy member name: {member}")
    token = f"{match.group('day')}{match.group('month').upper()}{match.group('year')}"
    try:
        return datetime.strptime(token, "%d%b%Y").replace(tzinfo=IST).date()
    except ValueError as exc:
        raise H019InputError(f"invalid legacy bhavcopy date token: {token}") from exc


def previous_quarter(q: date) -> date | None:
    if (q.month, q.day) == (3, 31):
        return date(q.year - 1, 12, 31)
    if (q.month, q.day) == (6, 30):
        return date(q.year, 3, 31)
    if (q.month, q.day) == (9, 30):
        return date(q.year, 6, 30)
    if (q.month, q.day) == (12, 31):
        return date(q.year, 9, 30)
    return None


def _load_bank_codes(source_root: Path) -> dict[str, str]:
    bank_by_url: dict[str, set[str]] = defaultdict(set)
    for meta in json.loads((source_root / "listing-manifest.json").read_text(encoding="utf-8")):
        payload = json.loads((source_root / meta["raw_path"]).read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            continue
        for row in payload:
            if not isinstance(row, dict):
                continue
            url = str(row.get("xbrl") or "").strip()
            code = str(row.get("bank") or "").strip().upper()
            if url.lower().endswith(".xml") and code:
                bank_by_url[url].add(code)
    conflicts = {url: codes for url, codes in bank_by_url.items() if len(codes) != 1}
    if conflicts:
        raise H019InputError(f"bank taxonomy conflicts on {len(conflicts)} exact XBRL URLs")
    return {url: next(iter(codes)) for url, codes in bank_by_url.items()}


def _filing_index(source_root: Path):
    bank_by_url = _load_bank_codes(source_root)
    normalized = json.loads((source_root / "normalized-listings.json").read_text(encoding="utf-8"))
    grouped: dict[tuple[str, str], dict[date, list[dict[str, object]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    seen: set[tuple[str, str, str, str, str]] = set()
    for row in normalized:
        key = (
            str(row["symbol"]),
            str(row["basis"]),
            str(row["quarter_end"]),
            str(row["published"]),
            str(row["url"]),
        )
        if key in seen:
            continue
        seen.add(key)
        code = bank_by_url.get(str(row["url"]))
        if code is None:
            continue
        item = dict(row)
        item["bank"] = code
        grouped[(str(row["symbol"]), str(row["basis"]))][
            date.fromisoformat(str(row["quarter_end"]))
        ].append(item)
    for quarters in grouped.values():
        for rows in quarters.values():
            rows.sort(key=lambda item: (str(item["published"]), str(item["url"])))
    return grouped


def _history_for(grouped, symbol: str, basis: str, cutoff: datetime):
    quarters = grouped.get((symbol, basis), {})
    available: dict[date, dict[str, object]] = {}
    for qend, rows in quarters.items():
        eligible = [row for row in rows if datetime.fromisoformat(str(row["published"])) <= cutoff]
        if eligible:
            available[qend] = max(
                eligible,
                key=lambda item: (str(item["published"]), str(item["url"])),
            )
    if not available:
        return None
    latest = max(available)
    if (cutoff.date() - latest).days > 150:
        return None
    chain = [latest]
    for _ in range(7):
        prior = previous_quarter(chain[-1])
        if prior is None or prior not in available:
            return None
        chain.append(prior)
    chosen = [available[q] for q in reversed(chain)]
    if any(str(row["bank"]) != "N" for row in chosen):
        return None
    return chosen


def _market_bars(coverage_root: Path) -> dict[date, dict[str, dict[str, object]]]:
    bars_by_day: dict[date, dict[str, dict[str, object]]] = {}
    for raw_path in sorted((coverage_root / "raw").glob("*")):
        raw = raw_path.read_bytes()
        day = legacy_bhavcopy_source_date(raw)
        if day in bars_by_day:
            if bars_by_day[day] != h15.parse_legacy_bhavcopy(raw, day):
                raise H019InputError(f"conflicting retained bhavcopies on {day}")
            continue
        bars_by_day[day] = h15.parse_legacy_bhavcopy(raw, day)
    return bars_by_day


def materialize(source_root: Path, coverage_root: Path, output_root: Path) -> dict[str, object]:
    source_summary = json.loads(
        (source_root / "source-feasibility-summary.json").read_text(encoding="utf-8")
    )
    coverage_summary = json.loads(
        (coverage_root / "input-coverage-summary.json").read_text(encoding="utf-8")
    )
    if source_summary.get("return_outcomes_opened") is not False:
        raise H019InputError("source metadata is not outcome-blind")
    if coverage_summary.get("return_outcomes_opened") is not False:
        raise H019InputError("coverage artifact is not outcome-blind")

    grouped = _filing_index(source_root)
    symbols = sorted({symbol for symbol, _ in grouped})
    metadata: dict[date, list[dict[str, object]]] = {}
    for nominal in DECISIONS:
        cutoff = datetime.combine(nominal, dtime(20, 0), tzinfo=IST)
        rows: list[dict[str, object]] = []
        for symbol in symbols:
            consolidated = _history_for(grouped, symbol, "C", cutoff)
            standalone = _history_for(grouped, symbol, "S", cutoff)
            chosen = consolidated or standalone
            if chosen is None:
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "basis": "C" if consolidated else "S",
                    "filings": chosen,
                }
            )
        metadata[nominal] = rows

    bars_by_day = _market_bars(coverage_root)
    if len(bars_by_day) != int(coverage_summary["market_sessions_retained"]):
        raise H019InputError(
            "retained market-session count does not reproduce first coverage audit"
        )

    cohorts = []
    all_urls: set[str] = set()
    for nominal in DECISIONS:
        sessions = sorted(
            day for day in bars_by_day if nominal - timedelta(days=LOOKBACK_DAYS) <= day <= nominal
        )
        if len(sessions) < 20:
            raise H019InputError(f"fewer than 20 retained sessions near {nominal}")
        decision = sessions[-1]
        trailing = sessions[-20:]
        candidates = []
        for row in metadata[nominal]:
            turnovers = []
            isins = []
            decision_bar = None
            for day in trailing:
                bar = bars_by_day[day].get(str(row["symbol"]))
                if bar is None:
                    continue
                turnovers.append(float(bar["turnover"]))
                isins.append(str(bar["isin"]))
                if day == decision:
                    decision_bar = bar
            if decision_bar is None or len(turnovers) < 15 or len(set(isins)) != 1:
                continue
            median_turnover = statistics.median(turnovers)
            if median_turnover < LIQUIDITY_FLOOR:
                continue
            item = {
                **row,
                "decision_date": decision.isoformat(),
                "decision_close": float(decision_bar["close"]),
                "isin": str(decision_bar["isin"]),
                "liquidity_sessions": len(turnovers),
                "median_20d_traded_value": median_turnover,
            }
            candidates.append(item)
            all_urls.update(str(filing["url"]) for filing in row["filings"])
        candidates.sort(
            key=lambda item: (-float(item["median_20d_traded_value"]), str(item["symbol"]))
        )
        cohorts.append(
            {
                "nominal_decision_date": nominal.isoformat(),
                "decision_date": decision.isoformat(),
                "metadata_complete_nonfinancial": len(metadata[nominal]),
                "liquidity_eligible": len(candidates),
                "candidates": candidates,
            }
        )

    actual_counts = tuple(int(cohort["liquidity_eligible"]) for cohort in cohorts)
    if actual_counts != EXPECTED_LIQUIDITY_COUNTS:
        raise H019InputError(
            f"complete-universe census mismatch: {actual_counts} != {EXPECTED_LIQUIDITY_COUNTS}"
        )

    output_root.mkdir(parents=True, exist_ok=True)
    summary = {
        "status": "H019_COMPLETE_INPUT_UNIVERSE_ONLY",
        "return_outcomes_opened": False,
        "selection_score_frozen": False,
        "liquidity_floor_inr": LIQUIDITY_FLOOR,
        "cohort_counts": list(actual_counts),
        "minimum_liquidity_eligible": min(actual_counts),
        "maximum_liquidity_eligible": max(actual_counts),
        "unique_required_xbrl_urls": len(all_urls),
        "source_universe_truncated": False,
        "live_capital_allowed": False,
    }
    dump(output_root / "complete-input-universe-summary.json", summary)
    dump(output_root / "complete-input-candidates.json", cohorts)
    dump(output_root / "complete-required-xbrl-urls.json", sorted(all_urls))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--coverage-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    summary = materialize(Path(args.source_root), Path(args.coverage_root), Path(args.out))
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
