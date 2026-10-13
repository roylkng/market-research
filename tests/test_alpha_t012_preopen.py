"""T012 registration and source-clock gates. Synthetic dates are never evidence."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_t012_preopen import (
    FIRST_FEATURE_SESSION,
    admit_t012_preopen,
    require_t012_registration,
)
from marketlab.calendar_snapshot import load_calendar_snapshot

ROOT = Path(__file__).resolve().parents[1]
CAL_PATH = ROOT / (
    "research/prospective/calendars/FY27-Q2-2026-09-06/"
    "NSE-CM-FY27Q2-v1.json"
)


def _read(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _inputs() -> dict:
    return {
        "calendar": load_calendar_snapshot(CAL_PATH),
        "sc003_ledger": _read("research/prospective/ae001-sc003/source-ledger.json"),
        "trial_ledger": _read("research/ae001/trial-ledger.json"),
        "rta_manifest": _read("research/rta001-trials-v1.json"),
        "frozen_models": _read(
            "research/prospective/ae001-t006/frozen-models-v1.json"
        ),
    }


def _resign_ledger(ledger: dict) -> None:
    ledger.pop("ledger_sha256", None)
    ledger["attempt_count"] = len(ledger["attempts"])
    ledger["ledger_sha256"] = digest(ledger)


def _future_sources() -> tuple[dict, dict]:
    """Fabricated fixtures for gates, explicitly not historical observations."""
    cash = _read("research/prospective/ae001-sc001/source-ledger.json")
    future_cash = copy.deepcopy([
        a for a in cash["attempts"] if a.get("eligible_before_cutoff") is True
    ][-1])
    future_cash.update({
        "seq": cash["attempt_count"] + 1,
        "session_date": FIRST_FEATURE_SESSION,
        "captured_at_utc": "2026-10-15T12:00:00+00:00",
        "decision_cutoff_utc": "2026-10-15T13:00:00+00:00",
    })
    future_cash.pop("attempt_sha256")
    future_cash["attempt_sha256"] = digest(future_cash)
    cash["attempts"].append(future_cash)
    _resign_ledger(cash)

    fo = _read("research/prospective/ae001-sc003/source-ledger.json")
    future_fo = copy.deepcopy([
        a for a in fo["attempts"] if a.get("ready_before_preopen_cutoff") is True
    ][-1])
    future_fo.update({
        "seq": fo["attempt_count"] + 1,
        "target_session_date": FIRST_FEATURE_SESSION,
        "observation_date": FIRST_FEATURE_SESSION,
        "captured_at_utc": "2026-10-15T13:30:00+00:00",
        "cutoff_session_date": "2026-10-16",
        "preopen_cutoff_utc": "2026-10-16T03:00:00+00:00",
        "target_close_timestamp_utc": "2026-10-15T10:00:00Z",
        "sc001_attempt_sha256": future_cash["attempt_sha256"],
    })
    future_fo.pop("attempt_sha256")
    future_fo["attempt_sha256"] = digest(future_fo)
    fo["attempts"].append(future_fo)
    _resign_ledger(fo)
    return cash, fo


def test_registration_matches_original_sealed_ready_sources() -> None:
    args = _inputs()
    registration = require_t012_registration(**args)
    assert registration["trial_id"] == "AE001-T012"
    assert registration["payload"]["earliest_feature_session"] == FIRST_FEATURE_SESSION
    assert args["frozen_models"]["live_capital_allowed"] is False


def test_registration_rejects_model_drift() -> None:
    args = _inputs()
    args["frozen_models"]["base_model"]["coefficients"][0] += 0.5
    with pytest.raises(AlphaContractError, match="model artifact hash mismatch"):
        require_t012_registration(**args)


def test_registration_rejects_source_gate_alteration() -> None:
    args = _inputs()
    args["sc003_ledger"]["attempts"][1]["raw_sha256"] = "x" * 64
    with pytest.raises(AlphaContractError, match="hash mismatch"):
        require_t012_registration(**args)


def test_preopen_admission_requires_future_target_and_exact_linkage() -> None:
    args = _inputs()
    cash, fo = _future_sources()
    args["sc003_ledger"] = fo
    admission = admit_t012_preopen(
        feature_session=FIRST_FEATURE_SESSION,
        sealed_at_utc="2026-10-16T02:55:00+00:00",
        sc001_ledger=cash,
        **args,
    )
    assert admission["entry_session"] == "2026-10-16"
    assert admission["outcomes_attached"] is False
    assert admission["live_capital_allowed"] is False

    with pytest.raises(AlphaContractError, match="pre-open decision missed"):
        admit_t012_preopen(
            feature_session=FIRST_FEATURE_SESSION,
            sealed_at_utc="2026-10-16T03:00:01+00:00",
            sc001_ledger=cash,
            **args,
        )

    with pytest.raises(AlphaContractError, match="prospective start"):
        admit_t012_preopen(
            feature_session="2026-10-12",
            sealed_at_utc="2026-10-13T02:55:00+00:00",
            sc001_ledger=cash,
            **args,
        )

    wrong = copy.deepcopy(cash)
    row = wrong["attempts"][-1]
    row.pop("attempt_sha256")
    row["captured_at_utc"] = "2026-10-15T12:01:00+00:00"
    row["attempt_sha256"] = digest(row)
    _resign_ledger(wrong)
    with pytest.raises(AlphaContractError, match="linked timely"):
        admit_t012_preopen(
            feature_session=FIRST_FEATURE_SESSION,
            sealed_at_utc="2026-10-16T02:55:00+00:00",
            sc001_ledger=wrong,
            **args,
        )


def test_future_futures_raw_missing_fails_closed() -> None:
    args = _inputs()
    cash, fo = _future_sources()
    row = fo["attempts"][-1]
    row.pop("attempt_sha256")
    row["raw_sha256"] = None
    row["attempt_sha256"] = digest(row)
    _resign_ledger(fo)
    args["sc003_ledger"] = fo
    with pytest.raises(AlphaContractError, match="official futures bytes absent"):
        admit_t012_preopen(
            feature_session=FIRST_FEATURE_SESSION,
            sealed_at_utc="2026-10-16T02:55:00+00:00",
            sc001_ledger=cash,
            **args,
        )


def test_t012_rejects_rewritten_failed_source_probe_even_with_valid_new_hashes() -> None:
    args = _inputs()
    ledger = args["sc003_ledger"]
    failure = ledger["attempts"][0]
    assert failure["ready_before_preopen_cutoff"] is False
    failure.pop("attempt_sha256")
    failure["source_url"] = "https://example.invalid/revised-old-probe"
    failure["attempt_sha256"] = digest(failure)
    _resign_ledger(ledger)
    with pytest.raises(AlphaContractError, match="sealed SC003 evidence prefix changed"):
        require_t012_registration(**args)
