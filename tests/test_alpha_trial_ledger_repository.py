import json
from pathlib import Path

from marketlab.alpha_trials import validate_trial_ledger


def test_repository_ae001_trial_ledger_is_hash_valid():
    root = Path(__file__).resolve().parents[1]
    path = root / "research/ae001/trial-ledger.json"
    ledger = json.loads(path.read_text(encoding="utf-8"))
    validate_trial_ledger(ledger)


def test_t007_negative_result_is_sealed_once():
    root = Path(__file__).resolve().parents[1]
    ledger = json.loads(
        (root / "research/ae001/trial-ledger.json").read_text(
            encoding="utf-8"
        )
    )
    results = [
        event
        for event in ledger["events"]
        if event["trial_id"] == "AE001-T007"
        and event["event_type"] == "TRIAL_RESULT_RECORDED"
    ]
    assert len(results) == 1
    payload = results[0]["payload"]
    assert payload["primary_1d"]["endpoint_supported"] is False
    assert payload["secondary_5d"]["endpoint_supported"] is False
    assert payload["prospective_claim_allowed"] is False
    assert payload["live_capital_allowed"] is False
