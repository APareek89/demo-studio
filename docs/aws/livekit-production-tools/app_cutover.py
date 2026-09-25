"""Switch application code/runtime only; preserve shared data and prior drop-ins."""
import json
import os
import shutil
import signal
import time
import urllib.request
from app_common import *


def install_interrupt_handler():
    def interrupted(*_):
        raise InterruptedError('Application cutover interrupted')
    signal.signal(signal.SIGTERM, interrupted)


def local_json(path):
    with urllib.request.urlopen('http://127.0.0.1:8877' + path, timeout=5) as response:
        return json.load(response)


def healthy():
    for _ in range(30):
        try:
            return local_json('/api/health')
        except Exception:
            time.sleep(1)
    raise RuntimeError('App did not become healthy')


def private_hash(path):
    return run('sudo', 'sha256sum', path).stdout.split()[0]


def dropin():
    return ('[Service]\nWorkingDirectory=' + str(RELEASE) + '\n'
            'EnvironmentFile=' + str(LIVEKIT_ENV) + '\nExecStart=\nExecStart=' + str(PYTHON) +
            ' -m uvicorn server.app:app --host 127.0.0.1 --port 8877 --proxy-headers --forwarded-allow-ips 127.0.0.1\n')


def validate_rtc_receipt():
    path = RECEIPT / 'hosted-rtc.json'
    report = json.loads(path.read_text())
    assert isinstance(report.get('passed'), int) and report['passed'] == report.get('total') and report['passed'] >= 30
    assert report.get('provider_calls') == 0 and report.get('physical_microphone') is False
    assert report.get('transport') == 'real-hosted-livekit' and report.get('errors') == [] and report.get('blocked') == []
    assert report.get('rtc', {}).get('localType') == 'relay' and report['rtc'].get('relayUsesTLS') is True
    assert report['rtc'].get('localRelayProtocol') in ('tls', 'tcp')
    assert all(isinstance(report.get('frames', {}).get(key), int) and report['frames'][key] > 0 for key in ('received', 'forwarded'))
    return sha(path)


