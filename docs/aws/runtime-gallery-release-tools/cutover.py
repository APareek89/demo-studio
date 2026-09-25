"""Code-only switch. Rollback owns only the new drop-in; never restore old data."""
import json
import os
import shutil
import time
import urllib.request
from release_common import *

os.umask(0o077)

def healthy():
    for _ in range(30):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8877/api/health', timeout=3) as response:
                return json.load(response)
        except Exception:
            time.sleep(1)
    raise RuntimeError('App did not become healthy')

assert state('WorkingDirectory') == str(OLD) and state('ActiveState') == 'active'
assert not privileged_exists(CONF), 'This release drop-in already exists'
assert privileged_exists(AUTH), 'Preserve the installed operator boundary'
assert run('systemctl', 'is-active', 'caddy').stdout.strip() == 'active'
source_count = verify_source()
verified = json.loads((RECEIPT / 'stage-verified.json').read_text())
gates = json.loads((RECEIPT / 'staged-gates.ok.json').read_text())
assert verified['commit'] == gates['commit'] == package()['commit']
assert gates['source_manifest_sha256'] == sha(RECEIPT / 'source-manifest.json')
assert gates['passed'] == gates['total'] >= 27 and gates['outbound_attempts'] == 0
assert gates['mock'] and gates['isolated']
assert gates['results_sha256'] == sha(RECEIPT / 'staged-gates.json')
activity = operational_metadata()
save('idle-preflight.json', activity)
assert all(not row['active'] for row in activity), 'Active Build; leave service untouched'
assert not (RELEASE / '.env').exists() and not (RELEASE / 'data').exists()
assert shutil.disk_usage(RECEIPT).free > 2 * int(run('du', '-sb', DATA).stdout.split()[0]) + 512*1024*1024

env_hash = sha(ENV)
proxy_hash = run('sudo', 'sha256sum', CADDY).stdout.split()[0]
auth_hash = run('sudo', 'sha256sum', AUTH).stdout.split()[0]
old_exec = state('ExecStart')
# Exact private service/environment snapshots are never printed or committed.
(RECEIPT / 'service.before.private').write_text(run('sudo', 'systemctl', 'cat', 'demo-studio').stdout)
run('sudo', 'cp', '-p', ENV, RECEIPT / 'environment.before.private')
run('sudo', 'chmod', '600', RECEIPT / 'environment.before.private')
run('sudo', 'cp', '-p', CADDY, RECEIPT / 'Caddyfile.before')
save('preflight.json', {'old': str(OLD), 'new': str(RELEASE), 'commit': package()['commit'],
     'source_files': source_count, 'environment_sha256': env_hash, 'caddy_sha256': proxy_hash})
stopped = False
try:
    stopped = True
    run('sudo', 'systemctl', 'stop', 'demo-studio')
    assert state('ActiveState') == 'inactive'
    before = data_manifest()
    save('data.before.json', before)
    backup = RECEIPT / 'data.before.tar.gz'
    assert not backup.exists(), 'Never overwrite a release backup'
    run('tar', '-I', 'gzip -1', '-cf', backup, '-C', '/opt/demo-studio', 'data', timeout=300)
    run('tar', '-tzf', backup, timeout=180)
    save('backup.json', {'bytes': backup.stat().st_size, 'sha256': sha(backup), 'files': len(before)})
    print('Stopped-service data backup verified.', flush=True)
    (RELEASE / '.env').symlink_to(ENV)
    (RELEASE / 'data').symlink_to(DATA)
    candidate = RECEIPT / 'release-service.conf'
    candidate.write_text('[Service]\nWorkingDirectory=' + str(RELEASE) + '\n')
    run('sudo', 'install', '-m', '644', candidate, CONF)
    run('sudo', 'systemctl', 'daemon-reload')
    run('sudo', 'systemctl', 'start', 'demo-studio')
    health = healthy()
    assert state('WorkingDirectory') == str(RELEASE) and state('ActiveState') == 'active'
    assert health.get('mock') is False and health.get('model_tier') == 'customer'
    assert health.get('tts_provider') == health.get('stt_provider') == 'sarvam'
    assert health.get('runtime_providers') == ['gemini', 'claude', 'runware']
    assert sha(ENV) == env_hash
    assert run('sudo', 'sha256sum', CADDY).stdout.split()[0] == proxy_hash
    assert run('sudo', 'sha256sum', AUTH).stdout.split()[0] == auth_hash
    assert verify_source() == source_count
    after = data_manifest()
    save('data.after.json', after)
    missing = sorted(set(before) - set(after))
    changed = sorted(path for path in before.keys() & after.keys() if before[path] != after[path])
    added = sorted(set(after) - set(before))
    assert set(missing + changed) <= SQLITE, 'Pre-existing demo files changed during code-only release'
    assert set(added) <= SQLITE, 'Unexpected new demo files during code-only release'
    save('verification.json', {'commit': package()['commit'], 'source_files': source_count,
         'existing_files_verified': len(before), 'missing': missing, 'changed': changed, 'added': added,
         'all_existing_demo_bytes_unchanged': True, 'environment_unchanged': True,
         'caddy_unchanged': True, 'operator_auth_unchanged': True,
         'health': selected_health(health), 'transport': 'existing_websocket', 'livekit_adopted': False})
    (RECEIPT / 'cutover.completed').write_text(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) + '\n')
    print('Code-only cutover complete; stored demo files, environment and proxy preserved.', flush=True)
except BaseException:
    if stopped:
        errors = []
        def recover(*args):
            try:
                run(*args)
            except Exception as failure:
                errors.append({'step': [str(x) for x in args[:4]], 'error': type(failure).__name__})
        recover('sudo', 'systemctl', 'stop', 'demo-studio')
        try:
            if privileged_exists(CONF):
                recover('sudo', 'mv', CONF, RECEIPT / 'failed-release-service.conf')
        except Exception as failure:
            errors.append({'step': 'inspect new drop-in', 'error': type(failure).__name__})
        # Independent recovery attempts: any failed step must not skip restarting the old app.
        recover('sudo', 'systemctl', 'daemon-reload')
        recover('sudo', 'systemctl', 'start', 'demo-studio')
        try:
            healthy()
            assert state('WorkingDirectory') == str(OLD) and state('ActiveState') == 'active'
        except Exception as failure:
            errors.append({'step': 'verify prior service', 'error': type(failure).__name__})
        save('rollback.json', {'errors': errors, 'shared_data_retained': True, 'proxy_untouched': True})
        print('Cutover failed; prior app recovery attempted. Recovery errors: ' + str(len(errors)), flush=True)
    raise
