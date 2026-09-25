"""Shared paths and read-only verification for this one code-only release."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import urllib.request

RECEIPT = Path('/opt/demo-studio-backups/20260925-runtime-gallery')
RELEASE = Path('/opt/demo-studio-releases/20260925-runtime-gallery')
OLD = Path('/opt/demo-studio-releases/20260925-bmw-gallery')
RUNTIME = Path('/opt/demo-studio-releases/20260923-creta-v8')
PYTHON = RUNTIME / '.venv/bin/python'
DATA = Path('/opt/demo-studio/data')
ENV = Path('/opt/demo-studio/.env')
CONF = Path('/etc/systemd/system/demo-studio.service.d/zz-release-20260925-runtime-gallery.conf')
CADDY = Path('/etc/caddy/Caddyfile')
AUTH = Path('/etc/caddy/demo-studio-admin.auth')
SQLITE = {'graph.sqlite', 'graph.sqlite-wal', 'graph.sqlite-shm'}
PROTECTED = 'demos/dm_41513908/'

def run(*args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, text=True, capture_output=True, **kwargs)

def state(key):
    return run('systemctl', 'show', 'demo-studio', '-p', key, '--value').stdout.strip()

def privileged_exists(path):
    result = subprocess.run(['sudo', 'test', '-e', str(path)], capture_output=True)
    assert result.returncode in (0, 1)
    return result.returncode == 0

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def save(name, value):
    path = RECEIPT / name
    path.write_text(json.dumps(value, indent=2) + '\n')
    path.chmod(0o600)

def package():
    value = json.loads((RECEIPT / 'package.json').read_text())
    assert re.fullmatch(r'[0-9a-f]{40}', value['commit'])
    assert set(value['archives']) == {'source.tar.gz'}
    return value

def source_manifest():
    value = json.loads((RECEIPT / 'source-manifest.json').read_text())
    assert value and all(isinstance(p, str) and isinstance(h, str) for p, h in value.items())
    for path, digest in value.items():
        parts = Path(path).parts
        assert parts and not path.startswith('/') and '..' not in parts and '\\' not in path
        assert parts[0] not in {'.git', 'data', 'output', '.venv'} and '.env' not in parts
        assert re.fullmatch(r'[0-9a-f]{64}', digest)
    return value

def verify_source():
    manifest = source_manifest()
    assert all((RELEASE / p).is_file() and not (RELEASE / p).is_symlink() and sha(RELEASE / p) == h
               for p, h in manifest.items()), 'Release source changed'
    assert (RELEASE / 'SOURCE_COMMIT').read_text().strip() == package()['commit']
    return len(manifest)

def data_manifest():
    # Read hashes only. The protected demo is never opened through an application API.
    return {str(path.relative_to(DATA)): sha(path)
            for path in sorted(DATA.rglob('*')) if path.is_file()}

def selected_health(value):
    return {key: value.get(key) for key in ('mock', 'model_tier', 'tts_provider', 'stt_provider', 'runtime_providers')}

def operational_metadata():
    rows = []
    for path in (DATA / 'demos').glob('dm_*/demo.json'):
        if path.parent.name == 'dm_41513908':
            continue
        demo = json.loads(path.read_text())
        active = bool(demo.get('running')) or any(
            stage.get('status') == 'running' for stage in demo.get('stages', {}).values()
            if isinstance(stage, dict))
        # The API adds graph.is_running(), covering an active worker before its
        # next persisted stage marker. Never call the protected demo's API.
        with urllib.request.urlopen('http://127.0.0.1:8877/api/demos/' + path.parent.name, timeout=15) as response:
            worker_active = bool(json.load(response).get('running'))
        rows.append({'id': path.parent.name, 'active': active or worker_active})
    return rows
