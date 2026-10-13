"""Prospective, testable transaction-stage forecasts from frozen HG006 histories.

Forecast *transaction milestones*, NEVER shareholder stock returns.
Original HG006 contains historical cumulative incidence estimates for
NEW stage entrants, not probabilities for months-old survivor cases.
A forecast cannot be used without exact original primary-source bytes,
public chronology and a frozen timestamp before any future resolution.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

BASELINE_ID = "HG008-P001-2026-10-13-HISTORICAL-EVENT-BASELINE-v1"
FORECAST_ID = "HG008-P001-FIRST-SEEN-TRANSACTION-FORECAST-v1"
D004_PATH = Path("research/hg006-d004-result-v1.json")
D004_GIT_BLOB = "89abf5ba79a3a6525339a6851bdcb19eb0cb508a"
P001_PATH = Path("research/hg006-p001-result-v1.json")
P001_GIT_BLOB = "2c13d5424c0f88af1bd0deeec559c60f190f464b"
EARLIEST_NEW_STAGE_UTC = datetime(2026, 10, 14, tzinfo=UTC)
MAX_FIRST_SEEN_LAG = timedelta(hours=8)
SOURCE_HOSTS = frozenset({"nsearchives.nseindia.com", "archives.nseindia.com", "www.bseindia.com"})
STAGES = frozenset({"BOARD_APPROVED", "ALLOTMENT_COMPLETED", "REGULATORY_OR_COURT_APPROVED"})
TRACKS = frozenset({"issuance_completion", "full_economic_exercise", "transaction_completion"})


def _git_sha(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _digest(obj: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    ).hexdigest()


def _utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("an explicit source/forecast UTC timestamp is required")
    try:
        instant = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid source/forecast timestamp") from exc
    if instant.tzinfo is None:
        raise ValueError("timezone-aware source/forecast timestamp required")
    return instant.astimezone(UTC)


def _number(value: object) -> float:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError("finite numeric probability required")
    return float(value)


def _read_original(root: Path, path: Path, sha: str) -> tuple[dict, dict]:
    raw = (root / path).read_bytes()
    if _git_sha(raw) != sha:
        raise ValueError(f"{path} original Git blob changed")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TypeError("source stage-base-rate packet must be JSON object")
    return value, {"path": str(path), "git_blob_sha": sha, "raw_sha256": hashlib.sha256(raw).hexdigest()}


def load_baseline_sources(root: Path) -> tuple[dict, dict, dict]:
    d004, d_receipt = _read_original(root, D004_PATH, D004_GIT_BLOB)
    p001, p_receipt = _read_original(root, P001_PATH, P001_GIT_BLOB)
    if (
        d004.get("diagnostic_id") != "HG006-D004-P1-v1"
        or d004.get("status") != "PASSED_HISTORICAL_STAGE_CONDITIONED_BASE_RATES"
        or d004.get("observation_cutoff") != "2026-09-30"
        or d004.get("feasibility_pass") is not True
        or d004.get("current_company_probabilities_assigned") is not False
        or d004.get("live_capital_allowed") is not False
    ):
        raise ValueError("frozen HG006 historical stage outcomes/source governance changed")
    if (
        p001.get("diagnostic_id") != "HG006-P001-v1"
        or p001.get("current_company_probability_surfaces_published") != 0
        or p001.get("current_evidence_cutoff") != "2026-10-04"
        or p001.get("live_capital_allowed") is not False
    ):
        raise ValueError("HG006 months-old current-company survivor block changed")
    return d004, p001, {"historical": d_receipt, "survivor": p_receipt}


def build_first_seen_baselines(d004: dict, p001: dict, receipts: dict) -> dict:
    raw = d004.get("publishable_stage_surfaces")
    if not isinstance(raw, list) or len(raw) != 4:
        raise ValueError("four original HG006 publishable stage surfaces required")
    stage_surfaces = []
    identities = set()
    for row in raw:
        if not isinstance(row, dict):
            raise TypeError("stage record must be object")
        family, track, stage = (row.get(k) for k in ("family", "track", "stage"))
        if track not in TRACKS or stage not in STAGES or not isinstance(family, str):
            raise ValueError("unrecognized historical event stage or track")
        key = (family, track, stage)
        if key in identities:
            raise ValueError("duplicate independent historical stage family")
        identities.add(key)
        support = row.get("support_count")
        terminal = row.get("terminal_count")
        if type(support) is not int or support < 30 or type(terminal) is not int or terminal < 10:
            raise ValueError("insufficient historical stage support for baseline")
        if (
            type(row.get("completed_count")) is not int
            or type(row.get("failed_count")) is not int
            or type(row.get("right_censored_count")) is not int
            or sum(row[k] for k in ("completed_count","failed_count","right_censored_count")) != support
            or row["completed_count"] + row["failed_count"] != terminal
        ):
            raise ValueError("terminal versus censor stage accounting mismatch")
        horizons = [90,180] if stage=="REGULATORY_OR_COURT_APPROVED" else [90]
        for horizon in horizons:
            metric = f"completion_cif_{horizon}d"
            bound = f"completion_ci95_{horizon}d"
            probability = _number(row.get(metric))
            ci = row.get(bound)
            if not isinstance(ci, dict):
                raise TypeError("historical 95% incidence bounds missing")
            low, high = _number(ci.get("lower")), _number(ci.get("upper"))
            if not 0 <= low <= probability <= high <= 1:
                raise ValueError("historical stage incidence/bounds inconsistent")
            stage_surfaces.append({
                "family": family, "track": track, "stage": stage,
                "horizon_days": horizon,
                "probability": probability,
                "historical_interval_95_lower": low,
                "historical_interval_95_upper": high,
                "historical_support": support,
                "historical_terminal": terminal,
                "right_censored": row["right_censored_count"],
                "prediction_target": f"{track.upper()}_WITHIN_{horizon}_DAYS_FROM_FIRST_STAGE_PUBLICATION",
                "intended_population": "FUTURE_FIRST_SEEN_STAGE_ENTRANTS_ONLY",
                "out_of_sample_forecast_calibration_confirmed": False,
                "existing_months_old_survivor_probability_allowed": False,
            })
    if len(stage_surfaces) != 5:
        raise ValueError("expected five horizon/track historical baseline curves")
    cases = p001.get("current_case_summary")
    if not isinstance(cases, list) or len(cases) != 6:
        raise ValueError("HG006 existing survivor episodes unexpectedly missing")
    existing = []
    for row in cases:
        if row.get("probability_surface") is not None:
            raise ValueError("existing survivor case cannot have published current probability")
        existing.append({
            "symbol": row["symbol"],
            "family": row["historical_family"],
            "track": row["historical_track"],
            "stage": row["current_stage"],
            "original_2026_10_04_stage_survivor_state": row["mapping_state"],
            "conditional_current_probability": None,
            "may_use_new_stage_inception_baseline_for_current_survivor": False,
        })
    result = {
        "schema_version": 1,
        "baseline_id": BASELINE_ID,
        "classification": "HISTORICAL_CIF_FOR_FUTURE_FIRST_SEEN_EVENTS_NOT_STOCK_RETURNS",
        "frozen_reference_date": "2026-10-13",
        "historical_source_cutoff": "2026-09-30",
        "source_receipts": receipts,
        "stage_baseline_count": 5,
        "stage_baselines": stage_surfaces,
        "existing_company_survivor_abstentions": existing,
        "existing_case_current_probability_count": 0,
        "new_prospective_forecast_count": 0,
        "historical_fitted_sample_is_not_out_of_sample_validation": True,
        "survivor_and_family_membership_bias_not_calibrated": True,
        "equity_return_prediction_calculated": False,
        "future_market_prices_used": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["packet_sha256"] = _digest(result)
    return result


def _official_url(url: object) -> bool:
    if not isinstance(url, str):
        return False
    try:
        p = urlsplit(url)
        return (
            p.scheme == "https"
            and p.hostname in SOURCE_HOSTS
            and p.port in (None, 443)
            and p.username is None
            and p.password is None
            and p.path.endswith(".pdf")
            and not p.fragment
        )
    except ValueError:
        return False


def freeze_new_event_forecast(
    baseline: dict[str, Any],
    *,
    event: dict[str, Any],
    original_notice_bytes: bytes,
    forecast_at_utc: str,
) -> dict[str, Any]:
    """Source-based future-event forecast. Never apply retrospectively to P001."""
    if (
        baseline.get("baseline_id") != BASELINE_ID
        or baseline.get("packet_sha256") != _digest({k:v for k,v in baseline.items() if k!="packet_sha256"})
        or baseline.get("new_prospective_forecast_count") != 0
    ):
        raise ValueError("expected exact frozen HG008 historical baseline")
    if not isinstance(event, dict):
        raise TypeError("new prospective event must be a source-verified mapping")
    symbol, isin = event.get("symbol"), event.get("isin")
    if not isinstance(symbol, str) or not symbol.isupper() or not symbol or not isinstance(isin, str) or len(isin)!=12:
        raise ValueError("new security requires exact NSE symbol/ISIN")
    episode = event.get("issuer_episode_id")
    if not isinstance(episode, str) or not episode or len(episode) > 180:
        raise ValueError("new original source episode identifier required")
    source_url = event.get("source_url")
    if not _official_url(source_url):
        raise ValueError("only original approved exchange disclosure URL allowed")
    if (
        not isinstance(original_notice_bytes, bytes)
        or len(original_notice_bytes) < 300
        or not original_notice_bytes.startswith(b"%PDF-")
        or b"%%EOF" not in original_notice_bytes[-2048:]
    ):
        raise ValueError("original exchange PDF bytes must have a valid source envelope")
    original_sha = hashlib.sha256(original_notice_bytes).hexdigest()
    if event.get("original_notice_sha256") != original_sha:
        raise ValueError("event notice SHA-256 does not match source bytes")
    if not isinstance(event.get("independent_stage_semantic_review_id"),str) or not event["independent_stage_semantic_review_id"]:
        raise ValueError("independent stage semantic review receipt required")
    published = _utc(event.get("first_stage_public_utc"))
    prepared = _utc(forecast_at_utc)
    if (
        published < EARLIEST_NEW_STAGE_UTC
        or prepared < published
        or prepared - published > MAX_FIRST_SEEN_LAG
    ):
        raise ValueError("future event stage cannot be pre-registered outside first-seen chronology")
    if event.get("completion_already_observed_at_forecast") is not False:
        raise ValueError("no already-completed event may be used for a forecast")
    if event.get("company_in_original_survivor_cases") is not False:
        raise ValueError("known surviving old HG006 episode is ineligible for first-stage baseline")
    key = tuple(event.get(x) for x in ("family","track","stage"))
    horizon = event.get("horizon_days")
    matches = [x for x in baseline["stage_baselines"] if (x["family"],x["track"],x["stage"])==key and x["horizon_days"]==horizon]
    if len(matches)!=1:
        raise ValueError("event stage is not an evidence-backed baseline family/horizon")
    chosen = matches[0]
    deadline = published + timedelta(days=horizon)
    if prepared >= deadline:
        raise ValueError("prospective forecast created after its own outcome deadline")
    result = {
        "schema_version":1,
        "forecast_id": FORECAST_ID,
        "issuer_episode_id": episode,
        "symbol":symbol,
        "isin":isin,
        "family":key[0],
        "track":key[1],
        "stage":key[2],
        "horizon_days":horizon,
        "first_stage_public_utc":published.isoformat().replace("+00:00","Z"),
        "forecast_frozen_at_utc":prepared.isoformat().replace("+00:00","Z"),
        "resolution_deadline_utc":deadline.isoformat().replace("+00:00","Z"),
        "original_source_url":source_url,
        "original_source_sha256":original_sha,
        "original_source_byte_count":len(original_notice_bytes),
        "source_stage_review_id":event["independent_stage_semantic_review_id"],
        "baseline_packet_sha256":baseline["packet_sha256"],
        "probability":chosen["probability"],
        "historical_interval_95_lower":chosen["historical_interval_95_lower"],
        "historical_interval_95_upper":chosen["historical_interval_95_upper"],
        "historical_source_event_count":chosen["historical_support"],
        "target":chosen["prediction_target"],
        "forecast_kind":"MECHANICAL_FIRST_SEEN_HISTORICAL_BASELINE_NOT_COMPANY_CALIBRATED",
        "outcome_known_or_scored":False,
        "source_complete_future_resolution_verified":False,
        "prospective_git_commit_before_outcome_verified":False,
        "stock_price_return_forecast":None,
        "live_capital_allowed":False,
        "portfolio_eligibility_allowed":False,
    }
    result["packet_sha256"] = _digest(result)
    return result
