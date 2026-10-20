"""Exclusive, fsynced evidence and append-only accounting; never a budget issuer."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
import zipfile

from finocr_answer.contract import canonical, digest, strict_json
from finocr_answer.setup import sha

CASES = ('signed', 'scale', 'margin', 'comparison', 'missing', 'capacity')


def sync_directory(directory: Path) -> None:
    # Windows cannot open directories this way. Files are fsynced on both OSes;
    # exclusive persistent anchors still block reuse after an interrupted write.
    if os.name != 'nt':
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def write_bytes(path: Path, data: bytes) -> None:
    with path.open('xb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    sync_directory(path.parent)


def write_json(path: Path, value) -> None:
    write_bytes(path, canonical(value) + b'\n')


def snapshot(paths) -> dict:
    result = {}
    for original in paths:
        raw = Path(original)
        if raw.is_symlink() or getattr(raw, 'is_junction', lambda: False)():
            raise ValueError('Preservation root must not be a symbolic link')
        p = raw.resolve(strict=True)
        if p.is_dir():
            entries = {}
            for q in sorted(p.rglob('*')):
                if q.is_symlink() or getattr(q, 'is_junction', lambda: False)():
                    raise ValueError('Symbolic links are not a preservation inventory')
                if q.is_file():
                    entries[q.relative_to(p).as_posix()] = sha(q)
            result[str(p)] = {'kind': 'tree', 'files': entries}
        else:
            result[str(p)] = {'kind': 'file', 'sha256': sha(p)}
    return result


def assert_preserved(expected: dict) -> dict:
    actual = snapshot(expected)
    if actual != expected:
        raise ValueError('Preservation mismatch, including added/deleted files')
    return actual


class Journal:
    """One immutable file/event, hash chained. No open-existing/resume API."""
    def __init__(self, root: Path, binding: dict):
        # The parent must already exist. Never create arbitrary ancestor paths.
        root.mkdir()
        sync_directory(root.parent)
        self.root = root
        self.events = root / 'events'
        self.events.mkdir()
        sync_directory(root)
        self.index, self.previous, self.attempted, self.closed = 0, None, 0, False
        self.pending = None
        self._append('claimed', {'binding': binding})

    def _append(self, kind: str, payload: dict) -> dict:
        event = {'sequence': self.index, 'previous_sha256': self.previous,
                 'time_ns': time.time_ns(), 'kind': kind, **payload}
        path = self.events / f'{self.index:04d}-{kind}.json'
        # Poison the instance before disk I/O. A failed/torn write is not retryable.
        self.closed = True
        write_json(path, event)
        self.index += 1
        self.previous = sha(path)
        self.closed = kind == 'terminal'
        return event

    def charge(self, case_id: str, request_sha256: str) -> dict:
        if self.closed or self.pending is not None or self.attempted >= len(CASES) or case_id != CASES[self.attempted]:
            raise ValueError('Terminal, duplicate, out-of-order or exhausted campaign')
        self.attempted += 1  # conservatively spent even if the fsync fails
        self.pending = case_id
        return self._append('attempt_started', {'case_id': case_id,
            'attempt': self.attempted, 'request_sha256': request_sha256})

    def finish(self, case_id: str, outcome: dict) -> None:
        if self.closed or case_id != self.pending:
            raise ValueError('No matching live attempt')
        self._append('attempt_finished', {'case_id': case_id, 'outcome': outcome})
        self.pending = None

    def close(self, reason: str) -> None:
        if self.closed:
            raise ValueError('Journal cannot be reopened or rewritten')
        self._append('terminal', {'reason': reason, 'attempted': self.attempted,
                                 'unattempted': list(CASES[self.attempted:])})


def inspect_journal(root: Path) -> dict:
    """Read-only conservative recovery summary; never resumes an interrupted run."""
    previous, attempts, finished = None, [], []
    events = sorted((root / 'events').glob('*.json'))
    complete = False
    for index, path in enumerate(events):
        value = strict_json(path.read_text(encoding='utf-8'))
        if value['sequence'] != index or value['previous_sha256'] != previous or complete:
            raise ValueError('Damaged or extended terminal journal')
        previous = sha(path)
        if value['kind'] == 'attempt_started':
            if len(attempts) >= 6 or value['case_id'] != CASES[len(attempts)]:
                raise ValueError('Invalid attempt order/count')
            attempts.append(value['case_id'])
        elif value['kind'] == 'attempt_finished':
            if not attempts or value['case_id'] != attempts[-1] or value['case_id'] in finished:
                raise ValueError('Duplicate/unmatched result')
            finished.append(value['case_id'])
        elif value['kind'] == 'terminal':
            complete = True
        elif value['kind'] != 'claimed' or index:
            raise ValueError('Unknown journal transition')
    return {'attempted': len(attempts), 'finished': len(finished),
            'uncertain_cases': [c for c in attempts if c not in finished],
            'unattempted': list(CASES[len(attempts):]), 'terminal_recorded': complete,
            'restart_permitted': False, 'existing_anchor_consumed': root.exists()}


def export_evidence(root: Path, archive: Path) -> dict:
    """Export any completed/interrupted campaign, including manual-review additions.

    No inference, ticket or journal creation. Never mutates the source evidence.
    """
    root, archive = root.resolve(strict=True), archive.resolve()
    if root in archive.parents or archive == root or archive.exists() or archive.with_name(archive.name + '.sha256.json').exists():
        raise ValueError('Use a new archive outside the evidence tree')
    inventory = snapshot([root])[str(root)]['files']
    if '_EXPORT_MANIFEST.json' in inventory:
        raise ValueError('Reserved export manifest name already exists')
    manifest = {'kind': 'evidence_export_not_authorization', 'files': inventory,
                'source_root': str(root), 'inference_executed_by_export': 0}
    with archive.open('xb') as raw:
        with zipfile.ZipFile(raw, 'w', zipfile.ZIP_DEFLATED) as bundle:
            for name in sorted(inventory):
                bundle.write(root / name, name)
            bundle.writestr('_EXPORT_MANIFEST.json', canonical(manifest))
        raw.flush()
        os.fsync(raw.fileno())
    # Detect source mutation during export, then verify every archived file.
    assert_preserved({str(root): {'kind': 'tree', 'files': inventory}})
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise ValueError('Archive CRC verification failed; preserve failed archive')
        for name, expected in inventory.items():
            if hashlib.sha256(bundle.read(name)).hexdigest() != expected:
                raise ValueError('Archive content changed; preserve failed archive')
    result = {'archive': str(archive), 'sha256': sha(archive),
              'files': len(inventory), 'verified': True, 'inference_executed_by_export': 0}
    write_json(archive.with_name(archive.name + '.sha256.json'), result)
    return result
