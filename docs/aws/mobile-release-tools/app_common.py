"""Shared paths and read-only verification for this one code-only release."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import time
import tarfile
import urllib.request

RECEIPT = Path('/opt/demo-studio-backups/20260926-mobile')
RELEASE = Path('/opt/demo-studio-releases/20260926-mobile')
OLD = Path('/opt/demo-studio-releases/20260925-livekit')
RUNTIME = Path('/opt/demo-studio-releases/20260923-creta-v8')
PYTHON = OLD / '.venv/bin/python'
LIVEKIT_ENV = Path('/etc/demo-livekit/runtime.env')
DATA = Path('/opt/demo-studio/data')
ENV = Path('/opt/demo-studio/.env')
CONF = Path('/etc/systemd/system/demo-studio.service.d/zzzz-release-20260926-mobile.conf')
CADDY = Path('/etc/caddy/Caddyfile')
AUTH = Path('/etc/caddy/demo-studio-admin.auth')
SQLITE = {'graph.sqlite', 'graph.sqlite-wal', 'graph.sqlite-shm'}
PROTECTED = 'demos/dm_41513908/'

def run(*args, **kwargs):
    if kwargs.get('timeout') is None:
        kwargs['timeout'] = 120
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
    assert not path.exists(), 'Never overwrite an earlier release receipt: ' + name
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
    # Account for every source file, while allowing only Python bytecode and the
    # explicitly separate installed runtime/shared-data links.
    seen = set()
    for root, dirs, files in os.walk(RELEASE, followlinks=False):
        here = Path(root)
        for name in list(dirs):
            path = here / name
            rel = str(path.relative_to(RELEASE))
            if rel == '.venv':
                raise AssertionError('Mobile source must reuse the external verified runtime')
            elif rel == 'data':
                assert path.is_symlink() and path.resolve() == DATA.resolve()
                dirs.remove(name)
            elif name == '__pycache__':
                assert not path.is_symlink()
                assert all(p.is_file() and not p.is_symlink() and p.suffix == '.pyc' for p in path.iterdir())
                dirs.remove(name)
            else:
                assert not path.is_symlink(), 'Unexpected source directory link'
        for name in files:
            path = here / name
            rel = str(path.relative_to(RELEASE))
            if rel == '.env':
                assert path.is_symlink() and path.resolve() == ENV.resolve()
            elif rel == 'SOURCE_COMMIT':
                assert not path.is_symlink()
            else:
                assert rel in manifest and not path.is_symlink(), 'Unmanifested release file: ' + rel
                seen.add(rel)
    assert seen == set(manifest), 'Release file inventory differs from manifest'
    return len(manifest)

def data_manifest():
    # Read hashes only. The protected demo is never opened through an application API.
    return {str(path.relative_to(DATA)): sha(path)
            for path in sorted(DATA.rglob('*')) if path.is_file()}

def verify_backup(archive,expected):
    """Verify every backed-up byte against the stopped-service manifest."""
    found={}
    with tarfile.open(archive,'r:gz') as bundle:
        for entry in bundle:
            parts=Path(entry.name).parts
            assert parts and parts[0]=='data' and '..' not in parts and not entry.name.startswith('/')
            assert entry.isdir() or entry.isfile(), 'No links or special files in customer-data backup'
            if entry.isfile():
                relative=str(Path(*parts[1:]));assert relative in expected and relative not in found
                stream=bundle.extractfile(entry);digest=hashlib.sha256()
                for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
                found[relative]=digest.hexdigest()
    assert found==expected, 'Backup bytes differ from stopped-service customer data'
    return len(found)

def active_rtc_rooms():
    # A local read-only RoomService request. Only counts leave the privileged
    # subprocess; its signing credential and room names are never printed.
    script='''from pathlib import Path
import json,urllib.request
from livekit import api
values=dict(line.split('=',1) for line in Path('/etc/demo-livekit/runtime.env').read_text().splitlines() if '=' in line)
token=api.AccessToken(values['LIVEKIT_API_KEY'],values['LIVEKIT_API_SECRET']).with_grants(api.VideoGrants(room_list=True)).to_jwt()
request=urllib.request.Request('http://127.0.0.1:7880/twirp/livekit.RoomService/ListRooms',data=b'{}',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=8) as response: rooms=json.load(response).get('rooms',[])
print(json.dumps({'rooms_with_participants':sum(int(r.get('numParticipants',r.get('num_participants',0)))>0 for r in rooms),'participants':sum(int(r.get('numParticipants',r.get('num_participants',0))) for r in rooms)}))
'''
    result=json.loads(run('sudo',PYTHON,'-c',script,timeout=15).stdout)
    assert set(result)=={'rooms_with_participants','participants'} and all(isinstance(v,int) and v>=0 for v in result.values())
    return result

def selected_health(value):
    return {key: value.get(key) for key in ('mock', 'model_tier', 'tts_provider', 'stt_provider', 'runtime_providers')}

def operational_metadata():
    rows = []
    for path in (DATA / 'demos').glob('dm_*/demo.json'):
        if path.parent.name == 'dm_41513908':
            continue
        original = path.read_bytes()
        demo = json.loads(original)
        active = bool(demo.get('running')) or any(
            stage.get('status') == 'running' for stage in demo.get('stages', {}).values()
            if isinstance(stage, dict))
        # The API adds graph.is_running(), covering an active worker before its
        # next persisted stage marker. Never call the protected demo's API.
        with urllib.request.urlopen('http://127.0.0.1:8877/api/demos/' + path.parent.name, timeout=15) as response:
            worker_active = json.load(response).get('running')
        assert isinstance(worker_active, bool), 'Worker state must be explicit'
        # A persisted marker can outlive a crashed worker. Never alter the demo;
        # accept it as idle only with an explicitly inactive actual thread, an
        # unchanged file and both stored/file timestamps older than 24 hours.
        marker_age = time.time() - max(float(demo.get('updated_at') or 0), path.stat().st_mtime)
        stale = active and not worker_active and marker_age > 86400 and path.read_bytes() == original
        rows.append({'id': path.parent.name, 'active': worker_active or (active and not stale),
                     'stale_marker_ignored': bool(stale)})
    return rows
