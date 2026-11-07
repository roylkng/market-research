from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest
import yaml

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_checkpoint import checkpoint, restore
from marketlab.company_change_report_archive import (
    archive_reports,
    main,
    restore_reports,
    verify_part,
)
from marketlab.company_change_store import EvidenceStore


def populated(tmp_path):
    root = tmp_path / 'workspace'
    with EvidenceStore(root) as store:
        capture = store.capture(b'original exchange bytes', {'url': 'https://issuer.test/source'})
    (root / 'reports/context').mkdir(parents=True)
    (root / 'reports/run.json').write_text('{"research":true}\n')
    (root / 'reports/context/first.html').write_text('<html>Original report</html>')
    return root, capture


def test_lossless_archive_preserves_sources_database_and_report_bytes(tmp_path):
    root, capture = populated(tmp_path)
    db_before = (root / 'evidence.sqlite3').read_bytes()
    originals = {p.relative_to(root).as_posix(): p.read_bytes() for p in (root / 'reports').rglob('*') if p.is_file()}
    history = tmp_path / 'history'
    receipt = archive_reports(root, history)
    assert receipt['archived_reports'] == 2
    assert receipt['source_blobs_moved'] == 0
    assert receipt['database_modified'] is False
    assert (root / 'evidence.sqlite3').read_bytes() == db_before
    assert not list((root / 'reports').rglob('*.json'))
    with EvidenceStore(root) as store:
        assert store.read_blob(capture['raw_sha256']) == b'original exchange bytes'
    receipt_path = history / (receipt['receipt_sha256'] + '.json')
    restored = tmp_path / 'restored-reports'
    assert restore_reports(receipt_path, restored)['restored_reports'] == 2
    assert {p.relative_to(restored).as_posix(): p.read_bytes() for p in restored.rglob('*') if p.is_file()} == originals
    assert archive_reports(root, history)['archived_reports'] == 0


def test_same_report_replay_is_content_addressed_not_overwrite(tmp_path):
    root, _ = populated(tmp_path)
    original = (root / 'reports/run.json').read_bytes()
    history = tmp_path / 'history'
    first = archive_reports(root, history)
    paths = {p.name: p.read_bytes() for p in history.iterdir()}
    (root / 'reports/run.json').write_bytes(original)
    second = archive_reports(root, history)
    assert second['archived_reports'] == 1
    assert all((history / name).read_bytes() == raw for name, raw in paths.items())
    assert first['receipt_sha256'] != second['receipt_sha256']


def test_corrupt_archive_prevents_removing_recreated_source(tmp_path):
    root, _ = populated(tmp_path)
    history = tmp_path / 'history'
    originals = {p.relative_to(root): p.read_bytes() for p in (root / 'reports').rglob('*') if p.is_file()}
    receipt = archive_reports(root, history)
    (history / receipt['parts'][0]['filename']).write_bytes(b'corrupt')
    for name, raw in originals.items():
        (root / name).write_bytes(raw)
    with pytest.raises(ChangeError, match='hash'):
        archive_reports(root, history)
    assert all((root / name).read_bytes() == raw for name, raw in originals.items())


def test_verified_parts_split_without_raising_original_checkpoint_limit(tmp_path, monkeypatch):
    import marketlab.company_change_report_archive as module
    root, _ = populated(tmp_path)
    monkeypatch.setattr(module, 'MAX_PART_BYTES', 30)
    receipt = archive_reports(root, tmp_path / 'history')
    assert len(receipt['parts']) == 2
    for part in receipt['parts']:
        assert verify_part(tmp_path / 'history' / part['filename'], part['sha256'])['expanded_bytes'] <= 30


def test_archiving_reports_unblocks_checkpoint_without_touching_raw_evidence(tmp_path, monkeypatch):
    import marketlab.company_change_checkpoint as ck
    root, capture = populated(tmp_path)
    # Make derived history exceed a controlled test cap. Source+DB alone fits.
    (root / 'reports/large.json').write_text(' ' * 50000)
    base_size = (root / 'evidence.sqlite3').stat().st_size + len(b'original exchange bytes')
    monkeypatch.setattr(ck, 'MAX_EXPANDED', base_size + 100)
    with pytest.raises(ChangeError, match='storage limit'):
        checkpoint(root, tmp_path / 'before.zip')
    archive_reports(root, tmp_path / 'history')
    receipt = checkpoint(root, tmp_path / 'after.zip')
    assert receipt['expanded_bytes'] <= ck.MAX_EXPANDED
    restore(tmp_path / 'after.zip', tmp_path / 'restored')
    with EvidenceStore(tmp_path / 'restored') as store:
        assert store.get_capture(capture['id'])['raw_sha256'] == capture['raw_sha256']
        assert store.read_blob(capture['raw_sha256']) == b'original exchange bytes'


