"""Verify public code, capability, media and privacy without questions or paid calls.

Root separately records an actual no-input LiveKit browser join after cutover.
This script does not issue valid tokens, open microphones or save customer visits.
"""
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from app_common import *

BASE = 'https://13-202-0-79.sslip.io'


def get(path, headers=None, *, body=None):
    try:
        request = urllib.request.Request(BASE + path, headers=headers or {}, data=body)
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read(), {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as error:
        return error.code, error.read(), {key.lower(): value for key, value in error.headers.items()}


def media_paths(value):
    if isinstance(value, str) and value.startswith('/media/dm_29df0418/'):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from media_paths(child)
    elif isinstance(value, list):
        for child in value:
            yield from media_paths(child)


def main():
    os.umask(0o077)
    checks = []
    def check(name, ok, **details):
        checks.append({'name': name, 'passed': bool(ok), **details})
        assert ok, name
    check('Correct source release active', state('WorkingDirectory') == str(RELEASE) and state('ActiveState') == 'active')
    check('All committed source bytes match', verify_source() == json.loads((RECEIPT / 'app-stage-verified.json').read_text())['source_files'])
    preflight = json.loads((RECEIPT / 'app-preflight.json').read_text())
    check('Shared provider environment unchanged', sha(ENV) == preflight['environment_sha256'])
    for path, key, name in ((CADDY, 'caddy_sha256', 'Caddy'), (AUTH, 'auth_sha256', 'Operator authentication'),
                            (LIVEKIT_ENV, 'rtc_environment_sha256', 'LiveKit configuration')):
        expected=preflight[key]
        if path==CADDY and (RECEIPT/'proxy-applied.json').exists():expected=json.loads((RECEIPT/'proxy-applied.json').read_text())['caddy_sha256']
        check(name + ' matches reviewed release state', run('sudo', 'sha256sum', path).stdout.split()[0] == expected)
    for service in ('caddy', 'haproxy', 'demo-livekit'):
        check(service + ' active', run('systemctl', 'is-active', service).stdout.strip() == 'active')
    status, body, _ = get('/api/health')
    check('Public health preserves configured real providers', status == 200 and selected_health(json.loads(body)) == preflight['health'])
    status, _, _ = get('/')
    check('Public shell loads', status == 200)
    for path in ('/favicon.ico','/apple-touch-icon.png','/apple-touch-icon-precomposed.png','/manifest.json'):
        status,_,headers=get(path)
        check('Optional browser asset has no operator challenge: '+path,status==404 and 'www-authenticate' not in headers)
    status, body, headers = get('/api/runtime/transport')
    expected_capability = {'transport':'livekit', 'livekit_enabled':True, 'livekit_available':True, 'mode':'hosted'}
    check('Normal public URLs select available hosted LiveKit', status == 200 and json.loads(body) == expected_capability)
    check('Transport discovery is not cached', 'no-store' in headers.get('cache-control', ''))
    for origin in (None, 'https://untrusted.invalid'):
        headers = {'Content-Type':'application/json'}
        if origin:
            headers['Origin'] = origin
        status, body, _ = get('/api/demos/dm_29df0418/run/livekit/token', headers,
                              body=b'{"session_id":"s_release_denied_origin"}')
        check('Token request denies ' + ('unapproved origin' if origin else 'missing origin'), status == 403)
        check('Denied token response contains no grant', b'"token"' not in body and b'"api_secret"' not in body)
    web = {path: digest for path, digest in source_manifest().items() if path.startswith('web/')}
    web_results = []
    for path, digest in web.items():
        status, body, _ = get('/' + path)
        web_results.append({'path': path, 'matched': status == 200 and hashlib.sha256(body).hexdigest() == digest})
    check('Every frontend file matches source', all(row['matched'] for row in web_results), files=len(web_results))
    status, body, _ = get('/api/demos/dm_29df0418/bundle')
    expected = json.loads((DATA / 'demos/dm_29df0418/bundle.json').read_text())
    check('Published BMW bundle retained', status == 200 and json.loads(body) == expected)
    paths = sorted(set(media_paths(expected)))
    for kind, suffixes in (('image', {'.jpg', '.jpeg', '.png', '.webp'}), ('audio', {'.mp3', '.wav', '.ogg'})):
        candidates = [path for path in paths if Path(urllib.parse.urlsplit(path).path).suffix.lower() in suffixes]
        assert candidates, 'BMW publication must have representative ' + kind
        path = candidates[0]
        relative = urllib.parse.unquote(urllib.parse.urlsplit(path).path).removeprefix('/media/')
        assert '..' not in Path(relative).parts
        local = DATA / 'demos' / relative
        assert local.resolve().is_relative_to((DATA / 'demos/dm_29df0418').resolve())
        with local.open('rb') as stream:
            prefix = stream.read(1024)
        status, body, _ = get(path, {'Range':'bytes=0-' + str(len(prefix)-1)})
        check('Published BMW ' + kind + ' supports exact byte ranges', status == 206 and body == prefix)
    for path in ('/api/demos', '/api/demos/dm_29df0418/sessions', '/api/demos/dm_29df0418/trace',
                 '/media/dm_29df0418/demo.json', '/media/dm_29df0418/knowledge/published.json', '/openapi.json'):
        status, _, _ = get(path)
        check('Private path still requires operator login: ' + path, status == 401)
    before = json.loads((RECEIPT / 'app-data.before.json').read_text())
    after = data_manifest()
    missing = sorted(set(before) - set(after))
    changed = sorted(path for path in before.keys() & after.keys() if before[path] != after[path])
    added = sorted(set(after) - set(before))
    check('Verification preserves all existing demo files', set(missing + changed + added) <= SQLITE)
    name = 'app-public-verification-' + str(time.time_ns()) + '.json'
    save(name, {'commit': package()['commit'], 'passed': len(checks), 'total': len(checks), 'checks': checks,
         'web_files': web_results, 'paid_calls': 0, 'data_missing': missing, 'data_changed': changed,
         'data_added': added, 'transport': 'livekit', 'livekit_adopted': True,
         'production_rtc_join': 'separate browser receipt required'})
    print(json.dumps({'passed': len(checks), 'total': len(checks), 'frontend_files': len(web), 'paid_calls': 0, 'receipt': name}))


if __name__ == '__main__':
    main()