def main():
    os.umask(0o077)
    assert state('WorkingDirectory') == str(OLD) and state('ActiveState') == 'active'
    assert not privileged_exists(CONF), 'This release drop-in already exists'
    assert privileged_exists(AUTH) and privileged_exists(LIVEKIT_ENV)
    for service in ('caddy', 'haproxy', 'demo-livekit'):
        assert run('systemctl', 'is-active', service).stdout.strip() == 'active', service + ' must be ready'
    source_count = verify_source()
    verified = json.loads((RECEIPT / 'app-stage-verified.json').read_text())
    gates = json.loads((RECEIPT / 'app-staged-gates.ok.json').read_text())
    assert verified['commit'] == gates['commit'] == package()['commit']
    assert gates['source_manifest_sha256'] == verified['source_manifest_sha256'] == sha(RECEIPT / 'source-manifest.json')
    assert gates['passed'] == gates['total'] == 34 and gates['outbound_attempts'] == 0
    assert gates['mock'] is True and gates['isolated'] is True
    result_path = RECEIPT / gates['results']
    assert result_path.resolve().is_relative_to(RECEIPT.resolve()) and not result_path.is_symlink()
    assert gates['results_sha256'] == sha(result_path)
    rtc_hash = validate_rtc_receipt()
    activity = operational_metadata()
    save('app-idle-preflight-' + str(time.time_ns()) + '.json', activity)
    assert all(not row['active'] for row in activity), 'Active Build; leave service untouched'
    assert not (RELEASE / '.env').exists() and not (RELEASE / 'data').exists()
    assert shutil.disk_usage(RECEIPT).free > 2 * int(run('du', '-sb', DATA).stdout.split()[0]) + 512*1024*1024
    prior_health = selected_health(healthy())
    assert prior_health['mock'] is False and prior_health['model_tier'] == 'customer'
    env_hash, proxy_hash, auth_hash, rtc_env_hash = sha(ENV), private_hash(CADDY), private_hash(AUTH), private_hash(LIVEKIT_ENV)
    assert not (RECEIPT / 'app-data.before.tar.gz').exists(), 'Never overwrite a release backup'
    assert not (RECEIPT / 'app-service.before.private').exists()
    (RECEIPT / 'app-service.before.private').write_text(run('sudo', 'systemctl', 'cat', 'demo-studio').stdout)
    for source, name in ((ENV, 'app-environment.before.private'), (CADDY, 'app-Caddyfile.before.private'),
                         (AUTH, 'app-auth.before.private'), (LIVEKIT_ENV, 'app-runtime.before.private')):
        target = RECEIPT / name
        assert not target.exists()
        run('sudo', 'cp', '-p', source, target)
        run('sudo', 'chmod', '600', target)
    save('app-preflight.json', {'old': str(OLD), 'new': str(RELEASE), 'commit': package()['commit'],
         'source_files': source_count, 'environment_sha256': env_hash, 'caddy_sha256': proxy_hash,
         'auth_sha256': auth_hash, 'rtc_environment_sha256': rtc_env_hash, 'hosted_rtc_sha256': rtc_hash,
         'health': prior_health, 'old_exec': state('ExecStart')})
    stopped = False
    try:
        stopped = True
        run('sudo', 'systemctl', 'stop', 'demo-studio')
        assert state('ActiveState') == 'inactive'
        before = data_manifest()
        save('app-data.before.json', before)
        backup = RECEIPT / 'app-data.before.tar.gz'
        run('tar', '-I', 'gzip -1', '-cf', backup, '-C', '/opt/demo-studio', 'data', timeout=300)
        run('tar', '-tzf', backup, timeout=180)
        save('app-backup.json', {'bytes': backup.stat().st_size, 'sha256': sha(backup), 'files': len(before)})
        print('Stopped-service data backup verified.', flush=True)
        (RELEASE / '.env').symlink_to(ENV)
        (RELEASE / 'data').symlink_to(DATA)
        candidate = RECEIPT / 'app-release-service.conf'
        candidate.write_text(dropin())
        run('sudo', 'install', '-m', '644', candidate, CONF)
        run('sudo', 'systemctl', 'daemon-reload')
        run('sudo', 'systemctl', 'start', 'demo-studio')
        health = healthy()
        assert state('WorkingDirectory') == str(RELEASE) and state('ActiveState') == 'active'
        assert str(PYTHON) in state('ExecStart') and '--forwarded-allow-ips 127.0.0.1' in state('ExecStart')
        assert selected_health(health) == prior_health, 'Existing provider configuration changed'
        capability = local_json('/api/runtime/transport')
        assert capability == {'transport':'livekit', 'livekit_enabled':True, 'livekit_available':True, 'mode':'hosted'}
        assert sha(ENV) == env_hash and private_hash(CADDY) == proxy_hash
        assert private_hash(AUTH) == auth_hash and private_hash(LIVEKIT_ENV) == rtc_env_hash
        assert verify_source() == source_count
        after = data_manifest()
        save('app-data.after.json', after)
        missing = sorted(set(before) - set(after))
        changed = sorted(path for path in before.keys() & after.keys() if before[path] != after[path])
        added = sorted(set(after) - set(before))
        assert set(missing + changed + added) <= SQLITE, 'Unexpected demo changes during application release'
        save('app-verification.json', {'commit': package()['commit'], 'source_files': source_count,
             'existing_files_verified': len(before), 'missing': missing, 'changed': changed, 'added': added,
             'all_existing_demo_bytes_unchanged': True, 'environment_unchanged': True, 'caddy_unchanged': True,
             'operator_auth_unchanged': True, 'health': selected_health(health), 'capability': capability,
             'transport': 'livekit', 'livekit_adopted': True, 'shared_data_retained': True})
        (RECEIPT / 'app-cutover.completed').write_text(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) + '\n')
        print('LiveKit application cutover complete; existing demos and provider settings retained.', flush=True)
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
                    recover('sudo', 'mv', CONF, RECEIPT / 'app-failed-release-service.conf')
            except Exception as failure:
                errors.append({'step': 'inspect new drop-in', 'error': type(failure).__name__})
            # Each recovery step runs independently. Never restore data or alter
            # previous drop-ins: customer writes and the last known app survive.
            recover('sudo', 'systemctl', 'daemon-reload')
            recover('sudo', 'systemctl', 'start', 'demo-studio')
            try:
                assert selected_health(healthy()) == prior_health
                assert state('WorkingDirectory') == str(OLD) and state('ActiveState') == 'active'
            except Exception as failure:
                errors.append({'step': 'verify prior service', 'error': type(failure).__name__})
            save('app-rollback-' + str(time.time_ns()) + '.json', {'errors': errors, 'shared_data_retained': True,
                 'prior_dropins_retained': True, 'proxy_untouched': True, 'infrastructure_rollback_separate': True})
            print('Application cutover failed; prior app recovery attempted. Recovery errors: ' + str(len(errors)), flush=True)
        raise


if __name__ == '__main__':
    install_interrupt_handler()
    main()
