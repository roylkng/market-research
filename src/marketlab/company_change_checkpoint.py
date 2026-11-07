"""Bounded durable workspace checkpoint/restore for a dedicated pilot state branch."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from marketlab.company_change import ChangeError
from marketlab.company_change_store import writable_workspace

MAX_EXPANDED = 128 * 1024 * 1024
MAX_FILES = 25000
MAX_COMPRESSED = 80 * 1024 * 1024
MARKER = 'CC001-PILOT-STATE-v1'


def checkpoint(workspace: Path, destination: Path) -> dict:
    root = writable_workspace(workspace)
    if not (root / 'evidence.sqlite3').is_file():
        raise ChangeError('no workspace database to checkpoint')
    with tempfile.TemporaryDirectory() as temp:
        staged = Path(temp)
        source = sqlite3.connect(root / 'evidence.sqlite3')
        target = sqlite3.connect(staged / 'evidence.sqlite3')
        try:
            source.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ChangeError('database checkpoint integrity failure')
        finally:
            target.close()
            source.close()
        files = [('evidence.sqlite3', staged / 'evidence.sqlite3')]
        for folder in ('blobs', 'reports'):
            for path in sorted((root / folder).rglob('*')):
                if path.is_symlink():
                    raise ChangeError('workspace symlinks cannot be archived')
                if path.is_file():
                    files.append((path.relative_to(root).as_posix(), path))
        total = sum(p.stat().st_size for _, p in files)
        if len(files) > MAX_FILES or total > MAX_EXPANDED:
            raise ChangeError('pilot state storage limit reached, migrate to approved durable object storage')
        manifest = {'format': MARKER, 'expanded_bytes': total,
                    'files': {name: hashlib.sha256(p.read_bytes()).hexdigest() for name, p in files}}
        output = staged / 'checkpoint.zip'
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, path in files:
                archive.writestr(zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)), path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
            archive.writestr('manifest.json', json.dumps(manifest, sort_keys=True))
        if output.stat().st_size > MAX_COMPRESSED:
            raise ChangeError('pilot compressed state limit reached')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output, destination)
    return {'format': MARKER, 'file_count': len(files), 'expanded_bytes': total,
            'sha256': hashlib.sha256(destination.read_bytes()).hexdigest()}


def restore(archive_path: Path, workspace: Path) -> dict:
    root = writable_workspace(workspace)
    if any(root.iterdir()):
        raise ChangeError('restore requires an empty destination workspace')
    if archive_path.stat().st_size > MAX_EXPANDED:
        raise ChangeError('checkpoint compressed-size limit exceeded')
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        names = [m.filename for m in members]
        if len(names) > MAX_FILES + 1 or len(names) != len(set(names)):
            raise ChangeError('duplicate or excessive checkpoint members')
        if sum(m.file_size for m in members) > MAX_EXPANDED + 5_000_000:
            raise ChangeError('checkpoint expanded-size limit exceeded')
        for member in members:
            path = PurePosixPath(member.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in member.filename or member.is_dir():
                raise ChangeError('unsafe checkpoint path')
            if member.filename not in {'evidence.sqlite3', 'manifest.json'} and path.parts[0] not in {'blobs', 'reports'}:
                raise ChangeError('unexpected checkpoint member')
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ChangeError('checkpoint symlinks forbidden')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('format') != MARKER or set(manifest['files']) != set(names) - {'manifest.json'}:
            raise ChangeError('checkpoint manifest mismatch')
        # Validate every digest before writing any destination member.
        for name, digest in manifest['files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ChangeError('checkpoint content integrity failure')
        for name in manifest['files']:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(name))
    return {'restored_files': len(manifest['files']), 'format': MARKER}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('save', 'restore'))
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    args = parser.parse_args(argv)
    result = checkpoint(args.workspace, args.archive) if args.mode == 'save' else restore(args.archive, args.workspace)
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
