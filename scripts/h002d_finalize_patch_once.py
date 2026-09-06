from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"patch target not found in {path}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/marketlab/prospective.py",
    '''def _snapshot_payload_for_state(snapshot: ObservationSnapshot) -> dict[str, Any]:
    payload = snapshot.to_dict()
    for key in (
        "snapshot_id",
        "state_hash",
        "sequence",
        "parent_snapshot_id",
        "recorded_at_utc",
    ):
        payload.pop(key, None)
    return payload
''',
    '''def _snapshot_payload_for_state(snapshot: ObservationSnapshot) -> dict[str, Any]:
    payload = snapshot.to_dict()
    for key in (
        "snapshot_id",
        "state_hash",
        "sequence",
        "parent_snapshot_id",
        "recorded_at_utc",
    ):
        payload.pop(key, None)
    position = payload.get("paper_position")
    if isinstance(position, dict):
        # evaluation_as_of_utc records when a poll reconstructed the position. It is
        # not an economic state transition and must not create ledger churn.
        position = dict(position)
        position.pop("evaluation_as_of_utc", None)
        payload["paper_position"] = position
    return payload
''',
)

replace_once(
    "src/marketlab/runner.py",
    '''                base_evidence["exit_corporate_action_artifact"] = exit_action_artifact.to_dict()
                base_evidence["exit_price_basis"] = asdict(exit_basis)
                if exit_basis.status != "READY" or exit_basis.version is None:
                    return self._append_price_basis_unresolved(
                        member,
                        as_of=as_of,
                        event=event,
                        record_id=record.record_id,
                        signal=signal,
                        evidence=base_evidence,
                        reason="exit_price_basis_unresolved",
                    )
                stock_bars.append(
''',
    '''                base_evidence["exit_corporate_action_artifact"] = exit_action_artifact.to_dict()
                base_evidence["exit_price_basis"] = asdict(exit_basis)
                if exit_basis.status != "READY" or exit_basis.version is None:
                    return self._append_price_basis_unresolved(
                        member,
                        as_of=as_of,
                        event=event,
                        record_id=record.record_id,
                        signal=signal,
                        evidence=base_evidence,
                        reason="exit_price_basis_unresolved",
                    )
                entry_basis_payload = base_evidence.get("entry_price_basis")
                entry_basis_version = (
                    entry_basis_payload.get("version")
                    if isinstance(entry_basis_payload, dict)
                    else None
                )
                if entry_basis_version != exit_basis.version:
                    return self._append_price_basis_unresolved(
                        member,
                        as_of=as_of,
                        event=event,
                        record_id=record.record_id,
                        signal=signal,
                        evidence=base_evidence,
                        reason="holding_period_price_basis_changed",
                    )
                stock_bars.append(
''',
)

prospective_tests = Path("tests/test_prospective.py")
prospective_tests.write_text(
    prospective_tests.read_text(encoding="utf-8")
    + '''\n\ndef test_observation_state_dedup_ignores_evaluation_poll_time(tmp_path):
    from datetime import UTC, datetime

    from marketlab.prospective import ObservationStore

    store = ObservationStore(tmp_path)
    base = {
        "schema_version": 3,
        "execution_rule_id": "H002-X001",
        "signal_rule_id": "H002-R001",
        "hypothesis_id": "H002",
        "position_id": "p1",
        "event_id": "e1",
        "event_version_id": "ev1",
        "expectation_id": "x1",
        "symbol": "TEST",
        "signal_bucket": "POSITIVE",
        "signal_ue": 0.01,
        "decision_timestamp_utc": "2026-10-01T10:00:00Z",
        "exchange_published_at_utc": "2026-10-01T09:00:00Z",
        "evaluation_as_of_utc": "2026-10-01T11:00:00Z",
        "calendar_version": "c1",
        "calendar_snapshot_sha256": "a" * 64,
        "reference_session_date": "2026-09-29",
        "entry_session_date": "2026-10-05",
        "exit_session_date": "2026-11-02",
        "status": "PENDING",
        "skip_or_pending_reason": "entry_not_due",
        "entry_price": None,
        "exit_price": None,
        "entry_price_source": None,
        "exit_price_source": None,
        "entry_price_source_timestamp_utc": None,
        "exit_price_source_timestamp_utc": None,
        "entry_corporate_action_version": None,
        "exit_corporate_action_version": None,
        "gross_return_pct": None,
        "cost_stressed_return_pct": None,
        "benchmarks": [],
        "sector_benchmark_id": None,
        "sector_benchmark_mapping_version": None,
        "sector_benchmark_mapping_sha256": None,
        "sector_benchmark_assigned_at_utc": None,
        "live_order_created": False,
    }
    first, created1 = store.append(
        cohort_id="C",
        symbol="TEST",
        target_period_end="2026-09-30",
        recorded_at=datetime(2026, 10, 1, 11, tzinfo=UTC),
        state="PENDING",
        paper_position=base,
    )
    changed_poll = dict(base)
    changed_poll["evaluation_as_of_utc"] = "2026-10-01T14:00:00Z"
    second, created2 = store.append(
        cohort_id="C",
        symbol="TEST",
        target_period_end="2026-09-30",
        recorded_at=datetime(2026, 10, 1, 14, tzinfo=UTC),
        state="PENDING",
        paper_position=changed_poll,
    )
    assert created1 is True
    assert created2 is False
    assert second.snapshot_id == first.snapshot_id
''',
    encoding="utf-8",
)

runner_tests = Path("tests/test_runner.py")
runner_tests.write_text(
    runner_tests.read_text(encoding="utf-8")
    + '''\n\ndef test_price_basis_version_changes_when_holding_period_share_basis_changes():
    from datetime import date

    from marketlab.marketdata import audit_price_basis_actions

    entry = audit_price_basis_actions(
        [], raw_payload=b"[]", symbol="TEST",
        start_date=date(2026, 10, 1), end_date=date(2026, 10, 5),
    )
    exit_basis = audit_price_basis_actions(
        [{"symbol": "TEST", "subject": "Bonus 1:1", "exDate": "20-Oct-2026"}],
        raw_payload=b"bonus", symbol="TEST",
        start_date=date(2026, 10, 1), end_date=date(2026, 11, 2),
    )
    assert entry.status == "READY" and exit_basis.status == "READY"
    assert entry.version != exit_basis.version
''',
    encoding="utf-8",
)
