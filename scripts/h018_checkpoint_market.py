"""Checkpoint-safe official NSE market acquisition for frozen H018.

This module changes acquisition durability only. H018 dates, eligibility, signal,
selection, execution, comparators, random seed, friction and pass/fail gates remain
owned by the frozen H018 runner.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import pickle
import time
from datetime import date
from multiprocessing import get_context
from pathlib import Path
from typing import Any

import run_h015_independent_challenge as h15

MAX_WORKERS = 8
DAY_TIMEOUT_SECONDS = 180
ACQUISITION_PASSES = 2
CHECKPOINT_SCHEMA = 1
CNX_500_RENAME_DATE = date(2015, 11, 9)


def _parse_nifty500_h018(raw_csv: bytes, session_date: date) -> dict[str, float]:
    """Resolve the frozen Nifty 500 benchmark across its official 2015 rename."""
    try:
        return h15.parse_nifty500_source_date(raw_csv, session_date)
    except ValueError:
        if session_date >= CNX_500_RENAME_DATE:
            raise

        text = raw_csv.decode("utf-8-sig")
        rows = [
            row
            for row in csv.DictReader(io.StringIO(text))
            if " ".join(str(row.get("Index Name") or "").split()).casefold() == "cnx 500"
        ]
        if len(rows) != 1:
            raise
        row = rows[0]
        parts = str(row.get("Index Date") or "").strip().split("-")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            raise
        source_date = date(int(parts[2]), int(parts[1]), int(parts[0]))
        if source_date != session_date:
            raise
        try:
            opened = float(row["Open Index Value"])
            closed = float(row["Closing Index Value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid CNX 500 OHLC in frozen H018 source compatibility") from exc
        if not all(math.isfinite(value) and value > 0 for value in (opened, closed)):
            raise ValueError("nonpositive CNX 500 OHLC in frozen H018 source compatibility")
        return {"open": opened, "close": closed}


def _checkpoint_path(root: Path, day: date) -> Path:
    return root / "checkpoints" / f"{day.isoformat()}.json"


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _resolved_fetch(day: date) -> dict[str, Any]:
    """Mirror H015 source policy, including its serial mismatch retries."""
    b_url = h15.legacy_bhavcopy_url(day)
    i_url = h15.base.index_snapshot_url(day)
    b_raw, b_meta = h15.base.fetch_public(b_url, kind="legacy-bhavcopy", attempts=4)
    i_raw, i_meta = h15.base.fetch_public(i_url, kind="index", attempts=4)
    retries: list[dict[str, object]] = []

    if b_raw is not None and i_raw is None:
        retry_raw, retry_meta = h15.base.fetch_public(
            i_url,
            kind="index-serial-retry",
            attempts=8,
        )
        retries.append(
            {
                "side": "index",
                "initial_status": i_meta.get("status"),
                "retry_status": retry_meta.get("status"),
            }
        )
        if retry_raw is not None:
            i_raw, i_meta = retry_raw, retry_meta
        else:
            alt_url = i_url.replace(
                "https://archives.nseindia.com/",
                "https://nsearchives.nseindia.com/",
                1,
            )
            alt_raw, alt_meta = h15.base.fetch_public(
                alt_url,
                kind="index-alt-official-host",
                attempts=4,
            )
            retries.append(
                {
                    "side": "index-alt-official-host",
                    "initial_status": retry_meta.get("status"),
                    "retry_status": alt_meta.get("status"),
                }
            )
            if alt_raw is not None:
                i_raw, i_meta, i_url = alt_raw, alt_meta, alt_url
    elif b_raw is None and i_raw is not None:
        retry_raw, retry_meta = h15.base.fetch_public(
            b_url,
            kind="legacy-bhavcopy-serial-retry",
            attempts=8,
        )
        retries.append(
            {
                "side": "bhavcopy",
                "initial_status": b_meta.get("status"),
                "retry_status": retry_meta.get("status"),
            }
        )
        if retry_raw is not None:
            b_raw, b_meta = retry_raw, retry_meta

    return {
        "date": day.isoformat(),
        "bhavcopy_url": b_url,
        "bhavcopy_raw": b_raw,
        "bhavcopy_meta": b_meta,
        "index_url": i_url,
        "index_raw": i_raw,
        "index_meta": i_meta,
        "serial_retries": retries,
    }


def _worker(day: date, output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    payload: dict[str, Any] = {"ok": True, "result": _resolved_fetch(day)}
    with temporary.open("wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(temporary, path)


def _complete_checkpoint(root: Path, day: date) -> dict[str, Any] | None:
    path = _checkpoint_path(root, day)
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if document.get("schema_version") != CHECKPOINT_SCHEMA:
        return None
    if document.get("date") != day.isoformat():
        return None
    if document.get("status") not in {"COMMON_SESSION", "NO_SESSION"}:
        return None
    return document


def _retain_result(root: Path, result: dict[str, Any], diagnostics: dict[str, list]) -> bool:
    day = date.fromisoformat(str(result["date"]))
    b_raw = result.get("bhavcopy_raw")
    i_raw = result.get("index_raw")
    b_meta = result.get("bhavcopy_meta") or {}
    i_meta = result.get("index_meta") or {}
    diagnostics["serial_retries"].extend(
        {"date": day.isoformat(), **row} for row in result.get("serial_retries", [])
    )

    if b_raw is None and i_raw is None:
        if b_meta.get("status") == "HTTP_404" and i_meta.get("status") == "HTTP_404":
            _atomic_json(
                _checkpoint_path(root, day),
                {
                    "schema_version": CHECKPOINT_SCHEMA,
                    "date": day.isoformat(),
                    "status": "NO_SESSION",
                    "bhavcopy_status": b_meta.get("status"),
                    "index_status": i_meta.get("status"),
                },
            )
            return True
        diagnostics["fetch_failures"].append(
            {
                "date": day.isoformat(),
                "bhavcopy_status": b_meta.get("status"),
                "index_status": i_meta.get("status"),
            }
        )
        return False

    if b_raw is None or i_raw is None:
        retained: list[dict[str, object]] = []
        if b_raw is not None:
            retained.append(
                h15.base.retain(
                    root, b_raw, url=str(result["bhavcopy_url"]), kind="legacy-bhavcopy"
                )
            )
        if i_raw is not None:
            retained.append(
                h15.base.retain(root, i_raw, url=str(result["index_url"]), kind="index")
            )
        diagnostics["source_mismatches"].append(
            {
                "date": day.isoformat(),
                "bhavcopy_status": b_meta.get("status"),
                "index_status": i_meta.get("status"),
                "retained": retained,
            }
        )
        return False

    b_retained = h15.base.retain(
        root,
        b_raw,
        url=str(result["bhavcopy_url"]),
        kind="legacy-bhavcopy",
    )
    i_retained = h15.base.retain(root, i_raw, url=str(result["index_url"]), kind="index")
    try:
        h15.parse_legacy_bhavcopy(b_raw, day)
        _parse_nifty500_h018(i_raw, day)
    except ValueError as exc:
        diagnostics["parse_errors"].append({"date": day.isoformat(), "error": str(exc)})
        return False

    _atomic_json(
        _checkpoint_path(root, day),
        {
            "schema_version": CHECKPOINT_SCHEMA,
            "date": day.isoformat(),
            "status": "COMMON_SESSION",
            "bhavcopy": b_retained,
            "index": i_retained,
        },
    )
    return True


def _run_pass(root: Path, days: list[date], diagnostics: dict[str, list], pass_number: int) -> None:
    context = get_context("fork")
    staging = root / "fetch-results"
    staging.mkdir(parents=True, exist_ok=True)
    pending = list(days)
    running: dict[date, tuple[Any, Path, float]] = {}
    completed = 0

    def launch() -> None:
        while pending and len(running) < MAX_WORKERS:
            day = pending.pop(0)
            result_path = staging / f"{day.isoformat()}.pkl"
            result_path.unlink(missing_ok=True)
            process = context.Process(target=_worker, args=(day, str(result_path)))
            process.start()
            running[day] = (process, result_path, time.monotonic())

    launch()
    while running:
        progressed = False
        now = time.monotonic()
        for day, (process, result_path, started) in list(running.items()):
            if not process.is_alive():
                process.join(timeout=1)
                running.pop(day)
                progressed = True
                completed += 1
                if process.exitcode == 0 and result_path.is_file():
                    try:
                        with result_path.open("rb") as handle:
                            payload = pickle.load(handle)
                        if payload.get("ok") is True:
                            _retain_result(root, payload["result"], diagnostics)
                        else:
                            diagnostics["worker_errors"].append(
                                {"date": day.isoformat(), "error": payload.get("error")}
                            )
                    except (
                        OSError,
                        pickle.UnpicklingError,
                        EOFError,
                        AttributeError,
                        KeyError,
                        TypeError,
                        ValueError,
                    ) as exc:
                        diagnostics["worker_errors"].append(
                            {"date": day.isoformat(), "error": f"result decode: {exc}"}
                        )
                    finally:
                        result_path.unlink(missing_ok=True)
                else:
                    diagnostics["worker_errors"].append(
                        {"date": day.isoformat(), "error": f"worker exit {process.exitcode}"}
                    )
                if completed % 100 == 0:
                    print(
                        f"H018 checkpointed market pass {pass_number}: {completed}/{len(days)}",
                        flush=True,
                    )
            elif now - started > DAY_TIMEOUT_SECONDS:
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=5)
                running.pop(day)
                result_path.unlink(missing_ok=True)
                diagnostics["hard_timeouts"].append(
                    {"date": day.isoformat(), "pass": pass_number, "seconds": DAY_TIMEOUT_SECONDS}
                )
                progressed = True
                completed += 1
        if progressed:
            launch()
        else:
            time.sleep(0.2)


def _reconstruct(root: Path, days: list[date], diagnostics: dict[str, list]):
    prices: dict[str, dict[date, dict[str, object]]] = {}
    index: dict[date, dict[str, float]] = {}
    sessions: list[date] = []
    manifest: list[dict[str, object]] = []

    for day in days:
        checkpoint = _complete_checkpoint(root, day)
        if checkpoint is None or checkpoint["status"] == "NO_SESSION":
            continue
        b_meta = checkpoint["bhavcopy"]
        i_meta = checkpoint["index"]
        b_path = root / str(b_meta["raw_path"])
        i_path = root / str(i_meta["raw_path"])
        b_raw = b_path.read_bytes()
        i_raw = i_path.read_bytes()
        if h15.base.sha256(b_raw) != b_meta["sha256"] or h15.base.sha256(i_raw) != i_meta["sha256"]:
            raise ValueError(f"H018 checkpoint source hash mismatch on {day}")
        equities = h15.parse_legacy_bhavcopy(b_raw, day)
        nifty = _parse_nifty500_h018(i_raw, day)
        sessions.append(day)
        index[day] = nifty
        manifest.extend([b_meta, i_meta])
        for symbol, bar in equities.items():
            prices.setdefault(symbol, {})[day] = bar

    sessions = sorted(set(sessions))
    pending = [day.isoformat() for day in days if _complete_checkpoint(root, day) is None]
    diagnostics["unresolved_dates"] = pending
    h15.base.dump(root / "market-acquisition-diagnostics.json", diagnostics)
    h15.base.dump(root / "market-source-manifest.json", manifest)
    if pending:
        raise ValueError(f"H018 market acquisition incomplete on {len(pending)} calendar dates")
    if len(sessions) < 400:
        raise ValueError(f"insufficient common market sessions: {len(sessions)}")
    return sessions, prices, index, manifest, diagnostics


def acquire_market(root: Path):
    days = h15.calendar_days(h15.MARKET_START, h15.MARKET_END)
    diagnostics: dict[str, list] = {
        "serial_retries": [],
        "fetch_failures": [],
        "source_mismatches": [],
        "parse_errors": [],
        "worker_errors": [],
        "hard_timeouts": [],
        "unresolved_dates": [],
    }

    for pass_number in range(1, ACQUISITION_PASSES + 1):
        unresolved = [day for day in days if _complete_checkpoint(root, day) is None]
        if not unresolved:
            break
        print(
            f"H018 acquisition pass {pass_number}: {len(unresolved)} unresolved calendar dates",
            flush=True,
        )
        _run_pass(root, unresolved, diagnostics, pass_number)

    return _reconstruct(root, days, diagnostics)