def test_report_history_budget_is_not_an_unbounded_escape(tmp_path, monkeypatch):
    import marketlab.company_change_report_archive as module
    root, _ = populated(tmp_path)
    monkeypatch.setattr(module, 'MAX_HISTORY_BYTES', 1)
    with pytest.raises(ChangeError, match='storage limit'):
        archive_reports(root, tmp_path / 'history')
    assert (root / 'reports/run.json').exists()


@pytest.mark.parametrize('fault', ['symlink', 'unknown-file', 'source-directory'])
def test_only_generated_reports_are_moved(tmp_path, fault):
    root, _ = populated(tmp_path)
    if fault == 'symlink':
        (root / 'reports/link.json').symlink_to(root / 'evidence.sqlite3')
    elif fault == 'unknown-file':
        (root / 'reports/data.sqlite3').write_bytes(b'not a report')
    else:
        (root / 'reports').rename(root / 'old-reports')
        (root / 'reports').symlink_to(root / 'old-reports')
    with pytest.raises(ChangeError):
        archive_reports(root, tmp_path / 'history')
    assert (root / 'evidence.sqlite3').exists()


def test_history_cannot_be_recursively_checkpointed_with_workspace(tmp_path):
    root, _ = populated(tmp_path)
    with pytest.raises(ChangeError, match='outside'):
        archive_reports(root, root / 'report-history')
    assert (root / 'reports/run.json').exists()


@pytest.mark.parametrize('filename', ['../outside.json', '/reports/x.json', 'blobs/a.json', 'reports/x.py',
                                      'reports/./x.json', 'reports//x.json'])
def test_untrusted_archive_paths_are_not_restored(tmp_path, filename):
    archive_path = tmp_path / 'malformed.zip'
    raw = b'content'
    files = {filename: {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}}
    with zipfile.ZipFile(archive_path, 'w') as archive:
        archive.writestr(filename, raw)
        archive.writestr('manifest.json', json.dumps({'format': 'CC001-GENERATED-REPORT-HISTORY-v1', 'files': files, 'expanded_bytes': len(raw)}))
    with pytest.raises(ChangeError):
        verify_part(archive_path)


def test_receipt_tamper_or_conflicting_destination_keeps_archive(tmp_path):
    root, _ = populated(tmp_path)
    history = tmp_path / 'history'
    receipt = archive_reports(root, history)
    receipt_path = history / (receipt['receipt_sha256'] + '.json')
    raw = receipt_path.read_bytes()
    receipt['expanded_bytes'] += 1
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ChangeError, match='integrity'):
        restore_reports(receipt_path, tmp_path / 'dest')
    receipt_path.write_bytes(raw)
    destination = tmp_path / 'nonempty'
    destination.mkdir()
    (destination / 'precious').write_text('keep')
    with pytest.raises(ChangeError, match='empty'):
        restore_reports(receipt_path, destination)
    assert (destination / 'precious').read_text() == 'keep'


def test_restored_hash_matches_original_and_command_interface(tmp_path, capsys):
    root, _ = populated(tmp_path)
    history = tmp_path / 'history'
    assert main(['archive', '--workspace', str(root), '--history', str(history)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt['receipt_sha256'] == canonical_hash({k: v for k, v in receipt.items() if k != 'receipt_sha256'})
    assert main(['restore', '--workspace', str(tmp_path / 'restored'), '--history', str(history / (receipt['receipt_sha256'] + '.json'))]) == 0
    assert json.loads(capsys.readouterr().out)['restored_reports'] == 2


def test_history_is_persisted_and_uncheckpointed_state_remains_recoverable():
    path = Path(__file__).resolve().parents[1] / '.github/workflows/cc001-daily-operations.yml'
    workflow = yaml.safe_load(path.read_text())
    steps = workflow['jobs']['refresh-research-workspace']['steps']
    export = next(s for s in steps if s.get('name') == 'Export research desk and checkpoint durable state')
    assert export['id'] == 'export_state'
    assert export['run'].index('company_change_report_archive archive') < export['run'].index('company_change_checkpoint save')
    assert 'add report-history' in export['run']
    assert '> "$CC_STATE/checkpoint.json.tmp"' in export['run']
    assert 'mv "$CC_STATE/checkpoint.json.tmp" "$CC_STATE/checkpoint.json"' in export['run']
    recovery = next(s for s in steps if s.get('name') == 'Preserve uncheckpointed workspace on export failure')
    assert "steps.export_state.outcome == 'failure'" in recovery['if']
    assert recovery['with']['path'].endswith('/cc001-workspace')
    persisted = next(s for s in steps if s.get('uses') == 'actions/upload-artifact@v4' and s.get('name') != recovery['name'])
    assert 'report-history' in persisted['with']['path']


def test_oversized_receipt_is_rejected_before_json_loading(tmp_path, monkeypatch):
    import marketlab.company_change_report_archive as module
    receipt = tmp_path / 'receipt.json'
    receipt.write_text('not-json' * 100)
    monkeypatch.setattr(module, 'MANIFEST_LIMIT', 10)
    with pytest.raises(ChangeError, match='receipt size'):
        restore_reports(receipt, tmp_path / 'restore')
