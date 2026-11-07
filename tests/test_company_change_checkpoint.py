from __future__ import annotations

import zipfile

import pytest

from marketlab.company_change import ChangeError
from marketlab.company_change_checkpoint import checkpoint, restore
from marketlab.company_change_store import EvidenceStore


def test_checkpoint_restores_actual_bytes_and_database(tmp_path):
    with EvidenceStore(tmp_path / 'old') as store:
        cap = store.capture(b'original response', {'url': 'https://example.test/source'})
        blob = cap['raw_sha256']
    archive = tmp_path / 'state.zip'
    info = checkpoint(tmp_path / 'old', archive)
    assert info['file_count'] == 2
    restore(archive, tmp_path / 'new')
    with EvidenceStore(tmp_path / 'new') as store:
        assert store.get_capture(cap['id'])['raw_sha256'] == blob
        assert store.read_blob(blob) == b'original response'


def test_restore_never_overwrites_existing_workspace(tmp_path):
    root = tmp_path / 'existing'
    root.mkdir()
    (root / 'precious').write_text('keep')
    with pytest.raises(ChangeError, match='empty'):
        restore(tmp_path / 'none.zip', root)
    assert (root / 'precious').read_text() == 'keep'


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'blobs/../../bad', 'code.py'])
def test_archive_path_escape_and_unknown_files_rejected(tmp_path, name):
    archive = tmp_path / 'bad.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr(name, b'x')
    with pytest.raises(ChangeError):
        restore(archive, tmp_path / 'dest')


def test_workspace_symlinks_not_checkpointed(tmp_path):
    root = tmp_path / 'w'
    with EvidenceStore(root):
        pass
    (root / 'blobs').mkdir()
    (root / 'blobs' / 'link').symlink_to('/etc/passwd')
    with pytest.raises(ChangeError, match='symlink'):
        checkpoint(root, tmp_path / 'bad.zip')
