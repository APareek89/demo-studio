#!/usr/bin/env python3
"""One reviewed CSS overlay on the 3591fb7 mobile release; no app restart or data write."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import tempfile
import time
import urllib.request

BASE_COMMIT = '3591fb7b8489a565e3aa2bfde66de22d66a21b30'
RELATIVE = 'web/player-ui.css'
BASE_DIGEST = '4b29880722c98a05292741bfecb6f8046e13483fda813c767360820ebb7eade6'
RELEASE = Path('/opt/demo-studio-releases/20260926-mobile')
BASE_RECEIPT = Path('/opt/demo-studio-backups/20260926-mobile')
PUBLIC = 'https://13-202-0-79.sslip.io/' + RELATIVE


def digest(value):
    return hashlib.sha256(value).hexdigest()


def atomic(path, content, mode=0o600, owner=None):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        if owner:
            os.chown(temporary, *owner)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def marker(release):
    path = release / 'SOURCE_COMMIT'
    assert not path.is_symlink() and path.read_text().strip() == BASE_COMMIT, 'Unexpected base source marker'


def package(commit, output):
    resolved = subprocess.check_output(['git', 'rev-parse', commit], text=True, timeout=20).strip()
    assert re.fullmatch('[0-9a-f]{40}', resolved) and resolved != BASE_COMMIT
    subprocess.run(['git', 'merge-base', '--is-ancestor', BASE_COMMIT, resolved], check=True, timeout=20)
    changed = subprocess.check_output(['git', 'diff', '--name-only', BASE_COMMIT, resolved], text=True, timeout=20).splitlines()
    allowed_docs = {'Handoff.MD', 'Loop.MD', 'Learning.MD', 'refine.MD'}
    assert RELATIVE in changed and all(path == RELATIVE or path in {'evals/mobile_gallery_contract.py', 'evals/mobile_welcome_contract.py'}
        or path.startswith('docs/') or path in allowed_docs for path in changed), 'Overlay commit changes other application source'
    old = subprocess.check_output(['git', 'show', BASE_COMMIT + ':' + RELATIVE], timeout=20)
    new = subprocess.check_output(['git', 'show', resolved + ':' + RELATIVE], timeout=20)
    assert digest(old) == BASE_DIGEST and new != old
    info = {'base_commit': BASE_COMMIT, 'new_commit': resolved, 'path': RELATIVE,
            'old_sha256': BASE_DIGEST, 'new_sha256': digest(new), 'changed_commit_paths': changed,
            'scope': 'Only web/player-ui.css is overlaid; remaining deployed source stays at base_commit.'}
    output.mkdir(mode=0o700)
    atomic(output / 'overlay.json', json_bytes(info))
    atomic(output / 'player-ui.css', new)
    return info


def inputs(package_dir):
    assert not package_dir.is_symlink() and package_dir.is_dir()
    for name in ('overlay.json', 'player-ui.css'):
        assert not (package_dir / name).is_symlink()
    info = json.loads((package_dir / 'overlay.json').read_text())
    assert info['base_commit'] == BASE_COMMIT and info['path'] == RELATIVE and info['old_sha256'] == BASE_DIGEST
    assert re.fullmatch('[0-9a-f]{40}', info['new_commit']) and info['new_commit'] != BASE_COMMIT
    assert re.fullmatch('[0-9a-f]{64}', info['new_sha256']) and info['new_sha256'] != BASE_DIGEST
    new = (package_dir / 'player-ui.css').read_bytes()
    assert digest(new) == info['new_sha256'], 'Overlay payload digest differs'
    return info, new


def current(release):
    marker(release)
    for part in (release, release / 'web', release / RELATIVE):
        assert not part.is_symlink(), 'No links in the allowlisted CSS path'
    path = release / RELATIVE
    state = path.stat()
    assert stat.S_ISREG(state.st_mode)
    return path, path.read_bytes(), (stat.S_IMODE(state.st_mode), (state.st_uid, state.st_gid))


def verify_manifest(release, manifest, overlay_digest=None):
    assert manifest and manifest[RELATIVE] == BASE_DIGEST
    for name, expected in manifest.items():
        parts = Path(name).parts
        assert parts and not name.startswith('/') and '..' not in parts
        assert re.fullmatch('[0-9a-f]{64}', expected)
        target = release / name
        assert not target.is_symlink() and target.is_file(), 'Unexpected linked or missing source file'
        wanted = overlay_digest if name == RELATIVE and overlay_digest else expected
        assert digest(target.read_bytes()) == wanted, 'Unreviewed source differs: ' + name
    return len(manifest)


def fetch_public():
    request = urllib.request.Request(PUBLIC + '?overlay_verify=' + str(time.time_ns()), headers={'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 200
        return response.read()


def verify_hash(expected, fetch=fetch_public):
    assert digest(fetch()) == expected, 'Public CSS differs from the reviewed bytes'


def rollback(release, receipt, info, fetch=fetch_public):
    """Try file restoration, metadata cleanup and public verification independently."""
    errors = []
    backup = receipt / 'player-ui.css.before'
    restored = False
    try:
        old = backup.read_bytes(); assert digest(old) == info['old_sha256'], 'Backup digest differs'
        path, value, properties = current(release)
        assert digest(value) in (info['old_sha256'], info['new_sha256']), 'Refuse to overwrite unrelated CSS'
        atomic(path, old, *properties); restored = True
    except BaseException as error: errors.append('css_restore:' + type(error).__name__)
    try:
        overlay = release / 'SOURCE_OVERLAY.json'
        if restored and overlay.exists():
            assert not overlay.is_symlink() and json.loads(overlay.read_text()) == info
            overlay.unlink()
    except BaseException as error: errors.append('overlay_cleanup:' + type(error).__name__)
    try:
        verify_hash(info['old_sha256'], fetch)
    except BaseException as error: errors.append('public_verification:' + type(error).__name__)
    result = {'restored': restored, 'errors': errors, 'base_commit': BASE_COMMIT, 'new_commit': info['new_commit']}
    atomic(receipt / ('rollback-' + str(time.time_ns()) + '.json'), json_bytes(result))
    assert restored and not errors, 'Rollback needs attention; see private receipt'
    return result


def apply(package_dir, release=RELEASE, receipt_base=BASE_RECEIPT, fetch=fetch_public):
    info, new = inputs(package_dir)
    path, old, properties = current(release)
    assert digest(old) == info['old_sha256'], 'Current CSS differs from the verified base'
    assert not (release / 'SOURCE_OVERLAY.json').exists() and not (release / 'SOURCE_OVERLAY.json').is_symlink(), 'An overlay already exists'
    # Compare the exact verified source manifest before making the one-file exception.
    manifest = json.loads((receipt_base / 'source-manifest.json').read_text())
    assert manifest[RELATIVE] == info['old_sha256']
    verify_manifest(release, manifest)
    receipt = receipt_base / ('css-overlay-' + info['new_commit'][:12])
    receipt.mkdir(mode=0o700)
    atomic(receipt / 'overlay.json', json_bytes(info))
    atomic(receipt / 'player-ui.css.before', old)
    assert digest((receipt / 'player-ui.css.before').read_bytes()) == info['old_sha256']
    try:
        atomic(path, new, *properties)
        assert digest(path.read_bytes()) == info['new_sha256']
        verify_hash(info['new_sha256'], fetch)
        atomic(release / 'SOURCE_OVERLAY.json', json_bytes(info))
        atomic(receipt / 'verified.json', json_bytes({'overlay': info, 'public_css_verified': True,
            'service_restart': False, 'data_touched': False, 'source_marker_unchanged': True}))
    except BaseException:
        # Termination during recovery must not abandon the old CSS restoration.
        previous = signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try: rollback(release, receipt, info, fetch)
        finally: signal.signal(signal.SIGTERM, previous)
        raise
    return {'receipt': str(receipt), 'new_commit': info['new_commit'], 'public_css_verified': True}


def verify(release, receipt_base, info, fetch=fetch_public):
    path, value, _ = current(release)
    assert digest(value) == info['new_sha256']
    overlay = release / 'SOURCE_OVERLAY.json'
    assert not overlay.is_symlink() and json.loads(overlay.read_text()) == info
    manifest = json.loads((receipt_base / 'source-manifest.json').read_text())
    assert manifest[RELATIVE] == info['old_sha256']
    verify_manifest(release, manifest, info['new_sha256'])
    verify_hash(info['new_sha256'], fetch)
    return {'verified_source_files': len(manifest), 'base_commit': BASE_COMMIT, 'overlay_commit': info['new_commit'], 'public_css_verified': True}


def terminate(signum, frame):
    raise SystemExit('CSS overlay interrupted')


def main():
    os.umask(0o077)
    signal.signal(signal.SIGTERM, terminate)
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    p = modes.add_parser('package'); p.add_argument('--commit', required=True); p.add_argument('--output', type=Path, required=True)
    for name in ('apply', 'verify', 'rollback'):
        p = modes.add_parser(name); p.add_argument('--package', type=Path, required=True)
    args = parser.parse_args()
    if args.mode == 'package': result = package(args.commit, args.output)
    elif args.mode == 'apply': result = apply(args.package)
    else:
        info, _ = inputs(args.package)
        if args.mode == 'verify': result = verify(RELEASE, BASE_RECEIPT, info)
        else: result = rollback(RELEASE, BASE_RECEIPT / ('css-overlay-' + info['new_commit'][:12]), info)
    print(json.dumps(result))


if __name__ == '__main__': main()
